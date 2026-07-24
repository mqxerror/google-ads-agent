"""Chat Orchestration v2 — task ledger / memory recall (Epic 2, §8).

`recall()` gathers prior work relevant to THIS campaign from every durable
source the agent has (workflow / chat specialist reports, scheduled-plan runs,
session summaries, per-role notes), scores each candidate against the caller's
`needs` + the raw query text, classifies its staleness (§8.2), and returns the
top-`limit` entries so the orchestrator can decide reuse-vs-reverify BEFORE it
dispatches fresh specialists.

Design rules:
  - EVERY DB read + file read is guarded in its OWN try/except: a missing table
    on an older DB (or a broken source) yields [] for that source, never a
    crash that kills the other sources.
  - Lazy imports of roles / campaign_memory / scheduler INSIDE functions to
    avoid import cycles (roles → config → … → task_ledger).
  - Pure-read: this module never writes.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Anti-sycophancy: directional-position extraction ──────────────────
# A "position" is a directional RECOMMENDATION already on record (pause/keep/
# add/remove/raise/…). These get surfaced as a distinct PRIOR POSITIONS block so
# the Director must DECLARE a reversal rather than silently flip to please the
# user (the observed 4-flip failure). This set is a SUPERSET of the opposing
# verb PAIRS the orchestrator uses for reversal detection — a position may show
# in the block even when it has no clean opposite (e.g. "launch"), which is fine.
_DIRECTIONAL_VERBS = {
    "pause", "keep", "hold", "add", "remove", "raise", "lower", "increase",
    "decrease", "cut", "scale", "switch", "enable", "disable", "expand",
    "shrink", "kill", "launch", "stop", "start", "drop", "boost", "maintain",
    "reduce", "grow", "hold off", "leave",
}


def _has_directional_verb(text: str) -> bool:
    """True when `text` carries a recommendation verb (word-boundary match)."""
    low = (text or "").lower()
    for v in _DIRECTIONAL_VERBS:
        if re.search(r"\b" + re.escape(v) + r"\b", low):
            return True
    return False


def _findings_from_text(text: str) -> list[dict]:
    """Best-effort: pull finding dicts ({claim, confidence, disconfirmed_by, …})
    out of a specialist report OR a role-notes body — WITHOUT importing the heavy
    workflow_orchestrator (import-cycle safe). Handles both the fenced findings
    JSON the specialist emits AND the {"summary","findings":[…]} blobs writeback
    appends. Never raises. `\\[.*?\\]` closes on the first `]` — finding objects
    carry no `]`, so the first one always closes the array."""
    out: list[dict] = []
    if not text:
        return out
    for m in re.finditer(r'"findings"\s*:\s*(\[.*?\])', text, re.DOTALL):
        try:
            arr = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(arr, list):
            for f in arr:
                if isinstance(f, dict) and f.get("claim"):
                    out.append(f)
    return out


def _position_when(entry: dict) -> str:
    """Human 'when' for a prior position: the created_at date if present, else a
    coarse age string, else 'earlier'."""
    ca = entry.get("created_at")
    if ca:
        s = str(ca).strip().replace(" ", "T", 1).rstrip("Z")
        try:
            return datetime.fromisoformat(s).date().isoformat()
        except (ValueError, TypeError):
            return str(ca)[:10]
    age = entry.get("age_days")
    if isinstance(age, int):
        return "today" if age <= 0 else f"~{age}d ago"
    return "earlier"


def _norm_position(text: str) -> str:
    """Normalized key for de-duplicating positions across sources."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())[:200]


