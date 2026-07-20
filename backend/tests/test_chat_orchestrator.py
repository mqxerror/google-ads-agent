"""Chat Orchestration v2 — Epic 2 tests (task_ledger + chat_orchestrator).

Stdlib unittest, REAL temp SQLite from init_db(), NO network, NO real LLM.

The LLM is mocked by monkeypatching app.services.agent.stream_agent_response
with a fake async generator driven by a per-test SCRIPT (a list of event-lists,
one per LLM call, popped in order). Because chat_orchestrator lazy-imports
`from app.services.agent import stream_agent_response` INSIDE its functions, the
binding resolves at call time to the module attribute — so patching the module
attribute intercepts every call (triage / plan / specialist / synth).

Run:  cd backend && .venv/bin/python -m unittest tests.test_chat_orchestrator -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="chat-orch-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import agent as agent_mod        # noqa: E402
from app.services import chat_orchestrator         # noqa: E402
from app.services import task_ledger               # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


# ── Fake LLM ──────────────────────────────────────────────────────────
_SCRIPT: list[list[dict]] = []


def _fake_stream_factory():
    """Return a fake stream_agent_response that pops the next scripted
    event-list from _SCRIPT per call. Exhausted script → a bland done event."""
    async def _fake(*args, **kwargs):
        if _SCRIPT:
            events = _SCRIPT.pop(0)
        else:
            events = [{"type": "text", "content": "ok"}, {"type": "done", "cost": 0.0}]
        for e in events:
            yield e
    return _fake


async def _fake_fetch(*args, **kwargs):
    return ""  # no network; VERIFY sees an empty block → "failed"


async def _fake_conv_fetch(*args, **kwargs):
    return "", []  # no network; S2b conversion pull sees nothing → "failed"


def _text_call(text: str, cost: float = 0.1) -> list[dict]:
    return [{"type": "text", "content": text}, {"type": "done", "cost": cost}]


def _collect(gen):
    async def _run():
        return [ev async for ev in gen]
    return asyncio.get_event_loop().run_until_complete(_run())


class _Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _SCRIPT.clear()
        self._orig_stream = agent_mod.stream_agent_response
        self._orig_fetch = agent_mod.fetch_ad_landing_pages
        self._orig_conv = agent_mod.fetch_conversion_actions
        agent_mod.stream_agent_response = _fake_stream_factory()
        agent_mod.fetch_ad_landing_pages = _fake_fetch
        agent_mod.fetch_conversion_actions = _fake_conv_fetch

    def tearDown(self):
        agent_mod.stream_agent_response = self._orig_stream
        agent_mod.fetch_ad_landing_pages = self._orig_fetch
        agent_mod.fetch_conversion_actions = self._orig_conv

    async def _ensure_conversation(self, conversation_id):
        db = await get_db()
        try:
            await db.execute(
                "INSERT OR IGNORE INTO conversations (id, account_id) VALUES (?, ?)",
                (conversation_id, "acc1"),
            )
            await db.commit()
        finally:
            await db.close()

    async def _run(self, **kw):
        defaults = dict(
            turn_id=str(uuid.uuid4()), account_id="acc1", campaign_id="cmp1",
            campaign_name="Test Campaign", conversation_id="conv1",
        )
        defaults.update(kw)
        await self._ensure_conversation(defaults["conversation_id"])
        return [ev async for ev in chat_orchestrator.run_turn(**defaults)]

    def types(self, events):
        return [e["type"] for e in events]

    def assertSubsequence(self, sub, full):
        it = iter(full)
        for want in sub:
            for got in it:
                if got == want:
                    break
            else:
                self.fail(f"{want!r} not found in order within {full}")


# ── task_ledger.recall ────────────────────────────────────────────────
class TaskLedgerRecall(_Base):
    async def test_recall_empty_db_no_crash(self):
        out = await task_ledger.recall("accX", "cmpX", [], "anything", limit=8)
        self.assertEqual(out, [])

    async def test_recall_finds_chat_dispatched_report(self):
        # Seed a chat-origin specialist report + a matching chat_turns row so the
        # ct.turn_id = workflow_reports.run_id join resolves to this campaign.
        run_id = "turn-seed-1"
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO chat_turns (turn_id, conversation_id, campaign_id, mode, status) "
                "VALUES (?, ?, ?, 'orchestrated', 'done')",
                (run_id, "conv-seed", "cmp-seed"),
            )
            await db.execute(
                "INSERT INTO workflow_reports "
                "(id, run_id, phase, role_id, role_name, task, content, cost, seq, origin) "
                "VALUES (?, ?, 'specialist', 'ppc_strategist', 'PPC Strategist', ?, ?, 0.0, 0, 'chat')",
                (str(uuid.uuid4()), run_id, "task", "increase budget on AG2 by 20%"),
            )
            await db.commit()
        finally:
            await db.close()

        out = await task_ledger.recall("acc-seed", "cmp-seed", [], "budget", limit=8)
        self.assertGreaterEqual(len(out), 1)
        e = out[0]
        for k in ("source", "staleness", "decision"):
            self.assertIn(k, e)


# ── run_turn state machine ────────────────────────────────────────────
class RunTurnStateMachine(_Base):
    async def test_greeting_goes_direct(self):
        events = await self._run(force_mode=None, user_message="hi")
        types = self.types(events)
        self.assertNotIn("plan", types)
        self.assertNotIn("agent_called", types)
        starts = [e for e in events if e["type"] == "turn_start"]
        self.assertTrue(starts)
        self.assertEqual(starts[0]["payload"]["mode"], "direct")
        self.assertIn("turn_done", types)

    async def test_orchestrated_ordered_subsequence(self):
        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze bids"},'
            '{"role_id":"analytics_analyst","model":"sonnet","tools":[],"task":"trend"}]}\n```')
        spec = _text_call(
            'Bids look fine.\n```json\n{"findings":['
            '{"claim":"keep budget steady","severity":"low","confidence":0.7,'
            '"sources":["ctx"],"disconfirmed_by":"a CPA spike"}],"summary":"steady"}\n```')
        synth = _text_call("Here is the reconciled answer.")
        _SCRIPT.extend([plan, spec, spec, synth])

        events = await self._run(
            force_mode="orchestrate",
            user_message="do a full audit of my bidding and trends across the campaign")
        types = self.types(events)
        self.assertSubsequence(
            ["turn_start", "plan", "agent_called", "agent_result",
             "final_start", "final_done", "turn_done"],
            types)

    async def test_plan_capped_to_max_specialists(self):
        five = ",".join(
            f'{{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"t{i}"}}'
            for i in range(5))
        plan = _text_call('```json\n{"specialists":[' + five + ']}\n```')
        spec = _text_call(
            'ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = _text_call("done")
        # plan + up to MAX specialist calls + synth
        _SCRIPT.extend([plan] + [spec] * 5 + [synth])

        events = await self._run(
            force_mode="orchestrate", user_message="audit everything please")
        plan_evs = [e for e in events if e["type"] == "plan"]
        self.assertTrue(plan_evs)
        self.assertLessEqual(
            len(plan_evs[0]["payload"]["specialists"]),
            settings.CHAT_ORCH_MAX_SPECIALISTS)
        called = [e for e in events if e["type"] == "agent_called"]
        self.assertLessEqual(len(called), settings.CHAT_ORCH_MAX_SPECIALISTS)

    async def test_degrade_on_unparseable_plan(self):
        plan = _text_call("I cannot produce JSON, sorry — here is prose only.")
        direct = _text_call("A direct answer instead.")
        _SCRIPT.extend([plan, direct])

        events = await self._run(
            force_mode="orchestrate", user_message="audit my whole account now")
        types = self.types(events)
        self.assertNotIn("agent_called", types)
        self.assertIn("turn_done", types)
        # Some direct answer streamed after the degrade.
        self.assertTrue(any(e["type"] in ("text", "final_chunk") for e in events))

    async def test_field_name_contracts(self):
        # Seed a recall entry so a memory_recall event is emitted.
        run_id = "turn-fc-1"
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO chat_turns (turn_id, conversation_id, campaign_id, mode, status) "
                "VALUES (?, ?, ?, 'orchestrated', 'done')",
                (run_id, "conv-fc", "cmp-fc"),
            )
            await db.execute(
                "INSERT INTO workflow_reports "
                "(id, run_id, phase, role_id, role_name, task, content, cost, seq, origin) "
                "VALUES (?, ?, 'specialist', 'ppc_strategist', 'PPC Strategist', ?, ?, 0.0, 0, 'chat')",
                (str(uuid.uuid4()), run_id, "task", "prior budget analysis"),
            )
            await db.commit()
        finally:
            await db.close()

        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = _text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = _text_call("done")
        _SCRIPT.extend([plan, spec, synth])

        events = await self._run(
            force_mode="orchestrate", campaign_id="cmp-fc",
            user_message="analyze my budget in depth across the campaign")
        recalls = [e for e in events if e["type"] == "memory_recall"]
        self.assertTrue(recalls)
        for k in ("staleness", "decision"):
            self.assertIn(k, recalls[0]["payload"])
        called = [e for e in events if e["type"] == "agent_called"]
        self.assertTrue(called)
        for k in ("call_id", "role_id"):
            self.assertIn(k, called[0]["payload"])


# ── Live conversion-action injection (Fix 4) ──────────────────────────
class LiveConversionActions(_Base):
    """S2 pulls ENABLED conversion actions LIVE and injects them into the
    Director's context (superseding any stale registry), tags them into the
    provenance manifest as LIVE_API, and emits a verification event."""

    _PANAMA_BLOCK = (
        "LIVE CONVERSION ACTIONS (fetched this turn — supersedes any remembered "
        "registry):\n"
        "- Panama QIV Lead (id 7607343274) status=ENABLED primary=YES"
    )

    async def _panama_conv(self, *args, **kwargs):
        return self._PANAMA_BLOCK, [{
            "id": "7607343274", "name": "Panama QIV Lead",
            "status": "ENABLED", "primary_for_goal": True}]

    def _capturing_stream(self):
        """A fake stream that records every user_message it is called with, so we
        can assert the conversion block reached the Director's plan/synth prompt.
        Still honors _SCRIPT for the returned events."""
        prompts = self.captured_prompts = []

        async def _fake(*args, **kwargs):
            prompts.append(kwargs.get("user_message", ""))
            events = _SCRIPT.pop(0) if _SCRIPT else [
                {"type": "text", "content": "ok"}, {"type": "done", "cost": 0.0}]
            for e in events:
                yield e
        return _fake

    async def test_conversion_block_injected_manifest_and_verification(self):
        agent_mod.fetch_conversion_actions = self._panama_conv
        agent_mod.stream_agent_response = self._capturing_stream()

        # Spy on the manifest so we capture the LIVE_API add for conversion actions.
        from app.services import provenance as prov_mod
        live_calls = []
        orig_add = prov_mod.ProvenanceManifest.add_live_api

        def _spy_add(self, output, ts, tool_name=""):
            live_calls.append({"output": output, "tool_name": tool_name})
            return orig_add(self, output, ts, tool_name=tool_name)

        prov_mod.ProvenanceManifest.add_live_api = _spy_add
        try:
            plan = _text_call(
                '```json\n{"specialists":['
                '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
            spec = _text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
            synth = _text_call("done")
            _SCRIPT.extend([plan, spec, synth])

            events = await self._run(
                force_mode="orchestrate",
                user_message="does a Panama QIP conversion action exist for this campaign?")
        finally:
            prov_mod.ProvenanceManifest.add_live_api = orig_add

        # (a) The block reached the Director context (plan prompt is the first
        # non-specialist call; the synth prompt also carries premise_block).
        self.assertTrue(
            any("Panama QIV Lead" in p and "id 7607343274" in p
                for p in self.captured_prompts),
            "live conversion block must be injected into the Director prompt")
        self.assertTrue(
            any("supersedes any remembered registry" in p
                for p in self.captured_prompts))

        # (b) It was added to the manifest as LIVE_API via conversion_action_gaql.
        self.assertTrue(
            any("Panama QIV Lead" in c["output"]
                and c["tool_name"] == "conversion_action_gaql"
                for c in live_calls),
            "conversion actions must be tagged LIVE_API in the manifest")

        # (c) A verification conversion_actions event fired, status=verified.
        conv_evs = [e for e in events if e["type"] == "verification"
                    and e["payload"].get("kind") == "conversion_actions"]
        self.assertTrue(conv_evs)
        self.assertEqual(conv_evs[0]["payload"]["status"], "verified")
        self.assertIn("Panama QIV Lead", conv_evs[0]["payload"]["detail"])

    async def test_conversion_fetch_failure_degrades_no_crash(self):
        # The GAQL read raises → helper contract is that agent.fetch_conversion_actions
        # NEVER raises; but even if the orchestrator's call path raised, the turn
        # must survive and report status=failed. Simulate the failed/empty result.
        async def _empty_conv(*args, **kwargs):
            return "", []

        agent_mod.fetch_conversion_actions = _empty_conv

        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = _text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = _text_call("done")
        _SCRIPT.extend([plan, spec, synth])

        events = await self._run(
            force_mode="orchestrate", user_message="audit my conversions in depth")
        types = self.types(events)
        # No crash: the turn still terminates normally.
        self.assertIn("turn_done", types)
        conv_evs = [e for e in events if e["type"] == "verification"
                    and e["payload"].get("kind") == "conversion_actions"]
        self.assertTrue(conv_evs)
        self.assertEqual(conv_evs[0]["payload"]["status"], "failed")

    async def test_conversion_fetch_raising_is_caught(self):
        # If the injected fetch itself raises, the orchestrator's guard degrades
        # to status=failed and the turn still completes (belt-and-suspenders).
        async def _raising_conv(*args, **kwargs):
            raise RuntimeError("boom")

        agent_mod.fetch_conversion_actions = _raising_conv

        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = _text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = _text_call("done")
        _SCRIPT.extend([plan, spec, synth])

        events = await self._run(
            force_mode="orchestrate", user_message="audit my conversions in depth now")
        types = self.types(events)
        self.assertIn("turn_done", types)
        conv_evs = [e for e in events if e["type"] == "verification"
                    and e["payload"].get("kind") == "conversion_actions"]
        self.assertTrue(conv_evs)
        self.assertEqual(conv_evs[0]["payload"]["status"], "failed")


# ── Write-intent detection unit (Fix 1) ───────────────────────────────
class WriteIntentDetection(unittest.TestCase):
    def test_explicit_flag_wins(self):
        self.assertTrue(chat_orchestrator._detect_write_intent(
            {"task": "just look", "tools": [], "write_intent": True}))
        self.assertFalse(chat_orchestrator._detect_write_intent(
            {"task": "push 20 negatives", "tools": ["mutate"], "write_intent": False}))

    def test_verb_heuristic(self):
        self.assertTrue(chat_orchestrator._detect_write_intent(
            {"task": "push 20 negative keywords", "tools": []}))
        self.assertTrue(chat_orchestrator._detect_write_intent(
            {"task": "analyze then pause AG4", "tools": []}))
        self.assertFalse(chat_orchestrator._detect_write_intent(
            {"task": "report on last week's trends", "tools": []}))

    def test_tool_heuristic(self):
        self.assertTrue(chat_orchestrator._detect_write_intent(
            {"task": "handle it", "tools": ["google_ads__mutate_campaign"]}))
        self.assertFalse(chat_orchestrator._detect_write_intent(
            {"task": "review it", "tools": ["search__execute_query"]}))


# ── turn-budget: $5 WATCH notice (informational) + runaway BACKSTOP wrap-up ──
class BudgetWrapup(_Base):
    """Retuned budget (2026-07-16, Wassim: on CLI/subscription — no hard limit,
    but SHOW when a turn passes $5). Crossing the $5 WATCH level emits a quiet
    kind='notice' and the turn KEEPS running; only the $50/15-min runaway
    BACKSTOP degrades DISPATCH and emits a kind='stop' + COMPLETE wrap-up (never
    a mid-sentence cut, never a wasted LLM synth past the cap)."""

    async def test_watch_notice_emitted_and_turn_keeps_running(self):
        # A single specialist crosses the $5 WATCH level (cost 6.0) but stays well
        # under the $50 backstop → ONE kind='notice', NOTHING cancelled/degraded,
        # and the LLM synthesis still runs to completion.
        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = _text_call(
            'Bids ok.\n```json\n{"findings":[],"summary":"bids fine"}\n```', cost=6.0)
        synth = _text_call("Reconciled: bids are fine, keep steady.", cost=0.1)
        _SCRIPT.extend([plan, spec, synth])
        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my bidding across the whole campaign in depth")

        notices = [e for e in events if e["type"] == "budget_notice"]
        self.assertEqual(len(notices), 1, "exactly one WATCH-level budget_notice")
        p = notices[0]["payload"]
        self.assertEqual(p["kind"], "notice")
        self.assertEqual(p["reason"], "cost")
        self.assertAlmostEqual(p["cap_usd"], 5.0)          # WATCH level, not the $50 backstop
        # Nothing was stopped: no kind='stop', every specialist finished ok.
        self.assertFalse([n for n in notices if n["payload"].get("kind") == "stop"])
        results = [e for e in events if e["type"] == "agent_result"]
        self.assertTrue(results and all(
            r["payload"]["status"] == "ok" for r in results),
            "no specialist was cancelled — the turn kept running")
        # The Director's LLM synthesis ran (NOT the deterministic wrap-up).
        final_text = "".join(
            e["payload"].get("content", "")
            for e in events if e["type"] == "final_chunk")
        self.assertIn("Reconciled: bids are fine", final_text)
        self.assertNotIn("Turn budget reached", final_text)

    async def test_backstop_blown_emits_stop_and_complete_wrapup(self):
        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze bids"}]}\n```')
        # This specialist alone blows the $50 backstop (cost 60.0) → S6 must take
        # the deterministic wrap-up path. NO synth entry is scripted: if the code
        # wrongly called the LLM, the fake would return the bland "ok".
        spec = [
            {"type": "text", "content":
                "Bids look high.\n```json\n{\"findings\":[{\"claim\":\"cut AG4 bids\","
                "\"severity\":\"high\",\"confidence\":0.8,\"sources\":[\"ctx\"],"
                "\"disconfirmed_by\":\"a volume drop\"}],"
                "\"summary\":\"AG4 bids are too high\"}\n```"},
            {"type": "done", "cost": 60.0},
        ]
        _SCRIPT.extend([plan, spec])  # deliberately NO synth entry
        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my bidding across the whole campaign in depth")
        types = self.types(events)

        notices = [e for e in events if e["type"] == "budget_notice"]
        self.assertTrue(notices, "a visible budget_notice must be emitted")
        stop = [n for n in notices if n["payload"].get("kind") == "stop"]
        self.assertTrue(stop, "the runaway backstop must emit a kind='stop' notice")
        for k in ("kind", "reason", "cost", "cap_usd", "elapsed_s", "cap_s",
                  "specialists_done", "specialists_total"):
            self.assertIn(k, stop[0]["payload"])
        self.assertEqual(stop[0]["payload"]["reason"], "cost")
        self.assertAlmostEqual(stop[0]["payload"]["cap_usd"], 50.0)  # the backstop cap

        final_text = "".join(
            e["payload"].get("content", "")
            for e in events if e["type"] == "final_chunk")
        self.assertIn("Turn budget reached", final_text)      # complete wrap-up header
        self.assertIn("AG4 bids are too high", final_text)     # summary FROM STATE
        self.assertNotIn("ok", final_text)                     # no LLM synth ran
        # A clean terminal — the turn ends on a whole thought, not mid-sentence.
        self.assertSubsequence(["final_start", "final_done", "turn_done"], types)

    async def test_within_budget_runs_llm_synthesis_no_notice(self):
        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = _text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```', cost=0.1)
        synth = _text_call("Reconciled: keep bids steady.", cost=0.1)
        _SCRIPT.extend([plan, spec, synth])
        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my bidding across the whole campaign in depth")
        self.assertFalse([e for e in events if e["type"] == "budget_notice"])
        final_text = "".join(
            e["payload"].get("content", "")
            for e in events if e["type"] == "final_chunk")
        self.assertIn("Reconciled: keep bids steady.", final_text)


# ── retuned budget: config defaults (soft $5 watch, $50/15-min backstop) ──
class BudgetConfigDefaults(unittest.TestCase):
    """Lock the retuned defaults (2026-07-16): a $5 informational WATCH level and
    a high $50 / 15-min RUNAWAY backstop — never the other way around."""

    def test_defaults(self):
        self.assertEqual(settings.CHAT_ORCH_COST_NOTICE_USD, 5.0)
        self.assertEqual(settings.CHAT_ORCH_COST_CAP_USD, 50.0)
        self.assertEqual(settings.CHAT_ORCH_MAX_RUNTIME_MIN, 15.0)
        # The watch level must sit well below the runaway backstop, and the synth
        # reserve must fit inside the cap so DISPATCH always keeps headroom.
        self.assertLess(
            settings.CHAT_ORCH_COST_NOTICE_USD, settings.CHAT_ORCH_COST_CAP_USD)
        self.assertLess(
            settings.CHAT_ORCH_SYNTH_RESERVE_USD, settings.CHAT_ORCH_COST_CAP_USD)


# ── Fix 2: meta-question triage + degrade renders a real answer ───────
class MetaQuestionRouting(_Base):
    async def test_meta_question_routes_direct_under_orchestrate(self):
        # "why did you stop?" is a meta aside → DIRECT even with the orchestrate
        # toggle ON: no recall / verify / plan / dispatch, and a rendered answer.
        _SCRIPT.extend([_text_call("I hit the turn budget and wrapped up.")])
        events = await self._run(
            force_mode="orchestrate", user_message="why did you stop?")
        types = self.types(events)
        starts = [e for e in events if e["type"] == "turn_start"]
        self.assertEqual(starts[0]["payload"]["mode"], "direct")
        for t in ("plan", "agent_called", "memory_recall", "verification"):
            self.assertNotIn(t, types)
        final_text = "".join(
            e["payload"].get("content", "")
            for e in events if e["type"] == "final_chunk")
        self.assertIn("wrapped up", final_text)                 # rendered as final_*
        self.assertIn("turn_done", types)

    async def test_degrade_renders_final_answer_not_just_notice(self):
        # Fix 2b: an unparseable plan degrades to a DIRECT answer that MUST render
        # as final_* (the orchestrated bubble ignores plain `text`).
        plan = _text_call("Sorry, prose only, no JSON here.")
        direct = _text_call("Here is a real direct answer with substance.")
        _SCRIPT.extend([plan, direct])
        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my entire account in great detail right now")
        types = self.types(events)
        self.assertNotIn("agent_called", types)
        self.assertTrue(any(
            e["type"] == "director_thought"
            and "degrading" in (e["payload"].get("text") or "")
            for e in events), "the degrade notice must still be shown")
        final_text = "".join(
            e["payload"].get("content", "")
            for e in events if e["type"] == "final_chunk")
        self.assertIn("real direct answer", final_text)         # answer renders
        self.assertNotIn("text", types)                         # no unrendered text leak
        self.assertSubsequence(["final_start", "final_done", "turn_done"], types)


# ── Fix 3: read-only tool whitelist for chat-dispatched specialists ───
class SpecialistToolScoping(_Base):
    async def test_dispatched_specialist_gets_readonly_whitelist(self):
        captured: list[dict] = []

        async def _capturing(*args, **kwargs):
            captured.append(kwargs)
            events = _SCRIPT.pop(0) if _SCRIPT else [
                {"type": "text", "content": "ok"}, {"type": "done", "cost": 0.0}]
            for e in events:
                yield e

        agent_mod.stream_agent_response = _capturing
        plan = _text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = _text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = _text_call("done")
        _SCRIPT.extend([plan, spec, synth])
        await self._run(
            force_mode="orchestrate",
            user_message="audit my conversion actions across the campaign in depth")

        spec_calls = [k for k in captured if k.get("active_role") == "ppc_strategist"]
        self.assertTrue(spec_calls, "the specialist must have been dispatched")
        allow = spec_calls[0].get("tool_allowlist") or []
        self.assertIn("search__execute_query", allow)           # a SELECT is reachable
        self.assertNotIn("campaign__update_campaign", allow)    # a mutate is NOT reachable
        # The Director's synth/plan stages stay tool-less (reconciliation only).
        director_calls = [k for k in captured if k.get("active_role") == "director"]
        self.assertTrue(director_calls)
        for k in director_calls:
            self.assertEqual(k.get("tool_allowlist"), [])


class SpecialistWhitelistUnit(unittest.TestCase):
    def test_readonly_whitelist_grants_select_no_mutate(self):
        allow = chat_orchestrator._specialist_tool_allowlist([])
        self.assertIn("search__execute_query", allow)
        self.assertFalse(any(
            ("update" in a) or ("mutate" in a) or ("create" in a) or ("remove" in a)
            for a in allow), "the read-only whitelist must contain no mutate tools")

    def test_plan_authorized_mutate_is_unioned(self):
        allow = chat_orchestrator._specialist_tool_allowlist(["campaign__update_campaign"])
        self.assertIn("search__execute_query", allow)            # reads granted
        self.assertIn("campaign__update_campaign", allow)        # plan's tool preserved

    def test_meta_question_detection(self):
        for m in ("why did you stop?", "why the plan stopped", "what happened",
                  "what did you just do?", "repeat that", "why you stopped",
                  "you got cut off", "finish your thought"):
            self.assertTrue(chat_orchestrator._is_meta_question(m), m)
        for m in ("what happened to my conversions last week?",
                  "should I pause AG4?", "increase budget on AG2 by 20%",
                  "audit my whole account in depth", ""):
            self.assertFalse(chat_orchestrator._is_meta_question(m), m)


class MiddlewareReadOnlyEnforcement(unittest.IsolatedAsyncioTestCase):
    """The REAL MCP middleware: given the read-only whitelist, a GAQL SELECT tool
    passes and a mutate tool is blocked (Fix 3 acceptance test)."""

    def _load_middleware(self):
        import sys as _sys
        from unittest import mock as _mock
        # argparse runs at import — feed clean argv so it parses (default groups).
        with _mock.patch.object(_sys, "argv", ["mcp_main.py"]):
            from google_ads.mcp_main import CampaignScopeMiddleware
        return CampaignScopeMiddleware

    async def _call(self, mw, tool_name, sentinel):
        import types as _types
        ctx = _types.SimpleNamespace(
            message=_types.SimpleNamespace(name=tool_name, arguments={}))

        async def _next(_c):
            return sentinel

        return await mw.on_call_tool(ctx, _next)

    async def test_whitelist_allows_select_blocks_mutate(self):
        import os
        mw = self._load_middleware()()
        allow = ",".join(chat_orchestrator._specialist_tool_allowlist([]))
        old_allow = os.environ.get("LANGAR_AGENT_TOOL_ALLOWLIST")
        old_bound = os.environ.get("LANGAR_BOUND_CAMPAIGN_ID")
        os.environ["LANGAR_AGENT_TOOL_ALLOWLIST"] = allow
        os.environ.pop("LANGAR_BOUND_CAMPAIGN_ID", None)
        sentinel = object()
        try:
            got = await self._call(mw, "search__execute_query", sentinel)
            self.assertIs(got, sentinel)                        # SELECT reachable
            with self.assertRaises(ValueError) as cm:
                await self._call(mw, "campaign__update_campaign", sentinel)
            self.assertIn("TOOL_NOT_ALLOWED", str(cm.exception))  # mutate blocked
        finally:
            if old_allow is None:
                os.environ.pop("LANGAR_AGENT_TOOL_ALLOWLIST", None)
            else:
                os.environ["LANGAR_AGENT_TOOL_ALLOWLIST"] = old_allow
            if old_bound is not None:
                os.environ["LANGAR_BOUND_CAMPAIGN_ID"] = old_bound


class ExecuteQueryReadOnlyGuard(unittest.IsolatedAsyncioTestCase):
    """The GAQL query tool is constrained to SELECT — a non-SELECT is rejected
    BEFORE any API call (Fix 3 defense-in-depth on the read surface)."""

    class _Ctx:
        async def log(self, *a, **k):  # FastMCP Context.log stand-in
            return None

    async def test_select_query_passes_guard(self):
        from google_ads.services.metadata.search_service import SearchService
        svc = SearchService()
        # A SELECT clears the guard; it then fails at self.client (no SDK in tests)
        # — proving the guard did NOT reject a legitimate read.
        with self.assertRaises(Exception) as cm:
            await svc.execute_query(self._Ctx(), "123", "SELECT campaign.id FROM campaign")
        self.assertNotIn("read-only", str(cm.exception))

    async def test_non_select_query_is_rejected(self):
        from google_ads.services.metadata.search_service import SearchService
        svc = SearchService()
        for q in ("DELETE FROM campaign", "UPDATE campaign SET x=1", "drop table", ""):
            with self.assertRaises(Exception) as cm:
                await svc.execute_query(self._Ctx(), "123", q)
            self.assertIn("read-only", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
