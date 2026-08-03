"""Near-dup Python twin: parity lock + determinism + Diversify (Epic 16, 16.4).

Fence F5 — the Python detector (``app.services.near_dup``) reads the SAME golden
fixture the vitest twin (``frontend/src/lib/nearDup.test.ts``) reads and MUST
produce identical flag sets on every case. A disagreement fails CI on both sides.

Also: threshold tuning on the labeled REAL-Mercan set (Risk R1), the zero-
subprocess determinism assert (FR1.10), and the Diversify job (locked rows
excluded, verify-below-threshold).

Run: cd backend && .venv/bin/python -m pytest tests/test_near_dup_parity.py -q
"""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

from app.services import creative_specs as cs
from app.services import near_dup

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
# The SAME path the vitest parity suite loads (symlink-free, single source).
_GOLDEN = json.loads((_FIXTURES / "near_dup_cases.json").read_text(encoding="utf-8"))
_LABELED = json.loads((_FIXTURES / "near_dup_mercan_labeled.json").read_text(encoding="utf-8"))


class ParityFixture(unittest.TestCase):
    def test_stopwords_match_fixture_no_drift(self):
        self.assertEqual(list(near_dup.STOPWORDS), _GOLDEN["stopwords"])

    def test_every_case_flags_the_expected_pairs(self):
        for case in _GOLDEN["cases"]:
            pairs = near_dup.find_near_dup_pairs(
                case["texts"],
                threshold=_GOLDEN["threshold"],
                stopwords=_GOLDEN["stopwords"],
            )
            self.assertEqual(
                pairs, [list(p) for p in case["expected_pairs"]],
                f"parity mismatch on case {case['name']!r}",
            )

    def test_two_known_near_dupes_stable_on_repeat(self):
        case = next(c for c in _GOLDEN["cases"] if c["name"] == "fifteen-rows-two-dupes")
        a = near_dup.find_near_dup_pairs(case["texts"], threshold=_GOLDEN["threshold"],
                                         stopwords=_GOLDEN["stopwords"])
        b = near_dup.find_near_dup_pairs(case["texts"], threshold=_GOLDEN["threshold"],
                                         stopwords=_GOLDEN["stopwords"])
        self.assertEqual(a, [[3, 11]])
        self.assertEqual(a, b)  # deterministic on repeat

    def test_threshold_defaults_to_registry(self):
        # No threshold arg → uses ENGINE.near_dup_threshold (0.65).
        self.assertEqual(cs.ENGINE.near_dup_threshold, _GOLDEN["threshold"])
        pairs = near_dup.find_near_dup_pairs(["Move to Panama", "Move to Panama today"])
        self.assertEqual(pairs, [[0, 1]])


class DeterministicNoSubprocess(unittest.TestCase):
    def test_detection_calls_no_subprocess_or_agent(self):
        # FR1.10 spy: detection is pure. Poison subprocess + the agent stream; if
        # detection touched either, these would raise.
        import subprocess

        import app.services.agent as agent_mod

        orig_run, orig_popen = subprocess.run, subprocess.Popen
        orig_stream = agent_mod.stream_agent_response

        def _boom(*_a, **_k):
            raise AssertionError("detection must not spawn a subprocess / call the agent")

        subprocess.run = _boom  # type: ignore[assignment]
        subprocess.Popen = _boom  # type: ignore[assignment]
        agent_mod.stream_agent_response = _boom  # type: ignore[assignment]
        try:
            near_dup.find_near_dup_pairs(_LABELED["texts"])
        finally:
            subprocess.run = orig_run  # type: ignore[assignment]
            subprocess.Popen = orig_popen  # type: ignore[assignment]
            agent_mod.stream_agent_response = orig_stream


class ThresholdTuningR1(unittest.TestCase):
    """Tune ENGINE.near_dup_threshold on the labeled real-Mercan set (R1). The
    result is recorded in the story's feature-log row."""

    def test_065_achieves_high_precision_and_recall(self):
        detected = {tuple(p) for p in near_dup.find_near_dup_pairs(
            _LABELED["texts"], threshold=_LABELED["threshold"])}
        labeled = {tuple(p) for p in _LABELED["labeled_dup_pairs"]}
        tp = len(detected & labeled)
        precision = tp / len(detected) if detected else 1.0
        recall = tp / len(labeled) if labeled else 1.0
        # 0.65 must not false-positive on distinct immigration copy and must catch
        # the token-overlap near-dupes (paraphrase-only dupes are out of scope, R1).
        self.assertGreaterEqual(precision, 0.9, f"precision {precision} at 0.65")
        self.assertGreaterEqual(recall, 0.9, f"recall {recall} at 0.65")


class Diversify(unittest.TestCase):
    def setUp(self):
        import app.services.agent as agent_mod
        self._agent = agent_mod
        self._orig = agent_mod.stream_agent_response

    def tearDown(self):
        self._agent.stream_agent_response = self._orig

    def _stream(self, text: str):
        async def _gen(*_a, **_k) -> AsyncIterator[Dict[str, Any]]:
            yield {"type": "text", "content": json.dumps({"text": text})}
        return _gen

    def _run(self, coro):
        return asyncio.run(coro)

    def test_locked_row_excluded_and_set_verified(self):
        # rows 0 & 1 are near-dupes; row 1 is LOCKED → only row 0 regenerates.
        rows: List[Dict[str, str]] = [
            {"text": "Move to Panama", "angle": "benefit", "tier": "headline"},
            {"text": "Move to Panama today", "angle": "benefit", "tier": "headline"},
            {"text": "Greece Golden Visa route", "angle": "feature", "tier": "headline"},
        ]
        self._agent.stream_agent_response = self._stream("Retire in the Caribbean sun")
        request = {"rows": rows, "flagged_rows": [0, 1], "locked_rows": [1]}
        out = self._run(near_dup.diversify("acc", "pmax", request=request))
        # locked row 1 unchanged (excluded from regenerate)
        self.assertEqual(out["rows"][1], rows[1])
        # row 0 replaced with the regenerated, non-duplicate line
        self.assertEqual(out["rows"][0]["text"], "Retire in the Caribbean sun")
        self.assertTrue(out["below_threshold"])
        self.assertEqual(out["flagged_after"], [])

    def test_dismissed_pair_does_not_block_verify(self):
        rows = [
            {"text": "Panama residency now", "angle": "urgency", "tier": "headline"},
            {"text": "Panama residency now", "angle": "benefit", "tier": "headline"},
        ]
        # nothing flagged to regenerate, but the identical pair is DISMISSED → the
        # verify treats the set as below threshold (R1 escape hatch).
        request = {"rows": rows, "flagged_rows": [], "locked_rows": [],
                   "dismissed_dup_pairs": [[0, 1]]}
        out = self._run(near_dup.diversify("acc", "pmax", request=request))
        self.assertTrue(out["below_threshold"])
        self.assertEqual(out["dismissed_dup_pairs"], [[0, 1]])


if __name__ == "__main__":
    unittest.main()
