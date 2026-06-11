"""YouTube connect + upload endpoints for the PMax wizard.

One-time connect (consent → localhost callback → refresh token on disk),
then POST /api/youtube/upload pushes a rendered ad_assets video as an
UNLISTED YouTube video and returns its id for the wizard's videoIds list.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.database import get_db
from app.services import youtube_uploader as yt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


@router.get("/status")
async def youtube_status() -> dict:
    """Is a refresh token on disk? The wizard polls this after opening consent."""
    return {"connected": yt.is_connected()}


@router.post("/disconnect")
async def youtube_disconnect() -> dict:
    """Forget the stored YouTube identity so a different account / brand
    channel can be connected (added after a wrong-account connect)."""
    try:
        yt.TOKEN_PATH.unlink(missing_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"could not remove token: {e}")
    return {"connected": False}


@router.get("/auth-url")
async def youtube_auth_url() -> dict:
    """Build the one-time Google consent URL. Open it in a new tab; after
    approval Google redirects to /api/youtube/oauth-callback on this server."""
    try:
        return {"auth_url": yt.build_auth_url()}
    except yt.YouTubeNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth-callback")
async def youtube_oauth_callback(code: str = "", state: str = "", error: str = "") -> HTMLResponse:
    """Google's redirect target. Exchanges the code and stores the refresh
    token, then tells the human to close the tab — the wizard's status poll
    picks up the connection automatically."""

    def _page(title: str, body: str, ok: bool) -> HTMLResponse:
        color = "#16a34a" if ok else "#dc2626"
        return HTMLResponse(
            f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title></head>
            <body style="font-family:Inter,system-ui,sans-serif;display:flex;align-items:center;
            justify-content:center;height:100vh;margin:0;background:#fafafa">
            <div style="max-width:420px;text-align:center">
            <h2 style="color:{color};margin-bottom:8px">{title}</h2>
            <p style="color:#555;font-size:14px;line-height:1.5">{body}</p>
            </div></body></html>"""
        )

    if error:
        return _page("YouTube connect failed", f"Google returned: {error}. Close this tab and try again.", False)
    if not code:
        return _page("YouTube connect failed", "No authorization code in the callback. Close this tab and try again.", False)
    if not yt.consume_state(state):
        return _page("YouTube connect failed", "State mismatch or expired link — start the connect flow again from the wizard.", False)
    try:
        await yt.exchange_code(code)
    except Exception as e:
        logger.exception("YouTube token exchange failed")
        return _page("YouTube connect failed", str(e), False)
    return _page(
        "YouTube connected",
        "Refresh token stored locally. You can close this tab — the wizard updates by itself.",
        True,
    )


class YouTubeUploadRequest(BaseModel):
    asset_id: str                 # ad_assets row id of a rendered video
    title: str
    description: str = ""
    privacy_status: str = "unlisted"
    thumbnail_asset_id: str = ""  # optional ad_assets image to set as the YT thumbnail


async def _resolve_asset_path(asset_id: str, expected_type: str) -> Path:
    """ad_assets id → on-disk Path, 4xx when the row or file is missing."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT filename, url, type FROM ad_assets WHERE id = ?", (asset_id,)
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"asset {asset_id} not found")
    if row["type"] != expected_type:
        raise HTTPException(status_code=400, detail=f"asset {asset_id} is not a {expected_type}")

    from app.routers.assets import ASSETS_DIR
    stored = (row["url"] or "").rsplit("/", 1)[-1] or row["filename"]
    path: Path = ASSETS_DIR / stored
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{expected_type} file missing on disk: {stored}")
    return path


@router.post("/upload")
async def youtube_upload(body: YouTubeUploadRequest) -> dict:
    """Upload a library video to YouTube (unlisted). Returns {video_id}.

    Files are small (5-15 MB) so a single request with a generous timeout is
    fine; the blocking google-api client runs in a worker thread so the event
    loop is never starved.

    When thumbnail_asset_id is set, thumbnails.set() runs after the insert.
    A thumbnail refusal (channel not phone-verified → 403) NEVER fails the
    request — the video id still comes back, plus a `warning` string the UI
    shows so the human can set it manually.
    """
    if not yt.is_connected():
        raise HTTPException(status_code=409, detail="YouTube not connected — run the connect flow first")
    if body.privacy_status not in ("unlisted", "private", "public"):
        raise HTTPException(status_code=400, detail="privacy_status must be unlisted, private, or public")
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="title is required")

    path = await _resolve_asset_path(body.asset_id, "video")
    # Resolve the thumbnail BEFORE the (expensive) upload so a bad id fails
    # fast instead of after minutes of video transfer.
    thumb_path: Path | None = None
    if body.thumbnail_asset_id.strip():
        thumb_path = await _resolve_asset_path(body.thumbnail_asset_id.strip(), "image")

    try:
        video_id = await asyncio.wait_for(
            asyncio.to_thread(
                yt.upload_video_sync,
                path,
                title=body.title.strip(),
                description=body.description.strip(),
                privacy_status=body.privacy_status,
            ),
            timeout=600.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="YouTube upload timed out after 10 minutes")
    except yt.YouTubeNotConnected as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception("YouTube upload failed for asset %s", body.asset_id)
        raise HTTPException(status_code=502, detail=f"YouTube upload failed: {str(e)[:400]}")

    warning = ""
    if thumb_path is not None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(yt.set_thumbnail_sync, video_id, thumb_path),
                timeout=120.0,
            )
        except yt.YouTubeThumbnailRejected as e:
            warning = str(e)
        except Exception as e:
            logger.exception("YouTube thumbnail set failed for video %s", video_id)
            warning = f"thumbnail could not be set ({str(e)[:160]}) — set it manually in YouTube Studio"

    out = {"video_id": video_id, "watch_url": f"https://youtube.com/watch?v={video_id}"}
    if warning:
        out["warning"] = warning
    return out
