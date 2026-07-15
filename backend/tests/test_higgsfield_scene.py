"""Epic 11 P1 — higgsfield storyboard scenes: validation + splice.

NO live Higgsfield calls and NO live Google calls. Clip resolution is
stubbed with a locally synthesized mp4 (ffmpeg color source); the
splice test runs the REAL ffmpeg normalize + xfade stitch so the
mezzanine path is what's actually exercised.

Run:  cd backend && .venv/bin/python -m unittest tests.test_higgsfield_scene -v
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.routers.pmax_video import _clean_scenes
from app.services import higgsfield_scene, premium_reel
from app.services.model_catalog import clamp_duration


FFMPEG = shutil.which("ffmpeg")


def _make_stub_mp4(dest: Path, *, seconds: float = 2.0, size: str = "640x360", fps: int = 24) -> Path:
    """Tiny synthetic clip standing in for a higgsfield render —
    deliberately NOT 1920x1080/30fps so normalization is observable."""
    subprocess.run(
        [
            FFMPEG, "-y", "-f", "lavfi",
            "-i", f"color=c=blue:s={size}:r={fps}:d={seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest),
        ],
        check=True, capture_output=True,
    )
    return dest


def _probe(path: Path) -> tuple[int, int, float]:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "default=nw=1", str(path),
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    vals: dict[str, str] = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k] = v
    return int(vals["width"]), int(vals["height"]), float(vals["duration"])


_LIBRARY = [
    {"filename": "img-a.png", "display_name": "a.png", "width": 1200, "height": 628, "is_logo": False},
    {"filename": "img-b.png", "display_name": "b.png", "width": 1200, "height": 1200, "is_logo": False},
    {"filename": "logo.png", "display_name": "logo.png", "width": 512, "height": 512, "is_logo": True},
]


class CleanScenesHiggsfield(unittest.TestCase):
    def _raw(self, n_hf: int) -> list[dict]:
        scenes: list[dict] = [{"type": "hero", "headline": "Live in Panama", "speak": "Hello."}]
        for i in range(n_hf):
            scenes.append({
                "type": "higgsfield",
                "prompt": f"slow aerial over a coastline {i}",
                "model": "kling3_0",          # LLM tries to pick — must be overridden
                "duration": 30,                # out of range — must be snapped
                "speak": f"line {i}",
            })
        scenes.append({"type": "cta", "cta": "Book a call", "speak": "Book a call."})
        return scenes

    def test_disallowed_higgsfield_degrades_to_broll(self):
        cleaned = _clean_scenes(self._raw(1), _LIBRARY, allow_higgsfield=False)
        types = [s["type"] for s in cleaned]
        self.assertNotIn("higgsfield", types)
        self.assertIn("broll", types)          # degraded, not silently dropped

    def test_cap_at_two_and_model_forced(self):
        cleaned = _clean_scenes(
            self._raw(4), _LIBRARY,
            allow_higgsfield=True, video_model="veo3_1_lite", max_higgsfield=2,
        )
        hf = [s for s in cleaned if s["type"] == "higgsfield"]
        self.assertEqual(len(hf), 2)
        for s in hf:
            self.assertEqual(s["model"], "veo3_1_lite")   # never the LLM's pick
            self.assertIn(s["duration"], (4, 6, 8))        # Veo string-enum snap
            self.assertTrue(s["_speak_text"])

    def test_duration_snapping_per_model_contract(self):
        self.assertIn(clamp_duration("veo3_1_lite", 30), (4, 6, 8))
        self.assertIn(clamp_duration("veo3_1_lite", 7), (6, 8))  # nearest enum (tie)
        self.assertEqual(clamp_duration("kling3_0", 30), 15)    # int cap
        self.assertIsNone(clamp_duration("veo3", 8))            # no --duration at all


@unittest.skipIf(FFMPEG is None, "ffmpeg not on PATH")
class NormalizeClip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hfscene-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mezzanine_dimensions_and_freeze_pad(self):
        src = _make_stub_mp4(self.tmp / "raw.mp4", seconds=2.0)
        dest = self.tmp / "norm.mp4"
        asyncio.run(higgsfield_scene.normalize_clip(src, dest, min_duration=4.0))
        w, h, dur = _probe(dest)
        self.assertEqual((w, h), (1920, 1080))
        self.assertGreaterEqual(dur, 3.8)      # freeze-frame padded to ~4s
        self.assertLessEqual(dur, 4.4)

    def test_no_pad_when_clip_long_enough(self):
        src = _make_stub_mp4(self.tmp / "raw.mp4", seconds=3.0)
        dest = self.tmp / "norm.mp4"
        asyncio.run(higgsfield_scene.normalize_clip(src, dest, min_duration=1.0))
        _, _, dur = _probe(dest)
        self.assertAlmostEqual(dur, 3.0, delta=0.5)


@unittest.skipIf(FFMPEG is None, "ffmpeg not on PATH")
class SpliceIntoStoryboard(unittest.TestCase):
    """generate_storyboard_reel with [hero, higgsfield, cta]: hyperframes
    renders and higgsfield resolution are stubbed with synthetic mp4s;
    the normalize + xfade stitch run for real."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hfsplice-test-"))
        self._orig = {
            "render": premium_reel._render_with_hyperframes,
            "avail": premium_reel._hyperframes_available,
            "assets": premium_reel.ASSETS_DIR,
            "resolve": higgsfield_scene.resolve_higgsfield_clip,
        }

        async def fake_render(project_dir, *, quality="draft"):
            # 1920x1080@30 like a real hyperframes scene.
            dest = self.tmp / f"hf-{project_dir.name}.mp4"
            return _make_stub_mp4(dest, seconds=2.0, size="1920x1080", fps=30)

        async def fake_resolve(scene, *, aspect="16:9", account_id=None, campaign_id=None):
            dest = self.tmp / "clip-raw.mp4"
            if not dest.exists():
                _make_stub_mp4(dest, seconds=2.0)   # 640x360@24 — normalize must fix
            return dest, False

        premium_reel._render_with_hyperframes = fake_render
        premium_reel._hyperframes_available = lambda: True
        premium_reel.ASSETS_DIR = self.tmp
        higgsfield_scene.resolve_higgsfield_clip = fake_resolve
        # premium_reel imports resolve_higgsfield_clip lazily from the
        # module, so patching the module attribute is sufficient.

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

    def test_higgsfield_scene_spliced(self):
        events = self._run([
            {"type": "hero", "headline": "Live in Panama"},
            {"type": "higgsfield", "prompt": "aerial over coastline", "model": "veo3_1_lite", "duration": 4},
            {"type": "cta", "cta": "Book a call"},
        ])
        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done), 1, f"no done event: {events}")
        self.assertEqual(done[0]["scene_count"], 3)
        out = self.tmp / f"{done[0]['video_id']}.mp4"
        self.assertTrue(out.is_file())
        w, h, dur = _probe(out)
        self.assertEqual((w, h), (1920, 1080))
        # 3 scenes x 2s minus 2 x 0.6s crossfade ≈ 4.8s
        self.assertGreater(dur, 3.5)

    def test_ninth_higgsfield_scene_capped(self):
        # Cap is now MAX_HIGGSFIELD_SCENES = 8. Feed 1 hero + 9 clips;
        # exactly the 9th is dropped, so 1 hero + 8 clips = 9 scenes.
        # (fake_resolve reuses one shared clip-raw.mp4 for every clip, so
        # 9 stub "renders" is still cheap and fast.)
        events = self._run(
            [{"type": "hero", "headline": "H"}]
            + [{"type": "higgsfield", "prompt": f"shot {i}"} for i in range(9)]
        )
        capped = [e for e in events if e.get("stage") == "higgsfield-capped"]
        self.assertEqual(len(capped), 1)
        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(done[0]["scene_count"], 9)           # hero + 8 clips


if __name__ == "__main__":
    unittest.main()
