"""V2 Search Term Analysis — AI-categorized search terms with bulk actions."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.google_ads import GoogleAdsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search-terms"])

_ads_svc = GoogleAdsService()


class BulkNegativeRequest(BaseModel):
    customer_id: str
    campaign_id: str
    keywords: list[dict]  # [{"text": "...", "match_type": "EXACT"}]


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/search-terms/analysis")
async def analyze_search_terms(
    account_id: str,
    campaign_id: str,
    days: int = Query(default=7, ge=1, le=90),
):
    """Fetch search terms and categorize into high_value, irrelevant, monitor."""
    date_to = date.today().isoformat()
    date_from = (date.today() - timedelta(days=days - 1)).isoformat()

    try:
        terms = await _ads_svc.get_search_terms(
            account_id, campaign_id, date_from, date_to, limit=300
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch search terms: {e}")

    # Fetch existing keywords to check which terms are already added
    existing_keywords = set()
    try:
        keywords = await _ads_svc.get_keywords(account_id, campaign_id)
        existing_keywords = {kw.text.lower() for kw in keywords}
    except Exception:
        pass

    high_value = []
    irrelevant = []
    monitor = []

    for t in terms:
        term = t["search_term"]
        impressions = t["impressions"]
        clicks = t["clicks"]
        cost_micros = t["cost_micros"]
        conversions = t["conversions"]
        cost = cost_micros / 1_000_000

        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpa = cost / conversions if conversions > 0 else 0

        entry = {
            "term": term,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 2),
            "conversions": round(conversions, 1),
            "ctr": round(ctr, 2),
            "cpa": round(cpa, 2) if conversions > 0 else None,
            "ad_group_id": t.get("ad_group_id", ""),
            "ad_group_name": t.get("ad_group_name", ""),
            "status": t.get("status", ""),
        }

        # Categorization logic
        if conversions > 0:
            if term.lower() not in existing_keywords:
                entry["recommendation"] = "Add as keyword — converting term not in keyword list"
                entry["suggested_match_type"] = "EXACT" if conversions >= 2 else "PHRASE"
                high_value.append(entry)
            else:
                # Already a keyword and converting — skip (it's working)
                continue
        elif cost > 10 and conversions == 0:
            # Spending money with no conversions — likely irrelevant
            entry["reason"] = f"${cost:.2f} spent with 0 conversions"
            entry["suggested_negative_match_type"] = "PHRASE" if clicks > 3 else "EXACT"
            irrelevant.append(entry)
        elif impressions > 50 and ctr < 1.0 and conversions == 0:
            # Low CTR, many impressions, no conversions — irrelevant
            entry["reason"] = f"Low CTR ({ctr:.1f}%) with {impressions} impressions, 0 conversions"
            entry["suggested_negative_match_type"] = "EXACT"
            irrelevant.append(entry)
        elif clicks > 0 and conversions == 0 and cost < 10:
            # Some activity but low spend — monitor
            entry["reason"] = "Some clicks but no conversions yet — needs more data"
            monitor.append(entry)
        elif impressions > 20:
            # Some impressions — put in monitor
            entry["reason"] = "Low activity — monitor for patterns"
            monitor.append(entry)

    # Sort each category
    high_value.sort(key=lambda x: x["conversions"], reverse=True)
    irrelevant.sort(key=lambda x: x["cost"], reverse=True)
    monitor.sort(key=lambda x: x["impressions"], reverse=True)

    return {
        "high_value": high_value,
        "irrelevant": irrelevant,
        "monitor": monitor,
        "total_terms": len(terms),
        "date_from": date_from,
        "date_to": date_to,
    }


@router.post("/operations/bulk-negatives")
async def add_bulk_negatives(body: BulkNegativeRequest):
    """Add multiple negative keywords to a campaign at once."""
    from google_ads.sdk_client import get_sdk_client, set_sdk_client, GoogleAdsSdkClient
    from google_ads.utils import format_customer_id
    from app.config import settings

    # Ensure SDK
    try:
        get_sdk_client()
    except Exception:
        client = GoogleAdsSdkClient()
        config = {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            "use_proto_plus": True,
        }
        from google.ads.googleads.client import GoogleAdsClient
        client._client = GoogleAdsClient.load_from_dict(config)
        set_sdk_client(client)

    sdk = get_sdk_client()
    cid = format_customer_id(body.customer_id)
    campaign_rn = f"customers/{cid}/campaigns/{body.campaign_id}"

    from google.ads.googleads.v23.enums.types.keyword_match_type import KeywordMatchTypeEnum
    from google.ads.googleads.v23.services.types.campaign_criterion_service import (
        CampaignCriterionOperation, MutateCampaignCriteriaRequest,
    )

    operations = []
    for kw in body.keywords:
        match_type = getattr(KeywordMatchTypeEnum.KeywordMatchType, kw.get("match_type", "EXACT"))
        op = CampaignCriterionOperation()
        op.create.campaign = campaign_rn
        op.create.negative = True
        op.create.keyword.text = kw["text"]
        op.create.keyword.match_type = match_type
        operations.append(op)

    if not operations:
        return {"added": 0}

    service = sdk.client.get_service("CampaignCriterionService")
    request = MutateCampaignCriteriaRequest(customer_id=cid, operations=operations)
    try:
        response = service.mutate_campaign_criteria(request=request)
        return {"added": len(response.results), "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
