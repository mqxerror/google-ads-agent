"""Google Ads API service — real data via google-ads SDK."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from functools import lru_cache

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from app.config import settings
from app.models.schemas import (
    AccountResponse,
    AdGroupResponse,
    AdResponse,
    CampaignMetrics,
    CampaignResponse,
    KeywordResponse,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _build_client() -> GoogleAdsClient:
    config = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
        "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)


def _clean_id(customer_id: str) -> str:
    return customer_id.replace("-", "")


def _default_dates(
    date_from: str | None, date_to: str | None
) -> tuple[str, str]:
    if not date_to:
        date_to = date.today().isoformat()
    if not date_from:
        date_from = (date.today() - timedelta(days=29)).isoformat()
    return date_from, date_to


def _run_query(customer_id: str, query: str) -> list:
    client = _build_client()
    service = client.get_service("GoogleAdsService")
    cid = _clean_id(customer_id)
    rows = []
    try:
        stream = service.search_stream(customer_id=cid, query=query)
        for batch in stream:
            for row in batch.results:
                rows.append(row)
    except GoogleAdsException as ex:
        logger.error("Google Ads API error for %s: %s", cid, ex)
        raise
    return rows


class GoogleAdsService:

    # ── accounts ─────────────────────────────────────────────────

    async def get_accessible_accounts(self) -> list[AccountResponse]:
        login_cid = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
        query = """
            SELECT
              customer_client.id,
              customer_client.descriptive_name,
              customer_client.manager,
              customer_client.level
            FROM customer_client
            ORDER BY customer_client.level
        """
        rows = await asyncio.to_thread(_run_query, login_cid, query)
        accounts: list[AccountResponse] = []
        for row in rows:
            cc = row.customer_client
            if cc.level == 0:
                level = "manager"
            elif cc.manager:
                level = "sub_manager"
            else:
                level = "client"
            accounts.append(
                AccountResponse(
                    id=str(cc.id),
                    name=cc.descriptive_name or f"Account {cc.id}",
                    parent_id=login_cid if cc.level > 0 else None,
                    level=level,
                    is_active=True,
                )
            )
        return accounts

    # ── campaigns ────────────────────────────────────────────────

    async def get_campaigns(
        self,
        customer_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[CampaignResponse]:
        d_from, d_to = _default_dates(date_from, date_to)
        query = f"""
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.advertising_channel_type,
              campaign_budget.amount_micros,
              campaign.bidding_strategy_type,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.ctr
            FROM campaign
            WHERE campaign.status != 'REMOVED'
              AND segments.date BETWEEN '{d_from}' AND '{d_to}'
            ORDER BY campaign.name
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        agg: dict[int, dict] = {}
        for row in rows:
            cid = row.campaign.id
            if cid not in agg:
                agg[cid] = {
                    "id": str(cid),
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                    "campaign_type": row.campaign.advertising_channel_type.name,
                    "budget_micros": row.campaign_budget.amount_micros,
                    "bidding_strategy": row.campaign.bidding_strategy_type.name,
                    "impressions": 0,
                    "clicks": 0,
                    "cost_micros": 0,
                    "conversions": 0.0,
                }
            a = agg[cid]
            a["impressions"] += row.metrics.impressions
            a["clicks"] += row.metrics.clicks
            a["cost_micros"] += row.metrics.cost_micros
            a["conversions"] += row.metrics.conversions

        result: list[CampaignResponse] = []
        for a in agg.values():
            clicks = a["clicks"]
            impressions = a["impressions"]
            ctr = (clicks / impressions * 100) if impressions > 0 else 0.0
            result.append(
                CampaignResponse(
                    id=a["id"],
                    name=a["name"],
                    status=a["status"],
                    campaign_type=a["campaign_type"],
                    budget_micros=a["budget_micros"],
                    bidding_strategy=a["bidding_strategy"],
                    metrics=CampaignMetrics(
                        impressions=a["impressions"],
                        clicks=a["clicks"],
                        cost_micros=a["cost_micros"],
                        conversions=a["conversions"],
                        ctr=ctr,
                        avg_cpc_micros=(
                            a["cost_micros"] // clicks if clicks > 0 else 0
                        ),
                    ),
                )
            )
        return result

    # ── daily metrics (for charts) ──────────────────────────────

    async def get_daily_metrics(
        self,
        customer_id: str,
        campaign_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """Get day-by-day metrics for a single campaign. Returns list of dicts."""
        d_from, d_to = _default_dates(date_from, date_to)
        query = f"""
            SELECT
              segments.date,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.ctr
            FROM campaign
            WHERE campaign.id = {campaign_id}
              AND segments.date BETWEEN '{d_from}' AND '{d_to}'
            ORDER BY segments.date
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        result = []
        for r in rows:
            cost = r.metrics.cost_micros / 1_000_000
            clicks = r.metrics.clicks
            conversions = r.metrics.conversions
            result.append({
                "date": str(r.segments.date),
                "impressions": r.metrics.impressions,
                "clicks": clicks,
                "cost": round(cost, 2),
                "conversions": round(conversions, 1),
                "ctr": round(r.metrics.ctr * 100, 2) if r.metrics.ctr else 0,
                "cpc": round(cost / clicks, 2) if clicks > 0 else 0,
                "cpa": round(cost / conversions, 2) if conversions > 0 else 0,
            })
        return result

    async def get_account_daily_metrics(
        self,
        customer_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """Get day-by-day metrics aggregated across all campaigns in account."""
        d_from, d_to = _default_dates(date_from, date_to)
        query = f"""
            SELECT
              segments.date,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM campaign
            WHERE campaign.status != 'REMOVED'
              AND segments.date BETWEEN '{d_from}' AND '{d_to}'
            ORDER BY segments.date
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        # Aggregate by date
        agg: dict[str, dict] = {}
        for r in rows:
            d = str(r.segments.date)
            if d not in agg:
                agg[d] = {"date": d, "impressions": 0, "clicks": 0, "cost_micros": 0, "conversions": 0.0}
            agg[d]["impressions"] += r.metrics.impressions
            agg[d]["clicks"] += r.metrics.clicks
            agg[d]["cost_micros"] += r.metrics.cost_micros
            agg[d]["conversions"] += r.metrics.conversions

        result = []
        for d in sorted(agg.keys()):
            a = agg[d]
            cost = a["cost_micros"] / 1_000_000
            clicks = a["clicks"]
            conversions = a["conversions"]
            result.append({
                "date": d,
                "impressions": a["impressions"],
                "clicks": clicks,
                "cost": round(cost, 2),
                "conversions": round(conversions, 1),
                "ctr": round(clicks / a["impressions"] * 100, 2) if a["impressions"] > 0 else 0,
                "cpc": round(cost / clicks, 2) if clicks > 0 else 0,
                "cpa": round(cost / conversions, 2) if conversions > 0 else 0,
            })
        return result

    # ── ad groups ────────────────────────────────────────────────

    async def get_adgroups(
        self, customer_id: str, campaign_id: str
    ) -> list[AdGroupResponse]:
        query = f"""
            SELECT
              ad_group.id,
              ad_group.name,
              ad_group.status,
              ad_group.cpc_bid_micros,
              campaign.id,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM ad_group
            WHERE campaign.id = {campaign_id}
              AND ad_group.status != 'REMOVED'
            ORDER BY ad_group.name
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        # Aggregate by ad_group.id (may have multiple date rows)
        agg: dict[int, dict] = {}
        for r in rows:
            agid = r.ad_group.id
            if agid not in agg:
                agg[agid] = {
                    "id": str(agid),
                    "name": r.ad_group.name,
                    "campaign_id": str(r.campaign.id),
                    "status": r.ad_group.status.name,
                    "cpc_bid_micros": r.ad_group.cpc_bid_micros,
                    "impressions": 0,
                    "clicks": 0,
                    "cost_micros": 0,
                    "conversions": 0.0,
                }
            a = agg[agid]
            a["impressions"] += r.metrics.impressions
            a["clicks"] += r.metrics.clicks
            a["cost_micros"] += r.metrics.cost_micros
            a["conversions"] += r.metrics.conversions

        return [
            AdGroupResponse(
                id=a["id"],
                name=a["name"],
                campaign_id=a["campaign_id"],
                status=a["status"],
                cpc_bid_micros=a["cpc_bid_micros"],
                metrics=CampaignMetrics(
                    impressions=a["impressions"],
                    clicks=a["clicks"],
                    cost_micros=a["cost_micros"],
                    conversions=a["conversions"],
                    ctr=(
                        a["clicks"] / a["impressions"] * 100
                        if a["impressions"] > 0
                        else 0.0
                    ),
                ),
            )
            for a in agg.values()
        ]

    # ── keywords ─────────────────────────────────────────────────

    async def get_keywords(
        self, customer_id: str, campaign_id: str
    ) -> list[KeywordResponse]:
        query = f"""
            SELECT
              ad_group_criterion.criterion_id,
              ad_group_criterion.keyword.text,
              ad_group_criterion.keyword.match_type,
              ad_group_criterion.status,
              ad_group_criterion.quality_info.quality_score,
              ad_group.id,
              ad_group.name,
              campaign.id,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM keyword_view
            WHERE campaign.id = {campaign_id}
              AND ad_group_criterion.status != 'REMOVED'
            ORDER BY metrics.impressions DESC
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        return [
            KeywordResponse(
                id=str(r.ad_group_criterion.criterion_id),
                text=r.ad_group_criterion.keyword.text,
                match_type=r.ad_group_criterion.keyword.match_type.name,
                ad_group_id=str(r.ad_group.id),
                ad_group_name=r.ad_group.name,
                campaign_id=str(r.campaign.id),
                status=r.ad_group_criterion.status.name,
                quality_score=(
                    r.ad_group_criterion.quality_info.quality_score
                    if r.ad_group_criterion.quality_info.quality_score > 0
                    else None
                ),
                metrics=CampaignMetrics(
                    impressions=r.metrics.impressions,
                    clicks=r.metrics.clicks,
                    cost_micros=r.metrics.cost_micros,
                    conversions=r.metrics.conversions,
                ),
            )
            for r in rows
        ]

    # ── ads ───────────────────────────────────────────────────────

    async def get_ads(
        self, customer_id: str, campaign_id: str
    ) -> list[AdResponse]:
        query = f"""
            SELECT
              ad_group_ad.ad.id,
              ad_group_ad.ad.responsive_search_ad.headlines,
              ad_group_ad.ad.responsive_search_ad.descriptions,
              ad_group_ad.ad.final_urls,
              ad_group_ad.status,
              ad_group.id,
              ad_group.name,
              campaign.id,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM ad_group_ad
            WHERE campaign.id = {campaign_id}
              AND ad_group_ad.status != 'REMOVED'
            ORDER BY ad_group_ad.ad.id
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        results: list[AdResponse] = []
        for r in rows:
            ad = r.ad_group_ad.ad
            headlines = []
            descriptions = []
            if ad.responsive_search_ad:
                headlines = [h.text for h in ad.responsive_search_ad.headlines]
                descriptions = [
                    d.text for d in ad.responsive_search_ad.descriptions
                ]
            results.append(
                AdResponse(
                    id=str(ad.id),
                    ad_group_id=str(r.ad_group.id),
                    ad_group_name=r.ad_group.name,
                    campaign_id=str(r.campaign.id),
                    headlines=headlines,
                    descriptions=descriptions,
                    final_urls=list(ad.final_urls),
                    status=r.ad_group_ad.status.name,
                    metrics=CampaignMetrics(
                        impressions=r.metrics.impressions,
                        clicks=r.metrics.clicks,
                        cost_micros=r.metrics.cost_micros,
                        conversions=r.metrics.conversions,
                    ),
                )
            )
        return results

    # ── campaign targeting ───────────────────────────────────────

    async def get_campaign_targeting(
        self, customer_id: str, campaign_id: str
    ) -> dict:
        query = f"""
            SELECT
              campaign_criterion.type,
              campaign_criterion.location.geo_target_constant,
              campaign_criterion.language.language_constant
            FROM campaign_criterion
            WHERE campaign.id = {campaign_id}
              AND campaign_criterion.negative = false
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        geo_resources: list[str] = []
        lang_resources: list[str] = []
        for r in rows:
            ctype = r.campaign_criterion.type_.name
            if ctype == "LOCATION":
                geo_resources.append(
                    r.campaign_criterion.location.geo_target_constant
                )
            elif ctype == "LANGUAGE":
                lang_resources.append(
                    r.campaign_criterion.language.language_constant
                )

        locations = await self._resolve_geo_names(customer_id, geo_resources)
        languages = await self._resolve_lang_names(customer_id, lang_resources)
        return {"locations": locations, "languages": languages}

    async def _resolve_geo_names(
        self, customer_id: str, resource_names: list[str]
    ) -> list[str]:
        if not resource_names:
            return []
        # Extract IDs from resource names like "geoTargetConstants/2840"
        geo_ids = []
        for rn in resource_names:
            parts = rn.split("/")
            if len(parts) == 2:
                geo_ids.append(parts[1])
        if not geo_ids:
            return resource_names  # fallback to raw names
        in_clause = ", ".join(geo_ids)
        query = f"""
            SELECT geo_target_constant.name,
                   geo_target_constant.canonical_name
            FROM geo_target_constant
            WHERE geo_target_constant.id IN ({in_clause})
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        return [
            r.geo_target_constant.canonical_name
            or r.geo_target_constant.name
            for r in rows
        ]

    async def _resolve_lang_names(
        self, customer_id: str, resource_names: list[str]
    ) -> list[str]:
        if not resource_names:
            return []
        # Extract IDs from resource names like "languageConstants/1000"
        lang_ids = []
        for rn in resource_names:
            parts = rn.split("/")
            if len(parts) == 2:
                lang_ids.append(parts[1])
        if not lang_ids:
            return resource_names
        in_clause = ", ".join(lang_ids)
        query = f"""
            SELECT language_constant.name
            FROM language_constant
            WHERE language_constant.id IN ({in_clause})
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        return [r.language_constant.name for r in rows]

    # ── search terms ─────────────────────────────────────────────

    async def get_search_terms(
        self,
        customer_id: str,
        campaign_id: str,
        date_from: str,
        date_to: str,
        limit: int = 50,
    ) -> list[dict]:
        """Return search terms for a campaign within a date range."""
        query = f"""
            SELECT
              search_term_view.search_term,
              search_term_view.status,
              ad_group.name,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM search_term_view
            WHERE campaign.id = {campaign_id}
              AND segments.date BETWEEN '{date_from}' AND '{date_to}'
            ORDER BY metrics.impressions DESC
            LIMIT {limit}
        """
        rows = await asyncio.to_thread(
            _run_query, _clean_id(customer_id), query
        )
        return [
            {
                "search_term": r.search_term_view.search_term,
                "status": r.search_term_view.status.name,
                "ad_group": r.ad_group.name,
                "impressions": r.metrics.impressions,
                "clicks": r.metrics.clicks,
                "cost_micros": r.metrics.cost_micros,
                "conversions": r.metrics.conversions,
            }
            for r in rows
        ]