def extract_positions(entries: list[dict]) -> list[dict]:
    """Extract DIRECTIONAL prior positions from recalled findings (piece 1).

    Each recall entry MAY carry structured `findings` (parsed from the report /
    role-notes content before truncation); those give a high-confidence position
    with the stated flip-condition (`disconfirmed_by`). Entries with only prose
    `summary` are scanned sentence-by-sentence for a recommendation verb — a
    CHEAP heuristic, marked `low_confidence=True` and carrying no flip-condition.

    Returns a list of:
        {position, when, flip_condition, confidence, role_id, source,
         low_confidence}
    De-duplicated by normalized position text (structured wins over prose)."""
    positions: list[dict] = []
    seen: set[str] = set()
    for e in entries or []:
        when = _position_when(e)
        role_id = e.get("role_id")
        source = e.get("source")
        # 1) structured findings → high-confidence positions
        for f in (e.get("findings") or []):
            if not isinstance(f, dict):
                continue
            claim = str(f.get("claim") or "").strip()
            if not claim or not _has_directional_verb(claim):
                continue
            key = _norm_position(claim)
            if key in seen:
                continue
            seen.add(key)
            conf = f.get("confidence")
            positions.append({
                "position": claim[:200],
                "when": when,
                "flip_condition": str(f.get("disconfirmed_by") or "").strip()[:200],
                "confidence": conf if isinstance(conf, (int, float)) else None,
                "role_id": role_id,
                "source": source,
                "low_confidence": False,
            })
        # 2) prose fallback — scan the summary for directional sentences
        for sent in re.split(r"(?<=[.!?])\s+|\n+", e.get("summary") or ""):
            sent = sent.strip()
            if len(sent) < 6 or not _has_directional_verb(sent):
                continue
            key = _norm_position(sent)
            if key in seen:
                continue
            seen.add(key)
            positions.append({
                "position": sent[:200],
                "when": when,
                "flip_condition": "",
                "confidence": None,
                "role_id": role_id,
                "source": source,
                "low_confidence": True,
            })
    return positions


# ── §8.2 staleness matrix — the SINGLE source of truth ────────────────
# fresh_days=None means "never goes stale" (a decision/chronicle). "always"
# forces a class to reverify regardless of age (live page/form/tracking state).
STALENESS_MATRIX: dict[str, dict] = {
    "landing_page": {"fresh_days": 0, "always": "reverify"},
    "metrics": {"fresh_days": 1},
    "search_terms": {"fresh_days": 3},
    "specialist": {"fresh_days": 7},
    "decision": {"fresh_days": None},
}

# Trivial stopword set for keyword-overlap scoring — kept tiny + local so the
# module has zero heavy deps.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "to", "of", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "it", "this", "that",
    "these", "those", "i", "you", "we", "they", "my", "our", "your", "their",
    "at", "by", "from", "as", "so", "do", "does", "did", "can", "should",
    "would", "will", "what", "how", "why", "which", "me", "us",
}


def _tokens(text: str) -> set[str]:
    """Lowercased word set minus stopwords (used for keyword overlap)."""
    if not text:
        return set()
    out: set[str] = set()
    word = []
    for ch in text.lower():
        if ch.isalnum():
            word.append(ch)
        elif word:
            w = "".join(word)
            if w not in _STOPWORDS and len(w) > 1:
                out.add(w)
            word = []
    if word:
        w = "".join(word)
        if w not in _STOPWORDS and len(w) > 1:
            out.add(w)
    return out


def _parse_age_days(created_at: Optional[str]) -> Optional[int]:
    """Age in days from an ISO-ish timestamp. Tolerates a trailing 'Z' and a
    space-vs-'T' separator (SQLite datetime('now') writes 'YYYY-MM-DD HH:MM:SS').
    Returns None when unparseable/absent (callers treat None as very old)."""
    if not created_at:
        return None
    s = str(created_at).strip()
    if s.endswith("Z"):
        s = s[:-1]
    s = s.replace(" ", "T", 1)
    try:
        then = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if then.tzinfo is not None:
        then = then.replace(tzinfo=None)
    age = (datetime.now() - then).days
    return age if age >= 0 else 0


