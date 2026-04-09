"""Account & campaign endpoints — real Google Ads data with SQLite caching."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

from app.models.schemas import (
    AccountResponse,
    AdGroupResponse,
    AdResponse,
    CampaignResponse,
    KeywordResponse,
)
from app.services.google_ads import GoogleAdsService
from app.services.cache import CacheService
from app.services.metrics_store import MetricsStore

router = APIRouter(prefix="/api", tags=["campaigns"])

_ads_svc = GoogleAdsService()
_cache = CacheService()
_metrics = MetricsStore()

# Cache TTLs (seconds)
_TTL_ACCOUNTS = 600       # 10 min — hierarchy rarely changes
_TTL_CAMPAIGNS = 300      # 5 min — default
_TTL_ADGROUPS = 300       # 5 min
_TTL_KEYWORDS = 300       # 5 min
_TTL_ADS = 600            # 10 min — ads change rarely
_TTL_TARGETING = 3600     # 1 hour — targeting almost never changes
_TTL_CHART = 600          # 10 min — daily metrics don't change often
_TTL_SEARCH_TERMS = 1800  # 30 min — expensive query


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts():
    return await _cache.get_or_fetch(
        "accounts:hierarchy",
        lambda: _ads_svc.get_accessible_accounts(),
        ttl=_TTL_ACCOUNTS,
    )


@router.get("/accounts/{account_id}/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    account_id: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    key = f"{account_id}:campaigns:{date_from}:{date_to}"
    return await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_campaigns(account_id, date_from, date_to),
        ttl=_TTL_CAMPAIGNS,
    )


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}",
    response_model=CampaignResponse,
)
async def get_campaign(
    account_id: str,
    campaign_id: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    campaigns = await list_campaigns(account_id, date_from, date_to)
    for c in campaigns:
        cid = c.id if isinstance(c, CampaignResponse) else c.get("id")
        if cid == campaign_id:
            return c
    raise HTTPException(status_code=404, detail="Campaign not found")


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}/adgroups",
    response_model=list[AdGroupResponse],
)
async def list_adgroups(account_id: str, campaign_id: str):
    key = f"{account_id}:{campaign_id}:adgroups"
    return await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_adgroups(account_id, campaign_id),
        ttl=_TTL_ADGROUPS,
    )


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}/keywords",
    response_model=list[KeywordResponse],
)
async def list_keywords(account_id: str, campaign_id: str):
    key = f"{account_id}:{campaign_id}:keywords"
    return await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_keywords(account_id, campaign_id),
        ttl=_TTL_KEYWORDS,
    )


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}/ads",
    response_model=list[AdResponse],
)
async def list_ads(account_id: str, campaign_id: str):
    key = f"{account_id}:{campaign_id}:ads"
    return await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_ads(account_id, campaign_id),
        ttl=_TTL_ADS,
    )


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/targeting")
async def get_targeting(account_id: str, campaign_id: str):
    key = f"{account_id}:{campaign_id}:targeting"
    return await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_campaign_targeting(account_id, campaign_id),
        ttl=_TTL_TARGETING,
    )


# ── V2: Chart Data ─────────────────────────────────────────────


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/chart")
async def campaign_chart_data(
    account_id: str,
    campaign_id: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """Daily metrics for a single campaign — also syncs to local metrics store."""
    key = f"{account_id}:{campaign_id}:chart:{date_from}:{date_to}"
    data = await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_daily_metrics(account_id, campaign_id, date_from, date_to),
        ttl=_TTL_CHART,
    )

    # Sync to local metrics store in background (fire and forget)
    try:
        await _metrics.sync_daily_metrics(account_id, data, campaign_id)
    except Exception:
        pass  # Don't fail the request if sync fails

    return data


@router.get("/accounts/{account_id}/chart")
async def account_chart_data(
    account_id: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """Daily metrics aggregated across all campaigns in an account."""
    key = f"{account_id}:chart:{date_from}:{date_to}"
    return await _cache.get_or_fetch(
        key,
        lambda: _ads_svc.get_account_daily_metrics(account_id, date_from, date_to),
        ttl=_TTL_CHART,
    )


# ── Cache management ───────────────────────────────────────────


@router.post("/accounts/{account_id}/cache/clear")
async def clear_account_cache(account_id: str):
    """Force-clear all cached data for an account. Use after making changes."""
    deleted = await _cache.invalidate(account_id)
    return {"cleared": deleted}


@router.post("/accounts/{account_id}/sync")
async def sync_metrics(account_id: str, days: int = Query(default=30, ge=1, le=90)):
    """Sync daily metrics from Google Ads API to local SQLite store.

    Call this once to populate historical data. Subsequent agent queries
    will read from local store (milliseconds) instead of API (seconds).
    """
    from datetime import date, timedelta

    date_from = (date.today() - timedelta(days=days - 1)).isoformat()
    date_to = date.today().isoformat()

    total_synced = 0
    try:
        # Get all campaigns
        campaigns = await _ads_svc.get_campaigns(account_id, date_from, date_to)

        # Sync each campaign's daily data
        for camp in campaigns:
            cid = camp.id if hasattr(camp, 'id') else camp.get('id', '')
            cname = camp.name if hasattr(camp, 'name') else camp.get('name', '')
            try:
                daily = await _ads_svc.get_daily_metrics(account_id, cid, date_from, date_to)
                synced = await _metrics.sync_daily_metrics(account_id, daily, cid, cname)
                total_synced += synced
            except Exception as e:
                logger.warning("Failed to sync campaign %s: %s", cid, e)

        return {"synced_rows": total_synced, "campaigns": len(campaigns), "days": days}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sync failed: {e}")
