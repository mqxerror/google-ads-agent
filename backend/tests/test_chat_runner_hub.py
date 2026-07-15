"""Chat Orchestration v2 — chat_runner hub (Epic 1.1).

Covers the transport skeleton with a FAKE run_fn (async generator; no real
LLM/subprocess):
  - late subscriber gets full replay (reconnect-proof)
  - cursor=N replays only seq > N
  - a run survives a subscriber disconnect (detached task completes + persists)
  - batched persistence lands in chat_turn_events (survives restart)
  - envelope stamping: monotonic seq + (v, conversation_id, turn_id, ts)
  - stop marks chat_turns.status and emits terminal turn_stopped

Repo test style: stdlib unittest, REAL temp SQLite from init_db(), no live calls.

Run:  cd backend && .venv/bin/python -m unittest tests.test_chat_runner_hub -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="chat-runner-hub-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import chat_runner as cr          # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


async def _turn_status(turn_id: str) -> str | None:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT status FROM chat_turns WHERE turn_id = ?", (turn_id,)
        )
        row = await cur.fetchone()
        return row["status"] if row else None
    finally:
        await db.close()


async def _persisted_events(turn_id: str) -> list[tuple[int, str]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT seq, type FROM chat_turn_events WHERE turn_id = ? ORDER BY seq",
            (turn_id,),
        )
        return [(r["seq"], r["type"]) for r in await cur.fetchall()]
    finally:
        await db.close()


def _scripted_run_fn(events: list[dict], *, gate: asyncio.Event | None = None,
                     done: asyncio.Event | None = None):
    """Build a fake run_fn that yields a scripted event list. Optional `gate`
    pauses mid-stream (for disconnect tests); `done` is set at completion."""
    async def run_fn(*, turn_id: str):
        for i, e in enumerate(events):
            yield e
            if gate is not None and i == 1:
                await gate.wait()
        if done is not None:
            done.set()
    return run_fn


class HubReplayAndCursor(unittest.IsolatedAsyncioTestCase):
    async def test_late_subscriber_gets_full_replay(self):
        done = asyncio.Event()
        run_fn = _scripted_run_fn(
            [{"type": "turn_start", "payload": {"mode": "direct"}},
             {"type": "text", "payload": {"content": "hi"}},
             {"type": "turn_done", "payload": {"stop_reason": "natural"}}],
            done=done,
        )
        turn_id = await cr.start(run_fn, conversation_id="c-replay")
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.02)  # let the driver close the hub

        replay = [e async for e in cr.subscribe(turn_id)]
        self.assertEqual([e["type"] for e in replay],
                         ["turn_start", "text", "turn_done"])
        # Envelope shape: monotonic seq starting at 1, keyed by conversation+turn.
        self.assertEqual([e["seq"] for e in replay], [1, 2, 3])
        for e in replay:
            self.assertEqual(e["v"], 2)
            self.assertEqual(e["conversation_id"], "c-replay")
            self.assertEqual(e["turn_id"], turn_id)
            self.assertIn("ts", e)

    async def test_cursor_replays_only_after_cursor(self):
        done = asyncio.Event()
        run_fn = _scripted_run_fn(
            [{"type": "turn_start", "payload": {}},
             {"type": "text", "payload": {"content": "a"}},
             {"type": "text", "payload": {"content": "b"}},
             {"type": "turn_done", "payload": {}}],
            done=done,
        )
        turn_id = await cr.start(run_fn, conversation_id="c-cursor")
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.02)

        # cursor=2 → only seq 3 and 4.
        tail = [e async for e in cr.subscribe(turn_id, cursor=2)]
        self.assertEqual([e["seq"] for e in tail], [3, 4])

    async def test_run_survives_subscriber_disconnect(self):
        gate = asyncio.Event()
        done = asyncio.Event()
        run_fn = _scripted_run_fn(
            [{"type": "turn_start", "payload": {}},
             {"type": "text", "payload": {"content": "mid"}},
             {"type": "text", "payload": {"content": "after-disconnect"}},
             {"type": "turn_done", "payload": {}}],
            gate=gate, done=done,
        )
        turn_id = await cr.start(run_fn, conversation_id="c-disc")

        # Subscribe, read two events, then abandon the iterator (client closes).
        agen = cr.subscribe(turn_id)
        seen = [await agen.__anext__(), await agen.__anext__()]
        await agen.aclose()
        self.assertEqual([e["type"] for e in seen], ["turn_start", "text"])

        # Release the gate — the detached task must finish regardless.
        gate.set()
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.02)

        hub = cr._chat_hubs.get(turn_id)
        self.assertIsNotNone(hub)
        self.assertIn("turn_done", [e["type"] for e in hub.buffer])
        self.assertTrue(hub.done.is_set())
        self.assertEqual(await _turn_status(turn_id), "done")

    async def test_batched_persistence_lands_in_db(self):
        done = asyncio.Event()
        # 25 events forces at least one size-based flush (flush_count=20 default).
        events = [{"type": "text", "payload": {"i": i}} for i in range(24)]
        events.append({"type": "turn_done", "payload": {}})
        run_fn = _scripted_run_fn(events, done=done)
        turn_id = await cr.start(run_fn, conversation_id="c-persist")
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.05)  # let the final flush land

        rows = await _persisted_events(turn_id)
        self.assertEqual(len(rows), 25)
        self.assertEqual([s for s, _ in rows], list(range(1, 26)))  # contiguous seq
        self.assertEqual(rows[-1][1], "turn_done")

    async def test_get_events_reads_from_db(self):
        done = asyncio.Event()
        run_fn = _scripted_run_fn(
            [{"type": "turn_start", "payload": {"mode": "direct"}},
             {"type": "turn_done", "payload": {}}],
            done=done,
        )
        turn_id = await cr.start(run_fn, conversation_id="c-getev")
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.05)

        evs = await cr.get_events(turn_id)
        self.assertEqual([e["type"] for e in evs], ["turn_start", "turn_done"])
        self.assertEqual(evs[0]["conversation_id"], "c-getev")
        self.assertEqual(evs[0]["payload"], {"mode": "direct"})


class HubStop(unittest.IsolatedAsyncioTestCase):
    async def test_stop_marks_status_and_emits_turn_stopped(self):
        started = asyncio.Event()

        async def hang_run_fn(*, turn_id: str):
            yield {"type": "turn_start", "payload": {}}
            started.set()
            await asyncio.sleep(30)  # hang until cancelled
            yield {"type": "turn_done", "payload": {}}  # never reached

        turn_id = await cr.start(hang_run_fn, conversation_id="c-stop")
        await asyncio.wait_for(started.wait(), timeout=2.0)

        res = await cr.stop_turn(turn_id)
        self.assertEqual(res["status"], "stopped")
        self.assertEqual(await _turn_status(turn_id), "stopped")

        # Terminal turn_stopped was emitted + persisted.
        evs = await cr.get_events(turn_id)
        self.assertIn("turn_stopped", [e["type"] for e in evs])

    async def test_stop_terminal_turn_is_already_done(self):
        done = asyncio.Event()
        run_fn = _scripted_run_fn(
            [{"type": "turn_start", "payload": {}},
             {"type": "turn_done", "payload": {}}],
            done=done,
        )
        turn_id = await cr.start(run_fn, conversation_id="c-stop2")
        await asyncio.wait_for(done.wait(), timeout=2.0)
        await asyncio.sleep(0.02)
        # Task already finished → stop flips nothing, reports already_done.
        res = await cr.stop_turn(turn_id)
        self.assertEqual(res["status"], "already_done")


if __name__ == "__main__":
    unittest.main()
