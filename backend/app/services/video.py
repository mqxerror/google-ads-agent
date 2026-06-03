"""Video ad creative pipeline.

Chains ElevenLabs (voice) → HeyGen (avatar) to produce a finished MP4 from a
spoken script. Designed as an async pipeline so the HTTP handler can stream
progress events back to the UI.

The Mercan HeyGen + ElevenLabs accounts are the only ones wired in right now —
per-client credentials would mean adding them to the account_credentials table
and threading them through here. That's a later problem.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Where rendered MP4s live. Served statically via /api/video/assets/{filename}
ASSETS_DIR = settings.DATA_DIR / "ad_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

HEYGEN_API = "https://api.heygen.com"
HEYGEN_UPLOAD = "https://upload.heygen.com/v1/asset"
ELEVENLABS_API = "https://api.elevenlabs.io/v1"


@dataclass
class VideoRequest:
    script: str
    voice_id: str | None = None
    avatar_id: str | None = None
    width: int = 1280
    height: int = 720  # 16:9 default; use (720, 1280) for 9:16, (1080, 1080) for 1:1
    model_id: str = "eleven_multilingual_v2"  # ElevenLabs TTS model
    character_type: str = "avatar"  # "avatar" (stock) or "talking_photo" (Avatar Snap)


@dataclass
class VideoResult:
    video_id: str
    local_path: Path
    public_url: str  # URL the frontend can hit
    script: str
    duration_s: float | None = None


# ── ElevenLabs ─────────────────────────────────────────────────────


async def elevenlabs_tts(script: str, voice_id: str, model_id: str = "eleven_multilingual_v2") -> bytes:
    """Generate speech MP3 from a script. Returns raw audio bytes."""
    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    url = f"{ELEVENLABS_API}/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": script,
        "model_id": model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs TTS failed: {r.status_code} {r.text[:300]}")
        return r.content


# ── HeyGen ─────────────────────────────────────────────────────────


async def heygen_upload_audio(audio_bytes: bytes) -> str:
    """Upload an MP3 to HeyGen's asset store. Returns the asset_id."""
    if not settings.HEYGEN_API_KEY:
        raise RuntimeError("HEYGEN_API_KEY not set")
    headers = {
        "X-Api-Key": settings.HEYGEN_API_KEY,
        "Content-Type": "audio/mpeg",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(HEYGEN_UPLOAD, headers=headers, content=audio_bytes)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"HeyGen asset upload failed: {r.status_code} {r.text[:300]}")
        data = r.json()
        # HeyGen upload response shape: {"code":100,"data":{"id":"...","name":"...",...}}
        asset_id = (data.get("data") or {}).get("id") or data.get("asset_id")
        if not asset_id:
            raise RuntimeError(f"HeyGen upload returned no asset id: {data}")
        return asset_id


async def heygen_generate_video(
    avatar_id: str,
    audio_asset_id: str,
    width: int,
    height: int,
    *,
    character_type: str = "avatar",  # "avatar" (stock) or "talking_photo" (Avatar Snap)
) -> str:
    """Kick off a HeyGen video render using an uploaded audio asset.

    `character_type="avatar"` → stock catalogue avatar (avatar_id from /v2/avatars).
    `character_type="talking_photo"` → photo-based talking head (talking_photo_id
    from a prior /v1/talking_photo creation).

    Returns video_id for polling.
    """
    url = f"{HEYGEN_API}/v2/video/generate"
    headers = {
        "X-Api-Key": settings.HEYGEN_API_KEY,
        "Content-Type": "application/json",
    }
    if character_type == "talking_photo":
        character: dict = {
            "type": "talking_photo",
            "talking_photo_id": avatar_id,
            "talking_photo_style": "stable",
        }
    else:
        character = {
            "type": "avatar",
            "avatar_id": avatar_id,
            "avatar_style": "normal",
        }
    payload = {
        "video_inputs": [
            {
                "character": character,
                "voice": {"type": "audio", "audio_asset_id": audio_asset_id},
            }
        ],
        "dimension": {"width": width, "height": height},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"HeyGen generate failed: {r.status_code} {r.text[:300]}")
        data = r.json()
        video_id = (data.get("data") or {}).get("video_id")
        if not video_id:
            raise RuntimeError(f"HeyGen generate returned no video_id: {data}")
        return video_id


async def heygen_create_talking_photo(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """Upload a photo to HeyGen as a talking_photo asset. Returns talking_photo_id.

    Uses the upload-asset endpoint, then registers it as a talking_photo. HeyGen's
    talking_photo creation can take a few seconds — we poll briefly.
    """
    if not settings.HEYGEN_API_KEY:
        raise RuntimeError("HEYGEN_API_KEY not set")

    headers_upload = {"X-Api-Key": settings.HEYGEN_API_KEY, "Content-Type": content_type}
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Upload the image as an asset
        r = await client.post(HEYGEN_UPLOAD, headers=headers_upload, content=image_bytes)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"HeyGen photo upload failed: {r.status_code} {r.text[:300]}")
        data = r.json()
        asset = (data.get("data") or {})
        # HeyGen returns image_url for image uploads
        image_url = asset.get("url") or asset.get("image_url")
        asset_id = asset.get("id")
        if not image_url and not asset_id:
            raise RuntimeError(f"HeyGen photo upload returned no usable id/url: {data}")

        # 2. Create a talking_photo from the uploaded image. Endpoint:
        #    POST /v1/talking_photo  with {image_url}
        create_url = f"{HEYGEN_API}/v1/talking_photo"
        payload = {"image_url": image_url} if image_url else {"image_key": asset_id}
        r2 = await client.post(create_url, headers={"X-Api-Key": settings.HEYGEN_API_KEY,
                                                     "Content-Type": "application/json"},
                                json=payload)
        if r2.status_code not in (200, 201):
            # Some HeyGen accounts require talking_photo creation via dashboard.
            # Surface a clear error so the UI can prompt the user.
            raise RuntimeError(
                f"HeyGen talking_photo creation failed: {r2.status_code} {r2.text[:300]}. "
                "If your plan doesn't include programmatic talking-photo creation, "
                "create one in the HeyGen dashboard and pass its ID via avatar_id."
            )
        body = r2.json().get("data") or {}
        tp_id = body.get("talking_photo_id") or body.get("id")
        if not tp_id:
            raise RuntimeError(f"HeyGen talking_photo response missing id: {r2.json()}")
        return tp_id


