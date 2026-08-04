"""Unit tests for the Responsive Display (RDA) orchestrator — NO live Google calls.

The P5 Display consumer (story 19.2). Covers the pieces that matter for a
money-safe RDA create:

  * campaign shape — DISPLAY channel, PAUSED, EU-political=3, MaximizeConversions,
    Display-only network settings
  * ad group — DISPLAY_STANDARD
  * image slot → ResponsiveDisplayAdInfo field mapping, INCLUDING the 4:1
    LANDSCAPE_LOGO field (`logo_images`) absent everywhere else in the repo, each
    slot cropped to its OWN aspect (landscape 1.91:1, square 1:1, logo 1:1,
    landscape_logo 4:1)
  * the SINGULAR long_headline (exactly one)
  * text char-limit + count validation from the registry (headlines ≤30, long
    ≤90, descriptions ≤90, business_name ≤25) + the exactly-1 long-headline HARD
    rejection + the required-slot rules
  * pre-flight rejection of an off-aspect pre-uploaded Google image asset
  * rollback on a partial failure (campaign + budget removed)
  * registry + harness wiring (tool registered under the exact name, present in
    the execution catalog, and a fail-closed dry-run harness entry exists)

Every service/SDK client the orchestrator touches is stubbed; nothing hits the
network. Consumes ``creative_images`` UNCHANGED (FR6.2).

Run:  cd backend && .venv/bin/python -m unittest tests.test_rda_orchestrator -v
"""

from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from PIL import Image

from google.ads.googleads.v23.services.types.ad_group_ad_service import (
    MutateAdGroupAdResult,
    MutateAdGroupAdsResponse,
)
from google.ads.googleads.v23.services.types.ad_group_service import (
    MutateAdGroupResult,
    MutateAdGroupsResponse,
)
from google.ads.googleads.v23.services.types.campaign_service import (
    MutateCampaignResult,
    MutateCampaignsResponse,
)

from app.services import creative_specs
from google_ads.services.campaign import rda_orchestrator as rda
from google_ads.services.campaign.rda_orchestrator import (
    ApiCtx,
    RdaOrchestrator,
    RdaStepError,
    RdaValidationError,
    create_rda_orchestrator_tools,
)


def _validate_bundle(bundle):
    """Adapter: the real `_validate_bundle` takes a spec and RETURNS a
    ValidationReport; raise on errors to keep a simple assert contract."""
    report = rda._validate_bundle(bundle, creative_specs.get("rda"))
    if report.errors:
        raise RdaValidationError(report.errors)
    return report


CUSTOMER = "1234567890"


def _valid_bundle(**overrides: Any) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {
        "name": "RDA Test",
        "budget_micros": 10_000_000,
        "final_urls": ["https://example.com"],
        "business_name": "Example",
        "headlines": ["Headline one", "Headline two"],
        "long_headlines": ["A single long headline for the value proposition"],
        "descriptions": ["Description one goes here", "Description two goes here"],
        "logos": ["logo-uuid"],
        "landscape_logos": ["landlogo-uuid"],
        "marketing_images": {
            "landscape": ["land-uuid"],
            "square": ["sq-uuid"],
        },
        "location_ids": ["21132"],
        "language_ids": ["1000"],
    }
    bundle.update(overrides)
    return bundle


# ── fake SDK clients ─────────────────────────────────────────────────────
class _FakeMutateClient:
    """Captures each request; returns a fixed real proto response."""

    def __init__(self, method_name: str, resp: Any) -> None:
        self.requests: List[Any] = []
        self._resp = resp
        setattr(self, method_name, self._mutate)

    def _mutate(self, request: Any) -> Any:
        self.requests.append(request)
        return self._resp


class _RaisingClient:
    def __init__(self, method_name: str) -> None:
        setattr(self, method_name, self._boom)

    def _boom(self, request: Any) -> Any:
        raise RuntimeError("simulated Google API failure")


class _FakeAssetService:
    """Records every image upload; returns unique resource names."""

    def __init__(self) -> None:
        self.image_uploads: List[Dict[str, Any]] = []
        self._n = 0

    async def create_image_asset(self, ctx, customer_id, image_data, name, mime_type):
        self._n += 1
        rn = f"customers/{CUSTOMER}/assets/{1000 + self._n}"
        self.image_uploads.append({"name": name, "data": image_data, "rn": rn})
        return {"results": [{"resource_name": rn}]}


