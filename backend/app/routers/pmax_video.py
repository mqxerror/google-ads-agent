"""PMax wizard video pipeline — agent-scripted slideshow ad from library images.

Two job+poll pairs (single long HTTP requests die behind the dev proxy —
same lesson as /api/pmax/draft-copy):

  POST /api/pmax/video/draft   → script_generator writes a 20-30s storyboard
                                 over the OPERATOR-CHOSEN images (grounded in
                                 the brief + landing page; no Google Ads tools)
  GET  /api/pmax/video/draft/{job_id}

  POST /api/pmax/video/render  → generate_storyboard_reel (Hyperframes) in a
                                 background task; MP4 lands in ad_assets with
                                 account_id set so the Studio library shows it
  GET  /api/pmax/video/render/{job_id}

The rendered asset is then uploaded to YouTube via /api/youtube/upload and the
returned video id auto-fills the wizard's videoIds list.

Two YouTube-metadata helpers round the panel out:

  POST /api/pmax/video/metadata → creative_director drafts 3 title options
                                  (≤95 chars) + a grounded description
                                  (job+poll, same reason as above)
  GET  /api/pmax/video/metadata/{job_id}

  POST /api/pmax/video/frames   → ffmpeg pulls 4 stills (10/35/60/85% of
                                  duration) from a rendered video into
                                  ad_assets so one can be the YT thumbnail
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pmax/video", tags=["pmax-video"])

# In-memory job stores — drafts/renders are ephemeral and single-process.
_draft_jobs: Dict[str, Dict[str, Any]] = {}
_render_jobs: Dict[str, Dict[str, Any]] = {}

# Palettes must mirror premium_reel's broll template switch
_COMPOSITIONS = ["letterbox", "split", "lowerthird", "fullbleed"]
_MOTIONS = ["kenburns-zoom-in", "pan-right", "kenburns-zoom-out", "parallax-tilt", "pan-left", "dolly-in"]
_TREATMENTS = ["blur-stagger", "slide-up", "mask-reveal", "scale-bounce", "typewriter"]
_VALID_TYPES = {"logo", "hero", "broll", "stat", "cta"}
_MAX_SCENES = 8

_LOGO_RX = re.compile(r"(^|[^a-z])logo([^a-z]|$)", re.IGNORECASE)


# ── Draft: script_generator writes the storyboard ───────────────────


class PMaxVideoDraftRequest(BaseModel):
    account_id: str
    brief: str = ""
    business_name: str = ""
    final_url: str = ""
    campaign_name: str = ""
    image_ids: List[str] = Field(default_factory=list)   # ad_assets row ids


async def _resolve_images(image_ids: List[str]) -> tuple[list[dict], dict[str, str]]:
    """ad_assets ids → [{filename(stored), display_name, width, height, is_logo}]
    plus a stored-filename → serving-URL lookup for the preview UI.
    Unknown ids and missing files are skipped (wizard slots may hold Google
    resource names that never lived in the local library)."""
    if not image_ids:
        return [], {}
    from PIL import Image as _PILImage
    from app.database import get_db
    from app.routers.assets import ASSETS_DIR

    db = await get_db()
    try:
        placeholders = ",".join("?" * len(image_ids))
        cur = await db.execute(
            f"SELECT id, filename, url FROM ad_assets WHERE id IN ({placeholders}) AND type = 'image'",
            tuple(image_ids),
        )
        rows = {r["id"]: r for r in await cur.fetchall()}
    finally:
        await db.close()

    library: list[dict] = []
    lookup: dict[str, str] = {}
    for iid in image_ids:                      # preserve operator's order
        row = rows.get(iid)
        if not row:
            continue
        stored = (row["url"] or "").rsplit("/", 1)[-1] or row["filename"]
        path = ASSETS_DIR / stored
        if not path.is_file():
            logger.warning("pmax video draft: file missing for asset %s (%s)", iid, stored)
            continue
        try:
            with _PILImage.open(path) as im:
                w, h = im.size
        except Exception:
            w = h = None
        display = row["filename"]
        library.append({
            "filename": stored,
            "display_name": display,
            "width": w,
            "height": h,
            "is_logo": bool(_LOGO_RX.search(display)),
        })
        lookup[stored] = f"/api/assets/file/{stored}"
    return library, lookup


def _draft_prompt(body: PMaxVideoDraftRequest, library: list[dict]) -> str:
    img_lines = []
    for img in library:
        dims = f"{img.get('width','?')}×{img.get('height','?')}"
        tag = " [LOGO]" if img["is_logo"] else ""
        img_lines.append(f"- `{img['filename']}` — original: `{img['display_name']}` ({dims}){tag}")
    return (
        "Storyboard a 20-30 second slideshow video ad for a Performance Max campaign. "
        "First fetch the landing page to ground every claim — never invent offers, numbers, or program names.\n\n"
        f"Landing page: {body.final_url or '(none — use the brief only)'}\n"
        f"Business name: {body.business_name or '-'}\n"
        f"Campaign name: {body.campaign_name or '-'}\n"
        f"Brief from the operator: {body.brief or '(none — derive from the landing page)'}\n\n"
        "AVAILABLE IMAGES (the operator picked these — use ONLY these, one per broll scene; "
        "copy the backtick-quoted storage id verbatim into image_filename):\n"
        + "\n".join(img_lines)
        + "\n\nSTRUCTURE — 6 to 8 scenes total:\n"
        "1. Open with a `logo` scene IF an image is tagged [LOGO] (set logo_filename to its storage id, "
        "brand_name, short tagline); otherwise open with a `hero` scene (headline 4-7 words).\n"
        "2. 3-5 `broll` scenes — one non-logo image each, never reuse an image. Each broll has: "
        "image_filename, caption (5-10 words, on-screen text), optional scene_label (1-3 word place/tag), "
        "composition (rotate: letterbox | split | lowerthird | fullbleed), "
        "motion (rotate: kenburns-zoom-in | pan-right | kenburns-zoom-out | parallax-tilt | pan-left | dolly-in), "
        "text_treatment (rotate: blur-stagger | slide-up | mask-reveal | scale-bounce | typewriter).\n"
        "3. AT MOST one `stat` scene (stat_value = number alone, stat_label 2-5 words) and ONLY if the "
        "number is verifiable on the landing page or in the brief.\n"
        "4. Close with exactly one `cta` scene (cta 4-8 words, action verb first; set logo_filename to the "
        "[LOGO] storage id if one exists).\n\n"
        "VOICEOVER — every scene MUST include a `speak` field: the spoken line for that scene. "
        "Write for the ear: contractions, short sentences, no abbreviations a TTS engine would "
        "mispronounce (write 'five hundred thousand euros', not '€500K'). Total spoken script across all "
        "scenes: 45-75 words (≈20-30s at natural pace). The captions and the spoken lines should "
        "complement, not duplicate each other word-for-word.\n\n"
        "RULES: no third-party brand names. No invented stats. Respect any pinned campaign facts. "
        "Captions ≤10 words.\n\n"
        "Respond with ONLY this JSON inside <json> tags, no prose outside them:\n"
        "<json>\n"
        '{"scenes": [\n'
        '  {"type": "logo", "logo_filename": "<storage id>", "brand_name": "...", "tagline": "...", "speak": "..."},\n'
        '  {"type": "broll", "image_filename": "<storage id>", "caption": "...", "scene_label": "...", '
        '"composition": "letterbox", "motion": "kenburns-zoom-in", "text_treatment": "blur-stagger", "speak": "..."},\n'
        '  {"type": "stat", "stat_value": "37", "stat_label": "years of experience", "speak": "..."},\n'
        '  {"type": "cta", "cta": "Book a free consultation", "logo_filename": "<storage id or omit>", "speak": "..."}\n'
        "]}\n"
        "</json>"
    )


def _clean_scenes(raw_scenes: list, library: list[dict]) -> list[dict]:
    """Validate + normalise the model's storyboard into scenes that
    generate_storyboard_reel accepts. Round-robins unassigned/unknown broll
    images, fills palette defaults, maps speak→_speak_text, forces cta last."""
    valid = {img["filename"] for img in library}
    non_logo = [img["filename"] for img in library if not img["is_logo"]]
    logo_fns = [img["filename"] for img in library if img["is_logo"]]
    rr = 0  # round-robin pointer for image recovery

    cleaned: list[dict] = []
    used_images: set[str] = set()
    for s in raw_scenes:
        if not isinstance(s, dict):
            continue
        t = (s.get("type") or "").strip().lower()
        if t not in _VALID_TYPES:
            continue
        speak = (s.get("speak") or s.get("_speak_text") or "").strip()
        if t == "hero":
            out = {"type": "hero", "headline": (s.get("headline") or "").strip()}
            if not out["headline"]:
                continue
        elif t == "logo":
            fn = (s.get("logo_filename") or "").strip()
            if fn not in valid:
                fn = logo_fns[0] if logo_fns else ""
            if not fn:
                continue  # no logo image — drop the scene
            out = {
                "type": "logo", "logo_filename": fn,
                "brand_name": (s.get("brand_name") or "").strip(),
                "tagline": (s.get("tagline") or "").strip(),
            }
        elif t == "stat":
            out = {
                "type": "stat",
                "stat_value": str(s.get("stat_value") or "").strip(),
                "stat_label": (s.get("stat_label") or "").strip(),
            }
            if not out["stat_value"]:
                continue
        elif t == "cta":
            fn = (s.get("logo_filename") or "").strip()
            out = {"type": "cta", "cta": (s.get("cta") or "Book a free consultation").strip()}
            if fn in valid:
                out["logo_filename"] = fn
            elif logo_fns:
                out["logo_filename"] = logo_fns[0]
        else:  # broll
            fn = (s.get("image_filename") or "").strip()
            if fn not in valid or fn in used_images:
                # Recover: next unused non-logo image, else next non-logo round-robin
                pool = [f for f in non_logo if f not in used_images] or non_logo
                if not pool:
                    continue
                fn = pool[rr % len(pool)]
                rr += 1
            used_images.add(fn)
            comp = (s.get("composition") or "").strip().lower()
            mot = (s.get("motion") or "").strip().lower()
            txt = (s.get("text_treatment") or "").strip().lower()
            n_broll = sum(1 for c in cleaned if c["type"] == "broll")
            out = {
                "type": "broll",
                "image_filename": fn,
                "caption": (s.get("caption") or "").strip(),
                "scene_label": (s.get("scene_label") or "").strip(),
                "composition": comp if comp in _COMPOSITIONS else _COMPOSITIONS[n_broll % len(_COMPOSITIONS)],
                "motion": mot if mot in _MOTIONS else _MOTIONS[n_broll % len(_MOTIONS)],
                "text_treatment": txt if txt in _TREATMENTS else _TREATMENTS[n_broll % len(_TREATMENTS)],
            }
        # _speak_text drives per-scene TTS + scene stretching in the renderer.
        # Fall back to the visible copy so a missing `speak` never mutes a scene.
        out["_speak_text"] = speak or (
            out.get("caption") or out.get("headline") or out.get("cta")
            or f"{out.get('stat_value','')} {out.get('stat_label','')}".strip()
            or ""
        )
        cleaned.append(out)

    cleaned = cleaned[:_MAX_SCENES]
    if not cleaned:
        return cleaned
    # Exactly one cta, always last
    ctas = [c for c in cleaned if c["type"] == "cta"]
    cleaned = [c for c in cleaned if c["type"] != "cta"]
    cta = ctas[0] if ctas else {
        "type": "cta", "cta": "Book a free consultation",
        "_speak_text": "Book a free consultation today.",
        **({"logo_filename": logo_fns[0]} if logo_fns else {}),
    }
    cleaned.append(cta)
    return cleaned


async def _run_draft_job(job_id: str, body: PMaxVideoDraftRequest) -> None:
    try:
        library, lookup = await _resolve_images(body.image_ids)
        if not library:
            _draft_jobs[job_id] = {
                "status": "error",
                "message": "none of the selected images exist in the local library — pick library/uploaded images",
            }
            return

        from app.services.agent import stream_agent_response

        parts: list[str] = []
        async for ev in stream_agent_response(
            user_message=_draft_prompt(body, library),
            account_id=body.account_id,
            active_role="script_generator",
            tool_allowlist=[],  # no Google Ads tools; built-in web fetch still grounds the landing page
        ):
            if ev.get("type") == "text":
                parts.append(ev.get("content", ""))
        raw = "".join(parts)

        m = re.search(r"<json>(.*?)</json>", raw, re.DOTALL | re.IGNORECASE)
        bodytxt = m.group(1).strip() if m else raw.strip()
        if bodytxt.startswith("```"):
            bodytxt = re.sub(r"^```\w*\s*|\s*```$", "", bodytxt, flags=re.MULTILINE).strip()
        if not bodytxt.startswith("{"):
            m2 = re.search(r"\{.*\}", bodytxt, re.DOTALL)
            if m2:
                bodytxt = m2.group(0)
        try:
            data = json.loads(bodytxt)
        except Exception:
            _draft_jobs[job_id] = {"status": "error", "message": "Script Generator returned no parseable JSON — try again."}
            return

        scenes = _clean_scenes(data.get("scenes") or [], library)
        if len(scenes) < 3:
            _draft_jobs[job_id] = {"status": "error", "message": f"Draft produced only {len(scenes)} usable scenes — try again."}
            return

        _draft_jobs[job_id] = {
            "status": "done",
            "scenes": scenes,
            "image_lookup": lookup,
        }
    except Exception as e:
        logger.exception("pmax video draft job %s failed", job_id)
        _draft_jobs[job_id] = {"status": "error", "message": str(e)[:300]}


@router.post("/draft")
async def start_video_draft(body: PMaxVideoDraftRequest) -> Dict[str, str]:
    """Start a storyboard draft job; poll GET /api/pmax/video/draft/{id}."""
    if not body.image_ids:
        raise HTTPException(status_code=400, detail="image_ids is required (3-8 library images)")
    job_id = str(uuid.uuid4())
    _draft_jobs[job_id] = {"status": "running"}
    asyncio.create_task(_run_draft_job(job_id, body))
    return {"job_id": job_id, "status": "running"}


@router.get("/draft/{job_id}")
async def get_video_draft(job_id: str) -> Dict[str, Any]:
    job = _draft_jobs.get(job_id)
    if not job:
        return {"status": "error", "message": "unknown draft job (server restarted?) — start a new draft"}
    return job


# ── Render: storyboard → MP4 in ad_assets ────────────────────────────


class PMaxVideoRenderRequest(BaseModel):
    account_id: str
    scenes: List[dict]
    voice_id: Optional[str] = None
    music_filename: Optional[str] = None
    quality: str = "draft"
    sync_audio_to_scenes: bool = True     # per-scene TTS, scenes stretch to audio
    campaign_id: Optional[str] = None
    brief: str = ""                       # library-card summary only


async def _run_render_job(job_id: str, body: PMaxVideoRenderRequest) -> None:
    from app.routers.assets import record_generated_video
    from app.routers.video import _resolve_music_path
    from app.services.premium_reel import StoryboardReelRequest, generate_storyboard_reel

    try:
        music_path = await _resolve_music_path(body.music_filename)
        req = StoryboardReelRequest(
            scenes=body.scenes,
            voice_id=body.voice_id,
            music_path=music_path,
            quality=body.quality,
            parallel_workers=2,
            sync_audio_to_scenes=body.sync_audio_to_scenes,
        )
        async for event in generate_storyboard_reel(req):
            et = event.get("type")
            if et == "status":
                _render_jobs[job_id] = {
                    "status": "running",
                    "stage": event.get("stage", ""),
                    "message": event.get("message", ""),
                }
            elif et == "error":
                _render_jobs[job_id] = {"status": "error", "message": event.get("message", "render failed")}
                return
            elif et == "done":
                vid = event.get("video_id")
                url = event.get("public_url")
                filename = url.rsplit("/", 1)[-1] if url else f"{vid}.mp4"
                summary = body.brief.strip() or f"PMax slideshow ad — {len(body.scenes)} scenes"
                try:
                    # account_id REQUIRED on the row — without it the Studio
                    # library (account-filtered) never shows the render.
                    await record_generated_video(
                        video_id=vid, filename=filename, url=url, script=summary,
                        account_id=body.account_id, campaign_id=body.campaign_id,
                        voice_id=body.voice_id, avatar_id="pmax-video",
                        width=1920, height=1080, duration=event.get("duration"),
                        thumbnail_url=None, size_bytes=event.get("size_bytes"),
                    )
                except Exception:
                    logger.exception("failed to record pmax video in ad_assets")
                _render_jobs[job_id] = {
                    "status": "done",
                    "asset_id": vid,
                    "url": url,
                    "duration": event.get("duration"),
                    "scene_count": event.get("scene_count"),
                }
                return
        # Generator finished without a done/error event — treat as failure
        if _render_jobs.get(job_id, {}).get("status") == "running":
            _render_jobs[job_id] = {"status": "error", "message": "render ended without producing a video"}
    except Exception as e:
        logger.exception("pmax video render job %s failed", job_id)
        _render_jobs[job_id] = {"status": "error", "message": str(e)[:300]}


@router.post("/render")
async def start_video_render(body: PMaxVideoRenderRequest) -> Dict[str, str]:
    """Start a Hyperframes render job; poll GET /api/pmax/video/render/{id}."""
    if not body.scenes:
        raise HTTPException(status_code=400, detail="scenes is required")
    if not body.account_id:
        raise HTTPException(status_code=400, detail="account_id is required")
    job_id = str(uuid.uuid4())
    _render_jobs[job_id] = {"status": "running", "stage": "queued", "message": "Render queued…"}
    asyncio.create_task(_run_render_job(job_id, body))
    return {"job_id": job_id, "status": "running"}


@router.get("/render/{job_id}")
async def get_video_render(job_id: str) -> Dict[str, Any]:
    job = _render_jobs.get(job_id)
    if not job:
        return {"status": "error", "message": "unknown render job (server restarted?) — start a new render"}
    return job


# ── Metadata: creative_director drafts YouTube title + description ──

_meta_jobs: Dict[str, Dict[str, Any]] = {}

_TITLE_MAX_CHARS = 95     # YouTube's hard cap is 100; 95 leaves headroom
_DESC_MAX_CHARS = 5000    # YouTube's hard cap


class PMaxVideoMetadataRequest(BaseModel):
    account_id: str
    brief: str = ""
    business_name: str = ""
    final_url: str = ""
    campaign_name: str = ""
    scenes: List[dict] = Field(default_factory=list)   # storyboard, for grounding


def _metadata_prompt(body: PMaxVideoMetadataRequest) -> str:
    spoken = " ".join(
        (s.get("_speak_text") or s.get("speak") or "").strip()
        for s in body.scenes if isinstance(s, dict)
    ).strip()
    return (
        "Write YouTube metadata for a 20-30 second Performance Max video ad. "
        "First fetch the landing page to ground every claim — never invent offers, numbers, or program names.\n\n"
        f"Landing page: {body.final_url or '(none — use the brief only)'}\n"
        f"Business name: {body.business_name or '-'}\n"
        f"Campaign name: {body.campaign_name or '-'}\n"
        f"Brief from the operator: {body.brief or '(none — derive from the landing page)'}\n"
        + (f"Spoken script of the video: {spoken}\n" if spoken else "")
        + "\nDELIVERABLES:\n"
        f"1. `titles` — exactly 3 options, each ≤{_TITLE_MAX_CHARS} characters. Vary the angles "
        "(benefit, specificity, question). No clickbait, no ALL CAPS, no third-party brand names.\n"
        "2. `description` — 2-3 SHORT paragraphs (plain text, blank line between paragraphs). "
        "Grounded in the landing page; end with a clear call to action followed by the landing page URL "
        "on its own line. No em dashes. No invented stats. No hashtag spam.\n\n"
        "Respond with ONLY this JSON, no prose:\n"
        '{"titles": ["...", "...", "..."], "description": "..."}'
    )


async def _run_metadata_job(job_id: str, body: PMaxVideoMetadataRequest) -> None:
    try:
        from app.services.agent import stream_agent_response

        parts: list[str] = []
        async for ev in stream_agent_response(
            user_message=_metadata_prompt(body),
            account_id=body.account_id,
            active_role="creative_director",
            tool_allowlist=[],  # no Google Ads tools; built-in web fetch still grounds the landing page
        ):
            if ev.get("type") == "text":
                parts.append(ev.get("content", ""))
        raw = "".join(parts)

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            _meta_jobs[job_id] = {"status": "error", "message": "Creative Director returned no JSON — try again."}
            return
        try:
            data = json.loads(m.group(0))
        except Exception:
            _meta_jobs[job_id] = {"status": "error", "message": "Could not parse the metadata draft — try again."}
            return

        # Server-side enforcement: the model's promises aren't a contract.
        titles = [
            t.strip()[:_TITLE_MAX_CHARS]
            for t in (data.get("titles") or [])
            if isinstance(t, str) and t.strip()
        ][:3]
        if not titles:
            _meta_jobs[job_id] = {"status": "error", "message": "Draft produced no usable titles — try again."}
            return

        desc = (data.get("description") or "").strip()
        # House rule: no em dashes in ad copy (applies to YT descriptions too).
        desc = desc.replace("—", "-").replace("–", "-")
        if body.final_url and body.final_url not in desc:
            desc = f"{desc}\n\n{body.final_url}".strip()
        desc = desc[:_DESC_MAX_CHARS]

        _meta_jobs[job_id] = {"status": "done", "titles": titles, "description": desc}
    except Exception as e:
        logger.exception("pmax video metadata job %s failed", job_id)
        _meta_jobs[job_id] = {"status": "error", "message": str(e)[:300]}


@router.post("/metadata")
async def start_video_metadata(body: PMaxVideoMetadataRequest) -> Dict[str, str]:
    """Start a YouTube title+description draft; poll GET /api/pmax/video/metadata/{id}."""
    if not body.account_id:
        raise HTTPException(status_code=400, detail="account_id is required")
    job_id = str(uuid.uuid4())
    _meta_jobs[job_id] = {"status": "running"}
    asyncio.create_task(_run_metadata_job(job_id, body))
    return {"job_id": job_id, "status": "running"}


@router.get("/metadata/{job_id}")
async def get_video_metadata(job_id: str) -> Dict[str, Any]:
    job = _meta_jobs.get(job_id)
    if not job:
        return {"status": "error", "message": "unknown metadata job (server restarted?) — start a new draft"}
    return job


# ── Frames: ffmpeg stills from a rendered video → thumbnail candidates ──

_FRAME_POSITIONS = (0.10, 0.35, 0.60, 0.85)   # fraction of duration


class PMaxVideoFramesRequest(BaseModel):
    asset_id: str               # ad_assets row id of a rendered video
    account_id: str = ""        # owner of the new image rows (falls back to the video's)


async def _probe_duration(path) -> Optional[float]:
    """ffprobe the container duration; None when it can't be read."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except Exception:
        return None


