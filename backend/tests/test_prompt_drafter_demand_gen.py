"""Unit tests for the Demand Gen creative preset + reference-asset anchoring
in the Studio prompt drafter — NO Claude CLI spawns (the LLM call is stubbed).

Covers:
  * `_reference_block` renders empty vs. an anchor instruction
  * Stage 2 injects the Demand Gen preset addendum (text-free, DG aspects,
    editorial) ONLY when preset='demand_gen' AND target='image'
  * the reference note is injected regardless of preset when supplied
  * neither block leaks into a default (no-preset, no-reference) draft

Run: cd backend && .venv/bin/python -m pytest tests/test_prompt_drafter_demand_gen.py -q
"""

from __future__ import annotations

import unittest

from app.services import prompt_drafter as pd


_CAPTURED: dict[str, str] = {}


async def _fake_claude(*, system: str, user: str, model: str = "sonnet", timeout_s: float = 45.0) -> str:
    """Capture the assembled prompt; return a well-formed 3-variant envelope."""
    _CAPTURED["system"] = system
    _CAPTURED["user"] = user
    return (
        '{"variants": ['
        '{"angle": "problem-led", "prompt": "p", "rationale": "r"},'
        '{"angle": "aspirational", "prompt": "a", "rationale": "r"},'
        '{"angle": "social-proof", "prompt": "s", "rationale": "r"}]}'
    )


_BRIEF = {
    "subject": "an investor in their 50s",
    "setting": "a Mediterranean waterfront",
    "value_prop": "residency by investment",
    "audience": "HNW investors",
    "tone": "aspirational",
    "program": "greece",
    "hard_constraints": [],
    "claim_hints": [],
}


class ReferenceBlockTests(unittest.TestCase):
    def test_empty_when_no_note(self):
        self.assertEqual(pd._reference_block(None), "")
        self.assertEqual(pd._reference_block("   "), "")

    def test_anchor_instruction_when_note_present(self):
        block = pd._reference_block("hotel-facade.jpg, lobby.jpg")
        self.assertIn("REFERENCE ASSETS ATTACHED", block)
        self.assertIn("this exact hotel property", block)
        self.assertIn("hotel-facade.jpg", block)


class Stage2PresetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _CAPTURED.clear()
        self._orig = pd._claude_one_shot
        pd._claude_one_shot = _fake_claude  # type: ignore[assignment]

    def tearDown(self) -> None:
        pd._claude_one_shot = self._orig  # type: ignore[assignment]

    async def test_demand_gen_preset_injects_addendum(self):
        out = await pd._stage2_draft(
            brief=_BRIEF, target="image", pinned_claims=[],
            visual_director_system="VD", preset="demand_gen",
        )
        self.assertEqual(len(out), 3)
        user = _CAPTURED["user"]
        self.assertIn("DEMAND GEN CREATIVE PRESET", user)
        self.assertIn("NO text", user)
        self.assertIn("1.91:1", user)

    async def test_demand_gen_preset_not_applied_to_video(self):
        await pd._stage2_draft(
            brief=_BRIEF, target="video", pinned_claims=[],
            visual_director_system="VD", preset="demand_gen",
        )
        self.assertNotIn("DEMAND GEN CREATIVE PRESET", _CAPTURED["user"])

    async def test_reference_note_injected_with_preset(self):
        await pd._stage2_draft(
            brief=_BRIEF, target="image", pinned_claims=[],
            visual_director_system="VD", preset="demand_gen",
            reference_note="hotel.jpg",
        )
        user = _CAPTURED["user"]
        self.assertIn("REFERENCE ASSETS ATTACHED", user)
        self.assertIn("hotel.jpg", user)

    async def test_default_draft_has_neither_block(self):
        await pd._stage2_draft(
            brief=_BRIEF, target="image", pinned_claims=[],
            visual_director_system="VD",
        )
        user = _CAPTURED["user"]
        self.assertNotIn("DEMAND GEN CREATIVE PRESET", user)
        self.assertNotIn("REFERENCE ASSETS ATTACHED", user)


if __name__ == "__main__":
    unittest.main()
