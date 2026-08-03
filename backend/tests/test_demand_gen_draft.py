"""Demand Gen assisted copy drafting — the wizard's Creative Director draft
(POST /api/accounts/{id}/demand-gen/draft-copy → poll GET .../draft-copy/{id}).

Drives the async route/inner functions directly (repo style), with
`stream_agent_response` monkeypatched to return canned Creative Director JSON.
Asserts the DG hard limits are re-enforced server-side: over-length lines are
DROPPED (never truncated into garbage), business_name is clipped to 25 / falls
back to the operator's own entry, too-few valid lines fail so the operator
regenerates, and the job-store start/poll lifecycle returns the result.

No live Google or Claude calls. As of story 15.3 the draft-job store is a
`creative_jobs` DB row (not an in-memory dict), so this module inits a throwaway
temp SQLite; the pure inner-function tests ignore it.

Run: cd backend && .venv/bin/python -m unittest tests.test_demand_gen_draft -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, AsyncIterator, Dict

from fastapi import HTTPException

from app.config import settings

# Throwaway data dir BEFORE importing the router (job store is DB-backed now).
_TMP = Path(tempfile.mkdtemp(prefix="dg-draft-test-"))
settings.DATA_DIR = _TMP

from app.database import init_db  # noqa: E402
from app.routers import demand_gen as dgr  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


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
        self.assertTrue(all(len(h) <= 40 for h in resp.headlines))
        self.assertEqual(resp.descriptions, ["Panama investor visa, done right.", "x"])

    def test_business_name_falls_back_to_operator_entry(self):
        self._patch('{"headlines": ["A", "B"], "descriptions": ["desc one"]}')
        resp = _run(dgr._draft_dg_copy_inner("acc", dgr.DGDraftRequest(business_name="Mercan")))
        self.assertEqual(resp.business_name, "Mercan")

    def test_too_few_valid_headlines_raises_502(self):
        # every headline is over 40 chars → all dropped → 0 valid < min 1
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


class DGDraftPromptFromRegistry(unittest.TestCase):
    """Story 14.4 — the draft prompt is BUILT from the registry (FR1.5/FR1.6)."""

    def _spec(self):
        from app.services import creative_specs
        return creative_specs.get("demand_gen")

    def test_prompt_hard_limits_track_the_registry(self):
        spec = self._spec()
        body = dgr.DGDraftRequest(brief="b", final_url="https://x",
                                  business_name="Mercan", campaign_name="c")
        prompt = dgr._dg_draft_prompt(body, spec)
        # char caps come from the registry, not a literal in the prompt string
        self.assertIn(f"≤{spec.text['headlines'].max_chars} chars", prompt)
        self.assertIn(f"≤{spec.text['descriptions'].max_chars} chars", prompt)
        self.assertIn(f"≤{spec.business_name_max} chars", prompt)

    def test_prompt_has_deliberate_40char_instruction(self):
        # FR1.5: the raised 40-char headline budget must be used deliberately.
        spec = self._spec()
        prompt = dgr._dg_draft_prompt(dgr.DGDraftRequest(), spec)
        self.assertEqual(spec.text["headlines"].max_chars, 40)
        self.assertIn("40", prompt)
        self.assertIn("deliberately", prompt.lower())
        self.assertIn("do not pad", prompt.lower())


class OnImageTextPolicyFlip(unittest.TestCase):
    """Story 14.4 / FR1.6 / NFR-C1 — the prompt builder reads spec.policy; a
    fixture flip changes the emitted prompt with ZERO code change."""

    def test_flip_rda_forbid_to_allow_changes_prompt(self):
        import dataclasses
        from app.services import creative_specs as cs

        rda = cs.get("rda")
        self.assertEqual(rda.policy.on_image_text, "forbid")
        forbid_line = cs.on_image_text_instruction(rda)

        allow_rda = dataclasses.replace(
            rda, policy=dataclasses.replace(rda.policy, on_image_text="allow_warned")
        )
        allow_line = cs.on_image_text_instruction(allow_rda)

        self.assertNotEqual(forbid_line, allow_line)
        self.assertIn("OUT of generated images", forbid_line)
        self.assertIn("WARNED", allow_line)


if __name__ == "__main__":
    unittest.main()
