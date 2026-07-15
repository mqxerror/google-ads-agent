"""Dashboard v2.1 — Epic A / A4 self-heal (sync-on-read) DECISION proof.

Exercises `sync_engine.maybe_kick_sync` against hand-seeded `sync_state`
fixtures in a REAL temp SQLite schema, with `sync_account` MONKEYPATCHED to a
recorder so NOTHING hits a live Google Ads account and no real sync runs. Proves
the DECISION logic — kick vs skip — not the writer:

  1. KICKS when there is no ledger row yet (never synced).
  2. KICKS when data_through_date < yesterday and no recent attempt (stale data).
  3. KICKS when the last SUCCESS is older than the hot-sync interval.
  4. SKIPS when in_progress = 1 (single-flight — a sync is already running),
     even though the data is stale.
  5. SKIPS when last_attempt_at is < 10 min ago (stampede guard), even though
     the data is stale — the 10-min guard beats staleness.
  6. SKIPS when data is fresh (covers yesterday + recent success).
  7. When it kicks, the scheduled background task actually invokes sync_account
     (proving the fire-and-forget wiring), and it uses the hot-window day-scope.

Run:  cd backend && .venv/bin/python -m unittest tests.test_self_heal -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="self-heal-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import sync_engine              # noqa: E402

_ACCOUNT = "9998887770"


def _iso(dt: datetime) -> str:
    """SQLite-style UTC stamp (no tz suffix — matches datetime('now'))."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _minutes_ago(n: float) -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(minutes=n))


