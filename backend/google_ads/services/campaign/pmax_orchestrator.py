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

from pathlib import Path
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
from google_ads.services.campaign.campaign_service import CampaignService
from google_ads.utils import format_customer_id, get_logger

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


# Google's hard minimums for PMax. Bundle is rejected pre-flight if any
# of these fail so we don't waste a round-trip on a doomed request.
TEXT_RULES = {
    "headlines":      {"min_count": 3, "max_chars": 30,  "field_type": AssetFieldTypeEnum.AssetFieldType.HEADLINE},
    "long_headlines": {"min_count": 1, "max_chars": 90,  "field_type": AssetFieldTypeEnum.AssetFieldType.LONG_HEADLINE},
    "descriptions":   {"min_count": 2, "max_chars": 90,  "field_type": AssetFieldTypeEnum.AssetFieldType.DESCRIPTION},
}

IMAGE_FIELD_TYPES = {
    "logos":     AssetFieldTypeEnum.AssetFieldType.LOGO,
    "landscape": AssetFieldTypeEnum.AssetFieldType.MARKETING_IMAGE,         # 1.91:1
    "square":    AssetFieldTypeEnum.AssetFieldType.SQUARE_MARKETING_IMAGE,  # 1:1
    "portrait":  AssetFieldTypeEnum.AssetFieldType.PORTRAIT_MARKETING_IMAGE,# 4:5 (optional)
}

REQUIRED_IMAGES = ("logos", "landscape", "square")  # each ≥1; portrait optional

# Google Ads only accepts these image formats for image assets. The local
# upload endpoint (/api/assets/upload) is deliberately broader (webp, mp4,
# audio...) because Studio uses it for non-Google purposes too — so the
# format gets re-checked at bridge time, not at upload time.
GOOGLE_IMAGE_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}

# Google rejects image assets above 5120KB — checked pre-flight so an
# oversized file gets transcoded (or cleanly refused) instead of blowing
# up the create mid-recipe.
MAX_GOOGLE_IMAGE_BYTES = 5 * 1024 * 1024

# Google enforces the slot's EXACT aspect ratio (±1% tolerance) and a
# hard minimum pixel size per PMax image field type. A near-miss — a
# 16:9 image in the 1.91:1 MARKETING_IMAGE slot — fails the whole
# atomic create with ASPECT_RATIO_NOT_ALLOWED at the asset_group_asset
# op (hit live 2026-06; campaign + budget rolled back correctly but the
# user got a Google error blob instead of a campaign). Local images are
# therefore center-cropped to the exact aspect pre-flight; images that
# sit below the minimum get a clean 422 instead. `aspect` is w/h.
IMAGE_SLOT_SPECS = {
    "logos":     {"aspect": 1.0,  "min_w": 128, "min_h": 128, "label": "1:1"},
    "landscape": {"aspect": 1.91, "min_w": 600, "min_h": 314, "label": "1.91:1"},
    "square":    {"aspect": 1.0,  "min_w": 300, "min_h": 300, "label": "1:1"},
    "portrait":  {"aspect": 0.8,  "min_w": 480, "min_h": 600, "label": "4:5"},
}
ASPECT_TOLERANCE = 0.01  # Google allows ±1% off the exact ratio


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


def _is_google_asset_ref(ref: str) -> bool:
    """True when `ref` already identifies a Google Ads asset — either a
    full resource name (`customers/123/assets/456`) or a bare numeric
    asset id. Anything else is treated as a local asset id (UUID) from
    /api/assets/upload or a Studio generation, whose bytes still need to
    be pushed to Google as an image asset."""
    ref = (ref or "").strip()
    if not ref:
        return False
    return ref.isdigit() or (ref.startswith("customers/") and "/assets/" in ref)


def _encode_for_google(img) -> Optional[tuple[bytes, str]]:
    """Encode a Pillow image to a (bytes, mime) pair under Google's 5MB
    cap, or None when even a JPEG re-encode busts it (caller downscales
    and retries). PNG first (lossless, keeps alpha — Studio .webp and
    logo transparency); JPEG q90 fallback for the Higgsfield Soul/4K
    outputs whose PNGs routinely exceed 5MB."""
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    if len(data) <= MAX_GOOGLE_IMAGE_BYTES:
        return data, "image/png"
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    data = buf.getvalue()
    if len(data) <= MAX_GOOGLE_IMAGE_BYTES:
        return data, "image/jpeg"
    return None


