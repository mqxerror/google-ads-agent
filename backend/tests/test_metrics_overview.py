"""Story 13.7 — period-over-period metrics overview for the homepage KPI cards.

NO live Google Ads calls and NO LLM: everything is computed from a REAL SQLite
DB (created by init_db() in a temp dir) seeded with stubbed
`campaign_daily_metrics` + `campaigns` rows. Exercises the actual schema and the
actual rollup arithmetic in app.services.metrics_store.get_overview.

Pins:
- rollup math: spend/conv/clicks summed across N campaigns × M days, account-wide
- ENABLED scoping: PAUSED / removed campaigns excluded (roster from `campaigns`,
  matching fast_signals.py — the single source of truth)
- CPA / Conv-rate null-guards: null when the denominator (conv / clicks) is 0
- delta_pct: null when the prior window is empty or its value is 0 (never a
  fabricated +100% / +inf, never a divide-by-zero)
- window vs prior-window slicing: current = [today-(n-1)..today], prior = the n
  days immediately before; rows outside both windows never leak in
- sparkline series: one entry per CURRENT-window day that carried data, ascending
- zero-state: empty account → valid shape, all values null, empty series

Run:  cd backend && .venv/bin/python -m unittest tests.test_metrics_overview -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.config import settings

# Point the app at a throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="metrics-overview-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import metrics_store            # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────


def _d(offset: int) -> str:
    """ISO date `offset` days before today (offset >= 0)."""
    return (date.today() - timedelta(days=offset)).isoformat()


async def _campaign(account_id: str, cid: str, name: str, status: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO campaigns "
            "(campaign_id, account_id, name, status, last_synced_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (cid, account_id, name, status),
        )
        await db.commit()
    finally:
        await db.close()


async def _metric(
    account_id: str, cid: str, day_offset: int,
    spend: float = 0.0, conversions: float = 0.0, clicks: int = 0,
    name: str = "C",
) -> None:
    """Insert one daily metrics row. `spend` in dollars → stored as micros."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO campaign_daily_metrics "
            "(account_id, campaign_id, campaign_name, date, "
            " cost_micros, conversions, clicks) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account_id, cid, name, _d(day_offset),
             int(round(spend * 1_000_000)), conversions, clicks),
        )
        await db.commit()
    finally:
        await db.close()


def _run(coro):
    return asyncio.run(coro)


# ── Rollup math across N campaigns / M days ───────────────────────────


class RollupMath(unittest.TestCase):
    ACCT = "acct-rollup"

    def setUp(self):
        # Two ENABLED campaigns, current 7-day window (offsets 0..6).
        _run(_campaign(self.ACCT, "c1", "One", "ENABLED"))
        _run(_campaign(self.ACCT, "c2", "Two", "ENABLED"))
        # c1: day0 $10/2conv/100clk, day1 $20/3conv/100clk
        _run(_metric(self.ACCT, "c1", 0, spend=10.0, conversions=2.0, clicks=100))
        _run(_metric(self.ACCT, "c1", 1, spend=20.0, conversions=3.0, clicks=100))
        # c2: day0 $5/1conv/50clk
        _run(_metric(self.ACCT, "c2", 0, spend=5.0, conversions=1.0, clicks=50))

    def test_totals_and_ratios_account_wide(self):
        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        m = ov["metrics"]
        # spend = 10+20+5 = 35 ; conv = 2+3+1 = 6 ; clicks = 250
        self.assertEqual(m["spend"]["value"], 35.0)
        self.assertEqual(m["conversions"]["value"], 6.0)
        # CPA = 35 / 6 = 5.833..  → 5.83
        self.assertEqual(m["cpa"]["value"], 5.83)
        # conv_rate = 6 / 250 = 0.024
        self.assertEqual(m["conv_rate"]["value"], 0.024)

    def test_days_echoed_and_window_bounds(self):
        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        self.assertEqual(ov["days"], 7)
        self.assertEqual(ov["window"]["end"], _d(0))
        self.assertEqual(ov["window"]["start"], _d(6))
        # prior window is the 7 days immediately before the current one
        self.assertEqual(ov["prev_window"]["end"], _d(7))
        self.assertEqual(ov["prev_window"]["start"], _d(13))

    def test_default_days_is_seven(self):
        ov = _run(metrics_store.get_overview(self.ACCT))
        self.assertEqual(ov["days"], 7)


# ── ENABLED scoping (PAUSED / unknown campaigns excluded) ─────────────


class EnabledScoping(unittest.TestCase):
    ACCT = "acct-scope"

    def test_paused_and_unrostered_campaigns_excluded(self):
        _run(_campaign(self.ACCT, "on", "On", "ENABLED"))
        _run(_campaign(self.ACCT, "off", "Off", "PAUSED"))
        # ENABLED contributes; PAUSED must NOT.
        _run(_metric(self.ACCT, "on", 0, spend=40.0, conversions=4.0, clicks=200))
        _run(_metric(self.ACCT, "off", 0, spend=999.0, conversions=99.0, clicks=999))
        # metrics row for a campaign that isn't in `campaigns` at all → excluded
        _run(_metric(self.ACCT, "ghost", 0, spend=500.0, conversions=50.0, clicks=500))

        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        m = ov["metrics"]
        self.assertEqual(m["spend"]["value"], 40.0)          # only "on"
        self.assertEqual(m["conversions"]["value"], 4.0)
        # sparkline reflects the same scoping (one ENABLED day)
        self.assertEqual(len(ov["series"]), 1)
        self.assertEqual(ov["series"][0]["spend"], 40.0)