async def _seed_state(
    *,
    last_attempt_at: str | None,
    last_success_at: str | None,
    in_progress: int,
    data_through_date: str | None,
    consecutive_failures: int = 0,
    last_error: str | None = None,
) -> None:
    """Overwrite the metrics sync_state row for _ACCOUNT with an exact fixture."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM sync_state WHERE account_id = ? AND domain = 'metrics'",
            (_ACCOUNT,),
        )
        await db.execute(
            """INSERT INTO sync_state
                   (account_id, domain, last_attempt_at, last_success_at,
                    last_error, consecutive_failures, in_progress,
                    data_through_date)
               VALUES (?, 'metrics', ?, ?, ?, ?, ?, ?)""",
            (_ACCOUNT, last_attempt_at, last_success_at, last_error,
             consecutive_failures, in_progress, data_through_date),
        )
        await db.commit()
    finally:
        await db.close()


async def _clear_state() -> None:
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM sync_state WHERE account_id = ? AND domain = 'metrics'",
            (_ACCOUNT,),
        )
        await db.commit()
    finally:
        await db.close()


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class _SyncRecorder:
    """Stands in for sync_account: records calls, never touches Google."""
    def __init__(self):
        self.calls: list[tuple[str, int | None]] = []

    async def __call__(self, account_id, days=None):
        self.calls.append((account_id, days))
        return {"status": "success", "data_through_date": None}


class SelfHealDecisionTest(unittest.TestCase):
    def setUp(self):
        # Monkeypatch sync_account so NO real sync runs when a kick fires. Both
        # maybe_kick_sync's helper (_run_one_account_scoped) and the recorder
        # resolve sync_account via the module attribute, so this fully isolates.
        self._orig_sync = sync_engine.sync_account
        self.recorder = _SyncRecorder()
        sync_engine.sync_account = self.recorder
        # A known guard interval regardless of env.
        self._orig_min = settings.METRICS_SELF_HEAL_MIN_INTERVAL_MINUTES
        self._orig_hot_min = settings.METRICS_HOT_SYNC_MINUTES
        self._orig_hot_days = settings.METRICS_HOT_WINDOW_DAYS
        self._orig_enabled = settings.SYNC_ENABLED
        settings.METRICS_SELF_HEAL_MIN_INTERVAL_MINUTES = 10
        settings.METRICS_HOT_SYNC_MINUTES = 60
        settings.METRICS_HOT_WINDOW_DAYS = 3
        settings.SYNC_ENABLED = True

    def tearDown(self):
        sync_engine.sync_account = self._orig_sync
        settings.METRICS_SELF_HEAL_MIN_INTERVAL_MINUTES = self._orig_min
        settings.METRICS_HOT_SYNC_MINUTES = self._orig_hot_min
        settings.METRICS_HOT_WINDOW_DAYS = self._orig_hot_days
        settings.SYNC_ENABLED = self._orig_enabled
        asyncio.run(_clear_state())

    # ── Decision-only helper (no task scheduled) ─────────────────────

    def _decide(self) -> tuple[bool, str]:
        return asyncio.run(sync_engine._self_heal_decision(_ACCOUNT))

    def test_kicks_when_never_synced(self):
        asyncio.run(_clear_state())
        should, reason = self._decide()
        self.assertTrue(should)
        self.assertEqual(reason, "never_synced")

    def test_kicks_when_data_stale_and_no_recent_attempt(self):
        # data_through 3 days ago (< yesterday); last attempt long ago → kick.
        two_days = (date.today() - timedelta(days=3)).isoformat()
        asyncio.run(_seed_state(
            last_attempt_at=_minutes_ago(120),
            last_success_at=_minutes_ago(120),
            in_progress=0,
            data_through_date=two_days,
        ))
        should, reason = self._decide()
        self.assertTrue(should)
        self.assertEqual(reason, "data_stale")

    def test_kicks_when_last_success_aged_out(self):
        # Data covers yesterday, but last success is 3h old (> 60 min) → kick.
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        asyncio.run(_seed_state(
            last_attempt_at=_minutes_ago(180),
            last_success_at=_minutes_ago(180),
            in_progress=0,
            data_through_date=yesterday,
        ))
        should, reason = self._decide()
        self.assertTrue(should)
        self.assertEqual(reason, "success_aged")

    def test_skips_single_flight_in_progress(self):
        # Stale data BUT a sync is already running → single-flight skip.
        old = (date.today() - timedelta(days=5)).isoformat()
        asyncio.run(_seed_state(
            last_attempt_at=_minutes_ago(1),
            last_success_at=_minutes_ago(600),
            in_progress=1,
            data_through_date=old,
        ))
        should, reason = self._decide()
        self.assertFalse(should)
        self.assertEqual(reason, "in_progress")

    def test_skips_stampede_guard_recent_attempt(self):
        # Stale data, NOT in progress, but last attempt 3 min ago (< 10) → skip.
        old = (date.today() - timedelta(days=5)).isoformat()
        asyncio.run(_seed_state(
            last_attempt_at=_minutes_ago(3),
            last_success_at=_minutes_ago(3),
            in_progress=0,
            data_through_date=old,
        ))
        should, reason = self._decide()
        self.assertFalse(should)
        self.assertEqual(reason, "recent_attempt")

    def test_skips_when_fresh(self):
        # Attempt is OUTSIDE the 10-min stampede window (so the guard doesn't
        # short-circuit), success is recent (< 60 min) and data covers
        # yesterday → genuinely fresh, nothing to do.
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        asyncio.run(_seed_state(
            last_attempt_at=_minutes_ago(20),
            last_success_at=_minutes_ago(20),
            in_progress=0,
            data_through_date=yesterday,
        ))
        should, reason = self._decide()
        self.assertFalse(should)
        self.assertEqual(reason, "fresh")

    def test_stampede_guard_beats_staleness_but_not_freshness(self):
        # A recent attempt (< 10 min) short-circuits to `recent_attempt` even
        # when success is old/data stale — proving the guard runs BEFORE the
        # staleness check (documents the ordering the fresh test relies on).
        old = (date.today() - timedelta(days=4)).isoformat()
        asyncio.run(_seed_state(
            last_attempt_at=_minutes_ago(4),
            last_success_at=_minutes_ago(600),
            in_progress=0,
            data_through_date=old,
        ))
        should, reason = self._decide()
        self.assertFalse(should)
        self.assertEqual(reason, "recent_attempt")

    # ── Full maybe_kick_sync: scheduling + no-schedule wiring ────────

    def test_maybe_kick_schedules_sync_when_stale(self):
        """A kick actually schedules the background sync with the hot-window
        day-scope; a skip schedules nothing."""
        async def _run():
            two_days = (date.today() - timedelta(days=3)).isoformat()
            await _seed_state(
                last_attempt_at=_minutes_ago(120),
                last_success_at=_minutes_ago(120),
                in_progress=0,
                data_through_date=two_days,
            )
            decision = await sync_engine.maybe_kick_sync(_ACCOUNT)
            self.assertTrue(decision["kicked"])
            # Let the fire-and-forget task run.
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.recorder.calls), 1)
            acct, days = self.recorder.calls[0]
            self.assertEqual(acct, _ACCOUNT)
            self.assertEqual(days, settings.METRICS_HOT_WINDOW_DAYS)
        asyncio.run(_run())

    def test_maybe_kick_schedules_nothing_when_in_progress(self):
        async def _run():
            old = (date.today() - timedelta(days=5)).isoformat()
            await _seed_state(
                last_attempt_at=_minutes_ago(1),
                last_success_at=_minutes_ago(600),
                in_progress=1,
                data_through_date=old,
            )
            decision = await sync_engine.maybe_kick_sync(_ACCOUNT)
            self.assertFalse(decision["kicked"])
            self.assertEqual(decision["reason"], "in_progress")
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.recorder.calls), 0)
        asyncio.run(_run())

    def test_maybe_kick_respects_explicit_hot_window(self):
        """Campaign-open passes an explicit hot_window_days; it must flow to the
        scheduled sync unchanged."""
        async def _run():
            await _clear_state()  # never synced → kick
            decision = await sync_engine.maybe_kick_sync(_ACCOUNT, hot_window_days=2)
            self.assertTrue(decision["kicked"])
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.recorder.calls), 1)
            self.assertEqual(self.recorder.calls[0][1], 2)
        asyncio.run(_run())

    def test_disabled_never_kicks(self):
        async def _run():
            settings.SYNC_ENABLED = False
            await _clear_state()
            decision = await sync_engine.maybe_kick_sync(_ACCOUNT)
            self.assertFalse(decision["kicked"])
            self.assertEqual(decision["reason"], "disabled")
            await asyncio.sleep(0.05)
            self.assertEqual(len(self.recorder.calls), 0)
        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
