"""Direct campaign operation endpoints — powered by bundled MCP services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client
from google_ads.utils import format_customer_id
from app.config import settings
from app.services.cache import CacheService

router = APIRouter(prefix="/api/operations", tags=["operations"])
_cache = CacheService()


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


class CreateCampaignRequest(BaseModel):
    customer_id: str
    name: str
    daily_budget_micros: int  # e.g. 50_000_000 = $50/day
    status: str = "PAUSED"  # PAUSED or ENABLED
    advertising_channel_type: str = "SEARCH"  # SEARCH, DISPLAY, SHOPPING, etc.
    bidding_strategy: str = "MAXIMIZE_CONVERSIONS"  # MAXIMIZE_CONVERSIONS, MAXIMIZE_CLICKS, TARGET_CPA, MANUAL_CPC
    target_cpa_micros: int | None = None  # For TARGET_CPA strategy
    start_date: str | None = None  # YYYY-MM-DD
    end_date: str | None = None  # YYYY-MM-DD
    network_settings: dict | None = None  # Override default network settings


class CreateAdGroupRequest(BaseModel):
    customer_id: str
    campaign_id: str
    name: str
    status: str = "ENABLED"  # ENABLED or PAUSED
    cpc_bid_micros: int | None = None  # Optional manual CPC bid


class CreateRSARequest(BaseModel):
    customer_id: str
    ad_group_id: str
    headlines: list[str]  # 3-15 headlines, max 30 chars each
    descriptions: list[str]  # 2-4 descriptions, max 90 chars each
    final_urls: list[str]  # Landing page URLs
    path1: str | None = None  # Display URL path part 1 (max 15 chars)
    path2: str | None = None  # Display URL path part 2 (max 15 chars)
    status: str = "PAUSED"  # PAUSED or ENABLED


class UpdateCampaignRequest(BaseModel):
    customer_id: str
    campaign_id: str
    name: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class BulkKeywordAddRequest(BaseModel):
    customer_id: str
    ad_group_id: str
    keywords: list[dict]  # [{"text": "...", "match_type": "EXACT"}]
    default_cpc_bid_micros: int | None = None


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
        await _cache.invalidate(cid)  # Clear cached campaign data
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


@router.post("/campaign/create")
async def create_campaign(body: CreateCampaignRequest):
    """Create a new campaign with budget. Returns campaign ID and resource name."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
    from google.ads.googleads.v23.enums.types.advertising_channel_type import AdvertisingChannelTypeEnum
    from google.ads.googleads.v23.enums.types.budget_delivery_method import BudgetDeliveryMethodEnum
    from google.ads.googleads.v23.services.types.campaign_budget_service import (
        CampaignBudgetOperation, MutateCampaignBudgetsRequest,
    )
    from google.ads.googleads.v23.services.types.campaign_service import (
        CampaignOperation, MutateCampaignsRequest,
    )

    # Step 1: Create campaign budget
    budget_service = client.get_service("CampaignBudgetService")
    budget_op = CampaignBudgetOperation()
    budget_op.create.name = f"{body.name} Budget"
    budget_op.create.amount_micros = body.daily_budget_micros
    budget_op.create.delivery_method = BudgetDeliveryMethodEnum.BudgetDeliveryMethod.STANDARD
    budget_op.create.explicitly_shared = False

    try:
        budget_response = budget_service.mutate_campaign_budgets(
            request=MutateCampaignBudgetsRequest(customer_id=cid, operations=[budget_op])
        )
        budget_rn = budget_response.results[0].resource_name
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create budget: {e}")

    # Step 2: Create campaign
    campaign_service = client.get_service("CampaignService")
    campaign_op = CampaignOperation()
    campaign_op.create.name = body.name
    campaign_op.create.campaign_budget = budget_rn
    campaign_op.create.status = getattr(CampaignStatusEnum.CampaignStatus, body.status)
    campaign_op.create.advertising_channel_type = getattr(
        AdvertisingChannelTypeEnum.AdvertisingChannelType, body.advertising_channel_type
    )

    # Network settings — Search only by default
    campaign_op.create.network_settings.target_google_search = True
    campaign_op.create.network_settings.target_search_network = False
    campaign_op.create.network_settings.target_content_network = False
    campaign_op.create.network_settings.target_partner_search_network = False

    if body.network_settings:
        for k, v in body.network_settings.items():
            setattr(campaign_op.create.network_settings, k, v)

    # Bidding strategy
    if body.bidding_strategy == "MAXIMIZE_CONVERSIONS":
        campaign_op.create.maximize_conversions.target_cpa_micros = body.target_cpa_micros or 0
    elif body.bidding_strategy == "MAXIMIZE_CLICKS":
        campaign_op.create.maximize_clicks.cpc_bid_ceiling_micros = 0
    elif body.bidding_strategy == "TARGET_CPA":
        if not body.target_cpa_micros:
            raise HTTPException(status_code=400, detail="target_cpa_micros required for TARGET_CPA strategy")
        campaign_op.create.target_cpa.target_cpa_micros = body.target_cpa_micros
    elif body.bidding_strategy == "MANUAL_CPC":
        campaign_op.create.manual_cpc.enhanced_cpc_enabled = True

    # Dates
    if body.start_date:
        campaign_op.create.start_date = body.start_date.replace("-", "")
    if body.end_date:
        campaign_op.create.end_date = body.end_date.replace("-", "")

    try:
        campaign_response = campaign_service.mutate_campaigns(
            request=MutateCampaignsRequest(customer_id=cid, operations=[campaign_op])
        )
        campaign_rn = campaign_response.results[0].resource_name
        campaign_id = campaign_rn.split("/")[-1]
        await _cache.invalidate(cid)
        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "campaign_resource_name": campaign_rn,
            "budget_resource_name": budget_rn,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create campaign: {e}")


