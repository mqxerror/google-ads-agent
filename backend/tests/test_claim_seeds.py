"""Story 18.3 — the scraped-claim accuracy gate (FR3.4 · Honesty ledger #5).

A scraped page can never resurrect the Panama stay-requirement class of error: a
claim that asserts a pinned-BANNED phrase appears in the RAW brand kit but is
filtered out of the copy-seed output, and the drop is logged with the claim text.

Network-free; pinned facts come from a temp memory dir (monkeypatched).
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from app.services import brand_kit, claim_gate
from app.services import prompt_drafter
from app.services.page_fetcher import FetchedPage


class ClaimGatePrimitives(unittest.TestCase):
    def test_normalize_claim(self):
        self.assertEqual(claim_gate.normalize_claim("No-minimum  STAY!"), "no minimum stay")

    def test_extract_banned_phrases_quoted_false_and_markers(self):
        facts = [
            'The "no minimum stay" is FALSE for Panama (one visit every 2 years).',
            "BANNED CLAIM: guaranteed citizenship — residency only",
            "Campaign ID: 24002195025 — a normal true fact, no ban marker",
        ]
        banned = claim_gate.extract_banned_phrases(facts)
        self.assertIn("no minimum stay", banned)
        self.assertIn("guaranteed citizenship", banned)
        # a plain true fact contributes NO ban (pinned facts aren't a banlist)
        self.assertFalse(any("campaign id" in b for b in banned))

    def test_claim_matches_banned_token_boundary(self):
        banned = ["no minimum stay"]
        self.assertEqual(
            claim_gate.claim_matches_banned("Enjoy Panama with no minimum stay requirement", banned),
            "no minimum stay")
        self.assertIsNone(claim_gate.claim_matches_banned("A real minimum investment applies", banned))


class FilterClaimSeeds(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="claim-seeds-test-"))
        (self._tmp / "acc1" / "camp1").mkdir(parents=True)
        (self._tmp / "acc1" / "camp1" / "pinned_facts.md").write_text(
            "# Pinned Facts\n"
            '- The "no minimum stay" is FALSE for Panama — one visit every 2 years.\n'
            "- BANNED CLAIM: guaranteed citizenship — residency only, never guaranteed\n"
            "- Currency: USD (a normal true fact)\n",
            encoding="utf-8",
        )
        self._orig = prompt_drafter._MEMORY_DIR
        prompt_drafter._MEMORY_DIR = self._tmp

    def tearDown(self):
        prompt_drafter._MEMORY_DIR = self._orig
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_banned_claims_dropped_clean_kept(self):
        claims = [
            "Panama residency with no minimum stay",       # banned (quoted-false)
            "Guaranteed citizenship in 12 months",         # banned (marker)
            "Trusted by thousands of investors worldwide", # clean
        ]
        kept, dropped = brand_kit.filter_claim_seeds(claims, "acc1", "camp1")
        self.assertEqual(kept, ["Trusted by thousands of investors worldwide"])
        dropped_claims = {d["claim"] for d in dropped}
        self.assertIn("Panama residency with no minimum stay", dropped_claims)
        self.assertIn("Guaranteed citizenship in 12 months", dropped_claims)
        # every drop carries the offending banned phrase for the audit log
        self.assertTrue(all(d["banned_phrase"] for d in dropped))

    def test_no_campaign_context_passes_through(self):
        kept, dropped = brand_kit.filter_claim_seeds(["anything"], "acc1", None)
        self.assertEqual(kept, ["anything"])
        self.assertEqual(dropped, [])

    def test_raw_kit_keeps_the_banned_claim_but_seeds_drop_it(self):
        """FR3.4 AC: the banned claim is present in the RAW brand kit, absent from
        the gated copy-seed output."""
        html = (
            "<html><body>"
            "<h1>Panama residency with no minimum stay</h1>"
            "<h2>Trusted by thousands of investors</h2>"
            "</body></html>"
        )
        page = FetchedPage(url="https://www.mercan.com/lp/panama",
                           final_url="https://www.mercan.com/lp/panama", title=None,
                           description=None, og={}, h1=None, body_excerpt="",
                           status=200, raw_html=html)
        kit = brand_kit.extract(page)
        # RAW kit contains the banned claim
        self.assertTrue(any("no minimum stay" in c for c in kit.claims))
        # gated seed output does NOT
        kept, dropped = brand_kit.filter_claim_seeds(kit.claims, "acc1", "camp1")
        self.assertFalse(any("no minimum stay" in c for c in kept))
        self.assertTrue(any("no minimum stay" in d["claim"] for d in dropped))


if __name__ == "__main__":
    unittest.main()
