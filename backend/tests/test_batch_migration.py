"""Story 17.1 — Migration V28 (`creative_batches` + `ad_assets` batch columns).

Proves the parent-batch table and the child columns exist EXACTLY per
architecture §5 before any scheduler is built on them (children ARE the existing
`ad_assets` job store — no second job table).

Run: cd backend && .venv/bin/python -m unittest tests.test_batch_migration -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="batch-migration-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


class MigrationV28(unittest.TestCase):
    def test_schema_is_at_least_v28(self):
        async def _flow():
            db = await get_db()
            try:
                cur = await db.execute("SELECT MAX(version) FROM schema_version")
                return (await cur.fetchone())[0]
            finally:
                await db.close()

        self.assertGreaterEqual(_run(_flow()), 28)

    def test_creative_batches_columns(self):
        async def _flow():
            db = await get_db()
            try:
                cur = await db.execute("PRAGMA table_info(creative_batches)")
                return {r[1] for r in await cur.fetchall()}
            finally:
                await db.close()

        cols = _run(_flow())
        for col in (
            "id", "account_id", "campaign_id", "art_direction", "model", "mode",
            "logo_asset_id", "reference_asset_ids_json", "slots_json", "status",
            "est_credits", "created_at",
        ):
            self.assertIn(col, cols, f"creative_batches missing column {col}")

    def test_ad_assets_gains_batch_columns(self):
        async def _flow():
            db = await get_db()
            try:
                cur = await db.execute("PRAGMA table_info(ad_assets)")
                return {r[1] for r in await cur.fetchall()}
            finally:
                await db.close()

        cols = _run(_flow())
        for col in (
            "batch_id", "slot", "variant_index", "retry_count",
            "parent_asset_id", "safe_zone_json", "meta_json",
        ):
            self.assertIn(col, cols, f"ad_assets missing batch column {col}")

    def test_batch_index_exists(self):
        async def _flow():
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='idx_ad_assets_batch'"
                )
                return await cur.fetchone()
            finally:
                await db.close()

        self.assertIsNotNone(_run(_flow()))

    def test_migration_is_idempotent(self):
        # Re-running init_db on an already-migrated DB must not raise.
        _run(init_db())
        _run(init_db())


if __name__ == "__main__":
    unittest.main()