@router.post("/frames")
async def extract_video_frames(body: PMaxVideoFramesRequest) -> Dict[str, Any]:
    """Extract 4 stills (10/35/60/85% of duration) from a rendered video.

    Each still becomes an ad_assets image row (account_id set) served from
    the normal assets path, so any of them can be picked as the YouTube
    thumbnail — or reused anywhere else the library reaches. Fast enough
    (4 keyframe seeks on a ≤60s mp4) to run inline, no job needed.
    """
    import shutil as _shutil
    if _shutil.which("ffmpeg") is None:
        raise HTTPException(status_code=500, detail="ffmpeg not on PATH")

    from app.database import get_db
    from app.routers.assets import ASSETS_DIR

    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT filename, url, type, duration, account_id FROM ad_assets WHERE id = ?",
            (body.asset_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"asset {body.asset_id} not found")
    if row["type"] != "video":
        raise HTTPException(status_code=400, detail=f"asset {body.asset_id} is not a video")

    stored = (row["url"] or "").rsplit("/", 1)[-1] or row["filename"]
    src = ASSETS_DIR / stored
    if not src.is_file():
        raise HTTPException(status_code=404, detail=f"video file missing on disk: {stored}")

    duration = row["duration"] or await _probe_duration(src)
    if not duration or duration <= 0:
        raise HTTPException(status_code=422, detail="could not determine video duration")

    account_id = body.account_id or row["account_id"]
    frames: list[dict] = []
    for frac in _FRAME_POSITIONS:
        t = round(duration * frac, 2)
        frame_id = str(uuid.uuid4())
        out_path = ASSETS_DIR / f"{frame_id}.jpg"
        # -ss before -i = fast keyframe seek; -q:v 2 = high-quality JPEG.
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-ss", str(t), "-i", str(src),
            "-frames:v", "1", "-q:v", "2", str(out_path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0 or not out_path.is_file():
            logger.warning("frame extraction at %.2fs failed: %s", t, (err or b"").decode()[-200:])
            continue
        try:
            from PIL import Image as _PILImage
            with _PILImage.open(out_path) as im:
                w, h = im.size
        except Exception:
            w = h = None
        url = f"/api/assets/file/{frame_id}.jpg"
        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO ad_assets
                   (id, account_id, type, filename, url, width, height, size_bytes, script, source)
                   VALUES (?, ?, 'image', ?, ?, ?, ?, ?, ?, 'generated')""",
                (frame_id, account_id, f"frame-{t:g}s-{row['filename']}.jpg", url,
                 w, h, out_path.stat().st_size,
                 f"Video frame at {t:g}s from {row['filename']} (thumbnail candidate)"),
            )
            await db.commit()
        finally:
            await db.close()
        frames.append({"id": frame_id, "url": url, "t": t})

    if not frames:
        raise HTTPException(status_code=500, detail="frame extraction produced no images")
    return {"frames": frames, "duration": duration}
