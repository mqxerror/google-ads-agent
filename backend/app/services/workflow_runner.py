"""Workflow runner — decouples execution from the SSE stream (Story 13.2).

THE BUG this fixes: `POST /api/workflows/run` used to drive the entire
workflow INSIDE the StreamingResponse generator. If the browser tab closed,
FastAPI cancelled the generator, the workflow died mid-flight, and the
`workflow_runs` row was orphaned as an eternal "running" zombie (live-confirmed:
e898a108-… and f3b630b1-…).

THE FIX:
  - `start(**params)` launches `run_workflow(...)` in a DETACHED asyncio task
    (`asyncio.create_task`) that runs to completion regardless of any client.
    Every event the orchestrator yields is published to an in-memory `_RunHub`
    keyed by the run_id (which the first `workflow_start` event carries).
  - The SSE endpoint becomes a VIEWER: `subscribe(run_id)` yields the hub's
    replay buffer (so a late/ reconnecting client still sees the whole run)
    then tails live events. Closing the stream only unsubscribes — the task
    keeps running.
  - `stop(run_id)` cancels the task cooperatively; the wrapper catches the
    cancellation, marks the row `stopped`, and closes the hub.
  - `sweep_zombies()` marks any run still `running` whose `updated_at` is older
    than `WORKFLOW_MAX_RUNTIME_MINUTES × WORKFLOW_STALE_MULTIPLIER` as
    `failed`/`stop_reason='stale'`. Runs on startup (reaps the two known
    zombies) and periodically.

The orchestrator (`run_workflow`) is UNCHANGED in behaviour — per-campaign mode
and the exact SSE event shape are preserved byte-for-byte; the runner is a thin
lifecycle+fan-out layer around it.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Optional

from app.config import settings
from app.database import get_db
from app.services.workflow_orchestrator import run_workflow

logger = logging.getLogger(__name__)

# A sentinel that tells subscribers the stream is over. Never sent to clients.
_SENTINEL = object()


class _RunHub:
    """Fan-out buffer for one run's events: replay history + live subscribers."""

    def __init__(self) -> None:
        self.buffer: list[dict] = []          # every event, in order (replay)
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

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay everything so far so a late viewer catches up fully.
        for event in self.buffer:
            q.put_nowait(event)
        if self.done.is_set():
            q.put_nowait(_SENTINEL)
        else:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)


# run_id → hub, and run_id → task. Both live for the process; cleaned on finish.
_hubs: dict[str, _RunHub] = {}
_tasks: dict[str, asyncio.Task] = {}


def _max_runtime_minutes() -> float:
    try:
        return float(getattr(settings, "WORKFLOW_MAX_RUNTIME_MINUTES", 0) or 20)
    except (TypeError, ValueError):
        return 20.0


def _stale_multiplier() -> float:
    try:
        return float(getattr(settings, "WORKFLOW_STALE_MULTIPLIER", 0) or 2.0)
    except (TypeError, ValueError):
        return 2.0


def _stale_threshold_minutes() -> float:
    return _max_runtime_minutes() * _stale_multiplier()


