"""Targeting reference service — named languages + a live geo-target picker.

Backs the campaign wizards' Targeting step so operators pick *named* locations
and languages instead of typing raw numeric constant ids:

  - ``list_languages()`` — the bundled Google Ads language set (static data).
  - ``suggest_geo_targets()`` — live GeoTargetConstantService.suggest lookups
    ("Dubai" → the emirate + city, named). READ-ONLY, no mutation.
  - ``resolve_geo_targets()`` — id → name resolution so a saved draft (which
    stores only ids) can redisplay the chosen locations by name.

Reuses the app-layer SDK client (``app.services.google_ads._build_client``) — the
same lazily-cached ``GoogleAdsClient`` the REST read endpoints use — so there is
no dependency on the MCP subprocess / FastMCP ``Context``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.data.google_ads_languages import get_languages
from app.services.google_ads import _build_client, _clean_id, _run_query

logger = logging.getLogger(__name__)


def list_languages() -> List[Dict[str, str]]:
    """Return the bundled Google Ads language constants (English first)."""
    return get_languages()


def _suggest_geo_targets_sync(
    query: str, country_code: Optional[str], limit: int
) -> List[Dict[str, Any]]:
    client = _build_client()
    service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = "en"
    request.location_names.names.extend([query])
    if country_code:
        request.country_code = country_code

    response = service.suggest_geo_target_constants(request=request)

    out: List[Dict[str, Any]] = []
    for suggestion in response.geo_target_constant_suggestions:
        g = suggestion.geo_target_constant
        out.append(
            {
                "id": str(g.id),
                "name": g.name,
                "canonical_name": g.canonical_name,
                "target_type": g.target_type,
                "country_code": g.country_code,
                "reach": suggestion.reach,
            }
        )
    # Highest-reach first so the most relevant (broadest) targets surface at the
    # top of the picker; cap to keep the dropdown tight.
    out.sort(key=lambda r: r.get("reach") or 0, reverse=True)
    return out[:limit]


async def suggest_geo_targets(
    query: str,
    country_code: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Suggest named geo target constants for a free-text query (read-only)."""
    if not query or not query.strip():
        return []
    return await asyncio.to_thread(
        _suggest_geo_targets_sync, query.strip(), country_code, limit
    )


def _resolve_geo_targets_sync(ids: List[str]) -> List[Dict[str, Any]]:
    in_clause = ", ".join(ids)
    query = f"""
        SELECT geo_target_constant.id,
               geo_target_constant.name,
               geo_target_constant.canonical_name,
               geo_target_constant.target_type,
               geo_target_constant.country_code
        FROM geo_target_constant
        WHERE geo_target_constant.id IN ({in_clause})
    """
    # geo_target_constant is account-independent, but the query still needs a
    # customer context — use the login (manager) customer id.
    login = _clean_id(settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
    rows = _run_query(login, query)
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        g = r.geo_target_constant
        by_id[str(g.id)] = {
            "id": str(g.id),
            "name": g.name,
            "canonical_name": g.canonical_name,
            "target_type": g.target_type,
            "country_code": g.country_code,
        }
    # Preserve caller order; fall back to a bare-id echo for anything Google
    # doesn't recognise so the picker never silently drops a chip.
    return [by_id.get(i, {"id": i, "name": i, "canonical_name": i}) for i in ids]


async def resolve_geo_targets(ids: List[str]) -> List[Dict[str, Any]]:
    """Resolve geo target constant ids to their names (read-only)."""
    clean = [str(i).strip() for i in ids if str(i).strip().isdigit()]
    if not clean:
        return []
    return await asyncio.to_thread(_resolve_geo_targets_sync, clean)