# ── CPA / Conv-rate null-guards ───────────────────────────────────────


class RatioNullGuards(unittest.TestCase):
    ACCT = "acct-ratio"

    def test_cpa_null_when_zero_conversions(self):
        _run(_campaign(self.ACCT, "c", "C", "ENABLED"))
        # spend but ZERO conversions → CPA must be null, not inf / a big number
        _run(_metric(self.ACCT, "c", 0, spend=25.0, conversions=0.0, clicks=80))
        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        m = ov["metrics"]
        self.assertEqual(m["spend"]["value"], 25.0)
        self.assertEqual(m["conversions"]["value"], 0.0)
        self.assertIsNone(m["cpa"]["value"])                 # 25 / 0 → null
        # conv_rate = 0 / 80 = 0.0 (a real zero — clicks present)
        self.assertEqual(m["conv_rate"]["value"], 0.0)
        # sparkline day mirrors the guard
        self.assertIsNone(ov["series"][0]["cpa"])
        self.assertEqual(ov["series"][0]["conv_rate"], 0.0)

    def test_conv_rate_null_when_zero_clicks(self):
        _run(_campaign(self.ACCT + "b", "c", "C", "ENABLED"))
        # conversions but ZERO clicks (edge) → conv_rate null, not div-by-zero
        _run(_metric(self.ACCT + "b", "c", 0, spend=12.0, conversions=2.0, clicks=0))
        ov = _run(metrics_store.get_overview(self.ACCT + "b", days=7))
        m = ov["metrics"]
        self.assertEqual(m["cpa"]["value"], 6.0)             # 12 / 2
        self.assertIsNone(m["conv_rate"]["value"])           # 2 / 0 → null


# ── delta_pct honesty ─────────────────────────────────────────────────


class DeltaHonesty(unittest.TestCase):
    def test_delta_computed_when_prior_has_data(self):
        acct = "acct-delta-ok"
        _run(_campaign(acct, "c", "C", "ENABLED"))
        # current-window day (offset 0): $120 ; prior-window day (offset 7): $100
        _run(_metric(acct, "c", 0, spend=120.0, conversions=6.0, clicks=100))
        _run(_metric(acct, "c", 7, spend=100.0, conversions=5.0, clicks=100))
        ov = _run(metrics_store.get_overview(acct, days=7))
        sp = ov["metrics"]["spend"]
        self.assertEqual(sp["value"], 120.0)
        self.assertEqual(sp["prev_value"], 100.0)
        self.assertEqual(sp["delta_pct"], 20.0)              # (120-100)/100 = +20%
        # a decrease is negative (UI colours CPA/cost inversely, but the sign
        # here is raw and honest)
        conv = ov["metrics"]["conversions"]
        self.assertEqual(conv["delta_pct"], 20.0)            # (6-5)/5

    def test_delta_null_when_prior_window_empty(self):
        acct = "acct-delta-empty-prior"
        _run(_campaign(acct, "c", "C", "ENABLED"))
        # only a current-window row; prior window has NOTHING
        _run(_metric(acct, "c", 0, spend=50.0, conversions=5.0, clicks=100))
        ov = _run(metrics_store.get_overview(acct, days=7))
        sp = ov["metrics"]["spend"]
        self.assertEqual(sp["value"], 50.0)
        self.assertIsNone(sp["prev_value"])                  # no prior data
        self.assertIsNone(sp["delta_pct"])                   # never fabricated

    def test_delta_null_when_prior_value_is_zero(self):
        acct = "acct-delta-zero-prior"
        _run(_campaign(acct, "c", "C", "ENABLED"))
        # current: 4 conversions ; prior: spend+clicks but ZERO conversions.
        # Prior window HAS activity (so prev is not "missing") but the
        # conversions figure itself is 0 → conv delta must be null, not +inf.
        _run(_metric(acct, "c", 0, spend=40.0, conversions=4.0, clicks=100))
        _run(_metric(acct, "c", 7, spend=30.0, conversions=0.0, clicks=100))
        ov = _run(metrics_store.get_overview(acct, days=7))
        conv = ov["metrics"]["conversions"]
        self.assertEqual(conv["value"], 4.0)
        self.assertEqual(conv["prev_value"], 0.0)
        self.assertIsNone(conv["delta_pct"])                 # /0 base → null
        # spend delta IS computable off the non-zero prior spend
        self.assertAlmostEqual(ov["metrics"]["spend"]["delta_pct"], 33.3)
        # prior CPA is null (30/0) → CPA delta also null
        self.assertIsNone(ov["metrics"]["cpa"]["prev_value"])
        self.assertIsNone(ov["metrics"]["cpa"]["delta_pct"])


