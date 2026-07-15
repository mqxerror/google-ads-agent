"""Per-campaign file-based memory system.

Each campaign gets its own memory directory:
    data/memory/{account_id}/{campaign_id}/
        MEMORY.md       — index of all memory files
        decisions.md    — structured decision log
        pinned_facts.md — facts that never expire from context
        profile.md      — campaign goals, phase, constraints
        role_notes/     — per-role findings (future: Phase 2)

The agent reads MEMORY.md to know what's available, then loads
only the files relevant to the current role + task.
"""

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_MEMORY_ROOT = settings.MEMORY_DIR

# WS3 — findings freshness guard. Role notes older than this are labelled STALE
# in assembled context so a persona re-verifies (live pull/fetch) before acting
# on a past state. CONSERVATIVE first-cut window — tune here.
ROLE_NOTES_STALE_DAYS = 7

# Matches the exact header save_role_notes/append_role_notes write:
#   **Last updated:** YYYY-MM-DD HH:MM
_LAST_UPDATED_RE = re.compile(r'\*\*Last updated:\*\* (\d{4}-\d{2}-\d{2} \d{2}:\d{2})')


def role_notes_age_days(body: str) -> tuple[int | None, str | None]:
    """Age (in days) of a role-notes body from its `**Last updated:**` header.

    Returns (age_days, date_str). age_days is None when the header is missing or
    unparseable; date_str is the raw matched timestamp (or None). Uses
    datetime.now() so it tracks local time like the writers do.
    """
    m = _LAST_UPDATED_RE.search(body or "")
    if not m:
        return None, None
    date_str = m.group(1)
    try:
        ts = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return None, date_str
    age = (datetime.now() - ts).days
    return (age if age >= 0 else 0), date_str


def _dir_has_real_content(d: Path) -> bool:
    """True if a memory dir holds actual logged work (not just seed skeletons).

    A freshly-seeded decisions.md is only a header + empty table; a real one
    has data rows. role_notes/ with any file also counts.
    """
    if not d.is_dir():
        return False
    dec = d / "decisions.md"
    if dec.is_file():
        for line in dec.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s.startswith("|") and "Date" not in s and "---" not in s:
                return True
    rn = d / "role_notes"
    if rn.is_dir() and any(rn.iterdir()):
        return True
    chron = d / "CHRONICLE.md"
    if chron.is_file() and len(chron.read_text(encoding="utf-8", errors="ignore")) > 400:
        return True
    return False


def _reconcile_build_namespace(account_id: str, campaign_id: str) -> None:
    """Self-heal the build→real campaign memory split.

    A campaign is built under a temp ``build-XXXX`` namespace. Once the real
    Google Ads campaign exists, chats address it by its numeric id — but the
    dir is only renamed if the promote endpoint ran with a live in-memory
    session, which doesn't survive restarts. Result: the real-id dir is empty
    and every agent reads it → total amnesia about the build (the bug the
    user hit: "agent memory is fucked up").

    Fix at the one chokepoint every read/write passes through: if a real
    campaign id has no real content, find the single build-* dir whose
    CHRONICLE/decisions reference this exact id and migrate it across,
    rewriting the old id → real id. Idempotent: once migrated this no-ops.
    """
    if not account_id or not campaign_id or campaign_id.startswith("build-"):
        return
    acct = _MEMORY_ROOT / account_id
    if not acct.is_dir():
        return
    real_dir = acct / campaign_id
    if _dir_has_real_content(real_dir):
        return  # already healthy — fast path

    candidates = []
    for d in acct.iterdir():
        if not d.is_dir() or not d.name.startswith("build-"):
            continue
        if not _dir_has_real_content(d):
            continue
        for fn in ("CHRONICLE.md", "decisions.md", "MEMORY.md"):
            f = d / fn
            if f.is_file() and campaign_id in f.read_text(encoding="utf-8", errors="ignore"):
                candidates.append(d)
                break
    if len(candidates) != 1:
        return  # none or ambiguous — never guess which build a campaign came from

    src = candidates[0]
    old_id = src.name
    try:
        if real_dir.exists():
            if any(real_dir.iterdir()):
                return  # unexpected content — don't clobber
            real_dir.rmdir()  # empty placeholder created by a prior _campaign_dir
        shutil.move(str(src), str(real_dir))
        # Rewrite the temp id → real id so "scope to THIS campaign id"
        # instructions in pinned_facts/profile/decisions point at the real one.
        for f in real_dir.rglob("*.md"):
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
                if old_id in t:
                    f.write_text(t.replace(old_id, campaign_id), encoding="utf-8")
            except Exception:
                pass
        logger.info(
            "Reconciled build memory %s → %s (account %s)",
            old_id, campaign_id, account_id,
        )
    except Exception as e:
        logger.warning(
            "Build-namespace reconcile failed (%s → %s): %s", old_id, campaign_id, e
        )