def _fit_image_for_slot(
    path: Path, slot: str, mime: Optional[str] = None
) -> Optional[tuple[bytes, str]]:
    """Make a local image Google-acceptable for `slot`, or reject it.

    Google enforces the slot's EXACT aspect (±1%) and a minimum pixel
    size — see IMAGE_SLOT_SPECS. The pipeline:

      1. Center-crop to the slot's exact aspect when off by more than
         the ±1% tolerance (crop, never letterbox/stretch).
      2. Reject anything below the slot minimum after cropping — we
         never upscale; Google would just serve a blurry ad.
      3. Re-encode (PNG first, JPEG fallback), downscaling at the same
         aspect until under the 5MB cap — but never below the minimum.

    Returns None when the on-disk file is already fully compliant
    (Google-OK format per `mime`, exact aspect, ≥ minimum, ≤ 5MB) so
    the caller can pass the original bytes through untouched — this
    keeps e.g. animated GIFs intact. Otherwise returns (bytes, mime).

    Raises ValueError with a user-actionable message phrased to read
    naturally after "<slot>[i] ('<ref>') ..."; the caller folds it into
    the pre-flight PMaxValidationError (HTTP 422), so a bad image fails
    BEFORE anything is created in Google.
    """
    from PIL import Image  # local import — keeps module import light

    spec = IMAGE_SLOT_SPECS[slot]
    target = spec["aspect"]

    with Image.open(path) as opened:
        opened.load()
        img = opened
        w, h = img.size
        if not w or not h:
            raise ValueError("has zero width/height — re-export and re-upload")

        # 1 — center-crop to the exact aspect when off by more than 1%.
        aspect_ok = abs((w / h) - target) <= target * ASPECT_TOLERANCE
        if not aspect_ok:
            if (w / h) > target:  # too wide — trim left/right
                new_w, new_h = max(1, round(h * target)), h
            else:  # too tall — trim top/bottom
                new_w, new_h = w, max(1, round(w / target))
            left = (w - new_w) // 2
            top = (h - new_h) // 2
            img = img.crop((left, top, left + new_w, top + new_h))
            w, h = img.size

        # 2 — minimum size (post-crop; cropping only ever shrinks).
        if w < spec["min_w"] or h < spec["min_h"]:
            crop_note = (
                "" if aspect_ok
                else f" after center-cropping to {spec['label']}"
            )
            raise ValueError(
                f"is {w}x{h}{crop_note} — below Google's "
                f"{spec['min_w']}x{spec['min_h']} minimum for this slot "
                f"({spec['label']}); use a larger source image"
            )

        # Fully compliant on disk → pass original bytes through.
        if (
            aspect_ok
            and mime is not None
            and path.stat().st_size <= MAX_GOOGLE_IMAGE_BYTES
        ):
            return None

        # 3 — encode under the 5MB cap, downscaling (same aspect) as
        # needed but never below the slot minimum.
        while True:
            encoded = _encode_for_google(img)
            if encoded is not None:
                return encoded
            scaled_w = int(w * 0.8)
            scaled_h = max(1, round(scaled_w / target))
            if scaled_w < spec["min_w"] or scaled_h < spec["min_h"]:
                raise ValueError(
                    f"can't be compressed under Google's 5120KB cap without "
                    f"dropping below the {spec['min_w']}x{spec['min_h']} "
                    f"minimum — re-export a lighter PNG/JPEG and re-upload"
                )
            img = img.resize((scaled_w, scaled_h), Image.LANCZOS)
            w, h = img.size


