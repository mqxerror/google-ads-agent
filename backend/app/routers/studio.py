"""Studio router — higgsfield generation endpoints.

Architectural invariants (mirror the campaigns_repo / chat-panel split-
brain fixes shipped earlier this month):

1. **Job lifecycle = DB row, NEVER in-memory state.** Every generation
   pre-creates an `ad_assets` row with status=pending. The async worker
   updates the row to running → completed | failed | nsfw. The SSE
   stream is a *view* of the row, not the source — if the user closes
   the tab mid-render and refreshes, GET /jobs/:id reconciles
   correctly.

2. **`ad_assets.id` is FE-facing.** Higgsfield's `job_id` lives in
   `higgsfield_job_id` (UNIQUE index, handles the retry-after-polling-
   5xx recovery path without duplicating rows).

3. **Synchronous local download.** Higgsfield CDN URLs expire in
   24-48h, so we download to ASSETS_DIR on success and serve via the
   existing `/api/assets/file/<filename>` route. Mirrors the
   stock-image adoption flow.

4. **Module-level Semaphore enforces higgsfield's per-account 6-job
   cap.** The CLI returns 403 if we exceed it, so queueing extra
   requests in Python is friendlier than letting the upstream reject.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.higgsfield_client import (
    HiggsfieldClient,
    HiggsfieldError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio"])


# Higgsfield's API enforces a 6-parallel-job cap per account. Queuing in
# Python is friendlier than letting the upstream return 403.
_GENERATION_SEMAPHORE = asyncio.Semaphore(6)

# Keep references to in-flight tasks so they aren't GC'd mid-run.
# A done-callback removes them when the task completes.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


# ── Pydantic models ───────────────────────────────────────────────────


class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str = "nano_banana_2"
    aspect_ratios: list[str] = Field(default_factory=lambda: ["1:1"])
    variants_per_aspect: int = Field(default=1, ge=1, le=6)
    soul_id: Optional[str] = None
    account_id: Optional[str] = None
    campaign_id: Optional[str] = None


class GenerateImageResponse(BaseModel):
    asset_ids: list[str]


# Video generation accepts a single aspect (most video models support
# one aspect per submission; multi-aspect for video isn't worth the
# parallelism cost) and a duration in seconds — model-dependent
# constraints (e.g. veo3_1 caps at 8s) are enforced by Higgsfield's
# upstream, surfaced via the existing structured error path.
class GenerateVideoRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str = "veo3_1"
    aspect_ratio: str = "16:9"
    duration_seconds: int | None = Field(default=None, ge=1, le=60)
    soul_id: Optional[str] = None
    account_id: Optional[str] = None
    campaign_id: Optional[str] = None


class GenerateVideoResponse(BaseModel):
    asset_id: str


class JobStatusResponse(BaseModel):
    asset_id: str
    status: str
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    prompt: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    higgsfield_cdn_url: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/generate-image", response_model=GenerateImageResponse)
async def generate_image(body: GenerateImageRequest) -> GenerateImageResponse:
    """Kick off N = (aspects × variants) image generations.

    Returns immediately with the new asset_ids. The frontend then
    subscribes to /jobs/<id>/stream for each, or polls /jobs/<id>.
    Total generations capped at 6 per request (Higgsfield's per-account
    parallel limit); pydantic validators enforce this client-side too.
    """
    n_aspects = len(body.aspect_ratios)
    if n_aspects == 0:
        raise HTTPException(
            status_code=400,
            detail="Must request at least one aspect_ratio",
        )
    total = n_aspects * body.variants_per_aspect
    if total > 6:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Total parallel generations = {total} ({n_aspects} aspects × "
                f"{body.variants_per_aspect} variants/aspect) > Higgsfield's "
                f"per-account 6-job cap. Reduce variants or aspects."
            ),
        )

    # Pre-create one row per (aspect × variant) so the FE can subscribe
    # immediately and the worker has a row to update.
    asset_ids: list[str] = []
    db = await get_db()
    try:
        for aspect in body.aspect_ratios:
            for _ in range(body.variants_per_aspect):
                asset_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO ad_assets
                       (id, account_id, campaign_id, type, filename, url,
                        source, status, higgsfield_model, prompt,
                        aspect_ratio, soul_id, created_at)
                       VALUES (?, ?, ?, 'image', '', '', 'higgsfield',
                               'pending', ?, ?, ?, ?, datetime('now'))""",
                    (
                        asset_id, body.account_id, body.campaign_id,
                        body.model, body.prompt, aspect, body.soul_id,
                    ),
                )
                asset_ids.append(asset_id)
        await db.commit()
    finally:
        await db.close()

    # Fire one background task per asset.
    for asset_id, aspect in _expand(body.aspect_ratios, body.variants_per_aspect, asset_ids):
        task = asyncio.create_task(
            _run_image_job(
                asset_id=asset_id,
                model=body.model,
                prompt=body.prompt,
                aspect_ratio=aspect,
                soul_id=body.soul_id,
            )
        )
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)

    return GenerateImageResponse(asset_ids=asset_ids)


