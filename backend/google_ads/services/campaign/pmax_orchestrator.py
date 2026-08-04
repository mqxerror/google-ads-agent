"""Performance Max campaign creation — single-shot orchestrator.

Sequences the operations needed to stand up a working PMax campaign with
a complete asset group. PMax requires a *recipe*, not just an API call:

    1. CampaignBudget
    2. Campaign (advertising_channel_type=PERFORMANCE_MAX)
    3. Assets (text + image + YouTube video) — one per content item
    4. AssetGroup + AssetGroupAsset link rows in ONE atomic
       GoogleAdsService.Mutate call — the group is created under a
       temporary resource name (`.../assetGroups/-1`) and every asset is
       bound to that temp name with a field_type (HEADLINE /
       LONG_HEADLINE / DESCRIPTION / LOGO / MARKETING_IMAGE /
       SQUARE_MARKETING_IMAGE / PORTRAIT_MARKETING_IMAGE / YOUTUBE_VIDEO
       / BUSINESS_NAME) in the same request
    5. (Optional) AssetGroupSignal[] for audience signals

Steps 1-3 are sequential per-service calls — chosen for debuggability
and to match the rest of this codebase's per-service style. Step 4 MUST
be atomic: Google validates PMax asset minimums AT asset-group creation
time, so an empty create followed by separate link calls is always
rejected (asset_group_error NOT_ENOUGH_HEADLINE_ASSET et al., hit live
2026-06-10). If any later step fails, prior creations are removed so the
user never sees half a campaign in their Google Ads UI. Pre-flight
validation catches Google's hard minimums before we hit the wire so
users get clear, actionable errors instead of API exceptions.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastmcp import Context, FastMCP
from google.ads.googleads.errors import GoogleAdsException
from google.ads.googleads.v23.enums.types.advertising_channel_type import (
    AdvertisingChannelTypeEnum,
)
from google.ads.googleads.v23.enums.types.asset_field_type import AssetFieldTypeEnum
from google.ads.googleads.v23.enums.types.asset_group_status import (
    AssetGroupStatusEnum,
)
from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum
from google.ads.googleads.v23.services.services.google_ads_service import (
    GoogleAdsServiceClient,
)
from google.ads.googleads.v23.services.types.google_ads_service import (
    MutateGoogleAdsRequest,
    MutateOperation,
)

from google_ads.sdk_client import get_sdk_client
from google_ads.services.assets.asset_group_signal_service import (
    AssetGroupSignalService,
)
from google_ads.services.assets.asset_service import AssetService
from google_ads.services.bidding.budget_service import BudgetService
from google_ads.services.campaign import creative_images
from google_ads.services.campaign.campaign_service import CampaignService
from google_ads.services.campaign.creative_images import (  # noqa: F401 (re-export)
    ASPECT_TOLERANCE,
    GOOGLE_IMAGE_MIME_BY_EXT,
    IMAGE_SLOT_SPECS,
    MAX_GOOGLE_IMAGE_BYTES,
)
from google_ads.services.campaign.creative_images import (
    asset_resource_name as _asset_resource_name,
)
from google_ads.utils import format_customer_id, get_logger

# The Creative Spec Registry (backend/app/services). The orchestrator reads its
# limits from here instead of a local constant table (Epic 14, fence F1). Safe
# import: creative_specs pulls in creative_images (a leaf), never this module.
from app.services import creative_specs
from app.services.creative_specs import CampaignSpec, ValidationReport  # noqa: F401

# The image-creative helpers live in `creative_images` (shared with the Demand
# Gen orchestrator). They are re-exported above under their historical
# single-underscore names so nothing that imported them from this module
# breaks. `_locate_local_image` is bound as a module global — NOT a direct
# re-export — because the resubmit regression tests monkeypatch
# `pmax_orchestrator._locate_local_image`, and `_resolve_image_plan` passes
# this global into the shared resolver so the patch still takes effect.
_locate_local_image = creative_images.locate_local_image

# Post-create hooks — pull our own DB into agreement with what we just
# created in Google Ads, so the sidebar / agent / chronicle reflect the
# new campaign within seconds (not the V11 5-min staleness window).
# Imports inside the function to avoid an MCP-side dependency on the
# FastAPI app package at module import time.

logger = get_logger(__name__)


class ApiCtx:
    """Minimal duck-typed substitute for `fastmcp.Context` so the FastAPI
    route can drive the orchestrator without a real MCP session.

    All the primitive services (BudgetService, CampaignService, etc.)
    call `await ctx.log(level=..., message=...)` to surface progress;
    redirect those into the standard Python logger so the user can see
    them in the uvicorn output.
    """
    import logging as _logging

    async def log(self, *, level: str = "info", message: str = "") -> None:
        lvl = getattr(self._logging, level.upper(), self._logging.INFO)
        logger.log(lvl, message)


# Text field → Google AssetFieldType. This is API PLUMBING (which proto field a
# given text list links as), NOT a limit table — the counts/char caps that used
# to live here now come from the Creative Spec Registry (creative_specs). The
# order also fixes the create-path asset-creation/linking order.
TEXT_FIELD_TYPES = {
    "headlines":      AssetFieldTypeEnum.AssetFieldType.HEADLINE,
    "long_headlines": AssetFieldTypeEnum.AssetFieldType.LONG_HEADLINE,
    "descriptions":   AssetFieldTypeEnum.AssetFieldType.DESCRIPTION,
}

IMAGE_FIELD_TYPES = {
    "logos":     AssetFieldTypeEnum.AssetFieldType.LOGO,
    "landscape": AssetFieldTypeEnum.AssetFieldType.MARKETING_IMAGE,         # 1.91:1
    "square":    AssetFieldTypeEnum.AssetFieldType.SQUARE_MARKETING_IMAGE,  # 1:1
    "portrait":  AssetFieldTypeEnum.AssetFieldType.PORTRAIT_MARKETING_IMAGE,# 4:5 (optional)
}

REQUIRED_IMAGES = ("logos", "landscape", "square")  # each ≥1; portrait optional

# NOTE: GOOGLE_IMAGE_MIME_BY_EXT, MAX_GOOGLE_IMAGE_BYTES, IMAGE_SLOT_SPECS, and
# ASPECT_TOLERANCE now live in `creative_images` (shared with the Demand Gen
# orchestrator) and are re-exported at the top of this module for
# backward-compatible access as `pmax_orchestrator.<name>`.


class PMaxValidationError(Exception):
    """Raised when the input bundle doesn't meet Google's PMax minimums.

    The orchestrator catches this and returns a structured error so the
    wizard / chat agent can highlight the specific fields to fix.
    """

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class PMaxStepError(Exception):
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
            f"PMax create failed at step '{step}'. {cleanup} Underlying error: {original}"
        )


def _validate_bundle(bundle: Dict[str, Any], spec: CampaignSpec) -> ValidationReport:
    """Pre-flight validation against the Creative Spec Registry (FR1.1/FR1.4).

    Returns a ``ValidationReport``: verified-limit violations are ``errors``
    (the create path raises), unverified (soft) ones are ``warnings`` that ride
    the create response. Every limit is read from ``spec`` — there is no local
    limit constant (fence F1)."""
    report = ValidationReport()

    if not bundle.get("name"):
        report.errors.append("campaign 'name' is required")
    if not bundle.get("budget_micros"):
        report.errors.append("'budget_micros' is required (1_000_000 micros = $1)")

    # final URL: presence + format + length (FR1.4 gap closure)
    creative_specs.check_final_urls(bundle, spec, report)

    # business name: presence + ≤ business_name_max (FR1.4 gap closure)
    creative_specs.check_business_name(bundle, spec, report)

    # text fields: count (min AND max — the max closes the FR1.4 gap) + char caps
    creative_specs.check_text_fields(bundle, spec, report)
    # soft: ≥1 short (≤60) description — warns, never blocks (verified:false)
    creative_specs.check_short_description(bundle, spec, report)

    # required images (presence) + cross-slot total cap + logo cap (FR1.4)
    imgs = bundle.get("marketing_images") or {}
    if not (bundle.get("logos") or []):
        report.errors.append("need ≥1 logo image (asset_id or upload)")
    for slot, slot_spec in spec.images.items():
        if slot_spec.required and not (imgs.get(slot) or []):
            report.errors.append(f"need ≥1 {slot} marketing image")
    creative_specs.check_image_caps(bundle, spec, report)

    # search themes: ≤max_count × ≤max_chars (FR1.4 gap closure)
    creative_specs.check_search_themes(bundle, spec, report)

    # Video is OPTIONAL for a PMax asset group: when none is supplied Google
    # auto-generates one from the image + text assets. Do NOT hard-gate on it —
    # requiring ≥1 YouTube id was stricter than Google and blocked every
    # image-only asset group. (Google Ads API "Asset Requirements"; Help
    # 14528532 — verified 2026-08-03.) The wizard still nudges the operator to
    # supply their own video for control / 'Excellent' Ad Strength.

    return report


def _extract_resource_name(mutate_response: Dict[str, Any]) -> str:
    """Pull the first result's resource_name from a serialized mutate response.

    All of the per-service `create_*` helpers in this codebase return the
    response of `serialize_proto_message(response)`, which has shape
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


