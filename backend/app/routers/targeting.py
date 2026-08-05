"""Targeting reference endpoints for the campaign wizards.

Serves the named-language set and a live, named geo-target picker so the wizard
Targeting step never asks operators to type raw numeric constant ids:

  GET /api/targeting/languages          → bundled Google Ads language set
  GET /api/targeting/geo/suggest?q=...   → live suggest ("Dubai" → emirate+city)
  GET /api/targeting/geo/resolve?ids=... → id → name (redisplay a saved draft)

All read-only. Suggest/resolve lazily init the SDK client (the MCP subprocess
normally owns it; this runs in the FastAPI process). Mirrors the pmax/demand_gen
routers' lazy-init + 502-on-Google-failure shape.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import targeting as targeting_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/targeting", tags=["targeting"])


def _ensure_sdk_client() -> None:
    """Lazily initialise the google_ads SDK client for the REST process."""
    from google_ads.sdk_client import (
        GoogleAdsSdkClient,
        get_sdk_client,
        set_sdk_client,
    )

    try:
        get_sdk_client()
    except Exception:
        set_sdk_client(GoogleAdsSdkClient())
        logger.info("Initialized Google Ads SDK client for the REST targeting path")


class Language(BaseModel):
    id: str
    name: str
    code: str


class GeoTarget(BaseModel):
    id: str
    name: str
    canonical_name: Optional[str] = None
    target_type: Optional[str] = None
    country_code: Optional[str] = None
    reach: Optional[int] = None


@router.get("/languages", response_model=List[Language])
async def list_languages() -> List[Language]:
    """The bundled Google Ads language constants (English/1000 first).

    Static data — no Google API call — so the wizard renders instantly.
    """
    return [Language(**lang) for lang in targeting_service.list_languages()]


@router.get("/geo/suggest", response_model=List[GeoTarget])
async def suggest_geo(
    q: str = Query(..., min_length=1, description="Free-text location query"),
    country_code: Optional[str] = Query(
        None, description="Optional 2-letter country filter, e.g. AE"
    ),
    limit: int = Query(20, ge=1, le=50),
) -> List[GeoTarget]:
    """Suggest named geo target constants for a query (read-only)."""
    try:
        _ensure_sdk_client()
        results: List[Dict[str, Any]] = await targeting_service.suggest_geo_targets(
            query=q, country_code=country_code, limit=limit
        )
    except Exception as e:  # pragma: no cover - network/SDK failure path
        logger.exception("Geo suggest failed for query=%r", q)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
    return [GeoTarget(**r) for r in results]


@router.get("/geo/resolve", response_model=List[GeoTarget])
async def resolve_geo(
    ids: str = Query(..., description="Comma-separated geo target constant ids"),
) -> List[GeoTarget]:
    """Resolve geo target constant ids to their names (read-only)."""
    id_list = [s.strip() for s in ids.split(",") if s.strip()]
    if not id_list:
        return []
    try:
        _ensure_sdk_client()
        results: List[Dict[str, Any]] = await targeting_service.resolve_geo_targets(
            id_list
        )
    except Exception as e:  # pragma: no cover - network/SDK failure path
        logger.exception("Geo resolve failed for ids=%r", ids)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
    return [GeoTarget(**r) for r in results]
