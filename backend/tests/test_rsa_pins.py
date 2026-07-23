"""Unit tests — RSA headline/description PINNING on the ad service.

Closes the confirmed MCP capability gap where the agent could CREATE responsive
search ads but never PIN headlines/descriptions, and had no in-place pin-update
tool (the operator had to pin the 4 ads created today via the raw SDK).

Two surfaces are covered:
  * ``create_responsive_search_ad`` gains optional ``pinned_headline_1..3`` /
    ``pinned_description_1..2`` (each names the EXACT text of a supplied asset).
  * new ``update_rsa_pins`` reads the live RSA and rewrites its asset lists in
    place (same ad id), preserving every text + existing pin except the named
    re-pins and an optional ``clear_pins`` reset.

No live Google mutation happens — ``get_sdk_client`` is patched with a fake whose
``get_service`` routes AdGroupAdService / GoogleAdsService / AdService to
request-capturing stubs; the captured request / update_mask is the smoke check.
The final class drives the real MCP tool enumeration (validate_all_tools) to
prove the harness discovers both tools, that the pin params surface on the
schema, that the fail-closed ARGS map exercises the pin + clear paths, and that
the execution catalog + live registry both list the tools.

Run:  cd backend && .venv/bin/python -m unittest tests.test_rsa_pins -v
"""

from __future__ import annotations

import unittest
from typing import Any, List, Optional, Tuple
from unittest import mock

from google.ads.googleads.v23.common.types.ad_asset import AdTextAsset
from google.ads.googleads.v23.enums.types.served_asset_field_type import (
    ServedAssetFieldTypeEnum,
)
from google.ads.googleads.v23.services.types.ad_group_ad_service import (
    MutateAdGroupAdResult,
    MutateAdGroupAdsResponse,
)
from google.ads.googleads.v23.services.types.ad_service import (
    MutateAdResult,
    MutateAdsResponse,
)
from google.ads.googleads.v23.services.types.google_ads_service import GoogleAdsRow

from google_ads.services.ad_group import ad_service as ad_module
from google_ads.services.ad_group.ad_service import AdService

PF = ServedAssetFieldTypeEnum.ServedAssetFieldType

CUSTOMER = "1234567890"
AD_ID = "555000111"
AD_RN = f"customers/{CUSTOMER}/ads/{AD_ID}"
AG_ID = "999888"


class _ApiCtx:
    """Minimal FastMCP-Context stand-in — only ctx.log is exercised."""

    async def log(self, level: str, message: str) -> None:  # pragma: no cover
        return None


class _CaptureAdGroupAdClient:
    """Captures create requests; returns a minimal real proto response."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_ad_group_ads(self, request):
        self.requests.append(request)
        return MutateAdGroupAdsResponse(
            results=[MutateAdGroupAdResult(resource_name=AD_RN)]
        )


class _CaptureAdClient:
    """Captures in-place Ad update requests (used by update_rsa_pins)."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_ads(self, request):
        self.requests.append(request)
        return MutateAdsResponse(results=[MutateAdResult(resource_name=AD_RN)])


class _FakeGoogleAdsService:
    """Returns the pre-baked live RSA rows for the update read step."""

    def __init__(self, rows: List[GoogleAdsRow]) -> None:
        self._rows = rows

    def search(self, customer_id: str, query: str):
        return list(self._rows)


class _FakeSdk:
    """Stand-in for GoogleAdsSdkClient — get_service routes by service name."""

    def __init__(
        self,
        *,
        rows: Optional[List[GoogleAdsRow]] = None,
        ag_ad_client: Optional[_CaptureAdGroupAdClient] = None,
        ad_client: Optional[_CaptureAdClient] = None,
    ) -> None:
        self._rows = rows or []
        self._ag_ad_client = ag_ad_client
        self._ad_client = ad_client
        self.client = self  # sdk_client.client.get_service(...)

    def get_service(self, name: str):
        if name == "AdGroupAdService":
            return self._ag_ad_client
        if name == "GoogleAdsService":
            return _FakeGoogleAdsService(self._rows)
        if name == "AdService":
            return self._ad_client
        raise AssertionError(f"unexpected service requested: {name}")


def _make_live_row(
    headlines: List[Tuple[str, Any]],
    descriptions: List[Tuple[str, Any]],
) -> GoogleAdsRow:
    """Build a real GoogleAdsRow whose ad_group_ad.ad is an RSA with the given
    (text, pinned_field) headline/description assets."""
    row = GoogleAdsRow()
    row.ad_group_ad.ad.id = int(AD_ID)
    rsa = row.ad_group_ad.ad.responsive_search_ad
    for text, pin in headlines:
        asset = AdTextAsset()
        asset.text = text
        if pin is not None:
            asset.pinned_field = pin
        rsa.headlines.append(asset)
    for text, pin in descriptions:
        asset = AdTextAsset()
        asset.text = text
        if pin is not None:
            asset.pinned_field = pin
        rsa.descriptions.append(asset)
    return row


