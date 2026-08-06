"""Responsive Display Ad campaign creation — single-shot orchestrator (P5, FR6.2).

The Display consumer of the Unified Creative Engine. Deliberately built as
PLUMBING on the ``demand_gen_orchestrator`` recipe shape, NOT as a third copy of
the creative machinery:

    1. CampaignBudget
    2. Campaign (advertising_channel_type=DISPLAY, PAUSED)
    3. Geo + language targeting (campaign criteria)
    4. Image assets (landscape / square marketing + 1:1 / 4:1 logos) — local
       uploads pushed to Google as image assets; Google refs pass through
    5. AdGroup (type=DISPLAY_STANDARD)
    6. AdGroupAd — a ``ResponsiveDisplayAdInfo`` carrying inline text
       (short headlines / the SINGULAR long headline / descriptions / business
       name / CTA) plus AdImageAsset references to the uploaded image assets,
       INCLUDING the 4:1 ``LANDSCAPE_LOGO`` field (``logo_images``) — a field
       type absent repo-wide until this module.

Every creative limit + policy is READ from the Creative Spec Registry
(``creative_specs.get("rda")``, verified in story 19.1) and every image is
classified / cropped / aspect-verified by ``creative_images`` — used UNCHANGED
(FR6.2: the P5 diff contains zero changes to ``creative_images.py``). If any step
fails, prior creations are rolled back so the user never sees half a campaign.

RDA field-type mapping (``ResponsiveDisplayAdInfo`` proto, v23):
  * landscape (1.91:1)   → ``marketing_images``
  * square (1:1)         → ``square_marketing_images``
  * logos (1:1)          → ``square_logo_images``
  * landscape_logo (4:1) → ``logo_images``   (the LANDSCAPE_LOGO field)
  * long headline        → ``long_headline`` (a SINGULAR field ⇒ exactly one)
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastmcp import Context, FastMCP
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v23.common.types import MaximizeConversions
from google.ads.googleads.v23.common.types.ad_asset import AdImageAsset, AdTextAsset
from google.ads.googleads.v23.common.types.ad_type_infos import (
    ResponsiveDisplayAdInfo,
)
from google.ads.googleads.v23.enums.types.ad_group_ad_status import (
    AdGroupAdStatusEnum,
)
from google.ads.googleads.v23.enums.types.ad_group_status import AdGroupStatusEnum
from google.ads.googleads.v23.enums.types.ad_group_type import AdGroupTypeEnum
from google.ads.googleads.v23.enums.types.advertising_channel_type import (
    AdvertisingChannelTypeEnum,
)
from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
from google.ads.googleads.v23.resources.types.ad import Ad
from google.ads.googleads.v23.resources.types.ad_group import AdGroup
from google.ads.googleads.v23.resources.types.ad_group_ad import AdGroupAd
from google.ads.googleads.v23.resources.types.campaign import Campaign
from google.ads.googleads.v23.services.types.ad_group_ad_service import (
    AdGroupAdOperation,
    MutateAdGroupAdsRequest,
)
from google.ads.googleads.v23.services.types.ad_group_service import (
    AdGroupOperation,
    MutateAdGroupsRequest,
)
from google.ads.googleads.v23.services.types.campaign_service import (
    CampaignOperation,
    MutateCampaignsRequest,
)

from google_ads.sdk_client import get_sdk_client
from google_ads.services.assets.asset_service import AssetService
from google_ads.services.bidding.budget_service import BudgetService
from google_ads.services.campaign import creative_images
from google_ads.services.conversions.conversion_goal_setup import (
    apply_bundle_conversion_goal,
)
from google_ads.services.campaign.campaign_service import CampaignService
from google_ads.services.campaign.campaign_criterion_service import (
    CampaignCriterionService,
)
# Shared plumbing reused verbatim from the DG orchestrator (F1 — no second copy).
from google_ads.services.campaign.demand_gen_orchestrator import (
    _extract_resource_name,
    _id_from_resource_name,
)
from google_ads.services.campaign.pmax_orchestrator import ApiCtx  # noqa: F401 (re-export)
from google_ads.utils import format_customer_id, get_logger, serialize_proto_message

# Creative Spec Registry — every RDA limit + policy is read from here (F1).
from app.services import creative_specs
from app.services.creative_specs import CampaignSpec, ValidationReport  # noqa: F401

logger = get_logger(__name__)

# `_locate_local_image` kept as a module global so unit tests can monkeypatch
# `rda_orchestrator._locate_local_image` (mirrors the PMax / DG pattern);
# `_resolve_image_plan` passes this global into the shared resolver.
_locate_local_image = creative_images.locate_local_image

# Registry image-slot key → ResponsiveDisplayAdInfo repeated-field name. Each
# slot's images are AdImageAsset references pointing at uploaded image assets.
# `landscape_logo` → `logo_images` is the 4:1 LANDSCAPE_LOGO field type, which no
# other orchestrator in this repo emits.
IMAGE_SLOT_TO_AD_FIELD = {
    "landscape": "marketing_images",             # 1.91:1
    "square": "square_marketing_images",         # 1:1
    "logos": "square_logo_images",               # 1:1 logo
    "landscape_logo": "logo_images",             # 4:1 LANDSCAPE_LOGO
}


class RdaValidationError(Exception):
    """Raised when the input bundle doesn't meet RDA's registry-driven minimums.

    The orchestrator catches this and returns a structured error so the wizard /
    chat agent can highlight the specific fields to fix.
    """

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class RdaStepError(Exception):
    """Raised when the recipe dies partway through a Google API call.

    Carries which step failed and what the rollback cleaned up, so the API layer
    / wizard can show an actionable message instead of a bare Google error blob.
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
            f"Responsive Display create failed at step '{step}'. {cleanup} "
            f"Underlying error: {original}"
        )


