"""YouTube upload — one-time OAuth connect + resumable video upload.

Reuses the Google Cloud OAuth client already configured for the Google Ads
API (GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET in backend/.env) with
the youtube.upload scope. The Google Ads refresh token does NOT carry that
scope, so a one-time consent flow mints a SEPARATE refresh token stored at
data/youtube_token.json (chmod 600, gitignored — never in the repo).

Connect flow (one human click, once):
  1. GET /api/youtube/auth-url      → consent URL (localhost callback)
  2. user approves in browser       → Google redirects to
     http://localhost:8000/api/youtube/oauth-callback?code=...
  3. callback exchanges code → refresh token saved to TOKEN_PATH.

Upload: resumable videos.insert via google-api-python-client. Synchronous —
ALWAYS call through asyncio.to_thread so the event loop never blocks.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
# Loopback redirect — Desktop OAuth clients accept any localhost path without
# pre-registration; Web clients need this exact URI added in Cloud Console.
REDIRECT_URI = "http://localhost:8000/api/youtube/oauth-callback"
TOKEN_PATH: Path = settings.DATA_DIR / "youtube_token.json"

# CSRF guard for the consent round-trip. In-memory is fine: single process,
# states are single-use and expire after 10 minutes.
_pending_states: dict[str, float] = {}
_STATE_TTL_S = 600.0


class YouTubeNotConfigured(RuntimeError):
    """OAuth client id/secret missing from env."""


class YouTubeNotConnected(RuntimeError):
    """No refresh token on disk — run the connect flow first."""


class YouTubeThumbnailRejected(RuntimeError):
    """thumbnails.set refused (usually: channel not phone-verified → 403).
    The video itself uploaded fine — callers surface this as a warning."""


def _client_creds() -> tuple[str, str]:
    cid = settings.GOOGLE_ADS_CLIENT_ID
    csec = settings.GOOGLE_ADS_CLIENT_SECRET
    if not cid or not csec:
        raise YouTubeNotConfigured(
            "GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET not set in backend/.env"
        )
    return cid, csec


# ── Connect flow ───────────────────────────────────────────────────


def build_auth_url() -> str:
    """Return the Google consent URL for the one-time YouTube connect."""
    cid, _ = _client_creds()
    state = secrets.token_urlsafe(24)
    now = time.monotonic()
    # Evict expired states while we're here
    for s, t in list(_pending_states.items()):
        if now - t > _STATE_TTL_S:
            _pending_states.pop(s, None)
    _pending_states[state] = now
    params = {
        "client_id": cid,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # we need a refresh token
        # consent: force refresh-token issuance even on re-auth.
        # select_account: ALWAYS show the account/brand-channel chooser so a
        # wrong logged-in Google account can't be silently reused (hit live:
        # connected a channel-less account -> youtubeSignupRequired on upload).
        "prompt": "consent select_account",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def consume_state(state: str) -> bool:
    """Single-use CSRF check for the callback."""
    issued = _pending_states.pop(state or "", None)
    return issued is not None and (time.monotonic() - issued) <= _STATE_TTL_S


async def exchange_code(code: str) -> None:
    """Exchange the consent code for tokens and persist the refresh token."""
    cid, csec = _client_creds()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": cid,
                "client_secret": csec,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    if r.status_code != 200:
        raise RuntimeError(f"token exchange failed ({r.status_code}): {r.text[:300]}")
    payload = r.json()
    refresh = payload.get("refresh_token")
    if not refresh:
        # Happens when Google skips re-consent; prompt=consent should prevent it.
        raise RuntimeError(
            "Google returned no refresh_token — revoke the app at "
            "myaccount.google.com/permissions and connect again."
        )
    _save_token({
        "refresh_token": refresh,
        "scope": payload.get("scope", SCOPE),
        "obtained_at": int(time.time()),
    })
    logger.info("YouTube refresh token stored at %s", TOKEN_PATH)


def _save_token(payload: dict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)  # owner-only — this is a live credential


def load_refresh_token() -> Optional[str]:
    try:
        if not TOKEN_PATH.is_file():
            return None
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        return data.get("refresh_token") or None
    except Exception:
        logger.exception("failed to read %s", TOKEN_PATH)
        return None


def is_connected() -> bool:
    return load_refresh_token() is not None


# ── Upload (synchronous — run via asyncio.to_thread) ───────────────


def _build_service():
    """Authenticated YouTube Data API v3 client from the stored refresh token.
    BLOCKING (discovery build) — only call from worker threads."""
    refresh = load_refresh_token()
    if not refresh:
        raise YouTubeNotConnected("YouTube not connected — run the connect flow first")
    cid, csec = _client_creds()

    # Imports kept local so the module imports cleanly even before
    # `uv add google-api-python-client` lands in an environment.
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=refresh,
        token_uri=TOKEN_ENDPOINT,
        client_id=cid,
        client_secret=csec,
        scopes=[SCOPE],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video_sync(
    file_path: Path,
    *,
    title: str,
    description: str = "",
    privacy_status: str = "unlisted",   # PMax accepts unlisted videos
    tags: Optional[list[str]] = None,
) -> str:
    """Resumable upload via YouTube Data API v3 videos.insert.

    Returns the YouTube video id. Raises YouTubeNotConnected when no refresh
    token exists, RuntimeError on API failures. BLOCKING — wrap in a thread.
    """
    if not file_path.is_file():
        raise RuntimeError(f"video file not found: {file_path}")

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    service = _build_service()

    body = {
        "snippet": {
            "title": (title or file_path.stem)[:100],   # YouTube hard limit
            "description": (description or "")[:5000],
            "categoryId": "22",                          # People & Blogs — safe default
            **({"tags": tags[:30]} if tags else {}),
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(
        str(file_path),
        mimetype="video/mp4",
        chunksize=4 * 1024 * 1024,
        resumable=True,
    )
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    last_progress = -1
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct != last_progress:
                    logger.info("YouTube upload %s: %d%%", file_path.name, pct)
                    last_progress = pct
    except HttpError as e:
        raise RuntimeError(f"YouTube API rejected the upload: {e}") from e

    video_id = (response or {}).get("id")
    if not video_id:
        raise RuntimeError(f"upload finished but no video id in response: {response}")
    logger.info("YouTube upload done: %s → https://youtube.com/watch?v=%s", file_path.name, video_id)
    return video_id


# ── Thumbnail (synchronous — run via asyncio.to_thread) ────────────

THUMB_MAX_BYTES = 2 * 1024 * 1024   # YouTube rejects custom thumbnails >2MB
THUMB_MAX_WIDTH = 1280              # YouTube's recommended max resolution


def _prepare_thumbnail_jpg(image_path: Path) -> tuple[Path, bool]:
    """Return (jpg_path, is_temp). Re-encodes to JPEG when the source is
    another format, oversized (>2MB), or wider than 1280px. Quality steps
    down 90→60 until the byte budget fits."""
    if (
        image_path.suffix.lower() in (".jpg", ".jpeg")
        and image_path.stat().st_size < THUMB_MAX_BYTES
    ):
        return image_path, False

    import tempfile

    from PIL import Image

    with Image.open(image_path) as im:
        img = im.convert("RGB")    # drops alpha (PNG/WebP logos etc.)
        if img.width > THUMB_MAX_WIDTH:
            ratio = THUMB_MAX_WIDTH / img.width
            img = img.resize((THUMB_MAX_WIDTH, max(1, round(img.height * ratio))))
        fd, tmp_name = tempfile.mkstemp(suffix=".jpg", prefix="yt-thumb-")
        os.close(fd)
        tmp = Path(tmp_name)
        for quality in (90, 80, 70, 60):
            img.save(tmp, "JPEG", quality=quality, optimize=True)
            if tmp.stat().st_size < THUMB_MAX_BYTES:
                break
    return tmp, True


def set_thumbnail_sync(video_id: str, image_path: Path) -> None:
    """thumbnails.set on an uploaded video. Raises YouTubeThumbnailRejected
    on a 4xx policy refusal (channel not phone-verified is the common one)
    so callers can degrade to a warning instead of failing the upload.
    BLOCKING — wrap in a thread."""
    if not image_path.is_file():
        raise RuntimeError(f"thumbnail image not found: {image_path}")

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    jpg_path, is_temp = _prepare_thumbnail_jpg(image_path)
    try:
        service = _build_service()
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(jpg_path), mimetype="image/jpeg"),
        ).execute()
        logger.info("YouTube thumbnail set on %s (%s)", video_id, image_path.name)
    except HttpError as e:
        status = getattr(getattr(e, "resp", None), "status", None)
        if status in (401, 403):
            raise YouTubeThumbnailRejected(
                "thumbnail needs a phone-verified channel — set it manually in YouTube Studio"
            ) from e
        raise RuntimeError(f"YouTube rejected the thumbnail: {e}") from e
    finally:
        if is_temp:
            jpg_path.unlink(missing_ok=True)
