"""Pause-confirmation endpoint (working-campaign pause protection).

The ONLY way a working campaign's PAUSE/REMOVE gets authorized: the UI confirm
card POSTs here, which mints a one-shot, short-TTL grant scoped to exactly one
(campaign_id, action). The MCP chokepoint (google_ads/mcp_main.py) then consumes
it once. Chat text never reaches this endpoint — only an explicit click does.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import pause_guard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["pause-guard"])


class PauseConfirmRequest(BaseModel):
    campaign_id: str
    action: str  # "PAUSED" | "REMOVED"
    customer_id: str | None = None
    campaign_name: str | None = None


@router.post("/pause-confirmations")
async def create_pause_confirmation(body: PauseConfirmRequest) -> dict:
    """Mint a one-shot confirmation grant that authorizes exactly one PAUSE/REMOVE
    of exactly one campaign. Returns the token + expiry. The grant is consumed by
    the MCP middleware on the very next matching status write, then discarded."""
    action = (body.action or "").strip().upper()
    if action not in pause_guard.PAUSE_REMOVE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"action must be one of {sorted(pause_guard.PAUSE_REMOVE_STATUSES)}",
        )
    if not (body.campaign_id or "").strip():
        raise HTTPException(status_code=400, detail="campaign_id is required")
    grant = pause_guard.mint_grant(
        customer_id=body.customer_id or "",
        campaign_id=body.campaign_id,
        action=action,
        campaign_name=body.campaign_name,
    )
    logger.info(
        "Minted pause-confirmation grant for campaign %s action %s (expires %s)",
        body.campaign_id, action, grant.get("expires_at"),
    )
    return grant
