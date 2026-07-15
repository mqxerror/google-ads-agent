"""Chat turn runner — Chat Orchestration v2 foundation (Epic 1.1/1.5/1.6).

Structurally lifted from `workflow_runner.py` (the transport skeleton the plan
adopts, §D1). Same detached-task + replay-hub pattern; the differences are the
ones the SHARED BUILD CONTRACT pins:

  - WE mint the turn_id UP FRONT (uuid4) and insert the `chat_turns` row BEFORE
    launching — unlike workflow_runner, which reads run_id off the first event.
  - The detached task drives a passed-in async-generator `run_fn(turn_id=...,
    **params)` (so Epic 2's orchestrator plugs in later; for now the runner is
    generic over run_fn). Direct-mode wires run_fn to a thin stream_agent_response
    wrapper (see chat.py).
  - The runner OWNS the envelope: run_fn yields bare `{type, payload}`; the
    runner assigns a monotonic `seq` per turn and stamps
    `{v, conversation_id, turn_id, seq, ts}` around it (§4.3).
  - Events are flushed to `chat_turn_events` in batches (~20 events / 500 ms,
    whichever first; remainder flushed on close) so history replay survives a
    restart — fixing the process-local `_agent_buffers` loss (chat.py:35-38).
  - `subscribe(turn_id, cursor)` replays events with seq > cursor then tails.
  - Zombie sweep for `chat_turns` mirrors workflow_runner.sweep_zombies.
  - `stop_turn` / `stop_call` do BOTH the asyncio task lifecycle AND the
    process-level killpg (agent.stop_turn / agent.stop_call). agent.py is
    imported LAZILY to avoid an import cycle (it is heavy), mirroring how
    workflow_runner imports run_workflow.

Public API (Epic 2 + the frontend agent import these — keep precise):
    start(run_fn, *, conversation_id, campaign_id=None, mode="direct", **params) -> str
    subscribe(turn_id, cursor=0) -> AsyncIterator[dict]
    get_events(turn_id) -> list[dict]          # from DB (history replay)
    active_turns(conversation_id) -> list[dict]
    stop_turn(turn_id) -> dict
    stop_call(turn_id, call_id) -> dict
    sweep_chat_zombies() -> int
    start_sweeper() / stop_sweeper()           # periodic lifecycle
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# A sentinel that tells subscribers the stream is over. Never sent to clients.
_SENTINEL = object()

# The type of a run function: an async generator yielding bare {type, payload}
# events. It receives turn_id plus whatever params start() was given.
RunFn = Callable[..., AsyncIterator[dict]]


# ── Hub (== workflow_runner._RunHub, keyed by turn_id) ────────────────


class _ChatHub:
    """Fan-out buffer for one turn's events: replay history + live subscribers.

    The buffer holds fully-stamped envelopes (with seq), so a late/reconnecting
    subscriber replays the exact bytes an early subscriber saw. Closing a
    subscriber never kills the run (workflow_runner.subscribe contract).
    """

    def __init__(self) -> None:
        self.buffer: list[dict] = []          # every stamped envelope, in order
        self.subscribers: set[asyncio.Queue] = set()
        self.done = asyncio.Event()

    def publish(self, event: dict) -> None:
        self.buffer.append(event)
        for q in list(self.subscribers):
            q.put_nowait(event)

    def close(self) -> None:
        self.done.set()
        for q in list(self.subscribers):
            q.put_nowait(_SENTINEL)

    def subscribe(self, cursor: int = 0) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay everything with seq > cursor so a late/reconnecting viewer
        # catches up without re-seeing what it already has.
        for event in self.buffer:
            if event.get("seq", 0) > cursor:
                q.put_nowait(event)
        if self.done.is_set():
            q.put_nowait(_SENTINEL)
        else:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)


# turn_id → hub, and turn_id → task. Both live for the process; cleaned on finish.
_chat_hubs: dict[str, _ChatHub] = {}
_chat_tasks: dict[str, asyncio.Task] = {}


# ── Config helpers ────────────────────────────────────────────────────


def _max_runtime_minutes() -> float:
    try:
        return float(getattr(settings, "CHAT_ORCH_MAX_RUNTIME_MIN", 0) or 6.0)
    except (TypeError, ValueError):
        return 6.0


def _stale_multiplier() -> float:
    try:
        return float(getattr(settings, "CHAT_ORCH_STALE_MULTIPLIER", 0) or 2.0)
    except (TypeError, ValueError):
        return 2.0


def _stale_threshold_minutes() -> float:
    return _max_runtime_minutes() * _stale_multiplier()


def _flush_count() -> int:
    try:
        return max(1, int(getattr(settings, "CHAT_TURN_EVENT_FLUSH_COUNT", 0) or 20))
    except (TypeError, ValueError):
        return 20


def _flush_ms() -> int:
    try:
        return max(1, int(getattr(settings, "CHAT_TURN_EVENT_FLUSH_MS", 0) or 500))
    except (TypeError, ValueError):
        return 500


# ── DB helpers ─────────────────────────────────────────────────────────


async def _insert_turn(
    turn_id: str, conversation_id: str, campaign_id: Optional[str],
    mode: str, parent_turn_id: Optional[str],
) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO chat_turns "
            "(turn_id, conversation_id, campaign_id, parent_turn_id, mode, status) "
            "VALUES (?, ?, ?, ?, ?, 'running')",
            (turn_id, conversation_id, campaign_id, parent_turn_id, mode),
        )
        await db.commit()
    finally:
        await db.close()


async def _mark_turn(
    turn_id: str, status: str, *, stop_reason: str | None = None,
    cost: float | None = None, final_message_id: str | None = None,
) -> None:
    """Flip a still-running turn to a terminal state. Never clobbers a row that
    already reached a terminal status (idempotent stop / normal finish race)."""
    sets = ["status = ?", "finished_at = datetime('now')"]
    params: list[Any] = [status]
    if stop_reason is not None:
        sets.append("stop_reason = ?")
        params.append(stop_reason[:300])
    if cost is not None:
        sets.append("cost = ?")
        params.append(cost)
    if final_message_id is not None:
        sets.append("final_message_id = ?")
        params.append(final_message_id)
    params.append(turn_id)
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE chat_turns SET {', '.join(sets)} "
            "WHERE turn_id = ? AND status = 'running'",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def _persist_events(turn_id: str, events: list[dict]) -> None:
    """Batch-insert stamped envelopes into chat_turn_events (INSERT OR IGNORE so
    a re-flush after a restart-race can't duplicate a (turn_id, seq) row)."""
    if not events:
        return
    db = await get_db()
    try:
        await db.executemany(
            "INSERT OR IGNORE INTO chat_turn_events (turn_id, seq, type, payload) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    turn_id, e["seq"], e["type"],
                    json.dumps(e.get("payload", {})),
                )
                for e in events
            ],
        )
        await db.commit()
    finally:
        await db.close()