# ── Window vs prior-window slicing correctness ────────────────────────


class WindowSlicing(unittest.TestCase):
    ACCT = "acct-slice"

    def setUp(self):
        _run(_campaign(self.ACCT, "c", "C", "ENABLED"))
        # current window (7d): put $70 on the last day (offset 0)
        _run(_metric(self.ACCT, "c", 0, spend=70.0, conversions=7.0, clicks=100))
        # prior window: put $50 on offset 7 (the day right before current start)
        _run(_metric(self.ACCT, "c", 7, spend=50.0, conversions=5.0, clicks=100))
        # OUT OF BOTH windows: offset 14 (older than prior window) — must not leak
        _run(_metric(self.ACCT, "c", 14, spend=1000.0, conversions=100.0, clicks=999))

    def test_current_and_prior_isolated_no_leak(self):
        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        sp = ov["metrics"]["spend"]
        self.assertEqual(sp["value"], 70.0)                  # only offset 0
        self.assertEqual(sp["prev_value"], 50.0)             # only offset 7
        # the $1000 at offset 14 is outside both windows entirely
        self.assertNotIn(1000.0, [r["spend"] for r in ov["series"]])
        self.assertEqual(ov["series"][0]["date"], _d(0))

    def test_boundary_day_offset_7_belongs_to_prior_not_current(self):
        # offset 7 is exactly one day before current start (offset 6) → prior.
        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        current_dates = {r["date"] for r in ov["series"]}
        self.assertNotIn(_d(7), current_dates)               # not in current
        self.assertEqual(ov["metrics"]["spend"]["prev_value"], 50.0)  # in prior


# ── Sparkline series shape ────────────────────────────────────────────


class SeriesShape(unittest.TestCase):
    ACCT = "acct-series"

    def test_series_has_one_entry_per_current_day_with_data_ascending(self):
        _run(_campaign(self.ACCT, "c", "C", "ENABLED"))
        # 3 current-window days with data (offsets 0,2,4) — sparse is fine
        _run(_metric(self.ACCT, "c", 4, spend=10.0, conversions=1.0, clicks=40))
        _run(_metric(self.ACCT, "c", 2, spend=20.0, conversions=2.0, clicks=40))
        _run(_metric(self.ACCT, "c", 0, spend=30.0, conversions=3.0, clicks=40))
        ov = _run(metrics_store.get_overview(self.ACCT, days=7))
        self.assertEqual(len(ov["series"]), 3)               # one per day-with-data
        dates = [r["date"] for r in ov["series"]]
        self.assertEqual(dates, sorted(dates))               # ascending
        self.assertEqual(dates, [_d(4), _d(2), _d(0)])
        # each series row carries all 4 fields
        for r in ov["series"]:
            self.assertEqual(set(r), {"date", "spend", "conversions", "cpa", "conv_rate"})

    def test_series_length_never_exceeds_days(self):
        _run(_campaign(self.ACCT + "x", "c", "C", "ENABLED"))
        for off in range(5):
            _run(_metric(self.ACCT + "x", "c", off, spend=1.0, conversions=1.0, clicks=1))
        ov = _run(metrics_store.get_overview(self.ACCT + "x", days=3))
        # window is 3 days (offsets 0..2); only those 3 appear, not all 5
        self.assertEqual(len(ov["series"]), 3)
        self.assertLessEqual(len(ov["series"]), ov["days"])


# ── Zero-state honesty (empty account) ────────────────────────────────


class ZeroState(unittest.TestCase):
    def test_empty_account_valid_shape_all_nulls(self):
        ov = _run(metrics_store.get_overview("acct-nobody-home", days=7))
        self.assertEqual(ov["days"], 7)
        self.assertEqual(ov["series"], [])
        for key in ("spend", "conversions", "cpa", "conv_rate"):
            block = ov["metrics"][key]
            # values are NULL, not zeros pretending to be data
            self.assertIsNone(block["value"], key)
            self.assertIsNone(block["prev_value"], key)
            self.assertIsNone(block["delta_pct"], key)

    def test_enabled_campaign_but_no_metrics_rows_is_zero_state(self):
        acct = "acct-enabled-no-metrics"
        _run(_campaign(acct, "c", "C", "ENABLED"))   # roster present, no metrics
        ov = _run(metrics_store.get_overview(acct, days=7))
        self.assertEqual(ov["series"], [])
        self.assertIsNone(ov["metrics"]["spend"]["value"])

    def test_days_param_clamped(self):
        # non-positive / silly inputs fall back to the 7-day default
        self.assertEqual(metrics_store._clamp_days(0), 7)
        self.assertEqual(metrics_store._clamp_days(-5), 7)
        self.assertEqual(metrics_store._clamp_days(None), 7)
        self.assertEqual(metrics_store._clamp_days("bad"), 7)  # type: ignore[arg-type]
        self.assertEqual(metrics_store._clamp_days(30), 30)
        self.assertEqual(metrics_store._clamp_days(10_000), metrics_store.MAX_OVERVIEW_DAYS)


if __name__ == "__main__":
    unittest.main()
