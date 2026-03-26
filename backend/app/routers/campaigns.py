"""Account & campaign endpoints — real Google Ads data."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    AccountResponse,
    AdGroupResponse,
    AdResponse,
    CampaignResponse,
    KeywordResponse,
)
from app.services.google_ads import GoogleAdsService

router = APIRouter(prefix="/api", tags=["campaigns"])

_ads_svc = GoogleAdsService()


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts():
    return await _ads_svc.get_accessible_accounts()


@router.get("/accounts/{account_id}/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    account_id: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    return await _ads_svc.get_campaigns(account_id, date_from, date_to)


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
    campaigns = await _ads_svc.get_campaigns(account_id, date_from, date_to)
    for c in campaigns:
        if c.id == campaign_id:
            return c
    raise HTTPException(status_code=404, detail="Campaign not found")


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}/adgroups",
    response_model=list[AdGroupResponse],
)
async def list_adgroups(account_id: str, campaign_id: str):
    return await _ads_svc.get_adgroups(account_id, campaign_id)


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}/keywords",
    response_model=list[KeywordResponse],
)
async def list_keywords(account_id: str, campaign_id: str):
    return await _ads_svc.get_keywords(account_id, campaign_id)


@router.get(
    "/accounts/{account_id}/campaigns/{campaign_id}/ads",
    response_model=list[AdResponse],
)
async def list_ads(account_id: str, campaign_id: str):
    return await _ads_svc.get_ads(account_id, campaign_id)


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/targeting")
async def get_targeting(account_id: str, campaign_id: str):
    return await _ads_svc.get_campaign_targeting(account_id, campaign_id)
