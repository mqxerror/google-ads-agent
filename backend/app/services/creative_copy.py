"""Creative-copy job store — DB-row job lifecycle (Epic 15, story 15.3).

The draft jobs that used to live in per-router IN-MEMORY dicts (`_dg_draft_jobs`
in demand_gen.py, `_draft_jobs` in pmax.py) are now ``creative_jobs`` DB rows
from birth (fence F6 — job state has no memory home). A backend restart therefore
yields a recoverable ``interrupted`` status (swept at boot by
``database.sweep_interrupted_creative_jobs``), never a 404 — and the persisted
``request_json`` lets the wizard offer a one-click re-run (Honesty Ledger #4:
restart survival is NOT mid-LLM resume; the Claude CLI subprocess dies with the
process).

This module is the STORE ONLY in P1. The unified ``[{text, angle, tier}]``
copy-jobs contract + endpoints arrive in Epic 16 (story 16.1); the storage layer
lands here first so both draft routes stop keeping job state in memory.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.services import creative_specs
from app.services.creative_specs import (
    ANGLES, FIELD_TIER as _FIELD_TIER, TIER_TEXTKEY as _TIER_TEXTKEY, TIERS,
    CampaignSpec,
)

logger = logging.getLogger(__name__)

# Default angle for rows the model returned without a valid one (kept, not
# dropped — the copy is still usable; only the label is missing). "benefit" is
# the safe generic. A row with an unplaceable TIER is dropped (we can't slot it).
# The tier/field lookup maps are taxonomy constants living in creative_specs
# (their single source, AD-2) — imported above, not redefined here.
_DEFAULT_ANGLE = "benefit"


async def create_job(
    kind: str,
    account_id: str,
    campaign_type: str,
    request: Optional[Dict[str, Any]] = None,
    research_hash: Optional[str] = None,
) -> str:
    """Insert a new ``running`` job row and return its id. ``kind`` in
    {'draft', 'rewrite_row', 'diversify'}; ``request`` is persisted verbatim so
    an interrupted job can be re-run one-click. ``research_hash`` records the
    shared page-research object's identity (Epic 18, FR3.3) — the SAME token the
    image path (extract-brief) computes for the same page, so both consumers are
    provably grounded in ONE fetch's object."""
    job_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO creative_jobs (id, kind, account_id, campaign_type, status, "
            "request_json, research_hash) VALUES (?, ?, ?, ?, 'running', ?, ?)",
            (job_id, kind, account_id, campaign_type,
             json.dumps(request) if request is not None else None, research_hash),
        )
        await db.commit()
    finally:
        await db.close()
    return job_id


async def complete_job(job_id: str, result: Dict[str, Any]) -> None:
    """Mark a job ``done`` with its result payload."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE creative_jobs SET status='done', result_json=?, error_message=NULL, "
            "updated_at=datetime('now') WHERE id=?",
            (json.dumps(result), job_id),
        )
        await db.commit()
    finally:
        await db.close()


async def fail_job(job_id: str, message: str) -> None:
    """Mark a job ``error`` with a message."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE creative_jobs SET status='error', error_message=?, "
            "updated_at=datetime('now') WHERE id=?",
            (message, job_id),
        )
        await db.commit()
    finally:
        await db.close()


