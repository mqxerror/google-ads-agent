"""Working-campaign pause protection (2026-07-27 incident fix).

Proves the gate at the ONE chokepoint without touching Google (the GAQL runner is
monkeypatched):

  1. ENABLE is never gated; non-pause tools are ignored.
  2. A WORKING campaign's PAUSE/REMOVE is BLOCKED without a grant (structured
     confirmation payload with name + last-7-day spend/conversions/CPA).
  3. A grant mints + consumes exactly once; a working campaign with a valid grant
     is allowed (and a second attempt re-blocks — the grant is gone).
  4. A grant authorizes exactly one (campaign_id, action) — never another.
  5. A NON-working campaign passes without a grant, as before.
  6. A stats-lookup FAILURE fails closed (treated as working → blocked).
  7. An expired grant is not consumable.
  8. The agent-side payload extractor pulls the JSON out of the tool-error string.

Run:  cd backend && .venv/bin/python -m pytest tests/test_pause_guard.py -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="pause-guard-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402
from app.services import pause_guard  # noqa: E402

_CUSTOMER = "7178239091"
_CAMPAIGN = "23847913167"          # MapleRoots (the campaign that got killed)
_TOOL = "campaign_update_campaign"


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _row(name: str, conversions: float, cost_micros: int):
    return SimpleNamespace(
        campaign=SimpleNamespace(name=name),
        metrics=SimpleNamespace(conversions=conversions, cost_micros=cost_micros),
    )


class PauseGuardTests(unittest.TestCase):
    def setUp(self):
        # Clear grants between tests.
        async def _clear():
            db = await get_db()
            try:
                await db.execute("DELETE FROM pause_confirmation_grants")
                await db.commit()
            finally:
                await db.close()
        asyncio.run(_clear())
        self._orig_gaql = pause_guard._run_gaql

    def tearDown(self):
        pause_guard._run_gaql = self._orig_gaql

    def _stub_working(self):
        # 3 conversions, $171 spend → $57 CPA (MapleRoots' real profile).
        pause_guard._run_gaql = lambda cid, q: [
            _row("MapleRoots — Citizenship by Descent (US)", 3.0, 171_000_000)
        ]

    def _stub_not_working(self):
        # 0 conversions, $10 spend → below both thresholds.
        pause_guard._run_gaql = lambda cid, q: [_row("Sleepy Campaign", 0.0, 10_000_000)]

    def _stub_raise(self):
        def _boom(cid, q):
            raise RuntimeError("transient API blip")
        pause_guard._run_gaql = _boom

    # ── detection ────────────────────────────────────────────────────────────
    def test_enable_is_never_gated(self):
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "ENABLED"}
        self.assertIsNone(pause_guard.is_campaign_pause_or_remove(_TOOL, args))
        self._stub_working()
        self.assertIsNone(pause_guard.check_and_gate(_TOOL, args))

    def test_non_pause_tool_ignored(self):
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "PAUSED"}
        self.assertIsNone(pause_guard.check_and_gate("budget_update_campaign_budget", args))
        self.assertIsNone(pause_guard.is_campaign_pause_or_remove("ad_group_update_ad_group", args))

    def test_pause_detected(self):
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "paused"}
        got = pause_guard.is_campaign_pause_or_remove(_TOOL, args)
        self.assertEqual(got, (_CUSTOMER, _CAMPAIGN, "PAUSED"))

    # ── the core safety invariant ──────────────────────────────────────────────
    def test_working_campaign_blocked_without_grant(self):
        self._stub_working()
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "PAUSED"}
        payload = pause_guard.check_and_gate(_TOOL, args)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["kind"], "pause_confirmation")
        self.assertEqual(payload["campaign_id"], _CAMPAIGN)
        self.assertEqual(payload["action"], "PAUSED")
        self.assertIn("MapleRoots", payload["campaign_name"])
        self.assertEqual(payload["cost"], 171.0)
        self.assertEqual(payload["conversions"], 3.0)
        self.assertEqual(payload["cpa"], 57.0)

    def test_removed_is_gated_too(self):
        self._stub_working()
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "REMOVED"}
        payload = pause_guard.check_and_gate(_TOOL, args)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["action"], "REMOVED")

    def test_non_working_campaign_passes(self):
        self._stub_not_working()
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "PAUSED"}
        self.assertIsNone(pause_guard.check_and_gate(_TOOL, args))

    def test_stats_lookup_failure_fails_closed(self):
        self._stub_raise()
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "PAUSED"}
        payload = pause_guard.check_and_gate(_TOOL, args)
        self.assertIsNotNone(payload)          # fail closed → blocked
        self.assertFalse(payload["lookup_ok"])

    # ── grants ──────────────────────────────────────────────────────────────────
    def test_grant_mint_and_consume_once(self):
        pause_guard.mint_grant(_CUSTOMER, _CAMPAIGN, "PAUSED")
        self.assertTrue(pause_guard.consume_grant(_CAMPAIGN, "PAUSED"))
        self.assertFalse(pause_guard.consume_grant(_CAMPAIGN, "PAUSED"))  # consumed

    def test_working_campaign_with_grant_allowed_then_reblocks(self):
        self._stub_working()
        args = {"customer_id": _CUSTOMER, "campaign_id": _CAMPAIGN, "status": "PAUSED"}
        pause_guard.mint_grant(_CUSTOMER, _CAMPAIGN, "PAUSED")
        self.assertIsNone(pause_guard.check_and_gate(_TOOL, args))       # grant consumed → allow
        self.assertIsNotNone(pause_guard.check_and_gate(_TOOL, args))    # gone → re-block

    def test_grant_scoped_to_exact_campaign_and_action(self):
        pause_guard.mint_grant(_CUSTOMER, _CAMPAIGN, "PAUSED")
        self.assertFalse(pause_guard.consume_grant("99999999", "PAUSED"))   # wrong campaign
        self.assertFalse(pause_guard.consume_grant(_CAMPAIGN, "REMOVED"))   # wrong action
        self.assertTrue(pause_guard.consume_grant(_CAMPAIGN, "PAUSED"))     # exact match

    def test_expired_grant_not_consumed(self):
        pause_guard.mint_grant(_CUSTOMER, _CAMPAIGN, "PAUSED", ttl_seconds=-1)
        self.assertFalse(pause_guard.consume_grant(_CAMPAIGN, "PAUSED"))

    def test_mint_rejects_bad_action(self):
        with self.assertRaises(ValueError):
            pause_guard.mint_grant(_CUSTOMER, _CAMPAIGN, "ENABLED")


class ConfirmationSurfacingTests(unittest.TestCase):
    """The agent-side extractor that turns a tool-error string into the confirm
    event the chat UI renders."""

    def test_extract_and_scan(self):
        from app.services import agent
        import json
        payload = {"kind": "pause_confirmation", "campaign_id": _CAMPAIGN,
                   "campaign_name": "MapleRoots", "action": "PAUSED", "cost": 171.0,
                   "conversions": 3.0, "cpa": 57.0}
        err = "Error executing tool: CONFIRMATION_REQUIRED:" + json.dumps(payload)
        self.assertEqual(agent._extract_confirmation_payload(err), payload)
        self.assertIsNone(agent._extract_confirmation_payload("no marker here"))

        blocks = [
            {"type": "text", "text": "ignore me"},
            {"type": "tool_result", "tool_use_id": "x",
             "content": [{"type": "text", "text": err}], "is_error": True},
        ]
        got = agent._scan_user_blocks_for_confirmation(blocks)
        self.assertEqual(got["campaign_id"], _CAMPAIGN)
        self.assertIsNone(agent._scan_user_blocks_for_confirmation(
            [{"type": "tool_result", "content": "all good"}]))


if __name__ == "__main__":
    unittest.main()