@router.post("/campaign/update")
async def update_campaign(body: UpdateCampaignRequest):
    """Update campaign properties (name, status, dates)."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
    from google.ads.googleads.v23.services.types.campaign_service import (
        CampaignOperation, MutateCampaignsRequest,
    )
    from google.protobuf import field_mask_pb2

    campaign_rn = f"customers/{cid}/campaigns/{body.campaign_id}"
    paths = []

    operation = CampaignOperation()
    operation.update.resource_name = campaign_rn

    if body.name is not None:
        operation.update.name = body.name
        paths.append("name")
    if body.status is not None:
        operation.update.status = getattr(CampaignStatusEnum.CampaignStatus, body.status)
        paths.append("status")
    if body.start_date is not None:
        operation.update.start_date = body.start_date.replace("-", "")
        paths.append("start_date")
    if body.end_date is not None:
        operation.update.end_date = body.end_date.replace("-", "")
        paths.append("end_date")

    if not paths:
        raise HTTPException(status_code=400, detail="No fields to update")

    operation.update_mask = field_mask_pb2.FieldMask(paths=paths)
    try:
        response = client.get_service("CampaignService").mutate_campaigns(
            request=MutateCampaignsRequest(customer_id=cid, operations=[operation])
        )
        await _cache.invalidate(cid)
        return {"status": "ok", "resource_name": response.results[0].resource_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ad-group/create")
async def create_ad_group(body: CreateAdGroupRequest):
    """Create an ad group within a campaign."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.ad_group_status import AdGroupStatusEnum
    from google.ads.googleads.v23.enums.types.ad_group_type import AdGroupTypeEnum
    from google.ads.googleads.v23.services.types.ad_group_service import (
        AdGroupOperation, MutateAdGroupsRequest,
    )

    campaign_rn = f"customers/{cid}/campaigns/{body.campaign_id}"

    operation = AdGroupOperation()
    operation.create.name = body.name
    operation.create.campaign = campaign_rn
    operation.create.status = getattr(AdGroupStatusEnum.AdGroupStatus, body.status)
    operation.create.type_ = AdGroupTypeEnum.AdGroupType.SEARCH_STANDARD

    if body.cpc_bid_micros:
        operation.create.cpc_bid_micros = body.cpc_bid_micros

    service = client.get_service("AdGroupService")
    try:
        response = service.mutate_ad_groups(
            request=MutateAdGroupsRequest(customer_id=cid, operations=[operation])
        )
        ag_rn = response.results[0].resource_name
        ad_group_id = ag_rn.split("/")[-1]
        return {"status": "ok", "ad_group_id": ad_group_id, "resource_name": ag_rn}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ad/create-rsa")