@router.post("/generate-video", response_model=GenerateVideoResponse)
async def generate_video(body: GenerateVideoRequest) -> GenerateVideoResponse:
    """Kick off a single video generation. Videos take 5-10+ minutes
    on veo3_1 / kling3_0 / seedance_2_0; the existing
    /jobs/:id/stream SSE handles both image and video state changes
    polymorphically (it just polls the row's status).

    Returns immediately with the new asset_id. Frontend subscribes to
    /jobs/<id>/stream for progress; tab refresh mid-render reconciles
    via the DB row.
    """
    asset_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets
               (id, account_id, campaign_id, type, filename, url,
                source, status, higgsfield_model, prompt,
                aspect_ratio, soul_id, duration, created_at)
               VALUES (?, ?, ?, 'video', '', '', 'higgsfield',
                       'pending', ?, ?, ?, ?, ?, datetime('now'))""",
            (
                asset_id, body.account_id, body.campaign_id,
                body.model, body.prompt, body.aspect_ratio, body.soul_id,
                body.duration_seconds,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    task = asyncio.create_task(
        _run_video_job(
            asset_id=asset_id,
            model=body.model,
            prompt=body.prompt,
            aspect_ratio=body.aspect_ratio,
            soul_id=body.soul_id,
            duration_seconds=body.duration_seconds,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return GenerateVideoResponse(asset_id=asset_id)


@router.get("/jobs/{asset_id}", response_model=JobStatusResponse)
async def get_job(asset_id: str) -> JobStatusResponse:
    """Single-shot job status read. Polling fallback when SSE drops."""
    row = await _read_asset_row(asset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _row_to_response(row)


@router.get("/jobs/{asset_id}/stream")
async def stream_job(asset_id: str) -> StreamingResponse:
    """Server-Sent Events stream of the asset row's status. Polls the
    DB every 1.5s and emits one event per status change; closes after
    a terminal status (completed | failed | nsfw)."""

    async def event_source():
        last_status: Optional[str] = None
        # Cap at 20 minutes — well above the longest video job. Prevents
        # zombie streams if a worker crashes without updating the row.
        max_iters = int(20 * 60 / 1.5)
        for _ in range(max_iters):
            row = await _read_asset_row(asset_id)
            if row is None:
                yield f"data: {json.dumps({'error': 'asset not found'})}\n\n"
                return
            status = row.get("status") or "unknown"
            if status != last_status:
                resp = _row_to_response(row)
                yield f"data: {resp.model_dump_json()}\n\n"
                last_status = status
            if status in ("completed", "failed", "nsfw"):
                return
            await asyncio.sleep(1.5)
        yield f"data: {json.dumps({'error': 'stream timeout (20m)'})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # required for nginx, harmless elsewhere
        },
    )


# ── Worker ────────────────────────────────────────────────────────────


async def _run_image_job(
    *,
    asset_id: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    soul_id: Optional[str],
) -> None:
    """Background task: submit higgsfield, download result, update row.

    Never raises — all failures land in `status=failed` so the FE always
    sees a terminal state. Acquires the global semaphore to enforce the
    6-job parallelism cap.
    """
    async with _GENERATION_SEMAPHORE:
        await _update_asset_status(asset_id, status="running")
        client = HiggsfieldClient()
        try:
            result = await client.submit_image(
                model=model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                **({"soul_id": soul_id} if soul_id else {}),
            )
        except HiggsfieldError as e:
            await _update_asset_status(
                asset_id, status="failed" if e.code != "nsfw" else "nsfw",
                error_code=e.code or "run",
                error_message=e.message,
            )
            logger.warning("higgsfield job failed (asset=%s code=%s): %s", asset_id, e.code, e.message)
            return
        except Exception as e:
            await _update_asset_status(
                asset_id, status="failed",
                error_code="internal",
                error_message=str(e)[:500],
            )
            logger.exception("higgsfield job unexpected failure (asset=%s)", asset_id)
            return

        cdn_url = result.get("image_url")
        if not cdn_url:
            await _update_asset_status(
                asset_id, status="failed",
                error_code="shape",
                error_message="higgsfield returned no image URL",
            )
            return

        # Higgsfield's job id is in the raw envelope's first job. Capture
        # it for the UNIQUE index — guards against the polling-retry
        # path creating a phantom duplicate row.
        raw = result.get("raw") or []
        hf_job_id = None
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            hf_job_id = str(raw[0].get("id") or "") or None

        # Download CDN bytes into ASSETS_DIR.
        try:
            local_url, filename, width, height, size_bytes = await _download_to_assets(
                asset_id=asset_id, cdn_url=cdn_url,
            )
        except Exception as e:
            # Generation succeeded but local download didn't — surface
            # the CDN URL anyway so the user can still use the asset
            # (with the known caveat that CDN URLs expire in 24-48h).
            await _update_asset_status(
                asset_id, status="completed",
                url=cdn_url,
                higgsfield_cdn_url=cdn_url,
                higgsfield_job_id=hf_job_id,
                error_code="download_failed",
                error_message=f"CDN download failed (asset still usable from CDN): {str(e)[:300]}",
            )
            logger.warning("higgsfield download failed for asset=%s: %s", asset_id, e)
            return

        await _update_asset_completed(
            asset_id=asset_id,
            url=local_url,
            filename=filename,
            width=width,
            height=height,
            size_bytes=size_bytes,
            higgsfield_cdn_url=cdn_url,
            higgsfield_job_id=hf_job_id,
        )
        logger.info("higgsfield job completed (asset=%s job=%s)", asset_id, hf_job_id)


async def _run_video_job(
    *,
    asset_id: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    soul_id: Optional[str],
    duration_seconds: Optional[int],
) -> None:
    """Background task for video generation. Same shape as the image
    job, but with HiggsfieldClient(timeout_s=600) for the 5-10 min
    render time. Still respects the 6-parallel semaphore so video and
    image jobs share the per-account concurrency budget.
    """
    async with _GENERATION_SEMAPHORE:
        await _update_asset_status(asset_id, status="running")
        # Video timeout is 10 minutes — well above the 30-180s image
        # range. _DEFAULT_TIMEOUT_S is constructor-overridable so this
        # is a clean lever without forking the client.
        client = HiggsfieldClient(timeout_s=600.0)
        params: dict[str, Any] = {"aspect_ratio": aspect_ratio}
        if soul_id:
            params["soul_id"] = soul_id
        if duration_seconds is not None:
            # Higgsfield's CLI accepts --duration as a model-specific
            # passthrough; some models cap (veo3_1 = 8s) and reject
            # higher values upstream. The structured `run` error path
            # already surfaces the rejection cleanly.
            params["duration"] = duration_seconds
        try:
            result = await client.submit_video(
                model=model, prompt=prompt, **params,
            )
        except HiggsfieldError as e:
            await _update_asset_status(
                asset_id, status="failed" if e.code != "nsfw" else "nsfw",
                error_code=e.code or "run",
                error_message=e.message,
            )
            logger.warning("higgsfield video failed (asset=%s code=%s): %s", asset_id, e.code, e.message)
            return
        except Exception as e:
            await _update_asset_status(
                asset_id, status="failed",
                error_code="internal",
                error_message=str(e)[:500],
            )
            logger.exception("higgsfield video unexpected failure (asset=%s)", asset_id)
            return

        cdn_url = result.get("image_url")  # client uses same key for video
        if not cdn_url:
            await _update_asset_status(
                asset_id, status="failed",
                error_code="shape",
                error_message="higgsfield returned no video URL",
            )
            return

        raw = result.get("raw") or []
        hf_job_id = None
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            hf_job_id = str(raw[0].get("id") or "") or None

        try:
            local_url, filename, _width, _height, size_bytes = await _download_to_assets(
                asset_id=asset_id, cdn_url=cdn_url,
            )
        except Exception as e:
            await _update_asset_status(
                asset_id, status="completed",
                url=cdn_url,
                higgsfield_cdn_url=cdn_url,
                higgsfield_job_id=hf_job_id,
                error_code="download_failed",
                error_message=f"CDN download failed (asset still usable from CDN): {str(e)[:300]}",
            )
            logger.warning("higgsfield video download failed for asset=%s: %s", asset_id, e)
            return

        # For videos we don't probe width/height/duration via PIL — the
        # row already has duration from the user request. ffprobe would
        # be more accurate but is out of scope for this slice; the
        # existing video pipeline has its own metadata extraction
        # (services/video.py) the operator can reuse if needed.
        await _update_asset_completed(
            asset_id=asset_id,
            url=local_url,
            filename=filename,
            width=None,
            height=None,
            size_bytes=size_bytes,
            higgsfield_cdn_url=cdn_url,
            higgsfield_job_id=hf_job_id,
        )
        logger.info("higgsfield video completed (asset=%s job=%s)", asset_id, hf_job_id)


# ── DB helpers ────────────────────────────────────────────────────────


async def _read_asset_row(asset_id: str) -> Optional[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM ad_assets WHERE id = ?", (asset_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _update_asset_status(
    asset_id: str, *,
    status: str,
    url: Optional[str] = None,
    higgsfield_cdn_url: Optional[str] = None,
    higgsfield_job_id: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Generic row-update. Each field is conditional so we only touch
    columns that have a non-None value."""
    sets: list[str] = ["status = ?"]
    params: list[Any] = [status]
    if url is not None:
        sets.append("url = ?"); params.append(url)
    if higgsfield_cdn_url is not None:
        sets.append("higgsfield_cdn_url = ?"); params.append(higgsfield_cdn_url)
    if higgsfield_job_id is not None:
        sets.append("higgsfield_job_id = ?"); params.append(higgsfield_job_id)
    if error_code is not None:
        sets.append("error_code = ?"); params.append(error_code)
    if error_message is not None:
        sets.append("error_message = ?"); params.append(error_message)
    params.append(asset_id)
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE ad_assets SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def _update_asset_completed(
    *,
    asset_id: str,
    url: str,
    filename: str,
    width: Optional[int],
    height: Optional[int],
    size_bytes: int,
    higgsfield_cdn_url: str,
    higgsfield_job_id: Optional[str],
) -> None:
    db = await get_db()
    try:
        await db.execute(
            """UPDATE ad_assets SET
                  status = 'completed',
                  url = ?,
                  filename = ?,
                  width = ?,
                  height = ?,
                  size_bytes = ?,
                  higgsfield_cdn_url = ?,
                  higgsfield_job_id = ?
               WHERE id = ?""",
            (url, filename, width, height, size_bytes, higgsfield_cdn_url, higgsfield_job_id, asset_id),
        )
        await db.commit()
    finally:
        await db.close()