# ── create_responsive_search_ad with pins ────────────────────────────────────
class CreateRSAWithPinsTests(unittest.IsolatedAsyncioTestCase):
    async def _create(self, **pins):
        capture = _CaptureAdGroupAdClient()
        with mock.patch.object(
            ad_module, "get_sdk_client", return_value=_FakeSdk(ag_ad_client=capture)
        ):
            await AdService().create_responsive_search_ad(
                _ApiCtx(),
                CUSTOMER,
                AG_ID,
                headlines=["Buy Visas Fast", "Trusted Advisors", "Apply Today"],
                descriptions=["Expert guidance now.", "Free consultation today."],
                final_urls=["https://example.com"],
                **pins,
            )
        return capture.requests[-1].operations[0].create.ad.responsive_search_ad

    async def test_create_pins_named_assets(self):
        """A pinned headline + description land on the matching assets only."""
        rsa = await self._create(
            pinned_headline_2="Trusted Advisors",
            pinned_description_1="Expert guidance now.",
        )
        pins_by_text = {h.text: h.pinned_field for h in rsa.headlines}
        self.assertEqual(pins_by_text["Trusted Advisors"], PF.HEADLINE_2)
        self.assertEqual(pins_by_text["Buy Visas Fast"], PF.UNSPECIFIED)
        self.assertEqual(pins_by_text["Apply Today"], PF.UNSPECIFIED)
        desc_pins = {d.text: d.pinned_field for d in rsa.descriptions}
        self.assertEqual(desc_pins["Expert guidance now."], PF.DESCRIPTION_1)
        self.assertEqual(desc_pins["Free consultation today."], PF.UNSPECIFIED)

    async def test_create_without_pins_is_backcompat(self):
        """Omitting all pins => every asset stays UNSPECIFIED (no pins)."""
        rsa = await self._create()
        self.assertTrue(
            all(h.pinned_field == PF.UNSPECIFIED for h in rsa.headlines)
        )
        self.assertTrue(
            all(d.pinned_field == PF.UNSPECIFIED for d in rsa.descriptions)
        )

    async def test_create_unknown_pin_text_errors(self):
        """Naming a headline that is not in the list raises, listing actuals."""
        with self.assertRaises(Exception) as ctx:
            await self._create(pinned_headline_1="Not In List")
        msg = str(ctx.exception)
        self.assertIn("Not In List", msg)
        self.assertIn("Buy Visas Fast", msg)  # the ad's actual headlines


