"""The claim gate — Chat Orchestration v2, Epic 4 (§7.2).

Deterministic, LLM-free, I/O-free post-processor that runs on the Director's
FINAL synthesized text (S7) BEFORE it is persisted. It catches the two classes
of hallucination that actually burned us (F1 fabricated IDs, F5 asserted page
state we never checked) and rewrites them IN PLACE — never silently deleting
text — so the persisted answer can't ship a fabricated GTM id or an unverified
"the page has a form" claim.

Scope discipline (§7.2): the gate targets **IDs**, **page-state assertions**,
and does a CONSERVATIVE flag-only pass on material numbers. It deliberately
does NOT try to verify arithmetic — numbers that the text itself DERIVES
(e.g. "$706 (45% × $1,569)") pass clean. Metric provenance beyond that is the
inline layer tags' job (§6.1), not the gate's.

Counting contract (asserted by the tests):
  * `checked`   = total distinct claims the gate EXAMINED (ID claims +
                  page-state claims + material-number claims it considered).
  * `rewritten` = claims the gate could NOT verify and rewrote in place
                  (unverified IDs, unbacked/failed-fetch page-state).
  * `flagged`   = claims the gate surfaced but did NOT rewrite (unmatched
                  material numbers; page-state claims when NO page check ran
                  this turn — conservative, we didn't try to verify).
  * `passed`    = checked − len(rewritten) − len(flagged)  (claims that traced
                  clean). Always 0 ≤ passed ≤ checked, so the frontend chip's
                  {passed}/{checked} ratio reads as verified/examined.

Pure function: `run_claim_gate(final_text, manifest, page_verified) -> {...}`.
"""

from __future__ import annotations

import re
from typing import Optional

from app.services.provenance import ID_PATTERNS, ProvenanceManifest, extract_ids

# The inline replacement for an unverified ID token (§7.2.3). We rewrite the
# TOKEN, keeping the surrounding sentence intact.
_ID_UNVERIFIED = "[ID not verified this session — pull it before relying on it]"
_PAGE_UNVERIFIED = (
    "page state UNVERIFIED this session — recommend re-fetch before relying on it."
)

# ── sentence splitting ────────────────────────────────────────────────
# Cheap, deterministic. Split on sentence terminators + newlines; keep it simple
# so behaviour is predictable (no NLP dependency).
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(text or "") if s.strip()]


# ── memory self-label detection (§7.2.2) ──────────────────────────────
# A sentence "self-labels" a memory source when it carries an explicit
# provenance marker: a "(from …, <date>)" citation, an explicit "not verified"
# hedge, or a MEMORY/recalled tag. Such an id is allowed to stand even without a
# live manifest entry — the reader has been told it's from memory.
_MEMORY_LABEL_RE = re.compile(
    r"\(from\b[^)]*\)"                 # "(from cro_specialist, 2026-06-01)"
    r"|not verified"
    r"|unverified"
    r"|from memory"
    r"|recalled\b"
    r"|\bMEMORY\b"
    r"|per (?:prior|earlier|last)\b",
    re.IGNORECASE,
)


def _self_labels_memory(sentence: str) -> bool:
    return bool(_MEMORY_LABEL_RE.search(sentence))


# ── page-state vocabulary (§7.2.4) ────────────────────────────────────
# A sentence ASSERTS page state when it talks about form / tracking / pixel /
# tag-firing / the page having-or-lacking something.
_PAGE_STATE_RE = re.compile(
    r"\bform\b"
    r"|\btracking\b"
    r"|\bpixel\b"
    r"|\btag (?:fires|firing|is present|present)\b"
    r"|\bthe page (?:has|lacks|contains|is missing|includes)\b"
    r"|\blanding page (?:has|lacks|contains)\b",
    re.IGNORECASE,
)


def _asserts_page_state(sentence: str) -> bool:
    return bool(_PAGE_STATE_RE.search(sentence))


# ── derived-math guard (§7.2.b — the critical false-positive guard) ───
# A number is "derived in text" when it sits next to arithmetic that produces
# it: a ×/x/*, a %, an =, "of", or lives inside a parenthetical that contains
# any of those. The canonical case that MUST pass clean:
#   "$706 (45% × $1,569)"  → 706, 45, 1,569 all treated as derived-math → PASS.
_MATH_NEAR_RE = re.compile(r"[×x*=]|%|\bof\b", re.IGNORECASE)
# A parenthetical containing math operators — everything inside is derivation.
_MATH_PAREN_RE = re.compile(r"\([^)]*(?:[×x*=]|%|\bof\b)[^)]*\)", re.IGNORECASE)


def _derived_number_spans(text: str) -> list[tuple[int, int]]:
    """Char-index spans of `text` covered by a math-derivation parenthetical.
    Numbers inside these spans are results/operands of shown arithmetic and are
    NEVER flagged."""
    return [(m.start(), m.end()) for m in _MATH_PAREN_RE.finditer(text or "")]


# Material-number tokens: money, percentages, or plain counts stated as fact.
_NUM_TOKEN_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def _normalize_num(tok: str) -> str:
    return tok.replace("$", "").replace(",", "").rstrip("%").strip()