def _campaign_dir(account_id: str, campaign_id: str) -> Path:
    """Get or create the memory directory for a campaign."""
    _reconcile_build_namespace(account_id, campaign_id)
    d = _MEMORY_ROOT / account_id / campaign_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _account_dir(account_id: str) -> Path:
    """Get or create the memory directory for an account."""
    d = _MEMORY_ROOT / account_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Initialize memory structure ────────────────────────────────


def init_campaign_memory(
    account_id: str, campaign_id: str, campaign_name: str,
) -> Path:
    """Create the memory directory and seed files for a campaign."""
    d = _campaign_dir(account_id, campaign_id)

    # MEMORY.md — index
    memory_index = d / "MEMORY.md"
    if not memory_index.exists():
        memory_index.write_text(
            f"# Campaign Memory: {campaign_name}\n\n"
            f"- [Decisions](decisions.md) — Actions taken with reasoning\n"
            f"- [Pinned Facts](pinned_facts.md) — Permanent context\n"
            f"- [Profile](profile.md) — Campaign goals and constraints\n",
            encoding="utf-8",
        )

    # decisions.md
    decisions = d / "decisions.md"
    if not decisions.exists():
        decisions.write_text(
            f"# Decision Log: {campaign_name}\n\n"
            "<!-- FORMAT: | Date | Action | Reason | Outcome | Role | -->\n\n"
            "| Date | Action | Reason | Outcome | Role |\n"
            "|------|--------|--------|---------|------|\n",
            encoding="utf-8",
        )

    # pinned_facts.md — seeded with safety baselines for brand-new campaigns
    # so agents don't invent CPA/CPC numbers when there's no historical data.
    pinned = d / "pinned_facts.md"
    if not pinned.exists():
        pinned.write_text(
            f"# Pinned Facts: {campaign_name}\n\n"
            "<!-- Facts listed here are ALWAYS included in agent context. -->\n"
            "<!-- They never expire from the conversation window. -->\n\n"
            f"- **Campaign ID:** {campaign_id} — every recommendation must be scoped to THIS campaign only.\n"
            "- **Currency:** USD (account billing currency). Convert any £/€ benchmark to USD before recommending.\n"
            f"- **Status:** Brand-new campaign created {datetime.now().date().isoformat()}. "
            "Until at least 7 days and 100+ impressions exist, **do not invent CPA/CPC/QS baselines** — "
            "say explicitly that there isn't enough data yet.\n",
            encoding="utf-8",
        )

    # profile.md
    profile = d / "profile.md"
    if not profile.exists():
        profile.write_text(
            f"# Campaign Profile: {campaign_name}\n\n"
            f"- **Campaign ID:** {campaign_id}\n"
            f"- **Account ID:** {account_id}\n"
            f"- **Created:** {datetime.now().isoformat()}\n\n"
            "## Goals\n\n"
            "<!-- Set campaign objectives here -->\n\n"
            "## Constraints\n\n"
            "<!-- Budget caps, CPA targets, etc. -->\n\n"
            "## Phase\n\n"
            "<!-- LEARNING / OPTIMIZATION / MATURE -->\n\n",
            encoding="utf-8",
        )

    return d


# ── Read memory ─────────────────────────────────────────────────


def load_memory_index(account_id: str, campaign_id: str) -> str:
    """Load the MEMORY.md index for a campaign."""
    d = _campaign_dir(account_id, campaign_id)
    index_file = d / "MEMORY.md"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return ""


