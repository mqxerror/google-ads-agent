"""Story 17.4 — batch restart recovery (FR2.4 restart clause, NFR-Q1, R2).

The flagged-hardest story: reattach vs re-enqueue vs never-re-render must each be
PROVEN, not assumed. This harness seeds the DB rows a killed process would leave
(the honest "app context died mid-batch" state), then runs the SAME
``recover_running_batches`` the app lifespan runs at boot, and asserts:

  * COMPLETED tiles are never re-rendered — zero generation calls, job id intact;
  * a ``running`` tile WITH a higgsfield_job_id reattaches (``wait_for_job``);
  * ``pending`` + ``running``-without-a-job-id tiles re-enqueue (``submit_image``);
  * progress is monotonic across the restart boundary;
  * an all-terminal batch left ``running`` is finalized, never left running.

All generation mocked at the client boundary — ZERO real Higgsfield credits.

Run: cd backend && .venv/bin/python -m unittest tests.test_batch_restart -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from PIL import Image

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="batch-restart-test-"))
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


class _RecordingClient:
    submit_count = 0
    wait_calls: list = []

    def __init__(self, *a, **k) -> None:
        pass

    async def submit_image(self, *, model, prompt, aspect_ratio, **params):
        _RecordingClient.submit_count += 1
        await asyncio.sleep(0)
        return {"image_url": "https://cdn.example/new.png", "raw": [{"id": str(uuid.uuid4())}]}

    async def wait_for_job(self, *, job_id):
        _RecordingClient.wait_calls.append(job_id)
        await asyncio.sleep(0)
        return {"image_url": "https://cdn.example/reattached.png", "raw": [{"id": job_id}]}


async def _fake_download(*, asset_id, cdn_url):
    from app.routers.assets import ASSETS_DIR

    fn = f"{asset_id}.png"
    Image.new("RGB", (640, 360), (150, 150, 150)).save(ASSETS_DIR / fn)
    return (f"/api/assets/file/{fn}", fn, 640, 360, 1)


async def _seed_batch(account: str, children: list[dict], *, status="running") -> str:
    """Seed one creative_batches row + children in exact states (the DB image a
    killed process leaves behind)."""
    from app.routers.assets import ASSETS_DIR

    batch_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO creative_batches (id, account_id, campaign_type,
               art_direction, model, mode, slots_json, status, created_at)
               VALUES (?, ?, 'pmax', 'panama skyline', 'nano_banana_2',
                       'without_logo', '[]', ?, datetime('now'))""",
            (batch_id, account, status),
        )
        for i, c in enumerate(children):
            aid = str(uuid.uuid4())
            c["id"] = aid
            url = ""
            if c["status"] == "completed":
                fn = f"{aid}.png"
                Image.new("RGB", (640, 360), (10, 10, 10)).save(ASSETS_DIR / fn)
                url = f"/api/assets/file/{fn}"
            await db.execute(
                """INSERT INTO ad_assets (id, account_id, type, filename, url,
                   source, status, higgsfield_model, prompt, aspect_ratio,
                   higgsfield_job_id, batch_id, slot, variant_index, retry_count,
                   created_at)
                   VALUES (?, ?, 'image', '', ?, 'higgsfield', ?, 'nano_banana_2',
                           'panama skyline', '1:1', ?, ?, ?, ?, 0, datetime('now'))""",
                (aid, account, url, c["status"], c.get("job_id"), batch_id,
                 c.get("slot", "square"), i),
            )
        await db.commit()
    finally:
        await db.close()
    return batch_id


async def _settled(batch_id: str) -> int:
    v = await br.get_batch(batch_id)
    return v["progress"]["done"] + v["progress"]["failed"]


