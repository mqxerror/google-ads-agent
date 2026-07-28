"""Demand Gen ad-image update — REST wrapper around the MCP orchestrator.

Lets the Studio "Push to campaign ad" action drive the SAME in-place image
refresh the chat agent / MCP tool (`demand_gen_update_ad_images`) uses — one
shared `DemandGenOrchestrator`, no duplicated logic. The reject-the-AI-creative
→ push-my-own-property-photos flow: replace or append the marketing / square /
portrait / tall / logo images on a live DemandGenMultiAssetAd, in place.

Mirrors app/routers/pmax.py (SDK-client lazy init, 422 for validation, 502 for
a Google API rejection).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from google_ads.services.campaign.demand_gen_orchestrator import (
    ApiCtx,
    DemandGenAdUpdateError,
    DemandGenOrchestrator,
    DemandGenValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["demand_gen"])

# One orchestrator per process (service clients cached inside it); stateless
# aside from those refs, so concurrent requests are safe.
_orchestrator = DemandGenOrchestrator()


def _ensure_sdk_client() -> None:
    """The google_ads SDK client is normally initialised by the MCP subprocess
    lifespan; the REST path runs in the FastAPI process, so lazily initialise
    from env (backend/.env is already loaded by app/mcp_server.py at import)."""
    from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client

    try:
        get_sdk_client()
    except Exception:
        set_sdk_client(GoogleAdsSdkClient())
        logger.info("Initialized Google Ads SDK client for the REST Demand Gen path")


class DemandGenUpdateImagesRequest(BaseModel):
    """Studio push-to-ad payload. All refs may be Google asset resource names,
    bare numeric asset ids, OR local library UUIDs (uploaded / generated) — the
    orchestrator uploads + crops local files to each slot's exact aspect."""

    # Target ad — either the resource name, or both ad_group_id + ad_id.
    ad_resource_name: Optional[str] = None
    ad_group_id: Optional[str] = None
    ad_id: Optional[str] = None
    mode: str = "replace"  # 'replace' | 'append'
    logos: List[str] = Field(default_factory=list)
    landscape_images: List[str] = Field(default_factory=list)
    square_images: List[str] = Field(default_factory=list)
    portrait_images: List[str] = Field(default_factory=list)
    tall_portrait_images: List[str] = Field(default_factory=list)


class DemandGenUpdateImagesResponse(BaseModel):
    ad_id: str
    ad_resource_name: str
    mode: str
    updated_slots: Dict[str, List[str]]
    field_mask: List[str]


@router.post(
    "/accounts/{account_id}/demand-gen/update-ad-images",
    response_model=DemandGenUpdateImagesResponse,
)
async def update_demand_gen_ad_images(
    account_id: str, body: DemandGenUpdateImagesRequest
) -> DemandGenUpdateImagesResponse:
    """Replace or append the image creatives on an existing Demand Gen ad.

    422 with a field-by-field error list when the payload is invalid; 502 when
    Google rejects the mutate (nothing changed live — safe to retry).
    """
    bundle: Dict[str, Any] = {
        "ad_resource_name": body.ad_resource_name,
        "ad_group_id": body.ad_group_id,
        "ad_id": body.ad_id,
        "mode": body.mode,
        "logos": body.logos,
        "marketing_images": {
            "landscape": body.landscape_images,
            "square": body.square_images,
            "portrait": body.portrait_images,
            "tall_portrait": body.tall_portrait_images,
        },
    }
    try:
        _ensure_sdk_client()
        result = await _orchestrator.update_ad_images(
            ctx=ApiCtx(), customer_id=account_id, bundle=bundle
        )
        return DemandGenUpdateImagesResponse(**result)
    except DemandGenValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_FAILED", "errors": e.errors},
        )
    except DemandGenAdUpdateError as e:
        logger.exception("Demand Gen image update failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e.message)[:800]},
        )
    except Exception as e:
        logger.exception("Demand Gen image update failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
