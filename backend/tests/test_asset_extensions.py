"""Unit tests — ad-extension (asset) creation tools on AssetService.

Pins the four extension-asset creators added to close the P0 audit gap
(mcp_main advertised "create sitelinks, callouts, call extensions,
structured snippets" but only text/image/youtube assets existed):

- create_sitelink_asset          → Asset.sitelink_asset (SitelinkAsset)
- create_callout_asset           → Asset.callout_asset (CalloutAsset)
- create_structured_snippet_asset → Asset.structured_snippet_asset
- create_call_asset              → Asset.call_asset (CallAsset)

Each test asserts the AssetOperation built by the service sets the right
oneof field with the caller's values, stamps the correct AssetType, and
propagates validate_only onto the MutateAssetsRequest. The SDK client is
stubbed — NO live Google mutation happens; the captured request is the
validate_only smoke check. The `mutate_assets` stub returns a minimal
response so serialize_proto_message yields the real resource_name shape.

Run:  cd backend && .venv/bin/python -m unittest tests.test_asset_extensions -v
"""

from __future__ import annotations

import unittest
from typing import Any, List

from google.ads.googleads.v23.enums.types.asset_type import AssetTypeEnum
from google.ads.googleads.v23.services.types.asset_service import (
    MutateAssetResult,
    MutateAssetsResponse,
)

from google_ads.services.assets.asset_service import AssetService

CUSTOMER = "1234567890"
ASSET_RN = f"customers/{CUSTOMER}/assets/424242"


class _ApiCtx:
    """Minimal FastMCP-Context stand-in — only ctx.log is exercised."""

    async def log(self, level: str, message: str) -> None:  # pragma: no cover
        return None


class _FakeAssetClient:
    """Captures every mutate_assets request; returns a minimal response."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_assets(self, request):
        self.requests.append(request)
        # Real proto response so serialize_proto_message returns the true
        # results[].resource_name dict shape (not the stringified fallback).
        return MutateAssetsResponse(
            results=[MutateAssetResult(resource_name=ASSET_RN)]
        )


def _service() -> tuple[AssetService, _FakeAssetClient]:
    svc = AssetService()
    fake = _FakeAssetClient()
    svc._client = fake  # type: ignore[assignment]  # bypass lazy SDK client
    return svc, fake


class AssetExtensionTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_sitelink_asset(self):
        svc, fake = _service()
        result = await svc.create_sitelink_asset(
            _ApiCtx(),
            CUSTOMER,
            link_text="Book a Call",
            description1="Talk to an advisor",
            description2="Free, no obligation",
            final_urls=["https://example.com/book"],
            validate_only=True,
        )
        req = fake.requests[-1]
        self.assertTrue(req.validate_only)
        asset = req.operations[0].create
        self.assertEqual(asset.type_, AssetTypeEnum.AssetType.SITELINK)
        self.assertEqual(asset.sitelink_asset.link_text, "Book a Call")
        self.assertEqual(asset.sitelink_asset.description1, "Talk to an advisor")
        self.assertEqual(asset.sitelink_asset.description2, "Free, no obligation")
        # final_urls live on the Asset, not the SitelinkAsset.
        self.assertEqual(list(asset.final_urls), ["https://example.com/book"])
        self.assertEqual(result["results"][0]["resource_name"], ASSET_RN)

    async def test_create_sitelink_asset_optional_fields_omitted(self):
        """Empty descriptions / no final_urls stay unset — not blank strings."""
        svc, fake = _service()
        await svc.create_sitelink_asset(_ApiCtx(), CUSTOMER, link_text="Home")
        asset = fake.requests[-1].operations[0].create
        self.assertFalse(fake.requests[-1].validate_only)
        self.assertEqual(asset.sitelink_asset.link_text, "Home")
        self.assertEqual(asset.sitelink_asset.description1, "")
        self.assertEqual(list(asset.final_urls), [])

    async def test_create_callout_asset(self):
        svc, fake = _service()
        await svc.create_callout_asset(
            _ApiCtx(), CUSTOMER, callout_text="Free Shipping", validate_only=True
        )
        req = fake.requests[-1]
        self.assertTrue(req.validate_only)
        asset = req.operations[0].create
        self.assertEqual(asset.type_, AssetTypeEnum.AssetType.CALLOUT)
        self.assertEqual(asset.callout_asset.callout_text, "Free Shipping")

    async def test_create_structured_snippet_asset(self):
        svc, fake = _service()
        await svc.create_structured_snippet_asset(
            _ApiCtx(),
            CUSTOMER,
            header="Services",
            values=["Consulting", "Filing", "Review"],
            validate_only=True,
        )
        req = fake.requests[-1]
        self.assertTrue(req.validate_only)
        asset = req.operations[0].create
        self.assertEqual(asset.type_, AssetTypeEnum.AssetType.STRUCTURED_SNIPPET)
        self.assertEqual(asset.structured_snippet_asset.header, "Services")
        self.assertEqual(
            list(asset.structured_snippet_asset.values),
            ["Consulting", "Filing", "Review"],
        )

    async def test_create_call_asset(self):
        svc, fake = _service()
        await svc.create_call_asset(
            _ApiCtx(),
            CUSTOMER,
            phone_number="+1 800 555 0100",
            country_code="US",
            validate_only=True,
        )
        req = fake.requests[-1]
        self.assertTrue(req.validate_only)
        asset = req.operations[0].create
        self.assertEqual(asset.type_, AssetTypeEnum.AssetType.CALL)
        self.assertEqual(asset.call_asset.phone_number, "+1 800 555 0100")
        self.assertEqual(asset.call_asset.country_code, "US")

    async def test_customer_id_is_formatted(self):
        """Dashed customer IDs are normalized before hitting the request."""
        svc, fake = _service()
        await svc.create_callout_asset(_ApiCtx(), "123-456-7890", callout_text="Hi")
        self.assertEqual(fake.requests[-1].customer_id, "1234567890")


if __name__ == "__main__":
    unittest.main()
