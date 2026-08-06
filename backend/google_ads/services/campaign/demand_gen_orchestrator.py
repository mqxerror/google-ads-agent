"""Demand Gen campaign creation — single-shot orchestrator.

Sequences the operations needed to stand up a working Demand Gen campaign
with one ad group and a multi-asset ad. Like PMax, Demand Gen needs a
*recipe*, not a single API call:

    1. CampaignBudget
    2. Campaign (advertising_channel_type=DEMAND_GEN)
    3. Geo + language targeting (campaign criteria)
    4. Image assets (marketing / square / portrait / logo) — local uploads
       are pushed to Google as image assets; Google asset refs pass through
    5. AdGroup — Demand Gen's channel controls live HERE, not on the
       campaign: `ad_group.demand_gen_ad_group_settings.channel_controls
       .selected_channels` toggles YouTube (in-stream / in-feed / shorts),
       Discover, Gmail, and Display individually. THE WHOLE POINT of this
       surface is being able to turn Gmail OFF while leaving Display ON.
    6. AdGroupAd — a DemandGenMultiAssetAdInfo carrying inline text
       (headlines / descriptions / business_name / CTA) plus AdImageAsset
       references to the uploaded image assets
    7. (Optional) audience criteria — customer-match list EXCLUSION
       (negative user_list) + custom-segment / customer-match INCLUSION
       (positive user_list) as ad-group criteria

Steps are sequential per-service calls for debuggability, matching the PMax
orchestrator's style. Unlike PMax's asset groups, Demand Gen ad groups have
no "minimum assets at creation" constraint, so the ad group and its ad are
created in separate calls. If any step fails, prior creations are removed so
the user never sees half a campaign in their Google Ads UI. Pre-flight
validation catches Google's hard minimums (and rejects off-aspect images)
before we hit the wire.

CHANNEL-CONTROL SDK NOTE (verified against google-ads v23, 2026-07-28): the
campaign-level `Campaign.DemandGenCampaignSettings` exposes ONLY
`upgraded_targeting` — it has NO channel controls. The Gmail/Display/Discover/
YouTube toggles are exclusively at the AD GROUP level on
`AdGroup.DemandGenAdGroupSettings.DemandGenChannelControls.selected_channels`
(bool fields: youtube_in_stream, youtube_in_feed, youtube_shorts, discover,
gmail, display). `selected_channels` is a member of the `channel_configuration`
oneof (mutually exclusive with `channel_strategy`), so setting explicit
channels means we do NOT also set a high-level strategy.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastmcp import Context, FastMCP
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v23.common.types import MaximizeConversions
from google.ads.googleads.v23.common.types.ad_asset import AdImageAsset, AdTextAsset
from google.ads.googleads.v23.common.types.ad_type_infos import (
    DemandGenMultiAssetAdInfo,
)
from google.ads.googleads.v23.common.types.criteria import UserListInfo
from google.ads.googleads.v23.enums.types.ad_group_ad_status import (
    AdGroupAdStatusEnum,
)
from google.ads.googleads.v23.enums.types.ad_group_criterion_status import (
    AdGroupCriterionStatusEnum,
)
from google.ads.googleads.v23.enums.types.ad_group_status import AdGroupStatusEnum
from google.ads.googleads.v23.enums.types.advertising_channel_type import (
    AdvertisingChannelTypeEnum,
)
from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
from google.ads.googleads.v23.resources.types.ad import Ad
from google.ads.googleads.v23.resources.types.ad_group import AdGroup
from google.ads.googleads.v23.resources.types.ad_group_ad import AdGroupAd
from google.ads.googleads.v23.resources.types.ad_group_criterion import (
    AdGroupCriterion,
)
from google.ads.googleads.v23.resources.types.campaign import Campaign
from google.ads.googleads.v23.services.types.ad_group_ad_service import (
    AdGroupAdOperation,
    MutateAdGroupAdsRequest,
)
from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
    AdGroupCriterionOperation,
    MutateAdGroupCriteriaRequest,
)
from google.ads.googleads.v23.services.types.ad_group_service import (
    AdGroupOperation,
    MutateAdGroupsRequest,
)
from google.ads.googleads.v23.services.types.ad_service import (
    AdOperation,
    MutateAdsRequest,
)
from google.ads.googleads.v23.services.types.campaign_service import (
    CampaignOperation,
    MutateCampaignsRequest,
)
from google.protobuf import field_mask_pb2

from google_ads.sdk_client import get_sdk_client
from google_ads.services.assets.asset_service import AssetService
from google_ads.services.bidding.budget_service import BudgetService
from google_ads.services.conversions.conversion_goal_setup import (
    apply_bundle_conversion_goal,
)
from google_ads.services.campaign import creative_images
from google_ads.services.campaign.campaign_service import CampaignService
from google_ads.services.campaign.campaign_criterion_service import (
    CampaignCriterionService,
)
from google_ads.services.campaign.pmax_orchestrator import ApiCtx  # noqa: F401 (re-export)
from google_ads.utils import format_customer_id, get_logger, serialize_proto_message

# Creative Spec Registry — DG limits are read from here, not a local table (F1).
from app.services import creative_specs
from app.services.creative_specs import CampaignSpec, ValidationReport  # noqa: F401

logger = get_logger(__name__)

# `_locate_local_image` kept as a module global (not a direct import) so unit
# tests can monkeypatch `demand_gen_orchestrator._locate_local_image` exactly
# the way they patch the PMax one; `_resolve_image_plan` passes this global
# into the shared resolver so the patch takes effect.
_locate_local_image = creative_images.locate_local_image

# Demand Gen creative limits (counts, char caps, business-name + logo caps) now
# come from the Creative Spec Registry (creative_specs.get("demand_gen")), not a
# local constant table (Epic 14, fence F1). The DG headline cap is 40 chars
# [research §3-Q1 DEFINITIVE] — served from ONE place so it can never drift.

# Slot → DemandGenMultiAssetAdInfo repeated-field name. Each slot's images are
# AdImageAsset references pointing at uploaded image assets.
IMAGE_SLOT_TO_AD_FIELD = {
    "logos": "logo_images",
    "landscape": "marketing_images",             # 1.91:1
    "square": "square_marketing_images",         # 1:1
    "portrait": "portrait_marketing_images",     # 4:5
    "tall_portrait": "tall_portrait_marketing_images",  # 9:16
}

# The six explicitly-selectable Demand Gen channels, in a stable order. Keys
# match `DemandGenSelectedChannels` bool field names. Defaults chosen so the
# out-of-the-box campaign is the "Gmail OFF, everything else ON" shape this
# surface exists to produce.
CHANNEL_FIELDS = (
    "youtube_in_stream",
    "youtube_in_feed",
    "youtube_shorts",
    "discover",
    "gmail",
    "display",
)
DEFAULT_CHANNELS = {
    "youtube_in_stream": True,
    "youtube_in_feed": True,
    "youtube_shorts": True,
    "discover": True,
    "gmail": False,   # OFF by default — the whole point of this surface
    "display": True,
}

# How an image-refresh call folds NEW refs into a live ad. `replace` swaps the
# slot's image list wholesale (the reject-the-AI-creative → push-my-own-photos
# flow); `append` keeps the ad's current images and adds the new ones after
# them (A/B a variant without dropping the incumbent). Only the slots the
# caller supplies refs for are touched — untouched slots keep their live value.
UPDATE_MODES = ("replace", "append")


class DemandGenValidationError(Exception):
    """Raised when the input bundle doesn't meet Demand Gen's minimums.

    The orchestrator catches this and returns a structured error so the
    wizard / chat agent can highlight the specific fields to fix.
    """

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class DemandGenStepError(Exception):
    """Raised when the recipe dies partway through a Google API call.

    Carries exactly which step failed and what the rollback managed to
    clean up, so the API layer / wizard can show an actionable message
    instead of a bare Google error blob.
    """

    def __init__(self, step: str, original: Exception, rollback_report: List[str]):
        self.step = step
        self.original = original
        self.rollback_report = rollback_report
        cleanup = (
            " ".join(rollback_report)
            if rollback_report
            else "Nothing was rolled back — no Google Ads entities had been created yet."
        )
        super().__init__(
            f"Demand Gen create failed at step '{step}'. {cleanup} "
            f"Underlying error: {original}"
        )


class DemandGenAdUpdateError(Exception):
    """Raised when the in-place image update fails at the Google API call.

    Carries the operator-useful message so the REST route / chat agent can show
    it verbatim. No rollback is needed: an ad-image update is a single mutate
    that either lands or doesn't — a rejected request changes nothing live.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _extract_resource_name(mutate_response: Dict[str, Any]) -> str:
    """Pull the first result's resource_name from a serialized mutate response.

    All of the per-service `create_*` helpers return the response of
    `serialize_proto_message(response)`, which has shape
    `{"results": [{"resource_name": "customers/.../entities/123", ...}]}`.
    """
    results = mutate_response.get("results") or []
    if not results:
        raise RuntimeError(f"mutate response had no results: {mutate_response!r}")
    rn = results[0].get("resource_name")
    if not rn:
        raise RuntimeError(f"mutate response missing resource_name: {results[0]!r}")
    return rn


