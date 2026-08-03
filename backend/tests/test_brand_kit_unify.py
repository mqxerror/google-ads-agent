"""Story 18.2 — unify with extract-brief + /api/creative/brand-kit + persistence.

Network-free: page_fetcher.fetch is stubbed with a local fixture FetchedPage, and
brand_kit._download_image is stubbed with a generated PNG. Proves:
  * the endpoint persists scraped assets to ad_assets (source='scraped') + the
    ONE brand_kit row (FR3.3);
  * exactly ONE HTML document fetch per URL per run (the fetch-count spy);
  * the shared research object's hash is identical across the image path
    (extract-brief) and the copy path (FR3.3 identity);
  * create_job records research_hash on the job row.
"""

from __future__ import annotations

import asyncio
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="brand-kit-unify-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402
from app.services import brand_kit, creative_copy  # noqa: E402
from app.services.page_fetcher import FetchedPage  # noqa: E402

_FIX = Path(__file__).parent / "fixtures" / "brand_kit"


def _fixture_page() -> FetchedPage:
    html = (_FIX / "ssr_page.html").read_text(encoding="utf-8")
    return FetchedPage(
        url="https://www.mercan.com/lp/panama",
        final_url="https://www.mercan.com/lp/panama",
        title="Panama Golden Visa | Mercan Group",
        description="Secure Panama residency by investment with Mercan Group's trusted program.",
        og={"site_name": "Mercan Group", "title": "Panama Golden Visa",
            "image": "https://cdn.example.com/og/panama-hero.jpg"},
        h1="Panama Residency by Investment", body_excerpt="body text", status=200,
        raw_html=html,
    )


def _png_bytes(size: int = 400) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (14, 53, 96)).save(buf, format="PNG")
    return buf.getvalue()


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class ResearchObjectIdentity(unittest.TestCase):
    def test_hash_is_deterministic_and_content_sensitive(self):
        page = _fixture_page()
        ro = brand_kit.research_object(page)
        h1 = brand_kit.research_hash(ro)
        h2 = brand_kit.research_hash(brand_kit.research_object(page))
        self.assertEqual(h1, h2)  # deterministic → same page, same hash
        self.assertEqual(len(h1), 16)

        page.body_excerpt = "a different page body"
        h3 = brand_kit.research_hash(brand_kit.research_object(page))
        self.assertNotEqual(h1, h3)  # content change → hash changes

    def test_research_object_carries_stage1_signals(self):
        ro = brand_kit.research_object(_fixture_page())
        for k in ("url", "final_url", "title", "description", "og", "h1", "body_excerpt"):
            self.assertIn(k, ro)


class BrandKitEndpoint(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def _patch(self, monkey_fetch_counter=None):
        page = _fixture_page()

        async def fake_fetch(url):
            if monkey_fetch_counter is not None:
                monkey_fetch_counter.append(url)
            return page

        async def fake_download(url, *, client=None):
            return _png_bytes(), "image/png"

        async def fake_css(page_arg, *, client=None):
            return []

        async def fake_robots(url):
            return True, ""      # network-free: no live robots.txt fetch

        import app.services.page_fetcher as pf
        self._orig_fetch = pf.fetch
        self._orig_dl = brand_kit._download_image
        self._orig_css = brand_kit.fetch_linked_css
        self._orig_robots = brand_kit._robots_allows
        pf.fetch = fake_fetch
        brand_kit._download_image = fake_download
        brand_kit.fetch_linked_css = fake_css
        brand_kit._robots_allows = fake_robots

    def _unpatch(self):
        import app.services.page_fetcher as pf
        pf.fetch = self._orig_fetch
        brand_kit._download_image = self._orig_dl
        brand_kit.fetch_linked_css = self._orig_css
        brand_kit._robots_allows = self._orig_robots

    def test_endpoint_persists_assets_and_returns_kit(self):
        self._patch()
        try:
            r = self.client.post("/api/creative/brand-kit", json={
                "url": "https://www.mercan.com/lp/panama",
                "account_id": "acc-18-2", "confirm_ownership": True,
            })
        finally:
            self._unpatch()
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["brand_name"], "Mercan Group")
        self.assertTrue(body["kit_asset_id"])
        self.assertTrue(body["research_hash"])
        self.assertIsNotNone(body["logo_asset_id"])           # logo persisted
        self.assertGreaterEqual(len(body["hero_images"]), 1)  # ≥1 hero persisted
        self.assertTrue(any(c["hex"] == "#0e3560" for c in body["colors"]))

        # ad_assets rows landed with source='scraped' — pickable in LibraryPicker.
        async def _count():
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT type, COUNT(*) n FROM ad_assets WHERE account_id='acc-18-2' "
                    "AND source='scraped' GROUP BY type")
                return {row["type"]: row["n"] for row in await cur.fetchall()}
            finally:
                await db.close()
        counts = asyncio.run(_count())
        self.assertEqual(counts.get("brand_kit"), 1)          # ONE brand_kit row
        self.assertGreaterEqual(counts.get("image", 0), 2)    # logo + ≥1 hero

    def test_one_html_fetch_per_run(self):
        counter: list[str] = []
        self._patch(monkey_fetch_counter=counter)
        try:
            r = self.client.post("/api/creative/brand-kit", json={
                "url": "https://www.mercan.com/lp/panama",
                "account_id": "acc-spy", "confirm_ownership": True,
            })
        finally:
            self._unpatch()
        self.assertEqual(r.status_code, 200, r.text)
        # Exactly ONE HTML document fetch; image + stylesheet sub-fetches are
        # separate asset fetches (mocked away here), never a page re-fetch.
        self.assertEqual(len(counter), 1)

    def test_refuses_without_ownership_confirmation(self):
        r = self.client.post("/api/creative/brand-kit", json={
            "url": "https://www.notmine.example.com/", "account_id": "acc-x",
        })
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "scrape_refused")


