"""Video ad generation endpoints — script, render, asset serving."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.services.brand_reel import BrandReelRequest, generate_brand_reel, generate_scenes, generate_storyboard
from app.services.premium_reel import (
    PremiumReelRequest, StoryboardReelRequest,
    generate_premium_reel, generate_storyboard_reel,
)
from app.services.video import (
    ASSETS_DIR,
    VideoRequest,
    generate_video,
    heygen_create_talking_photo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["video"])


# ── Stock image search + AI gen — used both standalone and as auto-fill ──


class StockSearchRequest(BaseModel):
    query: str
    count: int = 4


@router.post("/stock/search")
async def stock_search(body: StockSearchRequest):
    """Search Unsplash + Pexels for landscape images matching the query.
    Returns the merged candidate list — frontend shows them in a picker.
    """
    from app.services.stock_images import search_stock
    matches = await search_stock(body.query, count=body.count)
    return {
        "query": body.query,
        "matches": [m.__dict__ for m in matches],
    }


class StockAdoptRequest(BaseModel):
    """Save a stock match into the user's library so it can be referenced as
    a normal ad_assets row by the renderer."""
    image_url: str
    description: str = ""
    provider: str = "stock"
    photographer: str = ""
    photographer_url: str = ""
    width: int | None = None
    height: int | None = None
    account_id: str | None = None
    campaign_id: str | None = None


@router.post("/stock/adopt")
async def stock_adopt(body: StockAdoptRequest):
    """Download a stock image and register it in ad_assets. Returns the new
    asset row so the frontend can drop it into the storyboard immediately."""
    from app.services.stock_images import download_image, save_remote_to_assets, _ext_from_url
    img = await download_image(body.image_url)
    if not img:
        raise HTTPException(status_code=502, detail="Failed to fetch image from provider")
    attribution = ""
    if body.photographer:
        attribution = f"Photo by {body.photographer}"
        if body.photographer_url:
            attribution += f" ({body.photographer_url})"
    return await save_remote_to_assets(
        image_bytes=img,
        ext=_ext_from_url(body.image_url),
        account_id=body.account_id,
        campaign_id=body.campaign_id,
        description=body.description,
        source=f"stock-{body.provider}" if not body.provider.startswith("stock") else body.provider,
        width=body.width,
        height=body.height,
        attribution=attribution,
    )


class AIGenerateRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    account_id: str | None = None
    campaign_id: str | None = None


@router.post("/stock/ai-generate")
async def stock_ai_generate(body: AIGenerateRequest):
    """Generate one image with Replicate FLUX from the prompt and register it
    in ad_assets. ~$0.003/image, ~3-5 s. Returns the asset row.
    """
    from app.services.stock_images import generate_with_flux, save_remote_to_assets
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    img = await generate_with_flux(body.prompt, aspect_ratio=body.aspect_ratio)
    if not img:
        raise HTTPException(
            status_code=502,
            detail="AI generation failed — check REPLICATE_API_TOKEN is set in .env",
        )
    return await save_remote_to_assets(
        image_bytes=img,
        ext=".jpg",
        account_id=body.account_id,
        campaign_id=body.campaign_id,
        description=body.prompt[:200],
        source="ai-flux",
        attribution="Generated with FLUX",
    )


def _smart_split_script(text: str, target_min: int = 4, target_max: int = 9, max_hard: int = 13) -> list[str]:
    """Split a script into CLAUSE-RESPECTING chunks for scene captions.

    Breaks at, in priority order:
      1. Sentence boundaries (`.`, `!`, `?`, `:`).
      2. Inside long sentences: commas, semicolons, dashes, and conjunction words
         like "and", "with", "as well as", "but", "or", "while".
      3. Hard cap at `max_hard` words only as a last resort.

    Critical guarantees:
      - Never produces a chunk shorter than `target_min` words *unless* it is
        the natural end of a sentence.
      - Folds short orphan tails (< target_min words) into the previous chunk
        so a sentence never ends with a 1-3 word leftover scene.
      - Verbatim — never paraphrases, only re-segments.
    """
    import re as _re

    BREAK_RX = _re.compile(
        r"(?:"
        r",\s+|;\s+|"                                                    # commas, semicolons
        r"\s+—\s+|\s+--\s+|\s+-\s+|"                                     # em-dash / en-dash / hyphen-with-space
        r"\s+(?:and|with|as well as|but|or|while|where|when|because)\s+" # conjunctions
        r")",
        _re.IGNORECASE,
    )
    SENTENCE_RX = _re.compile(r"(?<=[.!?:])\s+")

    def _wc(s: str) -> int:
        return len(s.split())

    def _split_long_sentence(sent: str) -> list[str]:
        """Within one long sentence, walk break points greedily."""
        # Find all candidate break positions
        breaks: list[int] = [m.start() for m in BREAK_RX.finditer(sent)]
        breaks.append(len(sent))

        out: list[str] = []
        last = 0
        for pos in breaks:
            window = sent[last:pos].strip(" ,;—-")
            if not window:
                continue
            wc = _wc(window)
            # Emit when window reaches the target band, OR when we're about to exceed the hard cap
            # (tentative_next is the next candidate window — if it would push us past max_hard, emit now)
            next_idx = breaks.index(pos) + 1
            next_pos = breaks[next_idx] if next_idx < len(breaks) else None
            wc_if_extended = _wc(sent[last:next_pos].strip(" ,;—-")) if next_pos is not None else wc

            if wc >= target_min and (wc >= target_max or wc_if_extended > max_hard or next_pos is None):
                out.append(window)
                last = pos
            elif wc >= max_hard:
                # Forced cut even though it might be awkward
                out.append(window)
                last = pos
            # else: keep accumulating

        tail = sent[last:].strip(" ,;—-")
        if tail:
            tw = _wc(tail)
            if tw < target_min and out:
                # Fold short tail into previous chunk so no orphan ending
                out[-1] = (out[-1] + " " + tail).strip()
            else:
                out.append(tail)
        return out or [sent]

    text = (text or "").strip()
    if not text:
        return []

    sentences = [s.strip() for s in SENTENCE_RX.split(text) if s.strip()]
    chunks: list[str] = []
    for sent in sentences:
        if _wc(sent) <= target_max:
            chunks.append(sent)
        else:
            chunks.extend(_split_long_sentence(sent))

    # Final pass: fold any sub-target orphan into its neighbour (not just sentence tails)
    cleaned: list[str] = []
    for c in chunks:
        if cleaned and _wc(c) < target_min:
            cleaned[-1] = (cleaned[-1] + " " + c).strip()
        else:
            cleaned.append(c)
    return cleaned


def _build_verbatim_storyboard(brief: str, library: list[dict]) -> list[dict]:
    """Build a storyboard using the brief text VERBATIM — no model rewriting.
    For legal/regulated copy. Each scene's `caption` is also stored as `_speak_text`
    so the renderer can generate per-scene TTS that matches scene timing exactly.
    """
    text = (brief or "").strip()
    if not text:
        raise RuntimeError("use_brief_verbatim=True requires a non-empty brief")
    if not library:
        raise RuntimeError("use_brief_verbatim=True requires at least one library image (used as backdrop for each line of the script)")

    chunks = _smart_split_script(text)
    if not chunks:
        chunks = [text]

    # Hero = first chunk, CTA = last chunk, rest = broll
    hero = chunks[0]
    cta = chunks[-1] if len(chunks) > 1 else "Book a free consultation"
    body = chunks[1:-1] if len(chunks) > 2 else (chunks[1:] if len(chunks) > 1 else [])

    # Rotate composition + motion + text-treatment so consecutive broll scenes
    # never share the same visual treatment — same anti-repeat rule the
    # creative-mode Director follows.
    compositions = ["letterbox", "split", "lowerthird", "fullbleed"]
    motions = ["kenburns-zoom-in", "pan-right", "kenburns-zoom-out", "parallax-tilt", "pan-left", "dolly-in"]
    treatments = ["blur-stagger", "slide-up", "mask-reveal", "scale-bounce", "typewriter"]

    scenes: list[dict] = [{
        "type": "hero",
        "headline": hero,
        "_speak_text": hero,    # render synthesises audio matching this exactly
    }]
    for i, c in enumerate(body):
        img = library[i % len(library)] if library else None
        scenes.append({
            "type": "broll",
            "image_filename": img["filename"] if img else "",
            "caption": c,
            "scene_label": "",
            "composition": compositions[i % len(compositions)],
            "motion": motions[i % len(motions)],
            "text_treatment": treatments[i % len(treatments)],
            "_speak_text": c,
        })
    scenes.append({
        "type": "cta",
        "cta": cta,
        "_speak_text": cta,
    })
    return scenes


async def _resolve_music_path(music_filename: Optional[str]) -> Optional[Path]:
    """Resolve a user-supplied music filename (display name or stored UUID name)
    to an on-disk path inside ad_assets. Returns None if not found or not provided.
    """
    if not music_filename:
        return None
    from app.routers.assets import ASSETS_DIR as _ASSETS
    from app.database import get_db as _get_db
    # Try the supplied name as-is first
    direct = _ASSETS / music_filename
    if direct.is_file():
        return direct
    # Else look up the stored name via the DB
    db = await _get_db()
    try:
        cur = await db.execute(
            "SELECT url FROM ad_assets WHERE filename = ? AND type = 'audio' ORDER BY created_at DESC LIMIT 1",
            (music_filename,),
        )
        row = await cur.fetchone()
        if not row: return None
        stored = (row["url"] or "").rsplit("/", 1)[-1]
        if not stored: return None
        candidate = _ASSETS / stored
        return candidate if candidate.is_file() else None
    finally:
        await db.close()


class GenerateRequest(BaseModel):
    script: str
    voice_id: str | None = None
    avatar_id: str | None = None
    width: int = 1280
    height: int = 720
    campaign_id: str | None = None
    account_id: str | None = None
    character_type: str = "avatar"  # "avatar" or "talking_photo" (Avatar Snap)


class SceneGenerateRequest(BaseModel):
    brief: str = ""                         # one-line user intent — may be empty
    url: str | None = None                  # optional landing-page / article URL
    campaign_id: str | None = None
    account_id: str | None = None


class StoryboardReelHTTPRequest(BaseModel):
    brief: str = ""
    url: str | None = None                  # optional landing page for context
    target_seconds: int = 60                # 30 / 60 / 90
    target_scenes: int | None = None        # override the recommended count (None = auto: target_seconds/4.5)
    image_filenames: list[str] = []         # selected library image filenames (just the name, no path)
    voiceover_script: str = ""
    voice_id: str | None = None
    music_filename: str | None = None
    quality: str = "draft"
    parallel_workers: int = 2
    # When True, skip Director rewriting — use the brief verbatim, splitting it
    # mechanically into scene captions. For legal/regulated content where the
    # exact wording cannot be paraphrased.
    use_brief_verbatim: bool = False
    campaign_id: str | None = None
    account_id: str | None = None


class PremiumReelHTTPRequest(BaseModel):
    headline: str
    subhead: str = ""
    stat_value: str = ""
    stat_label: str = ""
    cta: str = "Book a free consultation"
    voiceover_script: str = ""
    voice_id: str | None = None
    music_filename: str | None = None     # royalty-free music bed (looked up in ad_assets library)
    quality: str = "draft"           # draft | standard | high
    campaign_id: str | None = None
    account_id: str | None = None


class BrandReelHTTPRequest(BaseModel):
    headline: str
    subhead: str = ""
    stat_value: str = ""
    stat_label: str = ""
    cta: str = "Book a free consultation"
    voiceover_script: str = ""
    b_roll_url: str | None = None
    voice_id: str | None = None
    width: int = 1920
    height: int = 1080
    duration_s: int = 15
    campaign_id: str | None = None
    account_id: str | None = None


class ScriptGenerateRequest(BaseModel):
    brief: str
    length_seconds: int = 15          # 6, 15, 30, 60
    variants: int = 2                 # 1-4
    campaign_id: str | None = None
    account_id: str | None = None
    model: str = "sonnet"


@router.post("/generate")
async def generate(body: GenerateRequest):
    """Run the ElevenLabs → HeyGen pipeline and stream progress as SSE.

    On successful render, writes a row to ad_assets so the Studio library
    picks up the new video without a second call.
    """
    if not body.script or not body.script.strip():
        raise HTTPException(status_code=400, detail="script is required")

    req = VideoRequest(
        script=body.script.strip(),
        voice_id=body.voice_id,
        avatar_id=body.avatar_id,
        width=body.width,
        height=body.height,
        character_type=body.character_type,
    )

    async def event_stream():
        from app.routers.assets import record_generated_video

        async for event in generate_video(req):
            if event.get("type") == "done":
                # Mirror the rendered file into the asset library
                try:
                    vid = event.get("video_id")
                    url = event.get("public_url")
                    filename = url.rsplit("/", 1)[-1] if url else f"{vid}.mp4"
                    local_path = ASSETS_DIR / filename
                    size_bytes = local_path.stat().st_size if local_path.is_file() else None
                    await record_generated_video(
                        video_id=vid,
                        filename=filename,
                        url=url,
                        script=body.script.strip(),
                        account_id=body.account_id,
                        campaign_id=body.campaign_id,
                        voice_id=body.voice_id,
                        avatar_id=body.avatar_id,
                        width=body.width,
                        height=body.height,
                        duration=event.get("duration"),
                        thumbnail_url=event.get("thumbnail_url"),
                        size_bytes=size_bytes,
                    )
                except Exception:
                    logger.exception("Failed to record generated video in ad_assets")
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Avatar Snap: upload a photo, get a HeyGen talking_photo_id back ──


@router.post("/talking-photo")
async def upload_talking_photo(file: UploadFile = File(...)):
    """Upload a face photo → HeyGen talking_photo. Returns the talking_photo_id
    the frontend should send back as `avatar_id` with `character_type=talking_photo`.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(status_code=400, detail=f"unsupported image extension {ext}")

    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="photo too large (>12MB)")

    content_type = file.content_type or ("image/png" if ext == ".png" else "image/jpeg")
    try:
        tp_id = await heygen_create_talking_photo(raw, content_type=content_type)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"talking_photo_id": tp_id}


