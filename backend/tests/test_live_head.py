"""Dashboard v2.1 — Epic B / B4 LIVE-TRUTH campaign header tests.

Exercises the `/live-head` endpoint handler (`campaign_live_head`) against a
REAL temp SQLite schema with the GoogleAdsService live-head read MOCKED — nothing
hits a live Google Ads account. Proves the B4 live-truth TTL / attribution logic:

  1. Live read succeeds → state == "live", verified_at present, no fallback.
  2. 60s micro-cache: a second call within the TTL does NOT hit Google again
     (the mocked live-head method is called EXACTLY once).
  3. Live read FAILS → state == "unverified", the roster `fallback` block is
     populated from a seeded `campaigns` row (status/bidding/budget +
     last_synced_at) — never silently serving DB as truth (RC-8).

The CacheService circuit breaker is a CLASS-level flag; each test resets it and
uses a unique account/campaign id so the 60s micro-cache and the open-circuit
state can't leak between tests.

Run:  cd backend && .venv/bin/python -m unittest tests.test_live_head -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="live-head-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                       # noqa: E402
from app.routers import campaigns as campaigns_router          # noqa: E402
from app.services.cache import CacheService                    # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class _FakeLiveOk:
    """Records call count; returns a scripted live-head payload."""

    def __init__(self, payload):
        self.calls = 0
        self.payload = payload

    async def get_campaign_live_head(self, customer_id, campaign_id):
        self.calls += 1
        return self.payload


class _FakeLiveFail:
    """Simulates a live-read failure (quota / API error / circuit)."""

    def __init__(self):
        self.calls = 0

    async def get_campaign_live_head(self, customer_id, campaign_id):
        self.calls += 1
        raise RuntimeError("simulated Google Ads failure")


async def _seed_roster(account_id, campaign_id, **cols):
    """Insert a `campaigns` roster row so the unverified fallback has data."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO campaigns
                   (campaign_id, account_id, name, status, channel,
                    bidding_strategy, budget_micros, last_synced_at,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (
                str(campaign_id), account_id,
                cols.get("name", "Fallback Campaign"),
                cols.get("status", "PAUSED"),
                cols.get("channel", "SEARCH"),
                cols.get("bidding_strategy", "TARGET_CPA"),
                cols.get("budget_micros", 42_000_000),
                cols.get("last_synced_at", "2026-07-12 08:00:00"),
            ),
        )
        await db.commit()
    finally:
        await db.close()


