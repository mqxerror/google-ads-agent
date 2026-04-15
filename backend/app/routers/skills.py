"""Skill evolution endpoints — view, edit, optimize role skills."""

from fastapi import APIRouter

from app.services.skill_loader import (
    load_skill, save_skill, list_versions, load_version,
    rollback_skill, get_skill_dashboard, seed_all_roles,
)
from app.services.skill_optimizer import optimize_role_skill, optimize_all_roles, score_skill

router = APIRouter(prefix="/api", tags=["skills"])


@router.get("/accounts/{account_id}/skills")
async def get_skills_dashboard(account_id: str) -> dict:
    """Get overview of all role skills for this account."""
    # Seed any missing role skills
    seeded = await seed_all_roles(account_id)
    dashboard = await get_skill_dashboard(account_id)
    return {"roles": dashboard, "seeded": seeded}


@router.get("/accounts/{account_id}/skills/{role_id}")
async def get_role_skill(account_id: str, role_id: str) -> dict:
    """Get a role's current skill file + version history + score."""
    skill = load_skill(account_id, role_id)
    versions = list_versions(account_id, role_id)
    score_data = await score_skill(account_id, role_id)

    return {
        "role_id": role_id,
        "content": skill,
        "versions": versions,
        **score_data,
    }


@router.get("/accounts/{account_id}/skills/{role_id}/versions/{version}")
async def get_skill_version(account_id: str, role_id: str, version: int) -> dict:
    """Get a specific version of a role's skill."""
    content = load_version(account_id, role_id, version)
    return {"role_id": role_id, "version": version, "content": content}


@router.put("/accounts/{account_id}/skills/{role_id}")
async def update_skill(account_id: str, role_id: str, body: dict) -> dict:
    """Manually edit a role's skill file."""
    content = body.get("content", "")
    if not content:
        return {"error": "content is required"}
    version = save_skill(account_id, role_id, content)
    return {"status": "saved", "version": version}


@router.post("/accounts/{account_id}/skills/{role_id}/optimize")
async def trigger_optimization(account_id: str, role_id: str) -> dict:
    """Trigger manual optimization for a role's skill."""
    result = await optimize_role_skill(account_id, role_id)
    return result


@router.post("/accounts/{account_id}/skills/optimize-all")
async def trigger_all_optimizations(account_id: str) -> dict:
    """Trigger optimization for all roles."""
    results = await optimize_all_roles(account_id)
    return {"results": results}


@router.post("/accounts/{account_id}/skills/{role_id}/rollback/{version}")
async def rollback_to_version(account_id: str, role_id: str, version: int) -> dict:
    """Rollback a role's skill to a previous version."""
    success = rollback_skill(account_id, role_id, version)
    return {"status": "rolled_back" if success else "error", "to_version": version}
