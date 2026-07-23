"""Unit tests — asset CRUD completion (update-in-place + detach/remove).

Covers the asset-CRUD-completion plan (research/asset-crud-completion-plan.md):

- AssetService.update_asset — per-type field-mask correctness (SITELINK /
  CALLOUT / STRUCTURED_SNIPPET / CALL / name), image-immutability rejection,
  char-limit + banned-symbol validation, cross-type mixing rejection, and the
  "no fields" guard. Mirrors the WS1 field-mask idiom (update_ad_final_urls) and
  primary_for_goal optional-masking: only provided fields enter the mask.
- AssetService.remove_asset — Google Ads assets can't be hard-deleted, so this
  DETACHES the asset across campaign/ad_group/customer links. The force guard:
  live linkages block removal unless force=True (blast-radius surfaced).
- CampaignAssetService.update_campaign_asset_status — the campaign-level status
  gap that ad_group/customer already had.
- Registry + catalog + harness discovery for all three new write tools.

No live Google mutation happens — SDK clients are stubbed; captured requests are
the validate_only smoke check.

Run:  cd backend && .venv/bin/python -m unittest tests.test_asset_crud_completion -v
"""

from __future__ import annotations

import types
import unittest
from typing import Any, List
from unittest import mock

from google.ads.googleads.v23.services.types.asset_service import (
    MutateAssetResult,
    MutateAssetsResponse,
)

from google_ads.services.assets import asset_service as asset_module
from google_ads.services.assets.asset_service import AssetService
from google_ads.services.campaign.campaign_asset_service import CampaignAssetService

CUSTOMER = "1234567890"
ASSET_ID = "424242"
ASSET_RN = f"customers/{CUSTOMER}/assets/{ASSET_ID}"


class _ApiCtx:
    """Minimal FastMCP-Context stand-in — only ctx.log is exercised."""

    async def log(self, level: str, message: str) -> None:  # pragma: no cover
        return None


