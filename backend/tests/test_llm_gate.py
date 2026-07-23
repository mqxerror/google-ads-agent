"""Chat-hardening item 1 — the global Claude-CLI concurrency gate.

Stdlib unittest, NO network, NO real CLI. Proves:
  * get_gate() is ONE shared instance within a loop (rebuilt per loop) sized
    from settings — the "shared across components" guarantee.
  * The gate actually CAPS concurrency: many concurrent acquirers never exceed
    the configured size (peak concurrency ≤ size).
  * prompt_drafter._claude_one_shot (the 2nd real Claude spawn site) routes its
    subprocess through the SAME gate — 4 concurrent one-shots with size 2 peak
    at 2, proving the cross-component ceiling is real, not just a primitive.

Run:  cd backend && python -m unittest tests.test_llm_gate -v
"""

from __future__ import annotations

import asyncio
import unittest

from app.config import settings
from app.services import llm_gate


class GateSingleton(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig = settings.LLM_GLOBAL_MAX_CONCURRENCY
        llm_gate._reset_for_tests()

    def tearDown(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = self._orig
        llm_gate._reset_for_tests()

    async def test_same_instance_within_loop(self):
        # Every component that asks within one loop gets the IDENTICAL object —
        # that shared identity IS the cross-component ceiling.
        a = llm_gate.get_gate()
        b = llm_gate.get_gate()
        self.assertIs(a, b)

    async def test_size_from_settings(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = 3
        llm_gate._reset_for_tests()
        g = llm_gate.get_gate()
        self.assertEqual(g._value, 3)  # unacquired semaphore value == size

    async def test_bad_setting_falls_back(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = 0  # invalid → default
        self.assertEqual(llm_gate.gate_size(), 4)


class GateCaps(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._orig = settings.LLM_GLOBAL_MAX_CONCURRENCY
        llm_gate._reset_for_tests()

    def tearDown(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = self._orig
        llm_gate._reset_for_tests()

    async def test_peak_concurrency_never_exceeds_size(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = 2
        llm_gate._reset_for_tests()
        live = 0
        peak = 0

        async def worker():
            nonlocal live, peak
            async with llm_gate.llm_slot():
                live += 1
                peak = max(peak, live)
                await asyncio.sleep(0.02)
                live -= 1

        # 8 concurrent runs (chat + audit + scheduler + video would stampede
        # WITHOUT the gate) — with size 2 the peak must stay at 2.
        await asyncio.gather(*(worker() for _ in range(8)))
        self.assertEqual(peak, 2)
        # Gate fully released afterward.
        self.assertEqual(llm_gate.get_gate()._value, 2)


class PromptDrafterRoutesThroughGate(unittest.IsolatedAsyncioTestCase):
    """The 2nd Claude spawn site (video-director decompose) must share the gate."""

    def setUp(self):
        self._orig = settings.LLM_GLOBAL_MAX_CONCURRENCY
        llm_gate._reset_for_tests()

    def tearDown(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = self._orig
        llm_gate._reset_for_tests()

    async def test_claude_one_shot_respects_global_gate(self):
        settings.LLM_GLOBAL_MAX_CONCURRENCY = 2
        llm_gate._reset_for_tests()
        from app.services import prompt_drafter

        live = 0
        peak = 0

        class _FakeProc:
            returncode = 0

            async def communicate(self, input=None):
                nonlocal live, peak
                live += 1
                peak = max(peak, live)
                await asyncio.sleep(0.02)
                live -= 1
                return (b"drafted", b"")

            def kill(self):
                pass

            async def wait(self):
                return 0

        async def _fake_exec(*args, **kwargs):
            return _FakeProc()

        orig = asyncio.create_subprocess_exec
        asyncio.create_subprocess_exec = _fake_exec  # type: ignore
        try:
            await asyncio.gather(*(
                prompt_drafter._claude_one_shot(system="s", user="u", timeout_s=5)
                for _ in range(4)
            ))
        finally:
            asyncio.create_subprocess_exec = orig  # type: ignore
        # 4 concurrent decompose calls, gate size 2 → peak 2 (NOT 4).
        self.assertEqual(peak, 2)


if __name__ == "__main__":
    unittest.main()
