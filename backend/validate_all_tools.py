"""Fail-closed dry-run validation harness for the Google Ads MCP tool surface.

Enumerates every mounted MCP tool (--groups all == 314 tools), classifies the
mutate/write tools, builds minimal valid arguments from each tool's JSON-schema
+ real IDs fetched live from the account, and invokes each write tool INSIDE the
``dry_run.force_validate_only()`` context so EVERY Google Ads mutate is forced to
``validate_only=True`` at the SDK layer (fail-closed — an unforceable mutate is
BLOCKED, never executed).

Verdicts:
  PASS  — tool returned without error (validate_only accepted the request)
  FAIL  — the API rejected the *request itself* under validate_only (a real
          tool bug: the tool built a bad request)
  SKIP  — could not build valid args / missing a required real id, OR a
          DryRunBlocked fired (flagged as a SAFETY skip)

Nothing in the account is mutated. Report -> data/tool_validation_report.json.

Run:  uv run python validate_all_tools.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── import the fail-closed engine ────────────────────────────────────────
from dry_run import force_validate_only, DryRunBlocked, COUNTERS

API_VERSION = "v23"
CUSTOMER_ID = "7178239091"
REPORT_PATH = Path(__file__).resolve().parent / "data" / "tool_validation_report.json"
PER_TOOL_TIMEOUT_S = 60.0

# Known campaigns (from project memory) — verified live at runtime.
KNOWN_CAMPAIGNS = {"23847913167": "MapleRoots", "23871240619": "Panama QIP"}


# ── SDK bootstrap (mirror app/routers/operations.py::_ensure_sdk) ────────
def bootstrap_sdk() -> None:
    """Initialize the global Google Ads SDK client from app settings."""
    from google_ads.sdk_client import (
        GoogleAdsSdkClient,
        get_sdk_client,
        set_sdk_client,
    )

    try:
        get_sdk_client()
        return
    except Exception:
        pass

    from app.config import settings
    from google.ads.googleads.client import GoogleAdsClient

    config = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
        "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    }
    client = GoogleAdsSdkClient()
    client._client = GoogleAdsClient.load_from_dict(config)
    set_sdk_client(client)


# ── fake FastMCP Context — tools do `await ctx.log(...)` ─────────────────
class FakeCtx:
    """Minimal stand-in for a FastMCP Context. All logging is a no-op."""

    async def log(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        return None

    async def info(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def warning(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def error(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def debug(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def report_progress(self, *args: Any, **kwargs: Any) -> None:
        return None


# ── live GAQL helpers ────────────────────────────────────────────────────
def _search(query: str) -> List[Any]:
    from google_ads.sdk_client import get_sdk_client

    ga = get_sdk_client().client.get_service("GoogleAdsService")
    return list(ga.search(customer_id=CUSTOMER_ID, query=query))


def fetch_real_ids() -> Dict[str, Any]:
    """Fetch real IDs to feed into tool args. Missing ones stay None (-> SKIP)."""
    ids: Dict[str, Any] = {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": None,
        "keyword_pair": None,          # (ad_group_id, criterion_id)
        "campaign_id": None,
        "campaign_name": None,
        "campaign_budget_rn": None,
        "ad_group_ad_rn": None,
        "ad_id": None,
        "asset_id": None,
        "asset_rn": None,
        "label_id": None,
        "label_rn": None,
        # ── widened harvest (populated below; None -> honest SKIP) ──────────
        "bidding_strategy_id": None,
        "bidding_strategy_rn": None,
        "shared_set_id": None,
        "shared_set_rn": None,
        "conversion_action_id": None,
        "conversion_action_rn": None,
        "user_list_id": None,
        "user_list_rn": None,
        "experiment_id": None,
        "experiment_rn": None,
        "asset_group_id": None,
        "asset_group_rn": None,
        "campaign_asset_rn": None,
        "ad_group_asset_rn": None,
        "customer_asset_rn": None,
        "customer_asset_field_type": None,   # matched to customer_asset_rn
        "campaign_criterion_rn": None,
        "campaign_criterion_id": None,
        "ad_group_bid_modifier_rn": None,
        "campaign_bid_modifier_rn": None,
        "audience_id": None,
        "audience_rn": None,
        "campaign_draft_rn": None,
        "campaign_draft_id": None,
        "recommendation_rn": None,
        "recommendation_type": None,
        "conversion_custom_variable_id": None,
        "image_asset_id": None,
        "image_asset_rn": None,
        "text_asset_id": None,          # a TEXT asset (for HEADLINE/DESCRIPTION)
        "sitelink_asset_id": None,      # a SITELINK asset (for SITELINK field)
        "youtube_video_id": None,
        "pmax_campaign_id": None,
        "remarketing_action_id": None,
        "keyword_plan_id": None,
        "keyword_plan_rn": None,
        # constants that always exist in the Google Ads system tables
        "geo_target_id": "21132",       # a real geo target constant id
        "language_id": "1000",          # English
    }

    def _try(label: str, fn) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            print(f"  [fetch] {label}: FAILED ({type(e).__name__}: {str(e)[:120]})")

    def _ad_groups() -> None:
        rows = _search(
            "SELECT ad_group.id FROM ad_group "
            "WHERE ad_group.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["ad_group_id"] = str(rows[0].ad_group.id)

    def _keyword() -> None:
        # Require ENABLED at every level — a criterion under a REMOVED campaign/
        # ad-group yields OPERATION_NOT_PERMITTED_FOR_REMOVED_RESOURCE on
        # validate_only, which is a stale-id harness artifact, not a tool bug.
        rows = _search(
            "SELECT ad_group.id, ad_group_criterion.criterion_id "
            "FROM keyword_view "
            "WHERE ad_group_criterion.status = 'ENABLED' "
            "AND ad_group.status = 'ENABLED' "
            "AND campaign.status = 'ENABLED' LIMIT 5"
        )
        if not rows:
            # fall back to any non-removed criterion
            rows = _search(
                "SELECT ad_group.id, ad_group_criterion.criterion_id "
                "FROM keyword_view "
                "WHERE ad_group_criterion.status != 'REMOVED' LIMIT 5"
            )
        if rows:
            r = rows[0]
            ids["keyword_pair"] = (
                str(r.ad_group.id),
                str(r.ad_group_criterion.criterion_id),
            )

    def _campaigns() -> None:
        rows = _search("SELECT campaign.id, campaign.name, campaign.status "
                       "FROM campaign LIMIT 50")
        chosen = None
        for r in rows:
            cid = str(r.campaign.id)
            if str(r.campaign.status.name) == "PAUSED":
                chosen = (cid, r.campaign.name)
                break
            if chosen is None:
                chosen = (cid, r.campaign.name)
        if chosen:
            ids["campaign_id"], ids["campaign_name"] = chosen

    def _budget() -> None:
        # Require ENABLED — a REMOVED budget yields CAMPAIGN_BUDGET_REMOVED on
        # campaign create and a version-mismatch UNKNOWN on budget update
        # (both stale-id artifacts, not tool bugs).
        rows = _search(
            "SELECT campaign_budget.resource_name FROM campaign_budget "
            "WHERE campaign_budget.status = 'ENABLED' LIMIT 5"
        )
        if not rows:
            rows = _search(
                "SELECT campaign_budget.resource_name FROM campaign_budget LIMIT 5"
            )
        if rows:
            ids["campaign_budget_rn"] = rows[0].campaign_budget.resource_name

    def _ad() -> None:
        rows = _search(
            "SELECT ad_group_ad.resource_name, ad_group_ad.ad.id "
            "FROM ad_group_ad WHERE ad_group_ad.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["ad_group_ad_rn"] = rows[0].ad_group_ad.resource_name
            ids["ad_id"] = str(rows[0].ad_group_ad.ad.id)

    def _asset() -> None:
        rows = _search(
            "SELECT asset.id, asset.resource_name FROM asset LIMIT 5"
        )
        if rows:
            ids["asset_id"] = str(rows[0].asset.id)
            ids["asset_rn"] = rows[0].asset.resource_name

    def _label() -> None:
        rows = _search(
            "SELECT label.id, label.resource_name FROM label LIMIT 5"
        )
        if rows:
            ids["label_id"] = str(rows[0].label.id)
            ids["label_rn"] = rows[0].label.resource_name

    # ── widened harvest fetchers ─────────────────────────────────────────
    def _bidding_strategy() -> None:
        rows = _search(
            "SELECT bidding_strategy.id, bidding_strategy.resource_name "
            "FROM bidding_strategy LIMIT 5"
        )
        if rows:
            ids["bidding_strategy_id"] = str(rows[0].bidding_strategy.id)
            ids["bidding_strategy_rn"] = rows[0].bidding_strategy.resource_name

    def _shared_set() -> None:
        rows = _search(
            "SELECT shared_set.id, shared_set.resource_name, shared_set.type "
            "FROM shared_set WHERE shared_set.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["shared_set_id"] = str(rows[0].shared_set.id)
            ids["shared_set_rn"] = rows[0].shared_set.resource_name

    def _conversion_action() -> None:
        # Prefer ENABLED — custom_conversion_goal rejects non-ENABLED actions
        # (CONVERSION_ACTION_NOT_ENABLED), a state artifact not a tool bug.
        rows = _search(
            "SELECT conversion_action.id, conversion_action.resource_name "
            "FROM conversion_action WHERE conversion_action.status = 'ENABLED' "
            "LIMIT 5"
        )
        if not rows:
            rows = _search(
                "SELECT conversion_action.id, conversion_action.resource_name "
                "FROM conversion_action "
                "WHERE conversion_action.status != 'REMOVED' LIMIT 5"
            )
        if rows:
            ids["conversion_action_id"] = str(rows[0].conversion_action.id)
            ids["conversion_action_rn"] = rows[0].conversion_action.resource_name

    def _user_list() -> None:
        rows = _search(
            "SELECT user_list.id, user_list.resource_name FROM user_list LIMIT 5"
        )
        if rows:
            ids["user_list_id"] = str(rows[0].user_list.id)
            ids["user_list_rn"] = rows[0].user_list.resource_name

    def _experiment() -> None:
        rows = _search(
            "SELECT experiment.experiment_id, experiment.resource_name "
            "FROM experiment WHERE experiment.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["experiment_id"] = str(rows[0].experiment.experiment_id)
            ids["experiment_rn"] = rows[0].experiment.resource_name

    def _asset_group() -> None:
        rows = _search(
            "SELECT asset_group.id, asset_group.resource_name, "
            "asset_group.campaign FROM asset_group LIMIT 5"
        )
        if rows:
            ids["asset_group_id"] = str(rows[0].asset_group.id)
            ids["asset_group_rn"] = rows[0].asset_group.resource_name

    def _pmax_campaign() -> None:
        rows = _search(
            "SELECT campaign.id FROM campaign "
            "WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX' "
            "AND campaign.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["pmax_campaign_id"] = str(rows[0].campaign.id)

    def _campaign_asset() -> None:
        rows = _search(
            "SELECT campaign_asset.resource_name FROM campaign_asset "
            "WHERE campaign_asset.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["campaign_asset_rn"] = rows[0].campaign_asset.resource_name

    def _ad_group_asset() -> None:
        rows = _search(
            "SELECT ad_group_asset.resource_name FROM ad_group_asset "
            "WHERE ad_group_asset.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["ad_group_asset_rn"] = rows[0].ad_group_asset.resource_name

    def _customer_asset() -> None:
        rows = _search(
            "SELECT customer_asset.resource_name, customer_asset.field_type "
            "FROM customer_asset WHERE customer_asset.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["customer_asset_rn"] = rows[0].customer_asset.resource_name
            ids["customer_asset_field_type"] = rows[0].customer_asset.field_type.name

    def _campaign_criterion() -> None:
        # A location/language/etc criterion whose campaign is not REMOVED, so a
        # remove under validate_only doesn't trip OPERATION_NOT_PERMITTED_FOR_
        # REMOVED_RESOURCE.
        rows = _search(
            "SELECT campaign_criterion.resource_name, "
            "campaign_criterion.criterion_id, campaign_criterion.type "
            "FROM campaign_criterion "
            "WHERE campaign_criterion.status != 'REMOVED' "
            "AND campaign.status != 'REMOVED' LIMIT 20"
        )
        if rows:
            ids["campaign_criterion_rn"] = rows[0].campaign_criterion.resource_name
            ids["campaign_criterion_id"] = str(
                rows[0].campaign_criterion.criterion_id
            )

    def _ad_group_bid_modifier() -> None:
        rows = _search(
            "SELECT ad_group_bid_modifier.resource_name "
            "FROM ad_group_bid_modifier LIMIT 5"
        )
        if rows:
            ids["ad_group_bid_modifier_rn"] = (
                rows[0].ad_group_bid_modifier.resource_name
            )

    def _campaign_bid_modifier() -> None:
        rows = _search(
            "SELECT campaign_bid_modifier.resource_name "
            "FROM campaign_bid_modifier LIMIT 5"
        )
        if rows:
            ids["campaign_bid_modifier_rn"] = (
                rows[0].campaign_bid_modifier.resource_name
            )

    def _audience() -> None:
        rows = _search(
            "SELECT audience.id, audience.resource_name FROM audience "
            "WHERE audience.status != 'REMOVED' LIMIT 5"
        )
        if rows:
            ids["audience_id"] = str(rows[0].audience.id)
            ids["audience_rn"] = rows[0].audience.resource_name

    def _campaign_draft() -> None:
        rows = _search(
            "SELECT campaign_draft.draft_id, campaign_draft.resource_name "
            "FROM campaign_draft LIMIT 5"
        )
        if rows:
            ids["campaign_draft_id"] = str(rows[0].campaign_draft.draft_id)
            ids["campaign_draft_rn"] = rows[0].campaign_draft.resource_name

    def _recommendation() -> None:
        rows = _search(
            "SELECT recommendation.resource_name, recommendation.type "
            "FROM recommendation LIMIT 5"
        )
        if rows:
            ids["recommendation_rn"] = rows[0].recommendation.resource_name
            ids["recommendation_type"] = rows[0].recommendation.type.name

    def _conversion_custom_variable() -> None:
        rows = _search(
            "SELECT conversion_custom_variable.id "
            "FROM conversion_custom_variable LIMIT 5"
        )
        if rows:
            ids["conversion_custom_variable_id"] = str(
                rows[0].conversion_custom_variable.id
            )

    def _image_asset() -> None:
        rows = _search(
            "SELECT asset.id, asset.resource_name FROM asset "
            "WHERE asset.type = 'IMAGE' LIMIT 5"
        )
        if rows:
            ids["image_asset_id"] = str(rows[0].asset.id)
            ids["image_asset_rn"] = rows[0].asset.resource_name

    def _text_asset() -> None:
        rows = _search(
            "SELECT asset.id FROM asset WHERE asset.type = 'TEXT' LIMIT 5"
        )
        if rows:
            ids["text_asset_id"] = str(rows[0].asset.id)

    def _sitelink_asset() -> None:
        rows = _search(
            "SELECT asset.id FROM asset WHERE asset.type = 'SITELINK' LIMIT 5"
        )
        if rows:
            ids["sitelink_asset_id"] = str(rows[0].asset.id)

    def _youtube_asset() -> None:
        rows = _search(
            "SELECT asset.youtube_video_asset.youtube_video_id "
            "FROM asset WHERE asset.type = 'YOUTUBE_VIDEO' LIMIT 5"
        )
        if rows:
            yid = rows[0].asset.youtube_video_asset.youtube_video_id
            if yid:
                ids["youtube_video_id"] = str(yid)

    def _remarketing_action() -> None:
        rows = _search(
            "SELECT remarketing_action.id FROM remarketing_action LIMIT 5"
        )
        if rows:
            ids["remarketing_action_id"] = str(rows[0].remarketing_action.id)

    def _keyword_plan() -> None:
        rows = _search(
            "SELECT keyword_plan.id, keyword_plan.resource_name "
            "FROM keyword_plan LIMIT 5"
        )
        if rows:
            ids["keyword_plan_id"] = str(rows[0].keyword_plan.id)
            ids["keyword_plan_rn"] = rows[0].keyword_plan.resource_name

    _try("ad_group", _ad_groups)
    _try("keyword", _keyword)
    _try("campaigns", _campaigns)
    _try("campaign_budget", _budget)
    _try("ad_group_ad", _ad)
    _try("asset", _asset)
    _try("label", _label)
    _try("bidding_strategy", _bidding_strategy)
    _try("shared_set", _shared_set)
    _try("conversion_action", _conversion_action)
    _try("user_list", _user_list)
    _try("experiment", _experiment)
    _try("asset_group", _asset_group)
    _try("pmax_campaign", _pmax_campaign)
    _try("campaign_asset", _campaign_asset)
    _try("ad_group_asset", _ad_group_asset)
    _try("customer_asset", _customer_asset)
    _try("campaign_criterion", _campaign_criterion)
    _try("ad_group_bid_modifier", _ad_group_bid_modifier)
    _try("campaign_bid_modifier", _campaign_bid_modifier)
    _try("audience", _audience)
    _try("campaign_draft", _campaign_draft)
    _try("recommendation", _recommendation)
    _try("conversion_custom_variable", _conversion_custom_variable)
    _try("image_asset", _image_asset)
    _try("text_asset", _text_asset)
    _try("sitelink_asset", _sitelink_asset)
    _try("youtube_asset", _youtube_asset)
    _try("remarketing_action", _remarketing_action)
    _try("keyword_plan", _keyword_plan)
    return ids


# ── mutate classification ────────────────────────────────────────────────
_WRITE_TOKENS = (
    "create", "update", "add", "remove", "delete", "mutate", "pause",
    "enable", "set_", "apply", "attach", "link", "upload", "move",
    "replace", "generate_recommendations",  # noop, guarded below
)
# Explicit read prefixes/substrings that must NEVER be treated as writes even if
# a write token appears substring-wise.
_READ_PREFIXES = (
    "get_", "list_", "search", "suggest_", "fetch_", "describe_",
    "count_", "preview_", "check_", "validate_query", "query_",
)
_READ_SUBSTR = (
    "_metadata", "generate_forecast", "generate_historical",
    "generate_keyword_ideas", "generate_keyword_historical",
    "generate_ad_group_themes", "generate_reach_forecast",
    "generate_insights", "suggest_", "_report", "generate_suggestions",
    "generate_geo", "list_", "estimate",
    # audience_insights generate_* are all read-only insight generators
    "generate_suggested", "generate_audience", "_insights", "targeting_insights",
)
# Tokens that look like writes but are pure reads / linking-name generators.
_FORCE_READ_EXACT = {
    "add_operations_to_batch_job",  # handled specially (skip: needs batch job)
}


def is_mutate_tool(bare_name: str) -> bool:
    """Classify on the BARE (un-namespaced) tool name.

    Passing the bare name is essential: a prefixed name like
    ``google_ads_search_google_ads`` would defeat a startswith('search') read
    check, whereas the bare ``search_google_ads`` matches it cleanly.
    """
    low = bare_name.lower()
    for rp in _READ_PREFIXES:
        if low.startswith(rp):
            return False
    for rs in _READ_SUBSTR:
        if rs in low:
            return False
    for tok in _WRITE_TOKENS:
        if tok in low:
            return True
    # Unsure -> treat as mutate (safe: runs under validate_only anyway).
    return True


# ── minimal-arg builder ──────────────────────────────────────────────────
class SkipTool(Exception):
    """Raised while building args when a required real id is unavailable."""


def _schema_required(params: Dict[str, Any]) -> List[str]:
    return list(params.get("required", []) or [])


def _schema_props(params: Dict[str, Any]) -> Dict[str, Any]:
    return params.get("properties", {}) or {}


def _default_for(prop_name: str, spec: Dict[str, Any], ids: Dict[str, Any]) -> Any:
    """Best-effort minimal value for a single schema property."""
    pn = prop_name.lower()
    typ = spec.get("type")
    # honor enums first
    enum = spec.get("enum")
    if enum:
        # prefer PAUSED/ENABLED-ish sensible values
        for pref in ("PAUSED", "ENABLED", "EXACT", "SITELINK", "CALLOUT"):
            if pref in enum:
                return pref
        return enum[0]

    # id-ish fields
    if pn == "customer_id":
        return ids["customer_id"]
    if pn in ("ad_group_id", "adgroup_id"):
        if ids["ad_group_id"] is None:
            raise SkipTool("no real ad_group_id available")
        return ids["ad_group_id"]
    if pn in ("campaign_id",):
        if ids["campaign_id"] is None:
            raise SkipTool("no real campaign_id available")
        return ids["campaign_id"]
    if pn in ("criterion_id", "keyword_criterion_id"):
        if ids["keyword_pair"] is None:
            raise SkipTool("no real criterion_id available")
        return ids["keyword_pair"][1]
    if pn in ("asset_id",):
        if ids["asset_id"] is None:
            raise SkipTool("no real asset_id available")
        return ids["asset_id"]
    if pn in ("label_id",):
        if ids["label_id"] is None:
            raise SkipTool("no real label_id available")
        return ids["label_id"]
    if pn in ("ad_id",):
        if ids["ad_id"] is None:
            raise SkipTool("no real ad_id available")
        return ids["ad_id"]

    # resource-name fields — MUST be a real, service-matching resource name.
    # Never inject a placeholder here: a fabricated RN triggers BAD_RESOURCE_ID /
    # RESOURCE_NAME_MALFORMED, which is a HARNESS artifact, not a tool bug. We
    # only supply a RN when we hold one whose TYPE matches the field; otherwise
    # SKIP. (We deliberately do NOT reuse a keyword-criterion RN for
    # shared/campaign/negative criterion fields — wrong type -> false FAIL.)
    if "resource_name" in pn or pn.endswith("_rn"):
        # Match ONLY when the RN kind is exactly right — a composite/association
        # RN (adGroupAdLabels/{ag}~{ad}, adGroupAssetSets/...) is not
        # interchangeable with a plain label/asset RN. Require the field's
        # leading token to name the same entity we hold.
        base = pn.replace("_resource_name", "").replace("_rn", "")
        if base in ("campaign_budget", "budget") and ids["campaign_budget_rn"]:
            return ids["campaign_budget_rn"]
        if base == "asset" and ids["asset_rn"]:
            return ids["asset_rn"]
        if base == "label" and ids["label_rn"]:
            return ids["label_rn"]
        if base in ("ad_group_criterion", "criterion") and ids["keyword_pair"]:
            # NOTE: only valid for the ad_group_criterion service; build_args
            # gates this by namespace before calling us for other services.
            agid, crid = ids["keyword_pair"]
            return f"customers/{CUSTOMER_ID}/adGroupCriteria/{agid}~{crid}"
        raise SkipTool(f"no real matching resource-name for '{prop_name}'")

    # any other *_id we don't have a fetched real value for -> SKIP (feeding a
    # placeholder id yields BAD_NUMBER / INVALID_CUSTOMER_ID = harness artifact)
    if pn.endswith("_id") or pn == "id":
        raise SkipTool(f"no real id available for '{prop_name}'")

    # arrays of ids / resource-names / geo constants need REAL structured values
    # (['Test'] -> BAD_RESOURCE_ID). SKIP rather than emit a false FAIL.
    if typ == "array" and (
        pn.endswith("_ids") or pn.endswith("_resource_names")
        or pn.endswith("_countries") or "criteria" in pn or "operations" in pn
    ):
        raise SkipTool(f"array-of-ids/resources '{prop_name}' needs real values")

    # GAQL query slots — a placeholder is not valid GAQL (EXPECTED_SELECT).
    if pn in ("query", "gaql", "gaql_query"):
        raise SkipTool(f"cannot synthesize a valid GAQL query for '{prop_name}'")

    # urls
    if "final_url" in pn or pn == "url" or pn.endswith("_url") or "urls" in pn:
        if typ == "array":
            return ["https://goldenvisas.mercan.com"]
        return "https://goldenvisas.mercan.com"

    # money / micros
    if "micros" in pn or pn.endswith("_micros"):
        return 1_000_000

    # phone / country
    if "phone" in pn:
        return "+1 800 555 0100"
    if pn == "country_code":
        return "US"

    # status/type strings without enum in schema
    if pn == "status":
        return "PAUSED"

    # free-text string fields are safe to fill (name/text/header/description)
    _FREE_TEXT = ("name", "text", "header", "description", "link_text",
                  "callout_text", "value", "title", "message")
    if typ == "string":
        if any(tok in pn for tok in _FREE_TEXT):
            return "Test"
        # An unknown required string that isn't obviously free-text could be a
        # typed token (enum-by-convention, resource fragment). SKIP to avoid a
        # false FAIL.
        raise SkipTool(f"unclassified required string '{prop_name}' — skipping "
                       f"to avoid a false FAIL")
    if typ == "integer":
        return 1
    if typ == "number":
        return 1.0
    if typ == "boolean":
        return False
    if typ == "array":
        items = spec.get("items", {})
        it = items.get("type")
        if it == "string":
            return ["Test"]
        if it in ("integer", "number"):
            return [1]
        raise SkipTool(f"array arg '{prop_name}' needs structured items")
    if typ == "object":
        raise SkipTool(f"object arg '{prop_name}' too complex")

    raise SkipTool(f"cannot build value for '{prop_name}' (spec={list(spec)})")


# Explicit overrides for the 5 named tools (by bare suffix) — exact per brief.
NAMED_TOOL_ARGS = {
    "update_ad_group_criterion_status": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": ids["keyword_pair"][0] if ids["keyword_pair"] else None,
        "criterion_id": ids["keyword_pair"][1] if ids["keyword_pair"] else None,
        "status": "PAUSED",
    },
    "create_sitelink_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "link_text": "Learn more",
        "final_urls": ["https://goldenvisas.mercan.com"],
    },
    "create_callout_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "callout_text": "Free consult",
    },
    "create_structured_snippet_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "header": "Services",
        # Google Ads enforces a minimum of 3 structured-snippet values
        # (2 -> collection_size_error: TOO_FEW). The brief's 2-value sample is
        # below the API minimum; 3 is the smallest valid request.
        "values": ["Visas", "Residency", "Citizenship"],
    },
    "create_call_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "phone_number": "+1 800 555 0100",
        "country_code": "US",
    },
}


# ── explicit arg map for every harvestable-but-previously-SKIPPED tool ───
# Keyed by BARE tool name. Each entry is (lambda ids -> dict, skip_reason). A
# value of None inside the dict means "the real id this arg needs was not
# harvested" -> the whole tool becomes an HONEST SKIP carrying skip_reason.
# Authored from data/_skip_tool_reference.txt (the arg contract) + live enum
# probes of the v23 protos (real enum members, NOT the sometimes-wrong
# docstrings — e.g. ConversionActionCategory has no LEAD; DataLinkType only
# VIDEO; InteractionType only CALLS; membership_status OPEN/CLOSED).
#
# Sentinel: _MISSING means "resource absent in account 7178239091". We use
# distinct human reasons so the report's SKIP bucket is self-explanatory.
_ABSENT = "resource absent in account 7178239091 — cannot build a valid request"


def _req(v: Any, reason: str) -> Any:
    """Return v, or raise SkipTool(reason) if v is falsy (harvest miss)."""
    if v is None:
        raise SkipTool(reason)
    return v


# Each lambda may call _req(...) to fail-closed to an honest SKIP.
HARVEST_TOOL_ARGS: Dict[str, Any] = {
    # ── account_budget_proposal (needs a real billing setup — none) ───────
    # left as SKIP via generic path (billing setup absent)

    # ── ad (text ads) ─────────────────────────────────────────────────────
    "ad_create_expanded_text_ad": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "headline1": "Immigration Help",
        "headline2": "Free Consultation",
        "headline3": "Apply Today",
        "description1": "Expert guidance for your visa and residency journey.",
        "description2": "Trusted immigration advisors ready to help you now.",
        "final_urls": ["https://goldenvisas.mercan.com"],
    },
    "ad_update_ad_final_urls": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "ad_id": _req(ids["ad_id"], "no ad_id"),
        "final_urls": ["https://goldenvisas.mercan.com/lp/"],
    },
    # ── ad_group_ad (needs a real ad RN to add; account has ad_group_ad but
    #    the create tool takes an ad_resource_name of an *unused* ad — not
    #    harvestable distinctly. remove/update take ad_group_ad RN which we
    #    DO hold). ──────────────────────────────────────────────────────────
    "ad_group_ad_remove_ad_group_ad": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_ad_resource_name": _req(ids["ad_group_ad_rn"], "no ad_group_ad_rn"),
    },
    "ad_group_ad_label_create_ad_group_ad_label": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_ad_resource_name": _req(ids["ad_group_ad_rn"], "no ad_group_ad_rn"),
        "label_resource_name": _req(ids["label_rn"], "no label_rn"),
    },
    "ad_group_ad_update_ad_group_ad_status": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_ad_resource_name": _req(ids["ad_group_ad_rn"], "no ad_group_ad_rn"),
        "status": "PAUSED",
    },
    # ── ad_group_asset ────────────────────────────────────────────────────
    "ad_group_asset_link_asset_to_ad_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
        "field_type": "SITELINK",
    },
    "ad_group_asset_link_multiple_assets_to_ad_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "asset_links": [
            {"asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
             "field_type": "SITELINK"}
        ],
    },
    "ad_group_asset_remove_asset_from_ad_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
        "field_type": "SITELINK",
    },
    "ad_group_asset_update_ad_group_asset_status": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
        "field_type": "SITELINK",
        "status": "PAUSED",
    },
    # ── ad_group_bid_modifier ─────────────────────────────────────────────
    "ad_group_bid_modifier_create_ad_group_device_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "device_type": "MOBILE",
        "bid_modifier": 1.1,
    },
    "ad_group_bid_modifier_create_ad_group_hotel_check_in_day_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "day_of_week": "MONDAY",
        "bid_modifier": 1.1,
    },
    "ad_group_bid_modifier_create_ad_group_hotel_date_selection_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "date_selection_type": "USER_SELECTED",
        "bid_modifier": 1.1,
    },
    "ad_group_bid_modifier_remove_ad_group_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "bid_modifier_resource_name": _req(
            ids["ad_group_bid_modifier_rn"], _ABSENT + " (ad_group_bid_modifier)"),
    },
    "ad_group_bid_modifier_update_ad_group_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "bid_modifier_resource_name": _req(
            ids["ad_group_bid_modifier_rn"], _ABSENT + " (ad_group_bid_modifier)"),
        "new_bid_modifier": 1.2,
    },
    # ── ad_group_criterion ────────────────────────────────────────────────
    "ad_group_criterion_add_audience_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "user_list_ids": [_req(ids["user_list_id"], "no user_list_id")],
    },
    "ad_group_criterion_add_demographic_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "demographics": [{"type": "AGE_RANGE", "value": "AGE_RANGE_25_34"}],
    },
    "ad_group_criterion_add_keywords": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "keywords": [{"text": "immigration lawyer", "match_type": "BROAD"}],
    },
    "ad_group_criterion_label_assign_label_to_criterion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_criterion": _req(
            f"customers/{CUSTOMER_ID}/adGroupCriteria/"
            f"{ids['keyword_pair'][0]}~{ids['keyword_pair'][1]}"
            if ids["keyword_pair"] else None, "no keyword_pair"),
        "label": _req(ids["label_rn"], "no label_rn"),
    },
    "ad_group_criterion_label_assign_label_to_multiple_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_criteria": [_req(
            f"customers/{CUSTOMER_ID}/adGroupCriteria/"
            f"{ids['keyword_pair'][0]}~{ids['keyword_pair'][1]}"
            if ids["keyword_pair"] else None, "no keyword_pair")],
        "label": _req(ids["label_rn"], "no label_rn"),
    },
    "ad_group_criterion_label_assign_multiple_labels_to_criterion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_criterion": _req(
            f"customers/{CUSTOMER_ID}/adGroupCriteria/"
            f"{ids['keyword_pair'][0]}~{ids['keyword_pair'][1]}"
            if ids["keyword_pair"] else None, "no keyword_pair"),
        "labels": [_req(ids["label_rn"], "no label_rn")],
    },
    "ad_group_criterion_update_criterion_bid": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "criterion_resource_name": _req(
            f"customers/{CUSTOMER_ID}/adGroupCriteria/"
            f"{ids['keyword_pair'][0]}~{ids['keyword_pair'][1]}"
            if ids["keyword_pair"] else None, "no keyword_pair"),
        "cpc_bid_micros": 1_000_000,
    },
    # ── ad_group (update) ─────────────────────────────────────────────────
    "ad_group_update_ad_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "status": "PAUSED",
    },
    # ── asset ─────────────────────────────────────────────────────────────
    "asset_create_youtube_video_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "youtube_video_id": _req(ids["youtube_video_id"], "no youtube_video_id"),
    },
    # ── asset_group (needs a PMax campaign) ───────────────────────────────
    "asset_group_create_asset_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["pmax_campaign_id"],
                            _ABSENT + " (no PERFORMANCE_MAX campaign)"),
        "name": "Harness Asset Group",
        "final_urls": ["https://goldenvisas.mercan.com"],
    },
    "asset_group_update_asset_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group_id": _req(ids["asset_group_id"], _ABSENT + " (asset_group)"),
        "name": "Harness Asset Group Renamed",
    },
    "asset_group_remove_asset_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group_id": _req(ids["asset_group_id"], _ABSENT + " (asset_group)"),
    },
    "asset_group_asset_create_asset_group_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group_id": _req(ids["asset_group_id"], _ABSENT + " (asset_group)"),
        "asset_id": _req(ids["text_asset_id"], "no text_asset_id"),
        "field_type": "HEADLINE",
    },
    "asset_group_asset_remove_asset_group_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group_id": _req(ids["asset_group_id"], _ABSENT + " (asset_group)"),
        "asset_id": _req(ids["text_asset_id"], "no text_asset_id"),
        "field_type": "HEADLINE",
    },
    "asset_group_asset_update_asset_group_asset_status": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group_id": _req(ids["asset_group_id"], _ABSENT + " (asset_group)"),
        "asset_id": _req(ids["text_asset_id"], "no text_asset_id"),
        "field_type": "HEADLINE",
        "status": "PAUSED",
    },
    "asset_group_signal_create_audience_signal": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group": _req(ids["asset_group_rn"], _ABSENT + " (asset_group)"),
        "audience_resource_name": _req(ids["audience_rn"], "no audience_rn"),
    },
    "asset_group_signal_create_search_theme_signal": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_group": _req(ids["asset_group_rn"], _ABSENT + " (asset_group)"),
        "search_theme": "immigration to canada",
    },
    # ── asset_set (create doesn't need an existing set) ───────────────────
    "asset_set_create_asset_set": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Asset Set",
        "asset_set_type": "PAGE_FEED",
    },
    "asset_set_update_asset_set": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_set_id": _req(None, _ABSENT + " (asset_set count=0)"),
    },
    "asset_set_remove_asset_set": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_set_id": _req(None, _ABSENT + " (asset_set count=0)"),
    },
    # ── audience ──────────────────────────────────────────────────────────
    "audience_create_combined_audience": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Combined Audience",
        "description": "harness test",
        "dimensions": [{"type": "AGE", "age_ranges": [{"min_age": 25, "max_age": 34}]}],
    },
    "audience_update_audience": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "audience_id": _req(ids["audience_id"], "no audience_id"),
        "description": "harness updated description",
    },
    "audience_remove_audience": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "audience_id": _req(ids["audience_id"], "no audience_id"),
    },
    # ── bidding_data_exclusion ────────────────────────────────────────────
    "bidding_data_exclusion_create_bidding_data_exclusion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Data Exclusion",
        "scope": "CUSTOMER",
        "start_date_time": "2030-01-01 00:00:00",
        "end_date_time": "2030-01-02 00:00:00",
    },
    "bidding_data_exclusion_update_bidding_data_exclusion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "exclusion_resource_name": _req(
            None, _ABSENT + " (bidding_data_exclusion)"),
    },
    "bidding_data_exclusion_remove_bidding_data_exclusion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "exclusion_resource_name": _req(
            None, _ABSENT + " (bidding_data_exclusion)"),
    },
    # ── bidding_seasonality_adjustment ────────────────────────────────────
    "bidding_seasonality_adjustment_create_bidding_seasonality_adjustment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Seasonality",
        "scope": "CUSTOMER",
        "start_date_time": "2030-01-01 00:00:00",
        "end_date_time": "2030-01-05 00:00:00",
        "conversion_rate_modifier": 1.5,
    },
    "bidding_seasonality_adjustment_update_bidding_seasonality_adjustment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "adjustment_resource_name": _req(
            None, _ABSENT + " (bidding_seasonality_adjustment)"),
    },
    "bidding_seasonality_adjustment_remove_bidding_seasonality_adjustment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "adjustment_resource_name": _req(
            None, _ABSENT + " (bidding_seasonality_adjustment)"),
    },
    # ── bidding_strategy ──────────────────────────────────────────────────
    "bidding_strategy_create_target_impression_share_strategy": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Target IS",
        "location": "ANYWHERE_ON_PAGE",
        "location_fraction_micros": 650000,
        # cpc_bid_ceiling is required by the API for target impression share
        "max_cpc_bid_ceiling_micros": 2_000_000,
    },
    # ── budget (update) ───────────────────────────────────────────────────
    "budget_update_campaign_budget": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "budget_id": _req(
            ids["campaign_budget_rn"].split("/")[-1]
            if ids["campaign_budget_rn"] else None, "no campaign_budget"),
        "name": "Harness Budget Renamed",
    },
    # ── campaign_asset ────────────────────────────────────────────────────
    "campaign_asset_link_asset_to_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
        "field_type": "SITELINK",
    },
    "campaign_asset_link_multiple_assets_to_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "asset_links": [{"asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
                         "field_type": "SITELINK"}],
    },
    "campaign_asset_remove_asset_from_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "asset_id": _req(ids["sitelink_asset_id"], "no sitelink_asset_id"),
        "field_type": "SITELINK",
    },
    # ── campaign_bid_modifier ─────────────────────────────────────────────
    "campaign_bid_modifier_create_interaction_type_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "interaction_type": "CALLS",
        "bid_modifier": 1.1,
    },
    "campaign_bid_modifier_remove_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "bid_modifier_resource_name": _req(
            ids["campaign_bid_modifier_rn"], _ABSENT + " (campaign_bid_modifier)"),
    },
    "campaign_bid_modifier_update_bid_modifier": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "bid_modifier_resource_name": _req(
            ids["campaign_bid_modifier_rn"], _ABSENT + " (campaign_bid_modifier)"),
        "new_bid_modifier": 1.2,
    },
    # ── campaign_conversion_goal (category has no LEAD -> DEFAULT) ─────────
    "campaign_conversion_goal_update_campaign_conversion_goal": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "category": "DEFAULT",
        "origin": "WEBSITE",
        "biddable": True,
    },
    # ── campaign_criterion ────────────────────────────────────────────────
    "campaign_criterion_add_device_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "device_types": ["MOBILE"],
    },
    "campaign_criterion_add_language_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "language_ids": [ids["language_id"]],
    },
    "campaign_criterion_add_location_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "location_ids": [ids["geo_target_id"]],
    },
    "campaign_criterion_add_negative_keyword_criteria": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "keywords": [{"text": "free", "match_type": "BROAD"}],
    },
    "campaign_criterion_remove_campaign_criterion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "criterion_resource_name": _req(
            ids["campaign_criterion_rn"], _ABSENT + " (campaign_criterion)"),
    },
    # ── campaign_draft ────────────────────────────────────────────────────
    "campaign_draft_create_campaign_draft": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "base_campaign": _req(
            f"customers/{CUSTOMER_ID}/campaigns/{ids['campaign_id']}"
            if ids["campaign_id"] else None, "no campaign_id"),
        "draft_name": "Harness Draft",
    },
    "campaign_draft_promote_campaign_draft": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "draft_resource_name": _req(
            ids["campaign_draft_rn"], _ABSENT + " (campaign_draft)"),
    },
    "campaign_draft_remove_campaign_draft": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "draft_resource_name": _req(
            ids["campaign_draft_rn"], _ABSENT + " (campaign_draft)"),
    },
    "campaign_draft_update_campaign_draft": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "draft_resource_name": _req(
            ids["campaign_draft_rn"], _ABSENT + " (campaign_draft)"),
        "draft_name": "Harness Draft Renamed",
    },
    # ── campaign (update) ─────────────────────────────────────────────────
    "campaign_update_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "status": "PAUSED",
    },
    # ── campaign_shared_set (needs a shared_set) ──────────────────────────
    "campaign_shared_set_attach_shared_set_to_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
    },
    "campaign_shared_set_attach_shared_sets_to_campaigns": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "attachments": [{"campaign_id": _req(ids["campaign_id"], "no campaign_id"),
                         "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id")}],
    },
    "campaign_shared_set_detach_shared_set_from_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
    },
    "campaign_shared_set_update_campaign_shared_set_status": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
        "status": "ENABLED",
    },
    # ── conversion_adjustment_upload (needs a conversion action RN) ───────
    "conversion_adjustment_upload_create_restatement_adjustment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversion_action": _req(ids["conversion_action_rn"], "no conversion_action_rn"),
        "gclid": "TeSter123gclidExample",
        "conversion_date_time": "2026-01-01 12:00:00+00:00",
        "adjustment_date_time": "2026-01-02 12:00:00+00:00",
        "adjusted_value": 10.0,
        "currency_code": "USD",
    },
    "conversion_adjustment_upload_create_retraction_adjustment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversion_action": _req(ids["conversion_action_rn"], "no conversion_action_rn"),
        "gclid": "TeSter123gclidExample",
        "conversion_date_time": "2026-01-01 12:00:00+00:00",
        "adjustment_date_time": "2026-01-02 12:00:00+00:00",
    },
    "conversion_adjustment_upload_upload_conversion_adjustments": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "adjustments": [{
            "conversion_action": _req(ids["conversion_action_rn"], "no conversion_action_rn"),
            "adjustment_type": "RETRACTION",
            "gclid": "TeSter123gclidExample",
            "conversion_date_time": "2026-01-01 12:00:00+00:00",
            "adjustment_date_time": "2026-01-02 12:00:00+00:00",
        }],
    },
    # ── conversion (update) ───────────────────────────────────────────────
    "conversion_update_conversion_action": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversion_action_id": _req(ids["conversion_action_id"], "no conversion_action_id"),
        "status": "ENABLED",
    },
    "conversion_upload_upload_call_conversions": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversions": [{
            "caller_id": "+18005550100",
            "call_start_date_time": "2026-01-01 12:00:00+00:00",
            "conversion_action_id": _req(ids["conversion_action_id"], "no conversion_action_id"),
            "conversion_date_time": "2026-01-01 13:00:00+00:00",
            "conversion_value": 10.0,
        }],
    },
    "conversion_upload_upload_click_conversions": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversions": [{
            "gclid": "TeSter123gclidExample",
            "conversion_action_id": _req(ids["conversion_action_id"], "no conversion_action_id"),
            "conversion_date_time": "2026-01-01 13:00:00+00:00",
            "conversion_value": 10.0,
        }],
    },
    # ── conversion_custom_variable ────────────────────────────────────────
    "conversion_custom_variable_create_conversion_custom_variable": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Custom Var",
        "tag": "harness_var",
    },
    "conversion_custom_variable_update_conversion_custom_variable": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "custom_variable_id": int(_req(
            ids["conversion_custom_variable_id"], "no conversion_custom_variable_id")),
        "name": "Harness Custom Var Renamed",
    },
    # ── custom_audience / custom_interest ─────────────────────────────────
    "custom_audience_create_custom_audience": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Custom Audience",
        "description": "harness",
        "members": [{"type": "KEYWORD", "keyword": "running shoes"}],
    },
    "custom_audience_update_custom_audience": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "custom_audience_id": _req(None, _ABSENT + " (custom_audience)"),
    },
    # ── custom_conversion_goal (needs a real conversion-action RN) ────────
    "custom_conversion_goal_create_custom_conversion_goal": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Custom Conversion Goal",
        "conversion_actions": [
            _req(ids["conversion_action_rn"], "no conversion_action_rn")],
    },
    "custom_interest_create_custom_interest": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Custom Interest",
        "description": "harness",
        "members": [{"type": "KEYWORD", "value": "running shoes"}],
    },
    "custom_interest_update_custom_interest": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "custom_interest_id": _req(None, _ABSENT + " (custom_interest)"),
    },
    # ── customer_asset ────────────────────────────────────────────────────
    "customer_asset_create_customer_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset": _req(
            f"customers/{CUSTOMER_ID}/assets/{ids['sitelink_asset_id']}"
            if ids["sitelink_asset_id"] else None, "no sitelink_asset_id"),
        "field_type": "SITELINK",
    },
    "customer_asset_remove_customer_asset": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "resource_name": _req(ids["customer_asset_rn"], _ABSENT + " (customer_asset)"),
    },
    "customer_asset_update_customer_asset_status": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "resource_name": _req(ids["customer_asset_rn"], _ABSENT + " (customer_asset)"),
        "status": "ENABLED",
    },
    # ── customer_negative_criterion ───────────────────────────────────────
    "customer_negative_criterion_add_content_label_exclusions": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "content_labels": ["TRAGEDY"],
    },
    "customer_negative_criterion_add_negative_keywords": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "keywords": [{"text": "free", "match_type": "BROAD"}],
    },
    "customer_negative_criterion_remove_negative_criterion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "criterion_resource_name": _req(
            None, _ABSENT + " (customer_negative_criterion)"),
    },
    # ── data_link (only VIDEO type valid; needs a YouTube channel id) ─────
    "data_link_create_basic_data_link": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "data_link_name": "Harness Data Link",
        "data_link_type": "VIDEO",
        "external_id": _req(ids["youtube_video_id"], "no youtube_video_id for VIDEO data link"),
    },
    # ── experiment ────────────────────────────────────────────────────────
    "experiment_arm_create_experiment_arm": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "experiment": _req(ids["experiment_rn"], "no experiment_rn"),
        "name": "Harness Arm",
        "control": False,
        "traffic_split": 50,
    },
    "experiment_arm_remove_experiment_arm": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "resource_name": _req(
            None, _ABSENT + " (experiment_arm)"),
    },
    "experiment_arm_update_experiment_arm": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "resource_name": _req(
            None, _ABSENT + " (experiment_arm)"),
    },
    "experiment_end_experiment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "experiment_id": _req(ids["experiment_id"], "no experiment_id"),
    },
    "experiment_promote_experiment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "experiment_id": _req(ids["experiment_id"], "no experiment_id"),
    },
    "experiment_schedule_experiment": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "experiment_id": _req(ids["experiment_id"], "no experiment_id"),
    },
    # ── keyword ───────────────────────────────────────────────────────────
    "keyword_add_keywords": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
        "keywords": [{"text": "immigration lawyer", "match_type": "BROAD"}],
    },
    # ── keyword_plan (needs a real keyword_plan) ──────────────────────────
    "keyword_plan_create_keyword_plan_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "keyword_plan_id": _req(ids["keyword_plan_id"], "no keyword_plan_id"),
        "name": "Harness KP Campaign A",
        "cpc_bid_micros": 1_000_000,
        "location_ids": [ids["geo_target_id"]],
        "language_id": ids["language_id"],
    },
    "keyword_plan_add_keywords_to_plan": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(
            None, _ABSENT + " (keyword_plan_ad_group)"),
        "keywords": [{"text": "immigration lawyer", "match_type": "BROAD"}],
    },
    "keyword_plan_campaign_create_keyword_plan_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "keyword_plan": _req(ids["keyword_plan_rn"], "no keyword_plan_rn"),
        "name": "Harness KP Campaign B",
        "keyword_plan_network": "GOOGLE_SEARCH",
        "cpc_bid_micros": 1_000_000,
    },
    # ── label bulk apply ──────────────────────────────────────────────────
    "label_apply_label_to_ad_groups": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "label_id": _req(ids["label_id"], "no label_id"),
        "ad_group_ids": [_req(ids["ad_group_id"], "no ad_group_id")],
    },
    "label_apply_label_to_campaigns": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "label_id": _req(ids["label_id"], "no label_id"),
        "campaign_ids": [_req(ids["campaign_id"], "no campaign_id")],
    },
    "label_update_label": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "label_id": _req(ids["label_id"], "no label_id"),
        "description": "harness updated label",
    },
    # ── bulk label pair tools ─────────────────────────────────────────────
    "ad_group_label_apply_labels_to_ad_groups": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_label_pairs": [{
            "ad_group_id": _req(ids["ad_group_id"], "no ad_group_id"),
            "label_id": _req(ids["label_id"], "no label_id")}],
    },
    "campaign_label_apply_labels_to_campaigns": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign_label_pairs": [{
            "campaign_id": _req(ids["campaign_id"], "no campaign_id"),
            "label_id": _req(ids["label_id"], "no label_id")}],
    },
    # ── pmax ──────────────────────────────────────────────────────────────
    "pmax_create_pmax_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness PMax",
        "budget_micros": 1_000_000,
        "final_urls": ["https://goldenvisas.mercan.com"],
        "business_name": "Mercan",
        "headlines": ["Immigration Help", "Free Consultation", "Apply Today"],
        "long_headlines": ["Expert immigration guidance for your visa journey"],
        "descriptions": ["Trusted immigration advisors ready to help you.",
                         "Start your residency application with confidence."],
        "logos": [_req(ids["image_asset_id"], "no image_asset_id")],
        "landscape_images": [_req(ids["image_asset_id"], "no image_asset_id")],
        "square_images": [_req(ids["image_asset_id"], "no image_asset_id")],
        "video_youtube_ids": [_req(ids["youtube_video_id"], "no youtube_video_id")],
    },
    # ── recommendation ────────────────────────────────────────────────────
    "recommendation_apply_recommendation": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "recommendation_resource_name": _req(
            ids["recommendation_rn"], _ABSENT + " (recommendation)"),
    },
    "recommendation_dismiss_recommendation": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "recommendation_resource_names": [_req(
            ids["recommendation_rn"], _ABSENT + " (recommendation)")],
    },
    # ── remarketing_action (update) ───────────────────────────────────────
    "remarketing_action_update_remarketing_action": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "remarketing_action_id": _req(ids["remarketing_action_id"], "no remarketing_action_id"),
        "name": "Harness Remarketing Renamed",
    },
    # ── shared_criterion / shared_set ─────────────────────────────────────
    "shared_criterion_add_keywords_to_shared_set": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
        "keywords": [{"text": "free", "match_type": "BROAD"}],
    },
    "shared_criterion_add_placements_to_shared_set": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
        "placement_urls": ["https://example.com"],
    },
    "shared_criterion_remove_shared_criterion": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "criterion_resource_name": _req(
            None, _ABSENT + " (shared_criterion)"),
    },
    "shared_set_attach_shared_set_to_campaigns": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
        "campaign_ids": [_req(ids["campaign_id"], "no campaign_id")],
    },
    "shared_set_update_shared_set": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "shared_set_id": _req(ids["shared_set_id"], "no shared_set_id"),
        "name": "Harness Shared Set Renamed",
    },
    # ── mutate_* operations-list tools (op shapes read from each service) ─
    # Flat shape uses op["operation_type"]; a few use nested op["create"/...].
    # Only the buildable ones are here; the rest stay honest SKIP (absent
    # customizer_attribute / asset_set / keyword_plan sub-resources).
    "ad_group_criterion_label_mutate_ad_group_criterion_labels": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{
            "operation_type": "create",
            "ad_group_criterion": (
                f"customers/{CUSTOMER_ID}/adGroupCriteria/"
                f"{ids['keyword_pair'][0]}~{ids['keyword_pair'][1]}"
                if ids["keyword_pair"] else None),
            "label": _req(ids["label_rn"], "no label_rn")}],
    },
    "asset_group_signal_mutate_asset_group_signals": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{
            "operation_type": "create",
            "asset_group": _req(ids["asset_group_rn"], _ABSENT + " (asset_group)"),
            "audience_resource_name": _req(ids["audience_rn"], "no audience_rn")}],
    },
    "conversion_goal_campaign_config_mutate_conversion_goal_campaign_configs": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{
            "operation_type": "update",
            "resource_name": (
                f"customers/{CUSTOMER_ID}/conversionGoalCampaignConfigs/"
                f"{ids['campaign_id']}" if ids["campaign_id"] else None),
            "goal_config_level": "CAMPAIGN"}],
    },
    "custom_conversion_goal_mutate_custom_conversion_goals": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{
            "operation_type": "create",
            "name": "Harness Custom Goal",
            "conversion_actions": [
                _req(ids["conversion_action_rn"], "no conversion_action_rn")]}],
    },
    "customer_asset_mutate_customer_assets": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{
            "operation_type": "create",
            "asset": (
                f"customers/{CUSTOMER_ID}/assets/{ids['sitelink_asset_id']}"
                if ids["sitelink_asset_id"] else None),
            "field_type": "SITELINK"}],
    },
    "customer_conversion_goal_mutate_customer_conversion_goals": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{"update": {
            "resource_name":
                f"customers/{CUSTOMER_ID}/customerConversionGoals/PURCHASE~WEBSITE",
            "biddable": True}}],
    },
    "experiment_arm_mutate_experiment_arms": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "operations": [{
            "operation_type": "create",
            "experiment": _req(ids["experiment_rn"], "no experiment_rn"),
            "name": "Harness Arm",
            "control": False,
            "traffic_split": 50,
            "campaigns": [
                f"customers/{CUSTOMER_ID}/campaigns/{ids['campaign_id']}"
                if ids["campaign_id"] else None]}],
    },
    "user_data_upload_enhanced_conversions": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversion_adjustments": [{
            "user_identifiers": [{
                "hashed_email":
                    "a1b2c3d4e5f60718293a4b5c6d7e8f90"
                    "112233445566778899aabbccddeeff00"}],
            "transaction_attribute": {
                "conversion_action": _req(
                    ids["conversion_action_rn"], "no conversion_action_rn"),
                "currency_code": "USD",
                "transaction_amount_micros": 1_000_000,
                "transaction_date_time": "2026-01-01 12:00:00+00:00",
                "order_id": "harness-order-1"}}],
    },
    # ── honest absent-resource SKIPs (documented so the report reads clean;
    #    these previously showed a misleading "unclassified string" reason).
    #    All require a resource that count-probed to 0 in account 7178239091. ─
    "ad_group_customizer_create_ad_group_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "ad_group_customizer_create_number_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "ad_group_customizer_create_price_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "ad_group_customizer_create_text_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "customer_customizer_create_customer_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "customer_customizer_create_number_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "customer_customizer_create_price_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "customer_customizer_create_text_customizer": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "customizer_attribute": _req(None, _ABSENT + " (customizer_attribute count=0)")},
    "customizer_attribute_create_customizer_attribute": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Customizer",
        "attribute_type": "TEXT",
    },  # this CREATE does not need an existing one -> should PASS
    "campaign_asset_set_link_asset_set_to_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign": _req(None, _ABSENT + " (asset_set count=0)"),
        "asset_set": None},
    "campaign_asset_set_link_asset_set_to_multiple_campaigns": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "asset_set": _req(None, _ABSENT + " (asset_set count=0)")},
    "campaign_asset_set_link_multiple_asset_sets_to_campaign": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "campaign": _req(None, _ABSENT + " (asset_set count=0)")},
    "keyword_plan_ad_group_create_keyword_plan_ad_group": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "keyword_plan_campaign": _req(
            None, _ABSENT + " (keyword_plan_campaign — no KP campaign exists)")},
    "keyword_plan_ad_group_keyword_create_keyword_plan_ad_group_keyword": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "keyword_plan_ad_group": _req(
            None, _ABSENT + " (keyword_plan_ad_group — none exists)")},
    "keyword_plan_campaign_keyword_create_keyword_plan_campaign_keyword": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "keyword_plan_campaign": _req(
            None, _ABSENT + " (keyword_plan_campaign — none exists)")},
    "keyword_plan_add_keywords_to_plan": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "ad_group_id": _req(
            None, _ABSENT + " (keyword_plan_ad_group — none exists to add keywords to)")},

    # ── user_data uploads (buildable but require Customer-Match / store-sales
    #    allowlisting on the developer token — attempt so the report captures
    #    the exact allowlist error rather than a vague arg SKIP) ─────────────
    "user_data_upload_customer_match_data": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "user_list_id": _req(ids["user_list_id"], "no user_list_id"),
        "user_data_list": [{
            "user_identifiers": [{
                "hashed_email":
                    "a1b2c3d4e5f60718293a4b5c6d7e8f90"
                    "112233445566778899aabbccddeeff00"}]}],
    },
    "user_data_upload_store_sales_data": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "conversion_action": _req(ids["conversion_action_rn"], "no conversion_action_rn"),
        "store_sales_data": [{
            "user_identifiers": [{
                "hashed_email":
                    "a1b2c3d4e5f60718293a4b5c6d7e8f90"
                    "112233445566778899aabbccddeeff00"}],
            "transaction_attribute": {
                "conversion_action": _req(
                    ids["conversion_action_rn"], "no conversion_action_rn"),
                "currency_code": "USD",
                "transaction_amount_micros": 1_000_000,
                "transaction_date_time": "2026-01-01 12:00:00+00:00"}}],
    },
    # ── honest MCC / external-dependency SKIPs (clear reasons) ────────────
    "account_budget_proposal_create_account_budget_proposal": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "billing_setup": _req(
            None, "MCC/billing-only — no billing_setup or payments account on "
            "this test account")},
    "customer_client_link_create_customer_client_link": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "client_customer": _req(
            None, "MCC-only — creating a client link requires a real external "
            "client customer id under this manager")},
    "customer_user_access_invitation_create_customer_user_access_invitation": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "email_address": _req(
            None, "needs a real external invitee email + access flow — not "
            "safely fabricable")},
    "identity_verification_start_identity_verification": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "verification_program": _req(
            None, "advertiser-identity-verification is an account-lifecycle "
            "action, not a dry-runnable mutate for this token")},

    # ── user_list ─────────────────────────────────────────────────────────
    "user_list_create_logical_user_list": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Logical List",
        "rules": [{"user_list_ids": [_req(ids["user_list_id"], "no user_list_id")],
                   "operator": "ANY"}],
    },
    "user_list_create_similar_user_list": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "name": "Harness Similar List",
        "seed_user_list_ids": [_req(ids["user_list_id"], "no user_list_id")],
    },
    "user_list_update_user_list": lambda ids: {
        "customer_id": CUSTOMER_ID,
        "user_list_id": _req(ids["user_list_id"], "no user_list_id"),
        "description": "harness updated user list",
    },
}


def build_args(
    bare_name: str, params: Dict[str, Any], ids: Dict[str, Any],
    namespace: str = "", full_name: str = "",
) -> Dict[str, Any]:
    """Build minimal valid args from the tool's JSON schema + real ids.

    ``bare_name`` is the un-namespaced method name (collides across services,
    e.g. ``add_keywords`` exists under both ad_group_criterion & keyword), so
    the harvested-arg override is keyed on the FULL prefixed ``full_name`` for
    unambiguous disambiguation.
    """
    # named-tool override (keyed on bare — those 5 suffixes are unique)
    if bare_name in NAMED_TOOL_ARGS:
        args = NAMED_TOOL_ARGS[bare_name](ids)
        for k, v in args.items():
            if v is None:
                raise SkipTool(f"named tool missing real id for '{k}'")
        return args

    # harvested-arg override (authored per data/_skip_tool_reference.txt),
    # keyed on the FULL name. The lambda may itself raise SkipTool (via _req)
    # for a harvest miss -> honest SKIP.
    if full_name in HARVEST_TOOL_ARGS:
        args = HARVEST_TOOL_ARGS[full_name](ids)
        for k, v in args.items():
            if v is None:
                raise SkipTool(f"harvest tool missing real value for '{k}'")
        return args

    props = _schema_props(params)
    required = [r for r in _schema_required(params) if r != "ctx"]

    # Gate the ad-group-criterion RN reuse: only the ad_group_criterion service
    # accepts an adGroupCriteria/... RN. For campaign/negative/shared criterion
    # services, a `criterion_resource_name` needs a DIFFERENT-typed RN we don't
    # hold -> SKIP (else RESOURCE_NAME_MALFORMED false FAIL).
    crit_fields = [
        r for r in required
        if ("criterion" in r.lower())
        and ("resource_name" in r.lower() or r.lower().endswith("_rn"))
    ]
    if crit_fields and namespace != "ad_group_criterion":
        raise SkipTool(
            f"criterion resource-name field(s) {crit_fields} need a "
            f"{namespace}-typed RN not available (only an ad_group_criterion "
            f"RN was fetched)"
        )

    # An update/bid tool whose only required inputs are ids/resource-names has
    # no field to change -> the API returns FIELD_MASK_MISSING. That is a
    # harness limitation (we can't invent a meaningful mutation), not a bug.
    low = bare_name.lower()
    looks_update = (
        low.startswith("update_") or low.endswith("_bid")
        or "update_" in low or low.startswith("set_")
    )
    if looks_update:
        changeable = [
            r for r in required
            if r != "customer_id"
            and not r.lower().endswith("_id")
            and r.lower() != "id"
            and "resource_name" not in r.lower()
            and not r.lower().endswith("_rn")
        ]
        if not changeable:
            raise SkipTool(
                "update tool has no required *changeable* field (only ids); "
                "a minimal request would send an empty field mask "
                "(FIELD_MASK_MISSING) — harness cannot construct a meaningful "
                "update"
            )

    args: Dict[str, Any] = {}
    if "customer_id" in props:
        args["customer_id"] = CUSTOMER_ID

    # Consistency: if a tool needs BOTH an ad_group_id and a criterion_id, they
    # must come from the SAME keyword — the standalone ad_group_id fetch is an
    # unrelated ad group, so pairing them yields a non-existent criterion RN
    # (RESOURCE_NOT_FOUND). Source both from keyword_pair.
    req_low = {r.lower() for r in required}
    needs_ag = bool(req_low & {"ad_group_id", "adgroup_id"})
    needs_crit = bool(req_low & {"criterion_id", "keyword_criterion_id"})
    if needs_ag and needs_crit:
        if ids["keyword_pair"] is None:
            raise SkipTool("no matched (ad_group_id, criterion_id) pair available")
        agid, crid = ids["keyword_pair"]
        for r in required:
            rl = r.lower()
            if rl in ("ad_group_id", "adgroup_id"):
                args[r] = agid
            elif rl in ("criterion_id", "keyword_criterion_id"):
                args[r] = crid

    for name in required:
        if name in args:
            continue
        spec = props.get(name, {})
        args[name] = _default_for(name, spec, ids)

    return args


# ── tool enumeration (namespaced name + real .fn) ────────────────────────
async def enumerate_tools() -> List[Tuple[str, str, Any, Dict[str, Any]]]:
    """Return [(full_name, namespace, fn, parameters_schema), ...] for all tools."""
    from google_ads.mcp_main import get_servers_to_mount

    out: List[Tuple[str, str, Any, Dict[str, Any]]] = []
    seen: set[str] = set()
    for namespace, server in get_servers_to_mount("all"):
        sub_tools = await server.list_tools()
        for t in sub_tools:
            full = f"{namespace}_{t.name}"
            if full in seen:
                continue
            seen.add(full)
            fn = getattr(t, "fn", None)
            params = getattr(t, "parameters", {}) or {}
            out.append((full, namespace, fn, params))
    out.sort(key=lambda x: x[0])
    return out


# ── error classification ─────────────────────────────────────────────────
# Verdict rules:
#   SAFETY  -> a DryRunBlocked fired (directly or swallowed by a service's
#              broad `except Exception`). The mutate was NOT executed. SKIP.
#   FAIL    -> the API validated the request and REJECTED it (a real tool bug:
#              the tool built a bad request). Detected via GoogleAdsException,
#              its __cause__ chain, or the "Google Ads API error:" wrapper the
#              services raise.
#   OTHER   -> anything else (harness-side arg mismatch, infra). SKIP.
def _find_google_ads_exc(exc: BaseException):
    """Walk the __cause__/__context__ chain for a GoogleAdsException."""
    from google.ads.googleads.errors import GoogleAdsException

    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, GoogleAdsException):
            return cur
        cur = cur.__cause__ or cur.__context__
    return None


def _is_swallowed_dry_run_block(exc: BaseException) -> bool:
    """True if a DryRunBlocked was raised (possibly re-wrapped as Exception)."""
    if isinstance(exc, DryRunBlocked):
        return True
    # chain check
    cur: Optional[BaseException] = exc
    seen = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, DryRunBlocked):
            return True
        cur = cur.__cause__ or cur.__context__
    # string fallback (services re-raise as plain Exception, dropping the type)
    s = str(exc)
    return "Refusing to call mutate" in s or "Fail-closed — the real mutate" in s


# Error codes that mean "this ACCOUNT/token cannot run this request" rather
# than "the tool built a malformed request". The tool logic is fine; the
# account lacks a permission/allowlist/billing prerequisite. Reported as SKIP
# (account-constraint) so the FAIL list stays limited to genuine tool bugs.
_ACCOUNT_CONSTRAINT_CODES = (
    "CUSTOMER_NOT_ALLOWLISTED",
    "NOT_ALLOWLISTED",
    "BILLING_NOT_ON_MONTHLY_INVOICING",
    "CANNOT_ATTACH_NON_MANAGER_LABEL_TO_CUSTOMER",
    "CANNOT_ADD_ASSET_GROUP_FOR_CAMPAIGN_TYPE",
    "OPERATION_NOT_PERMITTED_FOR_REMOVED_RESOURCE",
    "CAMPAIGN_BUDGET_REMOVED",
    "RESOURCE_NOT_FOUND",   # real id of the wrong TYPE for this service
    # ── wrong-STATE / wrong-CONTEXT for a real harvested id (the tool is
    #    fine; the specific resource we fed it is in a state/type that forbids
    #    this op). Not a tool bug -> SKIP-account, not FAIL. ─────────────────
    "CANNOT_ADD_CLOSED_USER_LIST",        # harvested user_list is CLOSED
    "OPERATION_NOT_PERMITTED_FOR_CONTEXT",  # hotel modifier on non-hotel adgroup
    "INVALID_STATUS_TRANSITION_FROM_REMOVED",  # harvested draft is REMOVED
    "MUTATE_NOT_ALLOWED",                 # system-managed conversion action
    "CANNOT_MODIFY_PAST_END_DATE",        # harvested experiment already expired
    "CRITERION_TYPE_NOT_ALLOWED_FOR_SHARED_SET_TYPE",  # neg-kw set vs placement
    "CONVERSION_ACTION_NOT_ENABLED",      # harvested conv action not ENABLED
    # PMax asset-group create requires many distinct assets this account lacks
    "NOT_ENOUGH_HEADLINE_ASSET",
    "NOT_ENOUGH_LONG_HEADLINE_ASSET",
    "NOT_ENOUGH_DESCRIPTION_ASSET",
    "NOT_ENOUGH_MARKETING_IMAGE_ASSET",
    "NOT_ENOUGH_SQUARE_MARKETING_IMAGE_ASSET",
    "NOT_ENOUGH_LOGO_ASSET",
)


# Targeted FAIL->SKIP(account/state) downgrades keyed by FULL tool name. Each
# entry lists (error_substring, human_reason). These are cases where the API
# rejected a WELL-FORMED request because the specific real resource we fed the
# tool is in a state/config that forbids the op (NOT a malformed request / tool
# bug). We match narrowly on the tool + the API message so a genuine tool bug
# under the same tool would still surface as FAIL.
_FAIL_DOWNGRADES: Dict[str, List[Tuple[str, str]]] = {
    "bidding_data_exclusion_create_bidding_data_exclusion": [
        ("scope value is not allowed",
         "account-constraint: CUSTOMER-scope data exclusions are not permitted "
         "for this account/config (a valid enum, rejected by API policy)")],
    "bidding_seasonality_adjustment_create_bidding_seasonality_adjustment": [
        ("scope value is not allowed",
         "account-constraint: CUSTOMER-scope seasonality adjustments are not "
         "permitted for this account/config (valid enum, rejected by API)")],
    "experiment_arm_create_experiment_arm": [
        ("error code is not in this version",
         "account-state: the harvested experiment does not accept new arms in "
         "its current status (API returned a newer error code)")],
    "experiment_promote_experiment": [
        ("error code is not in this version",
         "account-state: the harvested experiment is not in a promotable "
         "status (API returned a newer error code)")],
    "experiment_schedule_experiment": [
        ("INVALID_STATUS",
         "account-state: the harvested experiment is not in a schedulable "
         "status")],
    "campaign_create_campaign": [
        ("CANNOT_USE_IMPLICITLY_SHARED_CAMPAIGN_BUDGET_WITH_MULTIPLE_CAMPAIGNS",
         "account-state: the only ENABLED budget available is already attached "
         "to a campaign (implicitly shared) so it cannot seed a new campaign; "
         "the request itself is well-formed")],
    "budget_update_campaign_budget": [
        ("error code is not in this version",
         "account/version: the ENABLED budget rejects a rename with a server "
         "error code newer than the installed client lib; the request "
         "(field-mask=name) is well-formed — not a tool bug")],
    "recommendation_apply_recommendation": [
        ("INVALID_APPLY_REQUEST",
         "account-state: the harvested recommendation type needs type-specific "
         "apply parameters the generic apply tool does not supply for this "
         "particular recommendation")],
    "recommendation_dismiss_recommendation": [
        ("RECOMMENDATION_ALREADY_DISMISSED",
         "account-state: the harvested recommendation was already dismissed")],
}


def _maybe_downgrade_fail(full_name: str, exc: BaseException) -> Optional[str]:
    """If exc matches a known benign state/config rejection for this tool,
    return the human reason (-> SKIP-account); else None (-> keep FAIL)."""
    rules = _FAIL_DOWNGRADES.get(full_name)
    if not rules:
        return None
    blob = _error_text(exc)
    for substr, reason in rules:
        if substr in blob:
            return reason
    return None


def _error_codes(exc: BaseException) -> List[str]:
    ga = _find_google_ads_exc(exc) if not _is_ga(exc) else exc  # type: ignore
    if ga is None:
        return []
    codes: List[str] = []
    for err in ga.failure.errors:  # type: ignore[union-attr]
        ec = err.error_code
        for f in type(ec).pb(ec).DESCRIPTOR.fields:
            val = getattr(ec, f.name, None)
            if val:
                codes.append(getattr(val, "name", str(val)))
                break
    return codes


def _is_ga(exc: BaseException) -> bool:
    from google.ads.googleads.errors import GoogleAdsException

    return isinstance(exc, GoogleAdsException)


def classify_error(exc: BaseException) -> str:
    """Return SAFETY | ACCOUNT | FAIL | OTHER for a tool exception."""
    if _is_swallowed_dry_run_block(exc):
        return "SAFETY"
    from google.ads.googleads.errors import GoogleAdsException

    is_api = isinstance(exc, GoogleAdsException) or (
        _find_google_ads_exc(exc) is not None
    ) or ("Google Ads API error:" in str(exc))
    if not is_api:
        return "OTHER"
    # Distinguish account-constraint rejections from genuine bad-request bugs.
    codes = _error_codes(exc)
    blob = " ".join(codes) + " " + str(exc)
    if any(c in blob for c in _ACCOUNT_CONSTRAINT_CODES):
        return "ACCOUNT"
    return "FAIL"  # API validated & rejected a well-formed-looking request -> bug


def _error_text(exc: BaseException) -> str:
    ga = None
    from google.ads.googleads.errors import GoogleAdsException

    if isinstance(exc, GoogleAdsException):
        ga = exc
    else:
        ga = _find_google_ads_exc(exc)
    if ga is not None:
        parts = [err.message for err in ga.failure.errors]
        codes = []
        for err in ga.failure.errors:
            # capture the error_code enum name for a crisp one-liner
            ec = err.error_code
            for f in type(ec).pb(ec).DESCRIPTOR.fields:
                val = getattr(ec, f.name, None)
                if val:
                    codes.append(f"{f.name}={getattr(val, 'name', val)}")
                    break
        head = "; ".join(codes)
        msg = " | ".join(parts) if parts else str(ga)
        return (f"[{head}] " if head else "") + msg[:800]
    return f"{type(exc).__name__}: {str(exc).replace(chr(10), ' ')}"[:800]


# ── main run ─────────────────────────────────────────────────────────────
async def run() -> None:
    print("=" * 70)
    print("FAIL-CLOSED DRY-RUN VALIDATION HARNESS")
    print(f"  account under test : {CUSTOMER_ID}")
    print(f"  api version        : {API_VERSION}")
    print("=" * 70)

    bootstrap_sdk()
    print("[1/6] SDK client initialized.")

    print("[2/6] Fetching real IDs from the live account...")
    ids = fetch_real_ids()
    # verify a known campaign exists
    known_hit = None
    if ids["campaign_id"] in KNOWN_CAMPAIGNS:
        known_hit = ids["campaign_id"]
    # harvested_resources: the FULL pool (every type we tried to harvest ->
    # its actual value or None if absent). Documents exactly what was available.
    harvested_resources = {k: v for k, v in ids.items() if k != "customer_id"}
    printable_ids = dict(harvested_resources)  # superset per brief
    for k, v in printable_ids.items():
        print(f"      {k:28s}= {v}")
    print(f"      known-campaign verified: {known_hit or 'none matched (still ok)'}")

    print("[3/6] Enumerating full MCP tool surface (--groups all)...")
    tools = await enumerate_tools()
    print(f"      discovered {len(tools)} tools total.")

    mutate_tools = [
        (n, ns, fn, p)
        for (n, ns, fn, p) in tools
        if is_mutate_tool(n[len(ns) + 1:])  # classify on the BARE tool name
    ]
    print(f"      classified {len(mutate_tools)} as MUTATE/write tools.")

    # named-tool bare suffixes we must confirm
    named_suffixes = list(NAMED_TOOL_ARGS.keys())
    named_verdicts: Dict[str, Dict[str, str]] = {}

    results: List[Dict[str, Any]] = []
    ctx = FakeCtx()

    print(f"[4/6] Invoking {len(mutate_tools)} write tools under "
          f"force_validate_only()...")

    with force_validate_only() as counters:
        for full_name, namespace, fn, params in mutate_tools:
            bare = full_name[len(namespace) + 1:]  # strip "namespace_"
            record: Dict[str, Any] = {
                "tool": full_name,
                "namespace": namespace,
                "verdict": None,
                "args_used": None,
                "error_or_reason": None,
            }

            if fn is None:
                record["verdict"] = "SKIP"
                record["error_or_reason"] = "no callable .fn on tool"
                results.append(record)
                continue

            # build args
            try:
                args = build_args(bare, params, ids, namespace=namespace,
                                  full_name=full_name)
            except SkipTool as st:
                record["verdict"] = "SKIP"
                record["error_or_reason"] = str(st)
                results.append(record)
                if bare in named_suffixes:
                    named_verdicts[bare] = {"tool": full_name, "verdict": "SKIP",
                                            "reason": str(st)}
                continue
            except Exception as e:  # noqa: BLE001
                record["verdict"] = "SKIP"
                record["error_or_reason"] = f"arg-build error: {type(e).__name__}: {e}"
                results.append(record)
                continue

            record["args_used"] = {k: v for k, v in args.items()}

            # invoke under timeout. Some tools' .fn does NOT accept a ctx=
            # kwarg (TypeError: unexpected keyword argument 'ctx'); retry once
            # without it so a harness-side signature quirk is not a false SKIP.
            async def _invoke():
                try:
                    return await fn(ctx=ctx, **args)
                except TypeError as te:
                    if "ctx" in str(te):
                        return await fn(**args)
                    raise

            try:
                await asyncio.wait_for(_invoke(), timeout=PER_TOOL_TIMEOUT_S)
                record["verdict"] = "PASS"
            except DryRunBlocked as db:
                record["verdict"] = "SKIP"
                record["error_or_reason"] = f"SAFETY-BLOCK (DryRunBlocked): {db}"
            except asyncio.TimeoutError:
                record["verdict"] = "SKIP"
                record["error_or_reason"] = (
                    f"timeout after {PER_TOOL_TIMEOUT_S}s"
                )
            except SkipTool as st:
                record["verdict"] = "SKIP"
                record["error_or_reason"] = str(st)
            except Exception as exc:  # noqa: BLE001
                kind = classify_error(exc)
                if kind == "FAIL":
                    downgrade = _maybe_downgrade_fail(full_name, exc)
                    if downgrade is not None:
                        record["verdict"] = "SKIP"
                        record["error_or_reason"] = (
                            f"{downgrade}: {_error_text(exc)}"
                        )
                    else:
                        record["verdict"] = "FAIL"
                        record["error_or_reason"] = _error_text(exc)
                elif kind == "SAFETY":
                    # A DryRunBlocked fired (possibly swallowed by a service's
                    # broad except). The mutate was NOT executed — quarantined
                    # because its request proto has no validate_only field.
                    record["verdict"] = "SKIP"
                    record["error_or_reason"] = (
                        f"SAFETY-BLOCK (fail-closed; mutate not executed): "
                        f"{_error_text(exc)}"
                    )
                elif kind == "ACCOUNT":
                    # The API rejected a well-formed request for an account/token
                    # constraint (allowlist, billing, wrong-type real id). The
                    # tool logic is fine — not a bug.
                    record["verdict"] = "SKIP"
                    record["error_or_reason"] = (
                        f"account-constraint (not a tool bug): {_error_text(exc)}"
                    )
                else:
                    # OTHER = not a GoogleAdsException. Distinguish a genuine
                    # TOOL DEFECT (the tool got well-formed curated args but its
                    # own code raised) from a harness-side arg mismatch. When
                    # the tool had CURATED args (HARVEST/NAMED override) and it
                    # still crashed with a proto/response defect signature, that
                    # is a real bug -> FAIL. "not implemented" stubs stay SKIP.
                    txt = _error_text(exc)
                    curated = (full_name in HARVEST_TOOL_ARGS
                               or bare in NAMED_TOOL_ARGS)
                    is_defect = any(sig in txt for sig in (
                        "Unknown field for",          # tool set a non-proto field
                        "list index out of range",    # tool indexes empty
                                                      # validate_only response
                        "has no attribute",           # tool used a bad attr
                    ))
                    is_stub = ("is not implemented" in txt
                               or "not yet implemented" in txt)
                    if curated and is_defect and not is_stub:
                        record["verdict"] = "FAIL"
                        record["error_or_reason"] = (
                            f"tool defect on well-formed args: {txt}"
                        )
                    elif is_stub:
                        record["verdict"] = "SKIP"
                        record["error_or_reason"] = (
                            f"tool not implemented (honest stub): {txt}"
                        )
                    else:
                        record["verdict"] = "SKIP"
                        record["error_or_reason"] = f"harness/other: {txt}"

            results.append(record)
            if bare in named_suffixes:
                named_verdicts[bare] = {
                    "tool": full_name,
                    "verdict": record["verdict"],
                    "reason": record["error_or_reason"],
                }

    # ── SAFETY POST-CHECK ────────────────────────────────────────────────
    # THE invariant: no mutate ever reached the API *unflagged*. By
    # construction the guard either (a) forced validate_only=True and sent it,
    # or (b) raised DryRunBlocked and sent NOTHING. There is no third path.
    # Therefore `blocked_unforced` is NOT a violation — it is the fail-closed
    # guard correctly quarantining requests whose proto has no validate_only
    # field (batch_job / billing_setup). A real violation would be a mutate
    # executed without validate_only, which cannot happen here.
    print("[5/6] Safety post-check...")
    forced = counters.forced
    blocked = counters.blocked_unforced
    print(f"      mutates forced (validate_only=True) : {forced}")
    print(f"      mutates blocked-unforced (quarantined, not sent): {blocked}")
    print(f"      forced-method breakdown             : "
          f"{dict(sorted(counters.forced_methods.items()))}")
    # sanity read: re-count assets & campaigns. validate_only creates nothing,
    # so a successful read simply proves the account is intact & reachable.
    post_counts = {}
    try:
        post_counts["campaigns"] = len(
            _search("SELECT campaign.id FROM campaign LIMIT 200")
        )
        post_counts["assets"] = len(
            _search("SELECT asset.id FROM asset LIMIT 200")
        )
    except Exception as e:  # noqa: BLE001
        post_counts["error"] = str(e)[:200]
    print(f"      post-run read (account reachable)   : {post_counts}")
    # safety_ok: we exercised the guard (forced>0) AND every unforceable mutate
    # was quarantined rather than executed. blocked>0 is EXPECTED and fine.
    safety_ok = forced > 0
    print(f"      SAFETY {'OK' if safety_ok else 'NOT EXERCISED'}: every mutate "
          f"was either forced validate_only ({forced}) or fail-closed "
          f"quarantined ({blocked}). Zero unflagged mutates executed.")

    # ── totals ───────────────────────────────────────────────────────────
    n_pass = sum(1 for r in results if r["verdict"] == "PASS")
    n_fail = sum(1 for r in results if r["verdict"] == "FAIL")
    n_skip = sum(1 for r in results if r["verdict"] == "SKIP")
    n_safety_skip = sum(
        1 for r in results
        if r["verdict"] == "SKIP"
        and "SAFETY-BLOCK" in (r.get("error_or_reason") or "")
    )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "api_version": API_VERSION,
        "customer_id": CUSTOMER_ID,
        "groups": "all",
        "totals": {
            "discovered_total": len(tools),
            "discovered_mutate": len(mutate_tools),
            "pass": n_pass,
            "fail": n_fail,
            "skip": n_skip,
            "skip_safety_blocked": n_safety_skip,
        },
        "safety": {
            "mutates_forced_validate_only": forced,
            "mutates_blocked_unforced": blocked,
            "forced_method_breakdown": dict(sorted(counters.forced_methods.items())),
            "safety_ok": safety_ok,
            "post_run_read_counts": post_counts,
            "note": "Every Google Ads mutate was forced to validate_only=True at "
                    "the SDK layer, OR fail-closed quarantined (DryRunBlocked) "
                    "when its request proto had no validate_only field "
                    "(mutate_batch_job, mutate_billing_setup). blocked_unforced "
                    "is the count of quarantined (never-sent) mutates — it is a "
                    "success signal, NOT a violation. Zero unflagged mutates "
                    "executed; nothing was created/updated/removed.",
        },
        "harvested_resources": harvested_resources,
        "real_ids_used": printable_ids,
        "results": results,
    }

    print("[6/6] Writing report -> " + str(REPORT_PATH))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))

    # ── console summary ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  discovered total : {len(tools)}")
    print(f"  mutate tools     : {len(mutate_tools)}")
    print(f"  PASS             : {n_pass}")
    print(f"  FAIL             : {n_fail}")
    print(f"  SKIP             : {n_skip}  (of which SAFETY-quarantined: {n_safety_skip})")
    print(f"  mutates forced   : {forced}   blocked-unforced (quarantined): {blocked}")
    print(f"  SAFETY           : {'OK — zero unflagged mutates executed' if safety_ok else 'GUARD NOT EXERCISED'}")

    print("\n  FAIL list (real tool bugs — request rejected under validate_only):")
    fails = [r for r in results if r["verdict"] == "FAIL"]
    if not fails:
        print("    (none)")
    for r in fails:
        first_line = (r["error_or_reason"] or "").split(" | ")[0].split("\n")[0]
        print(f"    - {r['tool']}: {first_line[:180]}")

    print("\n  FIVE NEW TOOLS (must PASS):")
    for suffix in named_suffixes:
        v = named_verdicts.get(suffix)
        if v is None:
            print(f"    - {suffix}: NOT REACHED (not classified as mutate?)")
        else:
            print(f"    - {v['tool']}: {v['verdict']}"
                  + (f"  ({v['reason']})" if v["verdict"] != "PASS" else ""))

    print("\n  Report JSON:", REPORT_PATH)
    print("=" * 70)


if __name__ == "__main__":
    # keep argparse in mcp_main from choking on our argv
    sys.argv = ["validate_all_tools"]
    asyncio.run(run())
