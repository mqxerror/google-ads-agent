"""Video Director router — AI Video Studio project + brand-avatar CRUD.

Endpoints (plan §6.2 + avatars), all under the `/api/studio` prefix:

  POST   /video-projects                 create a project row + its conversation
  POST   /video-projects/{id}/draft      kick off a video_director_turn (chat_runner)
  PATCH  /video-projects/{id}            save operator edits (debounce-safe)
  GET    /video-projects/{id}            one project (storyboard parsed for the client)
  GET    /video-projects?account_id=…    list for an account (newest first)

  POST   /brand-avatars                  create a reusable brand avatar
  GET    /brand-avatars?account_id=…     list for an account
  GET    /brand-avatars/{id}             one avatar
  PATCH  /brand-avatars/{id}             update fields
  DELETE /brand-avatars/{id}             delete

DB-row-is-truth invariant (mirrors studio.py): the project row is the durable
source of truth for a Video-Director-led video. The kickoff endpoint only mints
a turn; the drafting state machine persists the storyboard back to the row.

Conversation↔campaign binding (plan §6.6): a project's conversation binds to
ONE campaign for life. Re-linking a project to a DIFFERENT campaign spawns a NEW
conversation and leaves the old one intact — never rebinds.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import get_db
from app.services import chat_runner
from app.services.video_director import video_director_turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio-video"])


# ── Request models ─────────────────────────────────────────────────────


class VideoProjectCreate(BaseModel):
    account_id: str
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    title: Optional[str] = None
    brief: Optional[str] = None
    model_id: str
    target_seconds: int
    aspect: Optional[str] = None
    consult_director: Optional[int] = None


class BriefSource(BaseModel):
    """How the operator seeded this draft. Backward compatible: omitted →
    None → the original text-brief behavior. `campaign` synthesizes the brief
    from the linked campaign's memory; `landing_page` grounds copy in a fetched
    page. `url` is required for landing_page (validated at the draft router)."""

    type: Literal["text", "campaign", "landing_page"] = "text"
    url: Optional[str] = None


class VideoProjectDraft(BaseModel):
    message: Optional[str] = None
    brief_source: Optional[BriefSource] = None


class VideoProjectPatch(BaseModel):
    title: Optional[str] = None
    brief: Optional[str] = None
    model_id: Optional[str] = None
    target_seconds: Optional[int] = None
    aspect: Optional[str] = None
    consult_director: Optional[int] = None
    storyboard_json: Optional[Any] = None      # str or dict — normalized to a string
    status: Optional[str] = None
    asset_id: Optional[str] = None
    campaign_id: Optional[str] = None


class BrandAvatarCreate(BaseModel):
    account_id: str
    name: str
    soul_id: Optional[str] = None
    voice_id: Optional[str] = None
    style_notes: Optional[str] = None


class BrandAvatarPatch(BaseModel):
    name: Optional[str] = None
    soul_id: Optional[str] = None
    voice_id: Optional[str] = None
    style_notes: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────


def _project_out(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize a project row for the client, parsing storyboard_json into an
    object (nicer for the FE) while the DB keeps the string."""
    out = dict(row)
    sb = out.get("storyboard_json")
    if isinstance(sb, str) and sb:
        try:
            out["storyboard_json"] = json.loads(sb)
        except (json.JSONDecodeError, TypeError):
            pass  # leave the raw string if it's not valid JSON
    return out


async def _fetch_project(db, project_id: str) -> dict[str, Any] | None:
    cur = await db.execute(
        "SELECT * FROM studio_video_projects WHERE id = ?", (project_id,)
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def _create_conversation(db, *, account_id, campaign_id, campaign_name, title) -> str:
    """Create a conversation bound to the campaign (or NULL), reusing the exact
    chat.py conversations INSERT path (plan §6.6)."""
    conv_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO conversations (id, account_id, campaign_id, campaign_name, title) "
        "VALUES (?, ?, ?, ?, ?)",
        (conv_id, account_id, campaign_id, campaign_name, title or "New conversation"),
    )
    return conv_id


