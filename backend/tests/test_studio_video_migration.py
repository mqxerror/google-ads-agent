"""Studio video-director foundation — Migration V23 (studio redesign §6.5).

Applies migrations on a temp DB, asserts the two new tables exist with the
expected column shape, schema_version == 23, and that re-running init_db is
idempotent (no crash, still 23, tables intact). Also proves the row defaults
(consult_director / status / aspect) come back as declared. Repo test style:
stdlib unittest, a REAL temp SQLite from init_db(), no live calls.

Run:  cd backend && .venv/bin/python -m unittest tests.test_studio_video_migration -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="studio-video-migration-v23-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


async def _columns(table: str) -> list[str]:
    db = await get_db()
    try:
        cur = await db.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in await cur.fetchall()]
    finally:
        await db.close()


async def _schema_version() -> int:
    db = await get_db()
    try:
        cur = await db.execute("SELECT MAX(version) FROM schema_version")
        row = await cur.fetchone()
        return row[0] if row and row[0] else 0
    finally:
        await db.close()


class MigrationV23(unittest.TestCase):
    def test_schema_version_is_23(self):
        # Head moves as migrations are added: 24 (brief_source) → 25 (change_log).
        self.assertEqual(_run(_schema_version()), 25)

    def test_studio_video_projects_columns(self):
        cols = _run(_columns("studio_video_projects"))
        for expected in (
            "id", "account_id", "campaign_id", "conversation_id", "title",
            "brief", "model_id", "target_seconds", "aspect", "consult_director",
            "storyboard_json", "status", "asset_id", "created_at", "updated_at",
            "brief_source",  # V24 (CHANGE-1 DB)
        ):
            self.assertIn(expected, cols, f"studio_video_projects missing {expected}")
        self.assertEqual(len(cols), 16, f"expected 16 columns, got {cols}")

    def test_brand_avatars_columns(self):
        cols = _run(_columns("brand_avatars"))
        for expected in (
            "id", "account_id", "name", "soul_id", "voice_id",
            "style_notes", "created_at",
        ):
            self.assertIn(expected, cols, f"brand_avatars missing {expected}")
        self.assertEqual(len(cols), 7, f"expected 7 columns, got {cols}")

    def test_rerun_init_db_is_idempotent(self):
        """Re-running init_db on an already-migrated DB must not crash and stays at head."""
        _run(init_db())
        _run(init_db())
        self.assertEqual(_run(_schema_version()), 25)
        # Tables still intact after re-run.
        self.assertIn("consult_director", _run(_columns("studio_video_projects")))
        self.assertIn("soul_id", _run(_columns("brand_avatars")))

    def test_studio_video_projects_defaults(self):
        """Insert a row with only the NOT NULL cols set → the declared
        defaults (consult_director=1, status='drafting', aspect='16:9')
        come back."""
        async def _check():
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO studio_video_projects "
                    "(id, account_id, conversation_id, model_id, target_seconds) "
                    "VALUES ('p-def', 'acc-1', 'conv-1', 'veo3_1_lite', 30)"
                )
                await db.commit()
                cur = await db.execute(
                    "SELECT consult_director, status, aspect "
                    "FROM studio_video_projects WHERE id = 'p-def'"
                )
                return await cur.fetchone()
            finally:
                await db.close()

        row = _run(_check())
        self.assertEqual(row["consult_director"], 1)
        self.assertEqual(row["status"], "drafting")
        self.assertEqual(row["aspect"], "16:9")


if __name__ == "__main__":
    unittest.main()
