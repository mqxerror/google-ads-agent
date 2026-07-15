"""Epic 11 P2 — video engine: segment compile, caps, soul presenter.

NO live Higgsfield calls and NO live Google calls. The CLI client,
downloads, and DB reads/writes are all stubbed; the timeline splice
test runs the REAL ffmpeg normalize + xfade stitch so the mezzanine
path is what's actually exercised (same policy as
tests/test_higgsfield_scene.py).

Run:  cd backend && .venv/bin/python -m unittest tests.test_video_engine -v
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.routers.pmax_video import _clean_scenes
from app.services import higgsfield_scene, premium_reel, video_engine

from tests.test_higgsfield_scene import _LIBRARY, _make_stub_mp4, _probe

FFMPEG = shutil.which("ffmpeg")


# ── Timeline compile + caps ──────────────────────────────────────────


class SegmentCompile(unittest.TestCase):
    def test_orders_and_maps_segments(self):
        segments = [
            {"engine": "soul", "soul_id": "HF-1", "script": "Welcome to Panama."},
            {"engine": "storyboard", "scenes": [
                {"type": "hero", "headline": "Live in Panama"},
                {"type": "broll", "image_filename": "img-a.png", "caption": "Skyline"},
            ]},
            {"engine": "higgsfield", "prompt": "aerial over a coastline", "model": "veo3_1_lite",
             "duration": 6, "speak": "The coast."},
            {"engine": "storyboard", "scenes": [{"type": "cta", "cta": "Book a call"}]},
        ]
        scenes, warnings = video_engine.segments_to_scenes(segments)
        self.assertEqual(warnings, [])
        self.assertEqual(
            [s["type"] for s in scenes],
            ["soul", "hero", "broll", "higgsfield", "cta"],
        )
        self.assertEqual(scenes[0]["_speak_text"], "Welcome to Panama.")
        self.assertEqual(scenes[3]["_speak_text"], "The coast.")
        self.assertEqual(scenes[3]["model"], "veo3_1_lite")

    def test_unknown_engine_and_empty_segments_warn(self):
        scenes, warnings = video_engine.segments_to_scenes([
            {"engine": "hologram", "prompt": "x"},
            {"engine": "soul", "soul_id": "HF-1"},          # no script
            {"engine": "higgsfield"},                        # no prompt
            {"engine": "storyboard", "scenes": []},          # empty
        ])
        self.assertEqual(scenes, [])
        self.assertEqual(len(warnings), 4)

    def test_caps_trim_extra_soul_and_higgsfield(self):
        # Soul cap = 1, higgsfield cap = 8. Feed 2 souls (1 over) and 9
        # higgsfield (1 over); first-N win, so soul[0] + 8 clips + cta
        # survive and exactly 2 warnings fire.
        scenes = (
            [
                {"type": "soul", "soul_id": "HF-1", "script": "a"},
                {"type": "soul", "soul_id": "HF-2", "script": "b"},   # over soul cap
            ]
            + [{"type": "higgsfield", "prompt": f"clip {i}"} for i in range(9)]  # 1 over hf cap
            + [{"type": "cta", "cta": "Go"}]
        )
        capped, warnings = video_engine.enforce_caps(scenes)
        self.assertEqual(
            [s["type"] for s in capped],
            ["soul"] + ["higgsfield"] * 8 + ["cta"],
        )
        self.assertEqual(capped[0]["soul_id"], "HF-1")   # first soul wins
        self.assertEqual(len(warnings), 2)


class AttachSoulIds(unittest.TestCase):
    def _fetch(self, rows):
        async def fetch(row_id):
            return rows.get(row_id)
        return fetch

    def _run(self, scenes, rows):
        return asyncio.run(
            video_engine.attach_soul_ids(scenes, fetch=self._fetch(rows))
        )

    def test_ready_row_attaches_soul_id(self):
        scenes = [{"type": "soul", "soul_character_id": "abc", "script": "hi", "_speak_text": "hi"}]
        out, warnings = self._run(scenes, {"abc": {"status": "ready", "soul_id": "HF-9"}})
        self.assertEqual(out[0]["soul_id"], "HF-9")
        self.assertEqual(warnings, [])

    def test_training_or_unknown_row_drops_scene(self):
        scenes = [
            {"type": "soul", "soul_character_id": "tr", "script": "hi"},
            {"type": "soul", "soul_character_id": "nope", "script": "hi"},
            {"type": "hero", "headline": "H"},
        ]
        out, warnings = self._run(scenes, {"tr": {"status": "training", "soul_id": None}})
        self.assertEqual([s["type"] for s in out], ["hero"])
        self.assertEqual(len(warnings), 2)

    def test_direct_soul_id_passes_without_fetch(self):
        scenes = [{"type": "soul", "soul_id": "HF-1", "script": "hi"}]
        out, warnings = self._run(scenes, {})   # fetch would return None
        self.assertEqual(out[0]["soul_id"], "HF-1")
        self.assertEqual(warnings, [])


class CleanScenesSoul(unittest.TestCase):
    def _raw(self, n_soul: int = 1) -> list[dict]:
        scenes: list[dict] = []
        for i in range(n_soul):
            scenes.append({
                "type": "soul",
                "script": f"Welcome number {i}.",
                "soul_id": "LLM-SNEAKED-ID",   # must be overridden server-side
                "look_prompt": "bright office",
                "speak": f"Welcome number {i}.",
            })
        scenes.append({"type": "hero", "headline": "Live in Panama", "speak": "Hello."})
        scenes.append({"type": "cta", "cta": "Book a call", "speak": "Book a call."})
        return scenes

    def test_soul_kept_first_with_server_forced_id(self):
        cleaned = _clean_scenes(self._raw(1), _LIBRARY, soul_id="HF-REAL")
        self.assertEqual(cleaned[0]["type"], "soul")
        self.assertEqual(cleaned[0]["soul_id"], "HF-REAL")      # never the LLM's id
        self.assertEqual(cleaned[0]["_speak_text"], "Welcome number 0.")
        self.assertEqual(cleaned[0]["look_prompt"], "bright office")
        self.assertEqual(cleaned[-1]["type"], "cta")

    def test_soul_stripped_without_ready_character(self):
        cleaned = _clean_scenes(self._raw(1), _LIBRARY, soul_id=None)
        self.assertNotIn("soul", [s["type"] for s in cleaned])

    def test_second_soul_scene_stripped(self):
        cleaned = _clean_scenes(self._raw(2), _LIBRARY, soul_id="HF-REAL")
        souls = [s for s in cleaned if s["type"] == "soul"]
        self.assertEqual(len(souls), 1)
        self.assertEqual(souls[0]["script"], "Welcome number 0.")


# ── Soul clip resolution (stubbed CLI + downloads + DB) ──────────────


class _FakeClient:
    """Stands in for HiggsfieldClient — records calls, returns canned
    CDN URLs. No subprocess, no network."""

    calls: list[tuple[str, dict]] = []

    def __init__(self, **kwargs):
        pass

    async def submit_image(self, *, model, prompt, **params):
        _FakeClient.calls.append(("image", {"model": model, "prompt": prompt, **params}))
        return {"image_url": "http://cdn.test/still.png", "raw": [{"id": "job-still"}]}

    async def submit_video(self, *, model, prompt, **params):
        _FakeClient.calls.append(("video", {"model": model, "prompt": prompt, **params}))
        return {"image_url": "http://cdn.test/clip.mp4", "raw": [{"id": "job-clip"}]}


@unittest.skipIf(FFMPEG is None, "ffmpeg not on PATH")
class ResolveSoulClip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="soulclip-test-"))
        _FakeClient.calls = []
        self.recorded: list[dict] = []
        self._orig = {
            "client": video_engine.HiggsfieldClient,
            "download": video_engine._download_file,
            "record": video_engine._record_soul_asset,
            "cache": higgsfield_scene._find_cached_clip,
        }

        async def fake_download(url, suffix):
            dest = self.tmp / f"dl-{len(_FakeClient.calls)}{suffix}"
            if suffix == ".mp4":
                _make_stub_mp4(dest, seconds=2.0)
            else:
                dest.write_bytes(b"\x89PNG fake still")
            return dest

        async def fake_record(**kwargs):
            self.recorded.append(kwargs)

        async def cache_miss(prompt_hash):
            return None

        video_engine.HiggsfieldClient = _FakeClient
        video_engine._download_file = fake_download
        video_engine._record_soul_asset = fake_record
        higgsfield_scene._find_cached_clip = cache_miss

    def tearDown(self):
        video_engine.HiggsfieldClient = self._orig["client"]
        video_engine._download_file = self._orig["download"]
        video_engine._record_soul_asset = self._orig["record"]
        higgsfield_scene._find_cached_clip = self._orig["cache"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_stage_generation_and_recording(self):
        scene = {"type": "soul", "soul_id": "HF-1", "script": "Hi", "look_prompt": "navy suit"}
        path, was_cached = asyncio.run(
            video_engine.resolve_soul_clip(scene, aspect="16:9")
        )
        self.assertFalse(was_cached)
        self.assertTrue(path.is_file())
        # Stage 1: soul still with the trained face.
        kind, params = _FakeClient.calls[0]
        self.assertEqual(kind, "image")
        self.assertEqual(params["model"], video_engine.SOUL_STILL_MODEL)
        self.assertEqual(params["soul_id"], "HF-1")
        self.assertEqual(params["prompt"], "navy suit")
        # Stage 2: motion pass fed the downloaded still.
        kind, params = _FakeClient.calls[1]
        self.assertEqual(kind, "video")
        self.assertEqual(params["model"], video_engine.SOUL_MOTION_MODEL)
        self.assertTrue(params[video_engine.SOUL_MOTION_IMAGE_PARAM].endswith(".png"))
        # Recorded with the cache hash so the next render is free.
        self.assertEqual(len(self.recorded), 1)
        self.assertEqual(
            self.recorded[0]["prompt_hash"],
            video_engine.soul_prompt_hash(soul_id="HF-1", look_prompt="navy suit", aspect="16:9"),
        )

    def test_cache_hit_burns_no_credits(self):
        cached_path = self.tmp / "cached.mp4"
        _make_stub_mp4(cached_path, seconds=1.0)

        async def cache_hit(prompt_hash):
            return cached_path

        higgsfield_scene._find_cached_clip = cache_hit
        scene = {"type": "soul", "soul_id": "HF-1", "script": "Hi"}
        path, was_cached = asyncio.run(video_engine.resolve_soul_clip(scene))
        self.assertTrue(was_cached)
        self.assertEqual(path, cached_path)
        self.assertEqual(_FakeClient.calls, [])   # zero generations

    def test_missing_soul_id_raises(self):
        with self.assertRaises(ValueError):
            asyncio.run(video_engine.resolve_soul_clip({"type": "soul", "script": "Hi"}))


# ── Full timeline through the REAL normalize + xfade stitch ──────────


@unittest.skipIf(FFMPEG is None, "ffmpeg not on PATH")
class EngineTimelineSplice(unittest.TestCase):
    """generate_engine_video with [soul intro, hero body, cta outro]:
    hyperframes renders and soul-clip resolution are stubbed with
    synthetic mp4s; the mezzanine normalize + xfade stitch run for
    real."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="enginesplice-test-"))
        self._orig = {
            "render": premium_reel._render_with_hyperframes,
            "avail": premium_reel._hyperframes_available,
            "assets": premium_reel.ASSETS_DIR,
            "resolve": video_engine.resolve_soul_clip,
        }

        async def fake_render(project_dir, *, quality="draft"):
            # 1920x1080@30 like a real hyperframes scene.
            dest = self.tmp / f"hf-{project_dir.name}.mp4"
            return _make_stub_mp4(dest, seconds=2.0, size="1920x1080", fps=30)

        async def fake_resolve(scene, *, aspect="16:9", account_id=None, campaign_id=None):
            dest = self.tmp / "soul-raw.mp4"
            if not dest.exists():
                _make_stub_mp4(dest, seconds=2.0)   # 640x360@24 — normalize must fix
            return dest, False

        premium_reel._render_with_hyperframes = fake_render
        premium_reel._hyperframes_available = lambda: True
        premium_reel.ASSETS_DIR = self.tmp
        # premium_reel imports resolve_soul_clip lazily from the module,
        # so patching the module attribute is sufficient.
        video_engine.resolve_soul_clip = fake_resolve

    def tearDown(self):
        premium_reel._render_with_hyperframes = self._orig["render"]
        premium_reel._hyperframes_available = self._orig["avail"]
        premium_reel.ASSETS_DIR = self._orig["assets"]
        video_engine.resolve_soul_clip = self._orig["resolve"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, segments):
        async def collect():
            events = []
            req = video_engine.VideoEngineRequest(
                account_id=None, segments=segments,
                sync_audio_to_scenes=False, quality="draft",
            )
            async for ev in video_engine.generate_engine_video(req):
                events.append(ev)
            return events
        return asyncio.run(collect())

    def test_soul_intro_body_outro_spliced(self):
        events = self._run([
            {"engine": "soul", "soul_id": "HF-1", "script": "Welcome."},
            {"engine": "storyboard", "scenes": [{"type": "hero", "headline": "Live in Panama"}]},
            {"engine": "storyboard", "scenes": [{"type": "cta", "cta": "Book a call"}]},
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

    def test_second_soul_segment_capped_before_render(self):
        events = self._run([
            {"engine": "soul", "soul_id": "HF-1", "script": "One."},
            {"engine": "soul", "soul_id": "HF-2", "script": "Two."},   # over cap
            {"engine": "storyboard", "scenes": [{"type": "cta", "cta": "Go"}]},
        ])
        cap_warnings = [
            e for e in events
            if e.get("stage") == "timeline" and "Soul presenter" in e.get("message", "")
            and "Dropped" in e.get("message", "")
        ]
        self.assertEqual(len(cap_warnings), 1)
        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(done[0]["scene_count"], 2)               # soul + cta

    def test_empty_timeline_errors(self):
        events = self._run([{"engine": "storyboard", "scenes": []}])
        self.assertEqual(events[-1]["type"], "error")


# ── Finished-video planner injection (stubbed reel — no ffmpeg) ───────


class GenerateEngineVideoPlanner(unittest.TestCase):
    """The dispatcher's finished-video branch: target_seconds+model_id+
    prompt with NO segments auto-plans N higgsfield scenes and hands them
    to premium_reel. generate_engine_video imports generate_storyboard_reel
    from the premium_reel MODULE at call time, so patching the module
    attribute captures the StoryboardReelRequest it builds. No ffmpeg,
    no CLI, no DB — enforce_caps runs (fine, ≤8) and attach_soul_ids
    passes higgsfield scenes through untouched (no soul → no DB I/O)."""

    def setUp(self):
        self._orig_reel = premium_reel.generate_storyboard_reel
        self.captured: dict = {}

        async def fake_reel(req):
            self.captured["req"] = req
            yield {
                "type": "done", "stage": "done", "message": "ok",
                "video_id": "vid", "public_url": "/api/video/assets/vid.mp4",
                "duration": 60.0, "size_bytes": 1, "scene_count": len(req.scenes),
            }

        premium_reel.generate_storyboard_reel = fake_reel

    def tearDown(self):
        premium_reel.generate_storyboard_reel = self._orig_reel

    def _run(self, **kwargs):
        async def collect():
            req = video_engine.VideoEngineRequest(**kwargs)
            return [ev async for ev in video_engine.generate_engine_video(req)]
        return asyncio.run(collect())

    def test_planner_builds_four_higgsfield_scenes_for_60s_kling(self):
        events = self._run(
            account_id=None, segments=[],
            target_seconds=60, model_id="kling3_0", prompt="aerial over a coastline",
        )
        done = [e for e in events if e["type"] == "done"]
        self.assertEqual(len(done), 1, f"no done event: {events}")
        scenes = self.captured["req"].scenes
        self.assertEqual(len(scenes), 4)
        self.assertTrue(all(s["type"] == "higgsfield" for s in scenes))
        self.assertTrue(all(s["duration"] == 15 for s in scenes))
        self.assertTrue(all(s["prompt"] == "aerial over a coastline" for s in scenes))
        self.assertTrue(all(s["model"] == "kling3_0" for s in scenes))

    def test_planner_skipped_when_segments_present(self):
        # Real segments AND the trio set → segments win, planner never runs.
        events = self._run(
            account_id=None,
            segments=[{"engine": "storyboard", "scenes": [
                {"type": "hero", "headline": "Live in Panama"},
            ]}],
            target_seconds=60, model_id="kling3_0", prompt="should be ignored",
        )
        self.assertTrue([e for e in events if e["type"] == "done"])
        scenes = self.captured["req"].scenes
        self.assertEqual([s["type"] for s in scenes], ["hero"])   # not a planned hf list

    def test_unknown_model_falls_through_to_no_scenes_error(self):
        # plan_scenes("nope") → [] → segments stays [] → error path fires.
        events = self._run(
            account_id=None, segments=[],
            target_seconds=60, model_id="nope", prompt="x",
        )
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn("req", self.captured)   # reel never invoked

    def test_planner_voiceover_uses_whole_script_bed(self):
        # Finished-video VO: one script for the whole timeline. Planner
        # clips carry speak="" so per-scene sync would be silent → the
        # dispatcher must switch OFF per-scene sync and pass the script
        # straight through as the spanning VO bed.
        events = self._run(
            account_id=None, segments=[],
            target_seconds=30, model_id="kling3_0", prompt="skyline",
            voiceover_script="Move to Panama and secure your future.",
        )
        self.assertTrue([e for e in events if e["type"] == "done"])
        reel = self.captured["req"]
        self.assertEqual(reel.voiceover_script, "Move to Panama and secure your future.")
        self.assertFalse(reel.sync_audio_to_scenes)   # spanning bed, not per-scene

    def test_planner_without_voiceover_keeps_per_scene_sync(self):
        # No VO script → the whole-script bed is empty and per-scene sync
        # stays ON (default behavior, unchanged).
        self._run(
            account_id=None, segments=[],
            target_seconds=30, model_id="kling3_0", prompt="skyline",
        )
        reel = self.captured["req"]
        self.assertEqual(reel.voiceover_script, "")
        self.assertTrue(reel.sync_audio_to_scenes)


# ── Raised cap (2 → 8) via enforce_caps ──────────────────────────────


class EnforceCapsRaised(unittest.TestCase):
    def test_keeps_up_to_eight_higgsfield_scenes(self):
        scenes = [{"type": "higgsfield", "prompt": f"shot {i}"} for i in range(9)]
        capped, warnings = video_engine.enforce_caps(scenes)
        hf = [s for s in capped if s["type"] == "higgsfield"]
        self.assertEqual(len(hf), 8)          # cap now 8, 9th dropped
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
