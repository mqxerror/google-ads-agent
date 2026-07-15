"""Video Director turn — the V0→V5 state machine driven directly.

Drives `video_director_turn` (the chat_runner run_fn) as a bare async generator,
mocking the LLM so no real `claude` CLI is hit (it's logged out). Covers:

  A  initial draft → concepts event (the 3-angle scaffold) then turn_done
  B  angle-jump storyboard → Veo enum-snap (a hallucinated 12s → 8s), ≤8 scenes,
     row persisted
  C  Kling int-cap (a 20s scene clamped to ≤15)
  ≤8 cap when the LLM returns 12 scenes
  ±1 deviation truncation + sequential renumber
  consult DEGRADE-not-block (stream_agent_response raises → drafting still finishes)

Repo test style: stdlib unittest, REAL temp SQLite from init_db(), no live calls.

Run: cd backend && .venv/bin/python -m unittest tests.test_video_director_turn -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="video-director-turn-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import prompt_drafter            # noqa: E402
from app.services import video_director as vd      # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


# ── Canned LLM output ──────────────────────────────────────────────────

_DECOMPOSE_JSON = json.dumps({
    "subject": "an investor in their 50s",
    "setting": "a Panama City skyline at dawn",
    "value_prop": "second residency by investment",
    "audience": "HNW investors",
    "tone": "aspirational",
    "program": "panama",
    "hard_constraints": ["no third-party brands"],
    "claim_hints": ["fast processing"],
})

_CONCEPTS_JSON = json.dumps({
    "variants": [
        {"angle": "problem-led", "logline": "Your capital is stuck.", "rationale": "pain"},
        {"angle": "aspirational", "logline": "A second home awaits.", "rationale": "dream"},
        {"angle": "social-proof", "logline": "Thousands already moved.", "rationale": "proof"},
    ],
})


def _storyboard_json(scenes: list[dict], title="Panama QIV") -> str:
    return json.dumps({
        "scenes": scenes,
        "vo_full": "A continuous voiceover.",
        "music_mood": "hopeful",
        "title": title,
    })


async def _make_project(**over) -> str:
    """Insert a project row + its conversation directly; return the project id."""
    pid = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())
    fields = {
        "account_id": "acct-1", "campaign_id": None,
        "title": "T", "brief": "A short brand video about Panama residency.",
        "model_id": "veo3_1", "target_seconds": 30, "aspect": "16:9",
        "consult_director": 0, "storyboard_json": None, "status": "drafting",
    }
    fields.update(over)
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (id, account_id, campaign_id, campaign_name, title) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, fields["account_id"], fields["campaign_id"], None, "conv"),
        )
        await db.execute(
            "INSERT INTO studio_video_projects "
            "(id, account_id, campaign_id, conversation_id, title, brief, model_id, "
            " target_seconds, aspect, consult_director, storyboard_json, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, fields["account_id"], fields["campaign_id"], conv_id,
             fields["title"], fields["brief"], fields["model_id"],
             fields["target_seconds"], fields["aspect"], fields["consult_director"],
             fields["storyboard_json"], fields["status"]),
        )
        await db.commit()
    finally:
        await db.close()
    return pid


async def _row(pid: str) -> dict:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM studio_video_projects WHERE id = ?", (pid,))
        r = await cur.fetchone()
        return dict(r) if r else None
    finally:
        await db.close()


async def _collect(pid: str, message: str = "") -> list[dict]:
    return [ev async for ev in vd.video_director_turn(
        turn_id="turn-" + uuid.uuid4().hex[:8], project_id=pid, message=message
    )]


def _run(coro):
    return asyncio.run(coro)


class VideoDirectorTurn(unittest.TestCase):

    def setUp(self):
        # Patch the single LLM seam + the decompose call for each test.
        self._orig_draft = vd._draft_llm
        self._orig_one_shot = prompt_drafter._claude_one_shot

    def tearDown(self):
        vd._draft_llm = self._orig_draft
        prompt_drafter._claude_one_shot = self._orig_one_shot

    # ── Test A: initial draft → concepts ──────────────────────────────
    def test_initial_draft_emits_three_concepts(self):
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose  # V2 decompose

        async def _draft(system, user, model="sonnet"):
            return _CONCEPTS_JSON  # V3 concepts
        vd._draft_llm = _draft

        pid = _run(_make_project())
        events = _run(_collect(pid))
        types = [e["type"] for e in events]
        self.assertIn("concepts", types)
        self.assertEqual(types[-1], "turn_done")
        concepts = next(e for e in events if e["type"] == "concepts")
        angles = [v["angle"] for v in concepts["payload"]["variants"]]
        self.assertEqual(angles, ["problem-led", "aspirational", "social-proof"])

    # ── Test B: angle-jump storyboard, Veo enum-snap ──────────────────
    def test_angle_jump_storyboard_veo_enum_snap(self):
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        # LLM hallucinates a 12s clip on veo3_1 (enum 4/6/8) → must snap to 8.
        scenes = [
            {"n": 1, "duration": 12, "visual_prompt": "aerial", "vo_line": "hi",
             "on_screen_text": "PANAMA", "continuity": "standalone"},
            {"n": 2, "duration": 8, "visual_prompt": "street", "vo_line": "yo",
             "on_screen_text": None, "continuity": "standalone"},
            {"n": 3, "duration": 6, "visual_prompt": "close", "vo_line": "go",
             "on_screen_text": None, "continuity": "standalone"},
        ]

        async def _draft(system, user, model="sonnet"):
            return _storyboard_json(scenes)
        vd._draft_llm = _draft

        pid = _run(_make_project(model_id="veo3_1", target_seconds=30))
        events = _run(_collect(pid, message="angle:aspirational"))
        sb = next(e for e in events if e["type"] == "storyboard")
        durations = [s["duration"] for s in sb["payload"]["scenes"]]
        self.assertTrue(all(d in (4, 6, 8) for d in durations), durations)
        self.assertEqual(durations[0], 8)  # 12 → 8 enum snap
        self.assertLessEqual(len(sb["payload"]["scenes"]), 8)
        self.assertEqual([e["type"] for e in events][-1], "turn_done")
        # Row persisted (DB = truth) + status flipped.
        row = _run(_row(pid))
        self.assertEqual(row["status"], "storyboard")
        persisted = json.loads(row["storyboard_json"])
        self.assertTrue(all(s["duration"] in (4, 6, 8) for s in persisted["scenes"]))

    # ── Test C: Kling int-cap ─────────────────────────────────────────
    def test_kling_int_cap(self):
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        scenes = [
            {"n": 1, "duration": 20, "visual_prompt": "long take", "vo_line": "a",
             "on_screen_text": None, "continuity": "evolving"},
        ]

        async def _draft(system, user, model="sonnet"):
            return _storyboard_json(scenes)
        vd._draft_llm = _draft

        pid = _run(_make_project(model_id="kling3_0", target_seconds=30))
        events = _run(_collect(pid, message="angle:aspirational"))
        sb = next(e for e in events if e["type"] == "storyboard")
        self.assertLessEqual(sb["payload"]["scenes"][0]["duration"], 15)

    # ── ≤8 cap when the LLM returns 12 scenes ─────────────────────────
    def test_scene_cap_at_eight(self):
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        scenes = [
            {"n": i, "duration": 8, "visual_prompt": f"s{i}", "vo_line": "x",
             "on_screen_text": None, "continuity": "standalone"}
            for i in range(1, 13)  # 12 scenes
        ]

        async def _draft(system, user, model="sonnet"):
            return _storyboard_json(scenes)
        vd._draft_llm = _draft

        # kling3_0 @ 30s plans to 2 clips → ±1 rule truncates to plan+1=3 which
        # is < 8; but for a raw ≤8 cap demonstration use veo3_1 @ 60s (plan=8).
        pid = _run(_make_project(model_id="veo3_1", target_seconds=60))
        events = _run(_collect(pid, message="angle:aspirational"))
        sb = next(e for e in events if e["type"] == "storyboard")
        self.assertLessEqual(len(sb["payload"]["scenes"]), 8)

    # ── ±1 deviation truncation + sequential renumber ─────────────────
    def test_plus_one_deviation_and_renumber(self):
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        # veo3_1_lite @ 30s → plan_scenes gives some N; the LLM returns 6 scenes.
        from app.services.model_catalog import plan_scenes
        plan_len = len(plan_scenes(30, "veo3_1_lite"))
        scenes = [
            {"n": 99 - i, "duration": 8, "visual_prompt": f"s{i}", "vo_line": "x",
             "on_screen_text": None, "continuity": "standalone"}
            for i in range(6)  # 6 scenes, deliberately mis-numbered
        ]

        async def _draft(system, user, model="sonnet"):
            return _storyboard_json(scenes)
        vd._draft_llm = _draft

        pid = _run(_make_project(model_id="veo3_1_lite", target_seconds=30))
        events = _run(_collect(pid, message="angle:aspirational"))
        sb = next(e for e in events if e["type"] == "storyboard")
        out = sb["payload"]["scenes"]
        # truncated to at most plan+1
        self.assertLessEqual(len(out), plan_len + 1)
        # renumbered sequentially 1..k
        self.assertEqual([s["n"] for s in out], list(range(1, len(out) + 1)))

    # ── Consult DEGRADE-not-block ─────────────────────────────────────
    def test_consult_degrades_not_blocks(self):
        # Campaign-linked project with consult ON; stream_agent_response raises.
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        async def _draft(system, user, model="sonnet"):
            return _CONCEPTS_JSON
        vd._draft_llm = _draft

        import app.services.agent as agent_mod

        async def _boom(*args, **kwargs):
            raise RuntimeError("director is down")
            yield  # pragma: no cover — makes this an async generator

        orig = agent_mod.stream_agent_response
        agent_mod.stream_agent_response = _boom
        try:
            pid = _run(_make_project(
                account_id="acct-1", campaign_id="camp-1", consult_director=1,
            ))
            events = _run(_collect(pid))
        finally:
            agent_mod.stream_agent_response = orig

        types = [e["type"] for e in events]
        # Drafting still completes: concepts emitted, turn terminates naturally.
        self.assertIn("concepts", types)
        self.assertIn("turn_done", types)
        self.assertNotIn("turn_error", types)
        # A degrade thought was surfaced (not a crash).
        thoughts = [e for e in events if e["type"] == "director_thought"]
        self.assertTrue(any("unavailable" in t["payload"]["text"] for t in thoughts))


class DraftStageTimeout(unittest.TestCase):
    """CHANGE 1 — the draft-timeout bug fix: threaded timeout_s, the 150s
    video-draft budget, and the graceful structured retryable turn_error."""

    def setUp(self):
        self._orig_draft = vd._draft_llm
        self._orig_one_shot = prompt_drafter._claude_one_shot
        self._orig_stage1 = prompt_drafter._stage1_decompose
        self._orig_exec = asyncio.create_subprocess_exec

    def tearDown(self):
        vd._draft_llm = self._orig_draft
        prompt_drafter._claude_one_shot = self._orig_one_shot
        prompt_drafter._stage1_decompose = self._orig_stage1
        asyncio.create_subprocess_exec = self._orig_exec

    # ── Test 1: _claude_one_shot honors a custom timeout_s ─────────────
    def test_claude_one_shot_threads_timeout_s(self):
        """A custom timeout_s reaches asyncio.wait_for AND (on timeout) the
        error message reports that exact value — not the hardcoded constant."""
        captured: dict = {}

        class _FakeProc:
            returncode = 0
            async def communicate(self, input=None):
                # never actually awaited — patched wait_for closes this coro —
                # but it must exist so `proc.communicate(...)` builds a coroutine.
                return (b"", b"")  # pragma: no cover
            def kill(self):  # pragma: no cover — timeout path calls this
                pass
            async def wait(self):  # pragma: no cover
                return 0

        async def _fake_exec(*args, **kwargs):
            return _FakeProc()
        asyncio.create_subprocess_exec = _fake_exec

        # (a) custom timeout_s flows to wait_for + returns cleanly.
        orig_wait_for = asyncio.wait_for

        async def _capture_wait_for(coro, timeout=None):
            captured["timeout"] = timeout
            # drain the passed coroutine so it isn't left un-awaited
            if asyncio.iscoroutine(coro):
                coro.close()
            return (b'{"ok": true}', b"")

        asyncio.wait_for = _capture_wait_for
        try:
            out = _run(prompt_drafter._claude_one_shot(
                system="s", user="u", timeout_s=150.0,
            ))
        finally:
            asyncio.wait_for = orig_wait_for
        self.assertEqual(captured["timeout"], 150.0)
        self.assertIn("ok", out)

        # default (image path) stays at the tight 45s budget.
        async def _capture_wait_for2(coro, timeout=None):
            captured["timeout"] = timeout
            if asyncio.iscoroutine(coro):
                coro.close()
            return (b"{}", b"")
        asyncio.wait_for = _capture_wait_for2
        try:
            _run(prompt_drafter._claude_one_shot(system="s", user="u"))
        finally:
            asyncio.wait_for = orig_wait_for
        self.assertEqual(captured["timeout"], prompt_drafter._STAGE_TIMEOUT_S)

        # (b) on timeout, the error string reports the ACTUAL timeout_s.
        async def _timeout_wait_for(coro, timeout=None):
            if asyncio.iscoroutine(coro):
                coro.close()
            raise asyncio.TimeoutError()
        asyncio.wait_for = _timeout_wait_for
        try:
            with self.assertRaises(prompt_drafter.PromptDrafterError) as ctx:
                _run(prompt_drafter._claude_one_shot(
                    system="s", user="u", timeout_s=150.0,
                ))
        finally:
            asyncio.wait_for = orig_wait_for
        self.assertIn("150.0", str(ctx.exception))

    # ── Test 2: video draft path uses the 150s budget ─────────────────
    def test_video_director_uses_150s_draft_budget(self):
        """The constant is 150s AND every video draft call (V2 decompose via
        _stage1_decompose, V3/V4 via _draft_llm) passes timeout_s=150.0 to
        _claude_one_shot, while the image path keeps the 45s default."""
        self.assertEqual(vd._DRAFT_STAGE_TIMEOUT_S, 150.0)

        seen: list[float | None] = []

        async def _spy_one_shot(*, system, user, model="sonnet",
                                timeout_s=prompt_drafter._STAGE_TIMEOUT_S):
            seen.append(timeout_s)
            # V2 decompose expects JSON; V3/V4 also parse JSON — return a brief
            # for decompose and concepts for the draft_llm calls. A concepts
            # blob parses fine for both (_stage1_decompose fills defaults).
            return _DECOMPOSE_JSON
        # patch at the source so BOTH _draft_llm and _stage1_decompose hit it.
        prompt_drafter._claude_one_shot = _spy_one_shot

        async def _draft(system, user, model="sonnet"):
            # route the real _draft_llm through the spied _claude_one_shot so we
            # observe the timeout it passes.
            return await self._orig_draft(system, user, model)
        vd._draft_llm = _draft

        pid = _run(_make_project())
        _run(_collect(pid))  # initial draft: V2 decompose + V3 concepts
        # every observed video-draft call used the 150s budget, none the 45s one.
        self.assertTrue(seen, "no draft calls were observed")
        self.assertTrue(all(t == 150.0 for t in seen), seen)

    # ── Test 3: draft timeout → structured retryable turn_error ───────
    def test_draft_timeout_emits_retryable_turn_error(self):
        """A PromptDrafterError during a draft stage yields the structured,
        retryable turn_error with the EXACT human message — and does NOT crash."""
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        async def _boom(system, user, model="sonnet"):
            raise prompt_drafter.PromptDrafterError("claude timed out after 150.0s")
        vd._draft_llm = _boom  # V3 concepts call raises

        pid = _run(_make_project())
        events = _run(_collect(pid))  # initial draft → V3 concepts times out
        types = [e["type"] for e in events]
        self.assertIn("turn_error", types)
        self.assertNotIn("concepts", types)
        err = next(e for e in events if e["type"] == "turn_error")
        self.assertTrue(err["payload"]["retryable"])
        self.assertEqual(err["payload"]["stage"], "draft-timeout")
        self.assertEqual(
            err["payload"]["message"],
            "The Director took too long drafting — this can happen with heavy "
            "campaign context. Retry.",
        )

    # V4 storyboard timeout also degrades gracefully (angle-jump path).
    def test_storyboard_timeout_emits_retryable_turn_error(self):
        async def _decompose(*, system, user, model="sonnet", timeout_s=None):
            return _DECOMPOSE_JSON
        prompt_drafter._claude_one_shot = _decompose

        async def _boom(system, user, model="sonnet"):
            raise prompt_drafter.PromptDrafterError("claude timed out after 150.0s")
        vd._draft_llm = _boom

        pid = _run(_make_project(model_id="veo3_1", target_seconds=30))
        events = _run(_collect(pid, message="angle:aspirational"))
        types = [e["type"] for e in events]
        self.assertIn("turn_error", types)
        self.assertNotIn("storyboard", types)
        err = next(e for e in events if e["type"] == "turn_error")
        self.assertTrue(err["payload"]["retryable"])


if __name__ == "__main__":
    unittest.main()
