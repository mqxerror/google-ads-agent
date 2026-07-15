"""Dashboard v2.1 — Epic C / C5: external-change detection (roster diff).

Exercises `external_change` against a REAL temp SQLite (the table is created
LAZILY by the module — there is no database.py migration for it, by design; a
concurrent agent owns that file). No Google Ads calls. Proves:

  1. `_ensure_table` is idempotent (calling twice doesn't error / duplicate).
  2. `diff_and_record` detects a status change (ENABLED→PAUSED) and a budget
     change, records them with source='external'.
  3. `diff_and_record` records NOTHING when before == after (incl. normalised
     equivalents like 100 vs '100').
  4. A brand-new campaign (only in `after`) is NOT recorded as a change.
  5. `list_external_changes` returns rows newest-first.

Run:  cd backend && .venv/bin/python -m unittest tests.test_external_change -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="external-change-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import external_change           # noqa: E402

_ACCOUNT = "1112223330"


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


async def _clear() -> None:
    db = await get_db()
    try:
        await external_change._ensure_table(db)
        await db.execute("DELETE FROM external_change WHERE account_id = ?", (_ACCOUNT,))
        await db.commit()
    finally:
        await db.close()


class ExternalChangeTest(unittest.TestCase):
    def setUp(self):
        asyncio.run(_clear())

    # ── _ensure_table ────────────────────────────────────────────────

    def test_ensure_table_idempotent(self):
        async def _run():
            db = await get_db()
            try:
                # Reset the process fast-path so the DDL actually runs twice.
                external_change._ensured = False
                await external_change._ensure_table(db)
                await external_change._ensure_table(db)  # second call must be a no-op
                # Table exists + is queryable.
                cur = await db.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='external_change'"
                )
                self.assertIsNotNone(await cur.fetchone())
            finally:
                await db.close()
        asyncio.run(_run())

    # ── diff_and_record ──────────────────────────────────────────────

    def test_detects_status_and_budget_change(self):
        async def _run():
            before = {
                "111": {"status": "ENABLED", "bidding_strategy": "MAXIMIZE_CLICKS",
                        "budget_micros": 50_000_000},
            }
            after = {
                "111": {"status": "PAUSED", "bidding_strategy": "MAXIMIZE_CLICKS",
                        "budget_micros": 75_000_000},
            }
            diffs = await external_change.diff_and_record(_ACCOUNT, before, after)
            fields = sorted(d["field"] for d in diffs)
            self.assertEqual(fields, ["budget_micros", "status"])
            # Every recorded row is source='external'.
            self.assertTrue(all(d["source"] == "external" for d in diffs))

            rows = await external_change.list_external_changes(_ACCOUNT)
            self.assertEqual(len(rows), 2)
            by_field = {r["field"]: r for r in rows}
            self.assertEqual(by_field["status"]["before"], "ENABLED")
            self.assertEqual(by_field["status"]["after"], "PAUSED")
            self.assertEqual(by_field["status"]["source"], "external")
            self.assertEqual(by_field["budget_micros"]["before"], "50000000")
            self.assertEqual(by_field["budget_micros"]["after"], "75000000")
        asyncio.run(_run())

    def test_records_nothing_when_unchanged(self):
        async def _run():
            # Identical, plus a normalised-equivalent budget (100 vs '100').
            before = {
                "222": {"status": "ENABLED", "bidding_strategy": "TARGET_CPA",
                        "budget_micros": 100},
            }
            after = {
                "222": {"status": "ENABLED", "bidding_strategy": "TARGET_CPA",
                        "budget_micros": "100"},
            }
            diffs = await external_change.diff_and_record(_ACCOUNT, before, after)
            self.assertEqual(diffs, [])
            rows = await external_change.list_external_changes(_ACCOUNT)
            self.assertEqual(rows, [])
        asyncio.run(_run())

    def test_new_campaign_is_not_a_change(self):
        async def _run():
            before: dict = {}  # campaign didn't exist before
            after = {
                "333": {"status": "ENABLED", "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                        "budget_micros": 10_000_000},
            }
            diffs = await external_change.diff_and_record(_ACCOUNT, before, after)
            self.assertEqual(diffs, [])
        asyncio.run(_run())

    # ── list ordering ────────────────────────────────────────────────

    def test_list_returns_newest_first(self):
        async def _run():
            # First change (older).
            await external_change.record_external_changes(
                _ACCOUNT,
                [{"campaign_id": "444", "field": "status",
                  "before": "ENABLED", "after": "PAUSED"}],
            )
            # Ensure a strictly later detected_at than the first row.
            await asyncio.sleep(1.05)
            await external_change.record_external_changes(
                _ACCOUNT,
                [{"campaign_id": "555", "field": "budget_micros",
                  "before": "1", "after": "2"}],
            )
            rows = await external_change.list_external_changes(_ACCOUNT)
            self.assertEqual(len(rows), 2)
            # Newest (campaign 555) first.
            self.assertEqual(rows[0]["campaign_id"], "555")
            self.assertEqual(rows[1]["campaign_id"], "444")
        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
