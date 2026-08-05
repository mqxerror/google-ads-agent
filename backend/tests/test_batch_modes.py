"""Story 17.2 — generation modes (with_logo / without_logo / asset_anchored).

  * with_logo under an `allow_warned` type (pmax): base render AND composite are
    TWO ad_assets rows linked by parent_asset_id — the base is recoverable
    (FR2.1); the logo is a Pillow paste, never re-prompted.
  * with_logo under a `forbid` type (demand_gen): NO composite; the base carries
    the policy warning and the logo routes to its slot (FR2.2). Same code, only
    the campaign_type (registry data) changed — the fixture-flip test.
  * asset_anchored: the reference upload ids reach submit_image as `--image`
    flags (request spy).

All generation mocked at the client boundary — ZERO real Higgsfield credits.

Run: cd backend && .venv/bin/python -m unittest tests.test_batch_modes -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from PIL import Image

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="batch-modes-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402
from app.routers import studio  # noqa: E402
from app.services import batch_render as br  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "ad_assets").mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


async def _seed_asset(account: str, size=(200, 80)) -> str:
    """Insert a real on-disk image ad_asset (logo / reference) and return its id."""
    from app.routers.assets import ASSETS_DIR

    asset_id = str(uuid.uuid4())
    fn = f"{asset_id}.png"
    Image.new("RGBA", size, (255, 0, 0, 255)).save(ASSETS_DIR / fn)
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets (id, account_id, type, filename, url, source,
               status, created_at) VALUES (?, ?, 'image', ?, ?, 'uploaded',
               'completed', datetime('now'))""",
            (asset_id, account, fn, f"/api/assets/file/{fn}"),
        )
        await db.commit()
    finally:
        await db.close()
    return asset_id


class _FakeClient:
    last_params: dict = {}
    last_prompt: str = ""
    submit_calls: int = 0

    def __init__(self, *a, **k) -> None:
        pass

    async def upload_media(self, *, file_path):
        return {"id": "up_" + Path(file_path).stem[:6]}

    async def submit_image(self, *, model, prompt, aspect_ratio, **params):
        _FakeClient.last_params = dict(params)
        _FakeClient.last_prompt = prompt
        _FakeClient.submit_calls += 1
        return {"image_url": "https://cdn.example/x.png", "raw": [{"id": str(uuid.uuid4())}]}


async def _fake_download(*, asset_id, cdn_url):
    from app.routers.assets import ASSETS_DIR

    fn = f"{asset_id}.png"
    Image.new("RGB", (640, 640), (180, 160, 140)).save(ASSETS_DIR / fn)
    return (f"/api/assets/file/{fn}", fn, 640, 640, 1)


class ModesBase(unittest.TestCase):
    def setUp(self) -> None:
        studio._GENERATION_SEMAPHORE = asyncio.Semaphore(6)
        _FakeClient.last_params = {}
        _FakeClient.last_prompt = ""
        _FakeClient.submit_calls = 0


class WithLogo(ModesBase):
    def test_allow_warned_type_composites_two_rows_linked_by_parent(self):
        # No campaign type is allow_warned anymore (all forbid since the medallion
        # defect fix), so the composite CAPABILITY is exercised by flipping the
        # policy function — proving the data-driven path still works end-to-end.
        async def _flow():
            logo = await _seed_asset("acc-logo")
            res = await br.create_batch(
                account_id="acc-logo", art_direction="panama skyline",
                model="nano_banana_2", mode="with_logo", campaign_type="pmax",
                logo_asset_id=logo, slots=[{"slot": "square", "variants": 1}])
            batch_id = res["batch_id"]
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download), \
                    mock.patch.object(br, "_logo_overlay_policy", lambda ct: "allow_warned"):
                await br._supervise(batch_id)
            view = await br.get_batch(batch_id)
            composites = await br._read_composites(batch_id)
            return res, view, composites

        res, view, composites = _run(_flow())
        base_id = res["tiles"][0]["asset_id"]
        # progress counts the ONE requested tile, not the overlay.
        self.assertEqual(view["progress"], {"done": 1, "failed": 0, "total": 1})
        # a composite exists, linked to the base.
        self.assertIn(base_id, composites)
        self.assertEqual(composites[base_id]["parent_asset_id"], base_id)
        meta = json.loads(composites[base_id]["meta_json"])
        self.assertEqual(meta["logo_overlay"], "composited")
        # the base tile surfaces its composite in the view.
        tile = view["tiles"][0]
        self.assertEqual(tile["composite_asset_id"], composites[base_id]["id"])

    def test_forbid_type_routes_to_logo_slot_no_composite(self):
        async def _flow():
            logo = await _seed_asset("acc-dg")
            res = await br.create_batch(
                account_id="acc-dg", art_direction="greece villa",
                model="nano_banana_2", mode="with_logo", campaign_type="demand_gen",
                logo_asset_id=logo, slots=[{"slot": "square", "variants": 1}])
            batch_id = res["batch_id"]
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(batch_id)
            composites = await br._read_composites(batch_id)
            base = await br._read_child(res["tiles"][0]["asset_id"])
            return composites, base

        composites, base = _run(_flow())
        self.assertEqual(composites, {})  # forbid → no overlay
        meta = json.loads(base["meta_json"])
        self.assertEqual(meta["logo_overlay"], "routed_to_logo_slot")
        self.assertIn("dedicated logo slot", meta["warning"])