# ── Brand Reel: scene auto-generator ────────────────────────────────


@router.post("/brand-reel/generate-scenes")
async def brand_reel_generate_scenes(body: SceneGenerateRequest) -> dict:
    """One-shot scene autofill — returns {headline, subhead, stat_value, stat_label, cta, voiceover_script}.

    Uses Mercan brand rules + (optional) campaign memory to write copy that
    respects pinned facts, no-third-party-brand-names, no-eligibility-language,
    HNW investor audience.
    """
    # Resolve campaign_name from cached conversations if id supplied — keeps the
    # autofill snappy without a Google Ads API roundtrip.
    campaign_name: str | None = None
    if body.campaign_id:
        from app.database import get_db
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT campaign_name FROM conversations WHERE campaign_id = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (body.campaign_id,),
            )
            row = await cur.fetchone()
            if row:
                campaign_name = row["campaign_name"]
        finally:
            await db.close()

    try:
        scenes = await generate_scenes(
            body.brief or "",
            account_id=body.account_id,
            campaign_id=body.campaign_id,
            campaign_name=campaign_name,
            source_url=(body.url or None),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return scenes


# ── Brand Story: storyboard + N-scene Premium Reel render ─────────


class StoryboardPlanResponse(BaseModel):
    scenes: list[dict]                   # [{"type": "hero"|"broll"|"stat"|"cta", ...}]
    image_lookup: dict[str, str] = {}    # stored_filename -> /api/assets/file/<stored>
    target_seconds: int
    estimated_render_seconds: int        # rough ETA for the user


@router.post("/premium-reel/storyboard-plan", response_model=StoryboardPlanResponse)
async def premium_reel_storyboard_plan(body: StoryboardReelHTTPRequest):
    """Phase 1 only — generate the storyboard JSON and return it for preview.
    Frontend shows the user the scene list with image thumbnails, then calls
    /storyboard-render with the (possibly edited) scenes when they're happy.
    """
    if not body.image_filenames and not body.brief.strip() and not body.url:
        raise HTTPException(status_code=400, detail="provide at least one of: brief, url, or images")

    from PIL import Image as _PILImage
    from app.routers.assets import ASSETS_DIR as _ASSETS
    from app.database import get_db as _get_db

    # Resolve display→stored names (same logic as the all-in-one endpoint)
    name_map: dict[str, str] = {}
    if body.image_filenames:
        _db = await _get_db()
        try:
            placeholders = ",".join("?" * len(body.image_filenames))
            cur = await _db.execute(
                f"SELECT filename, url FROM ad_assets WHERE filename IN ({placeholders}) AND type = 'image'",
                tuple(body.image_filenames),
            )
            for row in await cur.fetchall():
                stored = (row["url"] or "").rsplit("/", 1)[-1]
                if stored: name_map[row["filename"]] = stored
        finally:
            await _db.close()

    library: list[dict] = []
    image_lookup: dict[str, str] = {}
    for fn in body.image_filenames:
        candidates = [fn] + ([name_map[fn]] if fn in name_map and name_map[fn] != fn else [])
        path = next((p for p in (_ASSETS / c for c in candidates) if p.is_file()), None)
        if path is None:
            logger.warning("storyboard-plan: image not found in library: %s", fn)
            continue
        try:
            with _PILImage.open(path) as im:
                w, h = im.size
        except Exception:
            w = h = None
        library.append({
            "filename": path.name, "display_name": fn, "width": w, "height": h,
        })
        image_lookup[path.name] = f"/api/assets/file/{path.name}"

    if not library and body.image_filenames:
        raise HTTPException(status_code=400, detail="none of the supplied image filenames were found in the local library")

    # Resolve campaign_name for brand-context loading
    campaign_name: str | None = None
    if body.campaign_id:
        from app.database import get_db
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT campaign_name FROM conversations WHERE campaign_id = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (body.campaign_id,),
            )
            row = await cur.fetchone()
            if row: campaign_name = row["campaign_name"]
        finally:
            await db.close()

    try:
        if body.use_brief_verbatim:
            scenes = _build_verbatim_storyboard(body.brief, library)
        else:
            scenes = await generate_storyboard(
                brief=body.brief,
                target_seconds=body.target_seconds,
                target_scenes=body.target_scenes,
                library_images=library,
                account_id=body.account_id,
                campaign_id=body.campaign_id,
                campaign_name=campaign_name,
                source_url=body.url,
            )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"storyboard generator failed: {e}")

    # ─── Auto-fill missing broll images via stock search ───
    # When the Director writes `image_search_query` instead of `image_filename`,
    # try to fetch a free stock photo from Unsplash/Pexels and adopt it into the
    # library. Each scene's resolution runs in parallel.
    from app.services.stock_images import (
        search_stock as _search_stock,
        download_image as _download_image,
        save_remote_to_assets as _save_remote,
        _ext_from_url as _ext_from_url,
    )

    async def _resolve_scene_image(idx: int, scene: dict) -> None:
        if scene.get("type") != "broll": return
        if scene.get("image_filename"): return
        q = (scene.get("image_search_query") or "").strip()
        if not q: return
        matches = await _search_stock(q, count=3)
        if not matches: return
        chosen = matches[0]
        img = await _download_image(chosen.image_url)
        if not img: return
        attribution = ""
        if chosen.photographer:
            attribution = f"Photo by {chosen.photographer}"
            if chosen.photographer_url:
                attribution += f" ({chosen.photographer_url})"
        try:
            asset = await _save_remote(
                image_bytes=img,
                ext=_ext_from_url(chosen.image_url),
                account_id=body.account_id,
                campaign_id=body.campaign_id,
                description=chosen.description or q,
                source=f"stock-{chosen.provider}",
                width=chosen.width,
                height=chosen.height,
                attribution=attribution,
            )
            scene["image_filename"] = asset["filename"]
            scene["_stock_attribution"] = attribution
            image_lookup[asset["filename"]] = asset["url"]
        except Exception:
            logger.exception("failed to adopt stock image for scene %d", idx)

    if any(s.get("type") == "broll" and not s.get("image_filename") and s.get("image_search_query") for s in scenes):
        await asyncio.gather(*[_resolve_scene_image(i, s) for i, s in enumerate(scenes)])
        # NOTE: we used to drop broll scenes that ended up imageless after stock
        # search failed. That silently shrank 13-scene storyboards down to 6 when
        # the user only had Pexels keyed (or Director queries were too specific).
        # Now we KEEP them and surface them in the preview with a "needs image"
        # placeholder so the user can click to pick from Library / Stock / AI.
        # The renderer skips imageless broll with a scene-skipped event anyway.
        pass

    # Estimate ETA: ~75s/scene at 2-parallel, plus 10s stitch, plus 10s VO if any
    n = max(1, len(scenes))
    eta = int((n / 2) * 75) + 10 + (15 if body.voiceover_script.strip() else 0)

    return StoryboardPlanResponse(
        scenes=scenes,
        image_lookup=image_lookup,
        target_seconds=body.target_seconds,
        estimated_render_seconds=eta,
    )


