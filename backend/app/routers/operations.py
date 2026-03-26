"""Direct campaign operation endpoints — powered by bundled MCP services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client
from google_ads.utils import format_customer_id
from app.config import settings

router = APIRouter(prefix="/api/operations", tags=["operations"])


def _ensure_sdk():
    """Initialize the Google Ads SDK client if not already done."""
    try:
        get_sdk_client()
    except Exception:
        client = GoogleAdsSdkClient()
        # Override with our settings
        client._client = None
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


# ── Request Schemas ──────────────────────────────────────────────

class CampaignStatusRequest(BaseModel):
    customer_id: str
    campaign_id: str
    status: str  # "ENABLED" or "PAUSED"


class BudgetUpdateRequest(BaseModel):
    customer_id: str
    campaign_id: str
    budget_micros: int


class KeywordAddRequest(BaseModel):
    customer_id: str
    campaign_id: str
    ad_group_id: str
    keyword_text: str
    match_type: str = "EXACT"  # EXACT, PHRASE, BROAD


class KeywordStatusRequest(BaseModel):
    customer_id: str
    keyword_criterion_id: str
    ad_group_id: str
    status: str  # "ENABLED" or "PAUSED"


class NegativeKeywordRequest(BaseModel):
    customer_id: str
    campaign_id: str
    keyword_text: str
    match_type: str = "EXACT"


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/campaign/status")
async def update_campaign_status(body: CampaignStatusRequest):
    """Pause or enable a campaign with one click."""
    _ensure_sdk()
    client = get_sdk_client().client
    service = client.get_service("CampaignService")
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
    from google.ads.googleads.v23.services.types.campaign_service import (
        CampaignOperation, MutateCampaignsRequest,
    )
    from google.protobuf import field_mask_pb2

    status_enum = getattr(CampaignStatusEnum.CampaignStatus, body.status)
    campaign_rn = f"customers/{cid}/campaigns/{body.campaign_id}"

    operation = CampaignOperation()
    operation.update.resource_name = campaign_rn
    operation.update.status = status_enum
    operation.update_mask = field_mask_pb2.FieldMask(paths=["status"])

    request = MutateCampaignsRequest(customer_id=cid, operations=[operation])
    try:
        response = service.mutate_campaigns(request=request)
        return {"status": "ok", "resource_name": response.results[0].resource_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaign/budget")
async def update_campaign_budget(body: BudgetUpdateRequest):
    """Update a campaign's daily budget."""
    _ensure_sdk()
    client = get_sdk_client().client
    ga_service = client.get_service("GoogleAdsService")
    cid = format_customer_id(body.customer_id)

    # First get the campaign's budget resource name
    query = f"""
        SELECT campaign.campaign_budget
        FROM campaign
        WHERE campaign.id = {body.campaign_id}
    """
    rows = list(ga_service.search(customer_id=cid, query=query))
    if not rows:
        raise HTTPException(status_code=404, detail="Campaign not found")

    budget_rn = rows[0].campaign.campaign_budget

    from google.ads.googleads.v23.services.types.campaign_budget_service import (
        CampaignBudgetOperation, MutateCampaignBudgetsRequest,
    )
    from google.protobuf import field_mask_pb2

    budget_service = client.get_service("CampaignBudgetService")
    operation = CampaignBudgetOperation()
    operation.update.resource_name = budget_rn
    operation.update.amount_micros = body.budget_micros
    operation.update_mask = field_mask_pb2.FieldMask(paths=["amount_micros"])

    request = MutateCampaignBudgetsRequest(customer_id=cid, operations=[operation])
    try:
        response = budget_service.mutate_campaign_budgets(request=request)
        return {"status": "ok", "resource_name": response.results[0].resource_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/keyword/add")
async def add_keyword(body: KeywordAddRequest):
    """Add a keyword to an ad group."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.keyword_match_type import KeywordMatchTypeEnum
    from google.ads.googleads.v23.enums.types.ad_group_criterion_status import AdGroupCriterionStatusEnum
    from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
        AdGroupCriterionOperation, MutateAdGroupCriteriaRequest,
    )

    match_type = getattr(KeywordMatchTypeEnum.KeywordMatchType, body.match_type)
    ag_rn = f"customers/{cid}/adGroups/{body.ad_group_id}"

    operation = AdGroupCriterionOperation()
    operation.create.ad_group = ag_rn
    operation.create.status = AdGroupCriterionStatusEnum.AdGroupCriterionStatus.ENABLED
    operation.create.keyword.text = body.keyword_text
    operation.create.keyword.match_type = match_type

    service = client.get_service("AdGroupCriterionService")
    request = MutateAdGroupCriteriaRequest(customer_id=cid, operations=[operation])
    try:
        response = service.mutate_ad_group_criteria(request=request)
        return {"status": "ok", "resource_name": response.results[0].resource_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/keyword/status")
async def update_keyword_status(body: KeywordStatusRequest):
    """Pause or enable a keyword."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.ad_group_criterion_status import AdGroupCriterionStatusEnum
    from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
        AdGroupCriterionOperation, MutateAdGroupCriteriaRequest,
    )
    from google.protobuf import field_mask_pb2

    status_enum = getattr(AdGroupCriterionStatusEnum.AdGroupCriterionStatus, body.status)
    criterion_rn = f"customers/{cid}/adGroupCriteria/{body.ad_group_id}~{body.keyword_criterion_id}"

    operation = AdGroupCriterionOperation()
    operation.update.resource_name = criterion_rn
    operation.update.status = status_enum
    operation.update_mask = field_mask_pb2.FieldMask(paths=["status"])

    service = client.get_service("AdGroupCriterionService")
    request = MutateAdGroupCriteriaRequest(customer_id=cid, operations=[operation])
    try:
        response = service.mutate_ad_group_criteria(request=request)
        return {"status": "ok", "resource_name": response.results[0].resource_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaign/negative-keyword")
async def add_negative_keyword(body: NegativeKeywordRequest):
    """Add a campaign-level negative keyword."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.keyword_match_type import KeywordMatchTypeEnum
    from google.ads.googleads.v23.services.types.campaign_criterion_service import (
        CampaignCriterionOperation, MutateCampaignCriteriaRequest,
    )

    match_type = getattr(KeywordMatchTypeEnum.KeywordMatchType, body.match_type)
    campaign_rn = f"customers/{cid}/campaigns/{body.campaign_id}"

    operation = CampaignCriterionOperation()
    operation.create.campaign = campaign_rn
    operation.create.negative = True
    operation.create.keyword.text = body.keyword_text
    operation.create.keyword.match_type = match_type

    service = client.get_service("CampaignCriterionService")
    request = MutateCampaignCriteriaRequest(customer_id=cid, operations=[operation])
    try:
        response = service.mutate_campaign_criteria(request=request)
        return {"status": "ok", "resource_name": response.results[0].resource_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search-terms")
async def get_search_terms(body: dict):
    """Get search terms report for a campaign."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.get("customer_id", ""))
    campaign_id = body.get("campaign_id", "")
    date_from = body.get("date_from", "")
    date_to = body.get("date_to", "")

    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
          search_term_view.search_term,
          search_term_view.status,
          campaign.id,
          ad_group.id,
          ad_group.name,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions
        FROM search_term_view
        WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.impressions DESC
        LIMIT 200
    """
    try:
        rows = list(ga_service.search(customer_id=cid, query=query))
        results = []
        for r in rows:
            results.append({
                "search_term": r.search_term_view.search_term,
                "status": r.search_term_view.status.name,
                "campaign_id": str(r.campaign.id),
                "ad_group_id": str(r.ad_group.id),
                "ad_group_name": r.ad_group.name,
                "impressions": r.metrics.impressions,
                "clicks": r.metrics.clicks,
                "cost_micros": r.metrics.cost_micros,
                "conversions": r.metrics.conversions,
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
