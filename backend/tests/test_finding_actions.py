"""Story 13.3 — findings → approvable actions contract.

Repo test style: stdlib unittest, a REAL temp SQLite from init_db(), and
scripted fakes for anything that would otherwise fire an agent run / hit an LLM
/ Google Ads / the network. No live calls anywhere.

The ONE thing we stub is the plan-EXECUTION edge: `scheduler.run_now` (the auto
lane's guarded fire path, which would call `stream_agent_response`). We record
that it was invoked with the right plan_id — proving the auto lane routes
through the scheduler's scope-guarded path — without running an agent. Plan
CREATION uses the real `routers/plans.create_plan` against the real schema, so
gating (`scheduler.infer_mode`) and the plan row are exercised for real.

Covers:
  A) MAPPING — finding/signal → proposed action per category (actionable vs
     advisory), gated-vs-auto via infer_mode, $-impact + campaign binding,
     stable finding_key across re-audits.
  B) APPROVE — auto category creates a plan AND fires it through the (stubbed)
     guarded run_now; gated category creates a plan but does NOT auto-fire.
  C) APPROVE ONCE — one-time plan (run_at set), routed through the same gates
     + guarded path.
  D) DENY — persists + suppresses from list_actions; survives re-audit of the
     same finding; a changed finding re-surfaces.
  E) ADVISORY — audit/report/other + no-campaign findings produce no action.
  F) LIST — money-ranked, recoverable total counts only actionable non-denied.

Run:  cd backend && .venv/bin/python -m unittest tests.test_finding_actions -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="finding-actions-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                        # noqa: E402
from app.services import account_report_store                   # noqa: E402
from app.services import finding_actions as fa                  # noqa: E402
from app.services import scheduler                              # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────


def _finding(title, category, campaign_ids, impact, action="do the thing", evidence="ev"):
    return {
        "title": title,
        "campaign_ids": campaign_ids,
        "evidence": evidence,
        "dollar_impact_wk": impact,
        "action_category": category,
        "recommended_action": action,
    }


async def _save_report(account_id, findings, total=0.0):
    report = {
        "mode": "account",
        "findings": findings,
        "total_recoverable_wk": total,
        "summary": "s",
        "campaigns_audited": [],
        "campaigns_excluded": [],
        "parse_ok": True,
    }
    await account_report_store.save_latest(account_id, str(uuid.uuid4()), report)


async def _plan_row(plan_id):
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM scheduled_plans WHERE id = ?", (plan_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _state_row(account_id, finding_key):
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM finding_actions WHERE account_id = ? AND finding_key = ?",
            (account_id, finding_key),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


class _StubRunNow:
    """Records calls to scheduler.run_now instead of firing an agent."""
    def __init__(self):
        self.calls: list[str] = []

    async def __call__(self, plan_id):
        self.calls.append(plan_id)
        return {"status": "running", "plan_id": plan_id}


# ══ A) MAPPING ═════════════════════════════════════════════════════════


class Mapping(unittest.IsolatedAsyncioTestCase):
    async def test_search_terms_is_auto_and_actionable(self):
        p = fa.propose_action(
            _finding("Cut waste on X", "search_terms", ["c1"], 120.0), source="finding"
        )
        self.assertTrue(p["actionable"])
        self.assertEqual(p["mode"], "auto")
        self.assertFalse(p["requires_approval"])
        self.assertEqual(p["action_category"], "search_terms")
        self.assertEqual(p["campaign_ids"], ["c1"])
        self.assertEqual(p["dollar_impact_wk"], 120.0)
        self.assertIsNotNone(p["mutation"])
        self.assertIn("c1", p["diff_preview"])

    async def test_budget_bids_status_geo_are_gated(self):
        for cat in ("budget", "bids", "status", "geo"):
            p = fa.propose_action(_finding(f"{cat} thing", cat, ["c1"], 50.0))
            self.assertTrue(p["actionable"], cat)
            self.assertEqual(p["mode"], "approval", cat)
            self.assertTrue(p["requires_approval"], cat)

    async def test_negative_keyword_actionable_auto(self):
        p = fa.propose_action(_finding("Add negatives", "negative_keyword", ["c1"], 30.0))
        self.assertTrue(p["actionable"])
        self.assertEqual(p["mode"], "auto")   # not in gated set

    async def test_audit_report_other_are_advisory(self):
        for cat in ("audit", "report", "other"):
            p = fa.propose_action(_finding("Investigate", cat, ["c1"], 10.0))
            self.assertFalse(p["actionable"], cat)
            self.assertIsNone(p["mutation"], cat)
            self.assertIsNotNone(p["advisory_reason"], cat)

    async def test_actionable_category_without_campaign_is_advisory(self):
        """A budget finding with no campaign to scope → cannot safely write."""
        p = fa.propose_action(_finding("Raise budget somewhere", "budget", [], 40.0))
        self.assertFalse(p["actionable"])
        self.assertIn("No target campaign", p["advisory_reason"])

    async def test_signal_single_campaign_id_normalized(self):
        signal = {
            "type": "wasted_spend", "campaign_id": "c9", "campaign_name": "Nine",
            "title": "Wasted spend on Nine", "detail": "$70 with 0 conv",
            "action_category": "search_terms", "dollar_impact_wk": 70.0,
        }
        p = fa.propose_action(signal, source="signal")
        self.assertEqual(p["campaign_ids"], ["c9"])
        self.assertTrue(p["actionable"])
        self.assertEqual(p["source"], "signal")

    async def test_unknown_category_falls_to_other_advisory(self):
        p = fa.propose_action(_finding("weird", "quantum_bidding", ["c1"], 5.0))
        self.assertEqual(p["action_category"], "other")
        self.assertFalse(p["actionable"])

    async def test_finding_key_stable_across_impact_and_wording_drift(self):
        a = fa.propose_action(_finding("Cut waste on X", "search_terms", ["c1"], 120.0, evidence="a"))
        # same identity, different $ + different evidence wording
        b = fa.propose_action(_finding("Cut waste on X", "search_terms", ["c1"], 88.0, evidence="ZZZ"))
        self.assertEqual(a["finding_key"], b["finding_key"])
        # different campaign → different key
        c = fa.propose_action(_finding("Cut waste on X", "search_terms", ["c2"], 120.0))
        self.assertNotEqual(a["finding_key"], c["finding_key"])


# ══ B) APPROVE (auto fires, gated parks) ═══════════════════════════════


class Approve(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig_run_now = scheduler.run_now
        self.stub = _StubRunNow()
        scheduler.run_now = self.stub

    def tearDown(self):
        scheduler.run_now = self._orig_run_now

    async def test_approve_auto_creates_plan_and_fires_guarded(self):
        acct = "ap-auto"
        f = _finding("Clean search terms on C1", "search_terms", ["c1"], 70.0)
        await _save_report(acct, [f])
        key = fa.propose_action(f)["finding_key"]

        res = await fa.approve(acct, key, once=False)
        self.assertEqual(res["status"], "approved")
        self.assertFalse(res["gated"])
        self.assertTrue(res["fired"])                         # auto → fired now
        plan_id = res["plan_id"]
        self.assertIsNotNone(plan_id)
        self.assertEqual(self.stub.calls, [plan_id])          # through run_now (scope-guarded path)

        # A real plan row exists, category preserved, mode inferred auto.
        plan = await _plan_row(plan_id)
        self.assertEqual(plan["action_category"], "search_terms")
        self.assertEqual(plan["mode"], "auto")
        self.assertEqual(plan["campaign_id"], "c1")
        self.assertEqual(plan["schedule_type"], "once")

        # Decision state persisted with the plan_id.
        st = await _state_row(acct, key)
        self.assertEqual(st["status"], "approved")
        self.assertEqual(st["plan_id"], plan_id)

    async def test_approve_gated_creates_plan_but_does_not_fire(self):
        acct = "ap-gated"
        f = _finding("Raise budget on C1", "budget", ["c1"], 200.0)
        await _save_report(acct, [f])
        key = fa.propose_action(f)["finding_key"]

        res = await fa.approve(acct, key, once=False)
        self.assertEqual(res["status"], "approved")
        self.assertTrue(res["gated"])
        self.assertTrue(res["requires_approval"])
        self.assertFalse(res["fired"])                        # gated → NOT auto-fired
        self.assertEqual(self.stub.calls, [])                 # run_now never called

        plan = await _plan_row(res["plan_id"])
        self.assertEqual(plan["mode"], "approval")            # gated at the plan level too

    async def test_approve_advisory_returns_error_no_plan(self):
        acct = "ap-advisory"
        f = _finding("Rewrite the landing page", "other", ["c1"], 0.0)
        await _save_report(acct, [f])
        key = fa.propose_action(f)["finding_key"]

        res = await fa.approve(acct, key)
        self.assertIn("error", res)
        self.assertIsNotNone(res.get("advisory_reason"))
        self.assertEqual(self.stub.calls, [])
        self.assertIsNone(await _state_row(acct, key))        # nothing persisted

    async def test_approve_unknown_key_errors(self):
        acct = "ap-unknown"
        await _save_report(acct, [_finding("x", "search_terms", ["c1"], 5.0)])
        res = await fa.approve(acct, "deadbeefdeadbeefdead")
        self.assertIn("error", res)


# ══ C) APPROVE ONCE ════════════════════════════════════════════════════


class ApproveOnce(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig_run_now = scheduler.run_now
        self.stub = _StubRunNow()
        scheduler.run_now = self.stub

    def tearDown(self):
        scheduler.run_now = self._orig_run_now

    async def test_approve_once_auto_is_one_time_and_fires(self):
        acct = "once-auto"
        f = _finding("One-shot cleanup C1", "search_terms", ["c1"], 40.0)
        await _save_report(acct, [f])
        key = fa.propose_action(f)["finding_key"]

        res = await fa.decide(acct, key, "approve_once")
        self.assertEqual(res["status"], "approved_once")
        self.assertTrue(res["fired"])
        self.assertEqual(self.stub.calls, [res["plan_id"]])

        plan = await _plan_row(res["plan_id"])
        self.assertEqual(plan["schedule_type"], "once")
        self.assertIsNotNone(plan["run_at"])                  # run_at=now set
        self.assertIsNotNone(plan["next_run_at"])

        st = await _state_row(acct, key)
        self.assertEqual(st["status"], "approved_once")

    async def test_approve_once_gated_still_parks(self):
        acct = "once-gated"
        f = _finding("Pause C1 now", "status", ["c1"], 0.0)
        await _save_report(acct, [f])
        key = fa.propose_action(f)["finding_key"]

        res = await fa.decide(acct, key, "approve_once")
        self.assertEqual(res["status"], "approved_once")
        self.assertTrue(res["gated"])
        self.assertFalse(res["fired"])                        # gated one-shot still needs sign-off
        self.assertEqual(self.stub.calls, [])


# ══ D) DENY (persist + suppress) ═══════════════════════════════════════


class Deny(unittest.IsolatedAsyncioTestCase):
    async def test_deny_persists_and_suppresses(self):
        acct = "deny-1"
        f = _finding("Cut waste on C1", "search_terms", ["c1"], 70.0)
        await _save_report(acct, [f])
        key = fa.propose_action(f)["finding_key"]

        # Present before denial.
        before = await fa.list_actions(acct)
        self.assertIn(key, [a["finding_key"] for a in before["actions"]])

        res = await fa.deny(acct, key)
        self.assertEqual(res["status"], "denied")
        st = await _state_row(acct, key)
        self.assertEqual(st["status"], "denied")

        # Suppressed from the default list; recoverable total drops it.
        after = await fa.list_actions(acct)
        self.assertNotIn(key, [a["finding_key"] for a in after["actions"]])
        self.assertEqual(after["total_recoverable_wk"], 0.0)

        # Still visible with include_denied for audit.
        audited = await fa.list_actions(acct, include_denied=True)
        row = next(a for a in audited["actions"] if a["finding_key"] == key)
        self.assertEqual(row["status"], "denied")

    async def test_deny_survives_reaudit_of_same_finding(self):
        """Re-running the audit and re-persisting the SAME finding (same
        identity, drifted $ impact) must keep it suppressed — deny sticks."""
        acct = "deny-reaudit"
        f1 = _finding("Cut waste on C1", "search_terms", ["c1"], 70.0)
        await _save_report(acct, [f1])
        key = fa.propose_action(f1)["finding_key"]
        await fa.deny(acct, key)

        # New audit: same finding identity, different $ + wording.
        f2 = _finding("Cut waste on C1", "search_terms", ["c1"], 55.0, evidence="new words")
        await _save_report(acct, [f2])

        after = await fa.list_actions(acct)
        self.assertNotIn(key, [a["finding_key"] for a in after["actions"]])  # still gone

    async def test_changed_finding_resurfaces(self):
        """A materially different finding (new campaign) is a NEW key → not
        suppressed by the old denial."""
        acct = "deny-change"
        f1 = _finding("Cut waste", "search_terms", ["c1"], 70.0)
        await _save_report(acct, [f1])
        await fa.deny(acct, fa.propose_action(f1)["finding_key"])

        f2 = _finding("Cut waste", "search_terms", ["c2"], 70.0)   # different campaign
        await _save_report(acct, [f2])
        after = await fa.list_actions(acct)
        keys = [a["finding_key"] for a in after["actions"]]
        self.assertIn(fa.propose_action(f2)["finding_key"], keys)

    async def test_deny_unknown_finding_records_tombstone(self):
        acct = "deny-tombstone"
        await _save_report(acct, [])   # no live findings
        res = await fa.deny(acct, "ffffffffffffffffffff")
        self.assertEqual(res["status"], "denied")
        st = await _state_row(acct, "ffffffffffffffffffff")
        self.assertIsNotNone(st)       # tombstone persisted


# ══ E) ADVISORY / LIST ═════════════════════════════════════════════════


class ListAndAdvisory(unittest.IsolatedAsyncioTestCase):
    async def test_list_money_ranked_and_flags_advisory(self):
        acct = "list-rank"
        findings = [
            _finding("Small waste", "search_terms", ["c1"], 30.0),
            _finding("Big budget fix", "budget", ["c2"], 200.0),
            _finding("Investigate tracking", "audit", ["c3"], None),   # advisory
            _finding("Rewrite LP", "other", ["c4"], None),             # advisory
        ]
        await _save_report(acct, findings)

        out = await fa.list_actions(acct)
        # Ranked: 200 budget first, then 30 search_terms, advisory (no $) last.
        actionable = [a for a in out["actions"] if a["actionable"]]
        self.assertEqual(actionable[0]["action_category"], "budget")
        self.assertEqual(actionable[1]["action_category"], "search_terms")

        self.assertEqual(out["actionable_count"], 2)
        self.assertEqual(out["advisory_count"], 2)
        # Recoverable counts only actionable non-denied w/ $: 200 + 30.
        self.assertAlmostEqual(out["total_recoverable_wk"], 230.0, places=1)

        advisory = [a for a in out["actions"] if not a["actionable"]]
        self.assertTrue(all(a["advisory_reason"] for a in advisory))
        self.assertTrue(all(a["mutation"] is None for a in advisory))

    async def test_empty_account_empty_list(self):
        out = await fa.list_actions("list-empty")
        self.assertEqual(out["count"], 0)
        self.assertEqual(out["total_recoverable_wk"], 0.0)
        self.assertEqual(out["actions"], [])


if __name__ == "__main__":
    unittest.main()
