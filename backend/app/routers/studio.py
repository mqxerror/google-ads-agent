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
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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
    # Higgsfield's duration semantics differ per model: Veo accepts
    # enum strings ("4","6","8"), Kling accepts an integer up to 15.
    # Frontend sends an integer; we stringify in the worker because the
    # CLI handles both forms. The legacy "duration_seconds" name is
    # kept so the JS doesn't have to know about higgsfield's "duration"
    # param name.
    duration_seconds: int | None = Field(default=None, ge=1, le=60)
    # Kling's `mode` (std / pro / 4k) — the cheap/expensive selector
    # the user asked for ("kling 720 cheap" vs default 4k).
    mode: Optional[str] = None
    # Veo's `quality` (basic / high / ultra) and `model` sub-variant
    # (veo-3-1-fast / veo-3-1-preview).
    quality: Optional[str] = None
    submodel: Optional[str] = None
    # Kling's `sound` (on / off).
    sound: Optional[str] = None
    soul_id: Optional[str] = None
    account_id: Optional[str] = None
    campaign_id: Optional[str] = None


class GenerateVideoResponse(BaseModel):
    asset_id: str


class CostEstimateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str
    aspect_ratio: Optional[str] = None
    duration_seconds: Optional[int] = None
    mode: Optional[str] = None
    quality: Optional[str] = None
    soul_id: Optional[str] = None


class CostEstimateResponse(BaseModel):
    credits: int
    credits_exact: float