class StoryboardRenderHTTPRequest(BaseModel):
    """Phase 2: render an approved storyboard (possibly edited by the user)."""
    scenes: list[dict]                  # output from /storyboard-plan
    voiceover_script: str = ""
    voice_id: str | None = None
    music_filename: str | None = None
    quality: str = "draft"
    parallel_workers: int = 2
    brief: str = ""                     # optional, just for ad_assets.script summary
    # When True, generate per-scene TTS (using each scene's `_speak_text` or
    # caption/headline/cta) and stretch each scene's duration to match its
    # audio. Eliminates the cut-mid-sentence problem when using verbatim mode.
    sync_audio_to_scenes: bool = False
    campaign_id: str | None = None
    account_id: str | None = None


@router.post("/premium-reel/storyboard-render")
async def premium_reel_storyboard_render(body: StoryboardRenderHTTPRequest):
    """Phase 2 — accept an approved storyboard and stream the SSE render."""
    if not body.scenes:
        raise HTTPException(status_code=400, detail="scenes is required")

    async def event_stream():
        from app.routers.assets import record_generated_video
        music_path = await _resolve_music_path(body.music_filename)
        req = StoryboardReelRequest(
            scenes=body.scenes,
            voiceover_script=body.voiceover_script,
            voice_id=body.voice_id,
            music_path=music_path,
            quality=body.quality,
            parallel_workers=max(1, min(3, body.parallel_workers)),
            sync_audio_to_scenes=body.sync_audio_to_scenes,
        )
        async for event in generate_storyboard_reel(req):
            if event.get("type") == "done":
                try:
                    vid = event.get("video_id")
                    url = event.get("public_url")
                    filename = url.rsplit("/", 1)[-1] if url else f"{vid}.mp4"
                    summary = body.brief.strip() or f"Brand Story Reel — {len(body.scenes)} scenes"
                    await record_generated_video(
                        video_id=vid, filename=filename, url=url, script=summary,
                        account_id=body.account_id, campaign_id=body.campaign_id,
                        voice_id=body.voice_id, avatar_id="brand-story",
                        width=1920, height=1080, duration=event.get("duration"),
                        thumbnail_url=None, size_bytes=event.get("size_bytes"),
                    )
                except Exception:
                    logger.exception("Failed to record brand story reel in ad_assets")
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/premium-reel/storyboard")
async def premium_reel_storyboard(body: StoryboardReelHTTPRequest):
    """End-to-end: Director generates an N-scene storyboard from brief + URL +
    selected images, then renders each scene with Hyperframes and stitches.

    For a 60-second Mercan brand video with 8 user-selected hotel photos, this
    typically takes 2-4 minutes and produces an ~11-scene reel.
    """
    if not body.image_filenames and not body.brief.strip() and not body.url:
        raise HTTPException(status_code=400, detail="provide at least one of: brief, url, or images")

    # Build the library_images list with file dimensions (model uses these to
    # decide which image fits which scene).
    #
    # Frontend sends the *original* upload filename (e.g. "hotel-evora.jpg"),
    # but on disk the file is stored under its UUID (e.g. "abcd1234.jpg").
    # We keep the original as `display_name` (Director uses it to infer scene
    # fit) and resolve to the stored filename for downstream rendering.
    from PIL import Image as _PILImage
    from app.routers.assets import ASSETS_DIR as _ASSETS
    from app.database import get_db as _get_db

    # Pre-resolve original→stored via DB lookup
    name_map: dict[str, str] = {}  # display_name -> stored_name
    if body.image_filenames:
        _db = await _get_db()
        try:
            placeholders = ",".join("?" * len(body.image_filenames))
            cur = await _db.execute(
                f"SELECT filename, url FROM ad_assets WHERE filename IN ({placeholders}) AND type = 'image'",
                tuple(body.image_filenames),
            )
            for row in await cur.fetchall():
                # url is "/api/assets/file/<stored>"; extract the last segment
                stored = (row["url"] or "").rsplit("/", 1)[-1]
                if stored:
                    name_map[row["filename"]] = stored
        finally:
            await _db.close()

    library: list[dict] = []
    for fn in body.image_filenames:
        # Try the supplied name first (handles case where caller already passed stored name),
        # then fall back to the DB-resolved stored name.
        candidates = [fn] + ([name_map[fn]] if fn in name_map and name_map[fn] != fn else [])
        path = next((p for p in (_ASSETS / c for c in candidates) if p.is_file()), None)
        if path is None:
            logger.warning("storyboard request: image not found in library: %s", fn)
            continue
        try:
            with _PILImage.open(path) as im:
                w, h = im.size
        except Exception:
            w = h = None
        library.append({
            "filename": path.name,         # stored name — used by renderer to find file on disk
            "display_name": fn,            # original name — Director sees this for scene-fit inference
            "width": w, "height": h,
        })

    if not library and body.image_filenames:
        raise HTTPException(status_code=400, detail="none of the supplied image filenames were found in the local library")

    # Resolve campaign_name (cheap DB lookup so brand context loads correctly)
    campaign_name: str | None = None
    if body.campaign_id:
        from app.database import get_db
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT campaign_name FROM conversations WHERE campaign_id = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (body.campaign_id,),
            )
            row = await cur.fetchone()
            if row: campaign_name = row["campaign_name"]
        finally:
            await db.close()

    async def event_stream():
        from app.routers.assets import record_generated_video

        # Phase 1: storyboard generation (one Claude call)
        yield f"data: {json.dumps({'type':'status','stage':'storyboard','message':f'Director writing the {body.target_seconds}s storyboard…'})}\n\n"
        try:
            scenes = await generate_storyboard(
                brief=body.brief,
                target_seconds=body.target_seconds,
                library_images=library,
                account_id=body.account_id,
                campaign_id=body.campaign_id,
                campaign_name=campaign_name,
                source_url=body.url,
            )
        except RuntimeError as e:
            yield f"data: {json.dumps({'type':'error','stage':'storyboard','message':str(e)})}\n\n"
            return

        yield f"data: {json.dumps({'type':'status','stage':'storyboard-done','message':f'Storyboard ready — {len(scenes)} scenes','scenes':scenes})}\n\n"

        # Phase 2: render the storyboard
        req = StoryboardReelRequest(
            scenes=scenes,
            voiceover_script=body.voiceover_script,
            voice_id=body.voice_id,
            quality=body.quality,
            parallel_workers=max(1, min(3, body.parallel_workers)),
        )

        async for event in generate_storyboard_reel(req):
            if event.get("type") == "done":
                try:
                    vid = event.get("video_id")
                    url = event.get("public_url")
                    filename = url.rsplit("/", 1)[-1] if url else f"{vid}.mp4"
                    summary = body.brief.strip() or f"Brand Story Reel — {len(scenes)} scenes"
                    await record_generated_video(
                        video_id=vid,
                        filename=filename,
                        url=url,
                        script=summary,
                        account_id=body.account_id,
                        campaign_id=body.campaign_id,
                        voice_id=body.voice_id,
                        avatar_id="brand-story",
                        width=1920, height=1080,
                        duration=event.get("duration"),
                        thumbnail_url=None,
                        size_bytes=event.get("size_bytes"),
                    )
                except Exception:
                    logger.exception("Failed to record brand story reel in ad_assets")
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Premium Reel: Hyperframes (HTML+GSAP+Chrome) — kinetic typography ──


