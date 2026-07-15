"""Provenance manifest — Chat Orchestration v2, Epic 4 (§7.1).

A small, dependency-light, PURE record of every data block the orchestrator
touched during ONE turn. The claim gate (claim_gate.py) reads it to decide
which ID / page-state claims in the Director's final answer are actually
grounded in something we verified THIS session vs. recalled from memory.

Design invariants:
  * NO DB, NO network, NO I/O — pure in-memory accumulation, fully testable.
  * ID regexes are REUSED from agent._condense_for_memory's critical set
    (agent.py:910-917) so the manifest, the gate, and memory-condensing all
    speak the SAME ID vocabulary — prompt and enforcement stop drifting apart.

Manifest entry shape (§7.1):
  {"tag": LIVE_API|PAGE_FETCH|LOCAL_STORE|MEMORY, "ts": <ts>, "kind": <str>,
   "ids": [<id>, ...], "detail": <str>, ... tag-specific extras}
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# ── Tags (the §7.1 / §8.2 provenance taxonomy) ────────────────────────
TAG_LIVE_API = "LIVE_API"
TAG_PAGE_FETCH = "PAGE_FETCH"
TAG_LOCAL_STORE = "LOCAL_STORE"
TAG_MEMORY = "MEMORY"

# ── ID_PATTERNS — the shared ID vocabulary ────────────────────────────
# Reused from agent._condense_for_memory (critical_patterns). Ordered widest
# → narrowest; extract_ids runs them all and unions the hits.
#
# Conservative choices (flagged in the report):
#   * Conversion labels are the classic false-positive machine — a bare
#     [A-Za-z0-9_-]{10,} matches half of English. We ONLY harvest a label when
#     it is anchored to a "Label:" / "label" / "conversion" context, matching
#     the memory regex `Label:\s*[\w-]+`. Free-floating tokens are NOT labels.
#   * Long numeric campaign/criterion ids: `\b\d{9,}\b` (Google campaign ids are
#     ~10 digits). 9+ avoids catching prices/percentages.
ID_PATTERNS: list[re.Pattern] = [
    re.compile(r"GTM-[A-Z0-9]+"),
    re.compile(r"AW-\d+"),
    re.compile(r"G-[A-Z0-9]+"),
    # Conversion-ID phrasing carries its own numeric id.
    re.compile(r"Conversion ID:\s*(\d+)", re.IGNORECASE),
    # Conversion labels, anchored to a label/conversion context (no bare match).
    re.compile(r"(?:Label|conversion label)\s*:?\s*([A-Za-z0-9_-]{6,})", re.IGNORECASE),
    # Bare Google conversion-label shape ONLY inside a send_to-style pairing
    # like "AW-826329520/AbC-D_efG12" — captured via the slash-suffix.
    re.compile(r"AW-\d+/([A-Za-z0-9_-]{6,})"),
    # Long numeric campaign / criterion ids.
    re.compile(r"\b(\d{9,})\b"),
]

# Which regexes have a capture group (harvest group(1)) vs. the whole match.
_GROUP_INDEX = {
    re.compile(r"Conversion ID:\s*(\d+)", re.IGNORECASE): 1,
}


def extract_ids(text: str) -> set[str]:
    """Harvest every ID-shaped token from `text` using the shared pattern set.

    Returns the raw matched tokens (the full match for GTM-/AW-/G-, the captured
    numeric/label group for Conversion ID / Label / send_to shapes). Empty text
    → empty set. Pure.
    """
    out: set[str] = set()
    if not text:
        return out
    for pat in ID_PATTERNS:
        for m in pat.finditer(text):
            # Prefer a capture group when the pattern has one (label / conv-id /
            # send_to slash-suffix / bare numeric), else the whole match.
            if m.groups():
                val = m.group(1)
            else:
                val = m.group(0)
            if val:
                out.add(val.strip())
    return out


# ── Landing-page block parsing ────────────────────────────────────────
# fetch_ad_landing_pages emits (agent.py:876-895):
#   "=== LIVE LANDING PAGE STATE (fetched this session) ==="
#   "- {url} → HTTP {status} | ... | form signal: YES|none detected | tracking token: YES|none detected"
#   "- {url} → COULD NOT FETCH — treat page state as UNKNOWN"
_PAGE_URL_RE = re.compile(r"^-\s*(\S+)\s*→", re.MULTILINE)


class ProvenanceManifest:
    """Per-turn accumulation of every data block the orchestrator injected.

    Populated DURING the turn (RECALL / VERIFY / DISPATCH); read ONCE at S7 by
    run_claim_gate. Holds only plain dicts — trivially JSON-serialisable and
    snapshot-testable.
    """

    def __init__(self) -> None:
        self.entries: list[dict] = []
        # Every material number the manifest ever SAW (from tool outputs, the
        # page block, findings). The gate matches final-answer numbers against
        # this set for its FLAG-only numeric check (§7.2 b).
        self.seen_numbers: set[str] = set()

    # ── ingest helpers ────────────────────────────────────────────────
    def add_page_fetch(self, block: str, ts) -> Optional[dict]:
        """Record a PAGE_FETCH entry from a live landing-page block.

        Extracts every URL, and flags whether form / tracking signals were
        detected (so a "the page has a form" claim can trace to real evidence).
        Returns the entry (or None if the block was empty / unfetchable).
        """
        if not block:
            return None
        urls = _PAGE_URL_RE.findall(block)
        low = block.lower()
        form_present = "form signal: yes" in low
        tracking_present = "tracking token: yes" in low
        fetch_ok = "could not fetch" not in low and bool(urls)
        entry = {
            "tag": TAG_PAGE_FETCH,
            "ts": ts,
            "kind": "landing_page",
            "ids": urls,
            "urls": urls,
            "form_present": form_present,
            "tracking_present": tracking_present,
            "fetched": fetch_ok,
            "detail": "live landing-page fetch",
        }
        self.entries.append(entry)
        self._harvest_numbers(block)
        return entry

    def add_live_api(self, output: str, ts, tool_name: str = "") -> Optional[dict]:
        """Harvest ID-shaped tokens from a tool_result output → LIVE_API entry.

        A tool_result IS a this-session live pull, so any IDs it names are
        verified. Returns the entry (or None when the output carried no IDs —
        we don't record empty LIVE_API rows).
        """
        ids = extract_ids(output or "")
        self._harvest_numbers(output or "")
        if not ids:
            return None
        entry = {
            "tag": TAG_LIVE_API,
            "ts": ts,
            "kind": "tool_result",
            "tool": tool_name or "",
            "ids": sorted(ids),
            "detail": f"live tool output ({tool_name})" if tool_name else "live tool output",
        }
        self.entries.append(entry)
        return entry

    def add_local_store(self, ids: Iterable[str], ts, stale: bool = False,
                        detail: str = "local sync") -> dict:
        """Record a LOCAL_STORE entry (synced metrics etc.). `stale` marks a
        sync too old to count as verified for the gate."""
        idl = sorted({str(i).strip() for i in ids if str(i).strip()})
        entry = {
            "tag": TAG_LOCAL_STORE,
            "ts": ts,
            "kind": "metrics",
            "ids": idl,
            "stale": bool(stale),
            "detail": detail,
        }
        self.entries.append(entry)
        return entry

    def add_memory(self, summary: str, date, role: Optional[str] = None,
                   stale: bool = True) -> dict:
        """Record a MEMORY entry (recalled prior work). IDs inside memory are
        NOT auto-verified — the gate only trusts a memory id when the final
        sentence self-labels its source. We still harvest them so a
        self-labeled claim can trace back to this entry."""
        ids = sorted(extract_ids(summary or ""))
        entry = {
            "tag": TAG_MEMORY,
            "ts": date,
            "kind": "role_notes",
            "role": role,
            "ids": ids,
            "stale": bool(stale),
            "detail": (summary or "")[:200],
        }
        self.entries.append(entry)
        self._harvest_numbers(summary or "")
        return entry

    def add_from_findings(self, findings: Iterable[dict], ts) -> None:
        """Harvest IDs from specialist findings, tagging each by the source the
        finding CITES (conservative — we trust the specialist's own provenance):
          source string contains "live"/"api"  → LIVE_API
          "local"/"sync"/"store"               → LOCAL_STORE
          else                                 → MEMORY
        """
        for f in findings or []:
            if not isinstance(f, dict):
                continue
            claim = str(f.get("claim", "") or "")
            src_text = ""
            srcs = f.get("sources")
            if isinstance(srcs, list):
                for s in srcs:
                    if isinstance(s, dict):
                        src_text += " " + str(s.get("tag", "")) + " " + str(s.get("detail", ""))
                    else:
                        src_text += " " + str(s)
            src_low = src_text.lower()
            ids = extract_ids(claim)
            self._harvest_numbers(claim)
            if not ids:
                continue
            if "live" in src_low or "api" in src_low:
                self.add_live_api(claim, ts, tool_name="specialist-cited")
            elif "local" in src_low or "sync" in src_low or "store" in src_low:
                self.add_local_store(ids, ts, detail="specialist-cited local store")
            else:
                self.add_memory(claim, ts, stale=True)

    # ── read API (for the gate) ───────────────────────────────────────
    def verified_ids(self) -> set[str]:
        """The set of IDs the gate treats as verified WITHOUT needing a memory
        self-label: everything under LIVE_API / PAGE_FETCH / FRESH LOCAL_STORE.
        Bare MEMORY / stale LOCAL_STORE ids are excluded — they only pass the
        gate when the claim sentence self-labels its source."""
        out: set[str] = set()
        for e in self.entries:
            tag = e.get("tag")
            if tag in (TAG_LIVE_API, TAG_PAGE_FETCH):
                out.update(e.get("ids", []))
            elif tag == TAG_LOCAL_STORE and not e.get("stale"):
                out.update(e.get("ids", []))
        return out

    def page_fetch_entries(self) -> list[dict]:
        """PAGE_FETCH entries where the fetch actually succeeded."""
        return [e for e in self.entries
                if e.get("tag") == TAG_PAGE_FETCH and e.get("fetched")]

    def has_page_evidence(self) -> bool:
        return bool(self.page_fetch_entries())

    # ── internal ──────────────────────────────────────────────────────
    _NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

    def _harvest_numbers(self, text: str) -> None:
        if not text:
            return
        for m in self._NUM_RE.finditer(text):
            self.seen_numbers.add(m.group(0).replace(",", ""))
