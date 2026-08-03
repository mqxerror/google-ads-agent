"""Story 17.3 — Smart ASPECT Set scheduler (FR2.3/FR2.4, NFR-Q1).

Proves the batch layer orchestrates through the EXISTING single-image runner and
semaphore — never a second render path — with:

  * ≤6 concurrent Higgsfield jobs on a 10-tile batch (instrumented);
  * MONOTONIC progress across the automatic run (terminal states never revert);
  * per-tile retry bounded by ENGINE.batch_retry_max, never re-rendering a
    completed tile;
  * one parent `creative_batches` row + N child `ad_assets` rows;
  * a completed tile passing the EXISTING exact-aspect crop (±1%).

All generation is mocked at the client boundary — ZERO real Higgsfield credits.

Run: cd backend && .venv/bin/python -m unittest tests.test_batch_render -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
import uuid
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="batch-render-test-"))
settings.DATA_DIR = _TMP

from app.database import init_db  # noqa: E402
from app.routers import studio  # noqa: E402
from app.services import batch_render as br  # noqa: E402
from app.services.creative_specs import ENGINE  # noqa: E402
from app.services.higgsfield_client import HiggsfieldError  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "ad_assets").mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


class _Concurrency:
    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    def enter(self) -> None:
        self.current += 1
        self.peak = max(self.peak, self.current)

    def leave(self) -> None:
        self.current -= 1


def _fake_client(tracker: _Concurrency, *, fail: bool = False, size=(640, 360)):
    class FakeClient:
        def __init__(self, *a, **k) -> None:
            pass

        async def submit_image(self, *, model, prompt, aspect_ratio, **params):
            tracker.enter()
            try:
                await asyncio.sleep(0.05)  # a window for waves to overlap
                if fail:
                    raise HiggsfieldError(message="mock upstream failure", code="run")
                return {"image_url": "https://cdn.example/x.png",
                        "raw": [{"id": str(uuid.uuid4())}]}
            finally:
                tracker.leave()

    return FakeClient


async def _fake_download(*, asset_id, cdn_url, size=(640, 360)):
    """Write a REAL PNG to ASSETS_DIR so downstream crop/safe-zone can read it."""
    from app.routers.assets import ASSETS_DIR

    fn = f"{asset_id}.png"
    p = ASSETS_DIR / fn
    Image.new("RGB", size, (200, 180, 160)).save(p)
    return (f"/api/assets/file/{fn}", fn, size[0], size[1], p.stat().st_size)


class SchedulerBase(unittest.TestCase):
    def setUp(self) -> None:
        # Fresh semaphore per test — Python 3.12 binds it to the loop on first
        # use, so a leftover from another asyncio.run would raise cross-loop.
        studio._GENERATION_SEMAPHORE = asyncio.Semaphore(6)


class ConcurrencyCeiling(SchedulerBase):
    def test_ten_tile_batch_never_exceeds_six_concurrent(self):
        tracker = _Concurrency()

        async def _flow():
            res = await br.create_batch(
                account_id="acc-conc", art_direction="panama sunset skyline",
                model="nano_banana_2",
                slots=[
                    {"slot": "landscape", "variants": 2},
                    {"slot": "square", "variants": 2},
                    {"slot": "portrait", "variants": 2},
                    {"slot": "tall_portrait", "variants": 2},
                    {"slot": "logos", "variants": 2},
                ],
            )
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(tracker)), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return res["batch_id"]

        batch_id = _run(_flow())
        self.assertLessEqual(tracker.peak, 6, "exceeded the 6-job semaphore ceiling")
        self.assertGreaterEqual(tracker.peak, 2, "no parallelism observed — waves not working")
        view = _run(br.get_batch(batch_id))
        self.assertEqual(view["progress"], {"done": 10, "failed": 0, "total": 10})
        self.assertEqual(view["status"], "done")


class MonotonicProgress(SchedulerBase):
    def test_progress_never_decreases(self):
        tracker = _Concurrency()

        async def _flow():
            res = await br.create_batch(
                account_id="acc-mono", art_direction="greece villa golden hour",
                model="nano_banana_2",
                slots=[
                    {"slot": "landscape", "variants": 2},
                    {"slot": "square", "variants": 2},
                    {"slot": "tall_portrait", "variants": 2},
                ],
            )
            batch_id = res["batch_id"]
            seq: list[int] = []
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(tracker)), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                task = br.start_supervisor(batch_id)
                for _ in range(400):
                    v = await br.get_batch(batch_id)
                    p = v["progress"]
                    seq.append(p["done"] + p["failed"])
                    if v["status"] in ("done", "done_with_failures"):
                        break
                    await asyncio.sleep(0.01)
                await task
            return seq, await br.get_batch(batch_id)

        seq, view = _run(_flow())
        for a, b in zip(seq, seq[1:]):
            self.assertLessEqual(a, b, f"progress reverted: {seq}")
        self.assertEqual(view["progress"]["done"], 6)
        self.assertEqual(view["status"], "done")


class ParentAndChildren(SchedulerBase):
    def test_one_parent_row_and_n_children(self):
        async def _flow():
            res = await br.create_batch(
                account_id="acc-shape", art_direction="montreal loft interior",
                model="nano_banana_2",
                slots=[{"slot": "landscape", "variants": 3}, {"slot": "square", "variants": 1}],
            )
            batch = await br._read_batch(res["batch_id"])
            children = await br._read_children(res["batch_id"])
            return res, batch, children

        res, batch, children = _run(_flow())
        self.assertEqual(len(res["tiles"]), 4)
        self.assertIsNotNone(batch)
        self.assertEqual(batch["status"], "running")
        self.assertEqual(len(children), 4)
        self.assertTrue(all(c["status"] == "pending" for c in children))
        self.assertEqual({c["slot"] for c in children}, {"landscape", "square"})


class TileCapAndValidation(SchedulerBase):
    def test_over_cap_rejected(self):
        async def _flow():
            return await br.create_batch(
                account_id="acc-cap", art_direction="x", model="nano_banana_2",
                slots=[
                    {"slot": "landscape", "variants": 20},
                    {"slot": "square", "variants": 5},
                ],
            )

        with self.assertRaises(br.BatchRenderError) as ctx:
            _run(_flow())
        self.assertIn(str(ENGINE.batch_tile_cap), str(ctx.exception))

    def test_unknown_slot_rejected(self):
        with self.assertRaises(br.BatchRenderError):
            _run(br.create_batch(
                account_id="a", art_direction="x", model="nano_banana_2",
                slots=[{"slot": "billboard", "variants": 1}]))

    def test_unknown_mode_rejected(self):
        with self.assertRaises(br.BatchRenderError):
            _run(br.create_batch(
                account_id="a", art_direction="x", model="nano_banana_2",
                mode="teleport", slots=[{"slot": "square", "variants": 1}]))


class RetryPath(SchedulerBase):
    def test_failed_tile_retries_and_completes_without_rerendering_others(self):
        fail_tracker = _Concurrency()
        ok_tracker = _Concurrency()

        async def _flow():
            res = await br.create_batch(
                account_id="acc-retry", art_direction="tunis medina rooftop",
                model="nano_banana_2",
                slots=[{"slot": "square", "variants": 1}],
            )
            batch_id = res["batch_id"]
            tile_id = res["tiles"][0]["asset_id"]
            # First run: every submit fails → tile settles 'failed', batch
            # finalizes done_with_failures.
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(fail_tracker, fail=True)), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(batch_id)
            v1 = await br.get_batch(batch_id)

            # Retry with a succeeding client.
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(ok_tracker)), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br.retry_tile(batch_id, tile_id)
                # retry starts a background supervisor — poll until it settles.
                for _ in range(400):
                    v = await br.get_batch(batch_id)
                    if v["status"] in ("done", "done_with_failures"):
                        break
                    await asyncio.sleep(0.01)
            v2 = await br.get_batch(batch_id)
            return v1, v2, tile_id

        v1, v2, tile_id = _run(_flow())
        self.assertEqual(v1["progress"], {"done": 0, "failed": 1, "total": 1})
        self.assertEqual(v1["status"], "done_with_failures")
        self.assertEqual(v2["progress"], {"done": 1, "failed": 0, "total": 1})
        self.assertEqual(v2["status"], "done")
        tile = next(t for t in v2["tiles"] if t["asset_id"] == tile_id)
        self.assertEqual(tile["retry_count"], 1)

    def test_completed_tile_cannot_be_retried(self):
        tracker = _Concurrency()

        async def _flow():
            res = await br.create_batch(
                account_id="acc-noretry", art_direction="x", model="nano_banana_2",
                slots=[{"slot": "square", "variants": 1}])
            batch_id = res["batch_id"]
            tile_id = res["tiles"][0]["asset_id"]
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(tracker)), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(batch_id)
            return batch_id, tile_id

        batch_id, tile_id = _run(_flow())
        with self.assertRaises(br.BatchRenderError):
            _run(br.retry_tile(batch_id, tile_id))


class SafeZoneFlagStored(SchedulerBase):
    def test_completed_tile_gets_safe_zone_verdict(self):
        tracker = _Concurrency()

        async def _flow():
            res = await br.create_batch(
                account_id="acc-sz", art_direction="subject at frame edge",
                model="nano_banana_2",
                slots=[{"slot": "tall_portrait", "variants": 1}])
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(tracker)), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br._supervise(res["batch_id"])
            return await br.get_batch(res["batch_id"])

        view = _run(_flow())
        tile = view["tiles"][0]
        self.assertIsNotNone(tile["safe_zone"], "safe-zone verdict not stored at completion")
        self.assertEqual(tile["safe_zone"]["slot"], "tall_portrait")
        self.assertIn("tall_portrait", tile["safe_zone"]["slots"])


class CreditPreflight(SchedulerBase):
    def test_catalog_image_models_carry_numeric_est_credits(self):
        from app.services import model_catalog
        for mid in ("nano_banana_2", "gpt_image_2", "nano_banana"):
            entry = model_catalog.get_model(mid)
            self.assertIsInstance(entry.get("est_credits"), int)
            self.assertGreater(entry["est_credits"], 0)

    def test_estimate_scales_with_tiles(self):
        per = br.estimate_credits("nano_banana_2", 1)
        self.assertEqual(br.estimate_credits("nano_banana_2", 10), per * 10)

    def test_models_endpoint_surfaces_est_credits(self):
        # The batch preflight reads est_credits off /studio/models — the response
        # model must not strip it (live-smoke regression, 17.6).
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as client:
            body = client.get("/api/studio/models?kind=image").json()
        by_id = {m["id"]: m.get("est_credits") for m in body["models"]}
        self.assertIsInstance(by_id.get("nano_banana_2"), int)
        self.assertGreater(by_id["nano_banana_2"], 0)

    def test_est_credits_recorded_on_batch_row(self):
        async def _flow():
            res = await br.create_batch(
                account_id="acc-est", art_direction="x", model="nano_banana_2",
                slots=[{"slot": "square", "variants": 3}])
            batch = await br._read_batch(res["batch_id"])
            return res["est_credits"], batch["est_credits"]

        resp_est, row_est = _run(_flow())
        self.assertEqual(resp_est, row_est)
        self.assertEqual(resp_est, br.estimate_credits("nano_banana_2", 3))


class AutoAssignExactAspect(SchedulerBase):
    def test_completed_landscape_tile_crops_to_1_91_within_tolerance(self):
        from google_ads.services.campaign.creative_images import (
            fit_image_for_slot, ASPECT_TOLERANCE,
        )
        tracker = _Concurrency()

        async def _flow():
            res = await br.create_batch(
                account_id="acc-fit", art_direction="panama city waterfront",
                model="nano_banana_2",
                slots=[{"slot": "landscape", "variants": 1}])
            batch_id = res["batch_id"]
            with mock.patch.object(studio, "HiggsfieldClient", _fake_client(tracker)), \
                    mock.patch.object(studio, "_download_to_assets",
                                      lambda **k: _fake_download(size=(1280, 720), **k)):
                await br._supervise(batch_id)
            child = (await br._read_children(batch_id))[0]
            return child

        child = _run(_flow())
        from app.routers.assets import ASSETS_DIR
        path = ASSETS_DIR / f"{child['id']}.png"
        fitted = fit_image_for_slot(path, "landscape", "image/png")
        self.assertIsNotNone(fitted, "16:9 tile should be cropped to 1.91:1")
        im = Image.open(BytesIO(fitted[0]))
        w, h = im.size
        self.assertLessEqual(abs((w / h) - 1.91), 1.91 * ASPECT_TOLERANCE)


if __name__ == "__main__":
    unittest.main()
