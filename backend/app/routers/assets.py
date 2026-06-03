"""Ad asset library — list, upload, delete, attach.

The Studio page is the UI over this: it lists all generated videos + uploaded
images/clips, and feeds them into the PMax/Video campaign wizards later.
"""

from __future__ import annotations

import logging
import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])

ASSETS_DIR = settings.DATA_DIR / "ad_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed types for uploads — narrow set to avoid surprises
ALLOWED_EXT = {
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".mp3": "audio",
    ".wav": "audio",
}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


class AssetResponse(BaseModel):
    id: str
    account_id: Optional[str] = None
    campaign_id: Optional[str] = None
    type: str
    filename: str
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    size_bytes: Optional[int] = None
    script: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source: str
    voice_id: Optional[str] = None
    avatar_id: Optional[str] = None
    created_at: str


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    account_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    asset_type: Optional[str] = None,
    source: Optional[str] = None,            # "uploaded" | "generated"
    q: Optional[str] = None,
    limit: int = 100,
):
    """List assets, newest first. All filters are optional."""
    where: list[str] = []
    params: list = []
    if account_id:
        where.append("account_id = ?")
        params.append(account_id)
    if campaign_id:
        where.append("campaign_id = ?")
        params.append(campaign_id)
    if asset_type:
        where.append("type = ?")
        params.append(asset_type)
    if source:
        where.append("source = ?")
        params.append(source)
    if q:
        where.append("(filename LIKE ? OR script LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    sql = "SELECT * FROM ad_assets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    db = await get_db()
    try:
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return [AssetResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@router.post("/upload", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    account_id: Optional[str] = Form(None),
    campaign_id: Optional[str] = Form(None),
):
    """Upload an existing media file and add it to the library."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported extension {ext}; allowed: {sorted(ALLOWED_EXT)}",
        )
    asset_type = ALLOWED_EXT[ext]
    asset_id = str(uuid.uuid4())
    stored_name = f"{asset_id}{ext}"
    dest = ASSETS_DIR / stored_name

    total = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1 << 20):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="file too large (>200MB)")
            out.write(chunk)

    public_url = f"/api/assets/file/{stored_name}"

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets (id, account_id, campaign_id, type, filename, url, size_bytes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'uploaded')""",
            (asset_id, account_id, campaign_id, asset_type, file.filename, public_url, total),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM ad_assets WHERE id = ?", (asset_id,))
        row = await cur.fetchone()
        return AssetResponse(**dict(row))
    finally:
        await db.close()


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str):
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM ad_assets WHERE id = ?", (asset_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")

        # Best-effort file removal — DB row is the source of truth so keep going
        # even if the blob is already gone.
        url = row["url"] or ""
        if url.startswith("/api/assets/file/"):
            fname = url.rsplit("/", 1)[-1]
            (ASSETS_DIR / fname).unlink(missing_ok=True)
        elif url.startswith("/api/video/assets/"):
            fname = url.rsplit("/", 1)[-1]
            (ASSETS_DIR / fname).unlink(missing_ok=True)

        await db.execute("DELETE FROM ad_assets WHERE id = ?", (asset_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.get("/file/{filename}")
async def serve_asset_file(filename: str):
    """Serve an uploaded or generated media file."""
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    path = ASSETS_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    mime, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=mime or "application/octet-stream", filename=filename)


# Helper — called from the video router when a render completes so the asset
# automatically shows up in the Studio library.
async def record_generated_video(
    *,
    video_id: str,
    filename: str,
    url: str,
    script: str,
    account_id: Optional[str],
    campaign_id: Optional[str],
    voice_id: Optional[str],
    avatar_id: Optional[str],
    width: Optional[int],
    height: Optional[int],
    duration: Optional[float],
    thumbnail_url: Optional[str],
    size_bytes: Optional[int],
) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets
               (id, account_id, campaign_id, type, filename, url, width, height, duration, size_bytes,
                script, thumbnail_url, source, voice_id, avatar_id)
               VALUES (?, ?, ?, 'video', ?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?, ?)""",
            (video_id, account_id, campaign_id, filename, url, width, height, duration, size_bytes,
             script, thumbnail_url, voice_id, avatar_id),
        )
        await db.commit()
    finally:
        await db.close()