# ── Envelope stamping ─────────────────────────────────────────────────


def _stamp(conversation_id: str, turn_id: str, seq: int, raw: dict) -> dict:
    """Wrap a bare {type, payload} event in the v2 envelope (§4.3)."""
    return {
        "v": 2,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": raw.get("type", "event"),
        "payload": raw.get("payload", {}),
    }


# ── Driver ─────────────────────────────────────────────────────────────


async def _drive(
    turn_id: str, conversation_id: str, run_fn: RunFn, params: dict,
) -> None:
    """Background task body: iterate run_fn to completion, stamping each yielded
    event with a monotonic seq + envelope, publishing to the hub, and flushing
    to chat_turn_events in batches. Survives client disconnects; on cancellation
    (a stop request) marks the row stopped and emits a terminal turn_stopped."""
    hub = _chat_hubs[turn_id]
    seq = 0
    pending: list[dict] = []              # buffered-for-DB stamped envelopes
    last_flush = asyncio.get_event_loop().time()
    flush_count = _flush_count()
    flush_ms = _flush_ms()

    async def _flush() -> None:
        nonlocal pending, last_flush
        if pending:
            batch, pending = pending, []
            await _persist_events(turn_id, batch)
            last_flush = asyncio.get_event_loop().time()

    def _emit(raw: dict) -> dict:
        nonlocal seq
        seq += 1
        env = _stamp(conversation_id, turn_id, seq, raw)
        hub.publish(env)
        pending.append(env)
        return env

    try:
        async for raw in run_fn(turn_id=turn_id, **params):
            _emit(raw)
            # Time/size-based batched flush so history survives a crash without
            # a DB write per event.
            now = asyncio.get_event_loop().time()
            if len(pending) >= flush_count or (now - last_flush) * 1000 >= flush_ms:
                await _flush()
        # Normal completion — mark done if the run itself didn't already emit a
        # terminal turn_done that flipped the row (defensive; run_fn owns the
        # terminal semantics but the row must never be left 'running').
        await _mark_turn(turn_id, "done")
    except asyncio.CancelledError:
        # A stop_turn() task-cancel. Emit the terminal turn_stopped envelope so
        # the viewer's window shows it, then flip the row. The process-group
        # kill already happened in stop_turn (agent.stop_turn); this is the
        # task+event+row half.
        _emit({"type": "turn_stopped",
               "payload": {"stopped_by": "user", "partial_persisted": True}})
        await _mark_turn(turn_id, "stopped", stop_reason="stopped by user")
        raise
    except Exception as e:  # pragma: no cover — run_fn has its own guards
        logger.exception("chat turn %s crashed: %s", turn_id, e)
        _emit({"type": "turn_error", "payload": {"message": str(e)}})
        await _mark_turn(turn_id, "failed", stop_reason=str(e))
    finally:
        # Flush whatever remains, then close the hub + deregister the task.
        try:
            await _flush()
        except Exception:  # pragma: no cover — never let flush errors leak
            logger.warning("chat turn %s final flush failed", turn_id)
        hub.close()
        _chat_tasks.pop(turn_id, None)