def _validate_bundle(bundle: Dict[str, Any], spec: CampaignSpec) -> ValidationReport:
    """Pre-flight validation against the Creative Spec Registry (FR6.1/FR6.2).

    Verified-limit violations are ``errors`` (the create raises); unverified
    (soft) ones are ``warnings``. Text counts/caps (incl. the SINGULAR long
    headline, enforced structurally in ``check_text_fields``), business name,
    final URLs, the combined image cap, and the required marketing-image + logo
    slots all read from ``spec`` (fence F1). Image aspect/size is handled by
    ``_resolve_image_plan``."""
    report = ValidationReport()

    if not bundle.get("name"):
        report.errors.append("campaign 'name' is required")
    if not bundle.get("budget_micros"):
        report.errors.append("'budget_micros' is required (1_000_000 micros = $1)")

    creative_specs.check_business_name(bundle, spec, report)
    creative_specs.check_text_fields(bundle, spec, report)
    creative_specs.check_final_urls(bundle, spec, report)
    creative_specs.check_image_caps(bundle, spec, report)

    # Required marketing-image slots (landscape 1.91:1 AND square 1:1 are each
    # required for RDA — the registry marks them required=True). Every required
    # image slot must carry ≥1 image; read the requiredness from the registry so
    # a policy change here is a data change, not a code branch.
    marketing = bundle.get("marketing_images") or {}
    for slot, islot in spec.images.items():
        if islot.required and not (marketing.get(slot) or []):
            report.errors.append(
                f"need ≥1 {slot} marketing image ({islot.label or slot})"
            )

    # Required logo slot (1:1 square logo). The 4:1 landscape_logo is optional.
    logo_spec = spec.logos.get("logos")
    if logo_spec is not None and logo_spec.required and not (bundle.get("logos") or []):
        report.errors.append("need ≥1 logo image (1:1)")

    return report


