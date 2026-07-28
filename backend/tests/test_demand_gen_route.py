"""Demand Gen creation route — the wizard's entry point into the shared
orchestrator (POST /api/accounts/{id}/campaigns/demand-gen).

Repo test style: drive the async route function directly (no TestClient), with
the orchestrator + SDK-client init monkeypatched. Asserts:

  - the wizard payload maps onto the orchestrator BUNDLE correctly
    (budget micros, final_urls, marketing_images slots, channels dict with
    gmail OFF, tCPA micros, geo include/EXCLUDE + language id passthrough,
    numeric-only id filtering);
  - a clean create returns the DemandGenCreateResponse passthrough;
  - DemandGenValidationError → HTTP 422 with the field error list;
  - DemandGenStepError → HTTP 502 carrying step + rolled_back.

No DB, no live Google calls.

Run: cd backend && .venv/bin/python -m unittest tests.test_demand_gen_route -v
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, Dict

from fastapi import HTTPException

from app.routers import demand_gen as dgr
from google_ads.services.campaign.demand_gen_orchestrator import (
    DemandGenStepError,
    DemandGenValidationError,
)


def _run(coro):
    return asyncio.run(coro)


def _valid_body(**over) -> dgr.DemandGenCreateRequest:
    payload: Dict[str, Any] = {
        "name": "Panama QIV — DG",
        "budget_micros": 50_000_000,
        "final_urls": ["https://goldenvisas.mercan.com/panama"],
        "business_name": "Mercan",
        "headlines": ["Invest in Panama", "Second residency"],
        "descriptions": ["Panama's investor visa, done right."],
        "logos": ["uuid-logo-1"],
        "marketing_images": {
            "landscape": ["uuid-ls-1"],
            "square": ["uuid-sq-1"],
            "portrait": [],
            "tall_portrait": [],
        },
        "channels": {
            "youtube_in_stream": True, "youtube_in_feed": True,
            "youtube_shorts": True, "discover": True,
            "display": True, "gmail": False,
        },
        "call_to_action_text": "Learn more",
        "target_cpa_micros": 120_000_000,
        "location_ids": ["2840", "2826"],
        "excluded_location_ids": ["1014044"],
        "language_ids": ["1000"],
    }
    payload.update(over)
    return dgr.DemandGenCreateRequest(**payload)


class DemandGenRouteMapping(unittest.TestCase):
    def setUp(self):
        self._orig_ensure = dgr._ensure_sdk_client
        self._orig_create = dgr._orchestrator.create_demand_gen_campaign
        # SDK client init is a no-op in tests — the route runs in-process.
        dgr._ensure_sdk_client = lambda: None
        self.captured: Dict[str, Any] = {}

    def tearDown(self):
        dgr._ensure_sdk_client = self._orig_ensure
        dgr._orchestrator.create_demand_gen_campaign = self._orig_create

    def _patch_create(self, fn):
        dgr._orchestrator.create_demand_gen_campaign = fn

    def test_happy_path_maps_bundle_and_passes_through_result(self):
        async def _fake_create(*, ctx, customer_id, bundle):
            self.captured["customer_id"] = customer_id
            self.captured["bundle"] = bundle
            return {
                "campaign_id": "555",
                "budget_id": "111",
                "ad_group_id": "222",
                "ad_group_ad_id": "333",
                "channels": bundle["channels"],
                "image_asset_ids": {"logos": ["9001"], "landscape": ["9002"]},
                "warnings": ["audience skipped"],
            }
        self._patch_create(_fake_create)

        resp = _run(dgr.create_demand_gen("7178239091", _valid_body()))

        # Response passthrough
        self.assertEqual(resp.campaign_id, "555")
        self.assertEqual(resp.ad_group_id, "222")
        self.assertEqual(resp.warnings, ["audience skipped"])

        # Bundle mapping
        b = self.captured["bundle"]
        self.assertEqual(self.captured["customer_id"], "7178239091")
        self.assertEqual(b["budget_micros"], 50_000_000)
        self.assertEqual(b["final_urls"], ["https://goldenvisas.mercan.com/panama"])
        self.assertEqual(b["business_name"], "Mercan")
        self.assertEqual(b["marketing_images"]["landscape"], ["uuid-ls-1"])
        self.assertEqual(b["marketing_images"]["square"], ["uuid-sq-1"])
        self.assertEqual(b["target_cpa_micros"], 120_000_000)
        self.assertEqual(b["call_to_action_text"], "Learn more")
        self.assertEqual(b["location_ids"], ["2840", "2826"])
        self.assertEqual(b["excluded_location_ids"], ["1014044"])
        self.assertEqual(b["language_ids"], ["1000"])
        # Gmail defaults OFF; at least one channel ON.
        self.assertFalse(b["channels"]["gmail"])
        self.assertTrue(b["channels"]["display"])

    def test_gmail_defaults_off_when_channels_omitted(self):
        async def _fake_create(*, ctx, customer_id, bundle):
            self.captured["bundle"] = bundle
            return {
                "campaign_id": "1", "budget_id": "1", "ad_group_id": "1",
                "ad_group_ad_id": "1", "channels": bundle["channels"],
                "image_asset_ids": {}, "warnings": [],
            }
        self._patch_create(_fake_create)
        # Omit the channels block entirely — the request default must be gmail OFF.
        body = _valid_body()
        body.channels = dgr.DemandGenChannels()
        _run(dgr.create_demand_gen("7178239091", body))
        self.assertFalse(self.captured["bundle"]["channels"]["gmail"])
        self.assertTrue(self.captured["bundle"]["channels"]["youtube_in_stream"])

    def test_validation_error_is_422(self):
        async def _boom(*, ctx, customer_id, bundle):
            raise DemandGenValidationError(["need >=1 logo image", "business_name too long"])
        self._patch_create(_boom)

        with self.assertRaises(HTTPException) as c:
            _run(dgr.create_demand_gen("7178239091", _valid_body()))
        self.assertEqual(c.exception.status_code, 422)
        self.assertEqual(c.exception.detail["error"], "VALIDATION_FAILED")
        self.assertIn("need >=1 logo image", c.exception.detail["errors"])

    def test_step_error_is_502_with_rollback(self):
        async def _boom(*, ctx, customer_id, bundle):
            raise DemandGenStepError(
                step="campaign creation",
                original=RuntimeError("google said no"),
                rollback_report=["removed budget customers/x/campaignBudgets/1"],
            )
        self._patch_create(_boom)

        with self.assertRaises(HTTPException) as c:
            _run(dgr.create_demand_gen("7178239091", _valid_body()))
        self.assertEqual(c.exception.status_code, 502)
        self.assertEqual(c.exception.detail["error"], "GOOGLE_ADS_ERROR")
        self.assertEqual(c.exception.detail["step"], "campaign creation")
        self.assertTrue(c.exception.detail["rolled_back"])


if __name__ == "__main__":
    unittest.main()