def _classify(data_class: str, age_days: Optional[int]) -> tuple[str, str]:
    """(staleness, decision) for a candidate — the §8.2 classifier.

    age_days None → treat as very old for the age-gated classes.
    """
    # Live page/form/tracking state ALWAYS reverifies, regardless of age.
    if data_class in ("landing_page", "page", "form", "tracking"):
        return ("stale", "reverify")
    if data_class in ("decision", "chronicle"):
        return ("fresh", "reuse")

    if data_class in ("specialist", "role_notes"):
        fresh = age_days is not None and age_days < 7
        return ("fresh", "reuse") if fresh else ("stale", "reverify")
    if data_class == "scheduled":
        fresh = age_days is not None and age_days < 3
        return ("fresh", "reuse") if fresh else ("stale", "reverify")
    if data_class == "metrics":
        fresh = age_days is not None and age_days < 1
        return ("fresh", "reuse") if fresh else ("stale", "reverify")
    if data_class == "search_terms":
        fresh = age_days is not None and age_days < 3
        return ("fresh", "reuse") if fresh else ("stale", "reverify")

    # Unknown class → be conservative.
    return ("stale", "reverify")


def _needed_roles(needs: list[str]) -> set[str]:
    """Map each `need` string to the role(s) that own it. A need may be a
    scheduler action-category (mapped through _CATEGORY_ROLE) OR already a
    role_id, in which case it maps to itself."""
    from app.services.scheduler import _CATEGORY_ROLE  # lazy — avoid cycle

    roles: set[str] = set()
    for need in needs or []:
        if not need:
            continue
        mapped = _CATEGORY_ROLE.get(need)
        if mapped:
            roles.add(mapped)
        # A need that is itself a role_id counts as that role.
        roles.add(need)
    return roles


