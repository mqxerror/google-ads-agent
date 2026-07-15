"""Story 13.1 — account-wide planning mode in the workflow orchestrator.

NO live LLM calls and NO live Google Ads calls: stream_agent_response is
replaced with a scripted fake (recording every call), campaigns_repo's
sync is stubbed, and SYNC_ENABLED is off so Phase 0 never imports the
sync engine. The database is a REAL SQLite created by init_db() in a
temp dir, so campaign enumeration, spend ranking, and report persistence
exercise the actual schema.

Pins:
- campaign enumeration: ENABLED-only roster, ranked by recent spend,
  capped by WORKFLOW_MAX_CAMPAIGNS, excluded campaigns named (never silent)
- mode branching: campaign_id=None → account mode; a concrete campaign_id
  keeps the existing per-campaign behaviour untouched (tools pass through)
- findings contract: normalized structure, $-impact sort, recomputed
  "total recoverable" rollup, prose-only degrade on unparseable synthesis
- account runs are analysis-only: specialist/debate tools forced to []

Run:  cd backend && .venv/bin/python -m unittest tests.test_workflow_account_mode -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

# Point the app at a throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="wf-account-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db                      # noqa: E402
from app.services import campaigns_repo                       # noqa: E402
from app.services import workflow_orchestrator as wo          # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────


async def _seed(account_id: str, rows: list[tuple[str, str, str, float]]) -> None:
    """rows: (campaign_id, name, status, recent_spend_usd)."""
    db = await get_db()
    try:
        for cid, name, status, spend in rows:
            await db.execute(
                "INSERT OR REPLACE INTO campaigns "
                "(campaign_id, account_id, name, status, last_synced_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (cid, account_id, name, status),
            )
            await db.execute(
                "INSERT OR REPLACE INTO campaign_daily_metrics "
                "(account_id, campaign_id, campaign_name, date, cost_micros) "
                "VALUES (?, ?, ?, date('now', '-1 day'), ?)",
                (account_id, cid, name, int(spend * 1_000_000)),
            )
        await db.commit()
    finally:
        await db.close()


class FakeAgentStream:
    """Stands in for stream_agent_response — records calls, scripts replies."""

    def __init__(self, reply_fn):
        self.calls: list[dict] = []
        self.reply_fn = reply_fn

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.reply_fn(kwargs)

        async def gen():
            yield {"type": "text", "content": reply}
            yield {"type": "done", "cost": 0.01}

        return gen()


def _collect(agen) -> list[dict]:
    async def run():
        return [ev async for ev in agen]

    return asyncio.run(run())


async def _noop_sync(account_id: str) -> int:  # replaces campaigns_repo.sync_campaigns
    return 0


_FINDINGS_REPLY = (
    "Here is the account report.\n"
    "```json\n"
    + json.dumps({
        "findings": [
            {   # unquantified, listed FIRST by the LLM — must sort last
                "title": "Fix B",
                "campaign_ids": ["c-mid"],
                "evidence": "e2",
                "dollar_impact_wk": None,
                "action_category": "bids",
                "recommended_action": "raise bids",
            },
            {   # string impact + single campaign_id + bogus category
                "title": "Fix A",
                "campaign_id": "c-hi",
                "evidence": "e1",
                "dollar_impact_wk": "~ $120.0/wk",
                "action_category": "bogus-category",
                "recommended_action": "cut waste",
            },
        ],
        "total_recoverable_wk": 999.0,   # wrong on purpose — server recomputes
        "summary": "exec summary",
    })
    + "\n```\nTotal recoverable: $120/wk"
)


class _Base(unittest.TestCase):
    def setUp(self):
        self._orig_stream = wo.stream_agent_response
        self._orig_sync_enabled = settings.SYNC_ENABLED
        self._orig_cap = settings.WORKFLOW_MAX_CAMPAIGNS
        self._orig_repo_sync = campaigns_repo.sync_campaigns
        settings.SYNC_ENABLED = False          # Phase 0 stays offline
        campaigns_repo.sync_campaigns = _noop_sync  # belt + suspenders: no live roster sync

    def tearDown(self):
        wo.stream_agent_response = self._orig_stream
        settings.SYNC_ENABLED = self._orig_sync_enabled
        settings.WORKFLOW_MAX_CAMPAIGNS = self._orig_cap
        campaigns_repo.sync_campaigns = self._orig_repo_sync


# ── Campaign enumeration + cap ────────────────────────────────────────


class SelectAccountCampaigns(_Base):
    ACCT = "acct-sel"

    def test_ranked_by_spend_capped_and_enabled_only(self):
        asyncio.run(_seed(self.ACCT, [
            ("s-1", "Low", "ENABLED", 10.0),
            ("s-2", "Mid", "ENABLED", 20.0),
            ("s-3", "High", "ENABLED", 60.0),
            ("s-4", "Higher", "ENABLED", 40.0),
            ("s-5", "Highest", "ENABLED", 50.0),
            ("s-6", "Zero", "ENABLED", 0.0),
            ("s-7", "Paused big spender", "PAUSED", 999.0),
        ]))
        selected, excluded = asyncio.run(
            wo._select_account_campaigns(self.ACCT, 14, cap=4)
        )
        self.assertEqual([c["campaign_id"] for c in selected],
                         ["s-3", "s-5", "s-4", "s-2"])       # spend desc
        self.assertEqual([c["campaign_id"] for c in excluded],
                         ["s-1", "s-6"])                     # lowest spend out
        self.assertNotIn("s-7", [c["campaign_id"] for c in selected + excluded])
        self.assertEqual(selected[0]["spend"], 60.0)

    def test_cap_setting_is_env_configurable(self):
        settings.WORKFLOW_MAX_CAMPAIGNS = 3
        self.assertEqual(wo._max_campaigns(), 3)
        settings.WORKFLOW_MAX_CAMPAIGNS = 0     # falsy → default 5
        self.assertEqual(wo._max_campaigns(), 5)
        settings.WORKFLOW_MAX_CAMPAIGNS = -2    # nonsense → clamp to 1
        self.assertEqual(wo._max_campaigns(), 1)


# ── Findings contract normalization ───────────────────────────────────


class NormalizeFindings(unittest.TestCase):
    SELECTED = [{"campaign_id": "c-hi", "campaign_name": "Hi", "spend": 30.0}]
    EXCLUDED = [{"campaign_id": "c-lo", "campaign_name": "Lo", "spend": 5.0}]

    def test_unparseable_degrades_to_none(self):
        self.assertIsNone(wo._normalize_findings(None, self.SELECTED, self.EXCLUDED))
        self.assertIsNone(wo._normalize_findings({"findings": "prose"}, self.SELECTED, self.EXCLUDED))
        self.assertIsNone(wo._normalize_findings({"findings": []}, self.SELECTED, self.EXCLUDED))
        self.assertIsNone(wo._normalize_findings(
            {"findings": [{"evidence": "no title"}]}, self.SELECTED, self.EXCLUDED))

    def test_sort_coerce_and_recomputed_total(self):
        parsed = {
            "findings": [
                {"title": "unquantified", "dollar_impact_wk": None,
                 "action_category": "audit", "campaign_ids": ["c-hi"]},
                {"title": "small", "dollar_impact_wk": 40,
                 "action_category": "search_terms", "campaign_ids": ["c-hi"]},
                {"title": "big", "dollar_impact_wk": "about $150/wk",
                 "action_category": "NOT-A-CATEGORY", "campaign_id": "c-hi"},
            ],
            "total_recoverable_wk": 12345.0,   # ignored — recomputed
            "summary": "s",
        }
        report = wo._normalize_findings(parsed, self.SELECTED, self.EXCLUDED)
        self.assertEqual([f["title"] for f in report["findings"]],
                         ["big", "small", "unquantified"])   # $ desc, unquantified last
        self.assertEqual(report["findings"][0]["dollar_impact_wk"], 150.0)
        self.assertEqual(report["findings"][0]["action_category"], "other")
        self.assertEqual(report["findings"][0]["campaign_ids"], ["c-hi"])
        self.assertIsNone(report["findings"][2]["dollar_impact_wk"])
        self.assertEqual(report["total_recoverable_wk"], 190.0)
        self.assertEqual(report["campaigns_excluded"][0]["campaign_id"], "c-lo")
        self.assertIn("reason", report["campaigns_excluded"][0])


# ── Mode branching: per-campaign path untouched ───────────────────────


class CampaignModeUntouched(_Base):
    ACCT = "acct-camp"

    def test_campaign_scoped_run_behaves_as_before(self):
        asyncio.run(_seed(self.ACCT, [("c1", "One", "ENABLED", 10.0)]))
        fake = FakeAgentStream(lambda kw: "director prose"
                               if kw.get("active_role") == "director" else "specialist report")
        wo.stream_agent_response = fake

        events = _collect(wo.run_workflow(
            goal="audit it",
            account_id=self.ACCT,
            campaign_id="c1",
            campaign_name="One",
            plan_override={
                "specialists": [{
                    "role_id": "analytics_analyst", "model": "sonnet",
                    "tools": ["campaign__update_campaign"],  # must pass through UNstripped
                    "task": "check pacing",
                }],
                "debate_focus": "f",
            },
        ))

        types = [e["type"] for e in events]
        self.assertNotIn("account_scope", types)
        done = next(e for e in events if e["type"] == "workflow_done")
        self.assertNotIn("account_report", done)
        self.assertEqual(done["stop_reason"], "natural")
        self.assertNotIn("ACCOUNT AUDIT SCOPE", done["final_output"])

        spec_calls = [c for c in fake.calls if c.get("active_role") == "analytics_analyst"]
        self.assertEqual(len(spec_calls), 1)
        self.assertEqual(spec_calls[0]["campaign_id"], "c1")
        # campaign mode never rewrites the planned tool allowlist
        self.assertEqual(spec_calls[0]["tool_allowlist"], ["campaign__update_campaign"])

        start = next(e for e in events if e["type"] == "workflow_start")
        self.assertEqual(start["mode"], "campaign")


# ── Account mode: fan-out, scoping, rollup ────────────────────────────


class AccountModeRun(_Base):
    ACCT = "acct-acct"

    def _events(self):
        asyncio.run(_seed(self.ACCT, [
            ("c-hi", "High Roller", "ENABLED", 30.0),
            ("c-mid", "Middle", "ENABLED", 20.0),
            ("c-lo", "Little", "ENABLED", 10.0),
        ]))
        settings.WORKFLOW_MAX_CAMPAIGNS = 2

        def reply(kw):
            if kw.get("active_role") == "director":
                return _FINDINGS_REPLY
            return f"report for {kw.get('campaign_id')}"

        self.fake = FakeAgentStream(reply)
        wo.stream_agent_response = self.fake
        return _collect(wo.run_workflow(
            goal="account audit",
            account_id=self.ACCT,
            campaign_id=None,
            plan_override={
                "specialists": [
                    {"role_id": "analytics_analyst", "campaign_id": "c-hi",
                     "tools": ["campaign__update_campaign"],  # must be FORCED to []
                     "task": "audit hi"},
                    {"role_id": "ppc_strategist", "campaign_id": "c-mid",
                     "task": "audit mid"},
                    {"role_id": "analytics_analyst", "campaign_id": "c-lo",
                     "task": "out of scope — must be dropped"},
                    {"role_id": "creative_director",
                     "task": "no campaign — must be dropped"},
                ],
                "debate_focus": "cannibalization",
            },
        ))

    def test_account_run_end_to_end(self):
        events = self._events()

        # Scope event: cap + ranked selection + named exclusion
        scope = next(e for e in events if e["type"] == "account_scope")
        self.assertEqual(scope["cap"], 2)
        self.assertEqual([c["campaign_id"] for c in scope["selected"]], ["c-hi", "c-mid"])
        self.assertEqual(scope["excluded"][0]["campaign_id"], "c-lo")
        self.assertIn("cap", scope["excluded"][0]["reason"])
        self.assertEqual(scope["total_active"], 3)

        start = next(e for e in events if e["type"] == "workflow_start")
        self.assertEqual(start["mode"], "account")

        # Plan normalized: out-of-scope + campaign-less passes dropped
        plan = next(e for e in events if e["type"] == "plan")
        self.assertEqual(len(plan["specialists"]), 2)
        self.assertEqual({s["campaign_id"] for s in plan["specialists"]},
                         {"c-hi", "c-mid"})
        for s in plan["specialists"]:
            self.assertEqual(s["tools"], [])   # analysis-only, always

        # Specialist passes ran bound to their own campaign, tools forced []
        spec_calls = [c for c in self.fake.calls
                      if c.get("active_role") != "director" and c.get("campaign_id")]
        self.assertEqual({c["campaign_id"] for c in spec_calls}, {"c-hi", "c-mid"})
        for c in spec_calls:
            self.assertEqual(c["tool_allowlist"], [])

        # Cross-campaign debate ran UNBOUND (account-level reasoning)
        debate_starts = [e for e in events
                         if e["type"] == "agent_start" and e["phase"] == "debate"]
        self.assertTrue(debate_starts)
        for e in debate_starts:
            self.assertIsNone(e["campaign_id"])
        debate_calls = [c for c in self.fake.calls
                        if c.get("active_role") != "director" and not c.get("campaign_id")]
        for c in debate_calls:
            self.assertEqual(c["tool_allowlist"], [])

        # Rollup contract on workflow_done
        done = next(e for e in events if e["type"] == "workflow_done")
        report = done["account_report"]
        self.assertTrue(report["parse_ok"])
        self.assertEqual(report["mode"], "account")
        f0, f1 = report["findings"]
        self.assertEqual(f0["title"], "Fix A")               # quantified first
        self.assertEqual(f0["dollar_impact_wk"], 120.0)      # "~ $120.0/wk" coerced
        self.assertEqual(f0["action_category"], "other")     # bogus → other
        self.assertEqual(f0["campaign_ids"], ["c-hi"])       # single id → list
        self.assertIsNone(f1["dollar_impact_wk"])            # explicit unquantified
        self.assertEqual(report["total_recoverable_wk"], 120.0)  # recomputed, not 999
        self.assertEqual(report["campaigns_excluded"][0]["campaign_id"], "c-lo")

        # The report SAYS what was excluded — even in the prose output
        self.assertIn("ACCOUNT AUDIT SCOPE", done["final_output"])
        self.assertIn("EXCLUDED", done["final_output"])
        self.assertIn("Little", done["final_output"])

        # Persisted rollup row for Story 13.2 to consume
        async def fetch():
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT wr.content FROM workflow_reports wr "
                    "JOIN workflow_runs r ON r.id = wr.run_id "
                    "WHERE r.account_id = ? AND wr.phase = 'account_rollup'",
                    (self.ACCT,),
                )
                return [dict(r) for r in await cur.fetchall()]
            finally:
                await db.close()

        rows = asyncio.run(fetch())
        self.assertEqual(len(rows), 1)
        persisted = json.loads(rows[0]["content"])
        self.assertEqual(len(persisted["findings"]), 2)
        self.assertEqual(persisted["total_recoverable_wk"], 120.0)


# ── Account mode: degrade paths ───────────────────────────────────────


class AccountModeDegrades(_Base):
    def test_unparseable_plan_and_synthesis_degrade_gracefully(self):
        acct = "acct-fallback"
        asyncio.run(_seed(acct, [
            ("f-1", "Alpha", "ENABLED", 25.0),
            ("f-2", "Beta", "ENABLED", 15.0),
        ]))

        def reply(kw):
            if kw.get("active_role") == "director":
                return "no structured output here at all"   # plan AND synthesis
            return "campaign findings text"

        fake = FakeAgentStream(reply)
        wo.stream_agent_response = fake
        events = _collect(wo.run_workflow(
            goal="account audit", account_id=acct, campaign_id=None,
        ))

        # Unparseable Director plan → default ritual: one pass per campaign
        plan = next(e for e in events if e["type"] == "plan")
        self.assertEqual([s["campaign_id"] for s in plan["specialists"]],
                         ["f-1", "f-2"])
        self.assertTrue(all(s["role_id"] == "analytics_analyst"
                            for s in plan["specialists"]))

        # Unparseable synthesis → prose-only report, run still completes
        done = next(e for e in events if e["type"] == "workflow_done")
        report = done["account_report"]
        self.assertFalse(report["parse_ok"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["total_recoverable_wk"], 0.0)
        self.assertEqual(len(report["campaigns_audited"]), 2)
        self.assertIn("ACCOUNT AUDIT SCOPE", done["final_output"])

    def test_no_enabled_campaigns_errors_cleanly(self):
        fake = FakeAgentStream(lambda kw: "should never be called")
        wo.stream_agent_response = fake
        events = _collect(wo.run_workflow(
            goal="account audit", account_id="acct-empty", campaign_id=None,
        ))
        err = next(e for e in events if e["type"] == "error")
        self.assertIn("no ENABLED campaigns", err["message"])
        # No agent ever ran, no plan phase started
        self.assertEqual(fake.calls, [])
        self.assertNotIn("plan", [e.get("phase") for e in events if e["type"] == "phase"])


if __name__ == "__main__":
    unittest.main()