class AssetAnchored(ModesBase):
    def test_reference_ids_reach_submit_as_image_flags(self):
        async def _flow():
            ref = await _seed_asset("acc-anchor", size=(640, 640))
            res = await br.create_batch(
                account_id="acc-anchor", art_direction="hotel lobby",
                model="nano_banana_2", mode="asset_anchored",
                reference_asset_ids=[ref],
                slots=[{"slot": "landscape", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return _FakeClient.last_params

        params = _run(_flow())
        self.assertIn("image", params)          # --image reference flags passed
        self.assertTrue(params["image"])        # non-empty upload id list


class WithoutLogo(ModesBase):
    def test_default_mode_emits_no_logo_and_no_composite(self):
        async def _flow():
            res = await br.create_batch(
                account_id="acc-plain", art_direction="clean product shot",
                model="nano_banana_2", slots=[{"slot": "square", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return await br._read_composites(res["batch_id"]), _FakeClient.last_params

        composites, params = _run(_flow())
        self.assertEqual(composites, {})
        self.assertNotIn("image", params)  # no reference conditioning


class ReferencesFlowInEveryMode(ModesBase):
    """Defect (a) / fix 1: reference photos anchor SCENE tiles regardless of the
    mode selector. The maiden run chose with_logo, which silently DROPPED the
    references (empty reference_asset_ids_json in the DB) — this is the regression
    guard: refs + a logo now BOTH flow, and the scene tile gets `--image` flags."""

    def test_references_reach_submit_even_in_with_logo_mode(self):
        async def _flow():
            ref = await _seed_asset("acc-both", size=(640, 640))
            logo = await _seed_asset("acc-both", size=(256, 256))
            res = await br.create_batch(
                account_id="acc-both", art_direction="real property facade",
                model="nano_banana_2", mode="with_logo", campaign_type="demand_gen",
                logo_asset_id=logo, reference_asset_ids=[ref],
                slots=[{"slot": "landscape", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return _FakeClient.last_params

        params = _run(_flow())
        self.assertIn("image", params)     # scene tile anchored despite with_logo
        self.assertTrue(params["image"])

    def test_scene_prompt_contains_single_scene_anti_collage_clause(self):
        async def _flow():
            res = await br.create_batch(
                account_id="acc-scene",
                art_direction="3 concepts x landscape / square / portrait",
                model="nano_banana_2", campaign_type="demand_gen",
                slots=[{"slot": "landscape", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return _FakeClient.last_prompt

        prompt = _run(_flow())
        self.assertIn("SINGLE SCENE ONLY", prompt)   # defect b: no grids/mosaics
        self.assertIn("COMPOSITION FOR THIS VARIANT", prompt)  # defect e


class LogoSlotUsesRealAsset(ModesBase):
    """Defect (d) / fix 4: a logo slot with a provided logo asset is filled from
    the REAL logo file (crop/fit path), NOT an AI-generated brand impression and
    NEVER the scene brief. Generation is bypassed entirely (zero credits)."""

    def test_logo_slot_bypasses_generation_and_places_real_file(self):
        async def _flow():
            logo = await _seed_asset("acc-logoslot", size=(256, 256))
            res = await br.create_batch(
                account_id="acc-logoslot", art_direction="40s American with a family photo",
                model="nano_banana_2", mode="with_logo", campaign_type="demand_gen",
                logo_asset_id=logo, slots=[{"slot": "logos", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            tile = await br._read_child(res["tiles"][0]["asset_id"])
            return tile, _FakeClient.submit_calls

        tile, submit_calls = _run(_flow())
        self.assertEqual(submit_calls, 0)                 # NO generation call
        self.assertEqual(tile["status"], "completed")
        meta = json.loads(tile["meta_json"])
        self.assertEqual(meta["logo_source"], "asset_file")
        self.assertTrue(tile["url"])                       # a real file was placed

    def test_logo_slot_without_asset_generates_clean_mark_not_scene(self):
        async def _flow():
            res = await br.create_batch(
                account_id="acc-nologoasset",
                art_direction="40s American holding an old family photograph",
                model="nano_banana_2", campaign_type="demand_gen",
                slots=[{"slot": "logos", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return _FakeClient.last_prompt, _FakeClient.submit_calls

        prompt, submit_calls = _run(_flow())
        self.assertEqual(submit_calls, 1)                  # generated (no asset)
        self.assertIn("LOGO tile", prompt)                 # clean mark prompt
        self.assertNotIn("family photograph", prompt)      # never the scene brief


if __name__ == "__main__":
    unittest.main()
