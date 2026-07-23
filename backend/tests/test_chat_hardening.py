"""Chat-hardening batch — item 2 (degrade visibility) + item 4 (same-conversation
turn serialization) + add-ons.

Stdlib unittest, NO network, NO real LLM/CLI.

Item 2 reuses the test_chat_orchestrator scripted-fake harness (tco). The harness
already makes the conversion-registry fetch return empty, so EVERY orchestrated
run degrades that path — we assert the new `degrade` event + the caveat woven
into the Director's synthesis prompt. Recall failure is forced separately.

Item 4 drives chat_runner directly with a controllable run_fn (gated by an
asyncio.Event we own), proving: a 2nd non-identical message is QUEUED (never two
live turns), an identical re-send is deduped, and stopping the running turn
starts the queued one.

Run:  cd backend && python -m unittest tests.test_chat_hardening -v
"""

from __future__ import annotations

import asyncio
import unittest
import uuid

from app.database import get_db, init_db
from app.services import chat_runner
from app.services.chat_orchestrator import _compose_budget_wrapup

from tests import test_chat_orchestrator as tco  # sets DATA_DIR + provides harness


def setUpModule():
    tco._TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


# ─────────────────────────── item 2 — degrade ──────────────────────────
class DegradeVisibility(tco._Base):
    def _script_one_specialist(self, final="Here is the answer."):
        plan = tco._text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"x"}]}\n```')
        spec = tco._text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = tco._text_call(final)
        tco._SCRIPT.extend([plan, spec, synth])

    async def test_conversion_registry_failure_emits_degrade(self):
        # Harness _fake_conv_fetch returns "",[] → live registry unavailable.
        self._script_one_specialist()
        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my whole tracking + conversions end to end please")
        degr = [e for e in events if e["type"] == "degrade"
                and e["payload"].get("stage") == "conversion_registry"]
        self.assertTrue(degr, "expected a conversion_registry degrade event")
        for k in ("what", "impact"):
            self.assertIn(k, degr[0]["payload"])

    async def test_recall_failure_emits_degrade(self):
        from app.services import task_ledger
        orig = task_ledger.recall

        async def _boom(*a, **k):
            raise RuntimeError("recall backend down")

        task_ledger.recall = _boom
        try:
            self._script_one_specialist()
            events = await self._run(
                force_mode="orchestrate",
                user_message="audit my whole account end to end please now")
        finally:
            task_ledger.recall = orig
        degr = [e for e in events if e["type"] == "degrade"
                and e["payload"].get("stage") == "recall"]
        self.assertTrue(degr, "recall failure must surface a degrade event")

    async def test_degrade_caveat_woven_into_synth_prompt(self):
        # Capture every prompt the (fake) LLM is asked; the conversion degrade
        # always fires here → the synth prompt MUST carry the caveat so the final
        # answer can name what was missing.
        captured: list[str] = []

        def _rec_factory():
            async def _fake(*a, **k):
                captured.append(k.get("user_message", ""))
                events = tco._SCRIPT.pop(0) if tco._SCRIPT else [
                    {"type": "text", "content": "ok"}, {"type": "done", "cost": 0.0}]
                for e in events:
                    yield e
            return _fake

        tco.agent_mod.stream_agent_response = _rec_factory()  # tearDown restores
        self._script_one_specialist()
        await self._run(force_mode="orchestrate",
                        user_message="audit my tracking and conversions end to end")
        synth = [c for c in captured if "Reconcile" in c]
        self.assertTrue(synth, "a synthesis prompt should have been issued")
        self.assertIn("DEGRADED THIS TURN", synth[0])

    async def test_degrade_survives_and_turn_completes(self):
        # A degrade never blocks — the turn still reaches turn_done.
        self._script_one_specialist()
        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my whole setup end to end please today")
        types = [e["type"] for e in events]
        self.assertIn("degrade", types)
        self.assertIn("turn_done", types)


class BudgetWrapupNamesDegradations(unittest.TestCase):
    def test_wrapup_lists_degradations(self):
        wrap = _compose_budget_wrapup(
            specs=[], findings_by_call={}, summary_by_call={}, conflicts=[],
            degradations=["conversion-action registry: live registry unavailable"])
        self.assertIn("Degraded this turn", wrap)
        self.assertIn("conversion-action registry", wrap)

    def test_wrapup_without_degradations_unchanged(self):
        wrap = _compose_budget_wrapup([], {}, {}, [])
        self.assertNotIn("Degraded this turn", wrap)


# ──────────────────── item 4 — turn serialization ──────────────────────
class Serialization(unittest.IsolatedAsyncioTestCase):
    async def _status(self, tid: str):
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT status FROM chat_turns WHERE turn_id = ?", (tid,))
            row = await cur.fetchone()
            return row["status"] if row else None
        finally:
            await db.close()

    async def test_second_message_queued_and_serialized(self):
        conv = f"conv-{uuid.uuid4()}"
        started: list[tuple[str, str]] = []
        gate_a, gate_b = asyncio.Event(), asyncio.Event()

        async def run_fn(*, turn_id, tag, release):
            started.append(("start", tag))
            yield {"type": "text", "payload": {"content": tag}}
            await release.wait()
            started.append(("end", tag))
            yield {"type": "turn_done", "payload": {}}

        tid_a = await chat_runner.start(
            run_fn, conversation_id=conv, mode="direct",
            origin_message="msg A", tag="A", release=gate_a)
        await asyncio.sleep(0.05)
        task_a = chat_runner._chat_tasks[tid_a]

        tid_b = await chat_runner.start(
            run_fn, conversation_id=conv, mode="direct",
            origin_message="msg B", tag="B", release=gate_b)
        await asyncio.sleep(0.05)
        task_b = chat_runner._chat_tasks[tid_b]

        # A running, B QUEUED — B's run_fn has NOT started (only A started).
        self.assertEqual(await self._status(tid_a), "running")
        self.assertEqual(await self._status(tid_b), "queued")
        self.assertEqual([s for s in started if s[0] == "start"], [("start", "A")])

        # B emitted the visible "queued" notice.
        evs_b = await chat_runner.get_events(tid_b)
        self.assertTrue(any(e["type"] == "turn_queued" for e in evs_b))

        # Finish A → B promotes to running and its run_fn starts.
        gate_a.set()
        await task_a
        await asyncio.sleep(0.05)
        self.assertEqual(await self._status(tid_a), "done")
        self.assertEqual(await self._status(tid_b), "running")

        gate_b.set()
        await task_b
        self.assertEqual(await self._status(tid_b), "done")

        # The two turns NEVER overlapped: A fully ran before B began.
        self.assertEqual(
            started, [("start", "A"), ("end", "A"), ("start", "B"), ("end", "B")])

    async def test_identical_message_deduped(self):
        conv = f"conv-{uuid.uuid4()}"
        gate = asyncio.Event()

        async def run_fn(*, turn_id, release):
            yield {"type": "text", "payload": {}}
            await release.wait()

        tid = await chat_runner.start(
            run_fn, conversation_id=conv, mode="direct",
            origin_message="same text", release=gate)
        await asyncio.sleep(0.02)
        task = chat_runner._chat_tasks[tid]

        # Identical content on the SAME conversation → reuse the live turn.
        self.assertEqual(chat_runner.find_duplicate_active_turn(conv, "same text"), tid)
        # Different content → not a dup (it would be queued instead).
        self.assertIsNone(chat_runner.find_duplicate_active_turn(conv, "other text"))
        # Same content, DIFFERENT conversation → not a dup.
        self.assertIsNone(
            chat_runner.find_duplicate_active_turn("elsewhere", "same text"))

        gate.set()
        await task
        # Once finished it is no longer a live dup target.
        self.assertIsNone(chat_runner.find_duplicate_active_turn(conv, "same text"))

    async def test_stop_running_turn_starts_the_queued_one(self):
        conv = f"conv-{uuid.uuid4()}"
        started: list[str] = []
        gate_a, gate_b = asyncio.Event(), asyncio.Event()

        async def run_fn(*, turn_id, tag, release):
            started.append(tag)
            yield {"type": "text", "payload": {"content": tag}}
            await release.wait()
            yield {"type": "turn_done", "payload": {}}

        tid_a = await chat_runner.start(
            run_fn, conversation_id=conv, mode="direct",
            origin_message="A", tag="A", release=gate_a)
        await asyncio.sleep(0.05)
        tid_b = await chat_runner.start(
            run_fn, conversation_id=conv, mode="direct",
            origin_message="B", tag="B", release=gate_b)
        task_b = chat_runner._chat_tasks[tid_b]
        await asyncio.sleep(0.05)
        self.assertEqual(started, ["A"])  # B queued, not started

        # Stopping the running turn hands off to the queued one.
        await chat_runner.stop_turn(tid_a)
        await asyncio.sleep(0.05)
        self.assertIn("B", started)
        self.assertEqual(await self._status(tid_a), "stopped")
        self.assertEqual(await self._status(tid_b), "running")

        gate_b.set()
        await task_b
        self.assertEqual(await self._status(tid_b), "done")

    async def test_no_predecessor_runs_immediately(self):
        conv = f"conv-{uuid.uuid4()}"
        gate = asyncio.Event()
        started: list[str] = []

        async def run_fn(*, turn_id, release):
            started.append("go")
            yield {"type": "text", "payload": {}}
            await release.wait()

        tid = await chat_runner.start(
            run_fn, conversation_id=conv, mode="direct",
            origin_message="solo", release=gate)
        await asyncio.sleep(0.05)
        # No predecessor → runs at once (status running, run_fn started).
        self.assertEqual(await self._status(tid), "running")
        self.assertEqual(started, ["go"])
        gate.set()
        await chat_runner._chat_tasks[tid]


# ─────────────────── add-on — chat_turn_events retention ────────────────
class RetentionPrune(unittest.IsolatedAsyncioTestCase):
    async def test_prune_removes_only_old_terminal_events(self):
        db = await get_db()
        try:
            # An OLD, finished turn + a FRESH finished turn + a RUNNING turn.
            await db.execute(
                "INSERT INTO chat_turns (turn_id, conversation_id, mode, status, "
                "finished_at) VALUES ('old', 'c', 'direct', 'done', "
                "datetime('now','-200 days'))")
            await db.execute(
                "INSERT INTO chat_turns (turn_id, conversation_id, mode, status, "
                "finished_at) VALUES ('fresh', 'c', 'direct', 'done', datetime('now'))")
            await db.execute(
                "INSERT INTO chat_turns (turn_id, conversation_id, mode, status) "
                "VALUES ('live', 'c', 'direct', 'running')")
            for tid in ("old", "fresh", "live"):
                await db.execute(
                    "INSERT INTO chat_turn_events (turn_id, seq, type, payload) "
                    "VALUES (?, 1, 'text', '{}')", (tid,))
            await db.commit()
        finally:
            await db.close()

        deleted = await chat_runner.prune_old_turn_events(retention_days=90)
        self.assertEqual(deleted, 1)  # only the 200-day-old terminal turn

        db = await get_db()
        try:
            cur = await db.execute("SELECT turn_id FROM chat_turn_events")
            remaining = {r["turn_id"] for r in await cur.fetchall()}
        finally:
            await db.close()
        self.assertNotIn("old", remaining)
        self.assertIn("fresh", remaining)
        self.assertIn("live", remaining)

    async def test_prune_disabled_when_zero(self):
        self.assertEqual(await chat_runner.prune_old_turn_events(retention_days=0), 0)


if __name__ == "__main__":
    unittest.main()
