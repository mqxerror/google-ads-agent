"""Draft brief sources (CHANGE-1) — brief_source threading + router 400s.

Drives `video_director_turn` directly (chat_runner run_fn style) with the LLM
mocked, and patches `prompt_drafter._stage1_decompose` to CAPTURE its `page`
arg so we can assert the synthesized campaign block / landing-page claims reach
the decomposer. Also drives the draft router endpoint directly (repo style: no
TestClient) to assert the 400s for structurally-impossible requests.

Covers:
  - type="text" (default): back-compat — no source block, plain brief reaches decompose
  - type="campaign": campaign memory (profile/pinned/decisions) synthesized into page
  - type="landing_page": fetched page's title/h1/body reach decompose
  - landing_page fetch FAILURE: a page-unverified verification event is yielded
    AND the turn still completes (degrade, never block)
  - router 400: campaign source on a project with no campaign_id
  - router 400: landing_page source with no url

Repo test style: stdlib unittest, REAL temp SQLite from init_db(), no live calls.

Run: cd backend && .venv/bin/python -m unittest tests.test_brief_source -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi import HTTPException

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="brief-source-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db          # noqa: E402
from app.services import prompt_drafter            # noqa: E402
from app.services import video_director as vd      # noqa: E402
from app.services import page_fetcher              # noqa: E402
from app.routers import video_director as vdr      # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


_DECOMPOSE = {
    "subject": "an investor", "setting": "a skyline", "value_prop": "residency",
    "audience": "HNW", "tone": "aspirational", "program": "panama",
    "hard_constraints": [], "claim_hints": [],
}
_CONCEPTS_JSON = json.dumps({"variants": [
    {"angle": "problem-led", "logline": "x", "rationale": "x"},
    {"angle": "aspirational", "logline": "x", "rationale": "x"},
    {"angle": "social-proof", "logline": "x", "rationale": "x"},
]})


async def _make_project(**over) -> str:
    pid = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())
    fields = {
        "account_id": "acct-1", "campaign_id": None,
        "title": "T", "brief": "", "model_id": "veo3_1",
        "target_seconds": 30, "aspect": "16:9", "consult_director": 0,
        "storyboard_json": None, "status": "drafting",
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


async def _collect(pid: str, message: str = "", brief_source=None) -> list[dict]:
    return [ev async for ev in vd.video_director_turn(
        turn_id="turn-" + uuid.uuid4().hex[:8], project_id=pid,
        message=message, brief_source=brief_source,
    )]


class BriefSourceThreading(unittest.TestCase):

    def setUp(self):
        # Capture the `page` arg reaching _stage1_decompose across ALL calls.
        self._captured_pages: list[dict] = []
        self._orig_stage1 = prompt_drafter._stage1_decompose
        self._orig_draft = vd._draft_llm

        async def _capture(*, page, target, timeout_s=None):
            self._captured_pages.append(page)
            return dict(_DECOMPOSE)
        prompt_drafter._stage1_decompose = _capture

        async def _draft(system, user, model="sonnet"):
            return _CONCEPTS_JSON
        vd._draft_llm = _draft

    def tearDown(self):
        prompt_drafter._stage1_decompose = self._orig_stage1
        vd._draft_llm = self._orig_draft

    def _last_body(self) -> str:
        self.assertTrue(self._captured_pages, "decompose was never called")
        return self._captured_pages[-1].get("body_excerpt") or ""

    # ── type="text" (default) — back-compat ────────────────────────────
    def test_text_default_backcompat(self):
        pid = _run(_make_project(brief="A short video about Panama residency."))
        events = _run(_collect(pid, brief_source={"type": "text"}))
        self.assertIn("concepts", [e["type"] for e in events])
        body = self._last_body()
        self.assertIn("Panama residency", body)
        # No synthesized campaign / landing-page block leaked in.
        self.assertNotIn("SYNTHESIZED CAMPAIGN BRIEF", body)
        self.assertNotIn("LANDING PAGE", body)

    def test_none_brief_source_is_text(self):
        """Old clients send no brief_source at all → identical to text."""
        pid = _run(_make_project(brief="Legacy brief text."))
        events = _run(_collect(pid, brief_source=None))
        self.assertIn("concepts", [e["type"] for e in events])
        self.assertIn("Legacy brief text.", self._last_body())

    # ── type="campaign" — synthesized from campaign memory ─────────────
    def test_campaign_synthesizes_brief(self):
        import app.services.campaign_memory as cm
        orig = {
            "pinned": cm.load_pinned_facts,
            "profile": cm.load_profile,
            "decisions": cm.load_decisions,
        }
        # The turn imports campaign_memory as a module and calls these — patch
        # the module attributes so the synthesized block gets real signals.
        cm.load_pinned_facts = lambda a, c: "- Processing in 90 days"
        cm.load_profile = lambda a, c: "Goal: capture HNW demand-capture intent"
        cm.load_decisions = lambda a, c, limit=None: "| 2026-01-01 | raised budget |"
        try:
            pid = _run(_make_project(campaign_id="camp-1", brief=""))
            events = _run(_collect(pid, brief_source={"type": "campaign"}))
        finally:
            cm.load_pinned_facts = orig["pinned"]
            cm.load_profile = orig["profile"]
            cm.load_decisions = orig["decisions"]

        self.assertIn("concepts", [e["type"] for e in events])
        body = self._last_body()
        self.assertIn("SYNTHESIZED CAMPAIGN BRIEF", body)
        self.assertIn("Processing in 90 days", body)       # pinned facts
        self.assertIn("demand-capture intent", body)        # profile (guidelines)

    # ── type="landing_page" — fetched claims reach decompose ───────────
    def test_landing_page_claims_reach_decompose(self):
        orig_fetch = page_fetcher.fetch

        async def _fake_fetch(url):
            return page_fetcher.FetchedPage(
                url=url, final_url=url, title="Panama QIV Program",
                description=None, og={}, h1="Get residency in 90 days",
                body_excerpt="Invest EUR 250K and gain a second residency.",
                status=200,
            )
        page_fetcher.fetch = _fake_fetch
        try:
            pid = _run(_make_project(brief=""))
            events = _run(_collect(
                pid,
                brief_source={"type": "landing_page", "url": "https://example.com/qiv"},
            ))
        finally:
            page_fetcher.fetch = orig_fetch

        self.assertIn("concepts", [e["type"] for e in events])
        body = self._last_body()
        self.assertIn("LANDING PAGE", body)
        self.assertIn("Panama QIV Program", body)                 # title
        self.assertIn("Get residency in 90 days", body)           # h1
        self.assertIn("second residency", body)                   # body excerpt

    # ── landing_page fetch FAILURE — degrade, not block ────────────────
    def test_landing_page_fetch_failure_degrades(self):
        orig_fetch = page_fetcher.fetch

        async def _boom(url):
            raise page_fetcher.PageFetchError("network error")
        page_fetcher.fetch = _boom
        try:
            pid = _run(_make_project(brief="fallback brief text"))
            events = _run(_collect(
                pid,
                brief_source={"type": "landing_page", "url": "https://dead.example"},
            ))
        finally:
            page_fetcher.fetch = orig_fetch

        types = [e["type"] for e in events]
        # A verification/page-unverified event was yielded ...
        verifs = [e for e in events if e["type"] == "verification"]
        self.assertTrue(verifs, f"no verification event: {types}")
        self.assertEqual(verifs[0]["payload"]["stage"], "page-unverified")
        # ... AND the turn still completed (concepts drafted from the fallback).
        self.assertIn("concepts", types)
        self.assertIn("turn_done", types)
        self.assertIn("fallback brief text", self._last_body())

    def test_landing_page_non_2xx_degrades(self):
        orig_fetch = page_fetcher.fetch

        async def _404(url):
            return page_fetcher.FetchedPage(
                url=url, final_url=url, title="Nope", description=None, og={},
                h1=None, body_excerpt="", status=404,
            )
        page_fetcher.fetch = _404
        try:
            pid = _run(_make_project(brief="still have this"))
            events = _run(_collect(
                pid,
                brief_source={"type": "landing_page", "url": "https://example.com/x"},
            ))
        finally:
            page_fetcher.fetch = orig_fetch

        self.assertTrue([e for e in events if e["type"] == "verification"])
        self.assertIn("concepts", [e["type"] for e in events])


class DraftRouter400s(unittest.TestCase):
    """Draft endpoint validation — router-layer 400s for impossible requests."""

    def test_campaign_source_without_campaign_id_is_400(self):
        pid = _run(_make_project(campaign_id=None))
        body = vdr.VideoProjectDraft(brief_source=vdr.BriefSource(type="campaign"))
        with self.assertRaises(HTTPException) as ctx:
            _run(vdr.draft_video_project(pid, body))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_landing_page_source_without_url_is_400(self):
        pid = _run(_make_project())
        body = vdr.VideoProjectDraft(brief_source=vdr.BriefSource(type="landing_page"))
        with self.assertRaises(HTTPException) as ctx:
            _run(vdr.draft_video_project(pid, body))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_campaign_source_with_campaign_id_persists_and_starts(self):
        """Valid campaign source: no 400, brief_source persisted on the row."""
        pid = _run(_make_project(campaign_id="camp-9"))
        body = vdr.VideoProjectDraft(brief_source=vdr.BriefSource(type="campaign"))
        # chat_runner.start launches a detached task; we only need it not to 400.
        res = _run(vdr.draft_video_project(pid, body))
        self.assertIn("turn_id", res)

        async def _read():
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT brief_source FROM studio_video_projects WHERE id = ?", (pid,)
                )
                return (await cur.fetchone())[0]
            finally:
                await db.close()
        persisted = _run(_read())
        self.assertIsNotNone(persisted)
        self.assertEqual(json.loads(persisted)["type"], "campaign")


if __name__ == "__main__":
    unittest.main()
