"""Honest render failures (CHANGE-2) — per-scene error classification.

Patches `resolve_higgsfield_clip` to raise a classified HiggsfieldError and
drives `generate_storyboard_reel`. Asserts:

  - the per-scene `scene-skipped` status event carries `error_class`
  - when EVERY scene fails, the terminal event is a STRUCTURED
    {type:"error", scene_failures:[...]} (NOT an opaque RuntimeError), and an
    auth-class failure makes the top-level message clearly indicate auth
  - a partial reel (one clip fails, hyperframes scenes succeed) still finishes
    with a `done` event while surfacing the classified skip

Hyperframes render is stubbed with a synthetic 1920x1080 mp4 (same approach as
test_higgsfield_scene.py); NO live Higgsfield calls (the CLI is logged out).

Run: cd backend && .venv/bin/python -m unittest tests.test_render_error_classification -v
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.services import higgsfield_scene, premium_reel
from app.services.higgsfield_client import HiggsfieldError


FFMPEG = shutil.which("ffmpeg")


def _make_stub_mp4(dest: Path, *, seconds: float = 2.0, size: str = "1920x1080", fps: int = 30) -> Path:
    subprocess.run(
        [
            FFMPEG, "-y", "-f", "lavfi",
            "-i", f"color=c=blue:s={size}:r={fps}:d={seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest),
        ],
        check=True, capture_output=True,
    )
    return dest


@unittest.skipIf(FFMPEG is None, "ffmpeg not on PATH")
class RenderErrorClassification(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="render-errclass-test-"))
        self._orig = {
            "render": premium_reel._render_with_hyperframes,
            "avail": premium_reel._hyperframes_available,
            "assets": premium_reel.ASSETS_DIR,
            "resolve": higgsfield_scene.resolve_higgsfield_clip,
        }

        async def fake_render(project_dir, *, quality="draft"):
            dest = self.tmp / f"hf-{project_dir.name}.mp4"
            return _make_stub_mp4(dest, seconds=2.0)

        premium_reel._render_with_hyperframes = fake_render
        premium_reel._hyperframes_available = lambda: True
        premium_reel.ASSETS_DIR = self.tmp

    def tearDown(self):
        premium_reel._render_with_hyperframes = self._orig["render"]
        premium_reel._hyperframes_available = self._orig["avail"]
        premium_reel.ASSETS_DIR = self._orig["assets"]
        higgsfield_scene.resolve_higgsfield_clip = self._orig["resolve"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, scenes):
        async def collect():
            events = []
            req = premium_reel.StoryboardReelRequest(
                scenes=scenes, sync_audio_to_scenes=False, quality="draft",
            )
            async for ev in premium_reel.generate_storyboard_reel(req):
                events.append(ev)
            return events
        return asyncio.run(collect())

    # ── auth-class clip failure surfaces error_class on the skip ───────
    def test_scene_skip_carries_error_class(self):
        async def fake_resolve(scene, *, aspect="16:9", account_id=None, campaign_id=None):
            raise HiggsfieldError(message="not logged in", code="auth")
        higgsfield_scene.resolve_higgsfield_clip = fake_resolve

        # 1 hero (renders) + 1 higgsfield clip (fails auth) → partial reel.
        events = self._run([
            {"type": "hero", "headline": "Live in Panama"},
            {"type": "higgsfield", "prompt": "aerial", "model": "veo3_1_lite", "duration": 4},
        ])
        skips = [e for e in events if e.get("stage") == "scene-skipped"]
        self.assertEqual(len(skips), 1, f"expected one skip: {events}")
        self.assertEqual(skips[0].get("error_class"), "auth")
        # Partial reel is still a win — the hero rendered.
        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done), 1, f"no done event: {events}")
        self.assertEqual(done[0]["scene_count"], 1)

    # ── all scenes fail → structured error event with scene_failures ───
    def test_all_fail_emits_structured_error_with_failures(self):
        async def fake_resolve(scene, *, aspect="16:9", account_id=None, campaign_id=None):
            raise HiggsfieldError(message="not logged in", code="auth")
        higgsfield_scene.resolve_higgsfield_clip = fake_resolve

        # Only higgsfield scenes → every scene fails auth.
        events = self._run([
            {"type": "higgsfield", "prompt": "shot 1", "model": "veo3_1_lite", "duration": 4},
            {"type": "higgsfield", "prompt": "shot 2", "model": "veo3_1_lite", "duration": 4},
        ])
        # No opaque RuntimeError bubbled up — a structured error event instead.
        errors = [e for e in events if e["type"] == "error" and e.get("stage") == "error"]
        self.assertEqual(len(errors), 1, f"expected one structured error: {events}")
        err = errors[0]
        self.assertIn("scene_failures", err)
        self.assertEqual(len(err["scene_failures"]), 2)
        self.assertTrue(all(f["error_class"] == "auth" for f in err["scene_failures"]))
        # Each failure carries a scene_index + message.
        for f in err["scene_failures"]:
            self.assertIn("scene_index", f)
            self.assertIn("message", f)
        # auth-class → the top-level message clearly indicates auth (login banner).
        self.assertIn("logged in", err["message"].lower())
        # No done event when everything failed.
        self.assertEqual([e for e in events if e["type"] == "done"], [])

    # ── a non-higgsfield error is classified "other" ───────────────────
    def test_non_higgsfield_error_classified_other(self):
        async def fake_resolve(scene, *, aspect="16:9", account_id=None, campaign_id=None):
            raise ValueError("some unexpected boom")
        higgsfield_scene.resolve_higgsfield_clip = fake_resolve

        events = self._run([
            {"type": "higgsfield", "prompt": "x", "model": "veo3_1_lite", "duration": 4},
        ])
        errors = [e for e in events if e["type"] == "error" and e.get("stage") == "error"]
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["scene_failures"][0]["error_class"], "other")
        # non-auth → generic message, no false login nudge.
        self.assertNotIn("logged in", errors[0]["message"].lower())


if __name__ == "__main__":
    unittest.main()