def _orchestrator():
    orch = RdaOrchestrator()
    calls = {"budget": 0, "remove_campaign": 0, "remove_budget": 0,
             "loc": 0, "lang": 0, "loc_kwargs": []}
    fake_assets = _FakeAssetService()

    async def create_budget(ctx, customer_id, name, amount_micros):
        calls["budget"] += 1
        return {"results": [{"resource_name": f"customers/{CUSTOMER}/campaignBudgets/1"}]}

    async def remove_budget(ctx, customer_id, budget_id):
        calls["remove_budget"] += 1
        return {}

    async def remove_campaign(ctx, customer_id, campaign_id):
        calls["remove_campaign"] += 1
        return {}

    async def add_loc(**kw):
        calls["loc"] += 1
        calls["loc_kwargs"].append(kw)
        return {}

    async def add_lang(**kw):
        calls["lang"] += 1
        return {}

    orch._budget = SimpleNamespace(  # type: ignore[assignment]
        create_campaign_budget=create_budget, remove_campaign_budget=remove_budget)
    orch._campaign = SimpleNamespace(remove_campaign=remove_campaign)  # type: ignore[assignment]
    orch._campaign_criterion = SimpleNamespace(  # type: ignore[assignment]
        add_location_criteria=add_loc, add_language_criteria=add_lang)
    orch._asset = fake_assets  # type: ignore[assignment]
    orch._campaign_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_campaigns",
        MutateCampaignsResponse(
            results=[MutateCampaignResult(resource_name=f"customers/{CUSTOMER}/campaigns/2")]))
    orch._ad_group_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_ad_groups",
        MutateAdGroupsResponse(
            results=[MutateAdGroupResult(resource_name=f"customers/{CUSTOMER}/adGroups/3")]))
    orch._ad_group_ad_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_ad_group_ads",
        MutateAdGroupAdsResponse(
            results=[MutateAdGroupAdResult(resource_name=f"customers/{CUSTOMER}/adGroupAds/3~4")]))
    return orch, fake_assets, calls


def _aspect(data: bytes) -> float:
    with Image.open(BytesIO(data)) as img:
        w, h = img.size
    return w / h


# ── validation ───────────────────────────────────────────────────────────
class ValidationTests(unittest.TestCase):
    def test_valid_bundle_passes(self):
        report = _validate_bundle(_valid_bundle())
        self.assertTrue(report.ok)

    def test_headline_30_passes_31_fails(self):
        _validate_bundle(_valid_bundle(headlines=["x" * 30]))
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(headlines=["x" * 31]))

    def test_long_headline_90_passes_91_fails(self):
        _validate_bundle(_valid_bundle(long_headlines=["x" * 90]))
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(long_headlines=["x" * 91]))

    def test_two_long_headlines_rejected_hard(self):
        # Exactly-1 is enforceable STRUCTURE (a singular proto field), so 2 is a
        # hard error even though every RDA field carries verified=True (FR6.1).
        with self.assertRaises(RdaValidationError) as cm:
            _validate_bundle(_valid_bundle(long_headlines=["one", "two"]))
        self.assertIn("too many long_headlines", "; ".join(cm.exception.errors))

    def test_description_too_long(self):
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(descriptions=["x" * 91]))

    def test_business_name_too_long(self):
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(business_name="x" * 26))

    def test_too_many_headlines(self):
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(headlines=[f"h{i}" for i in range(6)]))

    def test_missing_landscape_marketing_image(self):
        with self.assertRaises(RdaValidationError) as cm:
            _validate_bundle(_valid_bundle(
                marketing_images={"landscape": [], "square": ["sq-uuid"]}))
        self.assertIn("landscape", "; ".join(cm.exception.errors))

    def test_missing_square_marketing_image(self):
        with self.assertRaises(RdaValidationError) as cm:
            _validate_bundle(_valid_bundle(
                marketing_images={"landscape": ["land-uuid"], "square": []}))
        self.assertIn("square", "; ".join(cm.exception.errors))

    def test_missing_logo(self):
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(logos=[]))

    def test_missing_final_url(self):
        with self.assertRaises(RdaValidationError):
            _validate_bundle(_valid_bundle(final_urls=[]))

    def test_landscape_logo_is_optional(self):
        # The 4:1 LANDSCAPE_LOGO is optional — a bundle without it validates.
        report = _validate_bundle(_valid_bundle(landscape_logos=[]))
        self.assertTrue(report.ok)