# ── Video projects ─────────────────────────────────────────────────────


@router.post("/video-projects")
async def create_video_project(body: VideoProjectCreate) -> dict[str, Any]:
    project_id = str(uuid.uuid4())
    aspect = body.aspect or "16:9"
    consult = body.consult_director
    if consult is None:
        # §13 default: consult ON when campaign-linked, OFF otherwise.
        consult = 1 if body.campaign_id else 0
    title = body.title or ""

    db = await get_db()
    try:
        conv_id = await _create_conversation(
            db, account_id=body.account_id, campaign_id=body.campaign_id,
            campaign_name=body.campaign_name,
            title=title or "Video Director",
        )
        await db.execute(
            "INSERT INTO studio_video_projects "
            "(id, account_id, campaign_id, conversation_id, title, brief, "
            " model_id, target_seconds, aspect, consult_director, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'drafting')",
            (project_id, body.account_id, body.campaign_id, conv_id, title,
             body.brief or "", body.model_id, body.target_seconds, aspect, int(consult)),
        )
        await db.commit()
        row = await _fetch_project(db, project_id)
    finally:
        await db.close()
    return _project_out(row)


@router.post("/video-projects/{project_id}/draft")
async def draft_video_project(project_id: str, body: VideoProjectDraft) -> dict[str, Any]:
    brief_source = body.brief_source
    db = await get_db()
    try:
        row = await _fetch_project(db, project_id)
        if row is None:
            raise HTTPException(status_code=404, detail="video project not found")

        # Validate the brief source at the router (we still hold the request +
        # the row here). The turn surfaces synthesis failures as events, but a
        # structurally-impossible request is a 400 up front.
        if brief_source is not None:
            if brief_source.type == "campaign" and not row.get("campaign_id"):
                raise HTTPException(
                    status_code=400,
                    detail="brief_source.type='campaign' requires the project "
                           "to be linked to a campaign",
                )
            if brief_source.type == "landing_page" and not (brief_source.url or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="brief_source.type='landing_page' requires a url",
                )
            # Persist the serialized brief_source on the row (reuse this
            # existing write path — no new one). NULL for plain text drafts.
            serialized = None
            if brief_source.type != "text" or brief_source.url:
                serialized = json.dumps(brief_source.model_dump())
            await db.execute(
                "UPDATE studio_video_projects SET brief_source = ?, "
                "updated_at = datetime('now') WHERE id = ?",
                (serialized, project_id),
            )
            await db.commit()
    finally:
        await db.close()

    turn_id = await chat_runner.start(
        video_director_turn,
        conversation_id=row["conversation_id"],
        campaign_id=row["campaign_id"],
        mode="direct",
        project_id=project_id,
        message=(body.message or ""),
        brief_source=(brief_source.model_dump() if brief_source is not None else None),
    )
    return {"turn_id": turn_id}


