"""Google Ads mutation + read-back service layer (the inverse-op home).

Small, single-purpose SDK helpers used by BOTH the app's operations router (to
read before-state before a write) AND the Changelog revert executor (to apply the
inverse). Centralising the inverse ops here is what lets `change_revert` undo a
change *through the existing service layer* rather than re-implementing raw
mutations — the "never raw duplicates" rule.

Every function takes a live ``GoogleAdsClient`` (``get_sdk_client().client``) so
tests inject a fake client and assert the captured request — no live mutation.
Reads use one GAQL each (cheap enough to run before a write).
"""

from __future__ import annotations

from typing import Any

from google_ads.utils import format_customer_id

_V = "v23"


# ── Reads (GAQL, one query each) ──────────────────────────────────────────────

def _search(client, cid: str, query: str) -> list:
    ga = client.get_service("GoogleAdsService")
    return list(ga.search(customer_id=cid, query=query))


def get_campaign_status(client, customer_id: str, campaign_id: str) -> str | None:
    cid = format_customer_id(customer_id)
    rows = _search(client, cid,
                   f"SELECT campaign.status FROM campaign WHERE campaign.id = {campaign_id}")
    if not rows:
        return None
    return rows[0].campaign.status.name


def get_ad_group_status(client, customer_id: str, ad_group_id: str) -> str | None:
    cid = format_customer_id(customer_id)
    rows = _search(client, cid,
                   f"SELECT ad_group.status FROM ad_group WHERE ad_group.id = {ad_group_id}")
    if not rows:
        return None
    return rows[0].ad_group.status.name


def get_keyword_status(client, customer_id: str, ad_group_id: str,
                       criterion_id: str) -> str | None:
    cid = format_customer_id(customer_id)
    rn = f"customers/{cid}/adGroupCriteria/{ad_group_id}~{criterion_id}"
    rows = _search(client, cid,
                   "SELECT ad_group_criterion.status FROM ad_group_criterion "
                   f"WHERE ad_group_criterion.resource_name = '{rn}'")
    if not rows:
        return None
    return rows[0].ad_group_criterion.status.name


def get_ad_status(client, customer_id: str, ad_group_id: str,
                  ad_id: str) -> str | None:
    cid = format_customer_id(customer_id)
    rn = f"customers/{cid}/adGroupAds/{ad_group_id}~{ad_id}"
    rows = _search(client, cid,
                   "SELECT ad_group_ad.status FROM ad_group_ad "
                   f"WHERE ad_group_ad.resource_name = '{rn}'")
    if not rows:
        return None
    return rows[0].ad_group_ad.status.name


def get_criterion_bid(client, customer_id: str,
                      criterion_resource_name: str) -> int | None:
    cid = format_customer_id(customer_id)
    rows = _search(client, cid,
                   "SELECT ad_group_criterion.cpc_bid_micros FROM ad_group_criterion "
                   f"WHERE ad_group_criterion.resource_name = '{criterion_resource_name}'")
    if not rows:
        return None
    return rows[0].ad_group_criterion.cpc_bid_micros


def get_campaign_budget(client, customer_id: str,
                        campaign_id: str) -> tuple[str, int] | None:
    """Return (budget_resource_name, amount_micros) for a campaign's budget."""
    cid = format_customer_id(customer_id)
    rows = _search(client, cid,
                   "SELECT campaign.campaign_budget, campaign_budget.amount_micros "
                   f"FROM campaign WHERE campaign.id = {campaign_id}")
    if not rows:
        return None
    return rows[0].campaign.campaign_budget, rows[0].campaign_budget.amount_micros


def get_ad_final_urls(client, customer_id: str, ad_resource_name: str) -> list[str]:
    cid = format_customer_id(customer_id)
    rows = _search(client, cid,
                   "SELECT ad.final_urls FROM ad_group_ad "
                   f"WHERE ad.resource_name = '{ad_resource_name}'")
    if not rows:
        return []
    return list(rows[0].ad.final_urls)


def get_campaign_asset_status(client, customer_id: str,
                              campaign_asset_resource_name: str) -> str | None:
    cid = format_customer_id(customer_id)
    rows = _search(client, cid,
                   "SELECT campaign_asset.status FROM campaign_asset "
                   f"WHERE campaign_asset.resource_name = '{campaign_asset_resource_name}'")
    if not rows:
        return None
    return rows[0].campaign_asset.status.name