# ── flow ─────────────────────────────────────────────────────────────────
class FlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # One 16:9 source large enough that a crop to EVERY slot aspect clears
        # its min dims (incl. 4:1 landscape_logo → 1600×400 ≥ 512×128).
        self.img_path = Path(self._tmp.name) / "src.png"
        Image.new("RGB", (1600, 900), (30, 120, 200)).save(self.img_path, "PNG")

        async def locate(ref):
            if ref in ("logo-uuid", "landlogo-uuid", "land-uuid", "sq-uuid"):
                return self.img_path, "image/png"
            raise LookupError("unknown local ref")

        self._orig_locate = rda._locate_local_image
        rda._locate_local_image = locate  # type: ignore[assignment]

    def tearDown(self) -> None:
        rda._locate_local_image = self._orig_locate  # type: ignore[assignment]
        self._tmp.cleanup()

    async def test_happy_path_campaign_adgroup_and_rda_fields(self):
        orch, fake_assets, calls = _orchestrator()
        result = await orch.create_responsive_display_campaign(
            ApiCtx(), CUSTOMER, _valid_bundle())

        # DG-shape response: campaign/budget/ad_group/ad ids + per-slot asset ids.
        self.assertEqual(result["campaign_id"], "2")
        self.assertEqual(result["ad_group_id"], "3")
        self.assertEqual(result["ad_id"], "3~4")
        self.assertIn("landscape", result["asset_ids"])
        self.assertIn("landscape_logo", result["asset_ids"])
        self.assertEqual(calls["loc"], 1)
        self.assertEqual(calls["lang"], 1)

        # Campaign: DISPLAY + PAUSED + EU-political=3 + MaxConv + Display-only net.
        camp = orch._campaign_client.requests[-1].operations[0].create
        self.assertEqual(camp.advertising_channel_type.name, "DISPLAY")
        self.assertEqual(camp.status.name, "PAUSED")
        self.assertEqual(int(camp.contains_eu_political_advertising), 3)
        self.assertTrue(camp._pb.HasField("maximize_conversions"))
        self.assertTrue(camp.network_settings.target_content_network)
        self.assertFalse(camp.network_settings.target_google_search)

        # Ad group: DISPLAY_STANDARD.
        ag = orch._ad_group_client.requests[-1].operations[0].create
        self.assertEqual(ag.type_.name, "DISPLAY_STANDARD")

        # RDA field mapping — including the 4:1 LANDSCAPE_LOGO (logo_images) and
        # the SINGULAR long_headline.
        info = orch._ad_group_ad_client.requests[-1].operations[0].create \
            .ad.responsive_display_ad
        self.assertEqual(len(info.marketing_images), 1)         # landscape 1.91:1
        self.assertEqual(len(info.square_marketing_images), 1)  # square 1:1
        self.assertEqual(len(info.square_logo_images), 1)       # logo 1:1
        self.assertEqual(len(info.logo_images), 1)              # LANDSCAPE_LOGO 4:1
        self.assertEqual(info.long_headline.text,
                         "A single long headline for the value proposition")
        self.assertEqual(info.business_name, "Example")
        self.assertEqual([h.text for h in info.headlines],
                         ["Headline one", "Headline two"])

        # Each slot cropped to ITS OWN aspect.
        by_rn = {u["rn"]: u for u in fake_assets.image_uploads}
        self.assertAlmostEqual(
            _aspect(by_rn[info.marketing_images[0].asset]["data"]), 1.91,
            delta=1.91 * 0.011)
        self.assertAlmostEqual(
            _aspect(by_rn[info.square_marketing_images[0].asset]["data"]), 1.0,
            delta=0.011)
        self.assertAlmostEqual(
            _aspect(by_rn[info.square_logo_images[0].asset]["data"]), 1.0,
            delta=0.011)
        self.assertAlmostEqual(
            _aspect(by_rn[info.logo_images[0].asset]["data"]), 4.0,
            delta=4.0 * 0.011)

    async def test_target_cpa_applied(self):
        orch, _, _ = _orchestrator()
        await orch.create_responsive_display_campaign(
            ApiCtx(), CUSTOMER, _valid_bundle(target_cpa_micros=7_500_000))
        camp = orch._campaign_client.requests[-1].operations[0].create
        self.assertEqual(int(camp.maximize_conversions.target_cpa_micros), 7_500_000)

    async def test_excluded_location_ids_add_negative_geo_criterion(self):
        orch, _, calls = _orchestrator()
        await orch.create_responsive_display_campaign(
            ApiCtx(), CUSTOMER,
            _valid_bundle(location_ids=["2784"],
                          excluded_location_ids=["9041083"]))
        self.assertEqual(calls["loc"], 2)
        negative = [k for k in calls["loc_kwargs"] if k.get("negative")]
        self.assertEqual(len(negative), 1)
        self.assertEqual(negative[0]["location_ids"], ["9041083"])

    async def test_rollback_on_ad_failure(self):
        orch, _, calls = _orchestrator()
        orch._ad_group_ad_client = _RaisingClient("mutate_ad_group_ads")  # type: ignore[assignment]
        with self.assertRaises(RdaStepError) as cm:
            await orch.create_responsive_display_campaign(
                ApiCtx(), CUSTOMER, _valid_bundle())
        self.assertEqual(cm.exception.step, "ad creation")
        self.assertEqual(calls["remove_campaign"], 1)
        self.assertEqual(calls["remove_budget"], 1)

    async def test_off_aspect_preuploaded_asset_rejected_preflight(self):
        orch, _, calls = _orchestrator()
        rn = f"customers/{CUSTOMER}/assets/555"
        orch._fetch_image_asset_dims = lambda cid, rns: {rn: (1000, 1000)}  # type: ignore[method-assign]
        bundle = _valid_bundle(marketing_images={"landscape": [rn], "square": ["sq-uuid"]})
        with self.assertRaises(RdaValidationError) as cm:
            await orch.create_responsive_display_campaign(ApiCtx(), CUSTOMER, bundle)
        msg = "; ".join(cm.exception.errors)
        self.assertIn("landscape[0]", msg)
        self.assertIn("1000x1000", msg)
        self.assertEqual(calls["budget"], 0, "nothing may be created pre-flight")


