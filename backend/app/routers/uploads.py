"""File upload endpoint — accepts files and clipboard images for chat attachments.

Files are stored in data/uploads/{conversation_id}/{uuid}_{filename}
The agent can read them via the Read tool when paths are passed in the prompt.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["uploads"])

_UPLOADS_DIR = settings.DATA_DIR / "uploads"
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file types — extend as needed
_ALLOWED_EXT = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
    # Documents
    ".pdf", ".txt", ".md", ".csv", ".json", ".xml", ".html",
    ".doc", ".docx", ".xls", ".xlsx",
    # Code/data
    ".js", ".ts", ".tsx", ".jsx", ".py", ".rb", ".go", ".rs",
    ".yaml", ".yml", ".toml", ".sql",
}

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _safe_filename(name: str) -> str:
    """Sanitize filename for safe filesystem storage."""
    name = re.sub(r'[^\w\.\-]', '_', name)
    return name[:200]


@router.post("/uploads")
async def upload_file(
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a file for the given conversation. Returns file metadata + path."""
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {', '.join(sorted(_ALLOWED_EXT))}",
        )

    # Read content with size limit
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File exceeds {_MAX_FILE_SIZE // (1024*1024)}MB limit")

    # Save to conversation-specific directory
    conv_dir = _UPLOADS_DIR / conversation_id
    conv_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    safe_name = _safe_filename(file.filename or f"upload{ext}")
    storage_name = f"{file_id}_{safe_name}"
    file_path = conv_dir / storage_name

    file_path.write_bytes(content)

    is_image = ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}

    logger.info("Uploaded file %s (%d bytes) to conversation %s", safe_name, len(content), conversation_id)

    return {
        "id": file_id,
        "filename": safe_name,
        "path": str(file_path),
        "size": len(content),
        "ext": ext,
        "is_image": is_image,
        "url": f"/api/uploads/{conversation_id}/{storage_name}",
    }


@router.get("/uploads/{conversation_id}/{filename}")
async def get_upload(conversation_id: str, filename: str):
    """Serve an uploaded file (for preview in the UI)."""
    # Sanitize to prevent path traversal
    safe_name = _safe_filename(filename)
    file_path = _UPLOADS_DIR / conversation_id / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(file_path))


@router.delete("/uploads/{conversation_id}/{filename}")
async def delete_upload(conversation_id: str, filename: str):
    """Delete an uploaded file."""
    safe_name = _safe_filename(filename)
    file_path = _UPLOADS_DIR / conversation_id / safe_name

    if file_path.exists():
        file_path.unlink()
        return {"deleted": True}
    return {"deleted": False}