async def create_responsive_search_ad(body: CreateRSARequest):
    """Create a responsive search ad (RSA) in an ad group."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.ad_group_ad_status import AdGroupAdStatusEnum
    from google.ads.googleads.v23.enums.types.served_asset_field_type import ServedAssetFieldTypeEnum
    from google.ads.googleads.v23.services.types.ad_group_ad_service import (
        AdGroupAdOperation, MutateAdGroupAdsRequest,
    )
    from google.ads.googleads.v23.common.types.ad_asset import AdTextAsset

    if len(body.headlines) < 3 or len(body.headlines) > 15:
        raise HTTPException(status_code=400, detail="RSA requires 3-15 headlines")
    if len(body.descriptions) < 2 or len(body.descriptions) > 4:
        raise HTTPException(status_code=400, detail="RSA requires 2-4 descriptions")
    if not body.final_urls:
        raise HTTPException(status_code=400, detail="At least one final URL required")

    ad_group_rn = f"customers/{cid}/adGroups/{body.ad_group_id}"

    operation = AdGroupAdOperation()
    operation.create.ad_group = ad_group_rn
    operation.create.status = getattr(AdGroupAdStatusEnum.AdGroupAdStatus, body.status)

    # Set final URLs
    operation.create.ad.final_urls.extend(body.final_urls)

    # Set display URL paths
    if body.path1:
        operation.create.ad.responsive_search_ad.path1 = body.path1
    if body.path2:
        operation.create.ad.responsive_search_ad.path2 = body.path2

    # Add headlines
    for h in body.headlines:
        headline_asset = AdTextAsset()
        headline_asset.text = h
        operation.create.ad.responsive_search_ad.headlines.append(headline_asset)

    # Add descriptions
    for d in body.descriptions:
        desc_asset = AdTextAsset()
        desc_asset.text = d
        operation.create.ad.responsive_search_ad.descriptions.append(desc_asset)

    service = client.get_service("AdGroupAdService")
    try:
        response = service.mutate_ad_group_ads(
            request=MutateAdGroupAdsRequest(customer_id=cid, operations=[operation])
        )
        ad_rn = response.results[0].resource_name
        return {"status": "ok", "resource_name": ad_rn}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/keyword/bulk-add")
async def bulk_add_keywords(body: BulkKeywordAddRequest):
    """Add multiple keywords to an ad group at once."""
    _ensure_sdk()
    client = get_sdk_client().client
    cid = format_customer_id(body.customer_id)

    from google.ads.googleads.v23.enums.types.keyword_match_type import KeywordMatchTypeEnum
    from google.ads.googleads.v23.enums.types.ad_group_criterion_status import AdGroupCriterionStatusEnum
    from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
        AdGroupCriterionOperation, MutateAdGroupCriteriaRequest,
    )

    ag_rn = f"customers/{cid}/adGroups/{body.ad_group_id}"
    operations = []

    for kw in body.keywords:
        op = AdGroupCriterionOperation()
        op.create.ad_group = ag_rn
        op.create.status = AdGroupCriterionStatusEnum.AdGroupCriterionStatus.ENABLED
        op.create.keyword.text = kw["text"]
        op.create.keyword.match_type = getattr(
            KeywordMatchTypeEnum.KeywordMatchType, kw.get("match_type", "EXACT")
        )
        if body.default_cpc_bid_micros:
            op.create.cpc_bid_micros = body.default_cpc_bid_micros
        operations.append(op)

    service = client.get_service("AdGroupCriterionService")
    try:
        response = service.mutate_ad_group_criteria(
            request=MutateAdGroupCriteriaRequest(customer_id=cid, operations=operations)
        )
        return {
            "status": "ok",
            "count": len(response.results),
            "resource_names": [r.resource_name for r in response.results],
        }
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
