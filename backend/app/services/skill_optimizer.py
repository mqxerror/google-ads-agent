"""Skill Optimizer — Autoresearch loop for role prompts.

Applies Karpathy's autoresearch pattern to role skill files:
Modify → Evaluate → Keep or Discard → Repeat

Each optimization cycle:
1. Loads the current skill file
2. Gathers outcome data, user corrections, marketing context
3. Asks Haiku to rewrite the skill based on evidence
4. Scores the new skill vs old skill
5. Keeps the better version
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.database import get_db
from app.services.skill_loader import (
    load_skill, save_skill, get_latest_version, seed_skill_from_role,
    ROLE_ACTION_DOMAINS,
)

logger = logging.getLogger(__name__)

# Eval criteria per role
ROLE_EVAL_CRITERIA = {
    "ppc_strategist": {"primary": "cpa_reduction", "secondary": "roas_improvement", "guard": "spend_efficiency"},
    "search_term_hunter": {"primary": "waste_reduction", "secondary": "quality_score", "guard": "impression_volume"},
    "creative_director": {"primary": "ctr_improvement", "secondary": "ad_strength", "guard": "conversion_rate"},
    "cro_specialist": {"primary": "conversion_rate", "secondary": "page_speed", "guard": "bounce_rate"},
    "gtm_specialist": {"primary": "tracking_accuracy", "secondary": "tag_load_time", "guard": "data_integrity"},
    "analytics_analyst": {"primary": "insight_quality", "secondary": "data_accuracy", "guard": "actionability"},
    "competitor_intel": {"primary": "intel_accuracy", "secondary": "opportunity_detection", "guard": "relevance"},
    "growth_hacker": {"primary": "growth_rate", "secondary": "experiment_quality", "guard": "risk_management"},
    "director": {"primary": "routing_accuracy", "secondary": "synthesis_quality", "guard": "response_time"},
}


async def optimize_role_skill(account_id: str, role_id: str) -> dict:
    """Run one optimization cycle for a role's skill file.

    Returns: {"status": "optimized"|"skipped"|"discarded", "version": int, ...}
    """
    from app.services.roles import ROLES

    role = ROLES.get(role_id)
    if not role:
        return {"status": "error", "reason": f"Unknown role: {role_id}"}

    # Seed skill if it doesn't exist
    current_skill = load_skill(account_id, role_id)
    if not current_skill:
        seed_skill_from_role(account_id, role_id, role.system_prompt, role.name)
        current_skill = load_skill(account_id, role_id)

    # Gather evidence
    outcomes = await _get_role_outcomes(account_id, role_id)
    user_corrections = await _get_user_corrections(account_id)
    account_knowledge = _get_account_knowledge(account_id)

    # Need at least some data to optimize
    if not outcomes and not user_corrections and not account_knowledge:
        return {"status": "skipped", "reason": "No outcomes, corrections, or account knowledge to learn from"}

    # Build optimization prompt
    prompt = _build_optimization_prompt(
        role_name=role.name,
        role_id=role_id,
        current_skill=current_skill,
        outcomes=outcomes,
        user_corrections=user_corrections,
        account_knowledge=account_knowledge,
        eval_criteria=ROLE_EVAL_CRITERIA.get(role_id, {}),
    )

    # Call Haiku for optimization
    new_skill = await _call_haiku(prompt)
    if not new_skill or len(new_skill) < 100:
        return {"status": "error", "reason": "Optimizer returned empty or too short result"}

    # Score comparison
    old_score = _score_skill_content(current_skill)
    new_score = _score_skill_content(new_skill)

    if new_score < old_score * 0.8:  # New skill is significantly worse
        logger.info("Discarding optimization for %s: score %d → %d (worse)", role_id, old_score, new_score)
        return {"status": "discarded", "reason": f"New skill scored lower ({new_score} vs {old_score})"}

    # Update header with version info
    old_version = get_latest_version(account_id, role_id)
    new_version = old_version + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Ensure the header line is updated
    if "Version:" in new_skill:
        lines = new_skill.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("Version:"):
                lines[i] = f"Version: {new_version} | Last optimized: {now} | Success rate: {_compute_success_rate(outcomes)}"
                break
        new_skill = "\n".join(lines)

    # Save new version
    save_skill(account_id, role_id, new_skill, version=new_version)

    # Record optimization event
    await _record_optimization(
        account_id, role_id, old_version, new_version,
        outcomes_count=len(outcomes),
        corrections_count=len(user_corrections),
        score_before=old_score, score_after=new_score,
    )

    logger.info(
        "Optimized %s v%d → v%d (score %d → %d, %d outcomes, %d corrections)",
        role_id, old_version, new_version, old_score, new_score,
        len(outcomes), len(user_corrections),
    )

    return {
        "status": "optimized",
        "role_id": role_id,
        "from_version": old_version,
        "to_version": new_version,
        "score_before": old_score,
        "score_after": new_score,
        "outcomes_used": len(outcomes),
        "corrections_applied": len(user_corrections),
    }


async def optimize_all_roles(account_id: str) -> list[dict]:
    """Run optimization for all roles that have enough data."""
    from app.services.roles import ROLES

    results = []
    for role_id in ROLES:
        try:
            result = await optimize_role_skill(account_id, role_id)
            results.append(result)
        except Exception as e:
            logger.warning("Optimization failed for %s: %s", role_id, e)
            results.append({"status": "error", "role_id": role_id, "reason": str(e)})

    return results


async def score_skill(account_id: str, role_id: str) -> dict:
    """Score a role's current skill based on outcome history."""
    outcomes = await _get_role_outcomes(account_id, role_id)
    current_skill = load_skill(account_id, role_id)
    version = get_latest_version(account_id, role_id)

    total = len(outcomes)
    measured = sum(1 for o in outcomes if o.get("status") == "measured")
    improved = sum(1 for o in outcomes if o.get("outcome") == "improved")

    return {
        "role_id": role_id,
        "version": version,
        "skill_score": _score_skill_content(current_skill) if current_skill else 0,
        "total_recommendations": total,
        "measured": measured,
        "improved": improved,
        "success_rate": round(improved / measured * 100) if measured > 0 else None,
        "has_skill_file": current_skill is not None,
    }