class _FakeAssetClient:
    """Captures every mutate_assets request; returns a minimal real response."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_assets(self, request):
        self.requests.append(request)
        return MutateAssetsResponse(
            results=[MutateAssetResult(resource_name=ASSET_RN)]
        )


def _service() -> tuple[AssetService, _FakeAssetClient]:
    svc = AssetService()
    fake = _FakeAssetClient()
    svc._client = fake  # type: ignore[assignment]
    return svc, fake


# ── update_asset ──────────────────────────────────────────────────────────────
class AssetUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_sitelink_fields_and_mask(self):
        svc, fake = _service()
        result = await svc.update_asset(
            _ApiCtx(),
            CUSTOMER,
            asset_id=ASSET_ID,
            asset_type="SITELINK",
            link_text="Book a Call",
            description1="Talk to an advisor",
            description2="Free, no obligation",
            final_urls=["https://example.com/book"],
        )
        op = fake.requests[-1].operations[0]
        upd = op.update
        self.assertEqual(upd.resource_name, ASSET_RN)
        self.assertEqual(upd.sitelink_asset.link_text, "Book a Call")
        self.assertEqual(upd.sitelink_asset.description1, "Talk to an advisor")
        self.assertEqual(list(upd.final_urls), ["https://example.com/book"])
        self.assertEqual(
            list(op.update_mask.paths),
            [
                "sitelink_asset.link_text",
                "sitelink_asset.description1",
                "sitelink_asset.description2",
                "final_urls",
            ],
        )
        self.assertEqual(result["results"][0]["resource_name"], ASSET_RN)

    async def test_callout_and_snippet_and_call_masks(self):
        svc, fake = _service()
        await svc.update_asset(
            _ApiCtx(), CUSTOMER, asset_id=ASSET_ID, callout_text="Free Shipping"
        )
        op = fake.requests[-1].operations[0]
        self.assertEqual(op.update.callout_asset.callout_text, "Free Shipping")
        self.assertEqual(list(op.update_mask.paths), ["callout_asset.callout_text"])

        await svc.update_asset(
            _ApiCtx(),
            CUSTOMER,
            asset_id=ASSET_ID,
            header="Services",
            values=["Consulting", "Filing"],
        )
        op = fake.requests[-1].operations[0]
        self.assertEqual(op.update.structured_snippet_asset.header, "Services")
        self.assertEqual(
            list(op.update.structured_snippet_asset.values),
            ["Consulting", "Filing"],
        )
        self.assertEqual(
            list(op.update_mask.paths),
            ["structured_snippet_asset.header", "structured_snippet_asset.values"],
        )

        await svc.update_asset(
            _ApiCtx(),
            CUSTOMER,
            asset_id=ASSET_ID,
            phone_number="+1 800 555 0100",
            country_code="US",
        )
        op = fake.requests[-1].operations[0]
        self.assertEqual(op.update.call_asset.phone_number, "+1 800 555 0100")
        self.assertEqual(op.update.call_asset.country_code, "US")
        self.assertEqual(
            list(op.update_mask.paths),
            ["call_asset.phone_number", "call_asset.country_code"],
        )

    async def test_name_only_update(self):
        """name is editable for any type; mask carries only 'name'."""
        svc, fake = _service()
        await svc.update_asset(
            _ApiCtx(), CUSTOMER, asset_resource_name=ASSET_RN, name="Renamed Asset"
        )
        op = fake.requests[-1].operations[0]
        self.assertEqual(op.update.name, "Renamed Asset")
        self.assertEqual(list(op.update_mask.paths), ["name"])

    async def test_image_data_rejected(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(
                _ApiCtx(), CUSTOMER, asset_id=ASSET_ID, image_data=b"\x89PNG"
            )
        self.assertIn("immutable", str(cm.exception).lower())

    async def test_image_type_only_name(self):
        """asset_type=IMAGE with any typed field is rejected (name only)."""
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(
                _ApiCtx(),
                CUSTOMER,
                asset_id=ASSET_ID,
                asset_type="IMAGE",
                link_text="nope",
            )
        self.assertIn("only 'name'", str(cm.exception))
        # name-only on an IMAGE asset is fine
        svc, fake = _service()
        await svc.update_asset(
            _ApiCtx(), CUSTOMER, asset_id=ASSET_ID, asset_type="IMAGE", name="Logo"
        )
        self.assertEqual(list(fake.requests[-1].operations[0].update_mask.paths), ["name"])

    async def test_char_limit_rejected(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(
                _ApiCtx(), CUSTOMER, asset_id=ASSET_ID, link_text="X" * 26
            )
        self.assertIn("max 25", str(cm.exception))

    async def test_banned_symbol_rejected(self):
        svc, _ = _service()
        for bad in ("Buy ~now", "A | B", "Save 50%+"):
            with self.assertRaises(Exception) as cm:
                await svc.update_asset(
                    _ApiCtx(), CUSTOMER, asset_id=ASSET_ID, callout_text=bad
                )
            self.assertIn("symbol", str(cm.exception).lower())

    async def test_snippet_value_over_limit_rejected(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(
                _ApiCtx(),
                CUSTOMER,
                asset_id=ASSET_ID,
                header="Services",
                values=["ok", "Y" * 26],
            )
        self.assertIn("values[1]", str(cm.exception))

    async def test_cross_type_mixing_rejected(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(
                _ApiCtx(),
                CUSTOMER,
                asset_id=ASSET_ID,
                link_text="Home",
                callout_text="Free",
            )
        self.assertIn("mix fields", str(cm.exception).lower())

    async def test_bad_final_url_rejected(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(
                _ApiCtx(),
                CUSTOMER,
                asset_id=ASSET_ID,
                link_text="Home",
                final_urls=["example.com/no-scheme"],
            )
        self.assertIn("http", str(cm.exception).lower())

    async def test_no_fields_rejected(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(_ApiCtx(), CUSTOMER, asset_id=ASSET_ID)
        self.assertIn("no updatable fields", str(cm.exception).lower())

    async def test_requires_an_identifier(self):
        svc, _ = _service()
        with self.assertRaises(Exception) as cm:
            await svc.update_asset(_ApiCtx(), CUSTOMER, name="X")
        self.assertIn("asset_resource_name or asset_id", str(cm.exception))


# ── remove_asset (detach with force guard) ─────────────────────────────────────
def _campaign_link(rn: str, cid: str):
    return types.SimpleNamespace(
        campaign_asset=types.SimpleNamespace(
            resource_name=rn, field_type=types.SimpleNamespace(name="SITELINK")
        ),
        campaign=types.SimpleNamespace(id=cid),
    )


def _ad_group_link(rn: str, agid: str):
    return types.SimpleNamespace(
        ad_group_asset=types.SimpleNamespace(
            resource_name=rn, field_type=types.SimpleNamespace(name="SITELINK")
        ),
        ad_group=types.SimpleNamespace(id=agid),
    )


def _customer_link(rn: str):
    return types.SimpleNamespace(
        customer_asset=types.SimpleNamespace(
            resource_name=rn, field_type=types.SimpleNamespace(name="SITELINK")
        )
    )


class _FakeGAService:
    def __init__(self, rows_by_source: dict) -> None:
        self.rows_by_source = rows_by_source

    def search(self, customer_id, query):
        if "FROM campaign_asset" in query:
            return self.rows_by_source.get("campaign_asset", [])
        if "FROM ad_group_asset" in query:
            return self.rows_by_source.get("ad_group_asset", [])
        if "FROM customer_asset" in query:
            return self.rows_by_source.get("customer_asset", [])
        return []


class _FakeLinkClient:
    """One object standing in for all three link service clients."""

    def __init__(self) -> None:
        self.removed: List[str] = []

    def mutate_campaign_assets(self, request):
        self.removed.append(request.operations[0].remove)

    def mutate_ad_group_assets(self, request):
        self.removed.append(request.operations[0].remove)

    def mutate_customer_assets(self, request):
        self.removed.append(request.operations[0].remove)


class _FakeSdk:
    def __init__(self, ga_service, link_client) -> None:
        self._ga = ga_service
        self._link = link_client
        self.client = self

    def get_service(self, name: str):
        if name == "GoogleAdsService":
            return self._ga
        return self._link


class AssetRemoveTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocked_when_linkages_and_no_force(self):
        ga = _FakeGAService(
            {
                "campaign_asset": [
                    _campaign_link(f"customers/{CUSTOMER}/campaignAssets/11~{ASSET_ID}~SITELINK", "11")
                ],
                "ad_group_asset": [
                    _ad_group_link(f"customers/{CUSTOMER}/adGroupAssets/22~{ASSET_ID}~SITELINK", "22")
                ],
            }
        )
        link = _FakeLinkClient()
        with mock.patch.object(
            asset_module, "get_sdk_client", return_value=_FakeSdk(ga, link)
        ):
            out = await AssetService().remove_asset(
                _ApiCtx(), CUSTOMER, asset_id=ASSET_ID
            )
        self.assertEqual(out["status"], "blocked")
        self.assertTrue(out["force_required"])
        self.assertEqual(out["linkage_count"], 2)
        self.assertEqual({l["level"] for l in out["linkages"]}, {"campaign", "ad_group"})
        # Nothing was actually detached.
        self.assertEqual(link.removed, [])

    async def test_force_detaches_all_levels(self):
        c_rn = f"customers/{CUSTOMER}/campaignAssets/11~{ASSET_ID}~SITELINK"
        a_rn = f"customers/{CUSTOMER}/adGroupAssets/22~{ASSET_ID}~SITELINK"
        u_rn = f"customers/{CUSTOMER}/customerAssets/{ASSET_ID}~SITELINK"
        ga = _FakeGAService(
            {
                "campaign_asset": [_campaign_link(c_rn, "11")],
                "ad_group_asset": [_ad_group_link(a_rn, "22")],
                "customer_asset": [_customer_link(u_rn)],
            }
        )
        link = _FakeLinkClient()
        with mock.patch.object(
            asset_module, "get_sdk_client", return_value=_FakeSdk(ga, link)
        ):
            out = await AssetService().remove_asset(
                _ApiCtx(), CUSTOMER, asset_id=ASSET_ID, force=True
            )
        self.assertEqual(out["status"], "removed")
        self.assertEqual(out["detached_count"], 3)
        self.assertEqual(set(link.removed), {c_rn, a_rn, u_rn})

    async def test_no_linkages_is_noop(self):
        ga = _FakeGAService({})
        link = _FakeLinkClient()
        with mock.patch.object(
            asset_module, "get_sdk_client", return_value=_FakeSdk(ga, link)
        ):
            out = await AssetService().remove_asset(
                _ApiCtx(), CUSTOMER, asset_resource_name=ASSET_RN
            )
        self.assertEqual(out["status"], "no_op")
        self.assertEqual(out["detached"], [])
        self.assertEqual(link.removed, [])


# ── campaign_asset status update (the filled linkage gap) ──────────────────────
class _FakeCampaignAssetClient:
    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_campaign_assets(self, request):
        self.requests.append(request)
        from google.ads.googleads.v23.services.types.campaign_asset_service import (
            MutateCampaignAssetResult,
            MutateCampaignAssetsResponse,
        )

        return MutateCampaignAssetsResponse(
            results=[MutateCampaignAssetResult(resource_name="rn")]
        )


class CampaignAssetStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_update_builds_mask(self):
        from google.ads.googleads.v23.enums.types.asset_field_type import (
            AssetFieldTypeEnum,
        )

        svc = CampaignAssetService()
        fake = _FakeCampaignAssetClient()
        svc._client = fake  # type: ignore[assignment]
        await svc.update_campaign_asset_status(
            _ApiCtx(),
            CUSTOMER,
            campaign_id="777",
            asset_id=ASSET_ID,
            field_type=AssetFieldTypeEnum.AssetFieldType.SITELINK,
            status="PAUSED",
        )
        op = fake.requests[-1].operations[0]
        self.assertEqual(list(op.update_mask.paths), ["status"])
        self.assertTrue(
            op.update.resource_name.endswith(f"777~{ASSET_ID}~SITELINK")
        )


# ── wire-through: catalog + registry + harness discovery ───────────────────────
class WireThroughTests(unittest.TestCase):
    def test_execution_catalog_lists_new_write_tools(self):
        from google_ads.tool_registry import execution_catalog

        write = execution_catalog()["write"]
        for name in (
            "asset_update_asset",
            "asset_remove_asset",
            "campaign_asset_update_campaign_asset_status",
        ):
            self.assertIn(name, write)


class HarnessDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_harness_discovers_new_tools_and_args(self):
        import sys

        with mock.patch.object(sys, "argv", ["validate_all_tools"]):
            from validate_all_tools import HARVEST_TOOL_ARGS, enumerate_tools

            tools = await enumerate_tools()
        by_name = {full: params for (full, _ns, _fn, params) in tools}

        for name in (
            "asset_update_asset",
            "asset_remove_asset",
            "campaign_asset_update_campaign_asset_status",
        ):
            self.assertIn(name, by_name)
            self.assertIn(name, HARVEST_TOOL_ARGS)

        # update surfaces the immutable-media guard param + typed fields.
        props = by_name["asset_update_asset"].get("properties", {})
        self.assertIn("image_data", props)
        self.assertIn("link_text", props)
        # remove surfaces the force guard.
        self.assertIn("force", by_name["asset_remove_asset"].get("properties", {}))

        # Harness entries are shaped right (fail-closed force / status).
        remove_args = HARVEST_TOOL_ARGS["asset_remove_asset"](
            {"sitelink_asset_id": ASSET_ID}
        )
        self.assertTrue(remove_args["force"])
        status_args = HARVEST_TOOL_ARGS["campaign_asset_update_campaign_asset_status"](
            {"campaign_id": "777", "sitelink_asset_id": ASSET_ID}
        )
        self.assertEqual(status_args["status"], "PAUSED")


if __name__ == "__main__":
    unittest.main()
