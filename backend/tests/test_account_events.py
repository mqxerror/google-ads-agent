"""Dashboard v2.1 — Epic C / C1: per-account SSE event hub (account_events).

Proves the in-process pub/sub hub that powers `GET /api/accounts/{id}/events`:

  1. A subscriber receives an event published AFTER it subscribed.
  2. Replay: an event published BEFORE a subscriber connects is delivered from
     the buffer on subscribe (so a late/reconnecting client catches up).
  3. The replay buffer is BOUNDED (last _BUFFER_MAX) — an old event that fell off
     the front is NOT replayed to a new subscriber; the newest ones are.
  4. Fan-out: two subscribers both receive a published event.
  5. Unsubscribe stops delivery (a dropped client no longer accumulates events).

Pure in-memory — no DB, no Google, no network.

Run:  cd backend && .venv/bin/python -m unittest tests.test_account_events -v
"""

from __future__ import annotations

import asyncio
import unittest

from app.services import account_events
from app.services.account_events import _BUFFER_MAX


def _drain(q: asyncio.Queue) -> list[dict]:
    """Non-blocking drain of everything currently queued for a subscriber."""
    out: list[dict] = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


class AccountEventsHubTest(unittest.TestCase):
    def setUp(self):
        # Isolate every test: fresh hub registry so buffers don't leak across.
        account_events._hubs.clear()

    def tearDown(self):
        account_events._hubs.clear()

    def test_subscriber_gets_event_published_after_subscribe(self):
        hub = account_events._hub_for("acct-1")
        q = hub.subscribe()
        self.assertEqual(_drain(q), [])  # nothing yet
        account_events.publish("acct-1", {"type": "sync_completed", "n": 1})
        got = _drain(q)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["type"], "sync_completed")

    def test_replay_delivers_prior_events_on_subscribe(self):
        # Publish BEFORE anyone subscribes; a late subscriber must still see it.
        account_events.publish("acct-2", {"type": "external_change", "count": 3})
        hub = account_events._hub_for("acct-2")
        q = hub.subscribe()
        got = _drain(q)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["count"], 3)

    def test_replay_buffer_is_bounded(self):
        acct = "acct-3"
        # Publish more than the buffer holds. Oldest fall off the front.
        total = _BUFFER_MAX + 10
        for i in range(total):
            account_events.publish(acct, {"type": "sync_completed", "i": i})
        hub = account_events._hub_for(acct)
        q = hub.subscribe()
        got = _drain(q)
        # Only the last _BUFFER_MAX events are replayed.
        self.assertEqual(len(got), _BUFFER_MAX)
        # The very first event (i=0) fell off; the newest (i=total-1) is present.
        replayed_i = [e["i"] for e in got]
        self.assertNotIn(0, replayed_i)
        self.assertEqual(replayed_i[0], total - _BUFFER_MAX)
        self.assertEqual(replayed_i[-1], total - 1)

    def test_fanout_to_multiple_subscribers(self):
        hub = account_events._hub_for("acct-4")
        q1 = hub.subscribe()
        q2 = hub.subscribe()
        account_events.publish("acct-4", {"type": "sync_completed"})
        self.assertEqual(len(_drain(q1)), 1)
        self.assertEqual(len(_drain(q2)), 1)

    def test_unsubscribe_stops_delivery(self):
        hub = account_events._hub_for("acct-5")
        q = hub.subscribe()
        hub.unsubscribe(q)
        account_events.publish("acct-5", {"type": "sync_completed"})
        self.assertEqual(_drain(q), [])

    def test_publish_empty_account_id_is_noop(self):
        # Guard: publishing to an empty account id must not raise or create a hub.
        account_events.publish("", {"type": "sync_completed"})
        self.assertNotIn("", account_events._hubs)

    def test_async_subscribe_yields_live_event(self):
        """The public async `subscribe` iterator yields a published event, then
        the client (us) closes it — mirroring the SSE endpoint's lifecycle."""
        async def _run():
            agen = account_events.subscribe("acct-6")
            # Publish after subscribing; the async generator must yield it.
            account_events.publish("acct-6", {"type": "sync_completed", "ok": True})
            event = await asyncio.wait_for(agen.__anext__(), timeout=1.0)
            self.assertEqual(event["ok"], True)
            await agen.aclose()
            # After close, the subscriber queue is unregistered from the hub.
            hub = account_events._hub_for("acct-6")
            self.assertEqual(len(hub.subscribers), 0)
        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
