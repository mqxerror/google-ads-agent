"""Landing Page Analyzer endpoints — read/write CRO analysis from campaign memory.

Analysis is performed by the CRO Specialist agent in chat using Chrome MCP tools.
This router just reads/writes the structured results stored in
data/memory/{account_id}/{campaign_id}/role_notes/cro_specialist.md
"""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import campaign_memory

router = APIRouter(prefix="/api", tags=["landing-page"])


class LandingPageAnalysisSave(BaseModel):
    content: str


def _parse_structured_data(markdown: str) -> dict[str, Any] | None:
    """Extract JSON block between STRUCTURED_DATA_START and STRUCTURED_DATA_END markers."""
    if not markdown:
        return None
    pattern = re.compile(
        r'<!-- STRUCTURED_DATA_START -->\s*```json\s*(\{.*?\})\s*```\s*<!-- STRUCTURED_DATA_END -->',
        re.DOTALL,
    )
    match = pattern.search(markdown)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: try to find any JSON object in the markdown
    json_pattern = re.compile(r'```json\s*(\{[\s\S]*?\})\s*```')
    json_match = json_pattern.search(markdown)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    return None


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/landing-page/analysis")
async def get_landing_page_analysis(account_id: str, campaign_id: str):
    """Read the CRO analysis from cro_specialist role notes."""
    raw = campaign_memory.load_role_notes(account_id, campaign_id, "cro_specialist")
    if not raw:
        return {"analysis": None, "raw_markdown": "", "has_data": False}

    analysis = _parse_structured_data(raw)
    return {
        "analysis": analysis,
        "raw_markdown": raw,
        "has_data": bool(raw),
    }


@router.post("/accounts/{account_id}/campaigns/{campaign_id}/landing-page/analysis")
async def save_landing_page_analysis(
    account_id: str,
    campaign_id: str,
    body: LandingPageAnalysisSave,
):
    """Save CRO analysis to cro_specialist role notes."""
    campaign_memory.save_role_notes(account_id, campaign_id, "cro_specialist", body.content)
    return {"status": "saved"}


@router.delete("/accounts/{account_id}/campaigns/{campaign_id}/landing-page/analysis")
async def clear_landing_page_analysis(account_id: str, campaign_id: str):
    """Clear the CRO analysis (delete the role notes file)."""
    from pathlib import Path
    from app.config import settings
    notes_file = settings.MEMORY_DIR / account_id / campaign_id / "role_notes" / "cro_specialist.md"
    if notes_file.exists():
        notes_file.unlink()
        return {"deleted": True}
    return {"deleted": False}
