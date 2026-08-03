"""Draft persistence — Migration V27 + boot-time interrupted sweep (Epic 15, story 15.1).

Applies migrations on a temp DB, asserts the two new tables + indexes exist with
the AD-5 column shape, schema_version == 27, idempotent re-run, and — the whole
point of the epic — that a `creative_jobs` row left `running` by a dead process
reads back `interrupted` after the startup sweep (FR4.3, NFR-R1). Repo test
style: stdlib unittest, a REAL temp SQLite from init_db(), no live calls.

Run:  cd backend && .venv/bin/python -m unittest tests.test_creative_drafts -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="creative-drafts-migration-v27-test-"))
settings.DATA_DIR = _TMP

from app.database import (  # noqa: E402
    get_db,
    init_db,
    sweep_interrupted_creative_jobs,
)


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


async def _indexes(table: str) -> list[str]:
    db = await get_db()
    try:
        cur = await db.execute(f"PRAGMA index_list({table})")
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


class MigrationV27(unittest.TestCase):
    def test_schema_version_is_27(self):
        self.assertEqual(_run(_schema_version()), 27)

    def test_creative_drafts_columns(self):
        cols = _run(_columns("creative_drafts"))
        for expected in (
            "id", "account_id", "campaign_type", "name", "bundle_json",
            "created_at", "updated_at",
        ):
            self.assertIn(expected, cols, f"creative_drafts missing {expected}")
        self.assertEqual(len(cols), 7, f"expected 7 columns, got {cols}")

    def test_creative_jobs_columns(self):
        cols = _run(_columns("creative_jobs"))
        for expected in (
            "id", "kind", "account_id", "campaign_type", "status",
            "request_json", "result_json", "error_message", "research_hash",
            "created_at", "updated_at",
        ):
            self.assertIn(expected, cols, f"creative_jobs missing {expected}")
        self.assertEqual(len(cols), 11, f"expected 11 columns, got {cols}")

    def test_indexes_exist(self):
        self.assertIn("idx_creative_drafts_scope", _run(_indexes("creative_drafts")))
        self.assertIn("idx_creative_jobs_status", _run(_indexes("creative_jobs")))

    def test_unique_scope_on_drafts(self):
        """Two drafts with the SAME (account, type, name) collide; a different
        name is fine — the row-not-singleton guarantee behind FR4.2."""
        async def _check():
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO creative_drafts (id, account_id, campaign_type, name, bundle_json) "
                    "VALUES ('d-1', 'acc-U', 'pmax', 'panama-v1', '{}')"
                )
                await db.commit()
                collided = False
                try:
                    await db.execute(
                        "INSERT INTO creative_drafts (id, account_id, campaign_type, name, bundle_json) "
                        "VALUES ('d-2', 'acc-U', 'pmax', 'panama-v1', '{}')"
                    )
                    await db.commit()
                except Exception:
                    collided = True
                # Same name, DIFFERENT type → allowed (independent row).
                await db.execute(
                    "INSERT INTO creative_drafts (id, account_id, campaign_type, name, bundle_json) "
                    "VALUES ('d-3', 'acc-U', 'demand_gen', 'panama-v1', '{}')"
                )
                await db.commit()
                return collided
            finally:
                await db.close()

        self.assertTrue(_run(_check()), "duplicate (account, type, name) should violate UNIQUE")

    def test_rerun_init_db_is_idempotent(self):
        _run(init_db())
        _run(init_db())
        self.assertEqual(_run(_schema_version()), 27)
        self.assertIn("bundle_json", _run(_columns("creative_drafts")))
        self.assertIn("request_json", _run(_columns("creative_jobs")))

    def test_startup_sweep_marks_running_jobs_interrupted(self):
        """The durability proof at the unit level: a `running` job seeded to
        simulate a process death reads back `interrupted` after the boot sweep;
        already-terminal jobs are untouched (FR4.3)."""
        async def _seed_and_sweep():
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO creative_jobs (id, kind, account_id, campaign_type, status, request_json) "
                    "VALUES ('j-run', 'draft', 'acc-S', 'pmax', 'running', '{\"brief\":\"x\"}')"
                )
                await db.execute(
                    "INSERT INTO creative_jobs (id, kind, account_id, campaign_type, status, result_json) "
                    "VALUES ('j-done', 'draft', 'acc-S', 'pmax', 'done', '{\"rows\":[]}')"
                )
                await db.commit()
            finally:
                await db.close()
            swept = await sweep_interrupted_creative_jobs()
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT id, status, request_json FROM creative_jobs WHERE id IN ('j-run', 'j-done')"
                )
                rows = {r["id"]: r for r in await cur.fetchall()}
            finally:
                await db.close()
            return swept, rows

        swept, rows = _run(_seed_and_sweep())
        self.assertGreaterEqual(swept, 1)
        self.assertEqual(rows["j-run"]["status"], "interrupted")
        # request_json survives so the wizard can offer one-click re-run.
        self.assertIn("brief", rows["j-run"]["request_json"])
        # terminal job untouched.
        self.assertEqual(rows["j-done"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