def run_claim_gate(
    final_text: str,
    manifest: ProvenanceManifest,
    page_verified: Optional[bool],
) -> dict:
    """Gate the Director's final text against the provenance manifest.

    Args:
      final_text:    the synthesized answer to be persisted.
      manifest:      the per-turn ProvenanceManifest (already populated).
      page_verified: True  = a landing-page fetch this turn SUCCEEDED,
                     False = a fetch was attempted but FAILED,
                     None  = no page check happened this turn.

    Returns {"text": <gated text>, "event": {checked, passed, rewritten, flagged}}.
    Deterministic. No LLM. No I/O.
    """
    text = final_text or ""
    verified = manifest.verified_ids()
    has_page_evidence = manifest.has_page_evidence()

    rewritten: list[dict] = []
    flagged: list[dict] = []
    checked = 0

    # ── (a) ID-shaped claims ──────────────────────────────────────────
    # Gather every ID token with its char span, then rewrite unverified ones.
    id_hits: list[tuple[int, int, str]] = []  # (start, end, token)
    for pat in ID_PATTERNS:
        for m in pat.finditer(text):
            # Only rewrite the actual id-token substring; for grouped patterns
            # (Conversion ID / Label / send_to) rewrite the captured group span.
            if m.groups() and m.group(1):
                span = m.span(1)
                token = m.group(1)
            else:
                span = m.span(0)
                token = m.group(0)
            id_hits.append((span[0], span[1], token))

    # De-dup overlapping spans (same char range matched by two patterns): keep
    # the widest. Sort by start, drop hits fully contained in a kept hit.
    id_hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, tok in id_hits:
        if any(start >= ks and end <= ke for ks, ke, _ in kept):
            continue
        kept.append((start, end, tok))

    # Which sentence each hit lives in (for the self-label check). Build a char
    # → sentence map once.
    def _sentence_at(pos: int) -> str:
        # Find the sentence window containing char pos.
        cursor = 0
        for s in _sentences(text):
            idx = text.find(s, cursor)
            if idx == -1:
                idx = cursor
            if idx <= pos < idx + len(s):
                return s
            cursor = idx + len(s)
        return text  # fallback: whole text

    # Rewrite from the END backwards so earlier spans stay valid.
    kept.sort(key=lambda h: h[0], reverse=True)
    out = text
    for start, end, tok in kept:
        checked += 1
        if tok in verified:
            continue  # traced to a live/page/fresh-local entry → PASS
        sentence = _sentence_at(start)
        if _self_labels_memory(sentence):
            continue  # reader was told it's from memory → allowed to stand
        # Unverified, unlabeled ID → rewrite the token in place.
        out = out[:start] + _ID_UNVERIFIED + out[end:]
        rewritten.append({
            "claim": tok,
            "reason": "ID not present in this session's live pulls / page fetch and the sentence does not self-label a memory source",
        })

    text = out  # continue page-state work on the id-rewritten text

    # ── (c) Page-state claims ─────────────────────────────────────────
    # Re-split AFTER id rewrites (spans changed). Rewrite unbacked assertions.
    page_sentences = [s for s in _sentences(text) if _asserts_page_state(s)]
    for s in page_sentences:
        checked += 1
        backed = has_page_evidence and page_verified is not False
        if page_verified is False or (page_verified is not None and not backed):
            # A fetch was ATTEMPTED (True→but no evidence, or False→failed) and
            # the claim isn't backed → rewrite the assertion.
            idx = text.find(s)
            if idx != -1:
                text = text[:idx] + _PAGE_UNVERIFIED + text[idx + len(s):]
            rewritten.append({
                "claim": s.strip()[:160],
                "reason": ("landing-page fetch failed this session"
                           if page_verified is False
                           else "no PAGE_FETCH evidence backs this page-state assertion"),
            })
        elif page_verified is None:
            # No page check ran → conservative: FLAG, don't rewrite.
            flagged.append({
                "claim": s.strip()[:160],
                "reason": "page state was not verified this turn (no fetch ran)",
            })
        # else backed by a successful fetch → PASS (counted in checked).

    # ── (b) Material numeric claims — FLAG only, derived-math PASSES ───
    derived_spans = _derived_number_spans(text)

    def _is_derived(pos: int, tok: str) -> bool:
        # Inside a math parenthetical?
        if any(a <= pos < b for a, b in derived_spans):
            return True
        # Adjacent to a math operator within a small window either side?
        lo = max(0, pos - 12)
        hi = min(len(text), pos + len(tok) + 12)
        window = text[lo:hi]
        return bool(_MATH_NEAR_RE.search(window))

    seen_norm = manifest.seen_numbers
    for m in _NUM_TOKEN_RE.finditer(text):
        tok = m.group(0)
        # Only consider "material" numbers: money ($), percent (%), or counts
        # of 2+ digits stated as fact. Skip tiny incidental integers.
        norm = _normalize_num(tok)
        is_material = tok.startswith("$") or tok.endswith("%") or len(norm) >= 2
        if not is_material or not norm:
            continue
        checked += 1
        if _is_derived(m.start(), tok):
            continue  # derived-math → PASS (the $706=45%×$1,569 guard)
        if norm in seen_norm:
            continue  # manifest saw this exact number → PASS
        flagged.append({
            "claim": tok,
            "reason": "material number not traced to a manifest-sourced value (flag only — not rewritten)",
        })

    passed = checked - len(rewritten) - len(flagged)
    if passed < 0:
        passed = 0

    return {
        "text": text,
        "event": {
            "checked": checked,
            "passed": passed,
            "rewritten": rewritten,
            "flagged": flagged,
        },
    }