@router.patch("/video-projects/{project_id}")
async def patch_video_project(project_id: str, body: VideoProjectPatch) -> dict[str, Any]:
    db = await get_db()
    try:
        row = await _fetch_project(db, project_id)
        if row is None:
            raise HTTPException(status_code=404, detail="video project not found")

        # Only update provided fields (debounce-safe partial save); always bump
        # updated_at. storyboard_json accepts a dict OR a string.
        sets: list[str] = []
        vals: list[Any] = []

        simple_fields = {
            "title": body.title, "brief": body.brief, "model_id": body.model_id,
            "target_seconds": body.target_seconds, "aspect": body.aspect,
            "consult_director": body.consult_director, "status": body.status,
            "asset_id": body.asset_id,
        }
        for col, val in simple_fields.items():
            if val is not None:
                sets.append(f"{col} = ?")
                vals.append(val)

        if body.storyboard_json is not None:
            sb = body.storyboard_json
            sets.append("storyboard_json = ?")
            vals.append(sb if isinstance(sb, str) else json.dumps(sb))

        # §6.6: re-link to a DIFFERENT non-null campaign → new conversation,
        # leave the old one intact (never rebind).
        if body.campaign_id is not None and body.campaign_id != row["campaign_id"]:
            sets.append("campaign_id = ?")
            vals.append(body.campaign_id)
            if body.campaign_id:  # only spawn a fresh thread for a real campaign
                new_conv = await _create_conversation(
                    db, account_id=row["account_id"], campaign_id=body.campaign_id,
                    campaign_name=None, title=row.get("title") or "Video Director",
                )
                sets.append("conversation_id = ?")
                vals.append(new_conv)

        sets.append("updated_at = datetime('now')")
        vals.append(project_id)
        await db.execute(
            f"UPDATE studio_video_projects SET {', '.join(sets)} WHERE id = ?",
            tuple(vals),
        )
        await db.commit()
        updated = await _fetch_project(db, project_id)
    finally:
        await db.close()
    return _project_out(updated)


@router.get("/video-projects/{project_id}")
async def get_video_project(project_id: str) -> dict[str, Any]:
    db = await get_db()
    try:
        row = await _fetch_project(db, project_id)
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="video project not found")
    return _project_out(row)


@router.get("/video-projects")
async def list_video_projects(account_id: str) -> list[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, account_id, campaign_id, conversation_id, title, model_id, "
            "target_seconds, aspect, status, asset_id, created_at, updated_at "
            "FROM studio_video_projects WHERE account_id = ? "
            "ORDER BY created_at DESC",
            (account_id,),
        )
        rows = [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()
    return rows


# ── Brand avatars ──────────────────────────────────────────────────────


@router.post("/brand-avatars")
async def create_brand_avatar(body: BrandAvatarCreate) -> dict[str, Any]:
    avatar_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO brand_avatars (id, account_id, name, soul_id, voice_id, style_notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (avatar_id, body.account_id, body.name, body.soul_id, body.voice_id,
             body.style_notes or ""),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM brand_avatars WHERE id = ?", (avatar_id,))
        row = await cur.fetchone()
    finally:
        await db.close()
    return dict(row)


@router.get("/brand-avatars")
async def list_brand_avatars(account_id: str) -> list[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM brand_avatars WHERE account_id = ? ORDER BY created_at DESC",
            (account_id,),
        )
        rows = [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()
    return rows


@router.get("/brand-avatars/{avatar_id}")
async def get_brand_avatar(avatar_id: str) -> dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM brand_avatars WHERE id = ?", (avatar_id,))
        row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="brand avatar not found")
    return dict(row)


@router.patch("/brand-avatars/{avatar_id}")
async def patch_brand_avatar(avatar_id: str, body: BrandAvatarPatch) -> dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM brand_avatars WHERE id = ?", (avatar_id,))
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="brand avatar not found")
        sets: list[str] = []
        vals: list[Any] = []
        for col, val in {
            "name": body.name, "soul_id": body.soul_id,
            "voice_id": body.voice_id, "style_notes": body.style_notes,
        }.items():
            if val is not None:
                sets.append(f"{col} = ?")
                vals.append(val)
        if sets:
            vals.append(avatar_id)
            await db.execute(
                f"UPDATE brand_avatars SET {', '.join(sets)} WHERE id = ?", tuple(vals)
            )
            await db.commit()
        cur = await db.execute("SELECT * FROM brand_avatars WHERE id = ?", (avatar_id,))
        updated = await cur.fetchone()
    finally:
        await db.close()
    return dict(updated)


@router.delete("/brand-avatars/{avatar_id}")
async def delete_brand_avatar(avatar_id: str) -> dict[str, Any]:
    db = await get_db()
    try:
        await db.execute("DELETE FROM brand_avatars WHERE id = ?", (avatar_id,))
        await db.commit()
    finally:
        await db.close()
    return {"ok": True}
