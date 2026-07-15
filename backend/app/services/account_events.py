"""Per-account SSE event hub (Dashboard v2.1 — Epic C / C1 "push updates").

The dashboard is stale-by-default (see the freshness plan §1.7). Polling the
home endpoints is wasteful and laggy; instead we push a tiny event whenever the
account's data actually changes — a metrics sync finishes, the roster refreshes,
an external change is detected — and the frontend invalidates just the affected
React-Query caches. The operator watches the "syncing…" chip flip to "live" with
no reload.

This MIRRORS `workflow_runner._RunHub` (in-process replay buffer + subscribers),
with two differences from the workflow case:

  1. Hubs are keyed by `account_id` and live for the whole process — they are
     NEVER closed (an account's event stream has no natural end, unlike a
     workflow run which finishes). A subscriber tails FOREVER until the CLIENT
     disconnects (the async generator is GC'd / cancelled).
  2. The replay buffer is BOUNDED (last ~50 events) so a client that reconnects
     after being away isn't flooded — it catches the recent tail, not all
     history.

Publishing is fire-and-forget and synchronous (`put_nowait`) so emit sites (the
sync engine, roster diff, etc.) never block on a slow subscriber. There is no
back-pressure by design: a subscriber that can't keep up drops events, which is
fine — every event is just an "invalidate your cache" nudge; the next read
re-fetches the truth from SQLite regardless.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# Keep the replay buffer small: a reconnecting client wants the recent tail, not
# an unbounded backlog. Each event is a tiny dict.
_BUFFER_MAX = 50


class _AccountHub:
    """Fan-out buffer for ONE account's events: bounded replay + live subscribers.

    Unlike the workflow hub this hub is never `close()`d — an account's stream is
    open-ended. It only accumulates subscribers (per SSE connection) and sheds
    them on unsubscribe.
    """

    def __init__(self) -> None:
        # Bounded replay: keep only the last _BUFFER_MAX events so a reconnecting
        # client isn't flooded. Oldest events fall off the front.
        self.buffer: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()

    def publish(self, event: dict) -> None:
        self.buffer.append(event)
        if len(self.buffer) > _BUFFER_MAX:
            # Trim from the front — keep the newest _BUFFER_MAX.
            del self.buffer[: len(self.buffer) - _BUFFER_MAX]
        for q in list(self.subscribers):
            try:
                q.put_nowait(event)
            except Exception:  # pragma: no cover — a dead queue; drop it.
                self.subscribers.discard(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        # Replay the recent tail so a late/reconnecting viewer catches up.
        for event in self.buffer:
            q.put_nowait(event)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)


# account_id → hub. Hubs live for the whole process (never torn down); an
# account's event stream is open-ended.
_hubs: dict[str, _AccountHub] = {}


def _hub_for(account_id: str) -> _AccountHub:
    hub = _hubs.get(account_id)
    if hub is None:
        hub = _AccountHub()
        _hubs[account_id] = hub
    return hub


def publish(account_id: str, event: dict) -> None:
    """Push one event to every live subscriber of `account_id` (and buffer it for
    reconnects). Non-blocking, best-effort. Safe to call from any coroutine — it
    only touches in-memory state and `put_nowait`.

    Emit sites: sync engine (`sync_completed`), roster diff (`external_change`),
    plan executor (`mutation_applied`), audits (`audit_completed`).
    """
    if not account_id:
        return
    try:
        _hub_for(account_id).publish(event)
    except Exception as e:  # pragma: no cover — never let an emit break its caller
        logger.warning("account_events.publish failed for %s: %s", account_id, e)


async def subscribe(account_id: str) -> AsyncIterator[dict]:
    """Tail an account's events forever: replay the recent buffer, then yield live
    events as they're published.

    Unlike `workflow_runner.subscribe`, this NEVER ends on its own — an account's
    stream is open-ended. It runs until the CLIENT disconnects, at which point
    FastAPI cancels the async generator; the `finally` unsubscribes the queue.
    (The SSE endpoint layers a periodic keepalive comment on top so idle proxies
    don't drop the connection — see routers/workflows.py.)
    """
    hub = _hub_for(account_id)
    q = hub.subscribe()
    try:
        while True:
            event = await q.get()
            yield event
    finally:
        hub.unsubscribe(q)
