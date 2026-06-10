"""PMax campaign creation — REST wrapper around the MCP orchestrator.

This endpoint exists so the visual wizard (PMaxWizard.tsx) can drive
the same flow the chat agent uses via MCP. Both surfaces call the
identical PMaxOrchestrator instance — no duplicated logic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from google_ads.services.campaign.pmax_orchestrator import (
    ApiCtx,
    PMaxOrchestrator,
    PMaxStepError,
    PMaxValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["pmax"])

# One orchestrator per process — primitive service clients are cached
# inside it. The orchestrator is stateless aside from those service
# refs, so concurrent requests are safe.
_orchestrator = PMaxOrchestrator()


def _ensure_sdk_client() -> None:
    """The google_ads SDK client is normally initialised by the MCP
    subprocess's lifespan (mcp_main.py). The REST wizard path runs in the
    FastAPI process, which never called set_sdk_client — so the first live
    submit failed with 'SDK client not initialized'. Lazily initialise from
    env here (backend/.env is already loaded into os.environ by
    app/mcp_server.py's load_dotenv at import time)."""
    from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client

    try:
        get_sdk_client()
    except Exception:
        set_sdk_client(GoogleAdsSdkClient())
        logger.info("Initialized Google Ads SDK client for the REST PMax path")


class PMaxMarketingImages(BaseModel):
    landscape: List[str] = Field(default_factory=list)
    square: List[str] = Field(default_factory=list)
    portrait: List[str] = Field(default_factory=list)


class PMaxCreateRequest(BaseModel):
    """Wizard submit payload. All fields validated server-side too —
    the wizard's client-side validation is a UX nicety; the orchestrator
    rejects anything that doesn't meet Google's hard minimums."""

    name: str
    budget_micros: int
    final_urls: List[str]
    business_name: str
    headlines: List[str]
    long_headlines: List[str]
    descriptions: List[str]
    logos: List[str] = Field(default_factory=list)
    marketing_images: PMaxMarketingImages = Field(default_factory=PMaxMarketingImages)
    video_youtube_ids: List[str]
    audience_signals: Optional[List[Dict[str, Any]]] = None
    final_mobile_urls: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PMaxCreateResponse(BaseModel):
    campaign_id: str
    budget_id: str
    asset_group_id: str
    asset_ids: Dict[str, List[str]]
    warnings: List[str] = Field(default_factory=list)


@router.post(
    "/accounts/{account_id}/campaigns/pmax",
    response_model=PMaxCreateResponse,
)
async def create_pmax(account_id: str, body: PMaxCreateRequest) -> PMaxCreateResponse:
    """Create a Performance Max campaign from the wizard's bundle.

    Returns 422 (Unprocessable Entity) with field-by-field error list
    when Google's hard minimums aren't met. Returns 502 (Bad Gateway)
    when the Google Ads API itself rejects the create — the prior
    campaign + budget have already been rolled back by the orchestrator
    at this point, so a retry is safe.
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
        "logos": body.logos,
        "marketing_images": {
            "landscape": body.marketing_images.landscape,
            "square": body.marketing_images.square,
            "portrait": body.marketing_images.portrait,
        },
        "video_youtube_ids": body.video_youtube_ids,
        "audience_signals": body.audience_signals,
        "start_date": body.start_date,
        "end_date": body.end_date,
    }
    try:
        _ensure_sdk_client()
        result = await _orchestrator.create_pmax_campaign(
            ctx=ApiCtx(),
            customer_id=account_id,
            bundle=bundle,
        )
        return PMaxCreateResponse(**result)
    except PMaxValidationError as e:
        # 422 = the standard "your payload is invalid" code; structured
        # errors so the wizard can highlight the offending fields.
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_FAILED", "errors": e.errors},
        )
    except PMaxStepError as e:
        logger.exception(
            "PMax orchestrator failed for account=%s at step '%s'",
            account_id, e.step,
        )
        # 502 — a Google Ads call failed mid-recipe. The orchestrator
        # already rolled back; `message` is the full self-contained
        # story (step + cleanup + underlying error) so the wizard can
        # show it verbatim, with `step`/`rolled_back` available for
        # richer UI treatment later.
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
        logger.exception("PMax orchestrator failed for account=%s", account_id)
        # 502 — the upstream Google Ads call failed. Rollback already
        # happened inside the orchestrator.
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
