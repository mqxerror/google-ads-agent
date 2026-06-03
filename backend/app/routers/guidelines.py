"""Guidelines CRUD endpoints + E7 (suggest edits via agent)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import (
    GuidelineContentResponse,
    GuidelineCreateRequest,
    GuidelineFileResponse,
    GuidelineSection,
    GuidelineUpdateRequest,
)
from app.services.guidelines import GuidelinesService
from app.services.guideline_optimizer import (
    apply_proposal,
    discard_proposal,
    list_proposals,
    suggest_guideline_edits,
)

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


# ── E7: Suggest edits ─────────────────────────────────────────────


class SuggestEditsRequest(BaseModel):
    account_id: str
    extra_focus: str | None = None


@router.post("/{filename}/suggest-edits")
async def suggest_edits(filename: str, body: SuggestEditsRequest) -> dict:
    """Run the optimizer once. Returns a pending proposal — does NOT modify the file."""
    return await suggest_guideline_edits(
        account_id=body.account_id,
        filename=filename,
        extra_focus=body.extra_focus,
    )


@router.get("/{filename}/proposals")
async def get_proposals(filename: str, account_id: str, status: str | None = None) -> list[dict]:
    """List recent proposals for this file (newest first)."""
    return await list_proposals(account_id=account_id, filename=filename, status=status)


@router.post("/{filename}/proposals/{proposal_id}/apply")
async def apply_proposal_endpoint(filename: str, proposal_id: str, account_id: str) -> dict:
    """Apply a previously-generated proposal. Refuses if the file changed in the meantime."""
    return await apply_proposal(account_id=account_id, proposal_id=proposal_id)


@router.post("/{filename}/proposals/{proposal_id}/discard")
async def discard_proposal_endpoint(filename: str, proposal_id: str, account_id: str) -> dict:
    """Mark a proposal as discarded (won't show in pending lists)."""
    return await discard_proposal(account_id=account_id, proposal_id=proposal_id)
