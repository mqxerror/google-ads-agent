"""Chat Orchestration v2 — the ISOLATION ACCEPTANCE TEST (story 1.6) + proc
registry stop routing (story 1.5/2.6). This is the F7 regression gate.

Two turns in two DIFFERENT conversations, each with its own fake run_fn emitting
a known event sequence into its own hub. Asserts:
  - each subscribe(turnA) sees ONLY turnA's events; subscribe(turnB) ONLY turnB's
  - stop_turn(turnA) → turnA gets terminal turn_stopped; turnB's stream is
    byte-identical to an undisturbed run and completes normally
  - the GET-stream 404 guard rejects a turn whose conversation_id != path

Plus the proc-registry stop routing with FAKE Popen objects injected into
agent._turn_procs (NEVER a real child):
  - stop_turn kills all of a turn's fake procs
  - stop_call kills exactly one call's proc
  - idempotent second call is a no-op
  - a (turn,"*") stop request blocks a would-be continuation (the guard helper
    returns the stop path)

Run:  cd backend && .venv/bin/python -m unittest tests.test_chat_stop_isolation -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="chat-stop-isolation-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import chat_runner as cr          # noqa: E402
from app.services import agent                       # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


# ── A) HUB-LEVEL ISOLATION ACCEPTANCE (story 1.6) ══════════════════════


class IsolationAcceptance(unittest.IsolatedAsyncioTestCase):
    async def test_two_turns_no_event_bleed_and_stop_isolation(self):
        # Turn A hangs (so we can stop it mid-flight); Turn B runs to completion.
        a_started = asyncio.Event()
        b_done = asyncio.Event()

        async def run_a(*, turn_id: str):
            yield {"type": "turn_start", "payload": {"who": "A"}}
            a_started.set()
            await asyncio.sleep(30)                   # hang until stopped
            yield {"type": "turn_done", "payload": {}}  # never reached

        # A KNOWN, fixed sequence for B — used to assert byte-identity.
        B_SEQUENCE = [
            {"type": "turn_start", "payload": {"who": "B"}},
            {"type": "text", "payload": {"content": "B-1"}},
            {"type": "text", "payload": {"content": "B-2"}},
            {"type": "turn_done", "payload": {"stop_reason": "natural"}},
        ]

        async def run_b(*, turn_id: str):
            for e in B_SEQUENCE:
                yield e
            b_done.set()

        turn_a = await cr.start(run_a, conversation_id="conv-A", campaign_id="camp-A")
        turn_b = await cr.start(run_b, conversation_id="conv-B", campaign_id="camp-B")
        self.assertNotEqual(turn_a, turn_b)

        await asyncio.wait_for(a_started.wait(), timeout=2.0)
        await asyncio.wait_for(b_done.wait(), timeout=2.0)
        await asyncio.sleep(0.02)

        # NO BLEED: A's stream carries only A's events (before we stop it).
        a_events = cr._chat_hubs[turn_a].buffer
        self.assertTrue(all(e["turn_id"] == turn_a for e in a_events))
        self.assertTrue(all(e["conversation_id"] == "conv-A" for e in a_events))
        self.assertNotIn("B", [e["payload"].get("who") for e in a_events if e["type"] == "turn_start"] or [None])

        # B's replay is EXACTLY its known sequence — undisturbed by A running.
        b_replay = [e async for e in cr.subscribe(turn_b)]
        self.assertEqual([e["type"] for e in b_replay], [e["type"] for e in B_SEQUENCE])
        self.assertEqual([e["payload"] for e in b_replay], [e["payload"] for e in B_SEQUENCE])
        self.assertTrue(all(e["conversation_id"] == "conv-B" for e in b_replay))
        self.assertTrue(all(e["turn_id"] == turn_b for e in b_replay))

        # STOP A → A gets terminal turn_stopped; B is completely unaffected.
        b_before = list(cr._chat_hubs[turn_b].buffer)
        res = await cr.stop_turn(turn_a)
        self.assertEqual(res["status"], "stopped")
        await asyncio.sleep(0.02)

        a_types = [e["type"] for e in cr._chat_hubs[turn_a].buffer]
        self.assertIn("turn_stopped", a_types)

        # B's buffer is byte-identical to before A's stop (no bleed of turn_stopped).
        b_after = cr._chat_hubs[turn_b].buffer
        self.assertEqual(b_before, b_after)
        self.assertNotIn("turn_stopped", [e["type"] for e in b_after])

    async def test_stream_404_guard_rejects_cross_conversation(self):
        """The GET-stream / events endpoints 404 when the turn's conversation_id
        != the path conversation. This is enforced in the router via the turn
        row lookup — assert the invariant on the persisted row directly."""
        done = asyncio.Event()

        async def run_fn(*, turn_id: str):
            yield {"type": "turn_start", "payload": {}}
            yield {"type": "turn_done", "payload": {}}
            done.set()

        turn_id = await cr.start(run_fn, conversation_id="conv-real")
        await asyncio.wait_for(done.wait(), timeout=2.0)

        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT conversation_id FROM chat_turns WHERE turn_id = ?", (turn_id,)
            )
            row = await cur.fetchone()
        finally:
            await db.close()
        # The turn belongs to conv-real; a request under conv-imposter would 404.
        self.assertEqual(row["conversation_id"], "conv-real")
        self.assertNotEqual(row["conversation_id"], "conv-imposter")


# ── A2) STOP WRITE-DISPOSITION (Fix 1 — P0 safety) ═════════════════════


class StopWriteDisposition(unittest.IsolatedAsyncioTestCase):
    """A stopped turn must report, per write-intent specialist, whether the
    approved write completed or was cut off — an approved write must never die
    silently. _drive observes agent_called(+write_intent)/agent_result through
    _emit and folds the result into the terminal turn_stopped payload."""

    def _turn_stopped(self, turn_id):
        buf = cr._chat_hubs[turn_id].buffer
        evs = [e for e in buf if e["type"] == "turn_stopped"]
        self.assertTrue(evs, "expected a terminal turn_stopped event")
        return evs[-1]["payload"]

    async def test_in_flight_write_specialist_reports_stopped_before_write(self):
        # A specialist was dispatched with write_intent, streamed "Pushing all 20
        # negatives now", then the turn hung — user presses stop before agent_result.
        started = asyncio.Event()

        async def run_fn(*, turn_id: str):
            yield {"type": "turn_start", "payload": {"mode": "orchestrated"}}
            yield {"type": "agent_called", "payload": {
                "call_id": "c1", "role_id": "ppc_strategist",
                "role_name": "PPC Strategist", "task": "push 20 negatives",
                "model": "sonnet", "tools": ["mutate"], "write_intent": True}}
            yield {"type": "agent_progress", "payload": {
                "call_id": "c1", "kind": "text",
                "content": "Pushing all 20 negatives now"}}
            started.set()
            await asyncio.sleep(30)              # hang until stopped (write never lands)
            yield {"type": "agent_result", "payload": {"call_id": "c1"}}  # never reached

        turn_id = await cr.start(run_fn, conversation_id="conv-w1", campaign_id="c")
        await asyncio.wait_for(started.wait(), timeout=2.0)
        await asyncio.sleep(0.02)

        res = await cr.stop_turn(turn_id)
        self.assertEqual(res["status"], "stopped")
        await asyncio.sleep(0.02)

        payload = self._turn_stopped(turn_id)
        # Existing keys preserved.
        self.assertEqual(payload["stopped_by"], "user")
        self.assertTrue(payload["partial_persisted"])
        # The write-intent specialist is reported as NOT executed.
        specs = payload["specialists"]
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["role_id"], "ppc_strategist")
        self.assertEqual(specs[0]["role_name"], "PPC Strategist")
        self.assertEqual(specs[0]["disposition"], "stopped_before_write")

    async def test_completed_write_specialist_reports_completed(self):
        # A write-intent specialist that FINISHED (agent_result seen) before a
        # later stop shows disposition 'completed'; a pure-read specialist that
        # never had write_intent produces NO warning entry.
        both_started = asyncio.Event()

        async def run_fn(*, turn_id: str):
            yield {"type": "turn_start", "payload": {"mode": "orchestrated"}}
            # write-intent specialist that completes
            yield {"type": "agent_called", "payload": {
                "call_id": "c1", "role_id": "ppc_strategist",
                "role_name": "PPC Strategist", "task": "push 20 negatives",
                "model": "sonnet", "tools": ["mutate"], "write_intent": True}}
            yield {"type": "agent_result", "payload": {
                "call_id": "c1", "role_id": "ppc_strategist", "status": "ok"}}
            # a pure-read specialist (no write_intent) — must NOT warn
            yield {"type": "agent_called", "payload": {
                "call_id": "c2", "role_id": "analytics_analyst",
                "role_name": "Analytics Analyst", "task": "report trends",
                "model": "sonnet", "tools": [], "write_intent": False}}
            both_started.set()
            await asyncio.sleep(30)              # hang until stopped
            yield {"type": "turn_done", "payload": {}}  # never reached

        turn_id = await cr.start(run_fn, conversation_id="conv-w2", campaign_id="c")
        await asyncio.wait_for(both_started.wait(), timeout=2.0)
        await asyncio.sleep(0.02)

        await cr.stop_turn(turn_id)
        await asyncio.sleep(0.02)

        specs = self._turn_stopped(turn_id)["specialists"]
        # Only the write-intent specialist appears; it is 'completed'.
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["role_id"], "ppc_strategist")
        self.assertEqual(specs[0]["disposition"], "completed")

    async def test_no_write_specialist_gives_empty_list(self):
        # The common safe case: no write-intent specialist in flight → empty list,
        # existing keys intact.
        started = asyncio.Event()

        async def run_fn(*, turn_id: str):
            yield {"type": "turn_start", "payload": {"mode": "orchestrated"}}
            yield {"type": "agent_called", "payload": {
                "call_id": "c1", "role_id": "analytics_analyst",
                "role_name": "Analytics Analyst", "task": "report trends",
                "model": "sonnet", "tools": [], "write_intent": False}}
            started.set()
            await asyncio.sleep(30)
            yield {"type": "turn_done", "payload": {}}

        turn_id = await cr.start(run_fn, conversation_id="conv-w3", campaign_id="c")
        await asyncio.wait_for(started.wait(), timeout=2.0)
        await asyncio.sleep(0.02)
        await cr.stop_turn(turn_id)
        await asyncio.sleep(0.02)

        payload = self._turn_stopped(turn_id)
        self.assertEqual(payload["specialists"], [])
        self.assertEqual(payload["stopped_by"], "user")


# ── B) PROC REGISTRY STOP ROUTING (story 1.5 / 2.6) ════════════════════


class _FakePopen:
    """A stand-in for subprocess.Popen. NEVER spawns a real child. Records that
    its process group was 'killed' so the tests can assert routing without ever
    touching os.killpg / real PIDs."""

    _next_pid = 100000

    def __init__(self):
        _FakePopen._next_pid += 1
        self.pid = _FakePopen._next_pid
        self.killed = False

    def wait(self, timeout=None):
        return 0


class ProcRegistryStopRouting(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Clean registries + monkeypatch the killpg helper to mark fakes instead
        # of signalling real process groups. Restored in tearDown.
        agent._turn_procs.clear()
        agent._turn_stop_requested.clear()
        self._orig_killpg = agent._killpg

        def _fake_killpg(proc):
            proc.killed = True
            return True

        agent._killpg = _fake_killpg

    def tearDown(self):
        agent._killpg = self._orig_killpg
        agent._turn_procs.clear()
        agent._turn_stop_requested.clear()

    def test_stop_turn_kills_all_turn_procs(self):
        c1a, c1b, c2 = _FakePopen(), _FakePopen(), _FakePopen()
        # Turn T1 has two calls (c1 has two procs — e.g. a continuation), T2 one.
        agent._turn_procs[("T1", "c1")] = {c1a, c1b}
        agent._turn_procs[("T1", "c2")] = {c2}
        other = _FakePopen()
        agent._turn_procs[("T2", "c1")] = {other}

        res = agent.stop_turn("T1")

        self.assertTrue(c1a.killed and c1b.killed and c2.killed)
        self.assertFalse(other.killed)               # a different turn is untouched
        self.assertEqual(sorted(res["killed"]), ["c1", "c2"])
        # T1's keys are popped; T2 remains; whole-turn stop flag set.
        self.assertNotIn(("T1", "c1"), agent._turn_procs)
        self.assertNotIn(("T1", "c2"), agent._turn_procs)
        self.assertIn(("T2", "c1"), agent._turn_procs)
        self.assertIn(("T1", "*"), agent._turn_stop_requested)

    def test_stop_call_kills_exactly_one_call(self):
        c1, c2 = _FakePopen(), _FakePopen()
        agent._turn_procs[("T1", "c1")] = {c1}
        agent._turn_procs[("T1", "c2")] = {c2}

        res = agent.stop_call("T1", "c1")

        self.assertTrue(c1.killed)
        self.assertFalse(c2.killed)                  # sibling call keeps running
        self.assertTrue(res["killed"])
        self.assertNotIn(("T1", "c1"), agent._turn_procs)
        self.assertIn(("T1", "c2"), agent._turn_procs)      # sibling untouched
        # Only c1 is flagged; the whole turn is NOT flagged (turn continues).
        self.assertIn(("T1", "c1"), agent._turn_stop_requested)
        self.assertNotIn(("T1", "*"), agent._turn_stop_requested)

    def test_idempotent_second_stop_is_noop(self):
        c1 = _FakePopen()
        agent._turn_procs[("T1", "c1")] = {c1}
        first = agent.stop_turn("T1")
        self.assertEqual(first["killed"], ["c1"])
        # Second call: nothing left to kill.
        second = agent.stop_turn("T1")
        self.assertEqual(second["killed"], [])

    def test_stop_request_blocks_continuation_guard(self):
        """A (turn,"*") stop request makes the continuation guard return the
        stop path — the mechanism that defeats the between-segments relaunch
        race by construction (story 1.5)."""
        key = ("T-guard", "director")
        # Before any stop: guard says 'do not stop'.
        self.assertFalse(agent._turn_stop_pending(key))
        # A per-call stop for a DIFFERENT call must not block this one.
        agent._turn_stop_requested.add(("T-guard", "other"))
        self.assertFalse(agent._turn_stop_pending(key))
        # The call's own stop blocks it.
        agent._turn_stop_requested.add(key)
        self.assertTrue(agent._turn_stop_pending(key))
        # A whole-turn stop blocks EVERY call under the turn.
        agent._turn_stop_requested.clear()
        agent._turn_stop_requested.add(("T-guard", "*"))
        self.assertTrue(agent._turn_stop_pending(("T-guard", "director")))
        self.assertTrue(agent._turn_stop_pending(("T-guard", "c1")))
        # None proc_key (direct/legacy callers) is never blocked by the v2 flag.
        self.assertFalse(agent._turn_stop_pending(None))


if __name__ == "__main__":
    unittest.main()
