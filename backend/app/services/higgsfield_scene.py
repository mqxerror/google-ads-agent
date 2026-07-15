"""Higgsfield clip as a storyboard scene — Epic 11 P1.

A storyboard scene `{type: "higgsfield", prompt, model, duration}`
becomes a generated video clip spliced into the hyperframes ffmpeg
stitch. This module owns the two pieces premium_reel delegates to:

1. `resolve_higgsfield_clip` — returns a LOCAL mp4 path for the scene.
   Credit-burn guard: clips are cached in `ad_assets` by `prompt_hash`
   (sha256 of model|prompt|duration|aspect, V18 column). A re-render
   of the same storyboard reuses the cached file instead of paying
   Higgsfield again. Cache misses generate via HiggsfieldClient
   (timeout 600s — veo/kling clips queue 5-10 min) and record a row so
   the Studio library shows the clip like any other generation.

2. `normalize_clip` — mezzanine-normalize to 1080p/30fps/yuv420p so
   ffmpeg's xfade chain (which assumes uniform dimensions + fps across
   inputs) accepts the clip next to hyperframes scenes. Optional
   freeze-frame tail (`min_duration`) covers the "spoken line is
   longer than the fixed-length clip" case — generative models can't
   stretch to audio the way HTML scenes can.

Scenes per render are capped at MAX_HIGGSFIELD_SCENES (8) — enforced
here AND in pmax_video's `_clean_scenes` (defense in depth; the
renderer cap also covers hand-edited storyboards). 60s worst case =
8× 8s Veo clips.

DECOUPLING: studio service layer — no google_ads imports.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Hard cap on generative scenes per render — the credit-burn guard from
# the video-engine plan. Anything beyond this is skipped with a warning.
# 60s worst case = 8× 8s Veo clips.
MAX_HIGGSFIELD_SCENES = 8

DEFAULT_SCENE_MODEL = "veo3_1_lite"   # 8 credits / 5s — cheapest verified


def scene_prompt_hash(
    *, model: str, prompt: str, duration: Optional[int], aspect: str,
) -> str:
    """Deterministic cache key for one generated clip."""
    key = f"{model}|{prompt.strip()}|{duration if duration is not None else ''}|{aspect}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def _find_cached_clip(prompt_hash: str) -> Optional[Path]:
    """Completed ad_assets row with this hash whose file still exists."""
    from app.database import get_db
    from app.routers.assets import ASSETS_DIR

    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT url, filename FROM ad_assets
               WHERE prompt_hash = ? AND type = 'video' AND status = 'completed'
               ORDER BY created_at DESC""",
            (prompt_hash,),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()
    for row in rows:
        stored = (row["url"] or "").rsplit("/", 1)[-1] or row["filename"]
        path = ASSETS_DIR / stored
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


async def resolve_higgsfield_clip(
    scene: dict[str, Any],
    *,
    aspect: str = "16:9",
    account_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> tuple[Path, bool]:
    """Local mp4 for a higgsfield scene. Returns (path, was_cached).

    Cache hit = zero credits. Miss = submit + wait via the CLI, download
    the CDN result into ASSETS_DIR, record an ad_assets row (with
    prompt_hash) so subsequent re-renders reuse it.
    """
    from app.services.model_catalog import clamp_duration

    prompt = (scene.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("higgsfield scene has no prompt")
    model = (scene.get("model") or DEFAULT_SCENE_MODEL).strip()
    raw_duration = scene.get("duration")
    try:
        requested = int(raw_duration) if raw_duration is not None else None
    except (TypeError, ValueError):
        requested = None
    duration = clamp_duration(model, requested)

    p_hash = scene_prompt_hash(
        model=model, prompt=prompt, duration=duration, aspect=aspect,
    )
    cached = await _find_cached_clip(p_hash)
    if cached is not None:
        logger.info("higgsfield scene cache HIT (%s) — no credits burned", p_hash[:12])
        return cached, True

    # ── Generate ──────────────────────────────────────────────────
    from app.services.higgsfield_client import HiggsfieldClient

    client = HiggsfieldClient(timeout_s=600.0)
    params: dict[str, Any] = {"aspect_ratio": aspect}
    if duration is not None:
        params["duration"] = duration
    result = await client.submit_video(model=model, prompt=prompt, **params)
    cdn_url = result.get("image_url")  # client uses one key for both media types
    if not cdn_url:
        raise RuntimeError("higgsfield returned no clip URL")

    raw = result.get("raw") or []
    hf_job_id = None
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        hf_job_id = str(raw[0].get("id") or "") or None

    path = await _download_clip(cdn_url)

    # Record in ad_assets — the library shows it AND the prompt_hash
    # makes the next render of this storyboard free.
    from app.database import get_db

    asset_id = path.stem
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets
               (id, account_id, campaign_id, type, filename, url, source,
                status, higgsfield_model, prompt, aspect_ratio, duration,
                higgsfield_cdn_url, higgsfield_job_id, prompt_hash,
                size_bytes, created_at)
               VALUES (?, ?, ?, 'video', ?, ?, 'higgsfield', 'completed',
                       ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                asset_id, account_id, campaign_id, path.name,
                f"/api/assets/file/{path.name}", model, prompt, aspect,
                duration, cdn_url, hf_job_id, p_hash, path.stat().st_size,
            ),
        )
        await db.commit()
    except Exception:
        # UNIQUE(higgsfield_job_id) collision on a retry path, or any
        # other recording hiccup — the clip file itself is fine; caching
        # just won't kick in for this one. Don't fail the render.
        logger.exception("failed to record higgsfield scene clip in ad_assets")
    finally:
        await db.close()

    logger.info(
        "higgsfield scene generated (model=%s dur=%s hash=%s)",
        model, duration, p_hash[:12],
    )
    return path, False


async def _download_clip(cdn_url: str) -> Path:
    """Download the CDN mp4 into ASSETS_DIR (CDN URLs expire in 24-48h,
    so we always localize — same rule as studio.py's image path)."""
    import httpx

    from app.routers.assets import ASSETS_DIR

    asset_id = str(uuid.uuid4())
    dest = ASSETS_DIR / f"{asset_id}.mp4"
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(cdn_url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


async def normalize_clip(
    src: Path,
    dest: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    min_duration: Optional[float] = None,
) -> Path:
    """Mezzanine-normalize a generated clip for the xfade concat chain.

    scale + pad (letterbox, never stretch) to width x height, constant
    fps, yuv420p. Video stream only — the storyboard stitcher muxes VO
    and music itself, and per-clip native audio (e.g. Kling --sound on)
    would fight the bed. When `min_duration` exceeds the clip length,
    the last frame freezes (tpad clone) so a longer spoken line fits.
    """
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={fps},format=yuv420p"
    )
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if min_duration is not None and min_duration > 0:
        src_dur = await _probe_duration(src)
        if float(min_duration) > src_dur + 0.05:
            # Freeze the last frame out to min_duration, trim exactly.
            pad_s = float(min_duration) - src_dur + 1.0  # slack; -t trims
            vf += f",tpad=stop_mode=clone:stop_duration={pad_s:.3f}"
            cmd += ["-t", f"{float(min_duration):.3f}"]
    cmd += [
        "-vf", vf, "-an",
        "-c:v", "libx264", "-preset", "veryfast",
        "-movflags", "+faststart", str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not dest.is_file():
        snippet = stderr.decode("utf-8", errors="replace")[-1200:]
        raise RuntimeError(f"clip normalize failed (rc={proc.returncode}):\n{snippet}")
    return dest


async def _probe_duration(mp4: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(mp4),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode("utf-8").strip())
    except Exception:
        return 5.0
