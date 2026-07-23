"""Chat Orchestration v2 — Epic 4 tests (provenance manifest + claim gate).

Stdlib unittest, NO network, NO real LLM. Two layers:
  1. Pure unit tests of ProvenanceManifest + run_claim_gate (the bulk — the gate
     is a deterministic pure function, so it's cheaply and thoroughly testable).
  2. ONE integration assertion through run_turn's orchestrate path, reusing the
     test_chat_orchestrator mocking harness (scripted fake stream), proving a
     claim_gate event with checked>0 is emitted when the Director final contains
     an unsourced ID.

Panama fixtures (plan lines 17/32/36): GTM-WZKDXFH8, AW-826329520, AW-959555504.

Run:  cd backend && python -m unittest tests.test_claim_gate -v
"""

from __future__ import annotations

import asyncio
import unittest
import uuid

from app.services.provenance import (
    ProvenanceManifest,
    TAG_LIVE_API,
    TAG_PAGE_FETCH,
    extract_ids,
)
from app.services.claim_gate import run_claim_gate, _ID_UNVERIFIED, _ID_SOFT_SUFFIX

_TS = "2026-07-14T12:00:00+00:00"

# A realistic landing-page block in the exact fetch_ad_landing_pages shape.
_PAGE_BLOCK = (
    "=== LIVE LANDING PAGE STATE (fetched this session) ===\n"
    "(Verify page/form/tracking claims against THIS, not stored findings.)\n"
    "- https://www.mercan.com/panama-qualified-investor-program → HTTP 200 | "
    "title: Panama QIV | h1: Invest in Panama | form signal: YES | "
    "tracking token: YES"
)


# ─────────────────────────── manifest units ───────────────────────────
class ProvenanceManifestUnit(unittest.TestCase):
    def test_extract_ids_all_shapes(self):
        text = (
            "Container GTM-WZKDXFH8 feeds AW-826329520 and GA4 G-ABC123XYZ. "
            "Conversion ID: 959505327. Label: fc6FCO3YnI4cELCTg4oD. "
            "Campaign 22996208317 is live."
        )
        ids = extract_ids(text)
        self.assertIn("GTM-WZKDXFH8", ids)
        self.assertIn("AW-826329520", ids)
        self.assertIn("G-ABC123XYZ", ids)
        self.assertIn("959505327", ids)            # Conversion ID group
        self.assertIn("fc6FCO3YnI4cELCTg4oD", ids)  # Label group
        self.assertIn("22996208317", ids)          # long numeric campaign id

    def test_extract_ids_no_false_positive_on_prose(self):
        # A bare 10+ char English word must NOT be harvested as a conversion
        # label (labels are anchored to a "Label:"/"conversion" context).
        ids = extract_ids("The recommendation is straightforward and reasonable.")
        self.assertEqual(ids, set())

    def test_page_fetch_parsing_records_url_and_flags(self):
        m = ProvenanceManifest()
        entry = m.add_page_fetch(_PAGE_BLOCK, _TS)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["tag"], TAG_PAGE_FETCH)
        self.assertIn(
            "https://www.mercan.com/panama-qualified-investor-program",
            entry["urls"])
        self.assertTrue(entry["form_present"])
        self.assertTrue(entry["tracking_present"])
        self.assertTrue(entry["fetched"])
        self.assertTrue(m.has_page_evidence())

    def test_page_fetch_could_not_fetch_not_evidence(self):
        m = ProvenanceManifest()
        block = (
            "=== LIVE LANDING PAGE STATE (fetched this session) ===\n"
            "- https://x.test/lp → COULD NOT FETCH — treat page state as UNKNOWN")
        m.add_page_fetch(block, _TS)
        self.assertFalse(m.has_page_evidence())

    def test_add_live_api_harvests_ids(self):
        m = ProvenanceManifest()
        m.add_live_api("send_to: AW-826329520/AbCdEfGhIj", _TS, tool_name="search")
        self.assertIn("AW-826329520", m.verified_ids())

    def test_verified_ids_excludes_bare_memory(self):
        m = ProvenanceManifest()
        m.add_memory("uses GTM-WZKDXFH8 per notes", "2026-06-01", stale=True)
        # A bare MEMORY id is NOT in verified_ids (only self-labeled claims pass).
        self.assertNotIn("GTM-WZKDXFH8", m.verified_ids())

    def test_fresh_local_store_verified_stale_not(self):
        m = ProvenanceManifest()
        m.add_local_store(["22996208317"], _TS, stale=False)
        m.add_local_store(["11111111111"], _TS, stale=True)
        v = m.verified_ids()
        self.assertIn("22996208317", v)
        self.assertNotIn("11111111111", v)

    def test_memory_ids_collects_memory_and_stale_local(self):
        # item 3 — memory_ids() = "known from records but not re-verified live":
        # MEMORY ids + STALE LOCAL_STORE ids; excludes LIVE / fresh-local.
        m = ProvenanceManifest()
        m.add_memory("container GTM-K6864NBH per guidelines", "2026-04-13")
        m.add_local_store(["11111111111"], _TS, stale=True)
        m.add_local_store(["22996208317"], _TS, stale=False)   # fresh → excluded
        m.add_live_api("AW-826329520 live", _TS, tool_name="search")  # excluded
        mem = m.memory_ids()
        self.assertIn("GTM-K6864NBH", mem)
        self.assertIn("11111111111", mem)
        self.assertNotIn("22996208317", mem)   # fresh local is verified, not memory
        self.assertNotIn("AW-826329520", mem)  # live is verified, not memory

    def test_add_from_findings_source_routing(self):
        m = ProvenanceManifest()
        m.add_from_findings([
            {"claim": "container GTM-WZKDXFH8 fires", "sources": ["live API pull"]},
            {"claim": "account AW-959505327 synced", "sources": ["local sync store"]},
            {"claim": "label from AW-826329520 recalled", "sources": ["prior notes"]},
        ], _TS)
        v = m.verified_ids()
        self.assertIn("GTM-WZKDXFH8", v)   # live → LIVE_API → verified
        self.assertIn("959505327", v)      # local → fresh LOCAL_STORE → verified
        # AW-826329520's memory-routed entry is NOT auto-verified.
        # (It could appear via other paths, but "prior notes" → MEMORY.)