async def _mark_stopped(run_id: str, reason: str) -> None:
    db = await get_db()
    try:
        # Only touch a still-running row — never clobber a finished one.
        await db.execute(
            "UPDATE workflow_runs SET status = 'stopped', stop_reason = ?, "
            "updated_at = datetime('now') WHERE id = ? AND status = 'running'",
            (reason[:300], run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _drive(run_id_box: dict, params: dict) -> None:
    """Background task body: iterate the orchestrator to completion, publishing
    each event to the run's hub. Survives client disconnects; on cancellation
    (a stop request) marks the row stopped."""
    run_id: Optional[str] = None
    hub: Optional[_RunHub] = None
    try:
        async for event in run_workflow(**params):
            if run_id is None:
                # The first event (workflow_start) carries the run_id the
                # orchestrator minted. Register the hub under it now so
                # subscribers can find it, and hand it back to the caller.
                run_id = event.get("run_id") or run_id_box.get("pending_id")
                if run_id:
                    hub = _hubs.get(run_id)
                    if hub is None:
                        hub = _RunHub()
                        _hubs[run_id] = hub
                    # Buffer the first event BEFORE signalling ready, so the
                    # SSE viewer that wakes on `ready` always finds a hub that
                    # already carries workflow_start (no empty-tail window).
                    hub.publish(event)
                    run_id_box["run_id"] = run_id
                    run_id_box["ready"].set()
                    continue
            if hub is not None:
                hub.publish(event)
    except asyncio.CancelledError:
        # A stop() request. The orchestrator's `except Exception` does NOT
        # catch CancelledError (BaseException), so the row is still 'running'.
        if run_id:
            await _mark_stopped(run_id, "stopped by user")
            if hub is not None:
                hub.publish({"type": "workflow_stopped", "run_id": run_id,
                             "stop_reason": "stopped by user"})
        raise
    except Exception as e:  # pragma: no cover — orchestrator has its own guard
        logger.exception("workflow runner crashed for run %s: %s", run_id, e)
        if hub is not None:
            hub.publish({"type": "error", "run_id": run_id, "message": str(e)})
    finally:
        # Unblock any waiter even if we never saw a workflow_start.
        if not run_id_box["ready"].is_set():
            run_id_box["ready"].set()
        if hub is not None:
            hub.close()
        if run_id:
            _tasks.pop(run_id, None)


async def start(**params: Any) -> str:
    """Launch a workflow in a detached background task and return its run_id.

    Blocks only until the orchestrator emits its first event (which carries the
    run_id) — a few milliseconds — then returns while execution continues in
    the background, independent of the caller."""
    box: dict = {"ready": asyncio.Event(), "run_id": None}
    task = asyncio.create_task(_drive(box, params))
    # Wait for the run_id to be known (first event), so the SSE viewer can
    # subscribe to the right hub. If the task dies before emitting anything,
    # `ready` is still set in the finally block.
    await box["ready"].wait()
    run_id = box.get("run_id")
    if run_id:
        _tasks[run_id] = task
    else:
        # Never emitted a workflow_start — surface the failure to the caller.
        raise RuntimeError("workflow failed to start (no run_id emitted)")
    return run_id


async def subscribe(run_id: str) -> AsyncIterator[dict]:
    """Tail a run's events (replay buffer + live). Closing this async iterator
    (client disconnect) only unsubscribes — it never cancels the run."""
    hub = _hubs.get(run_id)
    if hub is None:
        # Unknown run (already finished + cleaned, or bad id): nothing to tail.
        return
    q = hub.subscribe()
    try:
        while True:
            item = await q.get()
            if item is _SENTINEL:
                break
            yield item
    finally:
        hub.unsubscribe(q)


async def stop(run_id: str) -> dict:
    """Cooperatively cancel a running workflow and mark the row stopped."""
    task = _tasks.get(run_id)
    if task is None or task.done():
        # Not running in this process — still flip a stale 'running' row so the
        # UI stops showing a zombie as active.
        await _mark_stopped(run_id, "stopped by user")
        return {"run_id": run_id, "status": "stopped", "note": "no active task"}
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    return {"run_id": run_id, "status": "stopped"}


async def sweep_zombies() -> int:
    """Mark orphaned 'running' rows (updated_at older than the stale threshold)
    as failed/stale. Reaps runs whose process died or whose stream was severed
    before the decouple fix. Returns how many were swept."""
    threshold_min = _stale_threshold_minutes()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold_min)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id FROM workflow_runs WHERE status = 'running' AND updated_at < ?",
            (cutoff,),
        )
        stale_ids = [r["id"] for r in await cur.fetchall()]
        if stale_ids:
            await db.execute(
                "UPDATE workflow_runs SET status = 'failed', stop_reason = 'stale', "
                "updated_at = datetime('now') WHERE status = 'running' AND updated_at < ?",
                (cutoff,),
            )
            await db.commit()
            logger.info("zombie sweep: marked %d stale run(s) failed: %s",
                        len(stale_ids), ", ".join(i[:8] for i in stale_ids))
    finally:
        await db.close()
    return len(stale_ids)


# ── Periodic sweeper lifecycle ────────────────────────────────────────
_sweeper: asyncio.Task | None = None


async def _sweep_loop() -> None:
    try:
        interval_min = float(getattr(settings, "WORKFLOW_SWEEP_INTERVAL_MINUTES", 0) or 10)
    except (TypeError, ValueError):
        interval_min = 10.0
    logger.info("workflow zombie sweeper started (every %.0fm, stale > %.0fm)",
                interval_min, _stale_threshold_minutes())
    while True:
        try:
            await sweep_zombies()
        except Exception as e:
            logger.warning("zombie sweep error: %s", e)
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