async def _locate_local_image(ref: str) -> tuple[Path, Optional[str]]:
    """Map a local asset id (UUID from /api/assets/upload or a Studio
    generation) to its on-disk file + Google-compatible MIME type.

    Looks up the `ad_assets` DB row first (DB row = source of truth),
    then falls back to globbing ASSETS_DIR (the upload endpoint stores
    blobs as `{uuid}{ext}`). Returns mime=None when the file exists but
    isn't a format Google accepts (caller transcodes to PNG). Raises
    LookupError with a user-actionable reason — phrased to read
    naturally after "<slot>[i] ('<ref>') ..." — when the bytes can't be
    found locally.
    """
    # App-side imports live inside the function so the MCP server can
    # import this module standalone (same pattern as _post_create_sync).
    try:
        from app.database import get_db
        from app.routers.assets import ASSETS_DIR
    except ImportError as e:
        raise LookupError(
            f"is not a Google Ads asset resource name, and local-upload "
            f"resolution is unavailable in this process ({e}) — pass a "
            f"customers/<cid>/assets/<id> resource name instead"
        )

    # Defensive: refs feed a path lookup below; reject anything that
    # isn't a simple token.
    if "/" in ref or "\\" in ref or ".." in ref:
        raise LookupError(
            "is not a recognized asset reference (expected a Google Ads "
            "asset resource name or a local upload id)"
        )

    path: Optional[Path] = None
    db = await get_db()
    try:
        cur = await db.execute("SELECT url, type FROM ad_assets WHERE id = ?", (ref,))
        row = await cur.fetchone()
    finally:
        await db.close()

    if row:
        if row["type"] != "image":
            raise LookupError(
                f"is a {row['type']} asset — only images can fill "
                f"logo/marketing-image slots"
            )
        url = row["url"] or ""
        if url.startswith("/api/assets/file/") or url.startswith("/api/video/assets/"):
            path = ASSETS_DIR / url.rsplit("/", 1)[-1]

    if path is None or not path.is_file():
        # Glob fallback — covers rows whose url points elsewhere (e.g. a
        # Higgsfield CDN url after a failed local download) IF the blob
        # actually landed on disk, plus the missing-DB-row edge.
        matches = sorted(ASSETS_DIR.glob(f"{ref}.*"))
        path = matches[0] if matches else None

    if path is None or not path.is_file():
        raise LookupError(
            "has no file on this server (upload may have failed or the "
            "asset only exists on an expiring CDN) — re-upload the image"
        )

    # mime=None → not directly Google-compatible; caller transcodes.
    return path, GOOGLE_IMAGE_MIME_BY_EXT.get(path.suffix.lower())


def _validate_bundle(bundle: Dict[str, Any]) -> None:
    """Pre-flight validation before any Google API call."""
    errs: List[str] = []

    if not bundle.get("name"):
        errs.append("campaign 'name' is required")
    if not bundle.get("budget_micros"):
        errs.append("'budget_micros' is required (1_000_000 micros = $1)")
    if not bundle.get("final_urls"):
        errs.append("'final_urls' is required (at least one URL)")
    if not bundle.get("business_name"):
        errs.append("'business_name' is required for the asset group")

    for field, rule in TEXT_RULES.items():
        items = bundle.get(field) or []
        if len(items) < rule["min_count"]:
            errs.append(f"need ≥{rule['min_count']} {field} (got {len(items)})")
        for i, txt in enumerate(items):
            if not isinstance(txt, str) or not txt.strip():
                errs.append(f"{field}[{i}] is empty")
            elif len(txt) > rule["max_chars"]:
                errs.append(f"{field}[{i}] is {len(txt)} chars (max {rule['max_chars']})")

    imgs = bundle.get("marketing_images") or {}
    if not (bundle.get("logos") or []):
        errs.append("need ≥1 logo image (asset_id or upload)")
    for kind in ("landscape", "square"):
        if not (imgs.get(kind) or []):
            errs.append(f"need ≥1 {kind} marketing image")
    if not (bundle.get("video_youtube_ids") or []):
        errs.append("need ≥1 YouTube video ID")

    if errs:
        raise PMaxValidationError(errs)


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


