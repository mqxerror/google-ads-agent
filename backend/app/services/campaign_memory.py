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
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_MEMORY_ROOT = settings.MEMORY_DIR


def _campaign_dir(account_id: str, campaign_id: str) -> Path:
    """Get or create the memory directory for a campaign."""
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

    # pinned_facts.md
    pinned = d / "pinned_facts.md"
    if not pinned.exists():
        pinned.write_text(
            f"# Pinned Facts: {campaign_name}\n\n"
            "<!-- Facts listed here are ALWAYS included in agent context. -->\n"
            "<!-- They never expire from the conversation window. -->\n\n",
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


def load_decisions(account_id: str, campaign_id: str, limit: int = 20) -> str:
    """Load the most recent decisions from the decision log."""
    d = _campaign_dir(account_id, campaign_id)
    decisions_file = d / "decisions.md"
    if not decisions_file.exists():
        return ""
    content = decisions_file.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    # Keep header (first 5 lines) + last N decision rows
    header = lines[:5]
    data_lines = [l for l in lines[5:] if l.strip().startswith("|")]
    recent = data_lines[-limit:] if len(data_lines) > limit else data_lines
    return "\n".join(header + recent)


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


def save_role_notes(
    account_id: str,
    campaign_id: str,
    role: str,
    notes: str,
) -> None:
    """Replace findings from a specialist role (overwrites file)."""
    d = _campaign_dir(account_id, campaign_id)
    role_dir = d / "role_notes"
    role_dir.mkdir(exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    role_file = role_dir / f"{role}.md"

    header = f"# {role.replace('_', ' ').title()} Notes\n\n**Last updated:** {now}\n\n"
    role_file.write_text(header + notes, encoding="utf-8")

    _update_memory_index(account_id, campaign_id, role)


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
    """
    d = _campaign_dir(account_id, campaign_id)
    role_dir = d / "role_notes"
    role_dir.mkdir(exist_ok=True)

    role_file = role_dir / f"{role}.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not role_file.exists():
        # Nothing to append to — create fresh
        header = f"# {role.replace('_', ' ').title()} Notes\n\n**Last updated:** {now}\n\n"
        role_file.write_text(header + notes, encoding="utf-8")
        _update_memory_index(account_id, campaign_id, role)
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
    _update_memory_index(account_id, campaign_id, role)


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

    # Role-specific notes
    if active_role:
        role_notes = load_role_notes(account_id, campaign_id, active_role)
        if role_notes:
            parts.append(role_notes)

    # Account-wide insights
    account_mem = load_account_memory(account_id)
    if account_mem and account_mem.strip().count("\n") > 3:
        parts.append(account_mem)

    return "\n\n---\n\n".join(parts) if parts else ""