# ── MCP tool wrapper ─────────────────────────────────────────────────────
class ToolWrapperTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_error_returned_structured(self):
        svc = RdaOrchestrator()
        (tool,) = create_rda_orchestrator_tools(svc)
        out = await tool(
            ctx=ApiCtx(), customer_id=CUSTOMER, name="", budget_micros=0,
            final_urls=[], business_name="", headlines=[], long_headlines=[],
            descriptions=[], logos=[],
        )
        self.assertEqual(out["error"], "VALIDATION_FAILED")
        self.assertTrue(out["errors"])


# ── registry + harness wiring ─────────────────────────────────────────────
class WiringTests(unittest.TestCase):
    TOOL = "rda_create_responsive_display_campaign"

    def test_registered_under_exact_name(self):
        from google_ads.tool_registry import registered_tool_names
        self.assertIn(self.TOOL, registered_tool_names())

    def test_in_execution_catalog_write(self):
        from google_ads.tool_registry import execution_catalog
        self.assertIn(self.TOOL, execution_catalog()["write"])

    def test_harness_entry_present_and_fail_closed(self):
        import validate_all_tools as vat
        self.assertIn(self.TOOL, vat.HARVEST_TOOL_ARGS)
        # Classified as a WRITE so the harness forces validate_only on it.
        self.assertTrue(vat.is_mutate_tool("create_responsive_display_campaign"))
        # Fail-closed: with no harvested image asset id, building args SKIPs.
        ids = {"image_asset_id": None, "geo_target_id": "21132", "language_id": "1000"}
        with self.assertRaises(vat.SkipTool):
            vat.HARVEST_TOOL_ARGS[self.TOOL](ids)


if __name__ == "__main__":
    unittest.main()
