"""Findings → approvable actions contract (Story 13.3).

The homepage is a FIX LIST, not prose. Story 13.2 persists the latest account
audit (`account_report_store`) as a list of findings and computes always-fresh
`fast_signals`; each of those carries — by contract —::

    finding = {title, campaign_ids[], evidence, dollar_impact_wk,
               action_category, recommended_action}
    signal  = {type, campaign_id, campaign_name, title, detail,
               action_category, dollar_impact_wk, ...}

This module turns each one into a concrete, *approvable* ACTION and routes the
operator's decision through the EXISTING plan/approval + scope-guard machinery.
It never mutates Google Ads directly — every write goes through a Scheduled
Plan (`routers/plans.create_plan` → `scheduler`), so `CampaignScopeMiddleware`,
the cost cap and resumable sessions all apply for free, and the approval gate
(`scheduler.infer_mode`) decides gated-vs-auto by the SAME taxonomy the
scheduler already understands (budget|bids|status|geo → gated;
search_terms|audit|report|other → auto).

Three decisions, matching the brief's [Approve] [Approve once] [Deny]:

  • approve       — create a Scheduled Plan via the normal lifecycle. Gated
                    categories land in `awaiting_approval` (execute later via
                    `scheduler.approve_plan`); auto categories are scheduled and
                    fired now through the guarded path (`scheduler.run_now`).
  • approve_once  — one-shot: a `once` plan with run_at=now, then fired
                    immediately through the SAME guarded path. Gated categories
                    still park for sign-off first (never a silent money write).
  • deny          — persist a dismissal keyed by the finding's stable content
                    hash so it stops surfacing (excluded from the recoverable
                    total, retained for audit) until a re-audit genuinely
                    changes the finding's content.

Advisory findings (no safe automatable mutation — e.g. "rewrite the landing
page", a tracking-gap flag, an unquantified `audit`/`report`/`other` item, or
any finding with no campaign binding) are marked NON-actionable: they surface
as info with no Approve button. We never fabricate a mutation.

Decision state persists in the V20 `finding_actions` table (one row per
account_id + finding_key), carrying the resulting plan_id so the homepage
reflects approved / denied / executed status.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from app.database import get_db
from app.services import account_report_store, fast_signals, scheduler

logger = logging.getLogger(__name__)


# ── Taxonomy → actionability ──────────────────────────────────────────
# The scheduler taxonomy is the source of truth (do NOT invent a new one).
# A category is *directly automatable* only if a concrete, reversible,
# scope-guarded mutation exists for it. audit/report/other are analysis or
# open-ended work → advisory (surface as info, no Approve). budget/bids/status/
# geo/negative_keyword/search_terms map to concrete campaign mutations.
_KNOWN_CATEGORIES = {
    "budget", "bids", "status", "geo",
    "negative_keyword", "search_terms", "audit", "report", "other",
}
# Categories with a concrete, safe, reversible mutation the agent can perform.
_ACTIONABLE_CATEGORIES = {
    "budget", "bids", "status", "geo", "negative_keyword", "search_terms",
}
# Advisory-only: analysis / investigative / open-ended → info, never a write.
_ADVISORY_CATEGORIES = {"audit", "report", "other"}

# Human-readable mutation templates per category (the "what it would do"). These
# describe the SHAPE of the change; the agent computes exact numbers at run time
# (approval mode inspects state and produces the concrete diff before sign-off).
_MUTATION_TEMPLATE = {
    "budget":           "Adjust the campaign daily budget",
    "bids":             "Adjust the campaign bids / target CPA",
    "status":           "Change the campaign status (pause / enable)",
    "geo":              "Adjust geographic targeting",
    "negative_keyword": "Add negative keyword(s) to stop wasted spend",
    "search_terms":     "Clean up search terms (add negatives for 0-conversion terms)",
}


def _norm_category(cat: Optional[str]) -> str:
    c = (cat or "other").strip().lower()
    return c if c in _KNOWN_CATEGORIES else "other"


# ── Stable finding key ────────────────────────────────────────────────


def _finding_key(source: str, category: str, campaign_ids: list[str], title: str) -> str:
    """A content hash that is STABLE across re-audits for the same underlying
    issue. Deliberately excludes the $-impact (which drifts run to run) and the
    evidence prose (LLM-worded); keys on source + category + sorted campaign
    ids + a normalized title so a denied finding stays denied until its
    *identity* changes, not merely its wording or estimate."""
    norm_title = " ".join((title or "").lower().split())
    basis = "|".join([
        source,
        category,
        ",".join(sorted(str(c) for c in campaign_ids if c)),
        norm_title,
    ])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:20]


# ── Normalize a raw finding / signal into a common intermediate ───────


def _campaign_ids_of(item: dict) -> list[str]:
    """Findings carry `campaign_ids` (list); fast-signals carry a single
    `campaign_id`. Normalize to a de-duped list of non-empty strings."""
    ids: list[str] = []
    raw = item.get("campaign_ids")
    if isinstance(raw, list):
        ids = [str(c) for c in raw if c]
    single = item.get("campaign_id")
    if single and str(single) not in ids:
        ids.append(str(single))
    # de-dup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in ids:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _detail_of(item: dict) -> str:
    """The instruction/evidence text a finding carries. Findings use
    `recommended_action` / `evidence`; signals use `detail`."""
    for k in ("recommended_action", "detail", "evidence"):
        v = item.get(k)
        if v:
            return str(v).strip()
    return ""


def propose_action(item: dict, source: str = "finding") -> dict:
    """Turn ONE finding or fast-signal into a concrete proposed ACTION.

    Returns a dict describing what the action would do, its approval gating,
    its $-impact snapshot, a human-readable preview, and — crucially — whether
    it is `actionable` at all. An advisory item (no safe automatable mutation)
    comes back with `actionable=False` and an `advisory_reason`; the homepage
    renders it as info with no Approve button. No mutation is ever fabricated.
    """
    category = _norm_category(item.get("action_category"))
    campaign_ids = _campaign_ids_of(item)
    title = (item.get("title") or "").strip() or "Untitled finding"
    detail = _detail_of(item)
    impact = item.get("dollar_impact_wk")
    try:
        impact = float(impact) if impact is not None else None
    except (TypeError, ValueError):
        impact = None

    key = _finding_key(source, category, campaign_ids, title)
    mode = scheduler.infer_mode(category)  # 'approval' (gated) | 'auto'

    # Actionable iff: a concrete mutation template exists for the category AND
    # we have at least one campaign to target. Otherwise advisory (info only).
    advisory_reason: Optional[str] = None
    actionable = category in _ACTIONABLE_CATEGORIES
    if actionable and not campaign_ids:
        actionable = False
        advisory_reason = "No target campaign on this finding — cannot scope a safe write."
    if not actionable and advisory_reason is None:
        if category in _ADVISORY_CATEGORIES:
            advisory_reason = (
                "Advisory finding — analysis / open-ended work with no single "
                "reversible mutation to automate."
            )
        else:
            advisory_reason = "No safe automatable mutation for this finding."

    mutation = _MUTATION_TEMPLATE.get(category) if actionable else None

    # Human-readable diff/preview string for the fix-list row. For an
    # actionable item it names the mutation + campaigns + the recommendation;
    # for an advisory item it's just the recommendation (surfaced as info).
    if actionable:
        camp_txt = ", ".join(campaign_ids)
        preview = f"{mutation} on campaign {camp_txt}"
        if detail:
            preview += f" — {detail}"
    else:
        preview = detail or title

    return {
        "finding_key": key,
        "source": source,
        "title": title,
        "detail": detail,
        "action_category": category,
        "campaign_ids": campaign_ids,
        "campaign_name": item.get("campaign_name"),
        "dollar_impact_wk": impact,
        "actionable": actionable,
        "advisory_reason": advisory_reason,
        "mode": mode,                       # gating: approval (gated) | auto
        "requires_approval": mode == "approval",
        "mutation": mutation,               # None for advisory
        "diff_preview": preview,
    }


# ── Decision-state persistence (V20 finding_actions) ──────────────────


async def _get_state(account_id: str, finding_key: str) -> Optional[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT account_id, finding_key, source, status, plan_id, "
            "action_category, dollar_impact_wk, updated_at "
            "FROM finding_actions WHERE account_id = ? AND finding_key = ?",
            (account_id, finding_key),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _get_states(account_id: str) -> dict[str, dict]:
    """All decision rows for an account, keyed by finding_key (one query)."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT finding_key, status, plan_id, updated_at "
            "FROM finding_actions WHERE account_id = ?",
            (account_id,),
        )
        return {r["finding_key"]: dict(r) for r in await cur.fetchall()}
    finally:
        await db.close()


