"""P0 reliability — the /active-turn single-source-of-truth reconcile endpoint.

The chat has TWO turn engines and, before this endpoint, the frontend could
reconnect to only ONE of them (the legacy /agent/status), so a page refresh — or
a team↔individual mode switch — during a v2 "Ask the team" turn left the live
turn orphaned and the composer stale (the reported "refresh twice" bug).
GET /conversations/{id}/active-turn is the ONE truth the UI reconciles against,
spanning BOTH engines:

  * kind "v2"     — a running chat_turns row (orchestrated OR detached direct).
  * kind "direct" — a live in-process legacy ?stream=1 background send.
  * {active:false} — neither engine has a live run → the composer self-heals.

Repo test style: drive the async route function directly (no TestClient); REAL
temp SQLite via init_db; a fake gated run_fn (no LLM/subprocess).

Run: cd backend && .venv/bin/python -m unittest tests.test_active_turn_endpoint -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="active-turn-test-"))
settings.DATA_DIR = _TMP

from app.database import init_db          # noqa: E402
from app.services import chat_runner       # noqa: E402
from app.routers import chat as chat_router  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class ActiveTurnTruth(unittest.IsolatedAsyncioTestCase):
    async def test_idle_conversation_reports_inactive(self):
        conv = f"conv-{uuid.uuid4()}"
        res = await chat_router.active_turn(conv)
        self.assertEqual(res, {"active": False})

    async def test_running_v2_turn_reported_with_attach_info(self):
        conv = f"conv-{uuid.uuid4()}"
        gate = asyncio.Event()

        async def run_fn(*, turn_id, release):
            yield {"type": "final_chunk", "payload": {"content": "hi"}}
            await release.wait()
            yield {"type": "turn_done", "payload": {}}

        tid = await chat_runner.start(
            run_fn, conversation_id=conv, mode="orchestrated",
            origin_message="ask the team please", release=gate)
        await asyncio.sleep(0.05)
        try:
            res = await chat_router.active_turn(conv)
            self.assertTrue(res["active"])
            self.assertEqual(res["kind"], "v2")
            self.assertEqual(res["turn_id"], tid)
            self.assertEqual(res["mode"], "orchestrated")
            self.assertIn("last_seq", res)  # attach cursor hint present
        finally:
            gate.set()
            await chat_runner._chat_tasks[tid]
        # A finished turn is no longer active → composer goes idle.
        res2 = await chat_router.active_turn(conv)
        self.assertFalse(res2["active"])

    async def test_stopped_v2_turn_not_active(self):
        conv = f"conv-{uuid.uuid4()}"
        gate = asyncio.Event()

        async def run_fn(*, turn_id, release):
            yield {"type": "final_chunk", "payload": {}}
            await release.wait()

        tid = await chat_runner.start(
            run_fn, conversation_id=conv, mode="orchestrated",
            origin_message="x", release=gate)
        await asyncio.sleep(0.05)
        await chat_runner.stop_turn(tid)  # cancels the task, flips row → stopped
        res = await chat_router.active_turn(conv)
        self.assertFalse(res["active"])
        gate.set()  # harmless — the task is already cancelled

    async def test_legacy_direct_in_process_send_reported(self):
        conv = f"conv-{uuid.uuid4()}"
        # No v2 turn — simulate a live legacy ?stream=1 background task.
        loop_gate = asyncio.Event()

        async def _bg():
            await loop_gate.wait()

        task = asyncio.create_task(_bg())
        chat_router._agent_tasks[conv] = task
        chat_router._agent_done[conv] = False
        chat_router._agent_buffers[conv] = [{"type": "text", "content": "hi"}]
        try:
            res = await chat_router.active_turn(conv)
            self.assertTrue(res["active"])
            self.assertEqual(res["kind"], "direct")
            self.assertEqual(res["buffered_events"], 1)
        finally:
            loop_gate.set()
            await task
            chat_router._agent_tasks.pop(conv, None)
            chat_router._agent_done.pop(conv, None)
            chat_router._agent_buffers.pop(conv, None)
        # A finished/absent task → inactive.
        res2 = await chat_router.active_turn(conv)
        self.assertFalse(res2["active"])

    async def test_legacy_done_flag_reports_inactive(self):
        # A registered-but-DONE legacy task (or _agent_done set) is not active.
        conv = f"conv-{uuid.uuid4()}"
        done = asyncio.create_task(asyncio.sleep(0))
        await done
        chat_router._agent_tasks[conv] = done
        chat_router._agent_done[conv] = True
        try:
            res = await chat_router.active_turn(conv)
            self.assertFalse(res["active"])
        finally:
            chat_router._agent_tasks.pop(conv, None)
            chat_router._agent_done.pop(conv, None)

    async def test_v2_turn_wins_over_a_live_legacy_flag(self):
        # If BOTH engines somehow show activity, the durable v2 record wins — the
        # client attaches to the turn that actually owns the thread's state.
        conv = f"conv-{uuid.uuid4()}"
        gate = asyncio.Event()
        legacy_gate = asyncio.Event()

        async def run_fn(*, turn_id, release):
            yield {"type": "final_chunk", "payload": {}}
            await release.wait()
            yield {"type": "turn_done", "payload": {}}

        async def _bg():
            await legacy_gate.wait()

        tid = await chat_runner.start(
            run_fn, conversation_id=conv, mode="orchestrated",
            origin_message="x", release=gate)
        legacy_task = asyncio.create_task(_bg())
        chat_router._agent_tasks[conv] = legacy_task
        chat_router._agent_done[conv] = False
        await asyncio.sleep(0.05)
        try:
            res = await chat_router.active_turn(conv)
            self.assertEqual(res["kind"], "v2")
            self.assertEqual(res["turn_id"], tid)
        finally:
            legacy_gate.set()
            await legacy_task
            chat_router._agent_tasks.pop(conv, None)
            chat_router._agent_done.pop(conv, None)
            gate.set()
            await chat_runner._chat_tasks[tid]


if __name__ == "__main__":
    unittest.main()
