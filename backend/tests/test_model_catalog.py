"""Finished-video scene planner — plan_scenes clip-math.

NO live calls: plan_scenes is pure catalog arithmetic (no CLI, no
network, no DB). Just asserts clip COUNT and per-clip DURATION for
every model contract in the acceptance table.

Run:  cd backend && .venv/bin/python -m unittest tests.test_model_catalog -v
"""

from __future__ import annotations

import unittest

from app.services.model_catalog import plan_scenes


class PlanScenes(unittest.TestCase):
    def _assert_plan(self, target: int, model: str, count: int, dur):
        plan = plan_scenes(target, model)
        self.assertEqual(len(plan), count, f"{model}@{target}s → {plan}")
        self.assertTrue(
            all(s["duration"] == dur for s in plan),
            f"{model}@{target}s expected all dur={dur}, got {plan}",
        )

    def test_kling3_0_int_cap_15(self):
        # int, max 15
        self._assert_plan(15, "kling3_0", 1, 15)
        self._assert_plan(30, "kling3_0", 2, 15)
        self._assert_plan(60, "kling3_0", 4, 15)

    def test_veo3_1_enum_max_8(self):
        # enum 4/6/8, max 8. 15→ceil(15/8)=2 clips of 8s=16s (over-shoot,
        # expected — can't hit 15 exactly with 8s clips).
        self._assert_plan(15, "veo3_1", 2, 8)
        self._assert_plan(30, "veo3_1", 4, 8)
        self._assert_plan(60, "veo3_1", 8, 8)

    def test_minimax_hailuo_int_cap_10(self):
        # int, max 10
        self._assert_plan(15, "minimax_hailuo", 2, 10)
        self._assert_plan(30, "minimax_hailuo", 3, 10)
        self._assert_plan(60, "minimax_hailuo", 6, 10)

    def test_wan2_6_enum_max_15(self):
        # enum 5/10/15, max 15
        self._assert_plan(15, "wan2_6", 1, 15)
        self._assert_plan(30, "wan2_6", 2, 15)
        self._assert_plan(60, "wan2_6", 4, 15)

    def test_veo3_no_duration_control_single_native_clip(self):
        # duration_type None → exactly ONE clip at native length.
        for target in (15, 30, 60):
            plan = plan_scenes(target, "veo3")
            self.assertEqual(plan, [{"duration": None}], f"veo3@{target}s → {plan}")

    def test_unknown_model_empty_plan(self):
        self.assertEqual(plan_scenes(30, "nope"), [])

    def test_non_video_model_empty_plan(self):
        # An image model is not video → empty plan (caller falls back).
        self.assertEqual(plan_scenes(30, "gpt_image_2"), [])

    def test_cap_ceiling_never_exceeds_max_scenes(self):
        # minimax_hailuo max 10 at 90s → ceil(90/10)=9 → capped to 8.
        plan = plan_scenes(90, "minimax_hailuo")
        self.assertEqual(len(plan), 8)
        self.assertTrue(all(s["duration"] == 10 for s in plan))


if __name__ == "__main__":
    unittest.main()
