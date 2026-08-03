"""Copy-Workbench drafting contract (Epic 16, story 16.1 · FR1.7/1.9/1.13).

Covers the unified ``[{text, angle, tier}]`` service in
``app.services.creative_copy``: row parsing (new + legacy shapes, malformed
drop), the prompt builder (angle/tier menus + DG-parity policy block +
business_name), draft_copy / rewrite_row, and the job runner + poll lifecycle.

``stream_agent_response`` is monkeypatched to canned JSON — no live Claude/Google.
The job store is DB-backed (story 15.3), so a throwaway temp SQLite is inited.

Run: cd backend && .venv/bin/python -m pytest tests/test_creative_copy.py -q
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, AsyncIterator, Dict

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="copy-job-test-"))
settings.DATA_DIR = _TMP

from app.database import init_db  # noqa: E402
from app.services import creative_copy as cc  # noqa: E402
from app.services import creative_specs as cs  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


def _fake_stream(payload_json: str):
    async def _gen(*_a, **_k) -> AsyncIterator[Dict[str, Any]]:
        yield {"type": "text", "content": payload_json}
    return _gen


class ParseRows(unittest.TestCase):
    def setUp(self):
        self.spec = cs.get("pmax")

    def test_new_shape_valid_rows_kept(self):
        parsed = {"rows": [
            {"text": "Invest in Panama", "angle": "benefit", "tier": "headline"},
            {"text": "Move now, act fast", "angle": "urgency", "tier": "headline"},
        ]}
        rows = cc.parse_rows(parsed, self.spec)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"text": "Invest in Panama", "angle": "benefit", "tier": "headline"})

    def test_malformed_rows_dropped(self):
        parsed = {"rows": [
            {"text": "", "angle": "benefit", "tier": "headline"},            # empty → drop
            {"text": "ok", "angle": "benefit", "tier": "nonsense"},           # bad tier → drop
            {"text": "x" * 31, "angle": "benefit", "tier": "headline"},       # >30 → drop
            {"text": "Valid one", "angle": "benefit", "tier": "headline"},    # kept
            "not-a-dict",                                                     # → drop
        ]}
        rows = cc.parse_rows(parsed, self.spec)
        self.assertEqual([r["text"] for r in rows], ["Valid one"])

    def test_unknown_angle_coerced_not_dropped(self):
        parsed = {"rows": [{"text": "Keep me", "angle": "made_up", "tier": "headline"}]}
        rows = cc.parse_rows(parsed, self.spec)
        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0]["angle"], cs.ANGLES)

    def test_legacy_shape_reconstructs_rows(self):
        parsed = {"headlines": ["A", "B"], "long_headlines": ["Long one"],
                  "descriptions": ["Desc one"]}
        rows = cc.parse_rows(parsed, self.spec)
        tiers = sorted({r["tier"] for r in rows})
        self.assertEqual(tiers, ["description", "headline", "long_headline"])
        self.assertTrue(all(r["angle"] in cs.ANGLES for r in rows))

    def test_short_description_folds_when_absent(self):
        dg = cs.get("demand_gen")   # no short_description slot
        parsed = {"rows": [{"text": "hi", "angle": "benefit", "tier": "short_description"}]}
        rows = cc.parse_rows(parsed, dg)
        self.assertEqual(rows[0]["tier"], "description")


class RowsToLegacy(unittest.TestCase):
    def test_grouping_preserves_order(self):
        rows = [
            {"text": "h1", "angle": "benefit", "tier": "headline"},
            {"text": "lh1", "angle": "feature", "tier": "long_headline"},
            {"text": "h2", "angle": "urgency", "tier": "headline"},
            {"text": "d1", "angle": "benefit", "tier": "description"},
            {"text": "sd1", "angle": "benefit", "tier": "short_description"},
        ]
        legacy = cc.rows_to_legacy(rows)
        self.assertEqual(legacy["headlines"], ["h1", "h2"])
        self.assertEqual(legacy["long_headlines"], ["lh1"])
        self.assertEqual(legacy["descriptions"], ["d1", "sd1"])   # short folds in


class BuildPrompt(unittest.TestCase):
    def test_prompt_has_menus_and_policy(self):
        p = cc.build_draft_prompt("pmax", brief="b", final_url="https://x")
        for angle in cs.ANGLES:
            self.assertIn(angle, p)
        self.assertIn("headline", p)
        self.assertIn("business_name", p)
        self.assertIn("rows", p)

    def test_pmax_reaches_dg_policy_parity(self):
        # FR1.13 — PMax prompt carries the full DG policy block + business_name cap.
        p = cc.build_draft_prompt("pmax")
        self.assertIn("guaranteed-approval", p)
        self.assertIn("~ | +", p)
        self.assertIn("em dashes", p.lower())
        self.assertIn(f"≤{cs.get('pmax').business_name_max} chars", p)

    def test_dg_prompt_has_no_long_headline_tier(self):
        p = cc.build_draft_prompt("demand_gen")
        self.assertNotIn("long_headline", p)


class PMaxPromptParity(unittest.TestCase):
    """Story 16.6 (FR1.13) — the PMax draft prompt reaches DG parity: the SAME
    policy block + a drafted ≤25-char business_name. Snapshot-pinned."""

    # The policy block, lifted from the old DG prompt (demand_gen.py:283-287).
    _POLICY_MARKERS = (
        "NO prices or discounts",
        "guaranteed-approval",
        "~ | +",
        "No em dashes",
        "No third-party brand names",
    )

    def test_pmax_prompt_carries_full_policy_block(self):
        p = cc.build_draft_prompt("pmax")
        for marker in self._POLICY_MARKERS:
            self.assertIn(marker, p, f"PMax prompt missing policy marker {marker!r}")

    def test_pmax_and_dg_share_the_policy_block(self):
        # The policy block is identical across types (one unified prompt) — the
        # concrete meaning of "PMax reaches DG parity".
        pmax = cc.build_draft_prompt("pmax")
        dg = cc.build_draft_prompt("demand_gen")
        for marker in self._POLICY_MARKERS:
            self.assertIn(marker, pmax)
            self.assertIn(marker, dg)

    def test_pmax_prompt_requests_a_capped_business_name(self):
        p = cc.build_draft_prompt("pmax")
        self.assertIn("business_name", p)
        self.assertIn(f"≤{cs.get('pmax').business_name_max} chars", p)


class DraftCopy(unittest.TestCase):
    def setUp(self):
        import app.services.agent as agent_mod
        self._agent = agent_mod
        self._orig = agent_mod.stream_agent_response

    def tearDown(self):
        self._agent.stream_agent_response = self._orig

    def test_draft_copy_returns_typed_rows(self):
        self._agent.stream_agent_response = _fake_stream(
            '{"business_name": "Mercan Group Immigration Advisory Services", "rows": ['
            '{"text": "Invest in Panama", "angle": "benefit", "tier": "headline"},'
            '{"text": "Act now", "angle": "urgency", "tier": "headline"}]}'
        )
        out = _run(cc.draft_copy("acc", "pmax", brief="b", business_name="Mercan"))
        self.assertLessEqual(len(out["business_name"]), 25)
        self.assertEqual(len(out["rows"]), 2)
        self.assertTrue(all(r["angle"] in cs.ANGLES and r["tier"] in cs.TIERS for r in out["rows"]))

    def test_draft_copy_no_json_raises_valueerror(self):
        self._agent.stream_agent_response = _fake_stream("no json here at all")
        with self.assertRaises(ValueError):
            _run(cc.draft_copy("acc", "pmax"))


class RewriteRow(unittest.TestCase):
    def setUp(self):
        import app.services.agent as agent_mod
        self._agent = agent_mod
        self._orig = agent_mod.stream_agent_response

    def tearDown(self):
        self._agent.stream_agent_response = self._orig

    def test_only_target_row_replaced(self):
        self._agent.stream_agent_response = _fake_stream('{"text": "Brand-new urgent line"}')
        rows = [
            {"text": "keep 0", "angle": "benefit", "tier": "headline"},
            {"text": "replace me", "angle": "benefit", "tier": "headline"},
            {"text": "keep 2", "angle": "feature", "tier": "headline"},
        ]
        out = _run(cc.rewrite_row("acc", "pmax", rows=rows, row_index=1, target_angle="urgency"))
        self.assertEqual(out["rows"][0], rows[0])          # byte-identical
        self.assertEqual(out["rows"][2], rows[2])          # byte-identical
        self.assertEqual(out["rows"][1]["text"], "Brand-new urgent line")
        self.assertEqual(out["rows"][1]["angle"], "urgency")


class OnImageTextPolicyFlip(unittest.TestCase):
    """FR1.6 / NFR-C1 — the prompt builder reads spec.policy; a fixture flip
    changes the emitted instruction with ZERO code change. (Migrated here from
    test_demand_gen_draft.py when the legacy DG draft route was deleted, 16.8.)"""

    def test_flip_rda_forbid_to_allow_changes_instruction(self):
        import dataclasses
        rda = cs.get("rda")
        self.assertEqual(rda.policy.on_image_text, "forbid")
        forbid_line = cs.on_image_text_instruction(rda)
        allow_rda = dataclasses.replace(
            rda, policy=dataclasses.replace(rda.policy, on_image_text="allow_warned"))
        allow_line = cs.on_image_text_instruction(allow_rda)
        self.assertNotEqual(forbid_line, allow_line)
        self.assertIn("OUT of generated images", forbid_line)
        self.assertIn("WARNED", allow_line)


class CopyJobLifecycle(unittest.TestCase):
    def test_run_job_draft_persists_rows(self):
        import app.services.agent as agent_mod
        orig = agent_mod.stream_agent_response
        agent_mod.stream_agent_response = _fake_stream(
            '{"business_name": "Mercan", "rows": ['
            '{"text": "One", "angle": "benefit", "tier": "headline"}]}'
        )
        try:
            async def _flow():
                job_id = await cc.create_job("draft", "acc", "pmax", {"brief": "b"})
                await cc.run_copy_job(job_id, "draft", "acc", "pmax", {"brief": "b"})
                return await cc.get_job(job_id)
            job = _run(_flow())
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"]["rows"][0]["text"], "One")
        finally:
            agent_mod.stream_agent_response = orig

    def test_run_job_records_failure(self):
        import app.services.agent as agent_mod
        orig = agent_mod.stream_agent_response
        agent_mod.stream_agent_response = _fake_stream("no json")
        try:
            async def _flow():
                job_id = await cc.create_job("draft", "acc", "pmax", {})
                await cc.run_copy_job(job_id, "draft", "acc", "pmax", {})
                return await cc.get_job(job_id)
            job = _run(_flow())
            self.assertEqual(job["status"], "error")
        finally:
            agent_mod.stream_agent_response = orig


if __name__ == "__main__":
    unittest.main()
