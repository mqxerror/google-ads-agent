"""Deterministic near-duplicate detector — Python twin (Epic 16, story 16.4).

The AD-2 pinned algorithm, server side. This is the ONE sanctioned dual
implementation in the engine: it mirrors ``frontend/src/lib/nearDup.ts`` byte-for-
byte in BEHAVIOR and is PARITY-LOCKED against the SAME golden fixture
(``backend/tests/fixtures/near_dup_cases.json``) — both suites assert identical
flag sets on every case (fence F5). If the two implementations ever disagree on a
fixture, CI fails on both sides.

Algorithm (identical to the TS twin):
  1. Normalize: lowercase → strip punctuation/symbols → collapse whitespace →
     drop a fixed stopword list → light suffix fold (ing / ed / s).
  2. Compare: token-SET Jaccard  sim = |A∩B| / |A∪B|;  ALSO flag when the smaller
     set is fully contained in the larger (|A∩B| = min(|A|,|B|)).
  3. Flag a pair when sim ≥ threshold (from the registry — ENGINE.near_dup_
     threshold, never a baked constant) OR the containment rule fires.

Detection is pure + deterministic + zero-I/O (no CLI subprocess, no network) —
FR1.10's spy assert. The ``diversify`` job (below) is the only part that calls the
Creative Director, and only to REGENERATE flagged rows, never to DETECT.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from app.services import creative_specs
from app.services.creative_specs import ANGLES

logger = logging.getLogger(__name__)

# Fixed 30-word English stopword list — the canonical parity list. It ALSO ships
# in the golden fixture; the parity test asserts STOPWORDS == fixture["stopwords"]
# so the two runtimes cannot drift (mirrors nearDup.ts STOPWORDS exactly).
STOPWORDS: Tuple[str, ...] = (
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "were", "with", "you", "your", "we", "our", "my", "i", "but",
)


def suffix_fold(token: str) -> str:
    """Light suffix fold: 'ing'→'', 'ed'→'', trailing 's'→''. Order + length
    guards match the TS twin (nearDup.ts::suffixFold) exactly."""
    if len(token) > 4 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 3 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def normalize_tokens(text: str, stopwords: Set[str]) -> List[str]:
    """Normalize one string to its token list (may be empty). Mirrors the TS
    twin: lowercase → non-alphanumerics to spaces → collapse → drop stopwords →
    suffix fold."""
    lowered = text.lower()
    cleaned_chars = [c if (c.isascii() and (c.isalnum())) else " " for c in lowered]
    cleaned = "".join(cleaned_chars)
    cleaned = " ".join(cleaned.split())  # collapse whitespace + trim
    if not cleaned:
        return []
    return [suffix_fold(t) for t in cleaned.split(" ")
            if t and t not in stopwords]


def _is_near_dup(a: List[str], b: List[str], threshold: float) -> bool:
    A, B = set(a), set(b)
    if not A or not B:
        return False  # never flag empty / all-stopword rows
    inter = len(A & B)
    union = len(A) + len(B) - inter
    jaccard = 0.0 if union == 0 else inter / union
    contained = inter == min(len(A), len(B))
    return jaccard >= threshold or contained


def find_near_dup_pairs(
    texts: Sequence[str],
    *,
    threshold: Optional[float] = None,
    stopwords: Optional[Sequence[str]] = None,
) -> List[List[int]]:
    """Return flagged near-duplicate pairs as ``[i, j]`` (i < j), ascending and
    deterministic. Threshold defaults to the registry value (ENGINE)."""
    thr = threshold if threshold is not None else creative_specs.ENGINE.near_dup_threshold
    stop = {s.lower() for s in (stopwords if stopwords is not None else STOPWORDS)}
    norm = [normalize_tokens(t, stop) for t in texts]
    pairs: List[List[int]] = []
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            if _is_near_dup(norm[i], norm[j], thr):
                pairs.append([i, j])
    return pairs


def flagged_row_indices(
    texts: Sequence[str],
    *,
    threshold: Optional[float] = None,
    stopwords: Optional[Sequence[str]] = None,
) -> Set[int]:
    """The set of row indices participating in ANY near-dup pair (what the
    workbench badges)."""
    flagged: Set[int] = set()
    for i, j in find_near_dup_pairs(texts, threshold=threshold, stopwords=stopwords):
        flagged.add(i)
        flagged.add(j)
    return flagged


# ─────────────────────────────────────────────────────────────────────────────
# Diversify job (FR1.10 / demo step 4). The client flags near-dupes INSTANTLY
# (nearDup.ts, zero LLM). This job REGENERATES the flagged rows toward MISSING
# angles and VERIFIES the regenerated set is below threshold before returning.
# Locked rows are excluded from the regenerate payload (FR1.8).
# ─────────────────────────────────────────────────────────────────────────────

async def diversify(account_id: str, campaign_type: str, *,
                    request: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the client's flagged (non-locked) near-dup rows with rows carrying
    MISSING angles, then verify the new set's pairwise similarity is below
    threshold. Returns ``{rows, flagged_after, below_threshold,
    dismissed_dup_pairs}``. Dismissed pairs (R1 escape hatch) ride through
    untouched so the wizard can persist them in the draft bundle."""
    from app.services.creative_copy import rewrite_row  # lazy — avoids import cycle

    rows: List[Dict[str, str]] = [dict(r) for r in (request.get("rows") or [])
                                  if isinstance(r, dict)]
    locked: Set[int] = {int(i) for i in (request.get("locked_rows") or [])}
    dismissed = request.get("dismissed_dup_pairs") or []

    # A dismissed pair (R1 escape hatch) does not count against the verify.
    dismissed_pairset = {tuple(sorted(p)) for p in dismissed if len(p) == 2}
    flagged_in = [int(i) for i in (request.get("flagged_rows") or [])]
    to_replace = [i for i in flagged_in if i not in locked and 0 <= i < len(rows)]

    # angles already covered by rows we're KEEPING → regenerate toward the gaps.
    kept_angles = {rows[i].get("angle") for i in range(len(rows))
                   if i not in to_replace and isinstance(rows[i], dict)}
    missing = [a for a in ANGLES if a not in kept_angles] or list(ANGLES)

    mi = 0
    for idx in to_replace:
        target_angle = missing[mi % len(missing)]
        mi += 1
        res = await rewrite_row(
            account_id, campaign_type,
            rows=rows, row_index=idx, target_angle=target_angle,
            brief=request.get("brief", ""), final_url=request.get("final_url", ""),
            business_name=request.get("business_name", ""),
        )
        rows = res["rows"]

    texts = [r.get("text", "") for r in rows]
    remaining = find_near_dup_pairs(texts)
    # honor dismissed pairs — a dismissed pair does not count against the verify.
    remaining = [p for p in remaining if tuple(sorted(p)) not in dismissed_pairset]
    flagged_after = sorted({i for p in remaining for i in p})
    return {
        "rows": rows,
        "flagged_after": flagged_after,
        "below_threshold": len(remaining) == 0,
        "dismissed_dup_pairs": dismissed,
    }