# ── update_rsa_pins ───────────────────────────────────────────────────────────
class UpdateRSAPinsTests(unittest.IsolatedAsyncioTestCase):
    async def _update(self, row: GoogleAdsRow, **kwargs):
        ad_client = _CaptureAdClient()
        with mock.patch.object(
            ad_module,
            "get_sdk_client",
            return_value=_FakeSdk(rows=[row], ad_client=ad_client),
        ):
            await AdService().update_rsa_pins(
                _ApiCtx(), CUSTOMER, ad_id=AD_ID, **kwargs
            )
        return ad_client.requests[-1].operations[0]

    async def test_sets_named_pin_preserving_all_texts_and_mask(self):
        row = _make_live_row(
            [("H One", None), ("H Two", None), ("H Three", None)],
            [("D One", None), ("D Two", None)],
        )
        op = await self._update(row, pinned_headline_2="H Two")
        rsa = op.update.responsive_search_ad
        # every text survives, in order
        self.assertEqual([h.text for h in rsa.headlines], ["H One", "H Two", "H Three"])
        self.assertEqual([d.text for d in rsa.descriptions], ["D One", "D Two"])
        # only the named headline is pinned
        pins = {h.text: h.pinned_field for h in rsa.headlines}
        self.assertEqual(pins["H Two"], PF.HEADLINE_2)
        self.assertEqual(pins["H One"], PF.UNSPECIFIED)
        self.assertEqual(pins["H Three"], PF.UNSPECIFIED)
        # in-place update on the same ad, with the RSA asset mask
        self.assertEqual(op.update.resource_name, AD_RN)
        self.assertEqual(
            list(op.update_mask.paths),
            ["responsive_search_ad.headlines", "responsive_search_ad.descriptions"],
        )

    async def test_preserves_existing_pins_when_adding_a_new_one(self):
        row = _make_live_row(
            [("H One", PF.HEADLINE_3), ("H Two", None)],
            [("D One", None), ("D Two", None)],
        )
        op = await self._update(row, pinned_description_1="D One")
        rsa = op.update.responsive_search_ad
        h_pins = {h.text: h.pinned_field for h in rsa.headlines}
        d_pins = {d.text: d.pinned_field for d in rsa.descriptions}
        self.assertEqual(h_pins["H One"], PF.HEADLINE_3)  # existing pin kept
        self.assertEqual(d_pins["D One"], PF.DESCRIPTION_1)  # new pin applied

    async def test_clear_pins_strips_everything(self):
        row = _make_live_row(
            [("H One", PF.HEADLINE_1), ("H Two", PF.HEADLINE_2)],
            [("D One", PF.DESCRIPTION_1), ("D Two", None)],
        )
        op = await self._update(row, clear_pins=True)
        rsa = op.update.responsive_search_ad
        self.assertTrue(all(h.pinned_field == PF.UNSPECIFIED for h in rsa.headlines))
        self.assertTrue(all(d.pinned_field == PF.UNSPECIFIED for d in rsa.descriptions))
        # texts still preserved
        self.assertEqual([h.text for h in rsa.headlines], ["H One", "H Two"])

    async def test_clear_then_repin(self):
        row = _make_live_row(
            [("H One", PF.HEADLINE_1), ("H Two", None)],
            [("D One", None), ("D Two", None)],
        )
        op = await self._update(row, clear_pins=True, pinned_headline_2="H Two")
        pins = {h.text: h.pinned_field for h in op.update.responsive_search_ad.headlines}
        self.assertEqual(pins["H One"], PF.UNSPECIFIED)  # old pin cleared
        self.assertEqual(pins["H Two"], PF.HEADLINE_2)  # re-pinned

    async def test_unknown_text_errors_listing_actual_assets(self):
        row = _make_live_row(
            [("H One", None), ("H Two", None)],
            [("D One", None), ("D Two", None)],
        )
        with self.assertRaises(Exception) as ctx:
            await self._update(row, pinned_headline_1="Ghost Headline")
        msg = str(ctx.exception)
        self.assertIn("Ghost Headline", msg)
        self.assertIn("H One", msg)
        self.assertIn("H Two", msg)

    async def test_non_rsa_ad_errors(self):
        empty = GoogleAdsRow()
        empty.ad_group_ad.ad.id = int(AD_ID)  # no responsive_search_ad headlines
        with self.assertRaises(Exception) as ctx:
            await self._update(empty, pinned_headline_1="whatever")
        self.assertIn("not a responsive search ad", str(ctx.exception))

    async def test_missing_ad_errors(self):
        ad_client = _CaptureAdClient()
        with mock.patch.object(
            ad_module,
            "get_sdk_client",
            return_value=_FakeSdk(rows=[], ad_client=ad_client),
        ):
            with self.assertRaises(Exception) as ctx:
                await AdService().update_rsa_pins(
                    _ApiCtx(), CUSTOMER, ad_id=AD_ID, clear_pins=True
                )
        self.assertIn("No ad found", str(ctx.exception))
        self.assertEqual(ad_client.requests, [])  # never mutated


# ── harness / catalog / registry discovery ────────────────────────────────────
class RSAToolDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_enumeration_schema_harness_and_catalog(self):
        import sys

        with mock.patch.object(sys, "argv", ["validate_all_tools"]):
            from validate_all_tools import HARVEST_TOOL_ARGS, enumerate_tools

            tools = await enumerate_tools()
        by_name = {full: params for (full, _ns, _fn, params) in tools}

        # both tools registered, with pin params on the schema
        for name in ("ad_create_responsive_search_ad", "ad_update_rsa_pins"):
            self.assertIn(name, by_name)
            props = by_name[name].get("properties", {})
            for pin in (
                "pinned_headline_1",
                "pinned_headline_2",
                "pinned_headline_3",
                "pinned_description_1",
                "pinned_description_2",
            ):
                self.assertIn(pin, props, f"{pin} missing on {name}")
        self.assertIn("clear_pins", by_name["ad_update_rsa_pins"].get("properties", {}))

        # fail-closed harness args exercise the pin + clear paths
        create_args = HARVEST_TOOL_ARGS["ad_create_responsive_search_ad"](
            {"ad_group_id": AG_ID}
        )
        self.assertIn(create_args["pinned_headline_1"], create_args["headlines"])
        self.assertIn(
            create_args["pinned_description_1"], create_args["descriptions"]
        )
        update_args = HARVEST_TOOL_ARGS["ad_update_rsa_pins"]({"ad_id": AD_ID})
        self.assertTrue(update_args["clear_pins"])

        # execution catalog (grounded in the live registry) lists both writes.
        # execution_catalog uses asyncio.run internally, so it MUST run off this
        # test's event loop (per the tool_registry contract).
        import asyncio

        from google_ads.tool_registry import execution_catalog

        catalog = await asyncio.to_thread(execution_catalog)
        self.assertIn("ad_create_responsive_search_ad", catalog["write"])
        self.assertIn("ad_update_rsa_pins", catalog["write"])


if __name__ == "__main__":
    unittest.main()
