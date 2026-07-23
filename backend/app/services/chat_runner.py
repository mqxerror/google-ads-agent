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

# ── Same-conversation turn serialization (chat-hardening item 4) ──────────
# A conversation must NEVER have two turns EXECUTING at once — two live turns
# interleave their write-backs (role notes / resumable session / messages) and
# corrupt the thread (the deferred-since-Epic-0 second-send seam). So a NEW
# non-identical message that arrives while a turn is still running is QUEUED:
# its turn is created immediately (with a visible "queued behind the running
# turn" notice) but its run_fn does not start until the turn ahead of it
# finishes. Stop kills the running turn; the queued one then starts (and can be
# stopped too). An IDENTICAL re-send while a turn runs is a duplicate submit and
# reuses the running turn instead of queuing a second one.
#
#   _conversation_chain: conversation_id → the TAIL turn_id (what a new turn must
#                        wait behind). Updated on every start; cleared when the
#                        tail finishes with nothing queued after it.
#   _turn_gate:          turn_id → the Event a QUEUED turn's _drive awaits before
#                        running its run_fn (absent for a turn that ran at once).
#   _turn_next_gate:     predecessor turn_id → its direct successor's gate, set
#                        (released) when the predecessor's _drive finishes/stops.
#   _turn_origin:        turn_id → the originating user message (dedup + notice).
_conversation_chain: dict[str, str] = {}
_turn_gate: dict[str, asyncio.Event] = {}
_turn_next_gate: dict[str, asyncio.Event] = {}
_turn_origin: dict[str, str] = {}
_turn_conversation: dict[str, str] = {}  # turn_id → conversation_id (dedup scope)


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
    mode: str, parent_turn_id: Optional[str], status: str = "running",
) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO chat_turns "
            "(turn_id, conversation_id, campaign_id, parent_turn_id, mode, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (turn_id, conversation_id, campaign_id, parent_turn_id, mode, status),
        )
        await db.commit()
    finally:
        await db.close()