async def heygen_poll_video(
    video_id: str,
    max_wait_s: int = 600,
    poll_every_s: float = 4.0,
    on_tick: "callable | None" = None,
) -> dict:
    """Poll until the video is done or we hit the timeout.

    If `on_tick` is supplied, it's called with (status, elapsed_s, payload) on
    every poll so the caller can surface live progress to the UI.
    """
    url = f"{HEYGEN_API}/v1/video_status.get"
    headers = {"X-Api-Key": settings.HEYGEN_API_KEY}
    params = {"video_id": video_id}
    started_at = asyncio.get_event_loop().time()
    deadline = started_at + max_wait_s
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            r = await client.get(url, headers=headers, params=params)
            if r.status_code != 200:
                raise RuntimeError(f"HeyGen poll failed: {r.status_code} {r.text[:200]}")
            body = r.json().get("data") or {}
            status = body.get("status")
            elapsed = int(asyncio.get_event_loop().time() - started_at)
            if on_tick:
                try:
                    on_tick(status, elapsed, body)
                except Exception:
                    pass
            if status == "completed":
                return body
            if status in ("failed", "error"):
                raise RuntimeError(f"HeyGen video failed: {body.get('error') or body}")
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(f"HeyGen poll timed out after {max_wait_s}s (last status={status})")
            await asyncio.sleep(poll_every_s)


async def download_to_file(url: str, path: Path) -> None:
    """Stream a remote MP4 to disk."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=1 << 20):
                    f.write(chunk)


# ── Orchestration ──────────────────────────────────────────────────


async def generate_video(req: VideoRequest) -> AsyncIterator[dict]:
    """Run the full pipeline, yielding progress events.

    Event shape: {"type": "status"|"done"|"error", "stage": str, "message": str, ...}
    """
    voice_id = req.voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID
    avatar_id = req.avatar_id or settings.HEYGEN_DEFAULT_AVATAR_ID
    video_uuid = str(uuid.uuid4())

    try:
        yield {"type": "status", "stage": "tts", "message": "Generating voice with ElevenLabs..."}
        audio_bytes = await elevenlabs_tts(req.script, voice_id, req.model_id)

        yield {
            "type": "status",
            "stage": "upload",
            "message": f"Uploading {len(audio_bytes) // 1024} KB audio to HeyGen...",
        }
        asset_id = await heygen_upload_audio(audio_bytes)

        yield {"type": "status", "stage": "render", "message": "HeyGen is rendering the avatar..."}
        video_id = await heygen_generate_video(
            avatar_id, asset_id, req.width, req.height,
            character_type=req.character_type,
        )

        yield {
            "type": "status",
            "stage": "poll",
            "message": "Waiting for render to finish...",
            "video_id": video_id,
        }

        # Inline poll loop so we can stream progress events to the client.
        # HeyGen can take several minutes for longer scripts; cap at 10 min.
        import httpx as _httpx
        poll_url = f"{HEYGEN_API}/v1/video_status.get"
        poll_headers = {"X-Api-Key": settings.HEYGEN_API_KEY}
        started = asyncio.get_event_loop().time()
        max_wait_s = 600
        result: dict | None = None
        async with _httpx.AsyncClient(timeout=30.0) as client:
            while True:
                r = await client.get(poll_url, headers=poll_headers, params={"video_id": video_id})
                if r.status_code != 200:
                    raise RuntimeError(f"HeyGen poll failed: {r.status_code} {r.text[:200]}")
                body = r.json().get("data") or {}
                status = body.get("status")
                elapsed = int(asyncio.get_event_loop().time() - started)
                yield {
                    "type": "status",
                    "stage": "poll",
                    "message": f"HeyGen status: {status or 'queued'} — {elapsed}s elapsed",
                    "video_id": video_id,
                    "heygen_status": status,
                    "elapsed_s": elapsed,
                }
                if status == "completed":
                    result = body
                    break
                if status in ("failed", "error"):
                    raise RuntimeError(f"HeyGen video failed: {body.get('error') or body}")
                if elapsed >= max_wait_s:
                    raise TimeoutError(
                        f"HeyGen poll timed out after {max_wait_s}s (last status={status}). "
                        f"The job may still complete — check video_id {video_id} manually."
                    )
                await asyncio.sleep(4.0)
        assert result is not None

        video_url = result.get("video_url")
        if not video_url:
            raise RuntimeError(f"HeyGen completed but no video_url: {result}")

        yield {"type": "status", "stage": "download", "message": "Downloading rendered MP4..."}
        local_path = ASSETS_DIR / f"{video_uuid}.mp4"
        await download_to_file(video_url, local_path)

        yield {
            "type": "done",
            "stage": "done",
            "message": "Video ready.",
            "video_id": video_uuid,
            "public_url": f"/api/video/assets/{video_uuid}.mp4",
            "duration": result.get("duration"),
            "thumbnail_url": result.get("thumbnail_url"),
        }

    except Exception as e:
        logger.exception("generate_video failed")
        yield {"type": "error", "stage": "error", "message": str(e)}
