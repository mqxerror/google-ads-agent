"""Regression tests — PMax resubmit aspect-crop bypass (live 2026-06-11).

The ASPECT_RATIO_NOT_ALLOWED that survived the pre-flight crop had two
doors:

1. Step 3c's upload dedupe was keyed by local UUID alone, so the same
   source image filling two different-aspect slots uploaded ONCE with
   the FIRST slot's crop (slot order logos → landscape → ...), and the
   1:1 logo crop got linked as the 1.91:1 MARKETING_IMAGE.
2. Bundle entries that already looked like Google asset refs (resource
   names / bare numeric ids — e.g. a wizard bundle poisoned by a prior
   attempt) passed through with NO aspect verification at all.

These tests pin both fixes: per-(uuid, aspect) uploads with correctly
cropped bytes on every submit (incl. resubmits — nothing is reused
across attempts), and pre-flight 422 rejection of pre-uploaded assets
that are off-aspect or unverifiable.

Run:  cd backend && .venv/bin/python -m unittest tests.test_pmax_resubmit -v
No live Google calls — every service the orchestrator touches is stubbed.
"""

from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from PIL import Image

from google_ads.services.campaign import pmax_orchestrator as po
from google_ads.services.campaign.pmax_orchestrator import (
    ApiCtx,
    PMaxOrchestrator,
    PMaxValidationError,
)

CUSTOMER = "1234567890"
AG_RN = f"customers/{CUSTOMER}/assetGroups/999"


def _bundle(logos: List[str], landscape: List[str], square: List[str]) -> Dict[str, Any]:
    return {
        "name": "Resubmit Test",
        "budget_micros": 10_000_000,
        "final_urls": ["https://example.com"],
        "business_name": "Example",
        "headlines": ["H one", "H two", "H three"],
        "long_headlines": ["A long headline for the test"],
        "descriptions": ["Description one", "Description two"],
        "logos": logos,
        "marketing_images": {"landscape": landscape, "square": square, "portrait": []},
        "video_youtube_ids": ["dQw4w9WgXcQ"],
    }


class _FakeAssetService:
    """Records every image upload; returns unique resource names."""

    def __init__(self) -> None:
        self.image_uploads: List[Dict[str, Any]] = []  # {name, data, rn}
        self._n = 0
        self._text_n = 0

    async def create_text_asset(self, ctx, customer_id, text):
        self._text_n += 1
        return {"results": [{"resource_name": f"customers/{CUSTOMER}/assets/{9000 + self._text_n}"}]}

    async def create_image_asset(self, ctx, customer_id, image_data, name, mime_type):
        self._n += 1
        rn = f"customers/{CUSTOMER}/assets/{1000 + self._n}"
        self.image_uploads.append({"name": name, "data": image_data, "rn": rn})
        return {"results": [{"resource_name": rn}]}

    async def create_youtube_video_asset(self, ctx, customer_id, youtube_video_id, name=None):
        return {"results": [{"resource_name": f"customers/{CUSTOMER}/assets/8000"}]}


