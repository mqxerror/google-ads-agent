"""Multi-stage image-prompt drafter for Studio.

Replaces the original single-shot `extract_brief` Claude call with a
two-stage pipeline modeled on meta-ads-agent's `intent_decomposer.py`:

  Stage 1 — Decompose
    Input:  fetched landing page (title, description, og, h1, body)
    Output: structured brief (subject, setting, value_prop, audience,
            tone, hard_constraints) as JSON

  Stage 2 — Draft 3 angle variants
    Input:  stage-1 brief + visual_director role file + campaign's
            pinned_facts.md
    Output: 3 prompts (problem-led / aspirational / social-proof)
            each grounded in the firm rules and pinned claims

Why two stages: the original 40-line system prompt produced one
generic prompt. Splitting it lets Stage 2 receive a clean structured
brief (not raw HTML soup) AND lets us inject the operator-verified
pinned claims + the firm's full visual rulebook (visual_director.md,
~300 lines) without each call dragging the unrelated HTML through
Claude's attention.

Both stages use the `claude` CLI in --print mode (same subprocess
pattern agent.py uses). Sonnet by default; 45s timeout per stage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────


# Roles and memory paths live under the project's existing layout
# (data/roles/{account_id}/<role>.md and
#  data/memory/{account_id}/{campaign_id}/pinned_facts.md).
_ROLES_DIR = settings.PROJECT_ROOT.parent / "data" / "roles"
_MEMORY_DIR = settings.PROJECT_ROOT.parent / "data" / "memory"

# Per-stage Claude budget. Stage 1 is regex-shaped and fast (~5s);
# Stage 2 is the meaty drafting call. Keep tight so the operator
# doesn't wait > ~25s total for a brief extract.
_STAGE_TIMEOUT_S = 45.0


# ── Public API ────────────────────────────────────────────────────────


async def draft_variants(
    *,
    page: dict[str, Any],
    target: str,                 # 'image' | 'video'
    account_id: str | None,
    campaign_id: str | None,
) -> dict[str, Any]:
    """Run the 2-stage pipeline and return the variant package.

    Returns:
        {
            "brief": {subject, setting, value_prop, audience, tone, ...},
            "variants": [
                {"angle": "problem-led", "prompt": "...", "rationale": "..."},
                {"angle": "aspirational", "prompt": "...", "rationale": "..."},
                {"angle": "social-proof", "prompt": "...", "rationale": "..."},
            ],
            "pinned_claims_used": [<list of claim strings>],
        }

    All exceptions raise with a structured `message` attribute so the
    router can surface them to the UI without leaking raw stack
    traces.
    """
    brief = await _stage1_decompose(page=page, target=target)
    pinned = _load_pinned_claims(account_id=account_id, campaign_id=campaign_id)
    visual_director = _load_role_md(account_id=account_id, role="visual_director")
    variants = await _stage2_draft(
        brief=brief,
        target=target,
        pinned_claims=pinned,
        visual_director_system=visual_director,
    )
    return {
        "brief": brief,
        "variants": variants,
        "pinned_claims_used": pinned,
    }


# ── Stage 1: page → structured brief ──────────────────────────────────


_STAGE1_SYSTEM = (
    "You are a creative-brief decomposer. Given a landing page's content, "
    "extract the structured brief a visual director needs to produce ad creative. "
    "Output ONLY a JSON object — no preamble, no markdown fence, no explanation.\n\n"
    "Schema:\n"
    "{\n"
    "  \"subject\":          <one-line description of the human subject(s) implied — age range, role, NOT identity>,\n"
    "  \"setting\":          <one-line description of the program-specific location/setting>,\n"
    "  \"value_prop\":       <one short sentence: what is the investor buying / gaining>,\n"
    "  \"audience\":         <one short phrase: who is this for>,\n"
    "  \"tone\":             <one of: contemplative, aspirational, institutional, mixed>,\n"
    "  \"program\":          <one of: greece, portugal, panama, caribbean, uae, canada, other>,\n"
    "  \"hard_constraints\": [<list of MUST-NOT items derived from the page — e.g. 'no eligibility language', 'no third-party brands visible'>],\n"
    "  \"claim_hints\":      [<list of credibility claims the page itself makes — these may or may not be pinned, but they ground Stage 2 in what the page promises>]\n"
    "}\n\n"
    "Rules:\n"
    " - NEVER include identity (named individuals).\n"
    " - 'subject' is archetypal (\"a man in his 50s\", \"a multigenerational family\"), not a person.\n"
    " - If the page references a specific country/program, set 'program' precisely; default to 'other'.\n"
    " - 'claim_hints' captures what the page says; don't editorialize.\n"
)


async def _stage1_decompose(*, page: dict[str, Any], target: str) -> dict[str, Any]:
    """Stage 1: structured-brief extraction from raw page signals."""
    user = (
        f"Target creative format: {target}\n\n"
        f"Page URL: {page.get('url')}\n"
        f"Title: {page.get('title') or '(none)'}\n"
        f"Meta description: {page.get('description') or '(none)'}\n"
        f"H1: {page.get('h1') or '(none)'}\n"
        f"OG tags: {json.dumps(page.get('og') or {})}\n\n"
        f"Body excerpt (first 2k chars):\n{(page.get('body_excerpt') or '')[:2000]}\n\n"
        f"Return the JSON brief now."
    )
    raw = await _claude_one_shot(system=_STAGE1_SYSTEM, user=user)
    parsed = _parse_json_envelope(raw)
    # Don't crash on partial output — fill missing keys with safe
    # defaults so Stage 2 always has a workable brief.
    return {
        "subject": str(parsed.get("subject") or "an investor in their 40s-60s"),
        "setting": str(parsed.get("setting") or "a program-appropriate setting"),
        "value_prop": str(parsed.get("value_prop") or "residency-by-investment"),
        "audience": str(parsed.get("audience") or "HNW investors"),
        "tone": str(parsed.get("tone") or "mixed"),
        "program": str(parsed.get("program") or "other"),
        "hard_constraints": list(parsed.get("hard_constraints") or []),
        "claim_hints": list(parsed.get("claim_hints") or []),
    }


# ── Stage 2: brief + role + pinned → 3 angle variants ────────────────


async def _stage2_draft(
    *,
    brief: dict[str, Any],
    target: str,
    pinned_claims: list[str],
    visual_director_system: str,
) -> list[dict[str, Any]]:
    """Stage 2: produce three angle variants using the visual_director
    role file as the system prompt + pinned claims + structured brief."""
    target_label = "video" if target == "video" else "image"

    pinned_block = ""
    if pinned_claims:
        pinned_lines = "\n".join(f"  - {c}" for c in pinned_claims)
        pinned_block = (
            "\nPINNED CLAIMS — these are operator-verified facts; the "
            "social-proof angle MAY visually evoke them. Never invent "
            "credibility outside this list:\n" + pinned_lines + "\n"
        )

    if target_label == "video":
        target_addendum = (
            "\nFORMAT NOTE: each `prompt` is a VIDEO prompt — include camera "
            "movement (slow push-in, dolly, handheld, static), subject action, "
            "and a 5–10 second arc. Editorial / cinematic register, never "
            "TikTok-style.\n"
        )
    else:
        target_addendum = (
            "\nFORMAT NOTE: each `prompt` is an IMAGE prompt — lens (35mm / "
            "50mm / 85mm), depth-of-field, lighting register required.\n"
        )

    user = (
        "Draft the three angle variants for the brief below. Return ONLY the "
        "JSON object specified in your OUTPUT FORMAT — no preamble, no markdown.\n\n"
        "STRUCTURED BRIEF:\n"
        f"  subject:          {brief['subject']}\n"
        f"  setting:          {brief['setting']}\n"
        f"  value_prop:       {brief['value_prop']}\n"
        f"  audience:         {brief['audience']}\n"
        f"  tone:             {brief['tone']}\n"
        f"  program:          {brief['program']}\n"
        f"  hard_constraints: {brief['hard_constraints']}\n"
        f"  claim_hints:      {brief['claim_hints']}\n"
        f"{pinned_block}{target_addendum}\n"
        f"Target: {target_label}\n"
    )

    raw = await _claude_one_shot(system=visual_director_system, user=user)
    parsed = _parse_json_envelope(raw)
    raw_variants = parsed.get("variants") or []
    # Tolerate partial output: pad missing angles, clip extras.
    by_angle: dict[str, dict[str, Any]] = {}
    for v in raw_variants:
        if isinstance(v, dict):
            angle = str(v.get("angle") or "").strip().lower()
            if angle:
                by_angle[angle] = v
    out: list[dict[str, Any]] = []
    for expected in ("problem-led", "aspirational", "social-proof"):
        v = by_angle.get(expected) or {}
        out.append({
            "angle": expected,
            "prompt": str(v.get("prompt") or "").strip(),
            "rationale": str(v.get("rationale") or "").strip(),
        })
    return out


# ── Helpers ───────────────────────────────────────────────────────────


async def _claude_one_shot(*, system: str, user: str, model: str = "sonnet") -> str:
    """Single-shot Claude call via the `claude --print` CLI. Same
    subprocess pattern agent.py uses for the streaming agent path —
    just non-streaming here because we want one structured response.
    Times out at _STAGE_TIMEOUT_S; raises with a structured message
    on failure."""
    proc = await asyncio.create_subprocess_exec(
        "claude", "--print", "--model", model,
        "--system-prompt", system,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(input=user.encode("utf-8")),
            timeout=_STAGE_TIMEOUT_S,
        )
    except asyncio.TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise PromptDrafterError(
            f"claude timed out after {_STAGE_TIMEOUT_S}s",
        ) from e
    if proc.returncode != 0:
        err = err_b.decode("utf-8", errors="replace").strip()
        raise PromptDrafterError(err[:500] or "claude CLI exited non-zero")
    return out_b.decode("utf-8", errors="replace").strip()


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_envelope(raw: str) -> dict[str, Any]:
    """Pull a JSON object out of a Claude response.

    Sonnet usually returns clean JSON when the system prompt says
    "return only a JSON object", but occasionally wraps in ```json
    fences or prepends an "Here is the JSON:" preamble. Strip those
    defensively so we don't crash on cosmetic chatter.
    """
    s = raw.strip()
    # Markdown fence strip
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Greedy scan for the first balanced { ... } block.
        m = _JSON_BLOCK_RE.search(s)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("prompt_drafter: could not parse Claude JSON, raw=%r", s[:400])
    return {}


def _load_role_md(*, account_id: str | None, role: str) -> str:
    """Load `data/roles/{account_id}/{role}.md`, fall back to baseline
    if account-specific missing, then to an empty string so the call
    still works (Stage 2's user message carries the structure)."""
    candidates: list[Path] = []
    if account_id:
        candidates.append(_ROLES_DIR / account_id / f"{role}.md")
    candidates.append(_ROLES_DIR / "baseline" / f"{role}.md")
    candidates.append(_ROLES_DIR / f"{role}.md")
    for path in candidates:
        try:
            if path.exists():
                content = path.read_text(encoding="utf-8").strip()
                # Roles are sometimes wrapped in a ```markdown fence
                # (the existing creative_director.md is) — strip it
                # so Claude sees just the content as a system prompt.
                if content.startswith("```"):
                    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                    content = re.sub(r"\n?```$", "", content)
                return content.strip()
        except Exception as e:
            logger.warning("prompt_drafter: failed reading %s: %s", path, e)
    return ""


def _load_pinned_claims(
    *, account_id: str | None, campaign_id: str | None,
) -> list[str]:
    """Read `data/memory/{account_id}/{campaign_id}/pinned_facts.md`
    and return one trimmed claim per non-empty bullet line. These get
    injected into Stage 2 as the ONLY claims the social-proof variant
    may evoke."""
    if not account_id or not campaign_id:
        return []
    path = _MEMORY_DIR / account_id / campaign_id / "pinned_facts.md"
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("prompt_drafter: failed reading %s: %s", path, e)
        return []
    claims: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        # Pull bullets ("- ...", "* ...") and skip the file's header /
        # comment lines.
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        m = re.match(r"^[-*]\s+(.+)$", line)
        if m:
            claims.append(m.group(1).strip())
    return claims


class PromptDrafterError(RuntimeError):
    """Raised when the drafting pipeline fails. The router maps these
    to a 502 with the structured message."""

    pass