@router.post("/premium-reel")
async def premium_reel(body: PremiumReelHTTPRequest):
    """Render a Premium Reel with per-letter / per-element kinetic animations.
    Slower than Brand Reel (~60-90s for 3 scenes) but visually a different class.
    Same SSE event shape as /brand-reel and /generate."""
    if not body.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")

    music_path = await _resolve_music_path(body.music_filename)
    req = PremiumReelRequest(
        headline=body.headline.strip(),
        subhead=body.subhead.strip(),
        stat_value=body.stat_value.strip(),
        stat_label=body.stat_label.strip(),
        cta=body.cta.strip(),
        voiceover_script=body.voiceover_script.strip(),
        voice_id=body.voice_id,
        music_path=music_path,
        quality=body.quality,
    )

    async def event_stream():
        from app.routers.assets import record_generated_video

        async for event in generate_premium_reel(req):
            if event.get("type") == "done":
                try:
                    vid = event.get("video_id")
                    url = event.get("public_url")
                    filename = url.rsplit("/", 1)[-1] if url else f"{vid}.mp4"
                    script = " — ".join(p for p in [body.headline.strip(), body.subhead.strip(), body.cta.strip()] if p)
                    await record_generated_video(
                        video_id=vid,
                        filename=filename,
                        url=url,
                        script=script,
                        account_id=body.account_id,
                        campaign_id=body.campaign_id,
                        voice_id=body.voice_id,
                        avatar_id="premium-reel",  # synthetic, distinguishes from brand-reel + heygen
                        width=1920,
                        height=1080,
                        duration=event.get("duration"),
                        thumbnail_url=None,
                        size_bytes=event.get("size_bytes"),
                    )
                except Exception:
                    logger.exception("Failed to record premium reel in ad_assets")
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Brand Reel: local Pillow + ffmpeg, no HeyGen ────────────────────


