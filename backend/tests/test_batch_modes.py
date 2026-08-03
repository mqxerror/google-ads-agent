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

    def __init__(self, *a, **k) -> None:
        pass

    async def upload_media(self, *, file_path):
        return {"id": "up_" + Path(file_path).stem[:6]}

    async def submit_image(self, *, model, prompt, aspect_ratio, **params):
        _FakeClient.last_params = dict(params)
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


class WithLogo(ModesBase):
    def test_allow_warned_type_composites_two_rows_linked_by_parent(self):
        async def _flow():
            logo = await _seed_asset("acc-logo")
            res = await br.create_batch(
                account_id="acc-logo", art_direction="panama skyline",
                model="nano_banana_2", mode="with_logo", campaign_type="pmax",
                logo_asset_id=logo, slots=[{"slot": "square", "variants": 1}])
            batch_id = res["batch_id"]
            with mock.patch.object(studio, "HiggsfieldClient", _FakeClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
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


if __name__ == "__main__":
    unittest.main()
