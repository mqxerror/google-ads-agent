"""Story 13.4 — "Weekly account audit" Scheduled Plans ritual (auto lane).

Repo test style: stdlib unittest, a REAL temp SQLite from init_db(), and a
scripted fake for the workflow runner so NOTHING hits an LLM / Google Ads / the
network. The runner is stubbed at `app.services.workflow_runner.start` (the
scheduler imports it lazily inside `_run_account_audit`, so patching the module
attribute intercepts the real launch). No live workflow ever fires here.

Covers the four contract points:
  A) DISPATCH — firing an account-scoped `audit` plan calls the runner with
     `campaign_id=None` (+ the plan's account, weekly timeframe), NOT a
     per-campaign chat turn. On completion the plan re-arms (recurring).
  B) IDEMPOTENCY — `POST /api/plans/account-audit` seeds at most ONE active
     ritual per account; a second call returns the existing plan.
  C) RECURRING RE-ARM — after a fire, next_run_at advances to the next weekly
     slot and status returns to 'scheduled'.
  D) AUTO-LANE — `audit` classifies AUTO (never approval-gated); a campaign-
     scoped `audit` plan is NOT treated as the account ritual.

Run:  cd backend && .venv/bin/python -m unittest tests.test_account_audit_ritual -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="audit-ritual-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                          # noqa: E402
from app.routers import plans as plans_router                     # noqa: E402
from app.services import scheduler                                # noqa: E402
from app.services import workflow_runner                          # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class _FakeRunner:
    """Records every `start(**params)` call and returns a canned run_id — the
    stand-in for launching the account-wide workflow, so no real run fires."""

    def __init__(self, run_id: str = "run-fake-1"):
        self.run_id = run_id
        self.calls: list[dict] = []

    async def start(self, **params):
        self.calls.append(params)
        return self.run_id


async def _seed_plan(**over) -> dict:
    """Insert a scheduled_plans row directly (bypasses the API) and return it."""
    pid = over.get("id") or str(uuid.uuid4())
    fields = {
        "id": pid,
        "account_id": "acct-A",
        "campaign_id": None,
        "campaign_name": None,
        "title": "Weekly account audit",
        "action_detail": "Run the account-wide Team Audit.",
        "action_category": "audit",
        "mode": "auto",
        "schedule_type": "recurring",
        "recurrence": scheduler.WEEKLY_AUDIT_RECURRENCE,
        "status": "scheduled",
        "next_run_at": None,
    }
    fields.update(over)
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO scheduled_plans (id, account_id, campaign_id, campaign_name, "
            "title, action_detail, action_category, mode, schedule_type, recurrence, "
            "status, next_run_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (fields["id"], fields["account_id"], fields["campaign_id"],
             fields["campaign_name"], fields["title"], fields["action_detail"],
             fields["action_category"], fields["mode"], fields["schedule_type"],
             fields["recurrence"], fields["status"], fields["next_run_at"]),
        )
        await db.commit()
    finally:
        await db.close()
    return await scheduler.get_plan(pid)


# ══ A) DISPATCH — account audit fires the runner with campaign_id=None ══════


class AccountAuditDispatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig = workflow_runner.start
        self.fake = _FakeRunner()
        workflow_runner.start = self.fake.start

    def tearDown(self):
        workflow_runner.start = self._orig

    async def test_run_account_audit_calls_runner_account_wide(self):
        """The ritual action dispatches to the runner with campaign_id=None,
        the plan's account, and the weekly timeframe — a stubbed launch, never
        a per-campaign chat turn."""
        plan = await _seed_plan(account_id="acct-dispatch")
        text, cost = await scheduler._run_account_audit(plan)

        self.assertEqual(len(self.fake.calls), 1)
        params = self.fake.calls[0]
        self.assertIsNone(params["campaign_id"])          # account-wide
        self.assertIsNone(params["campaign_name"])
        self.assertEqual(params["account_id"], "acct-dispatch")
        self.assertEqual(params["timeframe"], "weekly")
        self.assertIn("account", params["goal"].lower())
        self.assertEqual(cost, 0.0)                        # scheduler doesn't bill; the run does
        self.assertIn(self.fake.run_id, text)

    async def test_fire_routes_account_audit_to_runner_not_chat(self):
        """`_fire` sends an account-scoped audit plan down the runner path (not
        `_run_agent`), marks the plan done+re-armed, and records a done run."""
        # Guard: if the audit ever fell through to _run_agent, this fake would
        # be hit and the test would fail loudly instead of hitting the LLM.
        orig_run_agent = scheduler._run_agent

        async def _boom(*a, **k):
            raise AssertionError("account audit must NOT go through _run_agent")

        scheduler._run_agent = _boom
        try:
            plan = await _seed_plan(
                account_id="acct-fire",
                next_run_at=(scheduler._now() - timedelta(minutes=1)).isoformat(sep=" ", timespec="seconds"),
            )
            await scheduler._fire(plan)
        finally:
            scheduler._run_agent = orig_run_agent

        self.assertEqual(len(self.fake.calls), 1)
        self.assertIsNone(self.fake.calls[0]["campaign_id"])

        refreshed = await scheduler.get_plan(plan["id"])
        self.assertEqual(refreshed["status"], "scheduled")   # recurring → re-armed
        self.assertEqual(refreshed["run_count"], 1)

        # A scheduled_plan_run recorded 'done'.
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT status FROM scheduled_plan_runs WHERE plan_id = ? "
                "ORDER BY started_at DESC LIMIT 1", (plan["id"],))
            self.assertEqual((await cur.fetchone())["status"], "done")
        finally:
            await db.close()

    async def test_campaign_scoped_audit_is_not_the_ritual(self):
        """A campaign-bound `audit` plan is a normal per-campaign turn — it must
        NOT trigger the account-wide runner path."""
        plan = await _seed_plan(account_id="acct-camp", campaign_id="c-123",
                                campaign_name=None)
        self.assertFalse(scheduler.is_account_audit(plan))
        self.assertEqual(len(self.fake.calls), 0)


# ══ B) IDEMPOTENCY — one active ritual per account ═════════════════════════


class AccountAuditIdempotency(unittest.IsolatedAsyncioTestCase):
    async def test_seed_is_idempotent_no_duplicate(self):
        acct = "acct-idem"
        first = await plans_router.enable_account_audit(
            plans_router.AccountAuditRequest(account_id=acct))
        self.assertFalse(first["already_active"])
        self.assertEqual(first["action_category"], "audit")
        self.assertIsNone(first["campaign_id"])
        self.assertEqual(first["mode"], "auto")            # auto lane
        self.assertEqual(first["schedule_type"], "recurring")
        self.assertIsNotNone(first["next_run_at"])         # first weekly slot armed

        # Second call returns the SAME plan, does not create a new one.
        second = await plans_router.enable_account_audit(
            plans_router.AccountAuditRequest(account_id=acct))
        self.assertTrue(second["already_active"])
        self.assertEqual(second["id"], first["id"])

        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT COUNT(*) c FROM scheduled_plans WHERE account_id = ? "
                "AND action_category = 'audit' AND campaign_id IS NULL", (acct,))
            self.assertEqual((await cur.fetchone())["c"], 1)   # exactly one
        finally:
            await db.close()

    async def test_ritual_appears_in_listing_and_upcoming(self):
        acct = "acct-listing"
        seeded = await plans_router.enable_account_audit(
            plans_router.AccountAuditRequest(account_id=acct))

        # Call the handlers directly → pass the params FastAPI would inject
        # (their defaults are Query(...) sentinels, not plain values).
        listing = await plans_router.list_plans(account_id=acct, campaign_id=None)
        self.assertIn(seeded["id"], [p["id"] for p in listing])

        upcoming = await plans_router.upcoming(account_id=acct, limit=50)
        row = next((p for p in upcoming if p["id"] == seeded["id"]), None)
        self.assertIsNotNone(row)                           # surfaces on the dashboard
        self.assertEqual(row["action_category"], "audit")
        self.assertEqual(row["mode"], "auto")

    async def test_done_ritual_does_not_block_new_seed(self):
        """A terminal (done) ritual is not 'active' — a fresh seed is allowed."""
        acct = "acct-doneseed"
        await _seed_plan(account_id=acct, status="done")
        fresh = await plans_router.enable_account_audit(
            plans_router.AccountAuditRequest(account_id=acct))
        self.assertFalse(fresh["already_active"])           # created a new one


# ══ C) RECURRING RE-ARM — next weekly slot ═════════════════════════════════


class AccountAuditReArm(unittest.IsolatedAsyncioTestCase):
    async def test_complete_rearms_to_next_weekly_slot(self):
        plan = await _seed_plan(
            account_id="acct-rearm",
            next_run_at="2026-07-06 09:00:00",   # a Monday
            run_count=0,
        )
        await scheduler._complete(plan, "launched", 0.0)

        refreshed = await scheduler.get_plan(plan["id"])
        self.assertEqual(refreshed["status"], "scheduled")
        self.assertEqual(refreshed["run_count"], 1)
        nxt = refreshed["next_run_at"]
        self.assertIsNotNone(nxt)
        # Next slot must be strictly in the future and land on a Monday 09:00.
        dt = datetime.fromisoformat(nxt)
        self.assertGreater(dt, scheduler._now())
        self.assertEqual(dt.weekday(), 0)                   # Monday
        self.assertEqual((dt.hour, dt.minute), (9, 0))

    async def test_weekly_recurrence_computes_next_monday(self):
        # Standalone check of the recurrence math the ritual relies on.
        after = datetime(2026, 7, 4, 12, 0, 0)              # a Saturday
        nxt = scheduler.compute_next_run(scheduler.WEEKLY_AUDIT_RECURRENCE, after)
        self.assertEqual(nxt.weekday(), 0)                  # Monday
        self.assertEqual((nxt.hour, nxt.minute), (9, 0))
        self.assertGreater(nxt, after)


# ══ D) AUTO-LANE — audit is never approval-gated ═══════════════════════════


class AccountAuditAutoLane(unittest.IsolatedAsyncioTestCase):
    def test_audit_infers_auto_never_approval(self):
        self.assertEqual(scheduler.infer_mode("audit"), "auto")
        # The money/structure categories stay gated; audit is not among them.
        for gated in ("budget", "bids", "status", "geo"):
            self.assertEqual(scheduler.infer_mode(gated), "approval")
        self.assertNotIn("audit", scheduler._APPROVAL_CATEGORIES)

    def test_is_account_audit_predicate(self):
        self.assertTrue(scheduler.is_account_audit(
            {"action_category": "audit", "campaign_id": None, "campaign_name": None}))
        # Wrong category, or any campaign binding → not the ritual.
        self.assertFalse(scheduler.is_account_audit(
            {"action_category": "report", "campaign_id": None, "campaign_name": None}))
        self.assertFalse(scheduler.is_account_audit(
            {"action_category": "audit", "campaign_id": "c1", "campaign_name": None}))
        self.assertFalse(scheduler.is_account_audit(
            {"action_category": "audit", "campaign_id": None, "campaign_name": "Legacy"}))


if __name__ == "__main__":
    unittest.main()
