"""Creative endpoints — the runtime surface of the Creative Spec Registry.

``GET /api/creative/specs`` serves the frozen registry verbatim so the frontend
wizards derive their validation from ONE source instead of baked constants
(FR1.2, NFR-D1). Static data → cheap and cacheable (NFR-P2, <100 ms).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_db
from app.services import creative_specs

router = APIRouter(prefix="/api/creative", tags=["creative"])


@router.get("/specs")
def get_creative_specs() -> Dict[str, Any]:
    """Full registry: every campaign type's limits + engine knobs + version.

    Shape (architecture §6): ``{campaign_types, engine, version}``. The client
    caches the last response and renders validation from it immediately
    (stale-while-revalidate); this endpoint is pure static data."""
    return {
        "campaign_types": creative_specs.serialize_registry(),
        "engine": {
            "near_dup_threshold": creative_specs.ENGINE.near_dup_threshold,
            "batch_tile_cap": creative_specs.ENGINE.batch_tile_cap,
            "batch_retry_max": creative_specs.ENGINE.batch_retry_max,
        },
        # Copy-Workbench angle/tier vocabulary (Epic 16, AD-2) — the frontend
        # reads its angle list from here, never a baked component constant.
        "taxonomy": {
            "angles": list(creative_specs.ANGLES),
            "tiers": list(creative_specs.TIERS),
        },
        "version": creative_specs.VERSION,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Named drafts CRUD (story 15.2, FR4.1/FR4.2/D4). Per-account, per-campaign-type
# named rows — a second draft NEVER destroys the first because a name is a ROW,
# not a singleton key. Backed by the V27 `creative_drafts` table. Draft state has
# a durable home (fence F6): the wizard's localStorage is only a crash cache
# (story 15.4). Registered as a SECOND router because these paths are
# account-scoped (/api/accounts/{id}/...), unlike the /api/creative specs route.
# ─────────────────────────────────────────────────────────────────────────────

drafts_router = APIRouter(prefix="/api/accounts", tags=["creative-drafts"])

_VALID_TYPES = tuple(creative_specs.REGISTRY.keys())  # pmax | demand_gen | rda


# ─────────────────────────────────────────────────────────────────────────────
# Copy-jobs — the unified drafting contract (Epic 16, story 16.1 · FR1.7/1.9/1.10).
# ONE endpoint pair for draft / rewrite_row / diversify across every campaign
# type. Jobs are `creative_jobs` DB rows (fence F6) so they survive restart as a
# recoverable `interrupted`, never a 404. The result is always typed rows
# `[{text, angle, tier}]`.
# ─────────────────────────────────────────────────────────────────────────────

_COPY_MODES = {"draft", "rewrite_row", "diversify"}


class CopyJobBody(BaseModel):
    campaign_type: str
    mode: str = "draft"                       # draft | rewrite_row | diversify
    brief: str = ""
    final_url: str = ""
    business_name: str = ""
    campaign_name: str = ""
    rows: Optional[List[Dict[str, Any]]] = None       # current set (rewrite/diversify)
    row_index: Optional[int] = None                   # rewrite_row
    target_angle: Optional[str] = None                # rewrite_row
    locked_rows: Optional[List[int]] = None           # diversify — never regenerated
    flagged_rows: Optional[List[int]] = None          # diversify — the near-dups to replace
    dismissed_dup_pairs: Optional[List[List[int]]] = None  # R1 escape hatch
    research_hash: Optional[str] = None


@drafts_router.post("/{account_id}/creative/copy-jobs")
async def start_copy_job(account_id: str, body: CopyJobBody) -> Dict[str, str]:
    """Start a copy job; poll GET /api/creative/copy-jobs/{job_id}."""
    import asyncio

    from app.services import creative_copy

    _require_type(body.campaign_type)
    if body.mode not in _COPY_MODES:
        raise HTTPException(
            status_code=422,
            detail={"error": "BAD_MODE", "message": f"mode must be one of {sorted(_COPY_MODES)}"},
        )
    request = body.model_dump()
    job_id = await creative_copy.create_job(
        body.mode, account_id, body.campaign_type, request,
    )
    asyncio.create_task(
        creative_copy.run_copy_job(job_id, body.mode, account_id, body.campaign_type, request)
    )
    return {"job_id": job_id, "status": "running"}


@router.get("/copy-jobs/{job_id}")
async def get_copy_job(job_id: str) -> Dict[str, Any]:
    """Poll a copy job. Returns ``{status, result?, message?, request?}`` — the
    same poll shape the draft routes use; `interrupted` after a restart."""
    from app.services import creative_copy

    job = await creative_copy.get_job(job_id)
    if not job:
        return {"status": "error", "message": "unknown job id — start a new job"}
    return job


class DraftCreateBody(BaseModel):
    name: str
    campaign_type: str
    bundle: Dict[str, Any] = Field(default_factory=dict)


class DraftUpdateBody(BaseModel):
    name: Optional[str] = None
    bundle: Optional[Dict[str, Any]] = None


class DraftRow(BaseModel):
    id: str
    account_id: str
    campaign_type: str
    name: str
    bundle: Dict[str, Any]
    created_at: str
    updated_at: str
    warnings: List[str] = Field(default_factory=list)


def _require_type(campaign_type: str) -> None:
    if campaign_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail={"error": "BAD_CAMPAIGN_TYPE",
                    "message": f"campaign_type must be one of {list(_VALID_TYPES)}"},
        )


def _row_to_draft(row: Any) -> DraftRow:
    try:
        bundle = json.loads(row["bundle_json"]) if row["bundle_json"] else {}
    except (ValueError, TypeError):
        bundle = {}
    warnings = creative_specs.validate_draft_bundle(bundle, row["campaign_type"])
    return DraftRow(
        id=row["id"], account_id=row["account_id"],
        campaign_type=row["campaign_type"], name=row["name"], bundle=bundle,
        created_at=row["created_at"], updated_at=row["updated_at"],
        warnings=warnings,
    )


@drafts_router.get("/{account_id}/creative-drafts", response_model=List[DraftRow])
async def list_creative_drafts(
    account_id: str,
    campaign_type: Optional[str] = Query(default=None),
) -> List[DraftRow]:
    """List an account's named drafts, newest first. Filter by ``campaign_type``.
    Account-scoped (D4): drafts saved under account A are invisible to B."""
    db = await get_db()
    try:
        if campaign_type:
            _require_type(campaign_type)
            cur = await db.execute(
                "SELECT * FROM creative_drafts WHERE account_id = ? AND campaign_type = ? "
                "ORDER BY updated_at DESC",
                (account_id, campaign_type),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM creative_drafts WHERE account_id = ? ORDER BY updated_at DESC",
                (account_id,),
            )
        rows = await cur.fetchall()
    finally:
        await db.close()
    return [_row_to_draft(r) for r in rows]


@drafts_router.post("/{account_id}/creative-drafts", response_model=DraftRow)
async def create_creative_draft(account_id: str, body: DraftCreateBody) -> DraftRow:
    """Create a named draft. 409 when (account, type, name) already exists —
    a second draft never silently overwrites the first (FR4.2)."""
    _require_type(body.campaign_type)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422,
                            detail={"error": "BAD_NAME", "message": "name is required"})
    draft_id = str(uuid.uuid4())
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT 1 FROM creative_drafts WHERE account_id = ? AND campaign_type = ? AND name = ?",
            (account_id, body.campaign_type, name),
        )
        if await cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail={"error": "NAME_TAKEN",
                        "message": f"a {body.campaign_type} draft named {name!r} already exists"},
            )
        await db.execute(
            "INSERT INTO creative_drafts (id, account_id, campaign_type, name, bundle_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (draft_id, account_id, body.campaign_type, name, json.dumps(body.bundle)),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM creative_drafts WHERE id = ?", (draft_id,))
        row = await cur.fetchone()
    finally:
        await db.close()
    return _row_to_draft(row)


@drafts_router.get("/{account_id}/creative-drafts/{draft_id}", response_model=DraftRow)
async def get_creative_draft(account_id: str, draft_id: str) -> DraftRow:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM creative_drafts WHERE id = ? AND account_id = ?",
            (draft_id, account_id),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "draft not found"})
    return _row_to_draft(row)


@drafts_router.put("/{account_id}/creative-drafts/{draft_id}", response_model=DraftRow)
async def update_creative_draft(
    account_id: str, draft_id: str, body: DraftUpdateBody
) -> DraftRow:
    """Rename and/or replace a draft's bundle. Re-validates the bundle against
    the registry (soft limits → ``warnings[]``); the save is never blocked (a
    draft may be incomplete). 409 on a rename into an existing name."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM creative_drafts WHERE id = ? AND account_id = ?",
            (draft_id, account_id),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404,
                                detail={"error": "NOT_FOUND", "message": "draft not found"})
        new_name = body.name.strip() if body.name is not None else row["name"]
        if not new_name:
            raise HTTPException(status_code=422,
                                detail={"error": "BAD_NAME", "message": "name cannot be empty"})
        if new_name != row["name"]:
            cur = await db.execute(
                "SELECT 1 FROM creative_drafts WHERE account_id = ? AND campaign_type = ? "
                "AND name = ? AND id != ?",
                (account_id, row["campaign_type"], new_name, draft_id),
            )
            if await cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail={"error": "NAME_TAKEN",
                            "message": f"a {row['campaign_type']} draft named {new_name!r} already exists"},
                )
        new_bundle_json = (
            json.dumps(body.bundle) if body.bundle is not None else row["bundle_json"]
        )
        await db.execute(
            "UPDATE creative_drafts SET name = ?, bundle_json = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (new_name, new_bundle_json, draft_id),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM creative_drafts WHERE id = ?", (draft_id,))
        row = await cur.fetchone()
    finally:
        await db.close()
    return _row_to_draft(row)


@drafts_router.delete("/{account_id}/creative-drafts/{draft_id}")
async def delete_creative_draft(account_id: str, draft_id: str) -> Dict[str, Any]:
    """Delete ONE draft. Deleting one leaves every other draft intact (FR4.2)."""
    db = await get_db()
    try:
        cur = await db.execute(
            "DELETE FROM creative_drafts WHERE id = ? AND account_id = ?",
            (draft_id, account_id),
        )
        await db.commit()
        deleted = cur.rowcount or 0
    finally:
        await db.close()
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "draft not found"})
    return {"deleted": draft_id}
