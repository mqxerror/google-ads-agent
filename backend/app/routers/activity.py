"""Campaign activity feed — aggregates role notes, decisions, and session summaries
into a per-campaign timeline of what each specialist did."""

from __future__ import annotations

import re
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["activity"])

_MEMORY_DIR = settings.MEMORY_DIR

ROLE_AVATARS: dict[str, str] = {
    "director": "briefcase",
    "ppc_strategist": "target",
    "search_term_hunter": "search",
    "creative_director": "palette",
    "analytics_analyst": "chart",
    "competitor_intel": "eye",
    "gtm_specialist": "code",
    "growth_hacker": "rocket",
    "cro_specialist": "gauge",
    "agent": "briefcase",
}

ROLE_NAMES: dict[str, str] = {
    "director": "Agency Director",
    "ppc_strategist": "PPC Strategist",
    "search_term_hunter": "Search Term Hunter",
    "creative_director": "Creative Director",
    "analytics_analyst": "Analytics Analyst",
    "competitor_intel": "Competitor Intel",
    "gtm_specialist": "GTM Specialist",
    "growth_hacker": "Growth Hacker",
    "cro_specialist": "CRO Specialist",
    "agent": "Agent",
}


def _extract_role_activities(account_id: str, campaign_id: str) -> list[dict]:
    """Extract activities from role_notes/*.md files."""
    role_dir = _MEMORY_DIR / account_id / campaign_id / "role_notes"
    if not role_dir.exists():
        return []

    activities = []
    for note_file in role_dir.glob("*.md"):
        role_id = note_file.stem
        content = note_file.read_text(encoding="utf-8")

        # Extract timestamp
        ts_match = re.search(r'\*\*Last updated:\*\*\s*([\d\-: ]+)', content)
        timestamp = ts_match.group(1).strip() if ts_match else None

        # Extract task
        task_match = re.search(r'\*\*Task:\*\*\s*(.+?)(?:\n|$)', content)
        task = task_match.group(1).strip()[:200] if task_match else None

        # Extract critical details
        details_match = re.search(r'\*\*Critical Details:\*\*\s*(.+?)(?:\n|$)', content)
        critical = details_match.group(1).strip()[:150] if details_match else None

        # Build action summary
        action = task or f"Updated {role_id.replace('_', ' ')} notes"
        if critical:
            action += f" ({critical[:80]})"

        if timestamp:
            activities.append({
                "timestamp": timestamp,
                "role": ROLE_NAMES.get(role_id, role_id.replace("_", " ").title()),
                "role_id": role_id,
                "avatar": ROLE_AVATARS.get(role_id, "briefcase"),
                "action": action,
                "type": "role_notes",
            })

    return activities


def _extract_decision_activities(account_id: str, campaign_id: str, limit: int = 5) -> list[dict]:
    """Extract recent decisions from decisions.md."""
    decisions_file = _MEMORY_DIR / account_id / campaign_id / "decisions.md"
    if not decisions_file.exists():
        return []

    content = decisions_file.read_text(encoding="utf-8")
    activities = []

    for line in content.split("\n"):
        if not line.strip().startswith("|") or "---" in line or "Date" in line:
            continue
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 4:
            timestamp, action, reason, outcome = cells[0], cells[1], cells[2], cells[3]
            role_id = cells[4] if len(cells) > 4 else "agent"
            activities.append({
                "timestamp": timestamp,
                "role": ROLE_NAMES.get(role_id, role_id.replace("_", " ").title()),
                "role_id": role_id,
                "avatar": ROLE_AVATARS.get(role_id, "briefcase"),
                "action": action[:200],
                "type": "decision",
            })

    return activities[-limit:]


