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


class NamedDraftsCRUD(unittest.TestCase):
    """Story 15.2 — the CRUD contract over the real HTTP surface (TestClient).
    DATA_DIR is the module temp DB (set at import), so these hit the V27 table."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from app.main import app
        cls.client = TestClient(app)

    def _base(self, account="acc-CRUD"):
        return f"/api/accounts/{account}/creative-drafts"

    def test_create_list_get_rename_delete(self):
        c = self.client
        # create
        r = c.post(self._base(), json={
            "name": "panama-v1", "campaign_type": "pmax",
            "bundle": {"headlines": ["Move to Panama"], "businessName": "Mercan"},
        })
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        did = d["id"]
        self.assertEqual(d["name"], "panama-v1")
        self.assertEqual(d["bundle"]["businessName"], "Mercan")

        # list (filtered by type) shows it
        r = c.get(self._base(), params={"campaign_type": "pmax"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(did, [x["id"] for x in r.json()])

        # get by id round-trips the bundle
        r = c.get(f"{self._base()}/{did}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bundle"]["headlines"], ["Move to Panama"])

        # rename
        r = c.put(f"{self._base()}/{did}", json={"name": "panama-final"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "panama-final")

        # delete
        r = c.delete(f"{self._base()}/{did}")
        self.assertEqual(r.status_code, 200)
        r = c.get(f"{self._base()}/{did}")
        self.assertEqual(r.status_code, 404)

    def test_name_collision_409(self):
        c = self.client
        c.post(self._base(), json={"name": "dup", "campaign_type": "pmax", "bundle": {}})
        r = c.post(self._base(), json={"name": "dup", "campaign_type": "pmax", "bundle": {}})
        self.assertEqual(r.status_code, 409, r.text)

    def test_second_draft_never_destroys_first(self):
        """FR4.2 core: two drafts of the same type both retrievable; deleting one
        leaves the other intact."""
        c = self.client
        a = c.post(self._base(), json={"name": "a", "campaign_type": "demand_gen",
                                       "bundle": {"headlines": ["A"]}}).json()
        b = c.post(self._base(), json={"name": "b", "campaign_type": "demand_gen",
                                       "bundle": {"headlines": ["B"]}}).json()
        c.delete(f"{self._base()}/{a['id']}")
        r = c.get(f"{self._base()}/{b['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bundle"]["headlines"], ["B"])

    def test_account_scoping(self):
        """A draft saved under account A is invisible to account B (D4)."""
        c = self.client
        made = c.post(self._base("acc-A"), json={"name": "scoped", "campaign_type": "pmax",
                                                  "bundle": {}}).json()
        r = c.get(self._base("acc-B"))
        self.assertNotIn(made["id"], [x["id"] for x in r.json()])
        # and B cannot fetch A's draft by id
        r = c.get(f"{self._base('acc-B')}/{made['id']}")
        self.assertEqual(r.status_code, 404)

    def test_put_revalidates_soft_limits_to_warnings(self):
        """PUT re-validates against the registry; over-limit is advisory (never
        blocks the save)."""
        c = self.client
        d = c.post(self._base(), json={"name": "warn", "campaign_type": "pmax",
                                       "bundle": {}}).json()
        r = c.put(f"{self._base()}/{d['id']}", json={
            "bundle": {"businessName": "z" * 40},  # over the 25-char cap
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(any("business_name" in w for w in r.json()["warnings"]))

    def test_bad_campaign_type_422(self):
        r = self.client.post(self._base(), json={"name": "x", "campaign_type": "search",
                                                 "bundle": {}})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