async def _upsert_state(
    account_id: str,
    proposed: dict,
    status: str,
    plan_id: Optional[str] = None,
) -> None:
    """Record the operator's decision on a finding. UPSERT on
    (account_id, finding_key) so re-deciding overwrites in place."""
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO finding_actions
                (account_id, finding_key, source, title, action_category,
                 status, plan_id, dollar_impact_wk, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(account_id, finding_key) DO UPDATE SET
                status           = excluded.status,
                plan_id          = COALESCE(excluded.plan_id, finding_actions.plan_id),
                title            = excluded.title,
                action_category  = excluded.action_category,
                dollar_impact_wk = excluded.dollar_impact_wk,
                updated_at       = datetime('now')
            """,
            (
                account_id,
                proposed["finding_key"],
                proposed.get("source", "finding"),
                proposed.get("title"),
                proposed.get("action_category"),
                status,
                plan_id,
                proposed.get("dollar_impact_wk"),
            ),
        )
        await db.commit()
    finally:
        await db.close()


# ── Read model: the account's actionable items + their decision state ─


async def _raw_items(account_id: str) -> list[tuple[dict, str]]:
    """Gather every finding + fast-signal for the account as (item, source)."""
    items: list[tuple[dict, str]] = []
    report = await account_report_store.get_latest(account_id)
    for f in report.get("findings") or []:
        if isinstance(f, dict):
            items.append((f, "finding"))
    sig = await fast_signals.get_signals(account_id)
    buckets = (sig.get("signals") or {})
    for bucket in buckets.values():
        if isinstance(bucket, list):
            for s in bucket:
                if isinstance(s, dict):
                    items.append((s, "signal"))
    return items


async def list_actions(account_id: str, include_denied: bool = False) -> dict:
    """The homepage fix-list payload: every finding/signal as a proposed
    action, annotated with its current decision state.

    Denied items are suppressed by default (they don't reappear until a
    re-audit changes their content → new finding_key). The recoverable total
    counts only actionable, non-denied items with a derivable $-impact.
    """
    states = await _get_states(account_id)
    raw = await _raw_items(account_id)

    actions: list[dict] = []
    seen_keys: set[str] = set()
    recoverable = 0.0
    for item, source in raw:
        proposed = propose_action(item, source=source)
        key = proposed["finding_key"]
        # A finding and a signal could collide on key only if identical; keep
        # the first (findings are appended first, deeper signal).
        if key in seen_keys:
            continue
        seen_keys.add(key)

        st = states.get(key)
        status = st["status"] if st else "proposed"
        proposed["status"] = status
        proposed["plan_id"] = st.get("plan_id") if st else None

        if status == "denied" and not include_denied:
            continue

        if (
            proposed["actionable"]
            and status not in ("denied",)
            and proposed["dollar_impact_wk"]
        ):
            recoverable += proposed["dollar_impact_wk"]

        actions.append(proposed)

    # Money-ranked: highest $-impact first; unquantified/advisory sink below.
    actions.sort(key=lambda a: -(a.get("dollar_impact_wk") or 0.0))

    actionable_n = sum(1 for a in actions if a["actionable"])
    return {
        "account_id": account_id,
        "actions": actions,
        "count": len(actions),
        "actionable_count": actionable_n,
        "advisory_count": len(actions) - actionable_n,
        "total_recoverable_wk": round(recoverable, 2),
    }


# ── Decision handlers (approve / approve_once / deny) ──────────────────


async def _resolve_proposed(account_id: str, finding_key: str) -> Optional[dict]:
    """Re-derive the proposed action for `finding_key` from live findings/
    signals (so we act on the CURRENT audit, not a stale client payload)."""
    for item, source in await _raw_items(account_id):
        proposed = propose_action(item, source=source)
        if proposed["finding_key"] == finding_key:
            return proposed
    return None


def _plan_body(account_id: str, proposed: dict, *, once: bool):
    """Build the PlanCreate body for a finding's action. Imported lazily to
    avoid a router↔service import cycle at module load."""
    from app.routers.plans import PlanCreate
    from datetime import datetime, timezone

    campaign_id = proposed["campaign_ids"][0] if proposed["campaign_ids"] else None
    # The instruction the agent will carry out — the recommendation, scoped to
    # the finding's category. Concrete numbers are resolved by the agent at run
    # time (approval mode inspects state and produces the exact diff first).
    action_detail = proposed.get("detail") or proposed.get("diff_preview") or proposed["title"]
    run_at = None
    if once:
        run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return PlanCreate(
        account_id=account_id,
        campaign_id=campaign_id,
        campaign_name=proposed.get("campaign_name"),
        title=proposed["title"][:120],
        action_detail=action_detail,
        context_snippet=f"[Home fix-list] {proposed.get('diff_preview') or ''}"[:1000],
        action_category=proposed["action_category"],
        # mode omitted → create_plan infers it via scheduler.infer_mode (gated
        # vs auto by category). We never override the gate.
        schedule_type="once",
        run_at=run_at,
        created_by="user",
    )


async def approve(
    account_id: str,
    finding_key: str,
    *,
    once: bool = False,
) -> dict:
    """[Approve] / [Approve once] — route the finding into the plan lifecycle.

    Creates a Scheduled Plan (via `routers/plans.create_plan`, which infers the
    approval gate from the category). Then:
      - gated categories (budget/bids/status/geo): the plan is created and, when
        run, executes analysis-only first and parks `awaiting_approval` — the
        operator signs off from the Plans UI (`scheduler.approve_plan`). We DO
        NOT auto-fire a gated action here (never a silent money write).
      - auto categories (search_terms/etc): fire immediately through the guarded
        path — `scheduler.run_now`, which runs `stream_agent_response` with the
        campaign binding so `CampaignScopeMiddleware` applies.
    `once` produces a one-time plan with run_at=now (same gates); repeated
    (non-once) approve schedules per the plan's own logic.
    """
    proposed = await _resolve_proposed(account_id, finding_key)
    if proposed is None:
        return {"error": "finding not found (re-audit may have changed it)", "finding_key": finding_key}
    if not proposed["actionable"]:
        return {
            "error": "advisory finding has no automatable action",
            "finding_key": finding_key,
            "advisory_reason": proposed["advisory_reason"],
        }

    from app.routers import plans as plans_router

    body = _plan_body(account_id, proposed, once=once)
    plan = await plans_router.create_plan(body)
    plan_id = plan.get("id")

    decision_status = "approved_once" if once else "approved"
    fired: Optional[dict] = None
    if proposed["mode"] == "auto" and plan_id:
        # Safe lane → execute now through the scope-guarded plan path.
        fired = await scheduler.run_now(plan_id)

    await _upsert_state(account_id, proposed, decision_status, plan_id=plan_id)

    return {
        "status": decision_status,
        "finding_key": finding_key,
        "plan_id": plan_id,
        "mode": proposed["mode"],
        "gated": proposed["mode"] == "approval",
        "requires_approval": proposed["mode"] == "approval",
        "fired": fired is not None,
        "run": fired,
        "plan": plan,
    }


async def deny(account_id: str, finding_key: str) -> dict:
    """[Deny] — dismiss a finding so it stops surfacing on the homepage.

    Persists a `denied` decision keyed by the finding's stable content hash.
    The finding is excluded from `list_actions` (and the recoverable total)
    until a re-audit produces a materially different finding (→ a new
    finding_key). Retained in the table for audit. We snapshot the title/
    category even if the finding is no longer live so denial is idempotent.
    """
    proposed = await _resolve_proposed(account_id, finding_key)
    if proposed is None:
        # Finding no longer live (already gone from the audit) — still record a
        # tombstone so any lingering client row is suppressed. Minimal snapshot.
        proposed = {
            "finding_key": finding_key, "source": "finding", "title": None,
            "action_category": None, "dollar_impact_wk": None,
        }
    await _upsert_state(account_id, proposed, "denied")
    return {"status": "denied", "finding_key": finding_key}


async def decide(account_id: str, finding_key: str, decision: str) -> dict:
    """Single entry point for the three fix-list buttons.

    decision ∈ {approve, approve_once, deny}.
    """
    d = (decision or "").strip().lower()
    if d == "approve":
        return await approve(account_id, finding_key, once=False)
    if d == "approve_once":
        return await approve(account_id, finding_key, once=True)
    if d == "deny":
        return await deny(account_id, finding_key)
    return {"error": f"unknown decision {decision!r} (want approve|approve_once|deny)"}
