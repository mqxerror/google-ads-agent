"""Skill file loader — manages per-account role skill files with versioning.

Each role's system prompt is a "skill" — a markdown file that evolves
based on outcomes, user corrections, and marketing updates.

Storage:
    data/roles/{account_id}/
        {role_id}.md            ← Current living skill file
        _versions/
            {role_id}_v1.md     ← Original (seeded from hardcoded prompt)
            {role_id}_v2.md     ← After first optimization
"""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

_ROLES_BASE = settings.DATA_DIR / "roles"


def _account_roles_dir(account_id: str) -> Path:
    d = _ROLES_BASE / account_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _versions_dir(account_id: str) -> Path:
    d = _account_roles_dir(account_id) / "_versions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_skill(account_id: str, role_id: str) -> str | None:
    """Load the current skill file for a role on this account.

    Returns None if no skill file exists (uses hardcoded prompt as fallback).
    """
    path = _account_roles_dir(account_id) / f"{role_id}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def save_skill(account_id: str, role_id: str, content: str, version: int | None = None) -> int:
    """Save a skill file and create a version snapshot.

    Returns the version number.
    """
    roles_dir = _account_roles_dir(account_id)
    versions_dir = _versions_dir(account_id)

    # Determine version number
    if version is None:
        version = get_latest_version(account_id, role_id) + 1

    # Write the current skill file
    skill_path = roles_dir / f"{role_id}.md"
    skill_path.write_text(content, encoding="utf-8")

    # Save versioned copy
    version_path = versions_dir / f"{role_id}_v{version}.md"
    version_path.write_text(content, encoding="utf-8")

    logger.info("Saved skill %s v%d for account %s", role_id, version, account_id)
    return version


def get_latest_version(account_id: str, role_id: str) -> int:
    """Get the latest version number for a role's skill."""
    versions_dir = _versions_dir(account_id)
    versions = sorted(versions_dir.glob(f"{role_id}_v*.md"))
    if not versions:
        return 0
    # Extract version number from filename
    try:
        last = versions[-1].stem  # e.g. "ppc_strategist_v3"
        return int(last.split("_v")[-1])
    except (ValueError, IndexError):
        return 0


def load_version(account_id: str, role_id: str, version: int) -> str | None:
    """Load a specific version of a skill file."""
    path = _versions_dir(account_id) / f"{role_id}_v{version}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def list_versions(account_id: str, role_id: str) -> list[dict]:
    """List all versions of a role's skill."""
    versions_dir = _versions_dir(account_id)
    results = []
    for path in sorted(versions_dir.glob(f"{role_id}_v*.md")):
        try:
            v = int(path.stem.split("_v")[-1])
            stat = path.stat()
            results.append({
                "version": v,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size,
            })
        except (ValueError, IndexError):
            continue
    return results


def rollback_skill(account_id: str, role_id: str, to_version: int) -> bool:
    """Rollback a skill to a previous version."""
    old_content = load_version(account_id, role_id, to_version)
    if not old_content:
        return False

    # Save as a new version (rollback is a forward operation)
    new_version = get_latest_version(account_id, role_id) + 1
    # Write current file
    skill_path = _account_roles_dir(account_id) / f"{role_id}.md"
    skill_path.write_text(old_content, encoding="utf-8")
    # Save versioned copy with note
    version_path = _versions_dir(account_id) / f"{role_id}_v{new_version}.md"
    version_path.write_text(old_content, encoding="utf-8")

    logger.info("Rolled back %s to v%d (saved as v%d)", role_id, to_version, new_version)
    return True


