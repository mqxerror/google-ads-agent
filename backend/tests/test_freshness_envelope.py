"""Dashboard v2.1 — Epic A / A3 freshness envelope unit tests.

Drives `compute_freshness` against `sync_state` fixtures inserted directly into
a REAL temp SQLite (no ads service, no scheduler). Covers every state:
fresh / syncing / stale / error / never-checked, plus age_minutes correctness.

Run:  cd backend && .venv/bin/python -m unittest tests.test_freshness_envelope -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="freshness-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                # noqa: E402
from app.services.freshness import compute_freshness    # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _iso_minutes_ago(minutes: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


async def _upsert(account_id, **cols):
    db = await get_db()
    try:
        keys = ["account_id", "domain"] + list(cols.keys())
        vals = [account_id, "metrics"] + list(cols.values())
        placeholders = ",".join("?" for _ in keys)
        await db.execute(
            f"INSERT OR REPLACE INTO sync_state ({','.join(keys)}) "
            f"VALUES ({placeholders})",
            vals,
        )
        await db.commit()
    finally:
        await db.close()


class FreshnessEnvelopeTest(unittest.TestCase):
    def test_never_checked_is_stale(self):
        env = asyncio.run(compute_freshness("no-such-account"))
        self.assertEqual(env["state"], "stale")
        self.assertIsNone(env["data_through_date"])
        self.assertIsNone(env["last_success_at"])
        self.assertIsNone(env["age_minutes"])

    def test_fresh(self):
        acct = "acct-fresh"
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        asyncio.run(_upsert(
            acct,
            last_success_at=_iso_minutes_ago(10),
            data_through_date=yesterday,
            consecutive_failures=0,
            in_progress=0,
        ))
        env = asyncio.run(compute_freshness(acct))
        self.assertEqual(env["state"], "fresh")
        self.assertIsNotNone(env["age_minutes"])
        self.assertTrue(9 <= env["age_minutes"] <= 12)  # ~10 min

    def test_syncing_wins_even_if_data_is_fresh(self):
        acct = "acct-syncing"
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        asyncio.run(_upsert(
            acct,
            last_success_at=_iso_minutes_ago(5),
            data_through_date=yesterday,
            in_progress=1,
        ))
        env = asyncio.run(compute_freshness(acct))
        self.assertEqual(env["state"], "syncing")

    def test_stale_when_success_is_old(self):
        acct = "acct-old"
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        # Covered date is fine, but the success is 200 min old (> 90) → stale.
        asyncio.run(_upsert(
            acct,
            last_success_at=_iso_minutes_ago(200),
            data_through_date=yesterday,
            consecutive_failures=0,
            in_progress=0,
        ))
        env = asyncio.run(compute_freshness(acct))
        self.assertEqual(env["state"], "stale")

    def test_stale_when_data_lags(self):
        acct = "acct-lag"
        old_date = (date.today() - timedelta(days=5)).isoformat()
        asyncio.run(_upsert(
            acct,
            last_success_at=_iso_minutes_ago(5),
            data_through_date=old_date,   # data only through 5 days ago
            consecutive_failures=0,
            in_progress=0,
        ))
        env = asyncio.run(compute_freshness(acct))
        self.assertEqual(env["state"], "stale")

    def test_error_state_carries_detail(self):
        acct = "acct-error"
        asyncio.run(_upsert(
            acct,
            last_attempt_at=_iso_minutes_ago(2),
            last_success_at=None,
            last_error="quota exceeded",
            consecutive_failures=3,
            in_progress=0,
        ))
        env = asyncio.run(compute_freshness(acct))
        self.assertEqual(env["state"], "error")
        self.assertEqual(env["detail"], "quota exceeded")
        self.assertIsNone(env["age_minutes"])  # never succeeded

    def test_error_after_stale_success(self):
        # A once-fresh account that now fails: last success old + failures>0.
        acct = "acct-error2"
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        asyncio.run(_upsert(
            acct,
            last_success_at=_iso_minutes_ago(500),
            data_through_date=yesterday,
            last_error="timeout",
            consecutive_failures=2,
            in_progress=0,
        ))
        env = asyncio.run(compute_freshness(acct))
        self.assertEqual(env["state"], "error")
        self.assertEqual(env["detail"], "timeout")


if __name__ == "__main__":
    unittest.main()