def _asset_resource_name(customer_id: str, ref: str) -> str:
    """Normalize an asset ref to a full resource name.

    Assets created in-process already carry full resource names; bundle
    entries that passed through as bare numeric ids (MCP/agent-created
    bundles) get expanded so the atomic mutate's link rows always
    reference `customers/<cid>/assets/<id>`.
    """
    return ref if ref.startswith("customers/") else f"customers/{customer_id}/assets/{ref}"


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

    async def _resolve_image_plan(
        self,
        bundle: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Classify every image ref in the bundle BEFORE touching Google.

        The wizard's upload endpoint (/api/assets/upload) stores files
        locally and returns a local UUID — those are NOT Google Ads
        resource names (the original Epic-8 blocker: _link() extracted
        garbage ids from them and Google rejected the create, rolling
        the whole campaign back). Entries that already look like Google
        asset refs pass through unchanged so MCP/agent-created bundles
        keep working.

        Returns {slot: [{"kind": "google"|"local", ...}]} for
        logos/landscape/square/portrait. Raises PMaxValidationError
        listing every unresolvable ref so the user fixes them all in
        one pass — and nothing has been created in Google yet.
        """
        mi = bundle.get("marketing_images") or {}
        slots = {
            "logos": list(bundle.get("logos") or []),
            "landscape": list(mi.get("landscape") or []),
            "square": list(mi.get("square") or []),
            "portrait": list(mi.get("portrait") or []),
        }
        plan: Dict[str, List[Dict[str, Any]]] = {}
        errs: List[str] = []
        for slot, refs in slots.items():
            entries: List[Dict[str, Any]] = []
            for i, raw_ref in enumerate(refs):
                ref = (raw_ref or "").strip()
                if not ref:
                    errs.append(f"{slot}[{i}] is empty")
                    continue
                if _is_google_asset_ref(ref):
                    entries.append({"kind": "google", "ref": ref})
                    continue
                try:
                    path, mime = await _locate_local_image(ref)
                except LookupError as e:
                    errs.append(f"{slot}[{i}] ('{ref[:40]}') {e}")
                    continue
                entry: Dict[str, Any] = {
                    "kind": "local", "ref": ref, "path": path, "mime": mime,
                }
                # Every local image goes through the slot fitter: it
                # center-crops to the slot's EXACT Google aspect (±1%),
                # transcodes non-Google formats (Studio .webp), enforces
                # the 5MB cap, and rejects below-minimum images — all
                # pre-flight, so a bad image fails as a clean 422 here
                # instead of ASPECT_RATIO_NOT_ALLOWED rolling back the
                # whole campaign mid-recipe (hit live 2026-06).
                try:
                    fitted = _fit_image_for_slot(path, slot, mime)
                except ValueError as exc:
                    errs.append(f"{slot}[{i}] ('{ref[:40]}') {exc}")
                    continue
                except Exception as exc:
                    errs.append(
                        f"{slot}[{i}] ('{ref[:40]}') is a {path.suffix} file "
                        f"that couldn't be processed for Google Ads ({exc}) — "
                        f"re-export as PNG/JPEG under 5MB and re-upload"
                    )
                    continue
                if fitted is not None:
                    entry["data"], entry["mime"] = fitted
                # fitted is None → file is already fully compliant
                # (format + exact aspect + size); original bytes pass
                # through untouched at upload time.
                entries.append(entry)
            plan[slot] = entries
        if errs:
            raise PMaxValidationError(errs)
        return plan

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
        _validate_bundle(bundle)
        customer_id = format_customer_id(customer_id)

        # Pre-flight: classify every image ref (Google asset ref vs local
        # upload UUID) and verify local files exist BEFORE creating
        # anything in Google — a bad ref fails as a clean validation
        # error instead of a created-then-rolled-back campaign.
        image_plan = await self._resolve_image_plan(bundle)

        created_budget_rn: Optional[str] = None
        created_campaign_rn: Optional[str] = None
        warnings: List[str] = []
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
            for field, rule in TEXT_RULES.items():
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
            #     and swap the UUID for the returned resource name.
            # A repeated local UUID (same image filling two slots)
            # uploads once.
            failed_step = "image asset upload"
            uploaded: Dict[str, str] = {}  # local uuid → google resource name
            for slot, entries in image_plan.items():
                rns = []
                for n, entry in enumerate(entries):
                    if entry["kind"] == "google":
                        rns.append(entry["ref"])
                        continue
                    local_id = entry["ref"]
                    if local_id not in uploaded:
                        # "data" is set when pre-flight transcoded the
                        # file (e.g. Studio .webp → PNG); otherwise the
                        # bytes come straight off disk.
                        img_resp = await self._asset.create_image_asset(
                            ctx=ctx,
                            customer_id=customer_id,
                            image_data=entry.get("data") or entry["path"].read_bytes(),
                            name=f"{bundle['name']} — {slot} {n + 1}",
                            mime_type=entry["mime"],
                        )
                        uploaded[local_id] = _extract_resource_name(img_resp)
                    rns.append(uploaded[local_id])
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

            for field, rule in TEXT_RULES.items():
                for rn in asset_ids[field]:
                    mutate_ops.append(_link_op(rn, rule["field_type"]))

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