async def _extract_summary_activities(campaign_id: str, limit: int = 5) -> list[dict]:
    """Extract recent session summaries from DB."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT summary, created_at FROM session_summaries WHERE campaign_id = ? ORDER BY created_at DESC LIMIT ?",
            (campaign_id, limit),
        )
        rows = await cur.fetchall()
        activities = []
        for r in rows:
            summary = r["summary"]
            # Extract role from "[Role Name]" prefix
            role_match = re.match(r'\[([^\]]+)\]', summary)
            role_name = role_match.group(1) if role_match else "Agent"
            # Find role_id
            role_id = "agent"
            for rid, rname in ROLE_NAMES.items():
                if rname.lower() == role_name.lower():
                    role_id = rid
                    break

            # Clean summary
            clean = re.sub(r'^\[[^\]]+\]\s*', '', summary).strip()
            # Extract just the key info
            parts = clean.split("|")
            action = parts[1].strip() if len(parts) > 1 else clean[:150]

            activities.append({
                "timestamp": r["created_at"],
                "role": role_name,
                "role_id": role_id,
                "avatar": ROLE_AVATARS.get(role_id, "briefcase"),
                "action": action[:200],
                "type": "session_summary",
            })
        return activities
    finally:
        await db.close()


def _parse_timestamp(ts: str) -> datetime:
    """Parse various timestamp formats."""
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(ts.strip(), fmt)
        except ValueError:
            continue
    return datetime.min


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/activity")
async def get_campaign_activity(account_id: str, campaign_id: str, limit: int = 15):
    """Get activity feed for a single campaign."""
    activities = []

    # Gather from all sources
    activities.extend(_extract_role_activities(account_id, campaign_id))
    activities.extend(_extract_decision_activities(account_id, campaign_id))
    activities.extend(await _extract_summary_activities(campaign_id))

    # Sort by timestamp descending, dedupe
    activities.sort(key=lambda a: _parse_timestamp(a["timestamp"]), reverse=True)

    # Dedupe similar activities within same minute
    seen = set()
    unique = []
    for a in activities:
        key = f"{a['timestamp'][:16]}:{a['role_id']}"
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique = unique[:limit]

    return {
        "campaign_id": campaign_id,
        "activity": unique,
        "last_activity": unique[0]["timestamp"] if unique else None,
        "active_roles": list(set(a["role_id"] for a in unique)),
        "total_activities": len(activities),
    }


@router.get("/accounts/{account_id}/activity")
async def get_account_activity(account_id: str, limit: int = 30):
    """Get activity feed across ALL campaigns for the account overview."""
    account_dir = _MEMORY_DIR / account_id
    if not account_dir.exists():
        return {"campaigns": [], "total_activities": 0}

    campaign_summaries = []
    for campaign_dir in account_dir.iterdir():
        if not campaign_dir.is_dir():
            continue
        campaign_id = campaign_dir.name

        # Get campaign name from profile.md
        profile = campaign_dir / "profile.md"
        campaign_name = campaign_id
        if profile.exists():
            name_match = re.search(r'# Campaign Profile:\s*(.+)', profile.read_text(encoding="utf-8"))
            if name_match:
                campaign_name = name_match.group(1).strip()

        # Get activities for this campaign
        activities = []
        activities.extend(_extract_role_activities(account_id, campaign_id))
        activities.extend(_extract_decision_activities(account_id, campaign_id, limit=3))

        activities.sort(key=lambda a: _parse_timestamp(a["timestamp"]), reverse=True)
        activities = activities[:5]

        if activities:
            campaign_summaries.append({
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "last_activity": activities[0]["timestamp"],
                "active_roles": list(set(a["role_id"] for a in activities)),
                "recent_activities": activities[:3],
                "total_activities": len(activities),
            })

    # Sort campaigns by last activity
    campaign_summaries.sort(
        key=lambda c: _parse_timestamp(c["last_activity"]) if c.get("last_activity") else datetime.min,
        reverse=True,
    )

    return {
        "campaigns": campaign_summaries[:limit],
        "total_activities": sum(c["total_activities"] for c in campaign_summaries),
    }