def seed_skill_from_role(account_id: str, role_id: str, role_prompt: str, role_name: str) -> int:
    """Create the initial v1 skill file from a role's hardcoded prompt.

    Only seeds if no skill file exists yet.
    """
    existing = load_skill(account_id, role_id)
    if existing:
        return get_latest_version(account_id, role_id)

    now = datetime.now().strftime("%Y-%m-%d")
    content = f"""# {role_name} — Account {account_id}
Version: 1 | Created: {now} | Success rate: N/A (no outcomes yet)

## Core Identity
{role_prompt}

## Techniques (what to do)
<!-- Auto-populated as outcomes are measured -->

## Anti-Patterns (what NOT to do)
<!-- Auto-populated from failed recommendations and user corrections -->

## Account Knowledge
<!-- Auto-populated from campaign memory and pinned facts -->

## Recent Learnings
<!-- Auto-populated from outcome tracking -->

## Marketing Intelligence
<!-- Auto-updated with industry best practices -->
"""
    return save_skill(account_id, role_id, content, version=1)


async def seed_all_roles(account_id: str) -> int:
    """Seed skill files for all roles from hardcoded prompts.

    Returns the number of roles seeded.
    """
    from app.services.roles import ROLES

    seeded = 0
    for role_id, role in ROLES.items():
        existing = load_skill(account_id, role_id)
        if not existing:
            seed_skill_from_role(account_id, role_id, role.system_prompt, role.name)
            seeded += 1
    return seeded


async def get_skill_dashboard(account_id: str) -> list[dict]:
    """Get overview data for all role skills on this account."""
    from app.services.roles import ROLES

    db = await get_db()
    try:
        results = []
        for role_id, role in ROLES.items():
            skill = load_skill(account_id, role_id)
            version = get_latest_version(account_id, role_id)
            versions = list_versions(account_id, role_id)

            # Count techniques in the skill file
            techniques_count = 0
            if skill:
                for line in skill.split("\n"):
                    if line.strip().startswith("- ") and "Auto-populated" not in line:
                        techniques_count += 1

            # Get outcome stats for this role's domain
            from app.services.outcome_tracker import TOOL_ACTION_MAP
            role_actions = _get_role_action_types(role_id)

            if role_actions:
                placeholders = ",".join("?" for _ in role_actions)
                cur = await db.execute(
                    f"""SELECT COUNT(*) as total,
                               SUM(CASE WHEN outcome = 'improved' THEN 1 ELSE 0 END) as improved,
                               SUM(CASE WHEN outcome = 'degraded' THEN 1 ELSE 0 END) as degraded,
                               SUM(CASE WHEN status = 'measured' THEN 1 ELSE 0 END) as measured
                        FROM recommendations
                        WHERE account_id = ? AND action_type IN ({placeholders})""",
                    (account_id, *role_actions),
                )
                row = await cur.fetchone()
                total = row["total"] or 0
                measured = row["measured"] or 0
                improved = row["improved"] or 0
                success_rate = round(improved / measured * 100) if measured > 0 else None
            else:
                total = 0
                measured = 0
                improved = 0
                success_rate = None

            # Parse last optimized from skill file header
            last_optimized = None
            if skill and "Last optimized:" in skill:
                for line in skill.split("\n"):
                    if "Last optimized:" in line:
                        try:
                            last_optimized = line.split("Last optimized:")[1].strip().split("|")[0].strip()
                        except IndexError:
                            pass

            results.append({
                "role_id": role_id,
                "role_name": role.name,
                "avatar": role.avatar,
                "version": version,
                "versions_count": len(versions),
                "techniques_count": techniques_count,
                "total_actions": total,
                "measured_actions": measured,
                "improved_actions": improved,
                "success_rate": success_rate,
                "has_skill_file": skill is not None,
                "last_optimized": last_optimized,
            })

        return results
    finally:
        await db.close()


# Role → action type mapping
ROLE_ACTION_DOMAINS = {
    "ppc_strategist": ["update_campaign", "budget_change", "update_bid"],
    "search_term_hunter": ["add_negatives", "add_keywords", "remove_keyword"],
    "creative_director": ["create_ad", "update_ad_status"],
    "gtm_specialist": [],
    "cro_specialist": [],
    "analytics_analyst": [],
    "competitor_intel": [],
    "growth_hacker": ["budget_change", "create_campaign"],
    "director": [],
}


def _get_role_action_types(role_id: str) -> list[str]:
    return ROLE_ACTION_DOMAINS.get(role_id, [])
