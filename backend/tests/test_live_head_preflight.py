"""Dashboard v2.1 — B4 approval pre-flight LIVE-READ tests.

Exercises `scheduler._live_preread_suffix` — the tiny live control-plane read
run BEFORE an approval-gated plan proposes OR applies a change, so the diff the
agent quotes is against LIVE account-truth, not the roster cache (PART 2 / B4).

Covers:
  1. Live read succeeds → the instruction suffix carries the LIVE status /
     bidding / budget values, and tells the agent to diff against them.
  2. Live read FAILS (quota / circuit / API error) → the plan is NOT blocked;
     the suffix degrades to a "live pre-read unavailable" note.
  3. Account-scoped plan (no campaign_id) → no live call is attempted, empty
     suffix (there is no single campaign control-plane to read).

`get_campaign_live_head` is MOCKED throughout — nothing hits a live Google Ads
account. We monkeypatch `GoogleAdsService` inside `app.services.google_ads`
because `_live_preread_suffix` imports it lazily at call time.

Run:  cd backend && .venv/bin/python -m unittest tests.test_live_head_preflight -v
"""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from app.services import scheduler


class _FakeAdsOk:
    """A GoogleAdsService stand-in whose live-head read returns a scripted payload."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def get_campaign_live_head(self, account_id, campaign_id):
        self.calls += 1
        return self.payload


class _FakeAdsFail:
    """A GoogleAdsService stand-in whose live-head read raises (quota / circuit)."""

    def __init__(self):
        self.calls = 0

    async def get_campaign_live_head(self, account_id, campaign_id):
        self.calls += 1
        raise RuntimeError("simulated Google Ads failure")


def _plan(**over) -> dict:
    base = {
        "id": "plan-1",
        "account_id": "acct-1",
        "campaign_id": "555",
        "campaign_name": "Greece Plan B",
        "action_detail": "raise daily budget to $150",
        "mode": "approval",
    }
    base.update(over)
    return base


class LivePrereadTest(unittest.TestCase):
    def test_live_read_success_injects_live_values(self):
        fake = _FakeAdsOk({
            "status": "PAUSED",
            "bidding_strategy": "TARGET_SPEND",
            "budget_micros": 100_000_000,
            "campaign_type": "SEARCH",
            "name": "Greece Plan B",
        })
        with mock.patch(
            "app.services.google_ads.GoogleAdsService", return_value=fake
        ):
            suffix = asyncio.run(scheduler._live_preread_suffix(_plan()))

        self.assertEqual(fake.calls, 1)
        # The suffix carries the LIVE control-plane values, verbatim.
        self.assertIn("Current LIVE state", suffix)
        self.assertIn("status=PAUSED", suffix)
        self.assertIn("bidding=TARGET_SPEND", suffix)
        self.assertIn("$100.00/day", suffix)
        # And it steers the agent to diff against those live values.
        self.assertIn("not cached data", suffix)

    def test_live_read_failure_does_not_block(self):
        fake = _FakeAdsFail()
        with mock.patch(
            "app.services.google_ads.GoogleAdsService", return_value=fake
        ):
            suffix = asyncio.run(scheduler._live_preread_suffix(_plan()))

        # The read was attempted, failed, and we DEGRADED — no exception bubbles.
        self.assertEqual(fake.calls, 1)
        self.assertIn("Live pre-read unavailable", suffix)
        # It must never leak fabricated live values on the failure path.
        self.assertNotIn("Current LIVE state", suffix)

    def test_live_read_none_result_degrades_gracefully(self):
        # A None return (campaign id matched no row) is a non-exception "no data"
        # — still degrade to the unavailable note, never block.
        fake = _FakeAdsOk(None)
        with mock.patch(
            "app.services.google_ads.GoogleAdsService", return_value=fake
        ):
            suffix = asyncio.run(scheduler._live_preread_suffix(_plan()))

        self.assertEqual(fake.calls, 1)
        self.assertIn("Live pre-read unavailable", suffix)

    def test_account_scoped_plan_skips_live_call(self):
        # No campaign binding → no single control-plane to read; do not call Google.
        fake = _FakeAdsOk({"status": "ENABLED"})
        with mock.patch(
            "app.services.google_ads.GoogleAdsService", return_value=fake
        ):
            suffix = asyncio.run(
                scheduler._live_preread_suffix(
                    _plan(campaign_id=None, campaign_name=None)
                )
            )

        self.assertEqual(suffix, "")
        self.assertEqual(fake.calls, 0)

    def test_missing_budget_micros_renders_unknown(self):
        # A live payload without a numeric budget must not crash the formatter.
        fake = _FakeAdsOk({
            "status": "ENABLED",
            "bidding_strategy": "MAXIMIZE_CONVERSIONS",
            "budget_micros": None,
        })
        with mock.patch(
            "app.services.google_ads.GoogleAdsService", return_value=fake
        ):
            suffix = asyncio.run(scheduler._live_preread_suffix(_plan()))

        self.assertIn("status=ENABLED", suffix)
        self.assertIn("budget=unknown", suffix)


if __name__ == "__main__":
    unittest.main()