class RestartRecovery(unittest.TestCase):
    def setUp(self) -> None:
        studio._GENERATION_SEMAPHORE = asyncio.Semaphore(6)
        _RecordingClient.submit_count = 0
        _RecordingClient.wait_calls = []

    def test_resume_reattaches_reenqueues_and_never_rerenders_completed(self):
        async def _flow():
            batch_id = await _seed_batch("acc-restart", [
                {"status": "completed", "job_id": "done-job-1"},   # terminal — keep
                {"status": "pending"},                              # re-enqueue
                {"status": "pending"},                              # re-enqueue
                {"status": "running"},                              # no job id → re-enqueue
                {"status": "running", "job_id": "reattach-job-1"},  # reattach
            ])
            completed_before = await br._read_child(
                (await br._read_children(batch_id))[0]["id"])
            settled_before = await _settled(batch_id)

            with mock.patch.object(studio, "HiggsfieldClient", _RecordingClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br.recover_running_batches()
                tasks = list(br._SUPERVISORS)
                await asyncio.gather(*tasks, return_exceptions=True)

            completed_after = await br._read_child(completed_before["id"])
            settled_after = await _settled(batch_id)
            view = await br.get_batch(batch_id)
            return completed_before, completed_after, settled_before, settled_after, view

        before, after, s_before, s_after, view = _run(_flow())
        # completed tile untouched — job id intact, zero re-render.
        self.assertEqual(after["status"], "completed")
        self.assertEqual(after["higgsfield_job_id"], "done-job-1")
        self.assertEqual(before["higgsfield_job_id"], after["higgsfield_job_id"])
        # 3 re-enqueues (2 pending + 1 running-without-jobid), 1 reattach.
        self.assertEqual(_RecordingClient.submit_count, 3)
        self.assertEqual(_RecordingClient.wait_calls, ["reattach-job-1"])
        # progress monotonic across the boundary, batch resumes to completion.
        self.assertLessEqual(s_before, s_after)
        self.assertEqual(s_before, 1)
        self.assertEqual(view["progress"], {"done": 5, "failed": 0, "total": 5})
        self.assertEqual(view["status"], "done")

    def test_all_terminal_batch_is_finalized_never_left_running(self):
        async def _flow():
            batch_id = await _seed_batch("acc-final", [
                {"status": "completed", "job_id": "j1"},
                {"status": "failed"},
                {"status": "completed", "job_id": "j2"},
            ])
            with mock.patch.object(studio, "HiggsfieldClient", _RecordingClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                out = await br.recover_running_batches()
                tasks = list(br._SUPERVISORS)
                await asyncio.gather(*tasks, return_exceptions=True)
            return out, await br.get_batch(batch_id)

        out, view = _run(_flow())
        # zero generation calls — every child was already terminal.
        self.assertEqual(_RecordingClient.submit_count, 0)
        self.assertEqual(_RecordingClient.wait_calls, [])
        self.assertGreaterEqual(out["finalized"], 1)
        self.assertEqual(view["status"], "done_with_failures")
        self.assertEqual(view["progress"], {"done": 2, "failed": 1, "total": 3})

    def test_recovery_is_idempotent_after_finish(self):
        async def _flow():
            batch_id = await _seed_batch("acc-idem", [{"status": "pending"}])
            with mock.patch.object(studio, "HiggsfieldClient", _RecordingClient), \
                    mock.patch.object(studio, "_download_to_assets", _fake_download):
                await br.recover_running_batches()
                await asyncio.gather(*list(br._SUPERVISORS), return_exceptions=True)
                # second sweep: batch already done → no-op, zero further gen calls.
                submit_after_first = _RecordingClient.submit_count
                out2 = await br.recover_running_batches()
                await asyncio.gather(*list(br._SUPERVISORS), return_exceptions=True)
            return submit_after_first, _RecordingClient.submit_count, out2

        first, second, out2 = _run(_flow())
        self.assertEqual(first, 1)
        self.assertEqual(second, 1)           # no extra renders on the 2nd sweep
        self.assertEqual(out2["recovered"], 0)


if __name__ == "__main__":
    unittest.main()
