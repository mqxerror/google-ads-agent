"""Performance Max campaign creation — single-shot orchestrator.

Sequences the operations needed to stand up a working PMax campaign with
a complete asset group. PMax requires a *recipe*, not just an API call:

    1. CampaignBudget
    2. Campaign (advertising_channel_type=PERFORMANCE_MAX)
    3. Assets (text + image + YouTube video) — one per content item
    4. AssetGroup attached to the campaign
    5. AssetGroupAsset link rows — assets bound to the group with a
       field_type (HEADLINE / LONG_HEADLINE / DESCRIPTION / LOGO /
       MARKETING_IMAGE / SQUARE_MARKETING_IMAGE / PORTRAIT_MARKETING_IMAGE
       / YOUTUBE_VIDEO / BUSINESS_NAME)
    6. (Optional) AssetGroupSignal[] for audience signals

Sequential calls (not a single GoogleAdsService.mutate batch) — chosen for
debuggability and to match the rest of this codebase's per-service style.
If any later step fails, prior creations are removed so the user never
sees half a campaign in their Google Ads UI. Pre-flight validation
catches Google's hard minimums before we hit the wire so users get
clear, actionable errors instead of API exceptions.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastmcp import Context, FastMCP
from google.ads.googleads.v23.enums.types.advertising_channel_type import (
    AdvertisingChannelTypeEnum,
)
from google.ads.googleads.v23.enums.types.asset_field_type import AssetFieldTypeEnum
from google.ads.googleads.v23.enums.types.asset_group_status import (
    AssetGroupStatusEnum,
)
from google.ads.googleads.v23.enums.types.campaign_status import CampaignStatusEnum

from google_ads.services.assets.asset_group_asset_service import AssetGroupAssetService
from google_ads.services.assets.asset_group_service import AssetGroupService
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


class PMaxValidationError(Exception):
    """Raised when the input bundle doesn't meet Google's PMax minimums.

    The orchestrator catches this and returns a structured error so the
    wizard / chat agent can highlight the specific fields to fix.
    """

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


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


class PMaxOrchestrator:
    """The recipe. Holds references to each primitive service so it can
    sequence them and roll back on failure."""

    def __init__(self) -> None:
        self._budget = BudgetService()
        self._campaign = CampaignService()
        self._asset = AssetService()
        self._asset_group = AssetGroupService()
        self._asset_group_asset = AssetGroupAssetService()

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

        created_budget_rn: Optional[str] = None
        created_campaign_rn: Optional[str] = None
        warnings: List[str] = []

        try:
            # ── Step 1 — Budget ───────────────────────────────────────
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
            biz_resp = await self._asset.create_text_asset(
                ctx=ctx, customer_id=customer_id, text=bundle["business_name"],
            )
            asset_ids["business_name"] = [_extract_resource_name(biz_resp)]

            # ── Step 3c — Image assets ────────────────────────────────
            # Bundle can pass image bytes / urls / existing asset ids. For
            # V1 we accept existing asset resource names (created via
            # /api/assets/upload). Uploading fresh bytes here would
            # require base64 plumbing — out of scope for this orchestrator;
            # the wizard uploads first, then passes asset resource_names.
            for field in ("logos",):
                rns = list(bundle.get(field) or [])
                asset_ids[field] = rns
            mi = bundle.get("marketing_images") or {}
            for kind in IMAGE_FIELD_TYPES:
                if kind == "logos":
                    continue
                asset_ids[kind] = list(mi.get(kind) or [])

            # ── Step 3d — YouTube video assets ────────────────────────
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

            # ── Step 4 — Asset group ──────────────────────────────────
            await ctx.log(level="info", message=f"[PMax] Creating asset group...")
            ag_resp = await self._asset_group.create_asset_group(
                ctx=ctx,
                customer_id=customer_id,
                campaign_id=campaign_id,
                name=f"{bundle['name']} — Asset Group 1",
                final_urls=bundle["final_urls"],
                final_mobile_urls=bundle.get("final_mobile_urls"),
                status=AssetGroupStatusEnum.AssetGroupStatus.PAUSED,
            )
            ag_rn = _extract_resource_name(ag_resp)
            asset_group_id = _id_from_resource_name(ag_rn)

            # ── Step 5 — Link each asset to the asset group ───────────
            await ctx.log(level="info", message=f"[PMax] Linking {sum(len(v) for v in asset_ids.values())} assets to the group...")

            async def _link(asset_rn: str, field_type) -> None:
                aid = _id_from_resource_name(asset_rn)
                try:
                    await self._asset_group_asset.create_asset_group_asset(
                        ctx=ctx,
                        customer_id=customer_id,
                        asset_group_id=asset_group_id,
                        asset_id=aid,
                        field_type=field_type,
                    )
                except Exception as e:
                    # Linking failures shouldn't kill the whole flow if
                    # the campaign is otherwise valid — log and continue.
                    warnings.append(f"link asset {aid} as {field_type.name} failed: {e}")

            for field, rule in TEXT_RULES.items():
                for rn in asset_ids[field]:
                    await _link(rn, rule["field_type"])

            # business name uses its own field type
            for rn in asset_ids["business_name"]:
                await _link(rn, AssetFieldTypeEnum.AssetFieldType.BUSINESS_NAME)

            for field, ft in IMAGE_FIELD_TYPES.items():
                for rn in asset_ids[field]:
                    await _link(rn, ft)

            for rn in asset_ids["videos"]:
                await _link(rn, AssetFieldTypeEnum.AssetFieldType.YOUTUBE_VIDEO)

            await ctx.log(
                level="info",
                message=f"[PMax] OK — campaign_id={campaign_id} asset_group_id={asset_group_id}",
            )

            # ── Step 6 — Bring our own DB in agreement with reality ──
            # Without this the sidebar would show stale data for up to
            # 5 minutes (V11 staleness threshold), and the agent would
            # have no memory folder for the new campaign.
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

        except Exception as e:
            await ctx.log(level="error", message=f"[PMax] failure: {e}; rolling back...")
            await self._rollback(
                ctx=ctx,
                customer_id=customer_id,
                campaign_rn=created_campaign_rn,
                budget_rn=created_budget_rn,
            )
            raise

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
    ) -> None:
        """Best-effort removal of the campaign we just created when
        something downstream failed.

        Assets created along the way are intentionally left behind —
        they're reusable from the account library and don't spend money.
        Budgets with no campaign attached also don't spend; we don't
        currently expose a remove-budget operation in this codebase
        (BudgetService.update_campaign_budget has no status param), so
        an orphan budget will appear in the account's budget list until
        manually cleaned up. Worst case is a cosmetic entry, not a cost
        leak — campaigns are what actually charge money, and those we
        do remove.
        """
        if campaign_rn:
            try:
                cid = _id_from_resource_name(campaign_rn)
                await self._campaign.update_campaign(
                    ctx=ctx,
                    customer_id=customer_id,
                    campaign_id=cid,
                    status=CampaignStatusEnum.CampaignStatus.REMOVED,
                )
                await ctx.log(level="info", message=f"[PMax rollback] removed campaign {cid}")
            except Exception as e:
                await ctx.log(level="warning", message=f"[PMax rollback] could not remove campaign: {e}")
        if budget_rn:
            bid = _id_from_resource_name(budget_rn)
            await ctx.log(
                level="warning",
                message=(
                    f"[PMax rollback] orphan budget {bid} left in account "
                    f"(no remove-budget tool wired). Safe to ignore — it won't spend."
                ),
            )


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
            logos: ≥1 asset resource_name for a logo image (upload first via /api/assets/upload).
            landscape_images: ≥1 asset resource_name, 1.91:1 marketing image.
            square_images: ≥1 asset resource_name, 1:1 marketing image.
            video_youtube_ids: ≥1 YouTube video ID (the campaign needs at least one video for PMax).
            portrait_images: Optional list of 4:5 portrait marketing images.
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