@router.post("/brand-reel")
async def brand_reel(body: BrandReelHTTPRequest):
    """Render a Brand Reel locally and stream progress as SSE.

    On success, the rendered MP4 is registered in ad_assets so it shows up in
    the Studio library next to HeyGen renders.
    """
    if not body.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")

    req = BrandReelRequest(
        headline=body.headline.strip(),
        subhead=body.subhead.strip(),
        stat_value=body.stat_value.strip(),
        stat_label=body.stat_label.strip(),
        cta=body.cta.strip(),
        voiceover_script=body.voiceover_script.strip(),
        b_roll_url=body.b_roll_url,
        voice_id=body.voice_id,
        width=body.width,
        height=body.height,
        duration_s=body.duration_s,
    )

    async def event_stream():
        from app.routers.assets import record_generated_video

        async for event in generate_brand_reel(req):
            if event.get("type") == "done":
                try:
                    vid = event.get("video_id")
                    url = event.get("public_url")
                    filename = url.rsplit("/", 1)[-1] if url else f"{vid}.mp4"
                    # Build a script-ish summary for the library card
                    script = " — ".join(p for p in [body.headline.strip(), body.subhead.strip(), body.cta.strip()] if p)
                    await record_generated_video(
                        video_id=vid,
                        filename=filename,
                        url=url,
                        script=script,
                        account_id=body.account_id,
                        campaign_id=body.campaign_id,
                        voice_id=body.voice_id,
                        avatar_id="brand-reel",  # synthetic — distinguishes from HeyGen renders
                        width=body.width,
                        height=body.height,
                        duration=event.get("duration"),
                        thumbnail_url=None,
                        size_bytes=event.get("size_bytes"),
                    )
                except Exception:
                    logger.exception("Failed to record brand reel in ad_assets")
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/script-generate")
async def script_generate(body: ScriptGenerateRequest):
    """Generate video ad script(s) using the script_generator role.

    Streams SSE events so the UI can show live progress. Uses an ephemeral
    conversation so campaign memory (role notes, pinned facts, decisions) flows
    into the prompt without polluting chat history.
    """
    import uuid as _uuid
    from app.database import get_db
    from app.services.agent import stream_agent_response

    if not body.brief or not body.brief.strip():
        raise HTTPException(status_code=400, detail="brief is required")
    if body.length_seconds not in (6, 15, 30, 60):
        raise HTTPException(status_code=400, detail="length_seconds must be 6, 15, 30, or 60")
    variants = max(1, min(4, body.variants))

    user_message = (
        f"Write {variants} variant(s) of a {body.length_seconds}-second video ad script.\n\n"
        f"Brief: {body.brief.strip()}\n\n"
        f"Use the OUTPUT FORMAT from your system prompt exactly "
        f"(LENGTH / HOOK / SCRIPT / CTA / B-ROLL NOTES)."
    )

    # Resolve campaign_name so the existing guideline loader can pull brand
    # rules (no-brand-names, no-affordability, HNW framing, etc).
    campaign_name = None
    if body.campaign_id:
        db = await get_db()
        try:
            # campaigns aren't in the local DB, so just ask for the running
            # conversations' cached name — otherwise agent resolves via the
            # ads API cache layer.
            cur = await db.execute(
                "SELECT campaign_name FROM conversations WHERE campaign_id = ? ORDER BY updated_at DESC LIMIT 1",
                (body.campaign_id,),
            )
            row = await cur.fetchone()
            if row:
                campaign_name = row["campaign_name"]
        finally:
            await db.close()

    # Ephemeral conversation — exists only for this one script gen, cleaned up after.
    conv_id = str(_uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (id, account_id, campaign_id, campaign_name, title) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, body.account_id, body.campaign_id, campaign_name, "Studio script generation"),
        )
        await db.commit()
    finally:
        await db.close()

    async def event_stream():
        try:
            async for event in stream_agent_response(
                user_message=user_message,
                account_id=body.account_id,
                campaign_id=body.campaign_id,
                campaign_name=campaign_name,
                conversation_id=conv_id,
                model=body.model,
                active_role="script_generator",
            ):
                # Pass through text + status; drop tool_call events (scripts don't use tools)
                et = event.get("type")
                if et in ("text", "text_delta"):  # relabel token-level delta → text for the v1 client (story 1.4)
                    yield f"data: {json.dumps({'type': 'text', 'content': event.get('content', '')})}\n\n"
                elif et == "done":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                elif et == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': event.get('message', 'unknown error')})}\n\n"
        finally:
            # Clean up the ephemeral conversation + its messages
            try:
                db2 = await get_db()
                try:
                    await db2.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
                    await db2.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
                    await db2.commit()
                finally:
                    await db2.close()
            except Exception:
                logger.exception("Failed to clean up ephemeral script-gen conversation %s", conv_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/assets/{filename}")
async def serve_asset(filename: str):
    """Serve a rendered MP4 from ASSETS_DIR. Guards against path traversal."""
    # Only allow simple .mp4 filenames — no subpaths, no tricks
    if "/" in filename or ".." in filename or not filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="invalid filename")
    path: Path = ASSETS_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)


