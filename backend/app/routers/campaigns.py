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
    DecisionLogEntry,
    KeywordResponse,
    PinnedFactEntry,
    CampaignProfileUpdate,
)
from app.services.google_ads import GoogleAdsService
from app.services.cache import CacheService
from app.services.metrics_store import MetricsStore
from app.services import campaign_memory, campaigns_repo
from app.models.schemas import CampaignMetrics

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
    """Single source of truth: metadata from the `campaigns` table
    (auto-synced via `campaigns_repo`), metrics joined in from the
    `campaign_daily_metrics` table for the requested date range.

    The pre-V11 path went through a JSON blob in `cache`, which let the
    sidebar drift up to 5 min and disagree silently with the agent's
    view. That path is gone; everything reads here now.
    """
    rows = await campaigns_repo.list_campaigns(account_id)

    # Aggregate metrics from campaign_daily_metrics for the date range.
    # Per-campaign sums; if no rows exist for a campaign in the window
    # the metrics simply come back as zeros and the response stays
    # shape-compatible with what the sidebar / overview expect.
    from app.database import get_db
    metrics_map: dict[str, dict] = {}
    if rows:
        cids = [str(r["campaign_id"]) for r in rows]
        placeholders = ",".join("?" for _ in cids)
        params: list = [account_id, *cids]
        where_date = ""
        if date_from:
            where_date += " AND date >= ?"
            params.append(date_from)
        if date_to:
            where_date += " AND date <= ?"
            params.append(date_to)
        db = await get_db()
        try:
            cur = await db.execute(
                f"""SELECT campaign_id,
                          COALESCE(SUM(impressions), 0)   AS impressions,
                          COALESCE(SUM(clicks), 0)        AS clicks,
                          COALESCE(SUM(cost_micros), 0)   AS cost_micros,
                          COALESCE(SUM(conversions), 0.0) AS conversions
                   FROM campaign_daily_metrics
                   WHERE account_id = ? AND campaign_id IN ({placeholders})
                   {where_date}
                   GROUP BY campaign_id""",
                params,
            )
            for m in await cur.fetchall():
                cid = str(m["campaign_id"])
                imp = m["impressions"] or 0
                clk = m["clicks"] or 0
                metrics_map[cid] = {
                    "impressions": imp,
                    "clicks": clk,
                    "cost_micros": m["cost_micros"] or 0,
                    "conversions": float(m["conversions"] or 0),
                    "ctr": (clk / imp * 100) if imp else 0.0,
                    "avg_cpc_micros": int((m["cost_micros"] or 0) / clk) if clk else 0,
                }
        finally:
            await db.close()

    out: list[CampaignResponse] = []
    for r in rows:
        cid = str(r["campaign_id"])
        out.append(CampaignResponse(
            id=cid,
            name=r.get("name") or "",
            status=r.get("status") or "ENABLED",
            campaign_type=r.get("channel") or "SEARCH",
            budget_micros=r.get("budget_micros") or 0,
            bidding_strategy=r.get("bidding_strategy") or "",
            metrics=CampaignMetrics(**metrics_map.get(cid, {})),
        ))
    return out


@router.get("/accounts/{account_id}/campaigns-sync-status")
async def campaigns_sync_status(account_id: str):
    """Surface the campaigns table's last sync timestamp so the sidebar
    can show 'last synced X ago' (Story 4 UX). No more invisible TTLs."""
    return {
        "account_id": account_id,
        "last_synced_at": await campaigns_repo.last_synced_at(account_id),
        "stale_after_seconds": campaigns_repo.STALE_AFTER_SECONDS,
    }


@router.post("/accounts/{account_id}/sync/campaigns")
async def force_sync_campaigns(account_id: str):
    """Explicit refresh — bypasses the staleness check. Wired to the
    sidebar's refresh button so the user can always force a real read."""
    n = await campaigns_repo.sync_campaigns(account_id)
    return {
        "account_id": account_id,
        "synced": n,
        "last_synced_at": await campaigns_repo.last_synced_at(account_id),
    }


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


# ── Campaign Memory endpoints ──────────────────────────────────


@router.post("/accounts/{account_id}/campaigns/{campaign_id}/memory/init")
async def init_memory(account_id: str, campaign_id: str, campaign_name: str = "Campaign"):
    path = campaign_memory.init_campaign_memory(account_id, campaign_id, campaign_name)
    return {"status": "initialized", "path": str(path)}


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/memory")
async def get_campaign_memory_context(account_id: str, campaign_id: str, role: str | None = None):
    context = campaign_memory.build_campaign_context(account_id, campaign_id, active_role=role)
    return {"context": context}


@router.post("/accounts/{account_id}/campaigns/{campaign_id}/memory/decisions")
async def add_decision(account_id: str, campaign_id: str, body: DecisionLogEntry):
    campaign_memory.append_decision(account_id, campaign_id, action=body.action, reason=body.reason, outcome=body.outcome, role=body.role)
    return {"status": "logged"}


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/memory/pinned")
async def get_pinned_facts(account_id: str, campaign_id: str):
    return {"pinned_facts": campaign_memory.load_pinned_facts(account_id, campaign_id)}


@router.post("/accounts/{account_id}/campaigns/{campaign_id}/memory/pinned")
async def add_pinned_fact(account_id: str, campaign_id: str, body: PinnedFactEntry):
    campaign_memory.add_pinned_fact(account_id, campaign_id, fact=body.fact, source=body.source)
    return {"status": "pinned"}


@router.delete("/accounts/{account_id}/campaigns/{campaign_id}/memory/pinned-facts/{fact_index}")
async def delete_pinned_fact(account_id: str, campaign_id: str, fact_index: int):
    """Delete a pinned fact by its index (0-based)."""
    from app.config import settings
    path = settings.MEMORY_DIR / account_id / campaign_id / "pinned_facts.md"
    if not path.exists():
        return {"status": "not_found"}
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    # Find fact lines (start with "- **")
    fact_lines = [(i, l) for i, l in enumerate(lines) if l.strip().startswith("- **")]
    if fact_index < 0 or fact_index >= len(fact_lines):
        return {"status": "invalid_index"}
    # Remove the line
    line_num = fact_lines[fact_index][0]
    lines.pop(line_num)
    path.write_text("\n".join(lines), encoding="utf-8")
    return {"status": "deleted", "remaining": len(fact_lines) - 1}


@router.put("/accounts/{account_id}/campaigns/{campaign_id}/memory/profile")
async def update_campaign_profile(account_id: str, campaign_id: str, body: CampaignProfileUpdate):
    campaign_memory.update_profile(account_id, campaign_id, campaign_name=body.campaign_name, goals=body.goals, constraints=body.constraints, phase=body.phase)
    return {"status": "updated"}
