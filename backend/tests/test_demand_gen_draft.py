"""Demand Gen assisted copy drafting — the wizard's Creative Director draft
(POST /api/accounts/{id}/demand-gen/draft-copy → poll GET .../draft-copy/{id}).

Drives the async route/inner functions directly (repo style), with
`stream_agent_response` monkeypatched to return canned Creative Director JSON.
Asserts the DG hard limits are re-enforced server-side: over-length lines are
DROPPED (never truncated into garbage), business_name is clipped to 25 / falls
back to the operator's own entry, too-few valid lines fail so the operator
regenerates, and the job-store start/poll lifecycle returns the result.

No DB, no live Google or Claude calls.

Run: cd backend && .venv/bin/python -m unittest tests.test_demand_gen_draft -v
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, AsyncIterator, Dict

from fastapi import HTTPException

from app.routers import demand_gen as dgr


def _run(coro):
    return asyncio.run(coro)


def _fake_stream(payload_json: str):
    """Return an async-generator stand-in for stream_agent_response that emits
    the canned Creative Director JSON as one text event."""

    async def _gen(*_args, **_kwargs) -> AsyncIterator[Dict[str, Any]]:
        yield {"type": "text", "content": payload_json}

    return _gen


class DGDraftInner(unittest.TestCase):
    def setUp(self):
        import app.services.agent as agent_mod

        self._agent_mod = agent_mod
        self._orig = agent_mod.stream_agent_response

    def tearDown(self):
        self._agent_mod.stream_agent_response = self._orig

    def _patch(self, payload_json: str):
        self._agent_mod.stream_agent_response = _fake_stream(payload_json)

    def test_enforces_limits_and_drafts_business_name(self):
        self._patch(
            '{"business_name": "Mercan Group Immigration Advisory Services",'
            ' "headlines": ["Invest in Panama",'
            ' "This headline is definitely over thirty characters long",'
            ' "Second residency"],'
            ' "descriptions": ["Panama investor visa, done right.", "x"]}'
        )
        body = dgr.DGDraftRequest(
            brief="b", final_url="https://x", business_name="Mercan", campaign_name="c",
        )
        resp = _run(dgr._draft_dg_copy_inner("acc", body))
        # business_name clipped to ≤25 (never fails on a long brand name)
        self.assertLessEqual(len(resp.business_name), 25)
        # over-length headline DROPPED (not truncated) — 2 valid remain, in order
        self.assertEqual(resp.headlines, ["Invest in Panama", "Second residency"])
        self.assertTrue(all(len(h) <= 30 for h in resp.headlines))
        self.assertEqual(resp.descriptions, ["Panama investor visa, done right.", "x"])

    def test_business_name_falls_back_to_operator_entry(self):
        self._patch('{"headlines": ["A", "B"], "descriptions": ["desc one"]}')
        resp = _run(dgr._draft_dg_copy_inner("acc", dgr.DGDraftRequest(business_name="Mercan")))
        self.assertEqual(resp.business_name, "Mercan")

    def test_too_few_valid_headlines_raises_502(self):
        # every headline is over 30 chars → all dropped → 0 valid < min 1
        self._patch(
            '{"business_name": "Mercan",'
            ' "headlines": ["this one is way over the thirty character maximum limit"],'
            ' "descriptions": ["ok description"]}'
        )
        with self.assertRaises(HTTPException) as c:
            _run(dgr._draft_dg_copy_inner("acc", dgr.DGDraftRequest()))
        self.assertEqual(c.exception.status_code, 502)

    def test_no_json_raises_502(self):
        self._patch("sorry, no json here")
        with self.assertRaises(HTTPException) as c:
            _run(dgr._draft_dg_copy_inner("acc", dgr.DGDraftRequest()))
        self.assertEqual(c.exception.status_code, 502)


class DGDraftJobStore(unittest.TestCase):
    def test_start_then_poll_returns_done_result(self):
        import app.services.agent as agent_mod

        orig = agent_mod.stream_agent_response
        agent_mod.stream_agent_response = _fake_stream(
            '{"business_name": "Mercan", "headlines": ["A", "B"], "descriptions": ["one desc"]}'
        )
        try:
            async def _flow():
                start = await dgr.start_draft_demand_gen_copy("acc", dgr.DGDraftRequest())
                draft_id = start["draft_id"]
                self.assertEqual(start["status"], "running")
                for _ in range(50):  # let the background task settle
                    await asyncio.sleep(0.02)
                    job = await dgr.get_draft_demand_gen_copy(draft_id)
                    if job["status"] != "running":
                        return job
                return job

            job = _run(_flow())
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"]["business_name"], "Mercan")
            self.assertEqual(job["result"]["headlines"], ["A", "B"])
        finally:
            agent_mod.stream_agent_response = orig

    def test_unknown_draft_id_returns_error(self):
        job = _run(dgr.get_draft_demand_gen_copy("nope-not-a-real-id"))
        self.assertEqual(job["status"], "error")


if __name__ == "__main__":
    unittest.main()
