"""E7 — Suggest edits to guideline files.

Reads recent agent sessions + user corrections + decisions, asks Haiku to
propose a refined guideline file. Returns the proposal as a stored row in
`guideline_proposals` so the user can review the diff before applying.

Pattern mirrors `skill_optimizer.py` but with two key differences:
  1. **Suggest, don't auto-apply.** The user always reviews the diff first.
  2. **Operates on guideline markdown files** (account-scoped) instead of
     per-role skill files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.database import get_db
from app.services.guidelines import GuidelinesService

logger = logging.getLogger(__name__)


# How much evidence to gather. Keep these tight to stay within Haiku's effective
# context — the optimizer doesn't need every message ever, just recent signal.
RECENT_MESSAGES_LIMIT = 60
USER_CORRECTIONS_LIMIT = 25
DECISIONS_LIMIT = 30


# ── Public API ──────────────────────────────────────────────────────


async def suggest_guideline_edits(
    account_id: str,
    filename: str,
    *,
    extra_focus: Optional[str] = None,
) -> dict:
    """Generate one suggestion. Returns the persisted proposal row as a dict.

    `extra_focus` lets the user nudge the optimizer ("focus on UK ad copy
    rules" / "add anything we learned about Panama"). Optional.
    """
    svc = GuidelinesService()
    try:
        current = svc.read_file(filename)
    except FileNotFoundError:
        return {"status": "error", "reason": f"Guideline file not found: {filename}"}

    current_content = current.content
    if not current_content.strip():
        return {"status": "error", "reason": "Guideline file is empty"}

    # Gather evidence
    sessions = await _get_recent_sessions(account_id, limit=RECENT_MESSAGES_LIMIT)
    corrections = await _get_user_corrections(account_id, limit=USER_CORRECTIONS_LIMIT)
    decisions = _get_recent_decisions(account_id, limit=DECISIONS_LIMIT)

    if not sessions and not corrections and not decisions:
        return {"status": "skipped", "reason": "No recent sessions, corrections, or decisions to learn from"}

    prompt = _build_prompt(
        filename=filename,
        current_content=current_content,
        sessions=sessions,
        corrections=corrections,
        decisions=decisions,
        extra_focus=extra_focus,
    )

    raw = await _call_haiku(prompt)
    if not raw:
        return {"status": "error", "reason": "Optimizer returned no output"}

    proposed_content, rationale, evidence = _parse_optimizer_output(raw)
    if not proposed_content or len(proposed_content) < 100:
        return {"status": "error", "reason": "Proposed content is empty or too short — model may have refused"}

    # No-op detection — if the proposed content is identical, don't store noise.
    if proposed_content.strip() == current_content.strip():
        return {"status": "skipped", "reason": "No changes proposed — guideline is already aligned"}

    # Persist as a pending proposal
    proposal_id = str(uuid.uuid4())
    based_on_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO guideline_proposals
               (id, account_id, filename, based_on_hash, based_on_content,
                proposed_content, rationale, evidence_summary, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (proposal_id, account_id, filename, based_on_hash, current_content,
             proposed_content, rationale, evidence),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT * FROM guideline_proposals WHERE id = ?", (proposal_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    return {"status": "proposed", "proposal": _row_to_dict(row)}


async def list_proposals(account_id: str, filename: Optional[str] = None,
                         status: Optional[str] = None, limit: int = 30) -> list[dict]:
    """List proposals for the account (newest first), optionally filtered."""
    sql = "SELECT * FROM guideline_proposals WHERE account_id = ?"
    params: list = [account_id]
    if filename:
        sql += " AND filename = ?"
        params.append(filename)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    db = await get_db()
    try:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()


async def apply_proposal(account_id: str, proposal_id: str) -> dict:
    """Apply a proposal to disk. Refuses if the file changed since the proposal
    was generated (avoids overwriting a manual edit)."""
    svc = GuidelinesService()

    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM guideline_proposals WHERE id = ? AND account_id = ?",
            (proposal_id, account_id),
        )
        row = await cur.fetchone()
        if not row:
            return {"status": "error", "reason": "Proposal not found"}
        if row["status"] != "pending":
            return {"status": "error", "reason": f"Proposal already {row['status']}"}

        # Stale check — has the underlying file changed since we generated this?
        current = svc.read_file(row["filename"])
        live_hash = hashlib.sha256(current.content.encode("utf-8")).hexdigest()
        if live_hash != row["based_on_hash"]:
            await db.execute(
                "UPDATE guideline_proposals SET status = 'stale' WHERE id = ?",
                (proposal_id,),
            )
            await db.commit()
            return {
                "status": "stale",
                "reason": "Guideline file has been modified since this suggestion was generated. Generate a fresh suggestion.",
            }

        # Atomic write via the existing service
        svc.write_file(row["filename"], row["proposed_content"])

        await db.execute(
            "UPDATE guideline_proposals SET status = 'applied', applied_at = datetime('now') WHERE id = ?",
            (proposal_id,),
        )
        await db.commit()
        return {"status": "applied"}
    finally:
        await db.close()


async def discard_proposal(account_id: str, proposal_id: str) -> dict:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE guideline_proposals SET status = 'discarded' "
            "WHERE id = ? AND account_id = ? AND status = 'pending'",
            (proposal_id, account_id),
        )
        await db.commit()
        return {"status": "discarded"}
    finally:
        await db.close()


# ── Evidence gathering ──────────────────────────────────────────────


async def _get_recent_sessions(account_id: str, limit: int) -> list[dict]:
    """Pull recent assistant messages across this account's conversations.

    These are the actual answers the agent has been giving — the optimizer
    looks at them to spot patterns the guideline should encode (e.g. recurring
    advice the agent re-derives every time, or angles it keeps proposing that
    are now standard).
    """
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT m.content, m.created_at, c.campaign_name, m.agent_role_name
               FROM messages m
               JOIN conversations c ON c.id = m.conversation_id
               WHERE c.account_id = ? AND m.role = 'assistant'
               ORDER BY m.created_at DESC LIMIT ?""",
            (account_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def _get_user_corrections(account_id: str, limit: int) -> list[str]:
    """Pull recent USER messages that look like corrections / pushback.

    Heuristic: short user messages containing words like 'no', 'wrong',
    "don't", 'instead', 'actually', 'correct' — strongest signal of where
    the guideline disagrees with how the user actually wants to operate.
    """
    correction_words = ("no", "wrong", "don't", "instead", "actually", "correct", "stop", "never")
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT m.content FROM messages m
               JOIN conversations c ON c.id = m.conversation_id
               WHERE c.account_id = ? AND m.role = 'user' AND length(m.content) < 600
               ORDER BY m.created_at DESC LIMIT 300""",
            (account_id,),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()

    out: list[str] = []
    for r in rows:
        text = (r["content"] or "").strip()
        lower = text.lower()
        if any(w in lower for w in correction_words):
            out.append(text)
            if len(out) >= limit:
                break
    return out


def _get_recent_decisions(account_id: str, limit: int) -> list[str]:
    """Pull recent decision-log entries from per-campaign memory folders."""
    from app.config import settings as S
    root = S.MEMORY_DIR / account_id
    if not root.is_dir():
        return []

    entries: list[tuple[str, str]] = []  # (timestamp, line)
    for camp_dir in root.iterdir():
        if not camp_dir.is_dir() or camp_dir.name.startswith(("_", ".", "build-")):
            continue
        decisions = camp_dir / "decisions.md"
        if not decisions.is_file():
            continue
        try:
            for line in decisions.read_text(encoding="utf-8").splitlines():
                if not line.startswith("|") or "----" in line or "Date" in line:
                    continue
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    entries.append((cells[0], " | ".join(cells)))
        except Exception:
            continue

    entries.sort(key=lambda x: x[0], reverse=True)
    return [line for _, line in entries[:limit]]


# ── Prompt + parser ────────────────────────────────────────────────


_OPTIMIZER_SYSTEM_PREAMBLE = """You are a senior PPC operations editor whose job is to keep a marketing agency's GUIDELINE files accurate, useful, and consistent with how the team actually operates.

You are NOT writing campaign analysis. You are EDITING a markdown guideline file.

Your output MUST follow this exact structure (do not deviate, do not add commentary outside these blocks):

<rationale>
2-5 short sentences explaining what you changed and WHY, citing the evidence you used.
</rationale>

<evidence>
Bullet list of the specific sessions/corrections/decisions that motivated each change.
</evidence>

<proposed_file>
The COMPLETE proposed contents of the guideline file, in markdown. This replaces the entire file when the user accepts. Do not include partial diffs — output the full new file.
</proposed_file>

Editing rules:
- Preserve the file's existing structure, headings, and tone.
- Only add, modify, or remove lines that the evidence supports.
- Do NOT invent metrics, claims, currencies, or rules that aren't already in the file or supported by the evidence.
- If a section already says X correctly, leave it alone.
- If the evidence contradicts the file, fix the file.
- If the evidence reveals a recurring rule the file is missing, add it.
- Mark new/changed lines lightly with `<!-- new -->` or `<!-- updated -->` HTML comments only if you think it'll help the reviewer — otherwise omit.
- Never reduce the file by more than 30% — if you'd remove that much, surface it in the rationale and stop.
"""


def _build_prompt(*, filename: str, current_content: str,
                  sessions: list[dict], corrections: list[str],
                  decisions: list[str], extra_focus: Optional[str]) -> str:
    parts = [_OPTIMIZER_SYSTEM_PREAMBLE, "", f"# Guideline file: {filename}", "", "## CURRENT CONTENTS", "```markdown", current_content, "```", ""]

    if sessions:
        parts.append("## RECENT AGENT SESSIONS (most recent first)")
        for s in sessions[:30]:
            label = s.get("agent_role_name") or "agent"
            camp = s.get("campaign_name") or "(no campaign)"
            body = (s.get("content") or "").strip()[:400]
            parts.append(f"- [{label} · {camp}] {body}")
        parts.append("")

    if corrections:
        parts.append("## USER CORRECTIONS (recent pushback / 'no' / 'instead' messages)")
        for c in corrections:
            parts.append(f"- {c[:300]}")
        parts.append("")

    if decisions:
        parts.append("## RECENT DECISIONS (from per-campaign decision logs)")
        for d in decisions[:30]:
            parts.append(f"- {d[:300]}")
        parts.append("")

    if extra_focus:
        parts.append(f"## EXTRA FOCUS FROM THE REVIEWER\n{extra_focus.strip()}\n")

    parts.append("Now produce the three blocks: <rationale>, <evidence>, <proposed_file>. Output nothing else.")
    return "\n".join(parts)


def _parse_optimizer_output(raw: str) -> tuple[str, str, str]:
    """Pull the three blocks from the model's output. Returns (proposed, rationale, evidence)."""
    import re
    def grab(tag: str) -> str:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""
    proposed = grab("proposed_file")
    # The model may wrap proposed_file in a markdown fence — strip it.
    if proposed.startswith("```"):
        lines = proposed.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        proposed = "\n".join(lines).strip()
    return proposed, grab("rationale"), grab("evidence")


# ── Claude CLI runner (copied + trimmed from skill_optimizer for isolation) ─


async def _call_haiku(prompt: str) -> Optional[str]:
    """One-shot Claude CLI call returning concatenated text output."""
    try:
        node_path = shutil.which("node") or "node"

        import glob
        cli_candidates = [
            Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
            Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
            Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
        ]
        cli_js = next((p for p in cli_candidates if p.exists()), None)
        if not cli_js:
            nvm = glob.glob(str(Path.home() / ".nvm/versions/node/*/lib/node_modules/@anthropic-ai/claude-code/cli.js"))
            if nvm:
                cli_js = Path(nvm[0])
        if not cli_js:
            try:
                r = subprocess.run([shutil.which("npm") or "npm", "root", "-g"], capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    candidate = Path(r.stdout.strip()) / "@anthropic-ai/claude-code/cli.js"
                    if candidate.exists():
                        cli_js = candidate
            except Exception:
                pass
        if not cli_js:
            logger.warning("Claude CLI not found for guideline_optimizer")
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

        proc = subprocess.run(cmd, input=prompt.encode("utf-8"), capture_output=True, timeout=240, env=env)
        if proc.returncode != 0:
            logger.warning("guideline_optimizer CLI failed (rc=%d): %s",
                           proc.returncode, proc.stderr.decode("utf-8", errors="replace")[:300])
            return None

        text_parts: list[str] = []
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "assistant":
                    for block in data.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
            except (json.JSONDecodeError, KeyError):
                continue
        return "\n".join(text_parts) if text_parts else None
    except subprocess.TimeoutExpired:
        logger.warning("guideline_optimizer timed out (240s)")
        return None
    except Exception as e:
        logger.warning("guideline_optimizer error: %s", e)
        return None


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "filename": row["filename"],
        "based_on_hash": row["based_on_hash"],
        "based_on_content": row["based_on_content"],
        "proposed_content": row["proposed_content"],
        "rationale": row["rationale"],
        "evidence_summary": row["evidence_summary"],
        "status": row["status"],
        "applied_at": row["applied_at"],
        "created_at": row["created_at"],
    }
