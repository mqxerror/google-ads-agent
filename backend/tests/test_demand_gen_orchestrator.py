"""Unit tests for the Demand Gen orchestrator — NO live Google calls.

Covers the pieces that matter for a money-safe Demand Gen create:

  * channel-control mapping — especially Gmail OFF + Display ON, the whole
    point of the surface — lands on the ad group's
    demand_gen_ad_group_settings.channel_controls.selected_channels
  * image slot → DemandGenMultiAssetAdInfo field mask, with each slot's
    image cropped to its OWN aspect (logo 1:1, marketing 1.91:1, square 1:1)
  * text char-limit + count validation (headlines ≤30, descriptions ≤90,
    business_name ≤25) and the all-channels-off rejection
  * pre-flight rejection of an off-aspect pre-uploaded Google image asset
  * rollback on a partial failure (campaign + budget removed)
  * audience customer-match EXCLUSION → negative ad-group criterion
  * registry + harness wiring (tool registered under the exact name, present
    in the execution catalog, and a fail-closed dry-run harness entry exists)

Every service/SDK client the orchestrator touches is stubbed; nothing hits
the network.

Run:  cd backend && .venv/bin/python -m unittest tests.test_demand_gen_orchestrator -v
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
from google.ads.googleads.v23.services.types.ad_group_criterion_service import (
    MutateAdGroupCriteriaResponse,
    MutateAdGroupCriterionResult,
)
from google.ads.googleads.v23.services.types.ad_group_service import (
    MutateAdGroupResult,
    MutateAdGroupsResponse,
)
from google.ads.googleads.v23.services.types.campaign_service import (
    MutateCampaignResult,
    MutateCampaignsResponse,
)

from google_ads.services.campaign import demand_gen_orchestrator as dg
from google_ads.services.campaign.demand_gen_orchestrator import (
    ApiCtx,
    DemandGenOrchestrator,
    DemandGenStepError,
    DemandGenValidationError,
    _validate_bundle,
    create_demand_gen_orchestrator_tools,
)

CUSTOMER = "1234567890"


def _valid_bundle(**overrides: Any) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {
        "name": "DG Test",
        "budget_micros": 10_000_000,
        "final_urls": ["https://example.com"],
        "business_name": "Example",
        "headlines": ["Headline one", "Headline two"],
        "descriptions": ["Description one goes here", "Description two goes here"],
        "logos": ["logo-uuid"],
        "marketing_images": {
            "landscape": ["land-uuid"],
            "square": ["sq-uuid"],
            "portrait": [],
            "tall_portrait": [],
        },
        "location_ids": ["21132"],
        "language_ids": ["1000"],
        "channels": dict(dg.DEFAULT_CHANNELS),
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
    orch = DemandGenOrchestrator()
    calls = {
        "budget": 0, "remove_campaign": 0, "remove_budget": 0,
        "loc": 0, "lang": 0, "loc_kwargs": [],
    }
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

    async def post_create_sync(**kw):
        return None

    orch._budget = SimpleNamespace(  # type: ignore[assignment]
        create_campaign_budget=create_budget, remove_campaign_budget=remove_budget
    )
    orch._campaign = SimpleNamespace(remove_campaign=remove_campaign)  # type: ignore[assignment]
    orch._campaign_criterion = SimpleNamespace(  # type: ignore[assignment]
        add_location_criteria=add_loc, add_language_criteria=add_lang
    )
    orch._asset = fake_assets  # type: ignore[assignment]
    orch._campaign_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_campaigns",
        MutateCampaignsResponse(
            results=[MutateCampaignResult(resource_name=f"customers/{CUSTOMER}/campaigns/2")]
        ),
    )
    orch._ad_group_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_ad_groups",
        MutateAdGroupsResponse(
            results=[MutateAdGroupResult(resource_name=f"customers/{CUSTOMER}/adGroups/3")]
        ),
    )
    orch._ad_group_ad_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_ad_group_ads",
        MutateAdGroupAdsResponse(
            results=[MutateAdGroupAdResult(resource_name=f"customers/{CUSTOMER}/adGroupAds/3~4")]
        ),
    )
    orch._ad_group_criterion_client = _FakeMutateClient(  # type: ignore[assignment]
        "mutate_ad_group_criteria",
        MutateAdGroupCriteriaResponse(
            results=[MutateAdGroupCriterionResult(
                resource_name=f"customers/{CUSTOMER}/adGroupCriteria/3~5")]
        ),
    )
    orch._post_create_sync = post_create_sync  # type: ignore[method-assign]
    return orch, fake_assets, calls


def _aspect(data: bytes) -> float:
    with Image.open(BytesIO(data)) as img:
        w, h = img.size
    return w / h


# ── validation (no orchestrator needed) ──────────────────────────────────
class ValidationTests(unittest.TestCase):
    def test_valid_bundle_passes(self):
        _validate_bundle(_valid_bundle())  # no raise

    def test_headline_too_long(self):
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(headlines=["x" * 31, "ok"]))
        self.assertIn("headlines[0]", "; ".join(cm.exception.errors))
        self.assertIn("max 30", "; ".join(cm.exception.errors))

    def test_description_too_long(self):
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(descriptions=["y" * 91, "ok two"]))
        self.assertIn("descriptions[0]", "; ".join(cm.exception.errors))
        self.assertIn("max 90", "; ".join(cm.exception.errors))

    def test_business_name_too_long(self):
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(business_name="z" * 26))
        self.assertIn("business_name", "; ".join(cm.exception.errors))
        self.assertIn("max 25", "; ".join(cm.exception.errors))

    def test_too_many_headlines(self):
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(headlines=[f"H{i}" for i in range(6)]))
        self.assertIn("too many headlines", "; ".join(cm.exception.errors))

    def test_missing_marketing_image(self):
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(
                marketing_images={"landscape": [], "square": [],
                                  "portrait": [], "tall_portrait": []}))
        self.assertIn("marketing image", "; ".join(cm.exception.errors))

    def test_missing_logo(self):
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(logos=[]))
        self.assertIn("logo", "; ".join(cm.exception.errors))

    def test_all_channels_off_rejected(self):
        off = {k: False for k in dg.CHANNEL_FIELDS}
        with self.assertRaises(DemandGenValidationError) as cm:
            _validate_bundle(_valid_bundle(channels=off))
        self.assertIn("at least one channel", "; ".join(cm.exception.errors))


# ── flow tests (stubbed clients) ─────────────────────────────────────────
class FlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # One 16:9 source image off-aspect for EVERY slot, so a crop runs per slot.
        self.img_path = Path(self._tmp.name) / "src.png"
        Image.new("RGB", (1600, 900), (30, 120, 200)).save(self.img_path, "PNG")

        async def locate(ref):
            if ref in ("logo-uuid", "land-uuid", "sq-uuid"):
                return self.img_path, "image/png"
            raise LookupError("unknown local ref")

        self._orig_locate = dg._locate_local_image
        dg._locate_local_image = locate  # type: ignore[assignment]

    def tearDown(self) -> None:
        dg._locate_local_image = self._orig_locate  # type: ignore[assignment]
        self._tmp.cleanup()

    async def test_happy_path_channel_controls_and_mask(self):
        orch, fake_assets, calls = _orchestrator()
        result = await orch.create_demand_gen_campaign(ApiCtx(), CUSTOMER, _valid_bundle())

        self.assertEqual(result["campaign_id"], "2")
        self.assertEqual(result["ad_group_id"], "3")
        # ad_group_ad resource names are the composite adGroupId~adId.
        self.assertEqual(result["ad_group_ad_id"], "3~4")
        self.assertEqual(calls["loc"], 1)
        self.assertEqual(calls["lang"], 1)

        # Campaign built as DEMAND_GEN + PAUSED + EU-political=3 + MaxConv.
        camp = orch._campaign_client.requests[-1].operations[0].create
        self.assertEqual(camp.advertising_channel_type.name, "DEMAND_GEN")
        self.assertEqual(camp.status.name, "PAUSED")
        self.assertEqual(int(camp.contains_eu_political_advertising), 3)
        self.assertTrue(camp._pb.HasField("maximize_conversions"))

        # Channel controls: Gmail OFF, Display ON (the whole point), the rest ON.
        sc = orch._ad_group_client.requests[-1].operations[0].create \
            .demand_gen_ad_group_settings.channel_controls.selected_channels
        self.assertFalse(sc.gmail)
        self.assertTrue(sc.display)
        self.assertTrue(sc.discover)
        self.assertTrue(sc.youtube_in_stream)
        self.assertEqual(result["channels"]["gmail"], False)
        # Ad group `type` is left unset (no DEMAND_GEN AdGroupType in v23).
        ag = orch._ad_group_client.requests[-1].operations[0].create
        self.assertEqual(ag.type_.name, "UNSPECIFIED")

        # Image slot → ad-field mask, each cropped to ITS OWN aspect.
        info = orch._ad_group_ad_client.requests[-1].operations[0].create \
            .ad.demand_gen_multi_asset_ad
        self.assertEqual(len(info.marketing_images), 1)
        self.assertEqual(len(info.square_marketing_images), 1)
        self.assertEqual(len(info.logo_images), 1)
        self.assertEqual(info.business_name, "Example")
        self.assertEqual([h.text for h in info.headlines], ["Headline one", "Headline two"])

        by_rn = {u["rn"]: u for u in fake_assets.image_uploads}
        self.assertAlmostEqual(
            _aspect(by_rn[info.marketing_images[0].asset]["data"]), 1.91,
            delta=1.91 * 0.011)
        self.assertAlmostEqual(
            _aspect(by_rn[info.logo_images[0].asset]["data"]), 1.0, delta=0.011)
        self.assertAlmostEqual(
            _aspect(by_rn[info.square_marketing_images[0].asset]["data"]), 1.0,
            delta=0.011)

    async def test_gmail_can_be_turned_on_and_display_off(self):
        orch, _, _ = _orchestrator()
        channels = dict(dg.DEFAULT_CHANNELS)
        channels["gmail"] = True
        channels["display"] = False
        await orch.create_demand_gen_campaign(
            ApiCtx(), CUSTOMER, _valid_bundle(channels=channels))
        sc = orch._ad_group_client.requests[-1].operations[0].create \
            .demand_gen_ad_group_settings.channel_controls.selected_channels
        self.assertTrue(sc.gmail)
        self.assertFalse(sc.display)

    async def test_target_cpa_applied(self):
        orch, _, _ = _orchestrator()
        await orch.create_demand_gen_campaign(
            ApiCtx(), CUSTOMER, _valid_bundle(target_cpa_micros=7_500_000))
        camp = orch._campaign_client.requests[-1].operations[0].create
        self.assertEqual(int(camp.maximize_conversions.target_cpa_micros), 7_500_000)

    async def test_audience_exclusion_is_negative_criterion(self):
        orch, _, _ = _orchestrator()
        await orch.create_demand_gen_campaign(
            ApiCtx(), CUSTOMER,
            _valid_bundle(audience_user_list_ids=["111"],
                          excluded_user_list_ids=["222"]))
        ops = orch._ad_group_criterion_client.requests[-1].operations
        self.assertEqual(len(ops), 2)
        included = [o.create for o in ops if not o.create.negative]
        excluded = [o.create for o in ops if o.create.negative]
        self.assertEqual(len(included), 1)
        self.assertEqual(len(excluded), 1)
        self.assertIn("userLists/111", included[0].user_list.user_list)
        self.assertIn("userLists/222", excluded[0].user_list.user_list)

    async def test_excluded_location_ids_add_negative_geo_criterion(self):
        orch, _, calls = _orchestrator()
        await orch.create_demand_gen_campaign(
            ApiCtx(), CUSTOMER,
            _valid_bundle(location_ids=["2784"],
                          excluded_location_ids=["9041083", "1000013"]))
        # Two add_location_criteria calls: one positive (target UAE), one
        # negative (exclude the Dubai emirate + city).
        self.assertEqual(calls["loc"], 2)
        positive = [k for k in calls["loc_kwargs"] if not k.get("negative")]
        negative = [k for k in calls["loc_kwargs"] if k.get("negative")]
        self.assertEqual(len(positive), 1)
        self.assertEqual(len(negative), 1)
        self.assertEqual(positive[0]["location_ids"], ["2784"])
        self.assertEqual(negative[0]["location_ids"], ["9041083", "1000013"])

    async def test_no_excluded_locations_means_no_negative_geo_call(self):
        orch, _, calls = _orchestrator()
        await orch.create_demand_gen_campaign(ApiCtx(), CUSTOMER, _valid_bundle())
        # Default bundle has location_ids but no exclusions → exactly one call.
        self.assertEqual(calls["loc"], 1)
        self.assertFalse(any(k.get("negative") for k in calls["loc_kwargs"]))

    async def test_rollback_on_ad_failure(self):
        orch, _, calls = _orchestrator()
        orch._ad_group_ad_client = _RaisingClient("mutate_ad_group_ads")  # type: ignore[assignment]
        with self.assertRaises(DemandGenStepError) as cm:
            await orch.create_demand_gen_campaign(ApiCtx(), CUSTOMER, _valid_bundle())
        self.assertEqual(cm.exception.step, "ad creation")
        # Campaign + budget were created, so both must be rolled back.
        self.assertEqual(calls["remove_campaign"], 1)
        self.assertEqual(calls["remove_budget"], 1)

    async def test_off_aspect_preuploaded_asset_rejected_preflight(self):
        orch, _, calls = _orchestrator()
        rn = f"customers/{CUSTOMER}/assets/555"
        orch._fetch_image_asset_dims = lambda cid, rns: {rn: (1000, 1000)}  # type: ignore[method-assign]
        bundle = _valid_bundle(marketing_images={
            "landscape": [rn], "square": ["sq-uuid"],
            "portrait": [], "tall_portrait": []})
        with self.assertRaises(DemandGenValidationError) as cm:
            await orch.create_demand_gen_campaign(ApiCtx(), CUSTOMER, bundle)
        msg = "; ".join(cm.exception.errors)
        self.assertIn("landscape[0]", msg)
        self.assertIn("1000x1000", msg)
        self.assertEqual(calls["budget"], 0, "nothing may be created pre-flight")


# ── MCP tool wrapper ─────────────────────────────────────────────────────
class ToolWrapperTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_error_returned_structured(self):
        svc = DemandGenOrchestrator()
        (tool,) = create_demand_gen_orchestrator_tools(svc)
        out = await tool(
            ctx=ApiCtx(), customer_id=CUSTOMER, name="", budget_micros=0,
            final_urls=[], business_name="", headlines=[], descriptions=[],
            logos=[],
        )
        self.assertEqual(out["error"], "VALIDATION_FAILED")
        self.assertTrue(out["errors"])


# ── registry + harness wiring ────────────────────────────────────────────
class WiringTests(unittest.TestCase):
    TOOL = "demand_gen_create_demand_gen_campaign"

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
        self.assertTrue(vat.is_mutate_tool("create_demand_gen_campaign"))
        # Fail-closed: with no harvested image asset id, building args SKIPs.
        ids = {"image_asset_id": None, "geo_target_id": "21132", "language_id": "1000"}
        with self.assertRaises(vat.SkipTool):
            vat.HARVEST_TOOL_ARGS[self.TOOL](ids)


if __name__ == "__main__":
    unittest.main()
