"""Video Director router CRUD — projects + brand avatars.

Calls the router endpoint functions directly with a REAL temp SQLite (no
TestClient — matches the repo's function-level test style). Covers:

  project: create (row + a conversation row) → get → patch storyboard_json
           → get reflects it; patch campaign_id change spawns a NEW conversation
           while the old conversation row survives.
  avatar:  create → list (contains it) → get → delete → get 404.

Repo test style: stdlib unittest, REAL temp SQLite from init_db(), no live calls.

Run: cd backend && .venv/bin/python -m unittest tests.test_video_director_crud -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="video-director-crud-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.routers import video_director as vdr      # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


async def _conversation_exists(conv_id: str) -> bool:
    db = await get_db()
    try:
        cur = await db.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,))
        return (await cur.fetchone()) is not None
    finally:
        await db.close()


class ProjectCrud(unittest.TestCase):

    def test_create_get_patch_and_relink(self):
        # ── create → row + a conversation ─────────────────────────────
        created = _run(vdr.create_video_project(vdr.VideoProjectCreate(
            account_id="acct-1", campaign_id="camp-A", campaign_name="Camp A",
            title="Panama 30s", brief="A video.", model_id="veo3_1",
            target_seconds=30, aspect="16:9",
        )))
        pid = created["id"]
        conv1 = created["conversation_id"]
        self.assertTrue(_run(_conversation_exists(conv1)))
        self.assertEqual(created["consult_director"], 1)  # §13 default: ON when linked

        # ── get ───────────────────────────────────────────────────────
        got = _run(vdr.get_video_project(pid))
        self.assertEqual(got["id"], pid)

        # ── patch storyboard_json (dict) → get reflects it ────────────
        sb = {"scenes": [{"n": 1, "duration": 8}], "vo_full": "", "music_mood": "",
              "title": "X"}
        _run(vdr.patch_video_project(pid, vdr.VideoProjectPatch(storyboard_json=sb)))
        got2 = _run(vdr.get_video_project(pid))
        self.assertEqual(got2["storyboard_json"]["scenes"][0]["duration"], 8)

        # ── re-link to a DIFFERENT campaign → NEW conversation, old survives ─
        relinked = _run(vdr.patch_video_project(
            pid, vdr.VideoProjectPatch(campaign_id="camp-B")))
        conv2 = relinked["conversation_id"]
        self.assertNotEqual(conv2, conv1)
        self.assertTrue(_run(_conversation_exists(conv2)))
        self.assertTrue(_run(_conversation_exists(conv1)))  # old intact, never rebinds
        self.assertEqual(relinked["campaign_id"], "camp-B")

    def test_unlinked_project_consult_defaults_off(self):
        created = _run(vdr.create_video_project(vdr.VideoProjectCreate(
            account_id="acct-1", model_id="kling3_0", target_seconds=15,
        )))
        self.assertEqual(created["consult_director"], 0)  # unlinked → OFF

    def test_get_missing_project_404(self):
        with self.assertRaises(HTTPException) as ctx:
            _run(vdr.get_video_project("nope"))
        self.assertEqual(ctx.exception.status_code, 404)


class BrandAvatarCrud(unittest.TestCase):

    def test_create_list_get_delete_roundtrip(self):
        created = _run(vdr.create_brand_avatar(vdr.BrandAvatarCreate(
            account_id="acct-2", name="Brand Face", soul_id="soul-1",
            voice_id="voice-1", style_notes="warm",
        )))
        aid = created["id"]
        self.assertEqual(created["name"], "Brand Face")

        listed = _run(vdr.list_brand_avatars("acct-2"))
        self.assertIn(aid, [a["id"] for a in listed])

        got = _run(vdr.get_brand_avatar(aid))
        self.assertEqual(got["soul_id"], "soul-1")

        _run(vdr.delete_brand_avatar(aid))
        with self.assertRaises(HTTPException) as ctx:
            _run(vdr.get_brand_avatar(aid))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_patch_avatar(self):
        created = _run(vdr.create_brand_avatar(vdr.BrandAvatarCreate(
            account_id="acct-2", name="Original",
        )))
        aid = created["id"]
        updated = _run(vdr.patch_brand_avatar(aid, vdr.BrandAvatarPatch(name="Renamed")))
        self.assertEqual(updated["name"], "Renamed")


if __name__ == "__main__":
    unittest.main()