def _id_from_resource_name(resource_name: str) -> str:
    """`customers/123/campaigns/456` → `456`."""
    return resource_name.rsplit("/", 1)[-1]


def _normalize_channels(raw: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """Merge the caller's channel toggles over the defaults, coercing to
    bool and ignoring unknown keys."""
    channels = dict(DEFAULT_CHANNELS)
    for key, val in (raw or {}).items():
        if key in channels and val is not None:
            channels[key] = bool(val)
    return channels


def _validate_bundle(bundle: Dict[str, Any], spec: CampaignSpec) -> ValidationReport:
    """Pre-flight validation against the Creative Spec Registry (FR1.1).

    Returns a ``ValidationReport``: verified-limit violations are ``errors``
    (the create path raises), unverified (soft) ones are ``warnings``. Covers
    text counts/limits, business name, required logo + marketing-image presence,
    logo cap, and the channel-controls invariant (at least one channel ON — an
    all-OFF `selected_channels` is rejected by Google). Every limit is read from
    ``spec`` (fence F1). Image aspect/size is handled separately by
    `_resolve_image_plan`."""
    report = ValidationReport()

    if not bundle.get("name"):
        report.errors.append("campaign 'name' is required")
    if not bundle.get("budget_micros"):
        report.errors.append("'budget_micros' is required (1_000_000 micros = $1)")
    if not bundle.get("final_urls"):
        report.errors.append("'final_urls' is required (at least one URL)")

    creative_specs.check_business_name(bundle, spec, report)
    creative_specs.check_text_fields(bundle, spec, report)

    logo_spec = spec.logos["logos"]
    logos = bundle.get("logos") or []
    if not logos:
        report.errors.append("need ≥1 logo image (asset_id or upload)")
    elif len(logos) > logo_spec.max_count:
        report.errors.append(f"too many logos: {len(logos)} (max {logo_spec.max_count})")

    mi = bundle.get("marketing_images") or {}
    if not (mi.get("landscape") or mi.get("square")):
        report.errors.append(
            "need ≥1 marketing image — at least one of landscape (1.91:1) "
            "or square (1:1) is required"
        )

    channels = _normalize_channels(bundle.get("channels"))
    if not any(channels.values()):
        report.errors.append(
            "at least one channel must be enabled (all of gmail/display/"
            "discover/youtube_* are off) — an empty channel selection is "
            "rejected by Google"
        )

    return report


def _validate_update_bundle(bundle: Dict[str, Any]) -> None:
    """Pre-flight for an in-place ad-image update (no campaign create).

    Requires (a) a way to name the target ad — either ``ad_resource_name`` or
    both ``ad_group_id`` + ``ad_id`` — (b) a valid ``mode``, and (c) at least
    one image ref in at least one slot (an update that touches nothing is a
    caller mistake, not a no-op we should silently accept). Image aspect / size
    is verified separately by ``_resolve_image_plan`` at push time; logo count
    is capped here to mirror the create path.
    """
    errs: List[str] = []

    has_rn = bool(bundle.get("ad_resource_name"))
    has_pair = bool(bundle.get("ad_group_id") and bundle.get("ad_id"))
    if not (has_rn or has_pair):
        errs.append(
            "target ad is required — pass ad_resource_name "
            "(customers/<cid>/ads/<ad_id>) or both ad_group_id and ad_id"
        )

    mode = str(bundle.get("mode") or "replace").lower()
    if mode not in UPDATE_MODES:
        errs.append(f"mode must be one of {list(UPDATE_MODES)} (got {mode!r})")

    mi = bundle.get("marketing_images") or {}
    logos = bundle.get("logos") or []
    any_images = bool(
        logos
        or mi.get("landscape")
        or mi.get("square")
        or mi.get("portrait")
        or mi.get("tall_portrait")
    )
    if not any_images:
        errs.append(
            "provide at least one image ref in a slot (logos / landscape / "
            "square / portrait / tall_portrait) — nothing to update otherwise"
        )
    logo_max = creative_specs.get("demand_gen").logos["logos"].max_count
    if len(logos) > logo_max:
        errs.append(f"too many logos: {len(logos)} (max {logo_max})")

    if errs:
        raise DemandGenValidationError(errs)


class DemandGenOrchestrator:
    """The Demand Gen recipe. Holds references to each primitive service so
    it can sequence them and roll back on failure."""

    def __init__(self) -> None:
        self._budget = BudgetService()
        self._campaign = CampaignService()          # rollback (remove_campaign)
        self._campaign_criterion = CampaignCriterionService()
        self._asset = AssetService()
        self._campaign_client: Optional[Any] = None
        self._ad_group_client: Optional[Any] = None
        self._ad_group_ad_client: Optional[Any] = None
        self._ad_group_criterion_client: Optional[Any] = None
        self._ad_client: Optional[Any] = None
        self._google_ads: Optional[Any] = None

    # ── lazy SDK clients (same pattern as the per-resource services) ──────
    @property
    def campaign_client(self) -> Any:
        if self._campaign_client is None:
            self._campaign_client = get_sdk_client().client.get_service(
                "CampaignService"
            )
        return self._campaign_client

    @property
    def ad_group_client(self) -> Any:
        if self._ad_group_client is None:
            self._ad_group_client = get_sdk_client().client.get_service(
                "AdGroupService"
            )
        return self._ad_group_client

    @property
    def ad_group_ad_client(self) -> Any:
        if self._ad_group_ad_client is None:
            self._ad_group_ad_client = get_sdk_client().client.get_service(
                "AdGroupAdService"
            )
        return self._ad_group_ad_client

    @property
    def ad_group_criterion_client(self) -> Any:
        if self._ad_group_criterion_client is None:
            self._ad_group_criterion_client = get_sdk_client().client.get_service(
                "AdGroupCriterionService"
            )
        return self._ad_group_criterion_client

    @property
    def ad_client(self) -> Any:
        """AdService client — the in-place image update mutates the shared `Ad`
        resource (customers/<cid>/ads/<id>), NOT the AdGroupAd wrapper, so the
        same ad id / history / text survive (mirrors AdService.update_rsa_pins).
        """
        if self._ad_client is None:
            self._ad_client = get_sdk_client().client.get_service("AdService")
        return self._ad_client

    @property
    def google_ads_client(self) -> Any:
        if self._google_ads is None:
            self._google_ads = get_sdk_client().client.get_service("GoogleAdsService")
        return self._google_ads

    # ── image aspect verification (stubbable in tests) ───────────────────
    def _fetch_image_asset_dims(
        self, customer_id: str, resource_names: List[str]
    ) -> Dict[str, tuple[int, int]]:
        """GAQL lookup: full-size pixel dimensions for existing image assets,
        keyed by resource name. Assets not found / not IMAGE assets simply
        don't appear — the caller treats "missing" as "aspect can't be
        verified" and rejects pre-flight. Isolated so unit tests can stub it
        without a live SDK client."""
        if not resource_names:
            return {}
        quoted = ", ".join(f"'{rn}'" for rn in resource_names)
        query = (
            "SELECT asset.resource_name, "
            "asset.image_asset.full_size.width_pixels, "
            "asset.image_asset.full_size.height_pixels "
            f"FROM asset WHERE asset.resource_name IN ({quoted})"
        )
        dims: Dict[str, tuple[int, int]] = {}
        for row in self.google_ads_client.search(
            customer_id=customer_id, query=query
        ):
            w = int(row.asset.image_asset.full_size.width_pixels or 0)
            h = int(row.asset.image_asset.full_size.height_pixels or 0)
            if w and h:
                dims[row.asset.resource_name] = (w, h)
        return dims

    def _fetch_current_ad_images(
        self, customer_id: str, ad_id: str
    ) -> Dict[str, List[str]]:
        """Read the live DemandGenMultiAssetAd's current image asset resource
        names, keyed by the abstract slot names in ``IMAGE_SLOT_TO_AD_FIELD``.

        Only used by ``mode='append'`` — replace never needs the incumbents.
        Isolated (like ``_fetch_image_asset_dims``) so unit tests can stub it
        without a live SDK client. Returns every slot with a (possibly empty)
        list so callers can index safely.
        """
        out: Dict[str, List[str]] = {slot: [] for slot in IMAGE_SLOT_TO_AD_FIELD}
        fields = ", ".join(
            f"ad_group_ad.ad.demand_gen_multi_asset_ad.{field_name}"
            for field_name in IMAGE_SLOT_TO_AD_FIELD.values()
        )
        query = (
            f"SELECT {fields} FROM ad_group_ad "
            f"WHERE ad_group_ad.ad.id = {ad_id} LIMIT 1"
        )
        for row in self.google_ads_client.search(
            customer_id=customer_id, query=query
        ):
            info = row.ad_group_ad.ad.demand_gen_multi_asset_ad
            for slot, field_name in IMAGE_SLOT_TO_AD_FIELD.items():
                out[slot] = [
                    img.asset for img in getattr(info, field_name) if img.asset
                ]
            break
        return out

    async def _resolve_image_plan(
        self, customer_id: str, bundle: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Classify + crop + aspect-verify every image ref pre-flight. Thin
        wrapper over the shared `creative_images.resolve_image_plan` (same
        logic PMax uses). `_locate_local_image` is passed as the module
        global so tests can monkeypatch it."""
        mi = bundle.get("marketing_images") or {}
        slots = {
            "logos": list(bundle.get("logos") or []),
            "landscape": list(mi.get("landscape") or []),
            "square": list(mi.get("square") or []),
            "portrait": list(mi.get("portrait") or []),
            "tall_portrait": list(mi.get("tall_portrait") or []),
        }
        return await creative_images.resolve_image_plan(
            customer_id=customer_id,
            slots=slots,
            fetch_dims=self._fetch_image_asset_dims,
            error_factory=DemandGenValidationError,
            locate=_locate_local_image,
        )

    # ── direct-build steps (protos the generic services can't express) ────
    def _create_campaign_resource(
        self,
        customer_id: str,
        name: str,
        budget_rn: str,
        target_cpa_micros: Optional[int],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> str:
        """Create the DEMAND_GEN campaign (PAUSED) and return its resource
        name. Bidding is MaximizeConversions, optionally with a target CPA.

        Network settings are intentionally NOT set — Google manages Demand
        Gen inventory automatically (same as PMax). `upgraded_targeting` is
        set False so location/language targeting is applied at the CAMPAIGN
        level via CampaignCriterionService (the well-supported path in this
        codebase); with the default True, targeting would move to the ad
        group.
        """
        campaign = Campaign()
        campaign.name = name
        campaign.campaign_budget = budget_rn
        campaign.advertising_channel_type = (
            AdvertisingChannelTypeEnum.AdvertisingChannelType.DEMAND_GEN
        )
        # Start PAUSED so the user reviews the ad + channels before spend.
        campaign.status = CampaignStatusEnum.CampaignStatus.PAUSED

        # EU political advertising compliance (required on create in v23).
        # 3 = DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING.
        campaign.contains_eu_political_advertising = 3

        # Campaign-level targeting (see docstring).
        try:
            campaign.demand_gen_campaign_settings.upgraded_targeting = False
        except AttributeError:
            pass

        maximize_conv = MaximizeConversions()
        if target_cpa_micros:
            maximize_conv.target_cpa_micros = int(target_cpa_micros)
        campaign.maximize_conversions = maximize_conv

        if start_date:
            campaign.start_date = start_date.replace("-", "")
        if end_date:
            campaign.end_date = end_date.replace("-", "")

        op = CampaignOperation()
        op.create = campaign
        request = MutateCampaignsRequest()
        request.customer_id = customer_id
        request.operations = [op]
        try:
            resp = self.campaign_client.mutate_campaigns(request=request)
        except GoogleAdsException as e:
            raise Exception(f"Google Ads API error: {e.failure}") from e
        return _extract_resource_name(serialize_proto_message(resp))

    def _create_ad_group_resource(
        self,
        customer_id: str,
        campaign_rn: str,
        name: str,
        channels: Dict[str, bool],
    ) -> str:
        """Create the Demand Gen ad group with explicit channel controls and
        return its resource name.

        The ad group `type` is deliberately left UNSET: v23's AdGroupType
        enum has no DEMAND_GEN member (verified 2026-07-28), and Google
        infers the type from the DEMAND_GEN campaign. The channel toggles
        are set on `demand_gen_ad_group_settings.channel_controls
        .selected_channels`, which is the `channel_configuration` oneof —
        setting explicit channels means NOT setting a high-level strategy.
        """
        ad_group = AdGroup()
        ad_group.name = name
        ad_group.campaign = campaign_rn
        ad_group.status = AdGroupStatusEnum.AdGroupStatus.ENABLED

        selected = (
            ad_group.demand_gen_ad_group_settings.channel_controls.selected_channels
        )
        for field in CHANNEL_FIELDS:
            setattr(selected, field, bool(channels.get(field, False)))

        op = AdGroupOperation()
        op.create = ad_group
        request = MutateAdGroupsRequest()
        request.customer_id = customer_id
        request.operations = [op]
        try:
            resp = self.ad_group_client.mutate_ad_groups(request=request)
        except GoogleAdsException as e:
            raise Exception(f"Google Ads API error: {e.failure}") from e
        return _extract_resource_name(serialize_proto_message(resp))

    def _build_multi_asset_ad(
        self,
        bundle: Dict[str, Any],
        asset_rns_by_slot: Dict[str, List[str]],
    ) -> Ad:
        """Assemble the Ad carrying a DemandGenMultiAssetAdInfo: inline text
        (headlines / descriptions / business_name / CTA) + AdImageAsset
        references to the uploaded image assets."""
        info = DemandGenMultiAssetAdInfo()
        info.business_name = bundle["business_name"]
        for h in bundle["headlines"]:
            info.headlines.append(AdTextAsset(text=h))
        for d in bundle["descriptions"]:
            info.descriptions.append(AdTextAsset(text=d))
        cta = bundle.get("call_to_action_text")
        if cta:
            info.call_to_action_text = str(cta)

        for slot, field_name in IMAGE_SLOT_TO_AD_FIELD.items():
            rns = asset_rns_by_slot.get(slot) or []
            repeated = getattr(info, field_name)
            for rn in rns:
                repeated.append(AdImageAsset(asset=rn))

        ad = Ad()
        ad.final_urls.extend(bundle["final_urls"])
        if bundle.get("final_mobile_urls"):
            ad.final_mobile_urls.extend(bundle["final_mobile_urls"])
        ad.demand_gen_multi_asset_ad = info
        return ad

    def _create_ad_group_ad_resource(
        self, customer_id: str, ad_group_rn: str, ad: Ad
    ) -> str:
        """Create the AdGroupAd (ENABLED) wrapping the multi-asset ad and
        return its resource name."""
        ad_group_ad = AdGroupAd()
        ad_group_ad.ad_group = ad_group_rn
        ad_group_ad.status = AdGroupAdStatusEnum.AdGroupAdStatus.ENABLED
        ad_group_ad.ad = ad

        op = AdGroupAdOperation()
        op.create = ad_group_ad
        request = MutateAdGroupAdsRequest()
        request.customer_id = customer_id
        request.operations = [op]
        try:
            resp = self.ad_group_ad_client.mutate_ad_group_ads(request=request)
        except GoogleAdsException as e:
            raise Exception(f"Google Ads API error: {e.failure}") from e
        return _extract_resource_name(serialize_proto_message(resp))

    def _attach_audience_criteria(
        self,
        customer_id: str,
        ad_group_rn: str,
        included_user_list_ids: List[str],
        excluded_user_list_ids: List[str],
    ) -> int:
        """Attach user-list audience criteria to the ad group.

        Included lists (custom segments / customer-match INCLUSION) become
        positive criteria; excluded lists (customer-match EXCLUSION) become
        negative criteria (`ad_group_criterion.negative = True`). Returns the
        number of criteria attached. Raises on API failure so the caller can
        log a warning (audience attach is best-effort — the campaign is valid
        without it).
        """
        ops: List[AdGroupCriterionOperation] = []
        for uid in included_user_list_ids:
            crit = AdGroupCriterion()
            crit.ad_group = ad_group_rn
            crit.status = AdGroupCriterionStatusEnum.AdGroupCriterionStatus.ENABLED
            crit.user_list = UserListInfo(
                user_list=f"customers/{customer_id}/userLists/{uid}"
            )
            op = AdGroupCriterionOperation()
            op.create = crit
            ops.append(op)
        for uid in excluded_user_list_ids:
            crit = AdGroupCriterion()
            crit.ad_group = ad_group_rn
            crit.negative = True  # customer-match / audience EXCLUSION
            crit.user_list = UserListInfo(
                user_list=f"customers/{customer_id}/userLists/{uid}"
            )
            op = AdGroupCriterionOperation()
            op.create = crit
            ops.append(op)
        if not ops:
            return 0
        request = MutateAdGroupCriteriaRequest()
        request.customer_id = customer_id
        request.operations = ops
        try:
            self.ad_group_criterion_client.mutate_ad_group_criteria(request=request)
        except GoogleAdsException as e:
            raise Exception(f"Google Ads API error: {e.failure}") from e
        return len(ops)

    async def _upload_images(
        self,
        ctx: Context,
        customer_id: str,
        name: str,
        image_plan: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[str]]:
        """Bridge local upload UUIDs to Google image-asset resource names,
        passing pre-existing Google asset refs through unchanged.

        Dedup is keyed by (ref, slot aspect) — NOT ref alone — so the same
        source image filling two different-aspect slots uploads once per crop
        (keying by ref alone would reuse the first slot's crop for a later
        different-aspect slot, the ASPECT_RATIO_NOT_ALLOWED class of bug hit
        live on PMax 2026-06-11).
        """
        uploaded: Dict[tuple[str, float], str] = {}
        asset_rns_by_slot: Dict[str, List[str]] = {}
        for slot, entries in image_plan.items():
            rns: List[str] = []
            for n, entry in enumerate(entries):
                if entry["kind"] == "google":
                    rns.append(
                        creative_images.asset_resource_name(customer_id, entry["ref"])
                    )
                    continue
                dedupe_key = (
                    entry["ref"],
                    creative_images.IMAGE_SLOT_SPECS[slot]["aspect"],
                )
                if dedupe_key not in uploaded:
                    img_resp = await self._asset.create_image_asset(
                        ctx=ctx,
                        customer_id=customer_id,
                        image_data=entry.get("data") or entry["path"].read_bytes(),
                        name=f"{name} — {slot} {n + 1}",
                        mime_type=entry["mime"],
                    )
                    uploaded[dedupe_key] = _extract_resource_name(img_resp)
                rns.append(uploaded[dedupe_key])
            asset_rns_by_slot[slot] = rns
        if uploaded:
            await ctx.log(
                level="info",
                message=(
                    f"[DemandGen] Uploaded {len(uploaded)} local image(s) to "
                    f"Google Ads as image assets"
                ),
            )
        return asset_rns_by_slot

    async def create_demand_gen_campaign(
        self,
        ctx: Context,
        customer_id: str,
        bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a Demand Gen campaign from a complete bundle.

        See the module docstring for the operation sequence. Returns:
            {
                "campaign_id": str,
                "budget_id": str,
                "ad_group_id": str,
                "ad_group_ad_id": str,
                "channels": {<channel>: bool, ...},
                "image_asset_ids": {<slot>: [str, ...], ...},
                "warnings": [str, ...]
            }

        Raises DemandGenValidationError pre-flight; DemandGenStepError on any
        Google API failure (with prior creations rolled back).
        """
        spec = creative_specs.get("demand_gen")
        report = _validate_bundle(bundle, spec)
        if report.errors:
            raise DemandGenValidationError(report.errors)
        customer_id = format_customer_id(customer_id)
        channels = _normalize_channels(bundle.get("channels"))

        # Pre-flight: classify + crop + aspect-verify every image ref BEFORE
        # creating anything in Google.
        image_plan = await self._resolve_image_plan(customer_id, bundle)

        created_budget_rn: Optional[str] = None
        created_campaign_rn: Optional[str] = None
        # Soft-limit (verified:false) violations surface as warnings, never block.
        warnings: List[str] = list(report.warnings)
        failed_step = "pre-flight"

        try:
            # ── Step 1 — Budget ───────────────────────────────────────
            failed_step = "budget creation"
            await ctx.log(
                level="info",
                message=(
                    f"[DemandGen] Creating budget for '{bundle['name']}' at "
                    f"{bundle['budget_micros']} micros/day..."
                ),
            )
            budget_resp = await self._budget.create_campaign_budget(
                ctx=ctx,
                customer_id=customer_id,
                name=f"{bundle['name']} — budget",
                amount_micros=int(bundle["budget_micros"]),
            )
            created_budget_rn = _extract_resource_name(budget_resp)
            budget_id = _id_from_resource_name(created_budget_rn)

            # ── Step 2 — Campaign ─────────────────────────────────────
            failed_step = "campaign creation"
            await ctx.log(
                level="info", message="[DemandGen] Creating DEMAND_GEN campaign..."
            )
            created_campaign_rn = self._create_campaign_resource(
                customer_id=customer_id,
                name=bundle["name"],
                budget_rn=created_budget_rn,
                target_cpa_micros=bundle.get("target_cpa_micros"),
                start_date=bundle.get("start_date"),
                end_date=bundle.get("end_date"),
            )
            campaign_id = _id_from_resource_name(created_campaign_rn)

            # ── Step 2.5 — Conversion goal (optional; wizard/Director choice) ─
            # Pin the ONE chosen conversion action as the campaign's biddable
            # goal, right after the campaign exists. No-op when the operator kept
            # the account-default goals or made no choice. A failure here rolls
            # back the campaign + budget like any other step.
            failed_step = "conversion goal setup"
            await apply_bundle_conversion_goal(
                ctx, customer_id, campaign_id, bundle, warnings
            )

            # ── Step 3 — Geo + language targeting ─────────────────────
            failed_step = "geo/language targeting"
            location_ids = [str(x) for x in (bundle.get("location_ids") or [])]
            excluded_location_ids = [
                str(x) for x in (bundle.get("excluded_location_ids") or [])
            ]
            language_ids = [str(x) for x in (bundle.get("language_ids") or [])]
            if location_ids:
                await self._campaign_criterion.add_location_criteria(
                    ctx=ctx,
                    customer_id=customer_id,
                    campaign_id=campaign_id,
                    location_ids=location_ids,
                )
            if excluded_location_ids:
                # Negative location criteria — carve regions OUT of the geo
                # target (e.g. exclude the Dubai emirate while targeting the
                # UAE). Same CampaignCriterion path, `negative=True`.
                await self._campaign_criterion.add_location_criteria(
                    ctx=ctx,
                    customer_id=customer_id,
                    campaign_id=campaign_id,
                    location_ids=excluded_location_ids,
                    negative=True,
                )
            if language_ids:
                await self._campaign_criterion.add_language_criteria(
                    ctx=ctx,
                    customer_id=customer_id,
                    campaign_id=campaign_id,
                    language_ids=language_ids,
                )

            # ── Step 4 — Image assets (local upload → resource name) ──
            failed_step = "image asset upload"
            asset_rns_by_slot = await self._upload_images(
                ctx=ctx,
                customer_id=customer_id,
                name=bundle["name"],
                image_plan=image_plan,
            )

            # ── Step 5 — Ad group (with channel controls) ─────────────
            failed_step = "ad group creation"
            gmail_state = "OFF" if not channels["gmail"] else "ON"
            await ctx.log(
                level="info",
                message=(
                    f"[DemandGen] Creating ad group with channel controls "
                    f"(Gmail {gmail_state}, Display "
                    f"{'ON' if channels['display'] else 'OFF'})..."
                ),
            )
            ad_group_rn = self._create_ad_group_resource(
                customer_id=customer_id,
                campaign_rn=created_campaign_rn,
                name=f"{bundle['name']} — Ad Group 1",
                channels=channels,
            )
            ad_group_id = _id_from_resource_name(ad_group_rn)

            # ── Step 6 — Ad group ad (multi-asset ad) ─────────────────
            failed_step = "ad creation"
            ad = self._build_multi_asset_ad(bundle, asset_rns_by_slot)
            ad_group_ad_rn = self._create_ad_group_ad_resource(
                customer_id=customer_id, ad_group_rn=ad_group_rn, ad=ad
            )
            ad_group_ad_id = _id_from_resource_name(ad_group_ad_rn)

            # ── Step 7 — Audience criteria (optional, best-effort) ────
            failed_step = "audience criteria attachment"
            included = [str(x) for x in (bundle.get("audience_user_list_ids") or [])]
            excluded = [str(x) for x in (bundle.get("excluded_user_list_ids") or [])]
            if included or excluded:
                try:
                    n = self._attach_audience_criteria(
                        customer_id=customer_id,
                        ad_group_rn=ad_group_rn,
                        included_user_list_ids=included,
                        excluded_user_list_ids=excluded,
                    )
                    await ctx.log(
                        level="info",
                        message=(
                            f"[DemandGen] Attached {n} audience criterion(s) "
                            f"({len(included)} included, {len(excluded)} excluded)"
                        ),
                    )
                except Exception as e:
                    warnings.append(
                        f"audience criteria attach failed (campaign unaffected): {e}"
                    )

            await ctx.log(
                level="info",
                message=(
                    f"[DemandGen] OK — campaign_id={campaign_id} "
                    f"ad_group_id={ad_group_id} ad_group_ad_id={ad_group_ad_id}"
                ),
            )

            # ── Step 8 — Bring our own DB in agreement with reality ───
            failed_step = "post-create local sync"
            await self._post_create_sync(
                ctx=ctx,
                account_id=customer_id,
                campaign_id=campaign_id,
                bundle=bundle,
                channels=channels,
            )

            return {
                "campaign_id": campaign_id,
                "budget_id": budget_id,
                "ad_group_id": ad_group_id,
                "ad_group_ad_id": ad_group_ad_id,
                "channels": channels,
                "image_asset_ids": {
                    slot: [_id_from_resource_name(rn) for rn in rns]
                    for slot, rns in asset_rns_by_slot.items()
                },
                "warnings": warnings,
            }

        except DemandGenValidationError:
            raise
        except Exception as e:
            await ctx.log(
                level="error",
                message=f"[DemandGen] failure at step '{failed_step}': {e}; rolling back...",
            )
            rollback_report = await self._rollback(
                ctx=ctx,
                customer_id=customer_id,
                campaign_rn=created_campaign_rn,
                budget_rn=created_budget_rn,
            )
            raise DemandGenStepError(
                step=failed_step, original=e, rollback_report=rollback_report
            ) from e

    async def update_ad_images(
        self,
        ctx: Context,
        customer_id: str,
        bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Swap / add image creatives on an EXISTING DemandGenMultiAssetAd.

        The reject-the-AI-creative → iterate-with-my-own-photos flow: a Studio
        selection (uploaded property photos and/or freshly generated images)
        replaces or appends the ad's image assets IN PLACE — same ad id, same
        text, same history — never a delete-and-recreate.

        Pipeline (mirrors the create path's image handling, reused not
        duplicated):

          1. Pre-flight ``_resolve_image_plan`` — classify every new ref as a
             Google asset (pass-through, aspect-verified) or a local upload
             UUID (center-crop to the slot's EXACT aspect, transcode, size-cap).
             A bad image fails as a clean ``DemandGenValidationError`` here,
             before anything touches the live ad.
          2. ``_upload_images`` — push local bytes to Google image assets;
             pre-existing Google refs pass through.
          3. ``mode='append'`` only — read the ad's live images per slot.
          4. Build a ``DemandGenMultiAssetAdInfo`` carrying ONLY the touched
             slots and an ``AdOperation`` update masked to exactly those image
             fields (``demand_gen_multi_asset_ad.<field>``). Untouched slots
             keep their live value; text / business_name / CTA are never in the
             mask so they are preserved.

        Returns::

            {
                "ad_id": str,
                "ad_resource_name": str,
                "mode": "replace" | "append",
                "updated_slots": {<slot>: [<image_asset_id>, ...], ...},
                "field_mask": ["demand_gen_multi_asset_ad.<field>", ...],
            }

        Raises ``DemandGenValidationError`` pre-flight; ``DemandGenAdUpdateError``
        when the Google mutate itself is rejected (nothing changed live).
        """
        _validate_update_bundle(bundle)
        customer_id = format_customer_id(customer_id)
        mode = str(bundle.get("mode") or "replace").lower()

        # Resolve the target ad's resource name + numeric id. The `Ad` resource
        # is keyed by ad id alone (not the ad-group composite), matching
        # AdService.update_rsa_pins.
        ad_rn = bundle.get("ad_resource_name")
        if ad_rn:
            resource_name = str(ad_rn)
            ad_id = resource_name.rstrip("/").rsplit("/", 1)[-1]
        else:
            ad_id = str(bundle["ad_id"])
            resource_name = f"customers/{customer_id}/ads/{ad_id}"

        # 1 — classify + crop + aspect-verify every NEW image ref pre-flight.
        image_plan = await self._resolve_image_plan(customer_id, bundle)

        # 2 — bridge local uploads to Google image assets (google refs pass
        #     through unchanged).
        new_rns_by_slot = await self._upload_images(
            ctx=ctx,
            customer_id=customer_id,
            name=str(bundle.get("name") or f"DG ad {ad_id} image refresh"),
            image_plan=image_plan,
        )
        provided = {slot for slot, rns in new_rns_by_slot.items() if rns}
        if not provided:
            # _validate_update_bundle already guarantees ≥1 ref, but resolve can
            # legitimately end with nothing (e.g. all refs empty strings) — fail
            # closed rather than send an empty field mask (FIELD_MASK_MISSING).
            raise DemandGenValidationError(
                ["no resolvable image refs after pre-flight — nothing to update"]
            )

        # 3 — append mode: fold in the ad's current images per touched slot.
        current_by_slot: Dict[str, List[str]] = {}
        if mode == "append":
            current_by_slot = self._fetch_current_ad_images(customer_id, ad_id)

        # 4 — build the partial ad + field mask over exactly the touched slots.
        info = DemandGenMultiAssetAdInfo()
        paths: List[str] = []
        updated_slots: Dict[str, List[str]] = {}
        for slot, field_name in IMAGE_SLOT_TO_AD_FIELD.items():  # stable order
            if slot not in provided:
                continue
            combined: List[str] = []
            if mode == "append":
                combined.extend(current_by_slot.get(slot, []))
            combined.extend(new_rns_by_slot[slot])
            # De-dup preserving order (append can re-list an incumbent).
            seen: set[str] = set()
            ordered: List[str] = []
            for rn in combined:
                if rn and rn not in seen:
                    seen.add(rn)
                    ordered.append(rn)
            repeated = getattr(info, field_name)
            for rn in ordered:
                repeated.append(AdImageAsset(asset=rn))
            paths.append(f"demand_gen_multi_asset_ad.{field_name}")
            updated_slots[slot] = ordered

        ad = Ad()
        ad.resource_name = resource_name
        ad.demand_gen_multi_asset_ad = info

        op = AdOperation()
        op.update = ad
        op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
        request = MutateAdsRequest()
        request.customer_id = customer_id
        request.operations = [op]

        await ctx.log(
            level="info",
            message=(
                f"[DemandGen] {mode.upper()} images on ad {ad_id}: "
                f"{', '.join(f'{s}×{len(rns)}' for s, rns in updated_slots.items())}"
            ),
        )
        try:
            resp = self.ad_client.mutate_ads(request=request)
        except GoogleAdsException as e:
            raise DemandGenAdUpdateError(
                f"Google Ads rejected the image update for ad {ad_id} "
                f"(nothing changed): {e.failure}"
            ) from e

        return {
            "ad_id": ad_id,
            "ad_resource_name": _extract_resource_name(
                serialize_proto_message(resp)
            ),
            "mode": mode,
            "updated_slots": {
                slot: [_id_from_resource_name(rn) for rn in rns]
                for slot, rns in updated_slots.items()
            },
            "field_mask": paths,
        }

    async def _post_create_sync(
        self,
        ctx: Context,
        account_id: str,
        campaign_id: str,
        bundle: Dict[str, Any],
        channels: Dict[str, bool],
    ) -> None:
        """Refresh local DB + bootstrap memory after a successful create.

        All best-effort: the campaign IS already live in Google, so a hiccup
        here must not fail the flow. App-side imports live inside the function
        so the MCP server can import this module standalone.
        """
        try:
            from app.services import campaigns_repo
            from app.services.campaign_memory import init_campaign_memory
            from app.services.chronicle import (
                _chronicle_path,
                _init_chronicle,
                _insert_entry,
                load_chronicle,
            )
            from datetime import datetime as _dt
            import re as _re
        except ImportError as e:
            await ctx.log(
                level="warning",
                message=(
                    f"[DemandGen post-create] app-side imports unavailable, "
                    f"skipping local sync: {e}"
                ),
            )
            return

        # 1) Pull fresh campaign list into the sidebar's `campaigns` table.
        try:
            n = await campaigns_repo.sync_campaigns(account_id)
            await ctx.log(
                level="info",
                message=f"[DemandGen post-create] campaigns sync: {n} rows",
            )
        except Exception as e:
            await ctx.log(
                level="warning",
                message=f"[DemandGen post-create] campaigns sync failed: {e}",
            )

        # 2) Bootstrap the per-campaign memory folder so the agent won't
        #    invent CPA/CPC numbers on its first read.
        try:
            init_campaign_memory(
                account_id=account_id,
                campaign_id=campaign_id,
                campaign_name=bundle["name"],
            )
        except Exception as e:
            await ctx.log(
                level="warning",
                message=f"[DemandGen post-create] memory init failed: {e}",
            )

        # 3) Chronicle entry for the creation event.
        try:
            existing = load_chronicle(account_id, campaign_id) or _init_chronicle(
                account_id, campaign_id, bundle["name"]
            )
            now = _dt.now()
            on_channels = [c for c in CHANNEL_FIELDS if channels.get(c)]
            entry_line = (
                f"- **{now.strftime('%b %d')}** — [demand_gen_strategist] "
                f"Created Demand Gen campaign **{bundle['name']}** "
                f"(daily budget ${bundle['budget_micros'] / 1_000_000:.2f}, "
                f"{len(bundle.get('headlines') or [])}H/"
                f"{len(bundle.get('descriptions') or [])}D, "
                f"channels: {', '.join(on_channels) or 'none'}; "
                f"Gmail {'OFF' if not channels.get('gmail') else 'ON'}). "
                f"Starts PAUSED — user enables after reviewing the ad."
            )
            month_header = f"### {now.strftime('%B %Y')}"
            updated = _insert_entry(existing, month_header, entry_line)
            updated = _re.sub(
                r"Last updated: .*",
                f"Last updated: {now.strftime('%Y-%m-%d')}",
                updated,
                count=1,
            )
            _chronicle_path(account_id, campaign_id).write_text(
                updated, encoding="utf-8"
            )
        except Exception as e:
            await ctx.log(
                level="warning",
                message=f"[DemandGen post-create] chronicle append failed: {e}",
            )

    async def _rollback(
        self,
        ctx: Context,
        customer_id: str,
        campaign_rn: Optional[str],
        budget_rn: Optional[str],
    ) -> List[str]:
        """Best-effort removal of the campaign + budget we just created when
        something downstream failed.

        Removal MUST use a REMOVE operation — Google rejects
        `update status=REMOVED` (request_error INVALID_ENUM_VALUE). Campaign
        first, then its budget (a budget can only be removed once no live
        campaign references it). Assets / ad groups created along the way are
        removed implicitly with their campaign; image assets are left in the
        account library (reusable, don't spend).

        Returns a human-readable report for the DemandGenStepError.
        """
        report: List[str] = []
        campaign_removed = campaign_rn is None
        if campaign_rn:
            cid = _id_from_resource_name(campaign_rn)
            try:
                await self._campaign.remove_campaign(
                    ctx=ctx, customer_id=customer_id, campaign_id=cid
                )
                campaign_removed = True
                await ctx.log(
                    level="info", message=f"[DemandGen rollback] removed campaign {cid}"
                )
                report.append(f"Rolled back: campaign {cid} was removed.")
            except Exception as e:
                await ctx.log(
                    level="warning",
                    message=f"[DemandGen rollback] could not remove campaign: {e}",
                )
                report.append(
                    f"ROLLBACK INCOMPLETE: campaign {cid} could not be removed ({e}) — "
                    f"remove it manually in the Google Ads UI. It was created PAUSED, "
                    f"so it is not spending."
                )
        if budget_rn:
            bid = _id_from_resource_name(budget_rn)
            try:
                if not campaign_removed:
                    raise RuntimeError("its campaign could not be removed first")
                await self._budget.remove_campaign_budget(
                    ctx=ctx, customer_id=customer_id, budget_id=bid
                )
                await ctx.log(
                    level="info", message=f"[DemandGen rollback] removed budget {bid}"
                )
                report.append(f"Rolled back: budget {bid} was removed.")
            except Exception as e:
                await ctx.log(
                    level="warning",
                    message=(
                        f"[DemandGen rollback] orphan budget {bid} left in account "
                        f"({e}). Safe to ignore — budgets without a campaign don't spend."
                    ),
                )
                report.append(
                    f"Orphan budget {bid} left in the account ({e}) — budgets "
                    f"without a campaign don't spend; safe to delete manually."
                )
        if not report:
            report.append(
                "Nothing was rolled back — no Google Ads entities had been created yet."
            )
        return report


def create_demand_gen_orchestrator_tools(
    service: DemandGenOrchestrator,
) -> List[Callable[..., Awaitable[Any]]]:
    """Wrap the orchestrator as FastMCP tool functions."""

    async def create_demand_gen_campaign(
        ctx: Context,
        customer_id: str,
        name: str,
        budget_micros: int,
        final_urls: List[str],
        business_name: str,
        headlines: List[str],
        descriptions: List[str],
        logos: List[str],
        landscape_images: Optional[List[str]] = None,
        square_images: Optional[List[str]] = None,
        location_ids: Optional[List[str]] = None,
        excluded_location_ids: Optional[List[str]] = None,
        language_ids: Optional[List[str]] = None,
        portrait_images: Optional[List[str]] = None,
        tall_portrait_images: Optional[List[str]] = None,
        call_to_action_text: Optional[str] = None,
        target_cpa_micros: Optional[int] = None,
        enable_gmail: bool = False,
        enable_display: bool = True,
        enable_discover: bool = True,
        enable_youtube_in_stream: bool = True,
        enable_youtube_in_feed: bool = True,
        enable_youtube_shorts: bool = True,
        audience_user_list_ids: Optional[List[str]] = None,
        excluded_user_list_ids: Optional[List[str]] = None,
        final_mobile_urls: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Demand Gen campaign in one shot.

        Demand Gen replaces the old Discovery campaign type and serves across
        YouTube (in-stream / in-feed / Shorts), Discover, Gmail, and the
        Display network. THE CHANNEL CONTROLS ARE THE POINT: `enable_gmail`
        defaults to OFF and `enable_display` to ON, and each channel is
        toggleable — an all-off selection is rejected pre-flight.

        Validates against Google's Demand Gen minimums (1-5 headlines ≤40
        chars, 1-5 descriptions ≤90 chars, business_name ≤25 chars, ≥1 logo,
        ≥1 marketing image [landscape 1.91:1 OR square 1:1]) and rolls back on
        partial failure. The campaign is created PAUSED so the user reviews
        the ad before spending.

        Args:
            customer_id: Google Ads customer ID.
            name: Campaign name (seeds the ad group + budget names).
            budget_micros: Daily budget in micros (1_000_000 = $1).
            final_urls: At least one landing URL (set on the ad).
            business_name: Advertiser/brand name shown in the ad (≤25 chars).
            headlines: 1-5 headlines, each ≤40 chars.
            descriptions: 1-5 descriptions, each ≤90 chars.
            logos: ≥1 logo image ref (1:1) — a Google Ads asset resource name
                (customers/<cid>/assets/<id>), a bare numeric asset id, OR a
                local asset UUID from /api/assets/upload / Studio (the
                orchestrator uploads local files to Google automatically).
            landscape_images: 1.91:1 marketing images (same ref forms as logos).
            square_images: 1:1 marketing images. At least one of
                landscape_images/square_images is required.
            location_ids: Optional geo target constant IDs for targeting.
            excluded_location_ids: Optional geo target constant IDs to EXCLUDE
                (negative location criteria) — e.g. exclude the Dubai emirate
                while still targeting the United Arab Emirates.
            language_ids: Optional language constant IDs for targeting.
            portrait_images: Optional 4:5 portrait marketing images.
            tall_portrait_images: Optional 9:16 tall portrait marketing images.
            call_to_action_text: Optional CTA text for the ad.
            target_cpa_micros: Optional target CPA in micros (MaximizeConversions
                with a CPA target); omit for uncapped MaximizeConversions.
            enable_gmail: Serve on Gmail (default False — OFF).
            enable_display: Serve on the Display network (default True).
            enable_discover: Serve on Discover (default True).
            enable_youtube_in_stream / enable_youtube_in_feed /
                enable_youtube_shorts: YouTube surface toggles (default True).
            audience_user_list_ids: Optional user-list IDs to INCLUDE (custom
                segments / customer-match inclusion) as ad-group criteria.
            excluded_user_list_ids: Optional user-list IDs to EXCLUDE
                (customer-match exclusion) as negative ad-group criteria.
            final_mobile_urls: Optional mobile-specific URLs.
            start_date / end_date: Optional 'YYYY-MM-DD' campaign window.

        Returns:
            {
                "campaign_id": "...",
                "budget_id": "...",
                "ad_group_id": "...",
                "ad_group_ad_id": "...",
                "channels": {...},
                "image_asset_ids": {...},
                "warnings": []
            }
        """
        bundle = {
            "name": name,
            "budget_micros": budget_micros,
            "final_urls": final_urls,
            "final_mobile_urls": final_mobile_urls,
            "business_name": business_name,
            "headlines": headlines,
            "descriptions": descriptions,
            "logos": logos,
            "marketing_images": {
                "landscape": landscape_images or [],
                "square": square_images or [],
                "portrait": portrait_images or [],
                "tall_portrait": tall_portrait_images or [],
            },
            "location_ids": location_ids or [],
            "excluded_location_ids": excluded_location_ids or [],
            "language_ids": language_ids or [],
            "call_to_action_text": call_to_action_text,
            "target_cpa_micros": target_cpa_micros,
            "channels": {
                "gmail": enable_gmail,
                "display": enable_display,
                "discover": enable_discover,
                "youtube_in_stream": enable_youtube_in_stream,
                "youtube_in_feed": enable_youtube_in_feed,
                "youtube_shorts": enable_youtube_shorts,
            },
            "audience_user_list_ids": audience_user_list_ids or [],
            "excluded_user_list_ids": excluded_user_list_ids or [],
            "start_date": start_date,
            "end_date": end_date,
        }
        try:
            return await service.create_demand_gen_campaign(
                ctx=ctx, customer_id=customer_id, bundle=bundle
            )
        except DemandGenValidationError as e:
            return {"error": "VALIDATION_FAILED", "errors": e.errors}

    return [create_demand_gen_campaign]


def create_demand_gen_ad_image_tools(
    service: DemandGenOrchestrator,
) -> List[Callable[..., Awaitable[Any]]]:
    """Wrap the in-place image-update flow as FastMCP tool function(s).

    Kept as a SEPARATE factory from ``create_demand_gen_orchestrator_tools`` so
    the create tool's call-sites / tests that unpack a single-element tuple stay
    intact; both factories share the one ``DemandGenOrchestrator`` instance.
    """

    async def update_ad_images(
        ctx: Context,
        customer_id: str,
        ad_group_id: Optional[str] = None,
        ad_id: Optional[str] = None,
        ad_resource_name: Optional[str] = None,
        mode: str = "replace",
        landscape_images: Optional[List[str]] = None,
        square_images: Optional[List[str]] = None,
        portrait_images: Optional[List[str]] = None,
        tall_portrait_images: Optional[List[str]] = None,
        logos: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Replace or append the image creatives on an existing Demand Gen ad.

        The iterate-in-Studio flow: after rejecting the auto-generated creative,
        push your OWN property photos (uploaded to the Studio library) and/or
        freshly generated images onto the live ad IN PLACE — same ad id, text,
        and history preserved (only the masked image slots change).

        Every image ref may be a Google Ads asset resource name
        (customers/<cid>/assets/<id>), a bare numeric asset id, OR a local asset
        UUID from /api/assets/upload or a Studio generation — local files are
        uploaded to Google and center-cropped to each slot's EXACT aspect
        automatically (logo/square 1:1, landscape 1.91:1, portrait 4:5, tall
        9:16). Off-aspect or below-minimum images fail pre-flight before the
        live ad is touched.

        Args:
            customer_id: Google Ads customer ID.
            ad_group_id: The ad group ID (with ``ad_id`` when
                ``ad_resource_name`` is not supplied).
            ad_id: The ad ID (with ``ad_group_id`` when ``ad_resource_name`` is
                not supplied).
            ad_resource_name: Full ad resource name
                (customers/<cid>/ads/<ad_id>); overrides ad_group_id/ad_id.
            mode: 'replace' (default — swap the slot's images wholesale) or
                'append' (keep the ad's current images, add the new ones after).
            landscape_images: 1.91:1 marketing image refs.
            square_images: 1:1 marketing image refs.
            portrait_images: 4:5 portrait marketing image refs.
            tall_portrait_images: 9:16 tall portrait marketing image refs.
            logos: 1:1 logo image refs (max 5).

        Only the slots you pass refs for are touched; omitted slots keep their
        live images. At least one image ref in one slot is required.

        Returns:
            {
                "ad_id": "...",
                "ad_resource_name": "...",
                "mode": "replace" | "append",
                "updated_slots": {"landscape": ["<asset_id>", ...], ...},
                "field_mask": ["demand_gen_multi_asset_ad.marketing_images", ...]
            }
        """
        bundle = {
            "ad_group_id": ad_group_id,
            "ad_id": ad_id,
            "ad_resource_name": ad_resource_name,
            "mode": mode,
            "logos": logos or [],
            "marketing_images": {
                "landscape": landscape_images or [],
                "square": square_images or [],
                "portrait": portrait_images or [],
                "tall_portrait": tall_portrait_images or [],
            },
        }
        try:
            return await service.update_ad_images(
                ctx=ctx, customer_id=customer_id, bundle=bundle
            )
        except DemandGenValidationError as e:
            return {"error": "VALIDATION_FAILED", "errors": e.errors}

    return [update_ad_images]


def register_demand_gen_tools(mcp: FastMCP[Any]) -> DemandGenOrchestrator:
    """Register the Demand Gen orchestrator tools with the FastMCP server.

    One shared orchestrator backs both the single-shot campaign create and the
    in-place image-update tool.
    """
    service = DemandGenOrchestrator()
    for tool in create_demand_gen_orchestrator_tools(service):
        mcp.tool(tool)
    for tool in create_demand_gen_ad_image_tools(service):
        mcp.tool(tool)
    return service