# ── Optional: expose HeyGen / ElevenLabs catalogs so the UI can pick ─


@router.get("/avatars")
async def list_avatars(limit: int = 20):
    """Return a small slice of HeyGen stock avatars for the UI dropdown."""
    import httpx
    from app.config import settings as S

    if not S.HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="HEYGEN_API_KEY not set")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            "https://api.heygen.com/v2/avatars",
            headers={"X-Api-Key": S.HEYGEN_API_KEY},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"HeyGen: {r.status_code}")
        data = (r.json().get("data") or {}).get("avatars") or []
        return [
            {
                "avatar_id": a.get("avatar_id"),
                "name": a.get("avatar_name"),
                "gender": a.get("gender"),
                "preview_image_url": a.get("preview_image_url"),
                "preview_video_url": a.get("preview_video_url"),
            }
            for a in data[:limit]
        ]


@router.get("/voices")
async def list_voices():
    """Return ElevenLabs voices on this account."""
    import httpx
    from app.config import settings as S

    if not S.ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY not set")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": S.ELEVENLABS_API_KEY},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"ElevenLabs: {r.status_code}")
        voices = r.json().get("voices") or []
        return [
            {
                "voice_id": v.get("voice_id"),
                "name": v.get("name"),
                "category": v.get("category"),
                "labels": v.get("labels"),
                "preview_url": v.get("preview_url"),
            }
            for v in voices
        ]