# ── Internal helpers ──────────────────────────────────────────────


async def _get_role_outcomes(account_id: str, role_id: str) -> list[dict]:
    """Get outcomes relevant to this role's domain."""
    action_types = ROLE_ACTION_DOMAINS.get(role_id, [])
    if not action_types:
        return []

    db = await get_db()
    try:
        placeholders = ",".join("?" for _ in action_types)
        cur = await db.execute(
            f"""SELECT action_type, action_detail, outcome, outcome_delta_json,
                       status, executed_at, measured_at
                FROM recommendations
                WHERE account_id = ? AND action_type IN ({placeholders})
                ORDER BY executed_at DESC LIMIT 30""",
            (account_id, *action_types),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


async def _get_user_corrections(account_id: str) -> list[str]:
    """Extract user corrections from pinned facts across all campaigns."""
    memory_dir = settings.MEMORY_DIR / account_id
    corrections = []
    if not memory_dir.exists():
        return corrections

    for campaign_dir in memory_dir.iterdir():
        if not campaign_dir.is_dir():
            continue
        pinned = campaign_dir / "pinned_facts.md"
        if not pinned.exists():
            continue
        for line in pinned.read_text(encoding="utf-8").split("\n"):
            if "source: user" in line.lower() or "source: user correction" in line.lower():
                # Extract the fact text
                fact = line.strip().lstrip("- ")
                if fact and len(fact) > 10:
                    corrections.append(fact)

    return corrections


def _get_account_knowledge(account_id: str) -> str:
    """Load account-wide memory for context."""
    account_mem = settings.MEMORY_DIR / account_id / "ACCOUNT_MEMORY.md"
    if account_mem.exists():
        return account_mem.read_text(encoding="utf-8")
    return ""


def _build_optimization_prompt(
    role_name: str,
    role_id: str,
    current_skill: str,
    outcomes: list[dict],
    user_corrections: list[str],
    account_knowledge: str,
    eval_criteria: dict,
) -> str:
    """Build the prompt for the optimizer model to rewrite the skill file."""

    # Format outcomes table
    outcomes_text = "No measured outcomes yet."
    if outcomes:
        lines = ["| Date | Action | Outcome | Details |", "|------|--------|---------|---------|"]
        for o in outcomes:
            date = (o.get("executed_at") or "")[:10]
            action = o.get("action_detail", "")[:40]
            outcome = o.get("outcome") or o.get("status", "pending")
            delta = ""
            if o.get("outcome_delta_json"):
                try:
                    d = json.loads(o["outcome_delta_json"])
                    if "cpa_change_pct" in d:
                        delta = f"CPA {d['cpa_change_pct']:+.1f}%"
                except (json.JSONDecodeError, KeyError):
                    pass
            lines.append(f"| {date} | {action} | {outcome} | {delta} |")
        outcomes_text = "\n".join(lines)

    corrections_text = "\n".join(f"- {c}" for c in user_corrections) if user_corrections else "No user corrections."

    criteria_text = ""
    if eval_criteria:
        criteria_text = f"""
Eval criteria for this role:
- Primary metric: {eval_criteria.get('primary', 'N/A')}
- Secondary metric: {eval_criteria.get('secondary', 'N/A')}
- Guard rail: {eval_criteria.get('guard', 'N/A')}"""

    return f"""You are a skill optimizer for a {role_name} in a Google Ads campaign management platform.

Your job: analyze what worked and what failed, then REWRITE the skill file to make this role smarter.

CURRENT SKILL FILE:
{current_skill}

OUTCOME DATA (what this role recommended and what actually happened):
{outcomes_text}

USER CORRECTIONS (explicit feedback from the account owner):
{corrections_text}

ACCOUNT KNOWLEDGE:
{account_knowledge or "None yet."}
{criteria_text}

INSTRUCTIONS:
1. REINFORCE techniques that led to improved outcomes — move them higher, add evidence
2. ADD CAUTIONS for techniques that led to degraded outcomes — explain when NOT to use them
3. INCORPORATE every user correction as a firm rule in Anti-Patterns
4. UPDATE Account Knowledge with any new facts from outcomes
5. ADD concrete techniques based on successful patterns (be specific, not generic)
6. REMOVE or demote vague/untested advice
7. Keep the SAME markdown structure (Core Identity, Techniques, Anti-Patterns, Account Knowledge, Recent Learnings, Marketing Intelligence)
8. Update the Version line at the top

The skill should read like advice from a veteran who has managed THIS specific account — not generic textbook knowledge.

Return ONLY the updated skill file markdown. No explanation or commentary."""


def _score_skill_content(skill: str | None) -> int:
    """Score a skill file's quality based on content richness.

    Higher scores for: concrete techniques, evidence-backed rules,
    account-specific knowledge, anti-patterns.
    """
    if not skill:
        return 0

    score = 0
    lines = skill.split("\n")

    for line in lines:
        stripped = line.strip()
        # Concrete techniques (bullet points with actionable content)
        if stripped.startswith("- ") and len(stripped) > 20 and "Auto-populated" not in stripped:
            score += 2
        # Evidence references
        if any(kw in stripped.lower() for kw in ["evidence:", "success rate", "times", "failed", "improved"]):
            score += 3
        # Account-specific knowledge
        if any(kw in stripped.lower() for kw in ["this account", "conversion:", "campaign:", "tracking:"]):
            score += 2
        # Anti-patterns (learning from mistakes)
        if stripped.startswith("- Don't") or stripped.startswith("- Never") or stripped.startswith("- Avoid"):
            score += 3
        # Sections with content
        if stripped.startswith("## ") and not stripped.endswith("-->"):
            score += 1

    return score


def _compute_success_rate(outcomes: list[dict]) -> str:
    """Compute success rate string from outcomes."""
    measured = [o for o in outcomes if o.get("status") == "measured"]
    if not measured:
        return "N/A"
    improved = sum(1 for o in measured if o.get("outcome") == "improved")
    return f"{round(improved / len(measured) * 100)}% ({improved}/{len(measured)})"


async def _call_haiku(prompt: str) -> str | None:
    """Call Haiku to optimize a skill file."""
    try:
        node_path = shutil.which("node") or "node"

        # Find CLI
        import glob
        cli_candidates = [
            Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
            Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
            Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
        ]
        cli_js = None
        for p in cli_candidates:
            if p.exists():
                cli_js = p
                break
        if not cli_js:
            nvm_matches = glob.glob(str(Path.home() / ".nvm/versions/node/*/lib/node_modules/@anthropic-ai/claude-code/cli.js"))
            if nvm_matches:
                cli_js = Path(nvm_matches[0])
        if not cli_js:
            try:
                result = subprocess.run([shutil.which("npm") or "npm", "root", "-g"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    candidate = Path(result.stdout.strip()) / "@anthropic-ai/claude-code/cli.js"
                    if candidate.exists():
                        cli_js = candidate
            except Exception:
                pass

        if not cli_js:
            logger.warning("Claude CLI not found for skill optimization")
            return None

        cmd = [
            node_path, str(cli_js),
            "--print", "--verbose", "--output-format", "stream-json",
            "--max-turns", "1",
            "--model", "claude-sonnet-4-6",
            "--permission-mode", "bypassPermissions",
        ]

        env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE_SESSION", None)

        proc = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=180, env=env)

        if proc.returncode != 0:
            logger.warning("Skill optimization CLI failed (rc=%d): %s", proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:300])
            return None

        text_parts = []
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json
                data = json.loads(line)
                if data.get("type") == "assistant":
                    for block in data.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
            except (json.JSONDecodeError, KeyError):
                continue

        return "\n".join(text_parts) if text_parts else None

    except subprocess.TimeoutExpired:
        logger.warning("Skill optimization timed out (180s)")
        return None
    except Exception as e:
        logger.warning("Skill optimization error: %s", e)
        return None


async def _record_optimization(
    account_id: str, role_id: str,
    from_version: int, to_version: int,
    outcomes_count: int, corrections_count: int,
    score_before: int, score_after: int,
):
    """Record an optimization event in the database."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO skill_optimizations
               (id, account_id, role_id, from_version, to_version,
                changes_summary, score_before, score_after)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), account_id, role_id,
                from_version, to_version,
                f"Used {outcomes_count} outcomes, {corrections_count} user corrections",
                score_before, score_after,
            ),
        )
        await db.commit()
    except Exception as e:
        logger.warning("Failed to record optimization: %s", e)
    finally:
        await db.close()