def _loads(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return the poll-shape dict for a job, or ``None`` if it never existed.

    Shape is backward-compatible with the old in-memory poll (the wizard reads
    ``status`` + ``result`` / ``message`` unchanged):
      - running     → ``{"status": "running"}``
      - done        → ``{"status": "done", "result": {...}}``
      - error       → ``{"status": "error", "message": "..."}``
      - interrupted → ``{"status": "interrupted", "message": ..., "request": {...}}``
        (a restart killed the in-flight job; the wizard offers one-click re-run)
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT kind, campaign_type, status, request_json, result_json, error_message "
            "FROM creative_jobs WHERE id=?",
            (job_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        return None
    status = row["status"]
    out: Dict[str, Any] = {"status": status, "kind": row["kind"],
                           "campaign_type": row["campaign_type"]}
    if status == "done":
        out["result"] = _loads(row["result_json"]) or {}
    elif status == "error":
        out["message"] = row["error_message"] or "draft failed"
    elif status == "interrupted":
        out["message"] = "Draft was interrupted by a backend restart — re-run it."
        out["request"] = _loads(row["request_json"])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Copy-Workbench drafting contract (Epic 16, story 16.1 · AD-2).
#
# ONE service + ONE endpoint pair for every campaign type. Draft/rewrite/diversify
# jobs all return the SAME typed rows ``[{text, angle, tier}]`` (FR1.7). The
# HARD-LIMITS prompt block and per-tier clamps derive from ``CampaignSpec`` (moved
# here from the 14.4 router-level derivation — the routers become thin shims that
# reshape rows back to the legacy ``{headlines, descriptions, ...}`` shape until
# they are deleted at the P2 exit, story 16.8).
#
# Angle/tier vocabulary is imported from the registry (creative_specs.ANGLES /
# .TIERS) — never a literal here — so the taxonomy has one source (AD-2).
# ─────────────────────────────────────────────────────────────────────────────


def _tier_max_chars(spec: CampaignSpec, tier: str) -> int:
    """The char cap governing ``tier`` for this campaign type, from the spec.
    Every number comes from the registry (no literals — CI guard, fence F1)."""
    if tier == "short_description" and spec.short_description is not None:
        return spec.short_description.max_chars
    key = _TIER_TEXTKEY.get(tier)
    fs = spec.text.get(key) if key else None
    if fs is not None:
        return fs.max_chars
    # Unreachable in practice (all tiers have a backing field); fall back to the
    # longest text cap in the spec rather than bake a literal.
    return max(f.max_chars for f in spec.text.values())


def _requested_tiers(spec: CampaignSpec) -> List[str]:
    """The tiers this campaign type actually drafts — those whose backing
    spec.text field exists, plus short_description when the type carries the soft
    short-desc rule (PMax)."""
    tiers = [t for t in ("headline", "long_headline", "description")
             if _TIER_TEXTKEY[t] in spec.text]
    if spec.short_description is not None:
        tiers.append("short_description")
    return tiers


def parse_rows(parsed: Any, spec: CampaignSpec) -> List[Dict[str, str]]:
    """Normalize a drafter's JSON into clean ``[{text, angle, tier}]`` rows.

    Accepts BOTH shapes (backward-compatible per the strangler rule):
      * NEW  — ``{"rows": [{"text", "angle", "tier"}, ...]}``
      * LEGACY — ``{"headlines": [...], "long_headlines": [...],
        "descriptions": [...]}`` (a bare-string-list draft; each string becomes a
        row with its field's tier and the default angle).

    A row is DROPPED (with a logged warning, never a crash — FR1.7 AC) when its
    text is empty/non-string, its tier is not placeable, or it exceeds the tier's
    char cap (mirrors the legacy over-length drop). An unknown angle is coerced to
    the default rather than dropped (the copy is still usable)."""
    rows: List[Dict[str, str]] = []
    if not isinstance(parsed, dict):
        return rows

    raw_rows = parsed.get("rows")
    if isinstance(raw_rows, list):
        candidates = raw_rows
    else:
        # Legacy shape: reconstruct rows from the bare string lists.
        candidates = []
        for field, tier in _FIELD_TIER.items():
            for text in parsed.get(field) or []:
                candidates.append({"text": text, "angle": _DEFAULT_ANGLE, "tier": tier})

    for raw in candidates:
        if not isinstance(raw, dict):
            logger.warning("copy draft: dropped a non-object row %r", raw)
            continue
        text = raw.get("text")
        text = text.strip() if isinstance(text, str) else ""
        tier = raw.get("tier")
        if not text:
            logger.warning("copy draft: dropped an empty-text row %r", raw)
            continue
        if tier not in TIERS or _TIER_TEXTKEY.get(tier) not in spec.text and tier != "short_description":
            logger.warning("copy draft: dropped a row with unplaceable tier %r", tier)
            continue
        if tier == "short_description" and spec.short_description is None:
            # This type has no short-desc slot; treat it as a description.
            tier = "description"
        if len(text) > _tier_max_chars(spec, tier):
            logger.warning("copy draft: dropped an over-length %s row (%d chars)", tier, len(text))
            continue
        angle = raw.get("angle")
        if angle not in ANGLES:
            angle = _DEFAULT_ANGLE
        rows.append({"text": text, "angle": angle, "tier": tier})
    return rows


def build_draft_prompt(
    campaign_type: str,
    *,
    brief: str = "",
    final_url: str = "",
    business_name: str = "",
    campaign_name: str = "",
    spec: Optional[CampaignSpec] = None,
    claim_seeds: Optional[List[str]] = None,
) -> str:
    """The unified Creative Director draft prompt for any campaign type (FR1.7,
    FR1.13). The HARD-LIMITS block, the deliberate-length note, and the requested
    tiers all derive from ``spec`` so the prompt can never promise a number the
    validator rejects. Every campaign type gets DG's full policy block (FR1.13
    parity) and drafts a ``business_name``.

    ``claim_seeds`` — GATED page claims from the shared research object (Epic 18,
    FR3.3/FR3.4). When present they ground the copy in what the page ALREADY says
    (already checked against pinned facts), never inventing offers."""
    spec = spec or creative_specs.get(campaign_type)
    tiers = _requested_tiers(spec)
    tier_menu = " | ".join(tiers)
    angle_menu = " | ".join(ANGLES)
    per_tier = "; ".join(
        f"{t}: {spec.text[_TIER_TEXTKEY[t]].min_count}-{spec.text[_TIER_TEXTKEY[t]].max_count} rows"
        for t in tiers if _TIER_TEXTKEY[t] in spec.text
    )
    label = "Performance Max" if campaign_type == "pmax" else (
        "Responsive Display" if campaign_type == "rda" else "Demand Gen")
    seed_block = ""
    if claim_seeds:
        seed_lines = "\n".join(f"  - {c}" for c in claim_seeds)
        seed_block = (
            "\nPAGE CLAIM SEEDS (already verified against pinned facts — lean on "
            "THESE, don't invent new offers/numbers):\n" + seed_lines + "\n"
        )
    return (
        f"Draft Google {label} ad copy for this campaign. First fetch the landing "
        "page to ground every claim — never invent offers or numbers.\n\n"
        f"Landing page: {final_url or '(none given — use the brief only)'}\n"
        f"Business name (brand): {business_name or '-'}\n"
        f"Campaign name: {campaign_name or '-'}\n"
        f"Brief from the operator: {brief or '(none — derive from the landing page)'}\n"
        f"{seed_block}\n"
        f"{creative_specs.hard_limits_prompt(spec)}\n"
        f"{creative_specs.deliberate_length_note(spec, 'headlines')}\n"
        "POLICY (Google disapproves violations): NO prices or discounts in the "
        "copy · NO citizenship or guaranteed-approval promises · avoid the symbols "
        "~ | + (flagged as gimmicky). No em dashes. No third-party brand names.\n"
        "Give each row an ANGLE (its persuasion strategy) and a TIER (which slot "
        f"it fills). Vary the angles for coverage.\n"
        f"Valid angles: {angle_menu}.\n"
        f"Valid tiers: {tier_menu}.\n"
        f"Draft {per_tier}.\n"
        "business_name is the advertiser's SHORT brand label shown on the ad — "
        f"keep it the real brand (≤{spec.business_name_max} chars), not a slogan.\n\n"
        "Respond with ONLY this JSON, no prose:\n"
        '{"business_name": "<brand, short>", "rows": [{"text": "<copy>", '
        '"angle": "<one valid angle>", "tier": "<one valid tier>"}, ...]}'
    )


async def _stream_draft(account_id: str, prompt: str) -> str:
    """Run the Creative Director role over ``prompt`` (analysis-only; web fetch
    allowed, no Google Ads tools) and return the concatenated text."""
    from app.services.agent import stream_agent_response

    parts: List[str] = []
    async for ev in stream_agent_response(
        user_message=prompt,
        account_id=account_id,
        active_role="creative_director",
        tool_allowlist=[],
    ):
        if ev.get("type") in ("text", "text_delta"):
            parts.append(ev.get("content", ""))
    return "".join(parts)


def _extract_json(raw: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        return None


def _business_name(parsed: dict, spec: CampaignSpec, fallback: str = "") -> str:
    bn = str(parsed.get("business_name") or "").strip() or (fallback or "").strip()
    return bn[: spec.business_name_max]


async def _research_claim_seeds(account_id: str, research_hash: Optional[str],
                                campaign_id: Optional[str]) -> List[str]:
    """Load the GATED claim seeds from the shared research object (by hash), the
    SAME brand kit the scrape produced (FR3.3 identity). Returns [] when no
    research is attached — the copy path stays fully backward compatible.

    The seeds are already gated against pinned facts at scrape time (FR3.4); this
    re-gates defensively so a stale kit can never resurrect a since-banned claim."""
    if not research_hash:
        return []
    from app.services import brand_kit

    kit = await brand_kit.load_brand_kit_by_hash(account_id, research_hash)
    if not kit:
        return []
    raw = kit.get("gated_claims") or kit.get("claims") or []
    kept, _dropped = brand_kit.filter_claim_seeds(
        [str(c) for c in raw], account_id, campaign_id)
    return kept


async def draft_copy(
    account_id: str,
    campaign_type: str,
    *,
    brief: str = "",
    final_url: str = "",
    business_name: str = "",
    campaign_name: str = "",
    research_hash: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Draft a full angle-tagged copy set. Returns ``{"rows": [...],
    "business_name": str}`` (the P2 contract). Raises no count errors — the
    contract returns whatever the drafter produced; count/coverage is the
    wizard's + the create validator's concern.

    When a ``research_hash`` is supplied, the drafter is grounded in the SAME
    page-research object the image path received (FR3.3): its GATED claim seeds
    are injected as the only page claims the copy may lean on (FR3.4)."""
    spec = creative_specs.get(campaign_type)
    claim_seeds = await _research_claim_seeds(account_id, research_hash, campaign_id)
    prompt = build_draft_prompt(
        campaign_type, brief=brief, final_url=final_url,
        business_name=business_name, campaign_name=campaign_name, spec=spec,
        claim_seeds=claim_seeds,
    )
    raw = await _stream_draft(account_id, prompt)
    parsed = _extract_json(raw)
    if parsed is None:
        raise ValueError("Creative Director returned no parseable JSON — try again.")
    rows = parse_rows(parsed, spec)
    return {"rows": rows, "business_name": _business_name(parsed, spec, business_name)}


async def rewrite_row(
    account_id: str,
    campaign_type: str,
    *,
    rows: List[Dict[str, str]],
    row_index: int,
    target_angle: str,
    brief: str = "",
    final_url: str = "",
    business_name: str = "",
) -> Dict[str, Any]:
    """Rewrite EXACTLY one row toward ``target_angle`` (FR1.9). Returns the full
    row set with only row ``row_index`` replaced — every other row byte-identical.
    ``rows`` is the client's current set (each ``{text, angle, tier}``)."""
    spec = creative_specs.get(campaign_type)
    if not (0 <= row_index < len(rows)):
        raise ValueError(f"row_index {row_index} out of range (have {len(rows)} rows)")
    if target_angle not in ANGLES:
        target_angle = _DEFAULT_ANGLE
    target = rows[row_index]
    tier = target.get("tier") if isinstance(target, dict) else "headline"
    if tier not in TIERS:
        tier = "headline"
    max_chars = _tier_max_chars(spec, tier)
    others = [r.get("text", "") for i, r in enumerate(rows) if i != row_index and isinstance(r, dict)]
    prompt = (
        f"Rewrite ONE Google {campaign_type} ad {tier.replace('_', ' ')} toward the "
        f"'{target_angle}' angle. Ground it in the landing page — no invented "
        "offers/numbers, no prices, no guaranteed-approval claims, no em dashes, "
        "no third-party brand names.\n\n"
        f"Landing page: {final_url or '(none — use the brief)'}\n"
        f"Business name: {business_name or '-'}\n"
        f"Brief: {brief or '(none)'}\n"
        f"Current text to replace: {target.get('text', '') if isinstance(target, dict) else ''!r}\n"
        f"Avoid duplicating these existing rows: {others}\n"
        f"HARD LIMIT: ≤{max_chars} chars.\n\n"
        'Respond with ONLY this JSON: {"text": "<new copy>"}'
    )
    raw = await _stream_draft(account_id, prompt)
    parsed = _extract_json(raw) or {}
    new_text = str(parsed.get("text") or "").strip()
    out = [dict(r) for r in rows]
    if new_text and len(new_text) <= max_chars:
        out[row_index] = {"text": new_text, "angle": target_angle, "tier": tier}
    else:
        # Keep the tier, adopt the target angle even if the model over-ran (the
        # UI clamps display); never crash the apply path.
        logger.warning("rewrite_row: model returned empty/over-length text; keeping original text")
        out[row_index] = {"text": target.get("text", "") if isinstance(target, dict) else "",
                          "angle": target_angle, "tier": tier}
    return {"rows": out, "row_index": row_index}


# ── job runner (background task target for the copy-jobs endpoints) ───────────

async def run_copy_job(job_id: str, kind: str, account_id: str,
                       campaign_type: str, request: Dict[str, Any]) -> None:
    """Execute a copy job (draft | rewrite_row | diversify) and persist its
    result to the ``creative_jobs`` row. Never raises — failures are recorded as
    the job's error status (the poller surfaces them)."""
    try:
        if kind == "draft":
            result = await draft_copy(
                account_id, campaign_type,
                brief=request.get("brief", ""), final_url=request.get("final_url", ""),
                business_name=request.get("business_name", ""),
                campaign_name=request.get("campaign_name", ""),
                research_hash=request.get("research_hash"),
                campaign_id=request.get("campaign_id"),
            )
        elif kind == "rewrite_row":
            result = await rewrite_row(
                account_id, campaign_type,
                rows=request.get("rows") or [],
                row_index=int(request.get("row_index", -1)),
                target_angle=str(request.get("target_angle") or _DEFAULT_ANGLE),
                brief=request.get("brief", ""), final_url=request.get("final_url", ""),
                business_name=request.get("business_name", ""),
            )
        elif kind == "diversify":
            from app.services import near_dup
            result = await near_dup.diversify(
                account_id, campaign_type, request=request,
            )
        else:
            raise ValueError(f"unknown copy-job kind {kind!r}")
        await complete_job(job_id, result)
    except Exception as e:  # noqa: BLE001 — record, never crash the task
        logger.exception("copy job %s (%s) failed", job_id, kind)
        await fail_job(job_id, str(e)[:300])


def rows_to_legacy(rows: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Group typed rows back into the legacy ``{headlines, long_headlines,
    descriptions}`` bare-string shape (short_description folds into descriptions).
    Order is preserved. Used by the P1 draft-route shims until 16.8 deletes them."""
    out: Dict[str, List[str]] = {"headlines": [], "long_headlines": [], "descriptions": []}
    tier_field = {"headline": "headlines", "long_headline": "long_headlines",
                  "description": "descriptions", "short_description": "descriptions"}
    for r in rows:
        field = tier_field.get(r.get("tier", ""))
        if field:
            out[field].append(r.get("text", ""))
    return out