class ExtractBriefUnification(unittest.TestCase):
    """extract-brief refactored onto brand_kit.research_object stays behavior-
    stable AND now surfaces the SAME research_hash the copy path records (FR3.3)."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_extract_brief_shares_research_hash_with_copy_path(self):
        page = _fixture_page()

        async def fake_fetch(url):
            return page

        async def fake_draft(**kwargs):
            # the Stage-1 input IS the shared research object — assert its shape
            assert "body_excerpt" in kwargs["page"] and "og" in kwargs["page"]
            return {
                "brief": {"subject": "an investor", "setting": "Panama",
                          "value_prop": "residency by investment", "audience": "HNW investors",
                          "tone": "aspirational", "program": "panama",
                          "hard_constraints": [], "claim_hints": ["trusted program"]},
                "variants": [{"angle": "problem-led", "prompt": "p", "rationale": "r"},
                             {"angle": "aspirational", "prompt": "p", "rationale": "r"},
                             {"angle": "social-proof", "prompt": "p", "rationale": "r"}],
                "pinned_claims_used": [],
            }

        import app.services.page_fetcher as pf
        import app.services.prompt_drafter as pd
        orig_fetch, orig_draft = pf.fetch, pd.draft_variants
        pf.fetch = fake_fetch
        pd.draft_variants = fake_draft
        try:
            r = self.client.post("/api/studio/extract-brief", json={
                "url": "https://www.mercan.com/lp/panama", "target": "image"})
        finally:
            pf.fetch, pd.draft_variants = orig_fetch, orig_draft

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        # brief + variants still returned (behavior stable for existing consumers)
        self.assertEqual(body["brief"]["value_prop"], "residency by investment")
        self.assertEqual(len(body["variants"]), 3)
        # the research_hash equals the deterministic hash for the same page — the
        # identity token the copy drafter records on its job row.
        expected = brand_kit.research_hash(brand_kit.research_object(page))
        self.assertEqual(body["research_hash"], expected)


class OwnedDomainsConfigSeed(unittest.TestCase):
    """Story 18.4 — the ownership allowlist lives in the config table, seeded
    idempotently by init_db (FR3.5). Owned domains + subdomains resolve; the
    scrape guard reads it."""

    def test_config_seed_present_and_read(self):
        async def _run():
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT value FROM config WHERE key='creative.owned_domains'")
                row = await cur.fetchone()
            finally:
                await db.close()
            domains = await brand_kit._owned_domains()
            return row, domains
        row, domains = asyncio.run(_run())
        self.assertIsNotNone(row)                     # init_db seeded the row
        self.assertIn("mercan.com", domains)

    def test_owned_subdomain_resolves_without_confirm(self):
        # www + goldenvisas subdomains both match mercan.com; robots stubbed open.
        orig = brand_kit._robots_allows

        async def fake_robots(url):
            return True, ""
        brand_kit._robots_allows = fake_robots
        try:
            async def _run():
                await brand_kit.assert_scrapable(
                    "https://goldenvisas.mercan.com/lp", confirm_ownership=False)
            asyncio.run(_run())  # no raise = owned subdomain allowed
        finally:
            brand_kit._robots_allows = orig


class CopyJobResearchHash(unittest.TestCase):
    def test_create_job_records_research_hash(self):
        async def _run():
            job_id = await creative_copy.create_job(
                "draft", "acc-rh", "pmax", {"brief": "x"}, research_hash="deadbeefcafe0001")
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT research_hash FROM creative_jobs WHERE id=?", (job_id,))
                return (await cur.fetchone())["research_hash"]
            finally:
                await db.close()
        self.assertEqual(asyncio.run(_run()), "deadbeefcafe0001")


if __name__ == "__main__":
    unittest.main()
