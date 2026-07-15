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
        agent_mod.stream_agent_response = _fake_stream_factory()
        agent_mod.fetch_ad_landing_pages = _fake_fetch

    def tearDown(self):
        agent_mod.stream_agent_response = self._orig_stream
        agent_mod.fetch_ad_landing_pages = self._orig_fetch

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


if __name__ == "__main__":
    unittest.main()