class LiveHeadTest(unittest.TestCase):
    def setUp(self):
        # Reset the class-level circuit breaker so a prior failure never leaks.
        CacheService._circuit_open_until = 0
        self._orig_ads = campaigns_router._ads_svc

    def tearDown(self):
        campaigns_router._ads_svc = self._orig_ads
        CacheService._circuit_open_until = 0

    def test_live_read_success(self):
        acct, cid = "acct-live", "111"
        fake = _FakeLiveOk({
            "status": "ENABLED",
            "bidding_strategy": "MAXIMIZE_CONVERSIONS",
            "budget_micros": 50_000_000,
            "campaign_type": "SEARCH",
            "name": "Alpha",
        })
        campaigns_router._ads_svc = fake

        resp = asyncio.run(campaigns_router.campaign_live_head(acct, cid))

        self.assertEqual(resp["state"], "live")
        self.assertEqual(resp["campaign_id"], cid)
        self.assertEqual(resp["status"], "ENABLED")
        self.assertEqual(resp["bidding_strategy"], "MAXIMIZE_CONVERSIONS")
        self.assertEqual(resp["budget_micros"], 50_000_000)
        self.assertEqual(resp["campaign_type"], "SEARCH")
        self.assertEqual(resp["name"], "Alpha")
        self.assertIsNotNone(resp["verified_at"])
        # verified_at must be a tz-aware ISO string.
        self.assertIn("+00:00", resp["verified_at"])
        self.assertNotIn("fallback", resp)
        self.assertEqual(fake.calls, 1)

    def test_ttl_second_call_does_not_hit_google(self):
        acct, cid = "acct-ttl", "222"
        fake = _FakeLiveOk({
            "status": "ENABLED",
            "bidding_strategy": "TARGET_SPEND",
            "budget_micros": 10_000_000,
            "campaign_type": "SEARCH",
            "name": "Beta",
        })
        campaigns_router._ads_svc = fake

        async def _run():
            r1 = await campaigns_router.campaign_live_head(acct, cid)
            r2 = await campaigns_router.campaign_live_head(acct, cid)
            return r1, r2

        r1, r2 = asyncio.run(_run())

        self.assertEqual(r1["state"], "live")
        self.assertEqual(r2["state"], "live")
        # 60s micro-cache: the live-head method is hit EXACTLY once for two
        # calls inside the TTL window.
        self.assertEqual(
            fake.calls, 1,
            "second call within 60s TTL must be served from cache, not Google",
        )
        # The cached serve carries the SAME verified_at (the original live read).
        self.assertEqual(r1["verified_at"], r2["verified_at"])

    def test_live_read_failure_returns_unverified_with_fallback(self):
        acct, cid = "acct-fail", "333"
        asyncio.run(_seed_roster(
            acct, cid,
            status="PAUSED",
            bidding_strategy="TARGET_CPA",
            budget_micros=42_000_000,
            last_synced_at="2026-07-11 14:02:00",
        ))
        fake = _FakeLiveFail()
        campaigns_router._ads_svc = fake

        resp = asyncio.run(campaigns_router.campaign_live_head(acct, cid))

        self.assertEqual(resp["state"], "unverified")
        self.assertEqual(resp["campaign_id"], cid)
        self.assertIsNone(resp["verified_at"])
        # Fallback block populated straight from the seeded roster row.
        self.assertIn("fallback", resp)
        fb = resp["fallback"]
        self.assertIsNotNone(fb)
        self.assertEqual(fb["status"], "PAUSED")
        self.assertEqual(fb["bidding_strategy"], "TARGET_CPA")
        self.assertEqual(fb["budget_micros"], 42_000_000)
        self.assertEqual(fb["last_synced_at"], "2026-07-11 14:02:00")
        # Top-level fields mirror the fallback so the UI can render either.
        self.assertEqual(resp["status"], "PAUSED")
        self.assertEqual(resp["bidding_strategy"], "TARGET_CPA")
        self.assertEqual(resp["budget_micros"], 42_000_000)

    def test_failure_without_roster_row_still_unverified(self):
        # No seeded roster row → still honest: unverified, fallback is None,
        # never a silent "looks fresh" answer.
        acct, cid = "acct-nofallback", "444"
        fake = _FakeLiveFail()
        campaigns_router._ads_svc = fake

        resp = asyncio.run(campaigns_router.campaign_live_head(acct, cid))

        self.assertEqual(resp["state"], "unverified")
        self.assertIsNone(resp["verified_at"])
        self.assertIsNone(resp["fallback"])
        self.assertIsNone(resp["status"])


class AsOfHeaderTest(unittest.TestCase):
    """B4 Task 3: the agent Layer-5 as-of header (metrics_store.format_for_agent).

    `_as_of_header` is a pure local read (roster + sync_state) — no live call —
    so we test it directly against seeded rows.
    """

    def test_as_of_header_uses_roster_and_data_through(self):
        from app.services.metrics_store import MetricsStore

        acct, cid = "acct-asof", "555"

        async def _run():
            await _seed_roster(
                acct, cid,
                status="ENABLED",
                bidding_strategy="MAXIMIZE_CONVERSIONS",
                last_synced_at="2026-07-12 09:00:00",
            )
            db = await get_db()
            try:
                await db.execute(
                    """INSERT OR REPLACE INTO sync_state
                           (account_id, domain, data_through_date)
                       VALUES (?, 'metrics', ?)""",
                    (acct, "2026-07-11"),
                )
                await db.commit()
            finally:
                await db.close()
            return await MetricsStore()._as_of_header(acct, cid)

        header = asyncio.run(_run())
        self.assertIn("AS OF", header)
        # Status + bidding come from the roster (fresh source).
        self.assertIn("ENABLED", header)
        self.assertIn("MAXIMIZE_CONVERSIONS", header)
        # Data-through date comes from the sync_state ledger.
        self.assertIn("2026-07-11", header)

    def test_as_of_header_no_data_yet(self):
        from app.services.metrics_store import MetricsStore

        # No roster row, no sync_state → still emits an honest header.
        header = asyncio.run(MetricsStore()._as_of_header("acct-empty", "999"))
        self.assertIn("AS OF", header)
        self.assertIn("no data yet", header)


if __name__ == "__main__":
    unittest.main()