class RdaOrchestrator:
    """The Responsive Display recipe. Holds references to each primitive service
    so it can sequence them and roll back on failure."""

    def __init__(self) -> None:
        self._budget = BudgetService()
        self._campaign = CampaignService()          # rollback (remove_campaign)
        self._campaign_criterion = CampaignCriterionService()
        self._asset = AssetService()
        self._campaign_client: Optional[Any] = None
        self._ad_group_client: Optional[Any] = None
        self._ad_group_ad_client: Optional[Any] = None
        self._google_ads: Optional[Any] = None

    # ── lazy SDK clients (same pattern as the DG orchestrator) ───────────
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
    def google_ads_client(self) -> Any:
        if self._google_ads is None:
            self._google_ads = get_sdk_client().client.get_service("GoogleAdsService")
        return self._google_ads

    # ── image aspect verification (stubbable in tests) ───────────────────
    def _fetch_image_asset_dims(
        self, customer_id: str, resource_names: List[str]
    ) -> Dict[str, tuple[int, int]]:
        """GAQL lookup: full-size pixel dimensions for existing image assets,
        keyed by resource name (mirrors the DG orchestrator). Isolated so unit
        tests can stub it without a live SDK client."""
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

    async def _resolve_image_plan(
        self, customer_id: str, bundle: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Classify + crop + aspect-verify every image ref pre-flight. Thin
        wrapper over the shared ``creative_images.resolve_image_plan`` (the same
        logic PMax + DG use, UNCHANGED — FR6.2). Only RDA's slots are passed."""
        mi = bundle.get("marketing_images") or {}
        slots = {
            "landscape": list(mi.get("landscape") or []),
            "square": list(mi.get("square") or []),
            "logos": list(bundle.get("logos") or []),
            "landscape_logo": list(bundle.get("landscape_logos") or []),
        }
        return await creative_images.resolve_image_plan(
            customer_id=customer_id,
            slots=slots,
            fetch_dims=self._fetch_image_asset_dims,
            error_factory=RdaValidationError,
            locate=_locate_local_image,
        )

    # ── direct-build steps ───────────────────────────────────────────────
    def _create_campaign_resource(
        self,
        customer_id: str,
        name: str,
        budget_rn: str,
        target_cpa_micros: Optional[int],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> str:
        """Create the DISPLAY campaign (PAUSED) and return its resource name.

        Bidding is MaximizeConversions, optionally with a target CPA (same as
        the DG recipe). Network settings target the Display Network only. Starts
        PAUSED so the user reviews the ad before spend.
        """
        campaign = Campaign()
        campaign.name = name
        campaign.campaign_budget = budget_rn
        campaign.advertising_channel_type = (
            AdvertisingChannelTypeEnum.AdvertisingChannelType.DISPLAY
        )
        campaign.status = CampaignStatusEnum.CampaignStatus.PAUSED

        # EU political advertising compliance (required on create in v23; DG
        # precedent). 3 = DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING.
        campaign.contains_eu_political_advertising = 3

        # Display-only network settings.
        campaign.network_settings.target_google_search = False
        campaign.network_settings.target_search_network = False
        campaign.network_settings.target_content_network = True
        campaign.network_settings.target_partner_search_network = False

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
        self, customer_id: str, campaign_rn: str, name: str
    ) -> str:
        """Create the DISPLAY_STANDARD ad group (ENABLED) and return its
        resource name."""
        ad_group = AdGroup()
        ad_group.name = name
        ad_group.campaign = campaign_rn
        ad_group.type_ = AdGroupTypeEnum.AdGroupType.DISPLAY_STANDARD
        ad_group.status = AdGroupStatusEnum.AdGroupStatus.ENABLED

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

    def _build_responsive_display_ad(
        self,
        bundle: Dict[str, Any],
        asset_rns_by_slot: Dict[str, List[str]],
    ) -> Ad:
        """Assemble the Ad carrying a ResponsiveDisplayAdInfo: inline text (short
        headlines / the SINGULAR long headline / descriptions / business name /
        CTA) + AdImageAsset references, INCLUDING the 4:1 LANDSCAPE_LOGO field."""
        info = ResponsiveDisplayAdInfo()
        info.business_name = bundle["business_name"]
        for h in bundle["headlines"]:
            info.headlines.append(AdTextAsset(text=h))
        # long_headline is a SINGULAR field — exactly one (validated upstream).
        long_headlines = bundle.get("long_headlines") or []
        if long_headlines:
            info.long_headline = AdTextAsset(text=long_headlines[0])
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
        ad.responsive_display_ad = info
        return ad

    def _create_ad_group_ad_resource(
        self, customer_id: str, ad_group_rn: str, ad: Ad
    ) -> str:
        """Create the AdGroupAd (ENABLED) wrapping the RDA and return its
        resource name."""
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

    async def _upload_images(
        self,
        ctx: Context,
        customer_id: str,
        name: str,
        image_plan: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[str]]:
        """Bridge local upload UUIDs to Google image-asset resource names, passing
        pre-existing Google asset refs through unchanged. Dedup keyed by (ref,
        slot aspect) — NOT ref alone — so one source image filling two different-
        aspect slots uploads once per crop (the ASPECT_RATIO_NOT_ALLOWED class of
        bug; mirrors the DG orchestrator)."""
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
                    f"[RDA] Uploaded {len(uploaded)} local image(s) to "
                    f"Google Ads as image assets"
                ),
            )
        return asset_rns_by_slot

    async def create_responsive_display_campaign(
        self,
        ctx: Context,
        customer_id: str,
        bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a Responsive Display campaign from a complete bundle.

        See the module docstring for the operation sequence. Returns the DG-shape
        create response::

            {
                "campaign_id": str,
                "budget_id": str,
                "ad_group_id": str,
                "ad_id": str,                       # the ad group ad id
                "asset_ids": {<slot>: [str, ...]},  # per RDA image slot
                "warnings": [str, ...],
            }

        Raises RdaValidationError pre-flight; RdaStepError on any Google API
        failure (with prior creations rolled back).
        """
        spec = creative_specs.get("rda")
        report = _validate_bundle(bundle, spec)
        if report.errors:
            raise RdaValidationError(report.errors)
        customer_id = format_customer_id(customer_id)

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
                    f"[RDA] Creating budget for '{bundle['name']}' at "
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
            await ctx.log(level="info", message="[RDA] Creating DISPLAY campaign...")
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
                    ctx=ctx, customer_id=customer_id, campaign_id=campaign_id,
                    location_ids=location_ids,
                )
            if excluded_location_ids:
                await self._campaign_criterion.add_location_criteria(
                    ctx=ctx, customer_id=customer_id, campaign_id=campaign_id,
                    location_ids=excluded_location_ids, negative=True,
                )
            if language_ids:
                await self._campaign_criterion.add_language_criteria(
                    ctx=ctx, customer_id=customer_id, campaign_id=campaign_id,
                    language_ids=language_ids,
                )

            # ── Step 4 — Image assets (local upload → resource name) ──
            failed_step = "image asset upload"
            asset_rns_by_slot = await self._upload_images(
                ctx=ctx, customer_id=customer_id, name=bundle["name"],
                image_plan=image_plan,
            )

            # ── Step 5 — Ad group ─────────────────────────────────────
            failed_step = "ad group creation"
            ad_group_rn = self._create_ad_group_resource(
                customer_id=customer_id,
                campaign_rn=created_campaign_rn,
                name=f"{bundle['name']} — Ad Group 1",
            )
            ad_group_id = _id_from_resource_name(ad_group_rn)

            # ── Step 6 — Ad group ad (responsive display ad) ──────────
            failed_step = "ad creation"
            ad = self._build_responsive_display_ad(bundle, asset_rns_by_slot)
            ad_group_ad_rn = self._create_ad_group_ad_resource(
                customer_id=customer_id, ad_group_rn=ad_group_rn, ad=ad
            )
            ad_id = _id_from_resource_name(ad_group_ad_rn)

            await ctx.log(
                level="info",
                message=(
                    f"[RDA] OK — campaign_id={campaign_id} "
                    f"ad_group_id={ad_group_id} ad_id={ad_id}"
                ),
            )

            return {
                "campaign_id": campaign_id,
                "budget_id": budget_id,
                "ad_group_id": ad_group_id,
                "ad_id": ad_id,
                "asset_ids": {
                    slot: [_id_from_resource_name(rn) for rn in rns]
                    for slot, rns in asset_rns_by_slot.items()
                },
                "warnings": warnings,
            }

        except RdaValidationError:
            raise
        except Exception as e:
            await ctx.log(
                level="error",
                message=f"[RDA] failure at step '{failed_step}': {e}; rolling back...",
            )
            rollback_report = await self._rollback(
                ctx=ctx,
                customer_id=customer_id,
                campaign_rn=created_campaign_rn,
                budget_rn=created_budget_rn,
            )
            raise RdaStepError(
                step=failed_step, original=e, rollback_report=rollback_report
            ) from e

    async def _rollback(
        self,
        ctx: Context,
        customer_id: str,
        campaign_rn: Optional[str],
        budget_rn: Optional[str],
    ) -> List[str]:
        """Best-effort removal of the campaign + budget we just created when a
        downstream step failed. Campaign first (a budget can only be removed once
        no live campaign references it); removal MUST use a REMOVE op. Assets /
        ad groups are removed implicitly with their campaign; image assets stay in
        the account library (reusable, don't spend). Mirrors the DG rollback."""
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
                    level="info", message=f"[RDA rollback] removed campaign {cid}"
                )
                report.append(f"Rolled back: campaign {cid} was removed.")
            except Exception as e:
                await ctx.log(
                    level="warning",
                    message=f"[RDA rollback] could not remove campaign: {e}",
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
                    level="info", message=f"[RDA rollback] removed budget {bid}"
                )
                report.append(f"Rolled back: budget {bid} was removed.")
            except Exception as e:
                await ctx.log(
                    level="warning",
                    message=(
                        f"[RDA rollback] orphan budget {bid} left in account "
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


def create_rda_orchestrator_tools(
    service: RdaOrchestrator,
) -> List[Callable[..., Awaitable[Any]]]:
    """Wrap the orchestrator as FastMCP tool functions."""

    async def create_responsive_display_campaign(
        ctx: Context,
        customer_id: str,
        name: str,
        budget_micros: int,
        final_urls: List[str],
        business_name: str,
        headlines: List[str],
        long_headlines: List[str],
        descriptions: List[str],
        logos: List[str],
        landscape_images: Optional[List[str]] = None,
        square_images: Optional[List[str]] = None,
        landscape_logos: Optional[List[str]] = None,
        location_ids: Optional[List[str]] = None,
        excluded_location_ids: Optional[List[str]] = None,
        language_ids: Optional[List[str]] = None,
        call_to_action_text: Optional[str] = None,
        target_cpa_micros: Optional[int] = None,
        final_mobile_urls: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Responsive Display Ad campaign in one shot (PAUSED).

        A Responsive Display Ad (RDA) serves across the Google Display Network,
        auto-fitting the assets you supply. Google combines your short headlines,
        the single long headline, descriptions, business name, marketing images
        (1.91:1 landscape + 1:1 square) and logos (1:1 + optional 4:1 landscape)
        into responsive layouts.

        Validates against the RDA limits in the Creative Spec Registry (≤5 short
        headlines ≤30 chars, EXACTLY 1 long headline ≤90 chars, ≤5 descriptions
        ≤90 chars, business_name ≤25 chars, ≥1 landscape + ≥1 square marketing
        image, ≥1 logo, ≤15 marketing images combined) and rolls back on partial
        failure. Created PAUSED so the user reviews the ad before spending.

        Args:
            customer_id: Google Ads customer ID.
            name: Campaign name (seeds the ad group + budget names).
            budget_micros: Daily budget in micros (1_000_000 = $1).
            final_urls: At least one landing URL (set on the ad).
            business_name: Advertiser/brand name shown in the ad (≤25 chars).
            headlines: 1-5 short headlines, each ≤30 chars.
            long_headlines: EXACTLY one long headline, ≤90 chars (a list for the
                unified copy contract; only the first element is used).
            descriptions: 1-5 descriptions, each ≤90 chars.
            logos: ≥1 square (1:1) logo image ref — a Google Ads asset resource
                name (customers/<cid>/assets/<id>), a bare numeric asset id, OR a
                local asset UUID from /api/assets/upload / Studio (uploaded +
                cropped to 1:1 automatically).
            landscape_images: 1.91:1 marketing images (same ref forms as logos).
            square_images: 1:1 marketing images. Both a landscape and a square
                marketing image are required.
            landscape_logos: Optional 4:1 LANDSCAPE_LOGO images (min 512×128).
            location_ids: Optional geo target constant IDs to target.
            excluded_location_ids: Optional geo target constant IDs to EXCLUDE.
            language_ids: Optional language constant IDs to target.
            call_to_action_text: Optional CTA text for the ad.
            target_cpa_micros: Optional target CPA in micros (MaximizeConversions
                with a CPA target); omit for uncapped MaximizeConversions.
            final_mobile_urls: Optional mobile-specific URLs.
            start_date / end_date: Optional 'YYYY-MM-DD' campaign window.

        Returns:
            {
                "campaign_id": "...",
                "budget_id": "...",
                "ad_group_id": "...",
                "ad_id": "...",
                "asset_ids": {"landscape": [...], "square": [...], ...},
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
            "long_headlines": long_headlines,
            "descriptions": descriptions,
            "logos": logos,
            "landscape_logos": landscape_logos or [],
            "marketing_images": {
                "landscape": landscape_images or [],
                "square": square_images or [],
            },
            "location_ids": location_ids or [],
            "excluded_location_ids": excluded_location_ids or [],
            "language_ids": language_ids or [],
            "call_to_action_text": call_to_action_text,
            "target_cpa_micros": target_cpa_micros,
            "start_date": start_date,
            "end_date": end_date,
        }
        try:
            return await service.create_responsive_display_campaign(
                ctx=ctx, customer_id=customer_id, bundle=bundle
            )
        except RdaValidationError as e:
            return {"error": "VALIDATION_FAILED", "errors": e.errors}

    return [create_responsive_display_campaign]


def register_rda_tools(mcp: FastMCP[Any]) -> RdaOrchestrator:
    """Register the Responsive Display orchestrator tools with the FastMCP
    server."""
    service = RdaOrchestrator()
    for tool in create_rda_orchestrator_tools(service):
        mcp.tool(tool)
    return service