# ── Mutations (each returns the affected resource_name) ────────────────────────

def set_campaign_status(client, customer_id: str, campaign_id: str, status: str) -> str:
    from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
    from google.ads.googleads.v23.services.types.campaign_service import (
        CampaignOperation, MutateCampaignsRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    op = CampaignOperation()
    op.update.resource_name = f"customers/{cid}/campaigns/{campaign_id}"
    op.update.status = getattr(CampaignStatusEnum.CampaignStatus, status)
    op.update_mask = field_mask_pb2.FieldMask(paths=["status"])
    resp = client.get_service("CampaignService").mutate_campaigns(
        request=MutateCampaignsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_ad_group_status(client, customer_id: str, ad_group_id: str, status: str) -> str:
    from google.ads.googleads.v23.enums.types.ad_group_status import AdGroupStatusEnum
    from google.ads.googleads.v23.services.types.ad_group_service import (
        AdGroupOperation, MutateAdGroupsRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    op = AdGroupOperation()
    op.update.resource_name = f"customers/{cid}/adGroups/{ad_group_id}"
    op.update.status = getattr(AdGroupStatusEnum.AdGroupStatus, status)
    op.update_mask = field_mask_pb2.FieldMask(paths=["status"])
    resp = client.get_service("AdGroupService").mutate_ad_groups(
        request=MutateAdGroupsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_keyword_status(client, customer_id: str, ad_group_id: str,
                       criterion_id: str, status: str) -> str:
    from google.ads.googleads.v23.enums.types.ad_group_criterion_status import (
        AdGroupCriterionStatusEnum)
    from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
        AdGroupCriterionOperation, MutateAdGroupCriteriaRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    op = AdGroupCriterionOperation()
    op.update.resource_name = f"customers/{cid}/adGroupCriteria/{ad_group_id}~{criterion_id}"
    op.update.status = getattr(AdGroupCriterionStatusEnum.AdGroupCriterionStatus, status)
    op.update_mask = field_mask_pb2.FieldMask(paths=["status"])
    resp = client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(
        request=MutateAdGroupCriteriaRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_ad_group_ad_status(client, customer_id: str, ad_group_id: str,
                           ad_id: str, status: str) -> str:
    from google.ads.googleads.v23.enums.types.ad_group_ad_status import AdGroupAdStatusEnum
    from google.ads.googleads.v23.services.types.ad_group_ad_service import (
        AdGroupAdOperation, MutateAdGroupAdsRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    op = AdGroupAdOperation()
    op.update.resource_name = f"customers/{cid}/adGroupAds/{ad_group_id}~{ad_id}"
    op.update.status = getattr(AdGroupAdStatusEnum.AdGroupAdStatus, status)
    op.update_mask = field_mask_pb2.FieldMask(paths=["status"])
    resp = client.get_service("AdGroupAdService").mutate_ad_group_ads(
        request=MutateAdGroupAdsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_campaign_budget_micros(client, customer_id: str, amount_micros: int,
                               *, budget_resource_name: str | None = None,
                               campaign_id: str | None = None) -> str:
    from google.ads.googleads.v23.services.types.campaign_budget_service import (
        CampaignBudgetOperation, MutateCampaignBudgetsRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    budget_rn = budget_resource_name
    if not budget_rn:
        if not campaign_id:
            raise ValueError("budget_resource_name or campaign_id required")
        info = get_campaign_budget(client, cid, campaign_id)
        if not info:
            raise ValueError("campaign budget not found")
        budget_rn = info[0]
    op = CampaignBudgetOperation()
    op.update.resource_name = budget_rn
    op.update.amount_micros = int(amount_micros)
    op.update_mask = field_mask_pb2.FieldMask(paths=["amount_micros"])
    resp = client.get_service("CampaignBudgetService").mutate_campaign_budgets(
        request=MutateCampaignBudgetsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_criterion_bid(client, customer_id: str, criterion_resource_name: str,
                      cpc_bid_micros: int) -> str:
    from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
        AdGroupCriterionOperation, MutateAdGroupCriteriaRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    op = AdGroupCriterionOperation()
    op.update.resource_name = criterion_resource_name
    op.update.cpc_bid_micros = int(cpc_bid_micros)
    op.update_mask = field_mask_pb2.FieldMask(paths=["cpc_bid_micros"])
    resp = client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(
        request=MutateAdGroupCriteriaRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def remove_ad_group_criteria(client, customer_id: str,
                             resource_names: list[str]) -> list[str]:
    from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
        AdGroupCriterionOperation, MutateAdGroupCriteriaRequest)
    cid = format_customer_id(customer_id)
    ops = []
    for rn in resource_names:
        op = AdGroupCriterionOperation()
        op.remove = rn
        ops.append(op)
    resp = client.get_service("AdGroupCriterionService").mutate_ad_group_criteria(
        request=MutateAdGroupCriteriaRequest(customer_id=cid, operations=ops))
    return [r.resource_name for r in resp.results]


def remove_campaign_criteria(client, customer_id: str,
                             resource_names: list[str]) -> list[str]:
    from google.ads.googleads.v23.services.types.campaign_criterion_service import (
        CampaignCriterionOperation, MutateCampaignCriteriaRequest)
    cid = format_customer_id(customer_id)
    ops = []
    for rn in resource_names:
        op = CampaignCriterionOperation()
        op.remove = rn
        ops.append(op)
    resp = client.get_service("CampaignCriterionService").mutate_campaign_criteria(
        request=MutateCampaignCriteriaRequest(customer_id=cid, operations=ops))
    return [r.resource_name for r in resp.results]


def remove_customer_negative_criteria(client, customer_id: str,
                                      resource_names: list[str]) -> list[str]:
    from google.ads.googleads.v23.services.types.customer_negative_criterion_service import (
        CustomerNegativeCriterionOperation, MutateCustomerNegativeCriteriaRequest)
    cid = format_customer_id(customer_id)
    ops = []
    for rn in resource_names:
        op = CustomerNegativeCriterionOperation()
        op.remove = rn
        ops.append(op)
    svc = client.get_service("CustomerNegativeCriterionService")
    resp = svc.mutate_customer_negative_criteria(
        request=MutateCustomerNegativeCriteriaRequest(customer_id=cid, operations=ops))
    return [r.resource_name for r in resp.results]


def remove_ad_group_ad(client, customer_id: str,
                       ad_group_ad_resource_name: str) -> str:
    from google.ads.googleads.v23.services.types.ad_group_ad_service import (
        AdGroupAdOperation, MutateAdGroupAdsRequest)
    cid = format_customer_id(customer_id)
    op = AdGroupAdOperation()
    op.remove = ad_group_ad_resource_name
    resp = client.get_service("AdGroupAdService").mutate_ad_group_ads(
        request=MutateAdGroupAdsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_ad_final_urls(client, customer_id: str, ad_resource_name: str,
                      final_urls: list[str]) -> str:
    from google.ads.googleads.v23.resources.types.ad import Ad
    from google.ads.googleads.v23.services.types.ad_service import (
        AdOperation, MutateAdsRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    ad = Ad()
    ad.resource_name = ad_resource_name
    ad.final_urls.extend(final_urls)
    op = AdOperation()
    op.update = ad
    op.update_mask = field_mask_pb2.FieldMask(paths=["final_urls"])
    resp = client.get_service("AdService").mutate_ads(
        request=MutateAdsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name


def set_campaign_asset_status(client, customer_id: str,
                              campaign_asset_resource_name: str, status: str) -> str:
    from google.ads.googleads.v23.enums.types.asset_link_status import AssetLinkStatusEnum
    from google.ads.googleads.v23.services.types.campaign_asset_service import (
        CampaignAssetOperation, MutateCampaignAssetsRequest)
    from google.protobuf import field_mask_pb2
    cid = format_customer_id(customer_id)
    op = CampaignAssetOperation()
    op.update.resource_name = campaign_asset_resource_name
    op.update.status = getattr(AssetLinkStatusEnum.AssetLinkStatus, status)
    op.update_mask = field_mask_pb2.FieldMask(paths=["status"])
    resp = client.get_service("CampaignAssetService").mutate_campaign_assets(
        request=MutateCampaignAssetsRequest(customer_id=cid, operations=[op]))
    return resp.results[0].resource_name