class SoulCharacter(BaseModel):
    id: str
    account_id: str
    name: str
    soul_id: Optional[str] = None
    training_model: str  # 'soul-2' | 'soul-cinematic'
    status: str          # pending | training | ready | failed
    reference_image_paths: Optional[list[str]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    ready_at: Optional[str] = None


class BalanceResponse(BaseModel):
    """Pass-through of `higgsfield account status`. Mirrors CLI shape
    `{email, credits, subscription_plan_type}` so a future Higgsfield
    API addition flows through to the UI without a code change."""

    credits: Optional[float] = None
    email: Optional[str] = None
    plan: Optional[str] = None  # subscription_plan_type
    extras: dict[str, Any] = Field(default_factory=dict)


class CostEstimateNullable(BaseModel):
    """Cost-estimate response that tolerates per-model param mismatches.
    Veo 3 (older) requires --input_image and rejects --duration; instead
    of 502'ing the whole UI, we return credits=null + error_code so the
    frontend can show "model doesn't fit these params" inline rather
    than displaying a useless "—" badge."""

    credits: Optional[int] = None
    credits_exact: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


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


@router.post("/cost-estimate", response_model=CostEstimateNullable)
async def cost_estimate(body: CostEstimateRequest) -> CostEstimateNullable:
    """Live cost estimate. Wraps `higgsfield generate cost`.

    Returns a nullable shape — credits=null with error_code/message
    when a model rejects the params we sent (Veo 3 old requires
    `--input_image`; Wan accepts duration as enum strings only; etc).
    The UI shows "model needs different params" inline instead of an
    empty "—" with no explanation.
    """
    client = HiggsfieldClient(timeout_s=30.0)
    params: dict[str, Any] = {}
    if body.aspect_ratio:
        params["aspect_ratio"] = body.aspect_ratio
    if body.duration_seconds is not None:
        params["duration"] = body.duration_seconds
    if body.mode:
        params["mode"] = body.mode
    if body.quality:
        params["quality"] = body.quality
    if body.soul_id:
        params["soul_id"] = body.soul_id
    try:
        envelope = await client.estimate_cost(
            model=body.model, prompt=body.prompt, **params,
        )
        return CostEstimateNullable(
            credits=int(envelope.get("credits", 0)),
            credits_exact=float(envelope.get("credits_exact", 0)),
        )
    except HiggsfieldError as e:
        # NOT a 4xx/5xx — the UI needs the structured info to render a
        # human-readable explanation inline. 200 with error fields.
        logger.info("cost-estimate soft-failed for %s: %s", body.model, e.message)
        return CostEstimateNullable(
            credits=None, credits_exact=None,
            error_code=e.code or "run",
            error_message=e.message,
        )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance() -> BalanceResponse:
    """Operator's current Higgsfield credit balance. Surfaced as a
    badge in the Studio header so the user knows how much they have
    to spend before triggering big video runs."""
    client = HiggsfieldClient(timeout_s=15.0)
    try:
        envelope = await client.get_balance()
    except HiggsfieldError as e:
        raise HTTPException(
            status_code=401 if e.code == "auth" else 502,
            detail={"code": e.code, "message": e.message},
        )
    return BalanceResponse(
        credits=envelope.get("credits"),
        email=envelope.get("email"),
        plan=envelope.get("subscription_plan_type") or envelope.get("plan"),
        extras={
            k: v for k, v in envelope.items()
            if k not in ("credits", "email", "subscription_plan_type", "plan")
        },
    )


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
            mode=body.mode,
            quality=body.quality,
            submodel=body.submodel,
            sound=body.sound,
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


# ── Landing-page brief extraction ─────────────────────────────────────


class ExtractBriefRequest(BaseModel):
    url: str = Field(min_length=1)
    # What kind of prompt to draft from the page. The drafter tunes
    # its system prompt around this so a "video" prompt focuses on
    # action / motion / scene, while "image" focuses on composition
    # / lighting / mood.
    target: str = "image"  # 'image' | 'video'
    # Account + campaign context for pinned-claims injection. When
    # provided, the drafter loads data/memory/{account}/{campaign}/
    # pinned_facts.md and grounds the social-proof variant in
    # operator-verified claims (the meta-ads-agent pattern). Without
    # these, social-proof falls back to composition-only authority.
    account_id: Optional[str] = None
    campaign_id: Optional[str] = None


class BriefVariant(BaseModel):
    """One angle variant produced by the prompt drafter. Three of these
    are returned per extract-brief call: problem-led, aspirational,
    social-proof. Operator picks the one that fits the campaign's
    creative rotation."""

    angle: str        # 'problem-led' | 'aspirational' | 'social-proof'
    prompt: str       # the actual generation prompt
    rationale: str    # one-line "why this composition fits"


class DecomposedBrief(BaseModel):
    """Structured brief from Stage 1 of the drafter. Surfaced to the
    UI so operators can see what fed into the variant prompts — keeps
    the output auditable; if a variant is off, the brief usually tells
    you why."""

    subject: str
    setting: str
    value_prop: str
    audience: str
    tone: str
    program: str
    hard_constraints: list[str] = Field(default_factory=list)
    claim_hints: list[str] = Field(default_factory=list)


class ExtractBriefResponse(BaseModel):
    url: str
    final_url: str
    title: Optional[str] = None
    description: Optional[str] = None
    h1: Optional[str] = None
    body_excerpt: Optional[str] = None
    og: dict[str, str] = Field(default_factory=dict)
    # Multi-stage output: the structured brief (Stage 1) + three angle
    # variants (Stage 2).
    brief: Optional[DecomposedBrief] = None
    variants: list[BriefVariant] = Field(default_factory=list)
    pinned_claims_used: list[str] = Field(default_factory=list)
    # Back-compat alias: first variant's prompt. Old FE callers that
    # haven't switched to the variants[] picker still get a usable
    # single prompt.
    drafted_prompt: str = ""


@router.post("/extract-brief", response_model=ExtractBriefResponse)
async def extract_brief(body: ExtractBriefRequest) -> ExtractBriefResponse:
    """Fetch a landing-page URL → decompose into a structured brief
    → draft three angle-specific generation prompts.

    Two-stage Claude pipeline (modeled on meta-ads-agent's
    intent_decomposer). Stage 1 distills page signals into a clean
    brief; Stage 2 uses the visual_director role file + the
    campaign's pinned facts to draft three angle variants
    (problem-led / aspirational / social-proof). Operator picks one.

    The single-shot `drafted_prompt` field is kept as a back-compat
    alias for the first variant so older FE callers don't break.
    """
    from app.services.page_fetcher import fetch, PageFetchError
    from app.services.prompt_drafter import draft_variants, PromptDrafterError

    # Step 1 — fetch + parse.
    try:
        page = await fetch(body.url)
    except PageFetchError as e:
        raise HTTPException(status_code=400, detail={"code": "fetch_failed", "message": str(e)})

    # Steps 2 + 3 — decompose into structured brief, then draft 3 variants.
    try:
        package = await draft_variants(
            page=page.to_dict(),
            target=body.target,
            account_id=body.account_id,
            campaign_id=body.campaign_id,
        )
    except PromptDrafterError as e:
        raise HTTPException(
            status_code=502,
            detail={"code": "drafter_failed", "message": str(e)},
        )

    brief_obj = DecomposedBrief(**package["brief"])
    variant_objs = [BriefVariant(**v) for v in package["variants"]]
    # Back-compat: first non-empty variant prompt as drafted_prompt.
    fallback = next(
        (v.prompt for v in variant_objs if v.prompt),
        "",
    )

    return ExtractBriefResponse(
        url=page.url,
        final_url=page.final_url,
        title=page.title,
        description=page.description,
        h1=page.h1,
        body_excerpt=(page.body_excerpt or "")[:500],
        og=page.og,
        brief=brief_obj,
        variants=variant_objs,
        pinned_claims_used=package.get("pinned_claims_used", []),
        drafted_prompt=fallback,
    )


# ── Marketing Studio presets ──────────────────────────────────────────


class MarketingHook(BaseModel):
    """One Marketing Studio hook — a pre-engineered ad concept with a
    prompt + media previews. Operators pick one as the starting point
    for a generation instead of writing prompts from scratch."""

    id: str
    name: str
    type: Optional[str] = None
    prompt: str
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    is_pinned: bool = False
    source: Optional[str] = None


@router.get("/marketing-studio/hooks", response_model=list[MarketingHook])
async def list_marketing_hooks() -> list[MarketingHook]:
    """Pre-built ad concepts (UGC, tutorial, unboxing, etc.) from
    Higgsfield's Marketing Studio. Each hook carries a prompt + preview
    so the operator can browse visually before picking one to drop
    into the generator."""
    client = HiggsfieldClient(timeout_s=30.0)
    try:
        items = await client.marketing_hooks_list()
    except HiggsfieldError as e:
        raise HTTPException(
            status_code=401 if e.code == "auth" else 502,
            detail={"code": e.code, "message": e.message},
        )
    out: list[MarketingHook] = []
    for item in items:
        out.append(MarketingHook(
            id=str(item.get("id") or ""),
            name=str(item.get("name") or "Untitled"),
            type=item.get("type"),
            prompt=str(item.get("prompt") or ""),
            thumbnail_url=item.get("thumbnail_url"),
            video_url=item.get("video_url"),
            is_pinned=bool(item.get("is_pinned") or False),
            source=item.get("source"),
        ))
    return out


# ── Soul training ─────────────────────────────────────────────────────


@router.post("/soul/train", response_model=SoulCharacter)
async def train_soul(
    name: str = Form(...),
    account_id: str = Form(...),
    training_model: str = Form(default="soul-2"),  # soul-2 | soul-cinematic
    images: list[UploadFile] = File(...),
) -> SoulCharacter:
    """Train a new Soul character. Higgsfield needs 5-20 reference
    photos of the subject (best: varied angles, lighting, expressions).
    Training takes 5-15 minutes upstream; this endpoint returns
    immediately with status=pending and the actual training runs in a
    background task that updates the row when it settles.

    The face-consistent generation is the differentiator: once a Soul
    is trained, picking text2image_soul_v2 / soul_cinematic / soul_cast
    + this soul_id produces images / videos where the person looks
    recognizably the same across every render.
    """
    if not (5 <= len(images) <= 20):
        raise HTTPException(
            status_code=400,
            detail=f"Soul training needs 5-20 reference images; got {len(images)}",
        )
    if training_model not in ("soul-2", "soul-cinematic"):
        raise HTTPException(
            status_code=400,
            detail="training_model must be 'soul-2' or 'soul-cinematic'",
        )

    # Save reference images locally so we can re-upload to higgsfield
    # (CLI wants file paths) AND so the UI can show them later.
    from app.routers.assets import ASSETS_DIR
    soul_id_local = str(uuid.uuid4())
    soul_dir = ASSETS_DIR / "souls" / soul_id_local
    soul_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for i, image in enumerate(images):
        suffix = Path(image.filename or f"ref{i}.png").suffix or ".png"
        if suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            suffix = ".png"
        dest = soul_dir / f"ref{i:02d}{suffix}"
        contents = await image.read()
        dest.write_bytes(contents)
        saved_paths.append(str(dest))

    # Pre-create the soul_characters row so the UI sees pending state
    # immediately. Background task does the heavy lifting.
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO soul_characters
               (id, account_id, name, training_model, status,
                reference_image_paths, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', ?, datetime('now'), datetime('now'))""",
            (
                soul_id_local, account_id, name, training_model,
                json.dumps(saved_paths),
            ),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT * FROM soul_characters WHERE id = ?", (soul_id_local,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    task = asyncio.create_task(
        _run_soul_training(
            row_id=soul_id_local,
            name=name,
            training_model=training_model,
            local_paths=saved_paths,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return _row_to_soul(dict(row))


@router.get("/soul", response_model=list[SoulCharacter])
async def list_souls(account_id: Optional[str] = None) -> list[SoulCharacter]:
    """List trained / training Soul characters. Account-scoped: each
    operator's account sees only their own. Sorted newest first so the
    most recent training is at the top of the picker."""
    db = await get_db()
    try:
        if account_id:
            cur = await db.execute(
                "SELECT * FROM soul_characters WHERE account_id = ? ORDER BY created_at DESC",
                (account_id,),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM soul_characters ORDER BY created_at DESC",
            )
        rows = await cur.fetchall()
        return [_row_to_soul(dict(r)) for r in rows]
    finally:
        await db.close()


@router.get("/soul/{soul_pk}", response_model=SoulCharacter)
async def get_soul(soul_pk: str) -> SoulCharacter:
    """Single Soul read by our internal id (not higgsfield's soul_id).
    Used by the UI to refresh status after training submission."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM soul_characters WHERE id = ?", (soul_pk,),
        )
        row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Soul not found")
        return _row_to_soul(dict(row))
    finally:
        await db.close()


def _row_to_soul(row: dict[str, Any]) -> SoulCharacter:
    refs_raw = row.get("reference_image_paths") or "null"
    try:
        refs = json.loads(refs_raw)
    except Exception:
        refs = None
    return SoulCharacter(
        id=row["id"],
        account_id=row["account_id"],
        name=row["name"],
        soul_id=row.get("soul_id"),
        training_model=row["training_model"],
        status=row["status"],
        reference_image_paths=refs if isinstance(refs, list) else None,
        error_code=row.get("error_code"),
        error_message=row.get("error_message"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        ready_at=row.get("ready_at"),
    )


async def _run_soul_training(
    *,
    row_id: str,
    name: str,
    training_model: str,
    local_paths: list[str],
) -> None:
    """Background task: upload each reference image to higgsfield, fire
    soul-id create, then wait for training to settle.

    Updates the soul_characters row through states: pending → training
    → ready (with the higgsfield soul_id) | failed. All exceptions
    land in status=failed so the UI always sees a terminal state.
    """
    async with _GENERATION_SEMAPHORE:
        await _update_soul_row(row_id, status="training")
        client = HiggsfieldClient(timeout_s=120.0)

        # Step 1: upload each reference image, collect upload IDs.
        upload_ids: list[str] = []
        for path in local_paths:
            try:
                env = await client.upload_media(file_path=path)
                uid = str(env.get("id") or "").strip()
                if not uid:
                    raise HiggsfieldError(
                        message=f"upload returned no id: {env!r}", code="shape",
                    )
                upload_ids.append(uid)
            except HiggsfieldError as e:
                await _update_soul_row(
                    row_id, status="failed",
                    error_code=e.code or "run",
                    error_message=f"upload {Path(path).name}: {e.message}",
                )
                return
            except Exception as e:
                await _update_soul_row(
                    row_id, status="failed",
                    error_code="internal",
                    error_message=f"upload {Path(path).name}: {str(e)[:300]}",
                )
                return

        # Step 2: create the Soul reference.
        try:
            env = await client.soul_create(
                name=name, upload_ids=upload_ids, model=training_model,
            )
            soul_id_remote = str(env.get("id") or env.get("soul_id") or "").strip()
            if not soul_id_remote:
                raise HiggsfieldError(
                    message=f"soul-id create returned no id: {env!r}", code="shape",
                )
        except HiggsfieldError as e:
            await _update_soul_row(
                row_id, status="failed",
                error_code=e.code or "run",
                error_message=f"soul-id create: {e.message}",
            )
            return
        except Exception as e:
            await _update_soul_row(
                row_id, status="failed",
                error_code="internal",
                error_message=f"soul-id create: {str(e)[:300]}",
            )
            return

        await _update_soul_row(row_id, soul_id=soul_id_remote)

        # Step 3: wait for training. Long-running upstream — give it
        # 30 minutes ceiling. The CLI exits on terminal state.
        try:
            env = await client.soul_wait(soul_id=soul_id_remote, timeout_s=1800.0)
            status = str(env.get("status") or "").lower()
            if status in ("ready", "completed", "complete", "success", "done"):
                await _update_soul_row(row_id, status="ready", ready_at_now=True)
                logger.info("Soul training ready: %s (soul_id=%s)", row_id, soul_id_remote)
            else:
                await _update_soul_row(
                    row_id, status="failed",
                    error_code="training_failed",
                    error_message=f"upstream status: {status or 'unknown'}",
                )
        except HiggsfieldError as e:
            await _update_soul_row(
                row_id, status="failed",
                error_code=e.code or "run",
                error_message=f"soul-id wait: {e.message}",
            )
        except Exception as e:
            await _update_soul_row(
                row_id, status="failed",
                error_code="internal",
                error_message=f"soul-id wait: {str(e)[:300]}",
            )


async def _update_soul_row(
    row_id: str, *,
    status: Optional[str] = None,
    soul_id: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    ready_at_now: bool = False,
) -> None:
    sets: list[str] = ["updated_at = datetime('now')"]
    params: list[Any] = []
    if status is not None:
        sets.append("status = ?"); params.append(status)
    if soul_id is not None:
        sets.append("soul_id = ?"); params.append(soul_id)
    if error_code is not None:
        sets.append("error_code = ?"); params.append(error_code)
    if error_message is not None:
        sets.append("error_message = ?"); params.append(error_message)
    if ready_at_now:
        sets.append("ready_at = datetime('now')")
    params.append(row_id)
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE soul_characters SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()


# ── Video worker ──────────────────────────────────────────────────────


async def _run_video_job(
    *,
    asset_id: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    soul_id: Optional[str],
    duration_seconds: Optional[int],
    mode: Optional[str] = None,
    quality: Optional[str] = None,
    submodel: Optional[str] = None,
    sound: Optional[str] = None,
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
            # Higgsfield's CLI accepts --duration; per-model upstream
            # caps are enforced by Higgsfield (Veo enum 4/6/8; Kling ≤
            # 15). The structured `run` error path surfaces the rejection.
            params["duration"] = duration_seconds
        # Kling's `mode` — std/pro/4k. The user's "kling 720 cheap"
        # request maps to mode=std (cheapest, lowest res).
        if mode:
            params["mode"] = mode
        # Veo's `quality` (basic/high/ultra) and `model` sub-variant.
        if quality:
            params["quality"] = quality
        if submodel:
            params["model"] = submodel  # CLI param name is `model`
        # Kling's audio toggle.
        if sound:
            params["sound"] = sound
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
