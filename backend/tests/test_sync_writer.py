"""Dashboard v2.1 — Epic A / A1 sync writer proof (core test).

Exercises the REWRITTEN metrics writer against a REAL temp SQLite schema with a
FAKE ads service injected — nothing hits a live Google Ads account. Proves:

  1. Rows land in `campaign_daily_metrics` with the ACTUAL columns — `date`
     (NOT `metric_date`) and `campaign_status` (NOT `status`) — populated
     correctly. This is the load-bearing column-correctness assertion.
  2. MAX(date) reflects what the fake returned.
  3. A ZERO-ROW is inserted for an ENABLED campaign on a day the fake returned
     no data ("checked, no data" != "never checked").
  4. Per-run API budget is MINIMAL: get_campaign_daily_metrics is called EXACTLY
     once, and the roster get_campaigns exactly once (≤3 API ops).
  5. The sync_state ledger records success + data_through_date.

Run:  cd backend && .venv/bin/python -m unittest tests.test_sync_writer -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="sync-writer-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                # noqa: E402
from app.services import campaigns_repo                 # noqa: E402
from app.services import sync_engine                    # noqa: E402


_TODAY = date.today()
_D0 = _TODAY.isoformat()                       # today
_D1 = (_TODAY - timedelta(days=1)).isoformat()  # yesterday

# Two enabled campaigns in the roster; the daily-metrics fake returns data for
# BOTH on yesterday but only campaign "111" on today. Campaign "222" therefore
# has NO row for today from the API → must get a zero-row.
_ACCOUNT = "1234567890"


class _FakeCampaign:
    """Minimal CampaignResponse-like object for the roster sync."""
    def __init__(self, cid, name, status="ENABLED"):
        self.id = cid
        self.name = name
        self.status = status
        self.campaign_type = "SEARCH"
        self.budget_micros = 50_000_000
        self.bidding_strategy = "MAXIMIZE_CONVERSIONS"

    def model_dump(self):
        return {
            "id": self.id, "name": self.name, "status": self.status,
            "campaign_type": self.campaign_type,
            "budget_micros": self.budget_micros,
            "bidding_strategy": self.bidding_strategy,
        }


class _FakeAds:
    """Records call counts; returns scripted campaign×day metrics + roster."""
    def __init__(self):
        self.daily_calls = 0
        self.roster_calls = 0

    async def get_campaign_daily_metrics(self, customer_id, date_from, date_to):
        self.daily_calls += 1
        return [
            {
                "campaign_id": "111", "campaign_name": "Alpha",
                "campaign_status": "ENABLED",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "budget_micros": 50_000_000, "date": _D1,
                "impressions": 1000, "clicks": 50, "cost_micros": 25_000_000,
                "conversions": 5.0,
            },
            {
                "campaign_id": "111", "campaign_name": "Alpha",
                "campaign_status": "ENABLED",
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "budget_micros": 50_000_000, "date": _D0,
                "impressions": 500, "clicks": 20, "cost_micros": 10_000_000,
                "conversions": 2.0,
            },
            {
                "campaign_id": "222", "campaign_name": "Beta",
                "campaign_status": "ENABLED",
                "bidding_strategy": "TARGET_CPA",
                "budget_micros": 30_000_000, "date": _D1,
                "impressions": 200, "clicks": 4, "cost_micros": 4_000_000,
                "conversions": 0.0,
            },
            # NOTE: no "222" row for today → zero-row expected.
        ]

    async def get_campaigns(self, customer_id, date_from=None, date_to=None):
        self.roster_calls += 1
        return [
            _FakeCampaign("111", "Alpha"),
            _FakeCampaign("222", "Beta"),
        ]


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())
    # Seed an active account so any roster read is grounded.
    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR IGNORE INTO accounts_v2 (id, name, level, is_active) "
                "VALUES (?, ?, 'client', 1)",
                (_ACCOUNT, "Test Account"),
            )
            await db.commit()
        finally:
            await db.close()
    asyncio.run(_seed())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class SyncWriterTest(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeAds()
        # Inject the fake into BOTH module-level services the writer uses.
        sync_engine._ads_svc = self.fake
        campaigns_repo._ads_svc = self.fake

    def test_writer_writes_real_columns_and_zero_rows(self):
        async def _run():
            result = await sync_engine.sync_account(_ACCOUNT, days=2)
            self.assertEqual(result["status"], "success")

            db = await get_db()
            try:
                # ── (1) Column correctness: query back `date` + `campaign_status`
                cur = await db.execute(
                    """SELECT campaign_id, date, campaign_status, impressions,
                              clicks, cost_micros, conversions, ctr, avg_cpc_micros,
                              bidding_strategy, budget_micros
                       FROM campaign_daily_metrics
                       WHERE account_id = ?
                       ORDER BY campaign_id, date""",
                    (_ACCOUNT,),
                )
                rows = [dict(r) for r in await cur.fetchall()]

                print("\n=== campaign_daily_metrics rows written ===")
                for r in rows:
                    print(
                        f"  cid={r['campaign_id']} date={r['date']} "
                        f"status={r['campaign_status']} impr={r['impressions']} "
                        f"clicks={r['clicks']} ctr={r['ctr']:.2f} "
                        f"cpc_micros={r['avg_cpc_micros']}"
                    )

                # The real row for 111 on yesterday must carry the right values.
                alpha_y = next(
                    r for r in rows if r["campaign_id"] == "111" and r["date"] == _D1
                )
                self.assertEqual(alpha_y["date"], _D1)
                self.assertEqual(alpha_y["campaign_status"], "ENABLED")
                self.assertEqual(alpha_y["impressions"], 1000)
                self.assertEqual(alpha_y["clicks"], 50)
                self.assertEqual(alpha_y["cost_micros"], 25_000_000)
                # ctr = 50/1000*100 = 5.0 ; avg_cpc = 25_000_000 // 50 = 500_000
                self.assertAlmostEqual(alpha_y["ctr"], 5.0, places=4)
                self.assertEqual(alpha_y["avg_cpc_micros"], 500_000)
                self.assertEqual(alpha_y["bidding_strategy"], "MAXIMIZE_CONVERSIONS")
                self.assertEqual(alpha_y["budget_micros"], 50_000_000)

                # ── (2) MAX(date) == today (the fake's latest date)
                cur = await db.execute(
                    "SELECT MAX(date) mx FROM campaign_daily_metrics WHERE account_id = ?",
                    (_ACCOUNT,),
                )
                mx = (await cur.fetchone())["mx"]
                print(f"MAX(date) = {mx}  (expected {_D0})")
                self.assertEqual(mx, _D0)

                # ── (3) Zero-row for ENABLED campaign 222 on TODAY (no API row)
                cur = await db.execute(
                    """SELECT campaign_id, date, campaign_status, impressions, clicks
                       FROM campaign_daily_metrics
                       WHERE account_id = ? AND campaign_id = '222' AND date = ?""",
                    (_ACCOUNT, _D0),
                )
                zero = await cur.fetchone()
                self.assertIsNotNone(zero, "expected a zero-row for enabled 222 on today")
                zero = dict(zero)
                print(
                    f"zero-row: cid={zero['campaign_id']} date={zero['date']} "
                    f"status={zero['campaign_status']} impr={zero['impressions']} "
                    f"clicks={zero['clicks']}"
                )
                self.assertEqual(zero["campaign_status"], "ENABLED")
                self.assertEqual(zero["impressions"], 0)
                self.assertEqual(zero["clicks"], 0)

                # ── (5) sync_state ledger recorded success + data_through_date
                cur = await db.execute(
                    """SELECT state_row.* FROM sync_state state_row
                       WHERE account_id = ? AND domain = 'metrics'""",
                    (_ACCOUNT,),
                )
                st = dict(await cur.fetchone())
                print(
                    f"sync_state: in_progress={st['in_progress']} "
                    f"consec_fail={st['consecutive_failures']} "
                    f"data_through={st['data_through_date']} "
                    f"success_at={'set' if st['last_success_at'] else 'None'}"
                )
                self.assertEqual(st["in_progress"], 0)
                self.assertEqual(st["consecutive_failures"], 0)
                self.assertEqual(st["data_through_date"], _D0)
                self.assertIsNotNone(st["last_success_at"])
            finally:
                await db.close()

            # ── (4) Minimal API budget: daily stream once, roster once.
            print(
                f"API ops: get_campaign_daily_metrics={self.fake.daily_calls} "
                f"get_campaigns(roster)={self.fake.roster_calls}"
            )
            self.assertEqual(
                self.fake.daily_calls, 1,
                "get_campaign_daily_metrics must be called EXACTLY once per run",
            )
            self.assertEqual(self.fake.roster_calls, 1)
            self.assertLessEqual(
                self.fake.daily_calls + self.fake.roster_calls, 3,
                "per-run API ops must be <= 3",
            )

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