# ── Public API ─────────────────────────────────────────────────────────


async def start(
    run_fn: RunFn,
    *,
    conversation_id: str,
    campaign_id: str | None = None,
    mode: str = "direct",
    parent_turn_id: str | None = None,
    **params: Any,
) -> str:
    """Mint a turn_id, insert the chat_turns row, launch a DETACHED task driving
    run_fn, and return the turn_id immediately (no waiting for a first event).

    run_fn is an async generator called as run_fn(turn_id=..., **params) that
    yields bare {type, payload} dicts; the runner stamps envelopes + persists.
    """
    turn_id = str(uuid.uuid4())
    # Register the hub BEFORE the row/task so a very-fast subscriber that races
    # in on the returned turn_id always finds a hub to attach to.
    _chat_hubs[turn_id] = _ChatHub()
    await _insert_turn(turn_id, conversation_id, campaign_id, mode, parent_turn_id)
    task = asyncio.create_task(_drive(turn_id, conversation_id, run_fn, params))
    _chat_tasks[turn_id] = task
    return turn_id


async def subscribe(turn_id: str, cursor: int = 0) -> AsyncIterator[dict]:
    """Tail a turn's events (replay from cursor + live). Closing this async
    iterator (client disconnect) only unsubscribes — it never cancels the run.

    If the in-memory hub is gone (turn finished + cleaned, or a restart), fall
    back to the persisted chat_turn_events so history replay still works."""
    hub = _chat_hubs.get(turn_id)
    if hub is None:
        # No live hub — replay persisted history (post-restart / post-cleanup).
        for event in await get_events(turn_id):
            if event.get("seq", 0) > cursor:
                yield event
        return
    q = hub.subscribe(cursor)
    try:
        while True:
            item = await q.get()
            if item is _SENTINEL:
                break
            yield item
    finally:
        hub.unsubscribe(q)


async def get_events(turn_id: str) -> list[dict]:
    """Return a turn's full event list from chat_turn_events (history replay),
    as fully-stamped envelopes ordered by seq."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT ct.conversation_id AS conversation_id, e.turn_id, e.seq, e.type, "
            "e.payload, e.created_at "
            "FROM chat_turn_events e "
            "JOIN chat_turns ct ON ct.turn_id = e.turn_id "
            "WHERE e.turn_id = ? ORDER BY e.seq ASC",
            (turn_id,),
        )
        rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"]) if r["payload"] else {}
            except (TypeError, ValueError):
                payload = {}
            out.append({
                "v": 2,
                "conversation_id": r["conversation_id"],
                "turn_id": r["turn_id"],
                "seq": r["seq"],
                "ts": r["created_at"],
                "type": r["type"],
                "payload": payload,
            })
        return out
    finally:
        await db.close()


async def active_turns(conversation_id: str) -> list[dict]:
    """Active (status='running') turns for a conversation, for reconnect. Newest
    first. Returns lightweight dicts (turn_id, mode, started_at, last_seq)."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT turn_id, mode, campaign_id, started_at "
            "FROM chat_turns WHERE conversation_id = ? AND status = 'running' "
            "ORDER BY started_at DESC",
            (conversation_id,),
        )
        rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            tid = r["turn_id"]
            # Prefer the live hub's cursor; fall back to the persisted max seq.
            hub = _chat_hubs.get(tid)
            if hub is not None and hub.buffer:
                last_seq = hub.buffer[-1].get("seq", 0)
            else:
                cur2 = await db.execute(
                    "SELECT MAX(seq) AS m FROM chat_turn_events WHERE turn_id = ?",
                    (tid,),
                )
                row2 = await cur2.fetchone()
                last_seq = (row2["m"] if row2 and row2["m"] is not None else 0)
            out.append({
                "turn_id": tid,
                "mode": r["mode"],
                "campaign_id": r["campaign_id"],
                "started_at": r["started_at"],
                "last_seq": last_seq,
            })
        return out
    finally:
        await db.close()


