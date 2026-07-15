"""Video Engine router — segment-timeline renders (Epic 11 P2).

Two surfaces on top of services/video_engine.py:

  POST /api/video-engine/estimate → summed credit estimate for every
                                    scene that would touch Higgsfield
                                    (the cost guardrail the operator
                                    sees BEFORE clicking render).
                                    Accepts `segments` (timeline) or
                                    raw `scenes` (wizard storyboards).

  POST /api/video-engine/render   → job+poll render of a segment
                                    timeline (soul intro + AI clip +
                                    storyboard scenes). MP4 lands in
                                    ad_assets with account_id set so
                                    the Studio library shows it.
  GET  /api/video-engine/render/{job_id}

Job state is in-memory (same tradeoff as pmax_video's job dicts). The
plan's DB-row job state is deliberately deferred to P3 so this build
doesn't add a schema migration next to the parallel Epic 13 work.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video-engine", tags=["video-engine"])

_render_jobs: Dict[str, Dict[str, Any]] = {}


# ── Estimate ─────────────────────────────────────────────────────────


class VideoEngineEstimateRequest(BaseModel):
    # A segment timeline, a flat storyboard scene list, OR the
    # finished-video trio (target_seconds + model_id + prompt) so the UI
    # can price an auto-planned finished video before rendering.
    segments: Optional[List[dict]] = None
    scenes: Optional[List[dict]] = None
    aspect: str = "16:9"
    target_seconds: Optional[int] = None
    model_id: Optional[str] = None
    prompt: Optional[str] = None


@router.post("/estimate")
async def estimate_timeline(body: VideoEngineEstimateRequest) -> Dict[str, Any]:
    """Summed live credit estimate (null-tolerant per item — a CLI
    hiccup shows as unknown_count, never a 5xx)."""
    from app.services.video_engine import (
        enforce_caps,
        estimate_timeline_credits,
        segments_to_scenes,
    )

    if body.segments:
        scenes, _ = segments_to_scenes(body.segments)
    elif body.scenes:
        scenes = [s for s in body.scenes if isinstance(s, dict)]
    elif body.target_seconds and body.model_id and body.prompt:
        # Finished-video plan priced before render. Scene dicts here use
        # key "type" (estimate_timeline_credits reads scene["type"]),
        # unlike the dispatcher which builds "engine" segments — that
        # asymmetry is intentional (this feeds estimate_timeline_credits
        # directly; the dispatcher feeds segments_to_scenes).
        from app.services.model_catalog import plan_scenes
        planned = plan_scenes(int(body.target_seconds), body.model_id)
        scenes = []
        for p in planned:
            sc = {"type": "higgsfield", "prompt": body.prompt, "model": body.model_id}
            if p.get("duration") is not None:
                sc["duration"] = p["duration"]
            scenes.append(sc)
    else:
        raise HTTPException(
            status_code=400,
            detail="provide `segments`, `scenes`, or `target_seconds`+`model_id`+`prompt`",
        )
    scenes, _ = enforce_caps(scenes)   # estimate what would actually render
    return await estimate_timeline_credits(scenes, aspect=body.aspect)


# ── Render (job + poll) ──────────────────────────────────────────────


class VideoEngineRenderRequest(BaseModel):
    account_id: str
    segments: List[dict] = []             # optional in finished-video mode
    voice_id: Optional[str] = None
    music_filename: Optional[str] = None
    quality: str = "draft"
    aspect: str = "16:9"
    campaign_id: Optional[str] = None
    brief: str = ""                       # library-card summary only
    sync_audio_to_scenes: bool = True
    # Finished-video mode — omit `segments` and set these three; the
    # dispatcher auto-plans N higgsfield clips sized to target_seconds.
    target_seconds: Optional[int] = None
    model_id: Optional[str] = None
    prompt: Optional[str] = None
    # Finished-video voiceover — one script for the whole video (the
    # dispatcher sizes a single VO track to the stitched duration).
    voiceover_script: Optional[str] = None


async def _run_render_job(job_id: str, body: VideoEngineRenderRequest) -> None:
    from app.routers.assets import record_generated_video
    from app.routers.video import _resolve_music_path
    from app.services.video_engine import VideoEngineRequest, generate_engine_video

    try:
        music_path = await _resolve_music_path(body.music_filename)
        req = VideoEngineRequest(
            account_id=body.account_id,
            segments=body.segments,
            voice_id=body.voice_id,
            music_path=music_path,
            quality=body.quality,
            aspect=body.aspect,
            campaign_id=body.campaign_id,
            sync_audio_to_scenes=body.sync_audio_to_scenes,
            target_seconds=body.target_seconds,
            model_id=body.model_id,
            prompt=body.prompt,
            voiceover_script=body.voiceover_script,
        )
        async for event in generate_engine_video(req):
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
                if body.brief.strip():
                    summary = body.brief.strip()
                elif not body.segments and body.target_seconds and body.model_id:
                    summary = f"Finished video — {body.target_seconds}s ({body.model_id})"
                else:
                    summary = f"Video engine timeline — {len(body.segments)} segments"
                try:
                    # account_id REQUIRED on the row — without it the Studio
                    # library (account-filtered) never shows the render.
                    await record_generated_video(
                        video_id=vid, filename=filename, url=url, script=summary,
                        account_id=body.account_id, campaign_id=body.campaign_id,
                        voice_id=body.voice_id, avatar_id="video-engine",
                        width=1920, height=1080, duration=event.get("duration"),
                        thumbnail_url=None, size_bytes=event.get("size_bytes"),
                    )
                except Exception:
                    logger.exception("failed to record video-engine render in ad_assets")
                _render_jobs[job_id] = {
                    "status": "done",
                    "asset_id": vid,
                    "url": url,
                    "duration": event.get("duration"),
                    "scene_count": event.get("scene_count"),
                }
                return
        if _render_jobs.get(job_id, {}).get("status") == "running":
            _render_jobs[job_id] = {"status": "error", "message": "render ended without producing a video"}
    except Exception as e:
        logger.exception("video-engine render job %s failed", job_id)
        _render_jobs[job_id] = {"status": "error", "message": str(e)[:300]}


@router.post("/render")
async def start_render(body: VideoEngineRenderRequest) -> Dict[str, str]:
    """Start a segment-timeline render; poll GET /api/video-engine/render/{id}."""
    if not body.segments and not (body.target_seconds and body.model_id and body.prompt):
        raise HTTPException(
            status_code=400,
            detail="provide `segments` or `target_seconds`+`model_id`+`prompt`",
        )
    if not body.account_id:
        raise HTTPException(status_code=400, detail="account_id is required")
    job_id = str(uuid.uuid4())
    _render_jobs[job_id] = {"status": "running", "stage": "queued", "message": "Render queued…"}
    asyncio.create_task(_run_render_job(job_id, body))
    return {"job_id": job_id, "status": "running"}


@router.get("/render/{job_id}")
async def get_render(job_id: str) -> Dict[str, Any]:
    job = _render_jobs.get(job_id)
    if not job:
        return {"status": "error", "message": "unknown render job (server restarted?) — start a new render"}
    return job
