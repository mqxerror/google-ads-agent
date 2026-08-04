"""Responsive Display Ad creation — REST wrapper around the MCP orchestrator.

Lets the RdaWizard (the P5 thin shell) drive the SAME ``RdaOrchestrator`` the
chat agent / MCP tool (``rda_create_responsive_display_campaign``) uses — one
shared recipe, no duplicated logic. Mirrors app/routers/demand_gen.py (SDK-client
lazy init, 422 for validation, 502 for a Google API rejection).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from google_ads.services.campaign.rda_orchestrator import (
    ApiCtx,
    RdaOrchestrator,
    RdaStepError,
    RdaValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["rda"])

# One orchestrator per process (service clients cached inside it); stateless
# aside from those refs, so concurrent requests are safe.
_orchestrator = RdaOrchestrator()


def _ensure_sdk_client() -> None:
    """The google_ads SDK client is normally initialised by the MCP subprocess
    lifespan; the REST path runs in the FastAPI process, so lazily initialise
    from env (backend/.env is already loaded by app/mcp_server.py at import)."""
    from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client

    try:
        get_sdk_client()
    except Exception:
        set_sdk_client(GoogleAdsSdkClient())
        logger.info("Initialized Google Ads SDK client for the REST RDA path")


class RdaMarketingImages(BaseModel):
    """Marketing-image slots for the responsive display ad. All refs may be
    Google asset resource names, bare numeric asset ids, OR local library UUIDs
    (uploaded / generated) — the orchestrator uploads + crops local files to each
    slot's exact aspect at submit. RDA has landscape (1.91:1) + square (1:1)
    marketing images only (no portrait)."""

    landscape: List[str] = Field(default_factory=list)      # 1.91:1
    square: List[str] = Field(default_factory=list)         # 1:1


class RdaCreateRequest(BaseModel):
    """Wizard submit payload. Every field is validated server-side too — the
    wizard's client-side validation is a UX nicety; the orchestrator rejects
    anything that doesn't meet the RDA registry limits (≤5 headlines ≤30c,
    EXACTLY 1 long headline ≤90c, ≤5 descriptions ≤90c, business_name ≤25c, ≥1
    landscape + ≥1 square marketing image, ≥1 logo)."""

    name: str
    budget_micros: int
    final_urls: List[str]
    business_name: str
    headlines: List[str]
    long_headlines: List[str]
    descriptions: List[str]
    logos: List[str] = Field(default_factory=list)
    landscape_logos: List[str] = Field(default_factory=list)   # optional 4:1
    marketing_images: RdaMarketingImages = Field(default_factory=RdaMarketingImages)
    call_to_action_text: Optional[str] = None
    target_cpa_micros: Optional[int] = None
    location_ids: Optional[List[str]] = None
    excluded_location_ids: Optional[List[str]] = None
    language_ids: Optional[List[str]] = None
    final_mobile_urls: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class RdaCreateResponse(BaseModel):
    campaign_id: str
    budget_id: str
    ad_group_id: str
    ad_id: str
    asset_ids: Dict[str, List[str]]
    warnings: List[str] = Field(default_factory=list)


@router.post(
    "/accounts/{account_id}/campaigns/rda",
    response_model=RdaCreateResponse,
)
async def create_rda(account_id: str, body: RdaCreateRequest) -> RdaCreateResponse:
    """Create a Responsive Display Ad campaign (PAUSED) from the wizard's bundle.

    Mirrors app/routers/demand_gen.py::create_demand_gen — the RdaWizard thin
    shell and the chat agent both drive the SAME ``RdaOrchestrator``.

    Returns 422 with a field-by-field error list when the RDA limits aren't met;
    502 when a Google Ads call fails mid-recipe (the orchestrator has already
    rolled back the prior creations, so a retry is safe).
    """
    bundle: Dict[str, Any] = {
        "name": body.name,
        "budget_micros": body.budget_micros,
        "final_urls": body.final_urls,
        "final_mobile_urls": body.final_mobile_urls,
        "business_name": body.business_name,
        "headlines": body.headlines,
        "long_headlines": body.long_headlines,
        "descriptions": body.descriptions,
        "call_to_action_text": body.call_to_action_text,
        "logos": body.logos,
        "landscape_logos": body.landscape_logos,
        "marketing_images": {
            "landscape": body.marketing_images.landscape,
            "square": body.marketing_images.square,
        },
        "target_cpa_micros": body.target_cpa_micros,
        "location_ids": body.location_ids,
        "excluded_location_ids": body.excluded_location_ids,
        "language_ids": body.language_ids,
        "start_date": body.start_date,
        "end_date": body.end_date,
    }
    try:
        _ensure_sdk_client()
        result = await _orchestrator.create_responsive_display_campaign(
            ctx=ApiCtx(),
            customer_id=account_id,
            bundle=bundle,
        )
        return RdaCreateResponse(**result)
    except RdaValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_FAILED", "errors": e.errors},
        )
    except RdaStepError as e:
        logger.exception(
            "RDA orchestrator failed for account=%s at step '%s'",
            account_id, e.step,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "GOOGLE_ADS_ERROR",
                "step": e.step,
                "rolled_back": e.rollback_report,
                "message": str(e)[:800],
            },
        )
    except Exception as e:
        logger.exception("RDA orchestrator failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