def load_decisions(account_id: str, campaign_id: str, limit: int | None = None) -> str:
    """Load ALL decisions with tiered compression.

    Recent 20: full table rows (detailed)
    Older: compressed by month ("March 2026 (8 decisions): key actions...")
    """
    d = _campaign_dir(account_id, campaign_id)
    decisions_file = d / "decisions.md"
    if not decisions_file.exists():
        return ""
    content = decisions_file.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    header = lines[:5]
    data_lines = [l for l in lines[5:] if l.strip().startswith("|")]

    if not data_lines:
        return "\n".join(header)

    # If limit is set (legacy callers), use the old behavior
    if limit is not None:
        recent = data_lines[-limit:] if len(data_lines) > limit else data_lines
        return "\n".join(header + recent)

    # Tiered: recent 20 detailed, older compressed by month
    recent_count = 20
    if len(data_lines) <= recent_count:
        return "\n".join(header + data_lines)

    recent = data_lines[-recent_count:]
    older = data_lines[:-recent_count]

    # Compress older decisions by month
    months: dict[str, list[str]] = {}
    for row in older:
        cells = row.split("|")
        if len(cells) >= 3:
            date_str = cells[1].strip()
            # Extract month-year (e.g., "2026-04" from "2026-04-13 15:30")
            month_key = date_str[:7] if len(date_str) >= 7 else "Unknown"
            action = cells[2].strip() if len(cells) > 2 else ""
            if month_key not in months:
                months[month_key] = []
            months[month_key].append(action)

    compressed_parts = ["\n## Historical Decisions (compressed)"]
    for month_key in sorted(months.keys()):
        actions = months[month_key]
        # Summarize: take first 4 unique actions
        unique_actions = list(dict.fromkeys(actions))[:4]
        summary = ", ".join(unique_actions)
        try:
            from datetime import datetime as dt
            month_label = dt.strptime(month_key, "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            month_label = month_key
        compressed_parts.append(f"- **{month_label}** ({len(actions)} decisions): {summary}")

    compressed_parts.append("\n## Recent Decisions (last 20)")

    return "\n".join(header + compressed_parts + recent)


def load_pinned_facts(account_id: str, campaign_id: str) -> str:
    """Load all pinned facts — these are ALWAYS in context."""
    d = _campaign_dir(account_id, campaign_id)
    pinned_file = d / "pinned_facts.md"
    if not pinned_file.exists():
        return ""
    return pinned_file.read_text(encoding="utf-8")


def load_profile(account_id: str, campaign_id: str) -> str:
    """Load campaign profile (goals, constraints, phase)."""
    d = _campaign_dir(account_id, campaign_id)
    profile_file = d / "profile.md"
    if not profile_file.exists():
        return ""
    return profile_file.read_text(encoding="utf-8")


def load_account_memory(account_id: str) -> str:
    """Load cross-campaign insights from ACCOUNT_MEMORY.md."""
    d = _account_dir(account_id)
    account_mem = d / "ACCOUNT_MEMORY.md"
    if account_mem.exists():
        return account_mem.read_text(encoding="utf-8")
    return ""


def load_role_notes(account_id: str, campaign_id: str, role: str) -> str:
    """Load notes for a specific role (future: Phase 2 roles)."""
    d = _campaign_dir(account_id, campaign_id)
    role_dir = d / "role_notes"
    if not role_dir.exists():
        return ""
    role_file = role_dir / f"{role}.md"
    if role_file.exists():
        return role_file.read_text(encoding="utf-8")
    return ""


# ── Write memory ────────────────────────────────────────────────


def append_decision(
    account_id: str,
    campaign_id: str,
    action: str,
    reason: str,
    outcome: str = "pending",
    role: str = "agent",
) -> None:
    """Append a decision to the campaign's decision log."""
    d = _campaign_dir(account_id, campaign_id)
    decisions_file = d / "decisions.md"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    # Escape pipes in content
    action_clean = action.replace("|", "/")
    reason_clean = reason.replace("|", "/")
    outcome_clean = outcome.replace("|", "/")
    row = f"| {now} | {action_clean} | {reason_clean} | {outcome_clean} | {role} |\n"

    if not decisions_file.exists():
        init_campaign_memory(account_id, campaign_id, f"Campaign {campaign_id}")

    with open(decisions_file, "a", encoding="utf-8") as f:
        f.write(row)

    logger.info("Decision logged for %s/%s: %s", account_id, campaign_id, action[:80])


def add_pinned_fact(
    account_id: str,
    campaign_id: str,
    fact: str,
    source: str = "user",
) -> None:
    """Add a pinned fact that will always be in context."""
    d = _campaign_dir(account_id, campaign_id)
    pinned_file = d / "pinned_facts.md"

    if not pinned_file.exists():
        init_campaign_memory(account_id, campaign_id, f"Campaign {campaign_id}")

    now = datetime.now().strftime("%Y-%m-%d")
    entry = f"- **[{now}]** {fact} _(source: {source})_\n"

    with open(pinned_file, "a", encoding="utf-8") as f:
        f.write(entry)

    logger.info("Pinned fact for %s/%s: %s", account_id, campaign_id, fact[:80])


def update_profile(
    account_id: str,
    campaign_id: str,
    campaign_name: str,
    goals: str | None = None,
    constraints: str | None = None,
    phase: str | None = None,
) -> None:
    """Update the campaign profile."""
    d = _campaign_dir(account_id, campaign_id)
    profile_file = d / "profile.md"

    content = (
        f"# Campaign Profile: {campaign_name}\n\n"
        f"- **Campaign ID:** {campaign_id}\n"
        f"- **Account ID:** {account_id}\n"
        f"- **Updated:** {datetime.now().isoformat()}\n\n"
        f"## Goals\n\n{goals or '<!-- Not set -->'}\n\n"
        f"## Constraints\n\n{constraints or '<!-- Not set -->'}\n\n"
        f"## Phase\n\n{phase or '<!-- Not set -->'}\n\n"
    )
    profile_file.write_text(content, encoding="utf-8")


# Pattern that matches Google Ads campaign IDs (10+ digits) in note content.
# Used by the write-side guard below.
_CAMPAIGN_ID_RE = re.compile(r"\b(\d{10,})\b")


def _resolve_target_campaign_id(account_id: str, intended_campaign_id: str, notes: str) -> str:
    """Detect cross-campaign pollution before persisting role notes.

    The agent sometimes analyzes campaign B but is asked to save under campaign
    A (because the conversation's stored campaign_id is A). Without a guard the
    note ends up in A's folder and pollutes future reads.

    Strategy: scan the note for campaign IDs. Only consider IDs that match
    existing memory folders for this account (real campaigns, not random
    numbers). If exactly one ID is mentioned and it differs from the intended
    target, redirect the write to that campaign's folder.

    Returns the campaign_id the note should actually be saved under.
    """
    intended = str(intended_campaign_id)
    found = set(_CAMPAIGN_ID_RE.findall(notes or ""))
    if not found or found == {intended}:
        return intended

    # Filter to real campaigns (existing memory folders for this account).
    account_root = _account_dir(account_id)
    real = {cid for cid in found if (account_root / cid).is_dir()}
    real.discard(intended)

    if len(real) == 1:
        actual = next(iter(real))
        logger.warning(
            "Cross-campaign role-notes write detected: agent asked to save under "
            "campaign %s but the note references real campaign %s. Redirecting write "
            "to %s.",
            intended, actual, actual,
        )
        return actual

    if len(real) > 1:
        # Ambiguous — multiple foreign campaigns mentioned. Refuse to redirect;
        # write under the intended target but prepend a warning so the next
        # reader knows the content is suspect.
        logger.warning(
            "Role-notes write mentions multiple foreign campaigns %s under target %s. "
            "Persisting to intended folder with a pollution warning header.",
            real, intended,
        )
    return intended


def save_role_notes(
    account_id: str,
    campaign_id: str,
    role: str,
    notes: str,
) -> None:
    """Replace findings from a specialist role (overwrites file).

    Includes a cross-campaign pollution guard — if the note's content references
    a different real campaign, the write is redirected to that campaign's folder.
    """
    target_id = _resolve_target_campaign_id(account_id, campaign_id, notes)
    if target_id != campaign_id:
        logger.info("save_role_notes: redirecting %s → %s for role %s", campaign_id, target_id, role)

    d = _campaign_dir(account_id, target_id)
    role_dir = d / "role_notes"
    role_dir.mkdir(exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    role_file = role_dir / f"{role}.md"

    header = f"# {role.replace('_', ' ').title()} Notes\n\n**Last updated:** {now}\n\n"
    if target_id != campaign_id:
        # The agent thought it was writing to a different campaign — leave a
        # breadcrumb at the top so anyone reviewing the file knows.
        header += (
            f"> Note auto-redirected from campaign {campaign_id} on {now} because "
            f"the analysis content was scoped to {target_id}.\n\n"
        )
    role_file.write_text(header + notes, encoding="utf-8")

    _update_memory_index(account_id, target_id, role)


def append_role_notes(
    account_id: str,
    campaign_id: str,
    role: str,
    notes: str,
    section_title: str = "Follow-up",
) -> None:
    """Append a follow-up note to existing role findings without overwriting.

    Used when the agent provides a fix/conversation that should be added to the
    history rather than replacing the main report.

    Includes the same cross-campaign pollution guard as save_role_notes.
    """
    target_id = _resolve_target_campaign_id(account_id, campaign_id, notes)
    if target_id != campaign_id:
        logger.info("append_role_notes: redirecting %s → %s for role %s", campaign_id, target_id, role)

    d = _campaign_dir(account_id, target_id)
    role_dir = d / "role_notes"
    role_dir.mkdir(exist_ok=True)

    role_file = role_dir / f"{role}.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not role_file.exists():
        # Nothing to append to — create fresh
        header = f"# {role.replace('_', ' ').title()} Notes\n\n**Last updated:** {now}\n\n"
        role_file.write_text(header + notes, encoding="utf-8")
        _update_memory_index(account_id, target_id, role)
        return

    # Append to existing — under a "Session Log" section
    existing = role_file.read_text(encoding="utf-8")

    # Update the "Last updated" timestamp at the top
    existing = re.sub(
        r'\*\*Last updated:\*\* [\d\-: ]+',
        f"**Last updated:** {now}",
        existing,
        count=1,
    )

    # Check if there's already a Session Log section
    if "## Session Log" in existing:
        # Append a new entry under the existing log
        new_entry = f"\n\n### {now} — {section_title}\n\n{notes}\n"
        # Insert at the end of the file
        existing = existing.rstrip() + new_entry
    else:
        # Add Session Log section at the end
        new_section = f"\n\n---\n\n## Session Log\n\n### {now} — {section_title}\n\n{notes}\n"
        existing = existing.rstrip() + new_section

    role_file.write_text(existing, encoding="utf-8")
    _update_memory_index(account_id, target_id, role)


def save_account_insight(account_id: str, insight: str) -> None:
    """Save a cross-campaign insight to account memory."""
    d = _account_dir(account_id)
    account_mem = d / "ACCOUNT_MEMORY.md"

    if not account_mem.exists():
        account_mem.write_text(
            "# Account-Wide Insights\n\n"
            "<!-- Cross-campaign patterns and learnings -->\n\n",
            encoding="utf-8",
        )

    now = datetime.now().strftime("%Y-%m-%d")
    with open(account_mem, "a", encoding="utf-8") as f:
        f.write(f"- **[{now}]** {insight}\n")


def _update_memory_index(account_id: str, campaign_id: str, role: str) -> None:
    """Add a role notes entry to MEMORY.md if not already present."""
    d = _campaign_dir(account_id, campaign_id)
    index_file = d / "MEMORY.md"
    if not index_file.exists():
        return

    content = index_file.read_text(encoding="utf-8")
    entry = f"role_notes/{role}.md"
    if entry not in content:
        role_label = role.replace("_", " ").title()
        with open(index_file, "a", encoding="utf-8") as f:
            f.write(f"- [{role_label} Notes]({entry}) — Latest findings from {role_label}\n")


# ── Build context from memory ──────────────────────────────────


def build_campaign_context(
    account_id: str,
    campaign_id: str,
    active_role: str | None = None,
) -> str:
    """Assemble the full campaign context from memory files.

    This is Layer A of the new 3-layer system:
    - Profile (goals, constraints, phase)
    - Pinned facts (always present)
    - Recent decisions (last 20)
    - Active role notes (if a role is loaded)
    - Account-wide insights
    """
    parts = []

    # Profile
    profile = load_profile(account_id, campaign_id)
    if profile:
        parts.append(profile)

    # Pinned facts — always loaded
    pinned = load_pinned_facts(account_id, campaign_id)
    if pinned and pinned.strip().count("\n") > 4:  # More than just the header
        parts.append(pinned)

    # Recent decisions
    decisions = load_decisions(account_id, campaign_id, limit=20)
    if decisions and decisions.strip().count("|") > 10:  # More than just the header
        parts.append(decisions)

    # ALL role notes — every role sees every other role's findings
    # This is critical for cross-role knowledge sharing
    role_dir = _campaign_dir(account_id, campaign_id) / "role_notes"
    if role_dir.exists():
        for role_file in sorted(role_dir.glob("*.md")):
            role_id = role_file.stem
            notes = role_file.read_text(encoding="utf-8")
            if notes and len(notes) > 50:
                # WS3 — flag stale findings so a persona re-verifies before acting.
                age_days, date_str = role_notes_age_days(notes)
                stale_prefix = ""
                if age_days is None:
                    stale_prefix = (
                        f"⚠️ STALE (>{ROLE_NOTES_STALE_DAYS}d old, last updated unknown) "
                        "— RE-VERIFY before acting\n"
                    )
                elif age_days > ROLE_NOTES_STALE_DAYS:
                    stale_prefix = (
                        f"⚠️ STALE (>{ROLE_NOTES_STALE_DAYS}d old, last updated {date_str}) "
                        "— RE-VERIFY before acting\n"
                    )
                if role_id == active_role:
                    parts.append(f"{stale_prefix}=== YOUR PREVIOUS FINDINGS — CONTINUE FROM HERE ===\n{notes}")
                else:
                    label = role_id.replace('_', ' ').upper()
                    parts.append(f"{stale_prefix}=== FINDINGS FROM {label} ===\n{notes}")

    # Account-wide insights
    account_mem = load_account_memory(account_id)
    if account_mem and account_mem.strip().count("\n") > 3:
        parts.append(account_mem)

    return "\n\n---\n\n".join(parts) if parts else ""