class _FakeGoogleAdsClient:
    """Captures the atomic mutate request; returns a minimal response."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            mutate_operation_responses=[
                SimpleNamespace(asset_group_result=SimpleNamespace(resource_name=AG_RN)),
            ]
        )

    def search(self, customer_id, query):  # pragma: no cover — stubbed per-test
        raise AssertionError("search should be stubbed via _fetch_image_asset_dims")


def _orchestrator() -> tuple[PMaxOrchestrator, _FakeAssetService, _FakeGoogleAdsClient, Dict[str, int]]:
    orch = PMaxOrchestrator()
    calls = {"budget": 0, "campaign": 0}
    fake_assets = _FakeAssetService()
    fake_ga = _FakeGoogleAdsClient()

    async def create_budget(ctx, customer_id, name, amount_micros):
        calls["budget"] += 1
        return {"results": [{"resource_name": f"customers/{CUSTOMER}/campaignBudgets/1"}]}

    async def create_campaign(ctx, customer_id, **kw):
        calls["campaign"] += 1
        return {"results": [{"resource_name": f"customers/{CUSTOMER}/campaigns/2"}]}

    async def post_create_sync(**kw):
        return None

    orch._budget = SimpleNamespace(create_campaign_budget=create_budget)  # type: ignore[assignment]
    orch._campaign = SimpleNamespace(create_campaign=create_campaign)  # type: ignore[assignment]
    orch._asset = fake_assets  # type: ignore[assignment]
    orch._google_ads = fake_ga  # type: ignore[assignment]
    orch._post_create_sync = post_create_sync  # type: ignore[method-assign]
    return orch, fake_assets, fake_ga, calls


def _aspect(data: bytes) -> float:
    with Image.open(BytesIO(data)) as img:
        w, h = img.size
    return w / h


class PMaxResubmitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # One 16:9 synthetic source image shared by every slot — off-aspect
        # for ALL PMax slots, so the crop must run for each.
        self.img_path = Path(self._tmp.name) / "src.png"
        Image.new("RGB", (1600, 900), (200, 40, 40)).save(self.img_path, "PNG")
        self.uuid = "11111111-2222-3333-4444-555555555555"

        async def locate(ref):
            if ref == self.uuid:
                return self.img_path, "image/png"
            raise LookupError("unknown local ref")

        self._orig_locate = po._locate_local_image
        po._locate_local_image = locate  # type: ignore[assignment]

    def tearDown(self) -> None:
        po._locate_local_image = self._orig_locate  # type: ignore[assignment]
        self._tmp.cleanup()

    async def test_same_uuid_in_two_slots_uploads_one_crop_per_aspect(self):
        """The live bypass: one UUID in logos + landscape + square must
        upload TWO distinct crops (1:1 and 1.91:1), and the MARKETING_IMAGE
        link must reference the 1.91:1 crop — never the 1:1 one. A second
        submit (resubmit path) re-fits from the local source again instead
        of reusing anything from attempt 1."""
        orch, fake_assets, fake_ga, _ = _orchestrator()
        bundle = _bundle([self.uuid], [self.uuid], [self.uuid])

        result = await orch.create_pmax_campaign(ApiCtx(), CUSTOMER, bundle)
        self.assertEqual(result["asset_group_id"], "999")

        # Exactly 2 uploads: aspects {1.0 (logos+square deduped), 1.91}.
        self.assertEqual(len(fake_assets.image_uploads), 2)
        by_rn = {u["rn"]: u for u in fake_assets.image_uploads}
        aspects = sorted(_aspect(u["data"]) for u in fake_assets.image_uploads)
        self.assertAlmostEqual(aspects[0], 1.0, delta=0.011)
        self.assertAlmostEqual(aspects[1], 1.91, delta=1.91 * 0.011)

        # Field-type ↔ asset wiring in the atomic mutate.
        ft = po.AssetFieldTypeEnum.AssetFieldType
        links: Dict[Any, List[str]] = {}
        for op in fake_ga.requests[-1].mutate_operations:
            link = op.asset_group_asset_operation.create
            if link.asset:
                links.setdefault(link.field_type, []).append(link.asset)
        self.assertAlmostEqual(
            _aspect(by_rn[links[ft.MARKETING_IMAGE][0]]["data"]), 1.91, delta=1.91 * 0.011
        )
        self.assertAlmostEqual(_aspect(by_rn[links[ft.LOGO][0]]["data"]), 1.0, delta=0.011)
        # logos + square share the 1:1 crop — same asset, by design.
        self.assertEqual(links[ft.LOGO][0], links[ft.SQUARE_MARKETING_IMAGE][0])

        # Resubmit: uploads again from local source — no cross-attempt reuse.
        await orch.create_pmax_campaign(ApiCtx(), CUSTOMER, _bundle([self.uuid], [self.uuid], [self.uuid]))
        self.assertEqual(len(fake_assets.image_uploads), 4)

    async def test_off_aspect_preuploaded_asset_rejected_preflight(self):
        """A bare resource name (e.g. swapped in during a prior attempt)
        whose stored dimensions don't match the slot is a 422 BEFORE any
        Google entity is created — naming the slot and the asset."""
        orch, _, _, calls = _orchestrator()
        rn = f"customers/{CUSTOMER}/assets/555"
        orch._fetch_image_asset_dims = lambda cid, rns: {rn: (1000, 1000)}  # type: ignore[method-assign]

        with self.assertRaises(PMaxValidationError) as cm:
            await orch.create_pmax_campaign(
                ApiCtx(), CUSTOMER, _bundle([self.uuid], [rn], [self.uuid])
            )
        msg = "; ".join(cm.exception.errors)
        self.assertIn("landscape[0]", msg)
        self.assertIn("555", msg)
        self.assertIn("1000x1000", msg)
        self.assertEqual(calls["budget"], 0, "nothing may be created pre-flight")
        self.assertEqual(calls["campaign"], 0)

    async def test_unverifiable_preuploaded_asset_rejected_preflight(self):
        """If the asset's dimensions can't be fetched (deleted, not an
        image, wrong account), the orchestrator must refuse to link it —
        unknown aspect is treated as off-aspect."""
        orch, _, _, calls = _orchestrator()
        orch._fetch_image_asset_dims = lambda cid, rns: {}  # type: ignore[method-assign]

        with self.assertRaises(PMaxValidationError) as cm:
            await orch.create_pmax_campaign(
                ApiCtx(), CUSTOMER, _bundle([self.uuid], ["customers/1234567890/assets/777"], [self.uuid])
            )
        msg = "; ".join(cm.exception.errors)
        self.assertIn("landscape[0]", msg)
        self.assertIn("could not be verified", msg)
        self.assertEqual(calls["budget"], 0)


if __name__ == "__main__":
    unittest.main()
