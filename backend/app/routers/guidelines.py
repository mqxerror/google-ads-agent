"""Guidelines CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    GuidelineContentResponse,
    GuidelineCreateRequest,
    GuidelineFileResponse,
    GuidelineSection,
    GuidelineUpdateRequest,
)
from app.services.guidelines import GuidelinesService

router = APIRouter(prefix="/api/guidelines", tags=["guidelines"])

_svc = GuidelinesService()


@router.get("", response_model=list[GuidelineFileResponse])
async def list_guidelines() -> list[GuidelineFileResponse]:
    """List all .md guideline files."""
    return _svc.list_files()


@router.get("/{filename}", response_model=GuidelineContentResponse)
async def get_guideline(filename: str) -> GuidelineContentResponse:
    """Read a single guideline file."""
    try:
        return _svc.read_file(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@router.put("/{filename}", response_model=GuidelineContentResponse)
async def update_guideline(
    filename: str, body: GuidelineUpdateRequest
) -> GuidelineContentResponse:
    """Overwrite a guideline file (atomic write)."""
    try:
        return _svc.write_file(filename, body.content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@router.post("", response_model=GuidelineContentResponse, status_code=201)
async def create_guideline(body: GuidelineCreateRequest) -> GuidelineContentResponse:
    """Create a new guideline file from the built-in template."""
    try:
        return _svc.create_file(
            filename=body.filename,
            campaign_id=body.campaign_id,
            campaign_name=body.campaign_name,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{filename}/sections", response_model=list[GuidelineSection])
async def list_sections(filename: str) -> list[GuidelineSection]:
    """List sections found in the guideline file."""
    try:
        result = _svc.read_file(filename)
        return result.sections
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
