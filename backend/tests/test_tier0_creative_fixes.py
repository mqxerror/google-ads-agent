"""Tier-0 creative bug fixes (meta-agent audit 2026-08-03).

Covers the three confirmed bugs fixed in one pass:

  1. Studio generate-image rejects an aspect ratio the chosen model does not
     declare (e.g. '1.91:1') with a clear 422 — instead of passing it silently
     to the Higgsfield CLI. Unknown model ids skip the check (CLI is authority).
  2. The account resolves its own Demand Gen ads for the Studio push-to-ad
     picker (no hardcoded live ad ids); the route maps the service output and
     502s on a Google failure.
  3. PMax no longer hard-requires a YouTube video — Google auto-generates one
     from the images + text when none is supplied.

Repo test style: drive the async route/validator functions directly (no
TestClient), monkeypatching the boundaries. No DB, no live Google calls.

Run: cd backend && .venv/bin/python -m pytest tests/test_tier0_creative_fixes.py -v
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, Dict, List

from fastapi import HTTPException

from app.routers import demand_gen as dgr
from app.routers import studio
from google_ads.services.campaign import pmax_orchestrator as po
from google_ads.services.campaign.pmax_orchestrator import PMaxValidationError


def _run(coro):
    return asyncio.run(coro)


# ── Bug 1: aspect validation in the generate-image route ──────────────────


class AspectValidationTests(unittest.TestCase):
    def test_unsupported_aspect_rejected_422(self):
        """'1.91:1' is not declared by any image model → clean 422 naming the
        allowed list, raised BEFORE any DB work."""
        body = studio.GenerateImageRequest(
            prompt="a corporate residency brand image",
            model="nano_banana_2",
            aspect_ratios=["1.91:1", "1:1"],
        )
        with self.assertRaises(HTTPException) as cm:
            _run(studio.generate_image(body))
        self.assertEqual(cm.exception.status_code, 422)
        detail = str(cm.exception.detail)
        self.assertIn("1.91:1", detail)
        self.assertIn("nano_banana_2", detail)

    def test_unknown_model_skips_aspect_validation(self):
        """A model id not in the curated catalog is NOT aspect-validated (the
        CLI is the authority). Prove it by making the NEXT stage (get_db) raise
        a sentinel: reaching it means the aspect 422 gate did not fire."""
        class _Sentinel(RuntimeError):
            pass

        async def boom():
            raise _Sentinel("reached DB stage")

        body = studio.GenerateImageRequest(
            prompt="x",
            model="some_future_model_not_in_catalog",
            aspect_ratios=["1.91:1"],
        )
        orig = studio.get_db
        studio.get_db = boom  # type: ignore[assignment]
        try:
            with self.assertRaises(_Sentinel):
                _run(studio.generate_image(body))
        finally:
            studio.get_db = orig  # type: ignore[assignment]


# ── Bug 2: account-resolved Demand Gen ad listing ─────────────────────────


class DemandGenAdListingTests(unittest.TestCase):
    def test_lists_ads_mapped_to_options(self):
        import app.services.google_ads as gads

        sample = [{
            "ad_id": "818651372857",
            "ad_name": "Panama DG",
            "ad_group_id": "205525130784",
            "ad_group_name": "AG1",
            "campaign_id": "24002195025",
            "campaign_name": "Panama QIP",
            "status": "ENABLED",
        }]

        async def fake_get(self, customer_id):
            return sample

        orig = gads.GoogleAdsService.get_demand_gen_ads
        gads.GoogleAdsService.get_demand_gen_ads = fake_get  # type: ignore[assignment]
        try:
            out = _run(dgr.list_demand_gen_ads("24002195025"))
        finally:
            gads.GoogleAdsService.get_demand_gen_ads = orig  # type: ignore[assignment]

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].ad_id, "818651372857")
        self.assertEqual(out[0].ad_group_id, "205525130784")
        self.assertEqual(out[0].campaign_name, "Panama QIP")

    def test_google_failure_returns_502(self):
        import app.services.google_ads as gads

        async def boom(self, customer_id):
            raise RuntimeError("quota exhausted")

        orig = gads.GoogleAdsService.get_demand_gen_ads
        gads.GoogleAdsService.get_demand_gen_ads = boom  # type: ignore[assignment]
        try:
            with self.assertRaises(HTTPException) as cm:
                _run(dgr.list_demand_gen_ads("24002195025"))
        finally:
            gads.GoogleAdsService.get_demand_gen_ads = orig  # type: ignore[assignment]
        self.assertEqual(cm.exception.status_code, 502)


# ── Bug 3: PMax video is optional ─────────────────────────────────────────


def _pmax_bundle(with_video: bool) -> Dict[str, Any]:
    b: Dict[str, Any] = {
        "name": "Video-optional test",
        "budget_micros": 10_000_000,
        "final_urls": ["https://example.com"],
        "business_name": "Example",
        "headlines": ["H one", "H two", "H three"],
        "long_headlines": ["A long headline for the test"],
        "descriptions": ["Description one", "Description two"],
        "logos": ["uuid-logo"],
        "marketing_images": {"landscape": ["uuid-ls"], "square": ["uuid-sq"], "portrait": []},
    }
    if with_video:
        b["video_youtube_ids"] = ["dQw4w9WgXcQ"]
    return b


class PMaxVideoOptionalTests(unittest.TestCase):
    def test_bundle_without_video_passes_validation(self):
        """No YouTube id must NOT raise — Google auto-generates a video."""
        po._validate_bundle(_pmax_bundle(with_video=False))  # no raise

    def test_bundle_with_video_still_passes(self):
        po._validate_bundle(_pmax_bundle(with_video=True))  # no raise

    def test_missing_images_still_rejected(self):
        """Sanity: dropping the video gate did not weaken the image gate."""
        bad = _pmax_bundle(with_video=False)
        bad["marketing_images"] = {"landscape": [], "square": [], "portrait": []}
        with self.assertRaises(PMaxValidationError) as cm:
            po._validate_bundle(bad)
        errs: List[str] = cm.exception.errors
        # The image errors are present; NO YouTube-video error is emitted.
        self.assertTrue(any("landscape" in e for e in errs))
        self.assertFalse(any("YouTube" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