# ──────────────────────────── the gate ─────────────────────────────────
class ClaimGate(unittest.TestCase):
    # KEY CASE 1 — fabricated GTM id gets REWRITTEN.
    def test_fabricated_gtm_id_rewritten(self):
        m = ProvenanceManifest()  # empty manifest → nothing verified
        text = "I set up the container GTM-WZKDXFH8 for this campaign."
        res = run_claim_gate(text, m, page_verified=None)
        self.assertNotIn("GTM-WZKDXFH8", res["text"])
        self.assertIn(_ID_UNVERIFIED, res["text"])
        rew_claims = [r["claim"] for r in res["event"]["rewritten"]]
        self.assertIn("GTM-WZKDXFH8", rew_claims)
        self.assertGreaterEqual(res["event"]["checked"], 1)

    # KEY CASE 2 — a manifest-backed id PASSES untouched.
    def test_manifest_backed_id_passes(self):
        m = ProvenanceManifest()
        m.add_live_api("account AW-826329520 active", _TS, tool_name="search")
        text = "Your Ads account AW-826329520 is tracking conversions correctly."
        res = run_claim_gate(text, m, page_verified=None)
        self.assertIn("AW-826329520", res["text"])          # stayed in text
        self.assertEqual(res["event"]["rewritten"], [])     # not rewritten
        self.assertGreaterEqual(res["event"]["passed"], 1)  # counted as passed

    # KEY CASE 3 — unsourced page-state claim is flagged (None) / rewritten (False).
    def test_page_state_claim_flagged_when_no_check(self):
        m = ProvenanceManifest()  # no PAGE_FETCH entry
        text = "The landing page has a working lead form and the tracking pixel fires."
        res = run_claim_gate(text, m, page_verified=None)  # no fetch ran → FLAG
        self.assertTrue(res["event"]["flagged"])
        self.assertEqual(res["event"]["rewritten"], [])  # None → flag, not rewrite

    def test_page_state_claim_rewritten_when_fetch_failed(self):
        m = ProvenanceManifest()
        text = "The page has a form capturing emails."
        res = run_claim_gate(text, m, page_verified=False)  # fetch FAILED → REWRITE
        self.assertIn("UNVERIFIED", res["text"])
        self.assertTrue(res["event"]["rewritten"])

    def test_page_state_claim_passes_when_backed(self):
        m = ProvenanceManifest()
        m.add_page_fetch(_PAGE_BLOCK, _TS)  # real PAGE_FETCH evidence
        text = "The landing page has a form and the tracking token is present."
        res = run_claim_gate(text, m, page_verified=True)
        self.assertEqual(res["event"]["rewritten"], [])
        self.assertEqual(res["event"]["flagged"], [])
        self.assertGreaterEqual(res["event"]["passed"], 1)

    # KEY CASE 4 — the $706 = 45% × $1,569 derived-math case PASSES clean.
    def test_derived_math_no_false_positive(self):
        m = ProvenanceManifest()  # manifest saw NONE of these numbers
        text = "Recommended budget cut is $706 (45% × $1,569) starting next week."
        res = run_claim_gate(text, m, page_verified=None)
        # Zero flags AND zero rewrites for those numbers.
        self.assertEqual(res["event"]["flagged"], [])
        self.assertEqual(res["event"]["rewritten"], [])
        self.assertIn("$706", res["text"])
        self.assertIn("$1,569", res["text"])

    def test_event_shape_matches_appendix(self):
        m = ProvenanceManifest()
        res = run_claim_gate("A plain answer with no claims to check.", m, None)
        ev = res["event"]
        for k in ("checked", "passed", "rewritten"):
            self.assertIn(k, ev)  # §4.4 line 171 shape
        self.assertIsInstance(ev["rewritten"], list)
        # passed ≤ checked and non-negative (frontend chip ratio invariant).
        self.assertLessEqual(ev["passed"], ev["checked"])
        self.assertGreaterEqual(ev["passed"], 0)

    def test_self_labeled_memory_id_allowed(self):
        m = ProvenanceManifest()  # empty — id not in a live pull
        text = "The container GTM-WZKDXFH8 (from cro_specialist, 2026-06-01) may still apply."
        res = run_claim_gate(text, m, page_verified=None)
        # Self-labeled memory source → id allowed to stand, not rewritten.
        self.assertIn("GTM-WZKDXFH8", res["text"])
        self.assertEqual(res["event"]["rewritten"], [])

    def test_mixed_verified_and_fabricated(self):
        m = ProvenanceManifest()
        m.add_live_api("AW-826329520", _TS, tool_name="search")
        text = "Account AW-826329520 uses container GTM-FAKE9999 for tracking."
        res = run_claim_gate(text, m, page_verified=None)
        self.assertIn("AW-826329520", res["text"])       # verified → stays
        self.assertNotIn("GTM-FAKE9999", res["text"])    # fabricated → rewritten
        self.assertEqual(len(res["event"]["rewritten"]), 1)

    # ── item 3 — memory-sourced IDs get a SOFT label, not a hard rewrite ──
    def test_memory_sourced_id_soft_labeled_not_rewritten(self):
        # A TRUE stored fact (in account records via MEMORY) that isn't re-pulled
        # live must NOT get the false-positive "[not verified]" hard rewrite —
        # it's SOFT-labeled in place (id kept + caveat appended).
        m = ProvenanceManifest()
        m.add_memory("we use container GTM-K6864NBH", "2026-04-13", stale=True)
        text = "The container GTM-K6864NBH handles conversion tracking."
        res = run_claim_gate(text, m, page_verified=None)
        self.assertIn("GTM-K6864NBH", res["text"])            # id KEPT
        self.assertNotIn(_ID_UNVERIFIED, res["text"])         # NOT hard-rewritten
        self.assertIn(_ID_SOFT_SUFFIX, res["text"])           # soft caveat appended
        self.assertEqual(res["event"]["rewritten"], [])
        soft = [s["claim"] for s in res["event"]["soft_labeled"]]
        self.assertIn("GTM-K6864NBH", soft)

    def test_gtm_from_guidelines_soft_labeled(self):
        # The canonical case: GTM-K6864NBH injected from guidelines (account
        # records) → soft-labeled, never hard-rewritten.
        m = ProvenanceManifest()
        m.add_memory(
            "GTM container GTM-K6864NBH; GV Lead label fc6FCO3YnI4cELCTg4oD",
            "2026-04-13", role="guidelines", stale=False)
        text = "Tracking runs through GTM-K6864NBH with the GV Lead label."
        res = run_claim_gate(text, m, page_verified=None)
        self.assertIn("GTM-K6864NBH", res["text"])
        self.assertNotIn(_ID_UNVERIFIED, res["text"])
        self.assertTrue(res["event"]["soft_labeled"])

    def test_no_source_anywhere_still_hard_rewritten(self):
        # The hard rewrite is RESERVED for an id with NO source at all.
        m = ProvenanceManifest()
        m.add_memory("we use GTM-K6864NBH", "2026-04-13")  # a DIFFERENT id known
        text = "You are on container GTM-TOTALLYFAKE right now."
        res = run_claim_gate(text, m, page_verified=None)
        self.assertNotIn("GTM-TOTALLYFAKE", res["text"])
        self.assertIn(_ID_UNVERIFIED, res["text"])
        rew = [r["claim"] for r in res["event"]["rewritten"]]
        self.assertIn("GTM-TOTALLYFAKE", rew)

    def test_soft_label_accounting_and_event_shape(self):
        # passed = checked − rewritten − flagged − soft_labeled; soft_labeled key
        # present and a list. One live id (pass) + one memory id (soft).
        m = ProvenanceManifest()
        m.add_live_api("AW-826329520 active", _TS, tool_name="search")
        m.add_memory("container GTM-K6864NBH", "2026-04-13")
        text = "Account AW-826329520 uses container GTM-K6864NBH."
        res = run_claim_gate(text, m, page_verified=None)
        ev = res["event"]
        self.assertIn("soft_labeled", ev)
        self.assertIsInstance(ev["soft_labeled"], list)
        self.assertEqual(len(ev["soft_labeled"]), 1)
        self.assertEqual(ev["rewritten"], [])
        # AW passed, GTM soft-labeled → passed counts only the live one.
        self.assertEqual(
            ev["passed"],
            ev["checked"] - len(ev["rewritten"]) - len(ev["flagged"])
            - len(ev["soft_labeled"]))