async def stop_turn(turn_id: str) -> dict:
    """Per-turn stop (story 1.5). Cooperatively cancels the detached task AND
    process-group-kills every CLI child registered under the turn.

    Idempotent: a turn already in a terminal state → {status:"already_done"}.
    The task-cancel path emits the terminal turn_stopped event + flips the row
    (see _drive's CancelledError branch). If no task is live in this process
    (post-restart zombie), still flip a lingering 'running' row so the UI stops
    showing it as active, and still fire the process kill in case children leak.
    """
    # Process-group kill first — reaches every live child even if the task is
    # mid-await between events (agent.py owns _turn_procs / _turn_stop_requested).
    from app.services.agent import stop_turn as _agent_stop_turn
    kill = _agent_stop_turn(turn_id)

    task = _chat_tasks.get(turn_id)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        return {"turn_id": turn_id, "status": "stopped", "killed": kill.get("killed", [])}

    # No live task. Flip a lingering 'running' row (idempotent — the guarded
    # UPDATE is a no-op if it already reached terminal).
    status = await _turn_status(turn_id)
    if status in (None,):
        return {"turn_id": turn_id, "status": "not_found", "killed": kill.get("killed", [])}
    if status != "running":
        return {"turn_id": turn_id, "status": "already_done", "killed": kill.get("killed", [])}
    await _mark_turn(turn_id, "stopped", stop_reason="stopped by user")
    return {"turn_id": turn_id, "status": "stopped", "note": "no active task",
            "killed": kill.get("killed", [])}


async def stop_call(turn_id: str, call_id: str) -> dict:
    """Per-specialist stop (story 2.6). Kills ONE call's process group; the turn
    (and its Director) continues. Does NOT cancel the turn task."""
    from app.services.agent import stop_call as _agent_stop_call
    res = _agent_stop_call(turn_id, call_id)
    return {"turn_id": turn_id, "call_id": call_id, "killed": bool(res.get("killed"))}


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


async def sweep_chat_zombies() -> int:
    """Mark orphaned 'running' chat_turns (started_at older than the stale
    threshold) as 'stale'. Reaps turns whose process died or whose driver was
    lost across a restart. Returns how many were swept."""
    threshold_min = _stale_threshold_minutes()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold_min)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT turn_id FROM chat_turns WHERE status = 'running' AND started_at < ?",
            (cutoff,),
        )
        stale_ids = [r["turn_id"] for r in await cur.fetchall()]
        # Never sweep a turn whose task is still live in THIS process — a
        # long-but-legitimate orchestrated turn. started_at is fixed at launch,
        # so a genuinely slow turn could cross the threshold while healthy.
        stale_ids = [t for t in stale_ids
                     if t not in _chat_tasks or _chat_tasks[t].done()]
        if stale_ids:
            await db.executemany(
                "UPDATE chat_turns SET status = 'stale', stop_reason = 'stale', "
                "finished_at = datetime('now') "
                "WHERE turn_id = ? AND status = 'running'",
                [(t,) for t in stale_ids],
            )
            await db.commit()
            logger.info("chat zombie sweep: marked %d stale turn(s): %s",
                        len(stale_ids), ", ".join(i[:8] for i in stale_ids))
    finally:
        await db.close()
    return len(stale_ids)


# ── Periodic sweeper lifecycle (mirrors workflow_runner) ───────────────
_sweeper: asyncio.Task | None = None


async def _sweep_loop() -> None:
    try:
        interval_min = float(getattr(settings, "CHAT_ORCH_SWEEP_INTERVAL_MINUTES", 0) or 5)
    except (TypeError, ValueError):
        interval_min = 5.0
    logger.info("chat zombie sweeper started (every %.0fm, stale > %.0fm)",
                interval_min, _stale_threshold_minutes())
    while True:
        try:
            await sweep_chat_zombies()
        except Exception as e:
            logger.warning("chat zombie sweep error: %s", e)
        await asyncio.sleep(interval_min * 60)


def start_sweeper() -> None:
    global _sweeper
    if _sweeper is None or _sweeper.done():
        _sweeper = asyncio.create_task(_sweep_loop())


def stop_sweeper() -> None:
    global _sweeper
    if _sweeper and not _sweeper.done():
        _sweeper.cancel()
        _sweeper = None