async def _mark_running(turn_id: str) -> None:
    """Flip a QUEUED turn to 'running' the moment its gate opens (item 4). Guarded
    so a concurrent stop that already moved it to a terminal state wins."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE chat_turns SET status = 'running' "
            "WHERE turn_id = ? AND status = 'queued'",
            (turn_id,),
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
        # Also flips a still-'queued' turn (item 4): a stop can land BEFORE the
        # gate opens, so a queued turn must be markable terminal directly.
        await db.execute(
            f"UPDATE chat_turns SET {', '.join(sets)} "
            "WHERE turn_id = ? AND status IN ('running', 'queued')",
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
    gate: Optional[asyncio.Event] = None,
) -> None:
    """Background task body: iterate run_fn to completion, stamping each yielded
    event with a monotonic seq + envelope, publishing to the hub, and flushing
    to chat_turn_events in batches. Survives client disconnects; on cancellation
    (a stop request) marks the row stopped and emits a terminal turn_stopped.

    Item 4: when `gate` is set this turn was QUEUED behind a still-running turn
    on the same conversation. It emits a visible "queued behind the running
    turn" notice immediately, then WAITS on the gate before running run_fn — so
    two turns on one conversation never execute at once. The gate opens when the
    turn ahead finishes/stops (see the finally). A stop while still waiting is a
    normal CancelledError (handled below)."""
    hub = _chat_hubs[turn_id]
    seq = 0
    pending: list[dict] = []              # buffered-for-DB stamped envelopes
    last_flush = asyncio.get_event_loop().time()
    flush_count = _flush_count()
    flush_ms = _flush_ms()

    # Fix 1 (P0 stop safety): track every dispatched WRITE-intent specialist so
    # a stop can report its disposition — an approved write must never die
    # silently. Keyed by call_id: {role_id, role_name, completed}. Populated by
    # observing agent_called(+write_intent) / agent_result as they flow through
    # _emit (the runner OWNS the terminal turn_stopped, so it needs this locally).
    dispatched_writes: dict[str, dict] = {}
    # Add-on (chat-hardening §5): best-effort running cost so a stopped turn can
    # report roughly what it spent before the kill (a NOTE, not billing). Summed
    # from per-call cost signals as they flow through _emit.
    _cost_box = [0.0]

    async def _flush() -> None:
        nonlocal pending, last_flush
        if pending:
            batch, pending = pending, []
            await _persist_events(turn_id, batch)
            last_flush = asyncio.get_event_loop().time()

    def _track_dispatch(raw: dict) -> None:
        """Observe dispatch events to keep dispatched_writes current (Fix 1)."""
        rtype = raw.get("type")
        payload = raw.get("payload", {}) or {}
        if rtype == "agent_called" and payload.get("write_intent"):
            cid = payload.get("call_id")
            if cid is not None:
                dispatched_writes[cid] = {
                    "role_id": payload.get("role_id"),
                    "role_name": payload.get("role_name"),
                    "completed": False,
                }
        elif rtype == "agent_result":
            cid = payload.get("call_id")
            if cid in dispatched_writes:
                dispatched_writes[cid]["completed"] = True
        # Accumulate a best-effort running cost from per-call cost signals
        # (agent_result.cost / direct done.cost). final_done.cost_total is the
        # authoritative total on a NORMAL finish; on a KILL we report this sum.
        if rtype in ("agent_result", "done"):
            _c = payload.get("cost")
            if isinstance(_c, (int, float)):
                _cost_box[0] += float(_c)

    def _stop_specialists() -> list[dict]:
        """Build the per-specialist disposition list for turn_stopped (Fix 1).

        completed             — the specialist's agent_result was seen before stop
        stopped_before_write  — dispatched write-intent, never completed (the
                                approved write did NOT execute)
        We report EVERY tracked write-intent specialist. Incomplete ones use
        'stopped_before_write' (the common, honest case: the batch never ran)."""
        out: list[dict] = []
        for _cid, info in dispatched_writes.items():
            disposition = "completed" if info["completed"] else "stopped_before_write"
            out.append({
                "role_id": info.get("role_id"),
                "role_name": info.get("role_name"),
                "disposition": disposition,
            })
        return out

    def _emit(raw: dict) -> dict:
        nonlocal seq
        seq += 1
        _track_dispatch(raw)
        env = _stamp(conversation_id, turn_id, seq, raw)
        hub.publish(env)
        pending.append(env)
        return env

    try:
        # Item 4: a QUEUED turn announces itself, then waits its turn. The notice
        # is seq 1 so an immediate subscriber sees it; run_fn events follow once
        # the turn ahead finishes and opens the gate.
        if gate is not None:
            _emit({"type": "turn_queued", "payload": {
                "message": _turn_origin.get(turn_id),
                "behind_turn_id": _conversation_chain.get(conversation_id)}})
            await _flush()
            await gate.wait()
            # The turn ahead finished — promote queued → running before we start.
            await _mark_running(turn_id)
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
               "payload": {"stopped_by": "user", "partial_persisted": True,
                           # Fix 1: per-specialist write disposition so the UI can
                           # warn about an approved-but-not-executed mutation.
                           # Empty list = the common safe case (no write in flight).
                           "specialists": _stop_specialists(),
                           # Add-on: best-effort spend before the kill (a NOTE).
                           "cost_on_kill": round(_cost_box[0], 4)}})
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
        # Item 4: release the NEXT queued turn on this conversation (if any), so a
        # normal finish OR a stop both hand off to the waiting turn. Then clean up
        # this turn's serialization bookkeeping. If this turn is still the chain
        # tail (nothing queued after it), clear the chain so the next fresh
        # message runs immediately.
        nxt = _turn_next_gate.pop(turn_id, None)
        if nxt is not None:
            nxt.set()
        _turn_gate.pop(turn_id, None)
        _turn_origin.pop(turn_id, None)
        _turn_conversation.pop(turn_id, None)
        if _conversation_chain.get(conversation_id) == turn_id:
            _conversation_chain.pop(conversation_id, None)


# ── Public API ─────────────────────────────────────────────────────────


async def start(
    run_fn: RunFn,
    *,
    conversation_id: str,
    campaign_id: str | None = None,
    mode: str = "direct",
    parent_turn_id: str | None = None,
    origin_message: str | None = None,
    **params: Any,
) -> str:
    """Mint a turn_id, insert the chat_turns row, launch a DETACHED task driving
    run_fn, and return the turn_id immediately (no waiting for a first event).

    run_fn is an async generator called as run_fn(turn_id=..., **params) that
    yields bare {type, payload} dicts; the runner stamps envelopes + persists.

    Item 4 — same-conversation serialization: if a turn is already LIVE (running
    OR queued) on this conversation, this new turn is QUEUED behind the tail of
    the chain (status 'queued', a visible notice, run_fn deferred until the turn
    ahead finishes) so two turns never execute at once. `origin_message` is
    recorded for the duplicate-submit check (find_duplicate_active_turn).
    """
    turn_id = str(uuid.uuid4())
    # Register the hub BEFORE the row/task so a very-fast subscriber that races
    # in on the returned turn_id always finds a hub to attach to.
    _chat_hubs[turn_id] = _ChatHub()

    # Serialize behind any still-live turn on this conversation (item 4). The
    # chain tail is what we wait behind; if it has already finished there is no
    # gate and we run immediately.
    gate: asyncio.Event | None = None
    predecessor = _conversation_chain.get(conversation_id)
    if predecessor and predecessor != turn_id:
        pred_task = _chat_tasks.get(predecessor)
        if pred_task is not None and not pred_task.done():
            gate = asyncio.Event()
            _turn_gate[turn_id] = gate
            _turn_next_gate[predecessor] = gate
    # This turn becomes the new tail of the conversation's chain.
    _conversation_chain[conversation_id] = turn_id
    _turn_conversation[turn_id] = conversation_id
    if origin_message is not None:
        _turn_origin[turn_id] = origin_message

    status = "queued" if gate is not None else "running"
    await _insert_turn(turn_id, conversation_id, campaign_id, mode,
                       parent_turn_id, status=status)
    task = asyncio.create_task(
        _drive(turn_id, conversation_id, run_fn, params, gate=gate))
    _chat_tasks[turn_id] = task
    return turn_id


def find_duplicate_active_turn(conversation_id: str, content: str) -> str | None:
    """A live (running OR queued) turn on THIS conversation whose originating
    message is IDENTICAL to `content` — a duplicate submit (double-click / retry)
    that should reuse the existing turn instead of queuing a second one (item 4).
    Returns its turn_id, or None. A non-identical message returns None → it will
    be queued normally by start()."""
    if not content:
        return None
    for tid, task in list(_chat_tasks.items()):
        if task.done():
            continue
        if _turn_conversation.get(tid) != conversation_id:
            continue
        if _turn_origin.get(tid) == content:
            return tid
    return None


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
        # Include 'queued' turns (item 4): a turn parked behind a predecessor that
        # died across a restart would otherwise linger forever.
        cur = await db.execute(
            "SELECT turn_id FROM chat_turns "
            "WHERE status IN ('running', 'queued') AND started_at < ?",
            (cutoff,),
        )
        stale_ids = [r["turn_id"] for r in await cur.fetchall()]
        # Never sweep a turn whose task is still live in THIS process — a
        # long-but-legitimate orchestrated turn (or one still queued behind it).
        # started_at is fixed at launch, so a genuinely slow turn could cross the
        # threshold while healthy.
        stale_ids = [t for t in stale_ids
                     if t not in _chat_tasks or _chat_tasks[t].done()]
        if stale_ids:
            await db.executemany(
                "UPDATE chat_turns SET status = 'stale', stop_reason = 'stale', "
                "finished_at = datetime('now') "
                "WHERE turn_id = ? AND status IN ('running', 'queued')",
                [(t,) for t in stale_ids],
            )
            await db.commit()
            logger.info("chat zombie sweep: marked %d stale turn(s): %s",
                        len(stale_ids), ", ".join(i[:8] for i in stale_ids))
    finally:
        await db.close()
    return len(stale_ids)


async def prune_old_turn_events(retention_days: Optional[int] = None) -> int:
    """Add-on (chat-hardening §5): prune chat_turn_events older than the
    retention window so the event log can't grow without bound. Piggybacks the
    zombie sweeper (called from _sweep_loop). Only prunes events of turns that
    already reached a terminal state (never a live/running/queued turn's log).
    Returns rows deleted. retention_days<=0 disables pruning."""
    if retention_days is None:
        try:
            retention_days = int(getattr(settings, "CHAT_TURN_EVENT_RETENTION_DAYS", 0) or 90)
        except (TypeError, ValueError):
            retention_days = 90
    if retention_days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    db = await get_db()
    try:
        cur = await db.execute(
            "DELETE FROM chat_turn_events WHERE turn_id IN ("
            "  SELECT turn_id FROM chat_turns "
            "  WHERE status NOT IN ('running', 'queued') AND finished_at IS NOT NULL "
            "    AND finished_at < ?"
            ")",
            (cutoff,),
        )
        deleted = cur.rowcount if cur.rowcount is not None else 0
        await db.commit()
        if deleted:
            logger.info("chat_turn_events retention prune: deleted %d row(s) "
                        "older than %dd", deleted, retention_days)
    finally:
        await db.close()
    return deleted


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
        try:
            await prune_old_turn_events()
        except Exception as e:  # retention prune must never break the sweeper
            logger.warning("chat_turn_events retention prune error: %s", e)
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