# ──────────────── integration: run_turn emits claim_gate ────────────────
# Reuse the test_chat_orchestrator harness (scripted fake stream). We import its
# module-level fake so setUp/tearDown patch app.services.agent identically.
# Importing sets DATA_DIR to a temp dir; we run init_db() here so this file also
# works when run standalone (test_chat_orchestrator.setUpModule may not fire).
from tests import test_chat_orchestrator as tco  # noqa: E402


def setUpModule():
    from app.database import init_db
    tco._TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


class RunTurnClaimGate(tco._Base):
    async def test_orchestrate_emits_claim_gate_with_unsourced_id(self):
        # Script: plan (1 specialist) → specialist (empty findings, no tools) →
        # synth returns a final containing an UNSOURCED GTM id.
        plan = tco._text_call(
            '```json\n{"specialists":['
            '{"role_id":"ppc_strategist","model":"sonnet","tools":[],"task":"analyze"}]}\n```')
        spec = tco._text_call('ok\n```json\n{"findings":[],"summary":"x"}\n```')
        synth = tco._text_call(
            "Your setup uses container GTM-FAKE123 for conversion tracking.")
        tco._SCRIPT.extend([plan, spec, synth])

        events = await self._run(
            force_mode="orchestrate",
            user_message="audit my whole tracking setup end to end please")
        gates = [e for e in events if e["type"] == "claim_gate"]
        self.assertTrue(gates, "expected a claim_gate event")
        payload = gates[0]["payload"]
        for k in ("checked", "passed", "rewritten"):
            self.assertIn(k, payload)
        self.assertGreater(payload["checked"], 0)
        # The fabricated id was rewritten.
        rew_claims = [r["claim"] for r in payload["rewritten"]]
        self.assertIn("GTM-FAKE123", rew_claims)

        # And the PERSISTED assistant message is the GATED text (id gone).
        from app.database import get_db
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT content FROM messages WHERE role='assistant' "
                "ORDER BY rowid DESC LIMIT 1")
            row = await cur.fetchone()
        finally:
            await db.close()
        self.assertIsNotNone(row)
        self.assertNotIn("GTM-FAKE123", row[0])


if __name__ == "__main__":
    unittest.main()