# ── CDN download ──────────────────────────────────────────────────────


async def _download_to_assets(
    *, asset_id: str, cdn_url: str,
) -> tuple[str, str, Optional[int], Optional[int], int]:
    """Download the CDN URL into ASSETS_DIR/<asset_id>.<ext> and return
    (local_url, filename, width, height, size_bytes). Local URL is
    served by the existing /api/assets/file/<filename> route."""
    from app.routers.assets import ASSETS_DIR

    async with httpx.AsyncClient(
        timeout=60.0, follow_redirects=True,
    ) as client:
        resp = await client.get(cdn_url)
        resp.raise_for_status()
        data = resp.content
        content_type = resp.headers.get("content-type", "").lower()

    # Pick extension from URL or content-type. We persist images as the
    # original format (no re-encoding) so quality is preserved.
    ext = ".png"
    if "jpeg" in content_type or cdn_url.lower().endswith((".jpg", ".jpeg")):
        ext = ".jpg"
    elif "webp" in content_type or cdn_url.lower().endswith(".webp"):
        ext = ".webp"
    elif "mp4" in content_type or cdn_url.lower().endswith(".mp4"):
        ext = ".mp4"
    elif cdn_url.lower().endswith(".png"):
        ext = ".png"
    filename = f"{asset_id}{ext}"
    dest: Path = ASSETS_DIR / filename
    dest.write_bytes(data)

    width = height = None
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        try:
            from PIL import Image as _PIL
            with _PIL.open(dest) as im:
                width, height = im.size
        except Exception:
            pass

    return (
        f"/api/assets/file/{filename}",
        filename,
        width,
        height,
        len(data),
    )


# ── Helpers ───────────────────────────────────────────────────────────


def _expand(aspects: list[str], variants: int, asset_ids: list[str]):
    """Pair each asset_id with its aspect, preserving the order we
    INSERT'd above so the FE can correlate."""
    iterator = iter(asset_ids)
    for aspect in aspects:
        for _ in range(variants):
            yield next(iterator), aspect


def _row_to_response(row: dict[str, Any]) -> JobStatusResponse:
    return JobStatusResponse(
        asset_id=row["id"],
        status=row.get("status") or "unknown",
        url=row.get("url") or None,
        thumbnail_url=row.get("thumbnail_url") or None,
        prompt=row.get("prompt"),
        model=row.get("higgsfield_model"),
        aspect_ratio=row.get("aspect_ratio"),
        higgsfield_cdn_url=row.get("higgsfield_cdn_url"),
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        width=row.get("width"),
        height=row.get("height"),
        created_at=row.get("created_at"),
    )