async def recall(
    account_id: str,
    campaign_id: Optional[str],
    needs: list[str],
    query_text: str,
    limit: int = 8,
) -> list[dict]:
    """Gather + rank prior work for THIS campaign.

    Returns up to `limit` dicts, each:
        {source, ref_id, role_id, created_at, age_days, staleness, decision,
         summary}   (summary ≤300 chars)
    """
    candidates: list[dict] = []

    # ── Source 1: specialist reports (workflow + chat-dispatched) ──────
    # Chat-dispatched reports have run_id = turn_id → join chat_turns; workflow
    # reports have run_id = workflow_runs.id. Two queries, deduped by report id.
    try:
        from app.database import get_db

        db = await get_db()
        try:
            seen_ids: set[str] = set()
            for join_sql in (
                "LEFT JOIN workflow_runs wr ON wr.id = workflow_reports.run_id "
                "WHERE workflow_reports.origin IN ('workflow','chat') "
                "AND workflow_reports.phase = 'specialist' AND wr.campaign_id = ?",
                "LEFT JOIN chat_turns ct ON ct.turn_id = workflow_reports.run_id "
                "WHERE workflow_reports.origin IN ('workflow','chat') "
                "AND workflow_reports.phase = 'specialist' AND ct.campaign_id = ?",
            ):
                cur = await db.execute(
                    "SELECT workflow_reports.id AS id, workflow_reports.role_id AS role_id, "
                    "workflow_reports.content AS content, workflow_reports.created_at AS created_at "
                    "FROM workflow_reports " + join_sql,
                    (campaign_id,),
                )
                for r in await cur.fetchall():
                    rid = r["id"]
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    candidates.append({
                        "source": "specialist_report",
                        "ref_id": rid,
                        "role_id": r["role_id"],
                        "created_at": r["created_at"],
                        "data_class": "specialist",
                        "summary": (r["content"] or "")[:300],
                        # parse structured findings from the FULL content BEFORE
                        # truncation so extract_positions sees the flip-conditions
                        "findings": _findings_from_text(r["content"] or ""),
                    })
        finally:
            await db.close()
    except Exception as e:
        logger.debug("recall source workflow_reports failed: %s", e)

    # ── Source 2: scheduled-plan runs for this campaign ────────────────
    try:
        from app.database import get_db
        from app.services.scheduler import _CATEGORY_ROLE

        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT r.id AS id, r.result AS result, r.started_at AS started_at, "
                "p.action_category AS action_category, p.title AS title "
                "FROM scheduled_plan_runs r "
                "JOIN scheduled_plans p ON p.id = r.plan_id "
                "WHERE p.campaign_id = ?",
                (campaign_id,),
            )
            for r in await cur.fetchall():
                summary = (r["result"] or r["title"] or "")[:300]
                candidates.append({
                    "source": "scheduled_plan",
                    "ref_id": r["id"],
                    "role_id": _CATEGORY_ROLE.get(r["action_category"]),
                    "created_at": r["started_at"],
                    "data_class": "scheduled",
                    "summary": summary,
                })
        finally:
            await db.close()
    except Exception as e:
        logger.debug("recall source scheduled_plan_runs failed: %s", e)

    # ── Source 3: session summaries for this campaign ──────────────────
    try:
        from app.database import get_db

        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT id, summary, created_at FROM session_summaries "
                "WHERE campaign_id = ?",
                (campaign_id,),
            )
            for r in await cur.fetchall():
                candidates.append({
                    "source": "session_summary",
                    "ref_id": r["id"],
                    "role_id": "director",
                    "created_at": r["created_at"],
                    "data_class": "specialist",
                    "summary": (r["summary"] or "")[:300],
                })
        finally:
            await db.close()
    except Exception as e:
        logger.debug("recall source session_summaries failed: %s", e)

    # ── Source 4: per-role notes files ─────────────────────────────────
    try:
        from app.services import campaign_memory
        from app.services.roles import list_roles

        for role in [r["id"] for r in list_roles() if r["id"] != "director"]:
            try:
                body = campaign_memory.load_role_notes(account_id, campaign_id, role)
            except Exception:
                body = ""
            if not body:
                continue
            age_days, _ = campaign_memory.role_notes_age_days(body)
            candidates.append({
                "source": "role_notes",
                "ref_id": f"{role}.md",
                "role_id": role,
                "created_at": None,
                "age_days": age_days,          # already resolved from the header
                "data_class": "specialist",
                "summary": body[:300],
                # writeback appends {"summary","findings":[…]} blobs — parse them
                # from the FULL body so prior positions survive the 300-char cut
                "findings": _findings_from_text(body),
            })
    except Exception as e:
        logger.debug("recall source role_notes failed: %s", e)

    # ── Score + classify ──────────────────────────────────────────────
    needed_roles = _needed_roles(needs)
    q_tokens = _tokens(query_text)

    scored: list[dict] = []
    for c in candidates:
        # age: role_notes carry a pre-resolved age; others parse created_at.
        age_days = c.get("age_days")
        if age_days is None and c.get("created_at") is not None:
            age_days = _parse_age_days(c.get("created_at"))

        role_bonus = 3 if (c.get("role_id") and c["role_id"] in needed_roles) else 0
        overlap = len(q_tokens & _tokens(c.get("summary", "")))
        recency = (max(0, 30 - age_days) / 30.0) if age_days is not None else 0.0
        score = role_bonus + overlap + recency

        staleness, decision = _classify(c["data_class"], age_days)
        scored.append({
            "source": c["source"],
            "ref_id": c["ref_id"],
            "role_id": c.get("role_id"),
            "created_at": c.get("created_at"),
            "age_days": age_days,
            "staleness": staleness,
            "decision": decision,
            "summary": c.get("summary", "")[:300],
            # structured findings ride along so extract_positions can pull
            # directional prior positions + their flip-conditions (piece 1)
            "findings": c.get("findings") or [],
            "_score": score,
        })

    scored.sort(key=lambda e: e["_score"], reverse=True)
    top = scored[: max(0, int(limit))]
    for e in top:
        e.pop("_score", None)
    return top
