"""Story 1.4 — token-level streaming previews (backend half) regression tests.

Repo test style: stdlib unittest, no real Claude / Google Ads / network calls.

These prove the ONLY new backend behaviour and its dedup invariant:

  1) FLAG OFF (default): `_emit_assistant_blocks` still emits `text` events and
     `full_response_text` accumulates the complete text — behaviour unchanged.
  2) FLAG ON: a simulated CLI `stream_event` content_block_delta yields a
     `text_delta` chunk via `_extract_stream_text_delta`, AND
     `_emit_assistant_blocks` does NOT re-emit the assistant `text` block (no
     doubling) while STILL accumulating `full_response_text` (persistence /
     findings-JSON must stay complete).
  3) Non-text blocks (tool_use / tool_result) are emitted in BOTH modes.
  4) `_extract_stream_text_delta` is tolerant of non-delta / malformed shapes.

Run:  cd backend && .venv/bin/python -m unittest tests.test_partial_streaming -v
"""

from __future__ import annotations

import queue
import unittest

from app.config import settings
from app.services.agent import _emit_assistant_blocks, _extract_stream_text_delta


def _drain(q: "queue.Queue") -> list[dict]:
    out: list[dict] = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            break
    return out


class ExtractStreamTextDeltaTest(unittest.TestCase):
    """The stream_event → text_delta extractor (flag-independent, pure)."""

    def test_valid_content_block_delta_returns_chunk(self):
        data = {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "hello"},
            },
        }
        self.assertEqual(_extract_stream_text_delta(data), "hello")

    def test_non_delta_event_returns_empty(self):
        # message_start / content_block_start / stop wrappers carry no text.
        for ev_type in ("message_start", "content_block_start", "content_block_stop", "message_stop"):
            data = {"type": "stream_event", "event": {"type": ev_type}}
            self.assertEqual(_extract_stream_text_delta(data), "")

    def test_non_text_delta_returns_empty(self):
        # e.g. an input_json_delta (tool args streaming) is not preview text.
        data = {
            "type": "stream_event",
            "event": {"type": "content_block_delta",
                      "delta": {"type": "input_json_delta", "partial_json": "{"}},
        }
        self.assertEqual(_extract_stream_text_delta(data), "")

    def test_malformed_shapes_return_empty(self):
        for data in ({}, {"event": None}, {"event": {}},
                     {"event": {"type": "content_block_delta"}},
                     {"event": {"type": "content_block_delta", "delta": {"type": "text_delta"}}}):
            self.assertEqual(_extract_stream_text_delta(data), "")


class EmitAssistantBlocksDedupTest(unittest.TestCase):
    """The Story 1.4 dedup gate inside the assistant-block parser."""

    def setUp(self):
        # Snapshot the flag so tests never leak state to the rest of the suite.
        self._orig = settings.AGENT_STREAM_PARTIAL_MESSAGES

    def tearDown(self):
        settings.AGENT_STREAM_PARTIAL_MESSAGES = self._orig

    def test_flag_off_emits_text_and_accumulates(self):
        """Default behaviour: text block → `text` event + full_response_text."""
        settings.AGENT_STREAM_PARTIAL_MESSAGES = False
        q: "queue.Queue" = queue.Queue()
        full: list[str] = []
        blocks = [{"type": "text", "text": "The answer is 42."}]

        _emit_assistant_blocks(blocks, q, full, stream_partial=False)

        events = _drain(q)
        self.assertEqual(events, [{"type": "text", "content": "The answer is 42."}])
        self.assertEqual("".join(full), "The answer is 42.")

    def test_flag_on_suppresses_text_but_still_accumulates(self):
        """Partial ON: NO `text` event re-emitted (deltas already streamed it),
        yet full_response_text stays complete for persistence / findings JSON."""
        settings.AGENT_STREAM_PARTIAL_MESSAGES = True
        q: "queue.Queue" = queue.Queue()
        full: list[str] = []
        blocks = [{"type": "text", "text": "The answer is 42."}]

        _emit_assistant_blocks(blocks, q, full, stream_partial=True)

        events = _drain(q)
        # No `text` event → no doubling with the already-streamed text_deltas.
        self.assertEqual([e for e in events if e.get("type") == "text"], [])
        # But the accumulator MUST still be complete.
        self.assertEqual("".join(full), "The answer is 42.")

    def test_delta_then_final_message_no_doubling(self):
        """End-to-end shape: the token-level deltas stream the text, then the
        final `assistant` message carries the SAME complete text. With the flag
        ON the streamed text appears exactly ONCE (deltas), never doubled."""
        settings.AGENT_STREAM_PARTIAL_MESSAGES = True
        q: "queue.Queue" = queue.Queue()
        full: list[str] = []

        # 1) The CLI streams token-level deltas (parsed in the stdout loop).
        delta_lines = [
            {"type": "stream_event", "event": {"type": "content_block_delta",
             "delta": {"type": "text_delta", "text": "The "}}},
            {"type": "stream_event", "event": {"type": "content_block_delta",
             "delta": {"type": "text_delta", "text": "answer is 42."}}},
        ]
        for line in delta_lines:
            chunk = _extract_stream_text_delta(line)
            if chunk:
                q.put({"type": "text_delta", "content": chunk})

        # 2) The final complete `assistant` message arrives too.
        _emit_assistant_blocks(
            [{"type": "text", "text": "The answer is 42."}], q, full, stream_partial=True,
        )

        events = _drain(q)
        deltas = [e for e in events if e.get("type") == "text_delta"]
        texts = [e for e in events if e.get("type") == "text"]
        # Deltas carried the streamed text; final message added NO `text` event.
        self.assertEqual("".join(e["content"] for e in deltas), "The answer is 42.")
        self.assertEqual(texts, [])
        # Persisted text (from full_response_text) is complete and un-doubled.
        self.assertEqual("".join(full), "The answer is 42.")

    def test_tool_blocks_emitted_in_both_modes(self):
        """tool_use / tool_result blocks must still be emitted with the flag ON
        (the dedup gate applies ONLY to text)."""
        blocks = [
            {"type": "text", "text": "checking"},
            {"type": "tool_use", "id": "t1", "name": "mcp__google-ads__get_campaigns", "input": {}},
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
        ]
        for flag in (False, True):
            with self.subTest(flag=flag):
                settings.AGENT_STREAM_PARTIAL_MESSAGES = flag
                q: "queue.Queue" = queue.Queue()
                full: list[str] = []
                _emit_assistant_blocks(blocks, q, full, stream_partial=flag)
                events = _drain(q)
                types = [e["type"] for e in events]
                self.assertIn("tool_call", types)
                self.assertIn("tool_result", types)
                # text present only when the flag is OFF.
                self.assertEqual(("text" in types), (flag is False))
                # full_response_text accumulates in BOTH modes.
                self.assertEqual("".join(full), "checking")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