class PMaxOrchestrator:
    """The recipe. Holds references to each primitive service so it can
    sequence them and roll back on failure."""

    def __init__(self) -> None:
        self._budget = BudgetService()
        self._campaign = CampaignService()
        self._asset = AssetService()
        self._asset_group_signal = AssetGroupSignalService()
        self._google_ads: Optional[GoogleAdsServiceClient] = None

    @property
    def google_ads_client(self) -> GoogleAdsServiceClient:
        """GoogleAdsService client — the multi-resource Mutate endpoint
        used for the atomic asset-group-plus-links create. Lazy, same
        pattern as the per-resource service clients."""
        if self._google_ads is None:
            self._google_ads = get_sdk_client().client.get_service("GoogleAdsService")
        assert self._google_ads is not None
        return self._google_ads

    def _fetch_image_asset_dims(
        self, customer_id: str, resource_names: List[str]
    ) -> Dict[str, tuple[int, int]]:
        """GAQL lookup: full-size pixel dimensions for existing image
        assets, keyed by resource name. Assets that aren't found, or
        aren't IMAGE assets, simply don't appear in the result — the
        caller treats "missing" as "aspect can't be verified" and
        rejects pre-flight. Isolated as a method so unit tests can stub
        it without a live SDK client."""
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
        self,
        customer_id: str,
        bundle: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Classify every image ref in the bundle BEFORE touching Google.

        Thin wrapper over ``creative_images.resolve_image_plan`` — the shared
        classify + crop + pre-uploaded-aspect-verify logic used by BOTH the
        PMax and Demand Gen orchestrators. See that function for the full
        rationale (the 2026-06 ASPECT_RATIO_NOT_ALLOWED live incident).

        ``_locate_local_image`` is passed as the module global (not the shared
        default) so the resubmit regression tests' monkeypatch of
        ``pmax_orchestrator._locate_local_image`` still takes effect.

        Returns {slot: [{"kind": "google"|"local", ...}]} for
        logos/landscape/square/portrait. Raises PMaxValidationError listing
        every unresolvable ref so the user fixes them all in one pass — and
        nothing has been created in Google yet.
        """
        mi = bundle.get("marketing_images") or {}
        slots = {
            "logos": list(bundle.get("logos") or []),
            "landscape": list(mi.get("landscape") or []),
            "square": list(mi.get("square") or []),
            "portrait": list(mi.get("portrait") or []),
        }
        return await creative_images.resolve_image_plan(
            customer_id=customer_id,
            slots=slots,
            fetch_dims=self._fetch_image_asset_dims,
            error_factory=PMaxValidationError,
            locate=_locate_local_image,
        )

    def _signal_operation(self, asset_group_rn: str, sig: Any):
        """Normalize one bundle audience-signal entry into a mutate op.

        Accepts plain strings (treated as search themes — what the
        wizard collects), {"search_theme"/"text": ...} dicts, or
        {"audience_resource_name"/"audience": ...} dicts for saved
        audiences. Returns None for shapes we don't recognize so the
        caller can warn instead of crash.
        """
        svc = self._asset_group_signal
        if isinstance(sig, str):
            text = sig.strip()
            if not text:
                return None
            return svc.create_search_theme_signal(
                asset_group=asset_group_rn, search_theme=text,
            )
        if isinstance(sig, dict):
            audience = sig.get("audience_resource_name") or sig.get("audience")
            if audience:
                return svc.create_audience_signal(
                    asset_group=asset_group_rn,
                    audience_resource_name=str(audience),
                )
            theme = sig.get("search_theme") or sig.get("text")
            if theme and str(theme).strip():
                return svc.create_search_theme_signal(
                    asset_group=asset_group_rn,
                    search_theme=str(theme).strip(),
                )
        return None

    async def create_pmax_campaign(
        self,
        ctx: Context,
        customer_id: str,
        bundle: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a PMax campaign from a complete asset bundle.

        See the module docstring for the bundle shape and the operation
        sequence. Returns:
            {
                "campaign_id": str,
                "budget_id": str,
                "asset_group_id": str,
                "asset_ids": {<field>: [str, ...], ...},
                "warnings": [str, ...]   # non-fatal issues during create
            }

        Raises PMaxValidationError pre-flight, Exception on any Google
        API failure (with prior creations rolled back).
        """
        spec = creative_specs.get("pmax")
        report = _validate_bundle(bundle, spec)
        if report.errors:
            raise PMaxValidationError(report.errors)
        customer_id = format_customer_id(customer_id)

        # Pre-flight: classify every image ref (Google asset ref vs local
        # upload UUID), verify local files exist, and aspect-check
        # pre-uploaded Google assets BEFORE creating anything in Google —
        # a bad ref fails as a clean validation error instead of a
        # created-then-rolled-back campaign.
        image_plan = await self._resolve_image_plan(customer_id, bundle)

        created_budget_rn: Optional[str] = None
        created_campaign_rn: Optional[str] = None
        # Soft-limit (verified:false) violations surface as warnings, never block.
        warnings: List[str] = list(report.warnings)
        failed_step = "pre-flight"

        try:
            # ── Step 1 — Budget ───────────────────────────────────────
            failed_step = "budget creation"
            await ctx.log(level="info", message=f"[PMax] Creating budget for '{bundle['name']}' at {bundle['budget_micros']} micros/day...")
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
            await ctx.log(level="info", message=f"[PMax] Creating PERFORMANCE_MAX campaign...")
            campaign_resp = await self._campaign.create_campaign(
                ctx=ctx,
                customer_id=customer_id,
                name=bundle["name"],
                budget_resource_name=created_budget_rn,
                advertising_channel_type=(
                    AdvertisingChannelTypeEnum.AdvertisingChannelType.PERFORMANCE_MAX
                ),
                # Start PAUSED so the user can review the asset group in
                # the Google UI before spending money. They flip to
                # ENABLED themselves once they're happy.
                status=CampaignStatusEnum.CampaignStatus.PAUSED,
                start_date=bundle.get("start_date"),
                end_date=bundle.get("end_date"),
            )
            created_campaign_rn = _extract_resource_name(campaign_resp)
            campaign_id = _id_from_resource_name(created_campaign_rn)

            # ── Step 3 — Text assets ──────────────────────────────────
            failed_step = "text asset creation"
            asset_ids: Dict[str, List[str]] = {}
            for field, _field_type in TEXT_FIELD_TYPES.items():
                rns = []
                for text in bundle[field]:
                    ar = await self._asset.create_text_asset(
                        ctx=ctx, customer_id=customer_id, text=text,
                    )
                    rns.append(_extract_resource_name(ar))
                asset_ids[field] = rns

            # ── Step 3b — Business name asset (single text) ───────────
            failed_step = "business name asset creation"
            biz_resp = await self._asset.create_text_asset(
                ctx=ctx, customer_id=customer_id, text=bundle["business_name"],
            )
            asset_ids["business_name"] = [_extract_resource_name(biz_resp)]

            # ── Step 3c — Image assets ────────────────────────────────
            # The UUID → resource-name bridge. Refs were classified by
            # _resolve_image_plan pre-flight:
            #   • "google" — already a Google asset ref (resource name or
            #     numeric id); passes through unchanged so MCP/agent-
            #     created bundles keep working.
            #   • "local" — a UUID from /api/assets/upload or a Studio
            #     generation; push its bytes to Google as an image asset
            #     and swap the UUID for the returned resource name. The
            #     swap stays server-side only (asset_ids in the result);
            #     the client bundle keeps its local UUIDs so a resubmit
            #     always re-fits from the local source.
            # Dedupe is keyed by (uuid, slot aspect) — NOT uuid alone.
            # The same source image filling two different-aspect slots
            # MUST upload once per crop: keying by uuid alone reused the
            # first slot's crop for every later slot (the 1:1 logo crop
            # got linked as the 1.91:1 MARKETING_IMAGE), which is exactly
            # the ASPECT_RATIO_NOT_ALLOWED that killed the atomic create
            # despite the pre-flight crop (hit live 2026-06-11).
            failed_step = "image asset upload"
            uploaded: Dict[tuple[str, float], str] = {}  # (uuid, aspect) → google rn
            for slot, entries in image_plan.items():
                rns = []
                for n, entry in enumerate(entries):
                    if entry["kind"] == "google":
                        rns.append(entry["ref"])
                        continue
                    dedupe_key = (entry["ref"], IMAGE_SLOT_SPECS[slot]["aspect"])
                    if dedupe_key not in uploaded:
                        # "data" is set when pre-flight cropped/transcoded
                        # the file for THIS slot (e.g. Studio .webp → PNG);
                        # otherwise the bytes come straight off disk.
                        img_resp = await self._asset.create_image_asset(
                            ctx=ctx,
                            customer_id=customer_id,
                            image_data=entry.get("data") or entry["path"].read_bytes(),
                            name=f"{bundle['name']} — {slot} {n + 1}",
                            mime_type=entry["mime"],
                        )
                        uploaded[dedupe_key] = _extract_resource_name(img_resp)
                    rns.append(uploaded[dedupe_key])
                asset_ids[slot] = rns
            if uploaded:
                await ctx.log(
                    level="info",
                    message=f"[PMax] Uploaded {len(uploaded)} local image(s) to Google Ads as image assets",
                )

            # ── Step 3d — YouTube video assets ────────────────────────
            failed_step = "YouTube video asset creation"
            video_rns = []
            for idx, yt_id in enumerate(bundle["video_youtube_ids"]):
                vr = await self._asset.create_youtube_video_asset(
                    ctx=ctx,
                    customer_id=customer_id,
                    name=f"{bundle['name']} — video {idx + 1}",
                    youtube_video_id=yt_id,
                )
                video_rns.append(_extract_resource_name(vr))
            asset_ids["videos"] = video_rns

            # ── Step 4 — Asset group + asset links (ONE atomic mutate) ─
            # Google validates PMax asset minimums AT asset-group
            # creation time, so creating an empty group and linking
            # afterwards is impossible (asset_group_error
            # NOT_ENOUGH_HEADLINE_ASSET et al., hit live 2026-06-10).
            # The documented pattern: one GoogleAdsService.Mutate call
            # whose first operation creates the group under a temporary
            # resource name (-1) and whose remaining operations link
            # every asset to that temp name — Google resolves the temp
            # id within the request and applies it all-or-nothing.
            failed_step = "asset group creation (atomic, with asset links)"
            temp_ag_rn = f"customers/{customer_id}/assetGroups/-1"
            mutate_ops: List[MutateOperation] = []

            ag_op = MutateOperation()
            ag = ag_op.asset_group_operation.create
            ag.resource_name = temp_ag_rn
            ag.campaign = created_campaign_rn
            ag.name = f"{bundle['name']} — Asset Group 1"
            ag.final_urls.extend(bundle["final_urls"])
            if bundle.get("final_mobile_urls"):
                ag.final_mobile_urls.extend(bundle["final_mobile_urls"])
            ag.status = AssetGroupStatusEnum.AssetGroupStatus.PAUSED
            mutate_ops.append(ag_op)

            def _link_op(asset_ref: str, field_type) -> MutateOperation:
                op = MutateOperation()
                link = op.asset_group_asset_operation.create
                link.asset_group = temp_ag_rn
                link.asset = _asset_resource_name(customer_id, asset_ref)
                link.field_type = field_type
                return op

            for field, field_type in TEXT_FIELD_TYPES.items():
                for rn in asset_ids[field]:
                    mutate_ops.append(_link_op(rn, field_type))

            # business name uses its own field type
            for rn in asset_ids["business_name"]:
                mutate_ops.append(
                    _link_op(rn, AssetFieldTypeEnum.AssetFieldType.BUSINESS_NAME)
                )

            for field, ft in IMAGE_FIELD_TYPES.items():
                for rn in asset_ids[field]:
                    mutate_ops.append(_link_op(rn, ft))

            for rn in asset_ids["videos"]:
                mutate_ops.append(
                    _link_op(rn, AssetFieldTypeEnum.AssetFieldType.YOUTUBE_VIDEO)
                )

            await ctx.log(
                level="info",
                message=(
                    f"[PMax] Creating asset group atomically with "
                    f"{len(mutate_ops) - 1} asset link(s)..."
                ),
            )
            ga_request = MutateGoogleAdsRequest()
            ga_request.customer_id = customer_id
            ga_request.mutate_operations.extend(mutate_ops)
            try:
                ga_resp = self.google_ads_client.mutate(request=ga_request)
            except GoogleAdsException as e:
                # Match the per-service error style so the wizard sees
                # the readable failure detail, not a gRPC blob.
                raise Exception(f"Google Ads API error: {e.failure}") from e

            # Results come back in operation order — the first is the
            # asset group create, carrying its REAL resource name.
            op_responses = list(ga_resp.mutate_operation_responses)
            if not op_responses:
                raise RuntimeError(
                    f"atomic mutate returned no results: {ga_resp!r}"
                )
            ag_rn = op_responses[0].asset_group_result.resource_name
            if not ag_rn:
                raise RuntimeError(
                    f"atomic mutate's first result is not an asset group: "
                    f"{op_responses[0]!r}"
                )
            asset_group_id = _id_from_resource_name(ag_rn)

            # ── Step 5b — Audience signals (optional, best-effort) ────
            # Signals steer PMax's initial exploration; the campaign is
            # complete and valid without them, so a failure here lands
            # in warnings instead of rolling everything back.
            failed_step = "audience signal attachment"
            signals = bundle.get("audience_signals") or []
            if signals:
                try:
                    sig_ops = []
                    for i, sig in enumerate(signals):
                        op = self._signal_operation(ag_rn, sig)
                        if op is None:
                            warnings.append(
                                f"audience_signals[{i}] skipped — unrecognized shape "
                                f"(want a string, {{'search_theme': ...}}, or "
                                f"{{'audience_resource_name': ...}}): {sig!r}"
                            )
                        else:
                            sig_ops.append(op)
                    if sig_ops:
                        sig_resp = self._asset_group_signal.mutate_asset_group_signals(
                            customer_id=customer_id,
                            operations=sig_ops,
                            partial_failure=True,
                        )
                        # Empty google.rpc.Status serializes to "" — a
                        # bare truthiness check on the proto is useless.
                        pfe = str(
                            getattr(sig_resp, "partial_failure_error", "") or ""
                        ).strip()
                        if pfe:
                            warnings.append(f"some audience signals were rejected: {pfe}")
                        await ctx.log(
                            level="info",
                            message=f"[PMax] Attached {len(sig_ops)} audience signal(s) to asset group {asset_group_id}",
                        )
                except Exception as e:
                    warnings.append(
                        f"audience signal attach failed (campaign unaffected): {e}"
                    )

            await ctx.log(
                level="info",
                message=f"[PMax] OK — campaign_id={campaign_id} asset_group_id={asset_group_id}",
            )

            # ── Step 6 — Bring our own DB in agreement with reality ──
            # Without this the sidebar would show stale data for up to
            # 5 minutes (V11 staleness threshold), and the agent would
            # have no memory folder for the new campaign.
            failed_step = "post-create local sync"
            await self._post_create_sync(
                ctx=ctx,
                account_id=customer_id,
                campaign_id=campaign_id,
                asset_group_id=asset_group_id,
                bundle=bundle,
                asset_ids_local={k: [_id_from_resource_name(rn) for rn in v] for k, v in asset_ids.items()},
            )

            return {
                "campaign_id": campaign_id,
                "budget_id": budget_id,
                "asset_group_id": asset_group_id,
                "asset_ids": {k: [_id_from_resource_name(rn) for rn in v] for k, v in asset_ids.items()},
                "warnings": warnings,
            }

        except PMaxValidationError:
            raise
        except Exception as e:
            await ctx.log(level="error", message=f"[PMax] failure at step '{failed_step}': {e}; rolling back...")
            rollback_report = await self._rollback(
                ctx=ctx,
                customer_id=customer_id,
                campaign_rn=created_campaign_rn,
                budget_rn=created_budget_rn,
            )
            # Surface exactly which step died and what got cleaned up —
            # the wizard shows this verbatim, so it must be actionable.
            raise PMaxStepError(
                step=failed_step, original=e, rollback_report=rollback_report,
            ) from e

    async def _post_create_sync(
        self,
        ctx: Context,
        account_id: str,
        campaign_id: str,
        asset_group_id: str,
        bundle: Dict[str, Any],
        asset_ids_local: Dict[str, List[str]],
    ) -> None:
        """Refresh local DB + bootstrap memory after a successful create.

        All best-effort: a failure here mustn't fail the whole flow,
        because the campaign IS already live in Google. Each block is
        independently try/excepted; the user sees a clean success even
        if one of the local-side updates hiccups.
        """
        # FastAPI-side imports live inside the function so the MCP
        # server can import this module standalone (e.g. for `--help`)
        # without dragging the app package in.
        try:
            from app.services import campaigns_repo, asset_groups_repo
            from app.services.campaign_memory import init_campaign_memory
            from app.services.chronicle import (
                _chronicle_path, _init_chronicle, _insert_entry, load_chronicle,
            )
            from datetime import datetime as _dt
            import re as _re
        except ImportError as e:
            await ctx.log(
                level="warning",
                message=f"[PMax post-create] app-side imports unavailable, skipping local sync: {e}",
            )
            return

        # 1) Pull fresh campaign list into the V11 `campaigns` table so
        #    the sidebar shows the new campaign immediately.
        try:
            n = await campaigns_repo.sync_campaigns(account_id)
            await ctx.log(level="info", message=f"[PMax post-create] campaigns sync: {n} rows")
        except Exception as e:
            await ctx.log(level="warning", message=f"[PMax post-create] campaigns sync failed: {e}")

        # 2) Record the asset group we sent into the V12 `asset_groups` table.
        try:
            await asset_groups_repo.upsert_asset_group(
                account_id=account_id,
                campaign_id=campaign_id,
                asset_group_id=asset_group_id,
                name=f"{bundle['name']} — Asset Group 1",
                status="PAUSED",
                final_urls=bundle.get("final_urls"),
                business_name=bundle.get("business_name"),
                headlines=bundle.get("headlines"),
                long_headlines=bundle.get("long_headlines"),
                descriptions=bundle.get("descriptions"),
                asset_refs=asset_ids_local,
                signals=bundle.get("audience_signals"),
            )
        except Exception as e:
            await ctx.log(level="warning", message=f"[PMax post-create] asset_groups upsert failed: {e}")

        # 3) Bootstrap the per-campaign memory folder. The seeded
        #    pinned_facts.md ensures the agent won't invent CPA/CPC
        #    numbers for the brand-new campaign on its first read.
        try:
            init_campaign_memory(
                account_id=account_id,
                campaign_id=campaign_id,
                campaign_name=bundle["name"],
            )
        except Exception as e:
            await ctx.log(level="warning", message=f"[PMax post-create] memory init failed: {e}")

        # 4) Chronicle entry for the creation event — surfaces in every
        #    future agent turn for this campaign. Use the chronicle
        #    primitives directly (not `update_chronicle`, which expects a
        #    full conversation + calls Sonnet) — we already know exactly
        #    what to record.
        try:
            existing = load_chronicle(account_id, campaign_id) or _init_chronicle(
                account_id, campaign_id, bundle["name"],
            )
            now = _dt.now()
            entry_line = (
                f"- **{now.strftime('%b %d')}** — [pmax_strategist] "
                f"Created PMax campaign **{bundle['name']}** "
                f"(daily budget ${bundle['budget_micros'] / 1_000_000:.2f}, "
                f"asset group `{asset_group_id}`, "
                f"{len(bundle.get('headlines') or [])}H/"
                f"{len(bundle.get('long_headlines') or [])}LH/"
                f"{len(bundle.get('descriptions') or [])}D, "
                f"{len(bundle.get('video_youtube_ids') or [])} video(s)). "
                f"Starts PAUSED — user enables after reviewing the asset group."
            )
            month_header = f"### {now.strftime('%B %Y')}"
            updated = _insert_entry(existing, month_header, entry_line)
            updated = _re.sub(
                r"Last updated: .*",
                f"Last updated: {now.strftime('%Y-%m-%d')}",
                updated,
                count=1,
            )
            _chronicle_path(account_id, campaign_id).write_text(updated, encoding="utf-8")
        except Exception as e:
            await ctx.log(level="warning", message=f"[PMax post-create] chronicle append failed: {e}")

    async def _rollback(
        self,
        ctx: Context,
        customer_id: str,
        campaign_rn: Optional[str],
        budget_rn: Optional[str],
    ) -> List[str]:
        """Best-effort removal of the campaign + budget we just created
        when something downstream failed.

        Removal MUST use a REMOVE mutate operation (operation.remove =
        resource name) — Google rejects `update status=REMOVED` with
        request_error INVALID_ENUM_VALUE ("Enum value 'REMOVED' cannot
        be used"), hit live 2026-06-10. Campaign first, then its budget
        (a budget can only be removed once no live campaign references
        it). Assets created along the way are intentionally left behind
        — they're reusable from the account library and don't spend
        money.

        Returns a human-readable report of what was (and wasn't) cleaned
        up, for inclusion in the PMaxStepError surfaced to the wizard.
        """
        report: List[str] = []
        campaign_removed = campaign_rn is None
        if campaign_rn:
            cid = _id_from_resource_name(campaign_rn)
            try:
                await self._campaign.remove_campaign(
                    ctx=ctx,
                    customer_id=customer_id,
                    campaign_id=cid,
                )
                campaign_removed = True
                await ctx.log(level="info", message=f"[PMax rollback] removed campaign {cid}")
                report.append(f"Rolled back: campaign {cid} was removed.")
            except Exception as e:
                await ctx.log(level="warning", message=f"[PMax rollback] could not remove campaign: {e}")
                report.append(
                    f"ROLLBACK INCOMPLETE: campaign {cid} could not be removed ({e}) — "
                    f"remove it manually in the Google Ads UI. It was created PAUSED, "
                    f"so it is not spending."
                )
        if budget_rn:
            bid = _id_from_resource_name(budget_rn)
            try:
                if not campaign_removed:
                    # A budget referenced by a still-live campaign can't
                    # be removed — don't burn an API call on it.
                    raise RuntimeError("its campaign could not be removed first")
                await self._budget.remove_campaign_budget(
                    ctx=ctx,
                    customer_id=customer_id,
                    budget_id=bid,
                )
                await ctx.log(level="info", message=f"[PMax rollback] removed budget {bid}")
                report.append(f"Rolled back: budget {bid} was removed.")
            except Exception as e:
                await ctx.log(
                    level="warning",
                    message=(
                        f"[PMax rollback] orphan budget {bid} left in account ({e}). "
                        f"Safe to ignore — budgets without a campaign don't spend."
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


def create_pmax_orchestrator_tools(
    service: PMaxOrchestrator,
) -> List[Callable[..., Awaitable[Any]]]:
    """Wrap the orchestrator as FastMCP tool functions."""

    async def create_pmax_campaign(
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
        landscape_images: List[str],
        square_images: List[str],
        video_youtube_ids: List[str],
        portrait_images: Optional[List[str]] = None,
        audience_signals: Optional[List[str]] = None,
        final_mobile_urls: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Performance Max campaign in one shot.

        Validates against Google's PMax minimums (≥3 headlines, ≥1 long
        headline, ≥2 descriptions, ≥1 logo, ≥1 landscape image, ≥1
        square image, ≥1 YouTube video, business name) and rolls back on
        partial failure.

        Args:
            customer_id: Google Ads customer ID.
            name: Campaign name (also seeds the asset group + budget names).
            budget_micros: Daily budget in micros (1_000_000 = $1).
            final_urls: At least one landing URL.
            business_name: Brand name displayed in some auto-generated layouts.
            headlines: ≥3 headlines, each ≤30 chars.
            long_headlines: ≥1 long headline, each ≤90 chars.
            descriptions: ≥2 descriptions, each ≤90 chars.
            logos: ≥1 logo image ref — a Google Ads asset resource name
                (customers/<cid>/assets/<id>), a bare numeric asset id, OR a
                local asset UUID from /api/assets/upload / Studio (the
                orchestrator uploads local files to Google automatically).
            landscape_images: ≥1 image ref (same forms as logos), 1.91:1 marketing image.
            square_images: ≥1 image ref (same forms as logos), 1:1 marketing image.
            video_youtube_ids: ≥1 YouTube video ID (the campaign needs at least one video for PMax).
            portrait_images: Optional list of 4:5 portrait marketing images.
            audience_signals: Optional search-theme strings to seed PMax's
                audience exploration (attached as asset group signals after create).
            final_mobile_urls: Optional mobile-specific URLs.
            start_date / end_date: Optional 'YYYY-MM-DD' campaign window.

        Returns:
            {
                "campaign_id": "...",
                "budget_id": "...",
                "asset_group_id": "...",
                "asset_ids": {...},
                "warnings": []
            }

        The campaign is created in PAUSED state so the user can review
        the asset group in the Google Ads UI before spending money.
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
            "marketing_images": {
                "landscape": landscape_images,
                "square": square_images,
                "portrait": portrait_images or [],
            },
            "video_youtube_ids": video_youtube_ids,
            "audience_signals": audience_signals,
            "start_date": start_date,
            "end_date": end_date,
        }
        try:
            return await service.create_pmax_campaign(ctx=ctx, customer_id=customer_id, bundle=bundle)
        except PMaxValidationError as e:
            # Surface a structured error the wizard can show field-by-field.
            return {"error": "VALIDATION_FAILED", "errors": e.errors}

    return [create_pmax_campaign]


def register_pmax_tools(mcp: FastMCP[Any]) -> PMaxOrchestrator:
    """Register the PMax orchestrator tool with the FastMCP server."""
    service = PMaxOrchestrator()
    for tool in create_pmax_orchestrator_tools(service):
        mcp.tool(tool)
    return service
