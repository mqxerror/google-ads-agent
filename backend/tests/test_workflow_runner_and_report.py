"""Story 13.2 — runner reliability + account-report persistence + fast signals.

Repo test style: stdlib unittest, a REAL temp SQLite from init_db(), and
scripted fakes for anything that would otherwise hit an LLM / Google Ads / the
network. No live calls anywhere.

Covers:
  A) RUNNER DECOUPLE
     - a run survives a simulated client disconnect (the subscriber stops
       tailing; the detached task still runs to completion + persists)
     - stop() cancels a running task and marks the row 'stopped'
     - sweep_zombies() flips a stale 'running' row to failed/stale (and leaves
       a fresh 'running' row alone)
  B) ACCOUNT-REPORT PERSISTENCE
     - save_latest → get_latest round-trip, latest-wins (second run overwrites)
     - empty-but-valid zero-state shape when nothing persisted
     - staleness flips past the configured threshold
  C) FAST-SIGNALS aggregator math
     - 0-conv wasted-spend sum, budget-pacing threshold, pending approvals,
       tracking-gap flag — all from stubbed local rows

Run:  cd backend && .venv/bin/python -m unittest tests.test_workflow_runner_and_report -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import unittest

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="wf-runner-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                        # noqa: E402
from app.services import account_report_store                   # noqa: E402
from app.services import fast_signals                           # noqa: E402
from app.services import workflow_runner as wr                  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


async def _insert_run(run_id: str, account_id: str, status: str, updated_at: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO workflow_runs (id, account_id, goal, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, account_id, "g", status, updated_at),
        )
        await db.commit()
    finally:
        await db.close()


async def _run_status(run_id: str) -> tuple[str, str]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT status, stop_reason FROM workflow_runs WHERE id = ?", (run_id,)
        )
        row = await cur.fetchone()
        return (row["status"], row["stop_reason"]) if row else ("", "")
    finally:
        await db.close()


# ══ A) RUNNER DECOUPLE ═════════════════════════════════════════════════


class RunnerDecouple(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig = wr.run_workflow

    def tearDown(self):
        wr.run_workflow = self._orig

    async def test_run_survives_client_disconnect(self):
        """The subscriber attaches, reads two events, then walks away (client
        disconnect). The detached task must still run to completion and write
        its terminal marker into the hub buffer."""
        acct = "acct-decouple"
        run_id = str(uuid.uuid4())
        started = asyncio.Event()
        completed = asyncio.Event()

        async def fake_workflow(**params):
            yield {"type": "workflow_start", "run_id": run_id, "mode": "campaign"}
            started.set()
            yield {"type": "phase", "phase": "plan", "status": "start"}
            # Simulate work AFTER the client has disconnected.
            await asyncio.sleep(0.05)
            yield {"type": "phase", "phase": "plan", "status": "done"}
            yield {"type": "workflow_done", "run_id": run_id, "final_output": "done"}
            completed.set()

        wr.run_workflow = fake_workflow

        rid = await wr.start(account_id=acct, goal="g")
        self.assertEqual(rid, run_id)

        # Subscribe, read just the first two events, then abandon the iterator
        # (== client closing the SSE connection mid-stream).
        seen = []
        agen = wr.subscribe(run_id)
        seen.append(await agen.__anext__())
        seen.append(await agen.__anext__())
        await agen.aclose()   # client disconnects here

        # The run must finish regardless.
        await asyncio.wait_for(completed.wait(), timeout=2.0)
        # Give the driver a tick to flush the terminal event + close the hub.
        await asyncio.sleep(0.02)

        hub = wr._hubs.get(run_id)
        self.assertIsNotNone(hub)
        types = [e["type"] for e in hub.buffer]
        self.assertIn("workflow_done", types)          # ran to completion
        self.assertTrue(hub.done.is_set())             # hub closed cleanly
        self.assertEqual(seen[0]["type"], "workflow_start")

    async def test_late_subscriber_gets_full_replay(self):
        """A viewer that attaches AFTER the run finished still receives every
        event from the replay buffer (reconnect-proof)."""
        run_id = str(uuid.uuid4())
        done = asyncio.Event()

        async def fake_workflow(**params):
            yield {"type": "workflow_start", "run_id": run_id}
            yield {"type": "workflow_done", "run_id": run_id}
            done.set()

        wr.run_workflow = fake_workflow
        await wr.start(account_id="a", goal="g")
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.02)

        replay = [e async for e in wr.subscribe(run_id)]
        self.assertEqual([e["type"] for e in replay],
                         ["workflow_start", "workflow_done"])

    async def test_stop_cancels_and_marks_stopped(self):
        acct = "acct-stop"
        run_id = str(uuid.uuid4())
        # Seed the run row the way run_workflow would, so _mark_stopped can flip it.
        await _insert_run(run_id, acct, "running",
                          datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        first = asyncio.Event()

        async def fake_workflow(**params):
            yield {"type": "workflow_start", "run_id": run_id}
            first.set()
            # Hang "forever" until cancelled by stop().
            await asyncio.sleep(30)
            yield {"type": "workflow_done", "run_id": run_id}   # never reached

        wr.run_workflow = fake_workflow
        await wr.start(account_id=acct, goal="g")
        await asyncio.wait_for(first.wait(), timeout=2.0)

        res = await wr.stop(run_id)
        self.assertEqual(res["status"], "stopped")
        status, reason = await _run_status(run_id)
        self.assertEqual(status, "stopped")
        self.assertIn("stop", (reason or "").lower())
        # Task deregistered after completion.
        self.assertNotIn(run_id, wr._tasks)

    async def test_stop_unknown_run_flips_stale_row(self):
        """stop() on a run with no active task still flips a lingering
        'running' row so the UI stops showing a zombie as active."""
        acct = "acct-stop-nostask"
        run_id = str(uuid.uuid4())
        await _insert_run(run_id, acct, "running",
                          datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        res = await wr.stop(run_id)
        self.assertEqual(res["status"], "stopped")
        status, _ = await _run_status(run_id)
        self.assertEqual(status, "stopped")


class ZombieSweeper(unittest.IsolatedAsyncioTestCase):
    async def test_sweep_flips_stale_running_leaves_fresh(self):
        acct = "acct-sweep"
        settings.WORKFLOW_MAX_RUNTIME_MINUTES = 20
        settings.WORKFLOW_STALE_MULTIPLIER = 2.0   # threshold = 40 min

        stale_id = str(uuid.uuid4())
        fresh_id = str(uuid.uuid4())
        done_id = str(uuid.uuid4())

        old = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        await _insert_run(stale_id, acct, "running", old)     # 3h old → stale
        await _insert_run(fresh_id, acct, "running", now)     # fresh → left alone
        await _insert_run(done_id, acct, "done", old)         # done → never touched

        swept = await wr.sweep_zombies()
        self.assertGreaterEqual(swept, 1)

        s_stale, r_stale = await _run_status(stale_id)
        self.assertEqual(s_stale, "failed")
        self.assertEqual(r_stale, "stale")

        s_fresh, _ = await _run_status(fresh_id)
        self.assertEqual(s_fresh, "running")   # untouched

        s_done, _ = await _run_status(done_id)
        self.assertEqual(s_done, "done")       # untouched

    async def test_sweep_reaps_the_two_known_zombies(self):
        """The two live-confirmed orphans (e898a108-…, f3b630b1-…) get swept
        on first run. Modelled with their real id prefixes."""
        acct = "acct-known-zombies"
        old = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
        z1 = "e898a108-" + uuid.uuid4().hex[:24]
        z2 = "f3b630b1-" + uuid.uuid4().hex[:24]
        await _insert_run(z1, acct, "running", old)
        await _insert_run(z2, acct, "running", old)

        await wr.sweep_zombies()
        for z in (z1, z2):
            status, reason = await _run_status(z)
            self.assertEqual(status, "failed")
            self.assertEqual(reason, "stale")


# ══ B) ACCOUNT-REPORT PERSISTENCE ══════════════════════════════════════


def _sample_report(total=120.0, parse_ok=True) -> dict:
    return {
        "mode": "account",
        "findings": [
            {"title": "Cut waste on X", "campaign_ids": ["c-hi"], "evidence": "e",
             "dollar_impact_wk": 120.0, "action_category": "search_terms",
             "recommended_action": "add negatives"},
        ],
        "total_recoverable_wk": total,
        "summary": "exec summary",
        "campaigns_audited": [{"campaign_id": "c-hi", "campaign_name": "Hi", "spend": 30.0}],
        "campaigns_excluded": [{"campaign_id": "c-lo", "campaign_name": "Lo",
                                "spend": 5.0, "reason": "cap"}],
        "parse_ok": parse_ok,
    }


class AccountReportPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_save_and_latest_lookup(self):
        acct = "acct-report-1"
        run_id = str(uuid.uuid4())
        await account_report_store.save_latest(acct, run_id, _sample_report())

        got = await account_report_store.get_latest(acct)
        self.assertTrue(got["exists"])
        self.assertEqual(got["run_id"], run_id)
        self.assertEqual(got["total_recoverable_wk"], 120.0)
        self.assertEqual(len(got["findings"]), 1)
        self.assertEqual(got["findings"][0]["action_category"], "search_terms")
        self.assertEqual(len(got["campaigns_audited"]), 1)
        self.assertTrue(got["parse_ok"])
        self.assertIsNotNone(got["generated_at"])
        self.assertIsNotNone(got["age_minutes"])
        self.assertFalse(got["is_stale"])          # just written → fresh

    async def test_latest_wins_overwrite(self):
        acct = "acct-report-2"
        run1, run2 = str(uuid.uuid4()), str(uuid.uuid4())
        await account_report_store.save_latest(acct, run1, _sample_report(total=50.0))
        await account_report_store.save_latest(acct, run2, _sample_report(total=222.0))

        got = await account_report_store.get_latest(acct)
        self.assertEqual(got["run_id"], run2)          # newest slot
        self.assertEqual(got["total_recoverable_wk"], 222.0)

        # Exactly one row per account (latest-wins, not append).
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT COUNT(*) c FROM account_reports WHERE account_id = ?", (acct,)
            )
            self.assertEqual((await cur.fetchone())["c"], 1)
        finally:
            await db.close()

    async def test_empty_zero_state_shape(self):
        got = await account_report_store.get_latest("acct-never-audited")
        self.assertFalse(got["exists"])
        self.assertEqual(got["findings"], [])
        self.assertEqual(got["total_recoverable_wk"], 0.0)
        self.assertEqual(got["campaigns_audited"], [])
        self.assertIsNone(got["generated_at"])
        self.assertTrue(got["is_stale"])           # nothing → treat as stale

    async def test_staleness_flips_past_threshold(self):
        acct = "acct-report-stale"
        run_id = str(uuid.uuid4())
        await account_report_store.save_latest(acct, run_id, _sample_report())
        # Backdate generated_at well past the stale window.
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        db = await get_db()
        try:
            await db.execute(
                "UPDATE account_reports SET generated_at = ? WHERE account_id = ?",
                (old, acct),
            )
            await db.commit()
        finally:
            await db.close()

        got = await account_report_store.get_latest(acct)
        self.assertTrue(got["is_stale"])
        self.assertGreaterEqual(got["age_hours"], 47.0)


# ══ C) FAST-SIGNALS AGGREGATOR MATH ════════════════════════════════════


async def _seed_campaign(account_id, cid, name, status, budget_daily):
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO campaigns "
            "(campaign_id, account_id, name, status, budget_micros, last_synced_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (cid, account_id, name, status, int(budget_daily * 1_000_000)),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_daily(account_id, cid, name, days_back, spend, conv):
    """One daily-metrics row `days_back` days ago."""
    d = (date.today() - timedelta(days=days_back)).isoformat()
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO campaign_daily_metrics "
            "(account_id, campaign_id, campaign_name, date, cost_micros, conversions) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, cid, name, d, int(spend * 1_000_000), conv),
        )
        await db.commit()
    finally:
        await db.close()


async def _seed_plan(account_id, cid, title, category, status):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO scheduled_plans "
            "(id, account_id, campaign_id, campaign_name, title, action_detail, "
            " action_category, mode, schedule_type, status, proposed_change) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'approval', 'once', ?, ?)",
            (str(uuid.uuid4()), account_id, cid, "C", title, "do it",
             category, status, "budget $100 -> $150"),
        )
        await db.commit()
    finally:
        await db.close()


class FastSignalsMath(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        settings.FAST_SIGNAL_WINDOW_DAYS = 7
        settings.FAST_SIGNAL_PACING_RATIO = 1.2
        settings.FAST_SIGNAL_WASTE_MIN_SPEND = 10.0

    async def test_wasted_spend_zero_conv_sum(self):
        acct = "fs-waste"
        # Waster: $70 over 7 days, 0 conv → flagged. Weekly waste == $70.
        await _seed_campaign(acct, "w1", "Waster", "ENABLED", 20.0)
        for i in range(7):
            await _seed_daily(acct, "w1", "Waster", i, 10.0, 0.0)
        # Converter: same spend but HAS conversions → NOT waste.
        await _seed_campaign(acct, "w2", "Converter", "ENABLED", 20.0)
        for i in range(7):
            await _seed_daily(acct, "w2", "Converter", i, 10.0, 1.0)
        # Tiny spender below threshold → not flagged.
        await _seed_campaign(acct, "w3", "Tiny", "ENABLED", 20.0)
        await _seed_daily(acct, "w3", "Tiny", 0, 3.0, 0.0)

        out = await fast_signals.get_signals(acct)
        waste = out["signals"]["wasted_spend"]
        self.assertEqual([w["campaign_id"] for w in waste], ["w1"])
        self.assertEqual(waste[0]["window_spend"], 70.0)
        # 7 days @ $10 → weekly-normalized == $70.
        self.assertAlmostEqual(waste[0]["dollar_impact_wk"], 70.0, places=1)

    async def test_budget_pacing_threshold(self):
        acct = "fs-pace"
        # Over-pacer: budget $10/day, spending $20/day avg (2× > 1.2×) → flagged.
        await _seed_campaign(acct, "p1", "OverPacer", "ENABLED", 10.0)
        for i in range(7):
            await _seed_daily(acct, "p1", "OverPacer", i, 20.0, 0.0)
        # On-budget: $10/day budget, $9/day spend → under 1.2× → not flagged.
        await _seed_campaign(acct, "p2", "OnBudget", "ENABLED", 10.0)
        for i in range(7):
            await _seed_daily(acct, "p2", "OnBudget", i, 9.0, 2.0)

        out = await fast_signals.get_signals(acct)
        pacing = out["signals"]["budget_pacing"]
        self.assertEqual([p["campaign_id"] for p in pacing], ["p1"])
        self.assertEqual(pacing[0]["avg_daily_spend"], 20.0)
        self.assertEqual(pacing[0]["daily_budget"], 10.0)
        # projected overspend/mo = (20-10)*30 = 300; weekly ≈ 300/4.345 ≈ 69.05
        self.assertGreater(pacing[0]["dollar_impact_wk"], 60.0)

    async def test_paused_campaigns_never_flagged(self):
        acct = "fs-paused"
        await _seed_campaign(acct, "x1", "PausedWaster", "PAUSED", 10.0)
        for i in range(7):
            await _seed_daily(acct, "x1", "PausedWaster", i, 50.0, 0.0)
        out = await fast_signals.get_signals(acct)
        self.assertEqual(out["signals"]["wasted_spend"], [])
        self.assertEqual(out["signals"]["budget_pacing"], [])

    async def test_pending_approvals_surface(self):
        acct = "fs-approvals"
        await _seed_plan(acct, "c1", "Bump budget to $150", "budget", "awaiting_approval")
        await _seed_plan(acct, "c1", "Already done", "budget", "done")   # not awaiting
        out = await fast_signals.get_signals(acct)
        pend = out["signals"]["pending_approvals"]
        self.assertEqual(len(pend), 1)
        self.assertEqual(pend[0]["title"], "Bump budget to $150")
        self.assertEqual(pend[0]["action_category"], "budget")
        self.assertIsNone(pend[0]["dollar_impact_wk"])   # not invented

    async def test_tracking_gap_flagged_for_full_window_zero_conv(self):
        acct = "fs-tracking"
        # Spends every day of the window, never a single conversion → tracking gap.
        await _seed_campaign(acct, "t1", "NoTracking", "ENABLED", 20.0)
        for i in range(7):
            await _seed_daily(acct, "t1", "NoTracking", i, 12.0, 0.0)
        out = await fast_signals.get_signals(acct)
        tracking = out["signals"]["tracking_flags"]
        self.assertEqual([t["campaign_id"] for t in tracking], ["t1"])
        self.assertEqual(tracking[0]["action_category"], "audit")
        self.assertIsNone(tracking[0]["dollar_impact_wk"])

    async def test_total_impact_and_count(self):
        acct = "fs-total"
        await _seed_campaign(acct, "w1", "Waster", "ENABLED", 100.0)  # high budget → no pacing flag
        for i in range(7):
            await _seed_daily(acct, "w1", "Waster", i, 10.0, 0.0)     # $70 waste, no pacing
        await _seed_plan(acct, "w1", "Approve me", "budget", "awaiting_approval")

        out = await fast_signals.get_signals(acct)
        # 1 waste + 1 tracking + 1 pending = 3 signals.
        self.assertEqual(out["count"], 3)
        # Only the waste contributes a derivable weekly $ ($70); pending + tracking are None.
        self.assertAlmostEqual(out["total_impact_wk"], 70.0, places=1)
        self.assertEqual(out["window_days"], 7)


if __name__ == "__main__":
    unittest.main()
