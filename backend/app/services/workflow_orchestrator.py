"""Director-orchestrated multi-agent workflow.

Turns the user's manual ritual — fire daily/weekly/adcopy templates, gather
three reports, then manually team-audit them for conflicts — into one
deterministic, streamed workflow:

    Phase 0  PRE-FETCH   one batched sync_account() into local SQLite so every
                          specialist reads local data, not the live Google Ads
                          API. This is the rate-limit firewall.
    Phase 1  PLAN        the Director (Opus) deeply prepares the task: which
                          specialists, each one's tailored prompt, its tool
                          allowlist, and model. Output is structured JSON.
    Phase 2  SPECIALISTS each planned specialist runs in parallel (capped),
                          tool-scoped, producing a report.
    Phase 3  DEBATE      each specialist reads peers' reports and surfaces
                          conflicts / challenges (the "team audit").
    Phase 4  SYNTHESIS   the Marketing Director reconciles everything into one
                          final action plan.

The whole thing is a plain async control loop around the EXISTING
stream_agent_response — no new SDK, no migration. Per-agent tool scoping is
enforced physically by CampaignScopeMiddleware (LANGAR_AGENT_TOOL_ALLOWLIST).
A per-run budget caps spend; the loop degrades to synthesis-with-what-we-have
rather than hard-failing.

ACCOUNT MODE (Story 13.1): when `campaign_id is None` (and no campaign_name),
the same phases run account-wide — the Director plans ACROSS active campaigns
(roster from the `campaigns` table via campaigns_repo, capped by
WORKFLOW_MAX_CAMPAIGNS, highest recent spend first), each specialist pass is
bound to the ONE concrete campaign it audits (role notes / campaign memory /
scope middleware stay campaign-bound per pass), debate hunts CROSS-campaign
conflicts, and synthesis emits ONE ranked account report with structured
findings JSON ($-impact/wk per finding + "Total recoverable" rollup).
Account runs are analysis-only: every pass gets tools=[] — no Google Ads
write/mutate surface. Campaigns excluded by the cap are always NAMED in the
report (scope footer + account_report.campaigns_excluded) — no silent
truncation. Story 13.2 persists the report; 13.3 turns findings into
approvable actions — both consume the `account_rollup` report row / the
`account_report` field on workflow_done.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import date, timedelta
from typing import Any, AsyncIterator, Optional

from app.config import settings
from app.database import get_db
from app.services.agent import stream_agent_response
from app.services.roles import list_roles, get_role

logger = logging.getLogger(__name__)

# Concurrency cap for parallel specialist / debate agents. Low on purpose:
# each agent is its own Claude CLI subprocess (~256MB) AND the whole point of
# the pre-fetch is to keep Google API pressure down — staggering helps further.
_MAX_PARALLEL = 2

# Default per-run budget (USD). Overridable per call. The run stops launching
# new agents once spend crosses this and proceeds straight to synthesis.
# Local tool — Opus-heavy multi-agent runs can be expensive; keep the ceiling
# generous so a deep audit never gets cut off mid-flow.
_DEFAULT_BUDGET = float(getattr(settings, "WORKFLOW_MAX_COST_USD", 0) or 50.0)

# Pre-fetch lookback window (days) for the one batched sync.
_PREFETCH_DAYS = 30

# Timeframe presets. Each maps to (a) the pre-fetch lookback in days — CAPPED
# so long periods don't hammer the Google Ads API (the local store accumulates
# more history over time anyway), and (b) the comparison framing the Director
# bakes into every specialist's task. `cap` is the hard sync ceiling.
_PREFETCH_CAP = 180
_TIMEFRAMES: dict[str, dict] = {
    "daily":     {"lookback": 14,  "window": "yesterday vs the 7-day average"},
    "weekly":    {"lookback": 21,  "window": "the last 7 days vs the prior 7 days"},
    "monthly":   {"lookback": 70,  "window": "the last 30 days vs the prior 30 days"},
    "quarterly": {"lookback": 180, "window": "the last 90 days vs the prior 90 days"},
    "yearly":    {"lookback": 180, "window": "year-over-year trend using all available local history (note any gaps — data may not reach a full year yet)"},
    "lifetime":  {"lookback": 180, "window": "the campaign's full lifetime trend using all available local history (note the actual span covered)"},
}


def _timeframe_cfg(timeframe: Optional[str]) -> dict:
    tf = (timeframe or "").lower().strip()
    cfg = _TIMEFRAMES.get(tf)
    if not cfg:
        return {"lookback": _PREFETCH_DAYS, "window": "the most recent period vs the period before it"}
    return {"lookback": min(cfg["lookback"], _PREFETCH_CAP), "window": cfg["window"]}


# ── Default plan (the user's exact ritual) ────────────────────────────
# Used when no goal-specific plan is requested or when the Director's JSON
# can't be parsed. tools=[] means analysis-only (zero Google Ads API calls) —
# specialists reason over the live campaign data stream_agent_response already
# injects into their context.
_DEFAULT_SPECIALISTS = [
    {
        "role_id": "analytics_analyst",
        "model": "opus",
        "tools": [],
        "task": (
            "Produce the DAILY performance review for this campaign:\n"
            "1. How did yesterday compare to the 7-day average? Flag anomalies.\n"
            "2. Budget pacing — on track for the month?\n"
            "3. Any keywords/terms with high spend and zero conversions?\n"
            "4. Top converting search terms — are they added as keywords?\n"
            "5. Immediate actions. Be concise and specific with numbers."
        ),
    },
    {
        "role_id": "ppc_strategist",
        "model": "opus",
        "tools": [],
        "task": (
            "Produce the WEEKLY report for this campaign:\n"
            "- Last 7 days vs prior 7 days: spend, clicks, conversions, CPA (WoW change).\n"
            "- Bidding & budget assessment given the trend.\n"
            "- Best and worst performing parts of the campaign.\n"
            "- Top 3 structural / bidding recommendations with rationale."
        ),
    },
    {
        "role_id": "creative_director",
        "model": "opus",
        "tools": [],
        "task": (
            "Audit the AD COPY for this campaign:\n"
            "1. Review the current RSA headlines/descriptions in context.\n"
            "2. Identify the weakest-CTR ads.\n"
            "3. Propose new headlines (benefit, urgency, social proof, question).\n"
            "4. Give 5 new headlines + 2 descriptions per underperforming ad, with rationale."
        ),
    },
]

_DEFAULT_DEBATE_FOCUS = (
    "Surface CONFLICTS between the three reports — e.g. the analyst says cut "
    "budget while the strategist says scale, or the creative direction "
    "contradicts the keyword/pacing reality. Name each conflict explicitly, "
    "say who is right and why, and flag anything the others missed."
)

# WS5 — appended to EVERY specialist task (Director-authored or default) to stop
# the verbose 7-persona sprawl and force each to name what would flip its call.
# CONSERVATIVE brevity cap (~200 words) — tunable.
_SPECIALIST_TASK_SUFFIX = (
    "\n\nKeep your report under ~200 words — a few tight bullets: findings + "
    "numbers, no padding or restated context. Ground every page/form/tracking "
    "claim in the VERIFIED PREMISE above (if present); if the premise is "
    "unverified, do NOT assert page facts. END with exactly one line:\n"
    "What would change my conclusion: <the one disconfirming fact or specific "
    "data point that would flip your recommendation>."
)

# WS5 — appended to each debate task so cross-examination also names its
# disconfirming pivot instead of digging in.
_DEBATE_DISCONFIRM_SUFFIX = (
    "\n\nEND with exactly one line:\nWhat would change my conclusion: <the one "
    "disconfirming fact that would flip your position in this debate>."
)


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response (handles ``` fences)."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        # Fall back to the outermost {...} span.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            candidate = text[start : end + 1]
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except Exception:
        return None


# ── Account mode (Story 13.1) ─────────────────────────────────────────
# The scheduler taxonomy Story 13.3 maps findings onto (scheduler.infer_mode).
_ACCOUNT_ACTION_CATEGORIES = {
    "budget", "bids", "status", "geo", "search_terms", "audit", "report", "other",
}

# Hard ceiling on Director-planned passes per campaign in account mode, so a
# runaway plan can't fan out unbounded (cost cap remains the money backstop).
_ACCOUNT_MAX_PASSES_PER_CAMPAIGN = 3

_DEFAULT_ACCOUNT_DEBATE_FOCUS = (
    "Surface CROSS-CAMPAIGN conflicts: budget cannibalization (two campaigns "
    "buying the same demand), keyword collisions (campaigns bidding against "
    "each other on the same terms), audience overlap, and recommendations "
    "for one campaign that contradict another's. Name each conflict, say "
    "which campaign should win and why, and flag account-level issues no "
    "single-campaign report caught."
)


def _max_campaigns() -> int:
    """Account-mode campaign cap (env: WORKFLOW_MAX_CAMPAIGNS, default 5).
    Read at call time so settings changes don't need a module reload."""
    try:
        n = int(getattr(settings, "WORKFLOW_MAX_CAMPAIGNS", 0) or 5)
    except (TypeError, ValueError):
        n = 5
    return max(1, n)


def _excluded_with_reason(excluded: list[dict]) -> list[dict]:
    return [
        {**c, "reason": "over WORKFLOW_MAX_CAMPAIGNS cap — lowest recent spend"}
        for c in excluded
    ]


async def _select_account_campaigns(
    account_id: str, lookback_days: int, cap: int,
) -> tuple[list[dict], list[dict]]:
    """Enumerate ENABLED campaigns from the `campaigns` table (campaigns_repo,
    the V11 single source of truth) and rank them by recent spend from
    campaign_daily_metrics. Returns (selected, excluded): selected = top `cap`
    by spend; excluded campaigns are surfaced by name in the report so the
    truncation is never silent."""
    from app.services import campaigns_repo  # lazy — mirrors the sync_engine import style

    roster = await campaigns_repo.list_campaigns(account_id, status="ENABLED")

    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    spend: dict[str, float] = {}
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT campaign_id, SUM(cost_micros) AS cost_micros "
            "FROM campaign_daily_metrics "
            "WHERE account_id = ? AND date >= ? "
            "GROUP BY campaign_id",
            (account_id, cutoff),
        )
        for row in await cur.fetchall():
            spend[str(row["campaign_id"])] = (row["cost_micros"] or 0) / 1_000_000
    finally:
        await db.close()

    entries: list[dict] = []
    for c in roster:
        cid = str(c.get("campaign_id") or "").strip()
        if not cid:
            continue
        entries.append({
            "campaign_id": cid,
            "campaign_name": c.get("name") or f"Campaign {cid}",
            "spend": round(spend.get(cid, 0.0), 2),
        })
    # Highest recent spend first; name/id tiebreak keeps order deterministic.
    entries.sort(key=lambda e: (-e["spend"], e["campaign_name"], e["campaign_id"]))
    return entries[:cap], entries[cap:]


def _default_account_specialists(selected: list[dict], window: str) -> list[dict]:
    """Fallback account plan: one analysis-only audit pass per selected
    campaign. Used when the Director's account plan can't be parsed or
    yields no valid passes — deterministic and bounded by the campaign cap."""
    return [
        {
            "role_id": "analytics_analyst",
            "model": "opus",
            "tools": [],
            "campaign_id": c["campaign_id"],
            "campaign_name": c["campaign_name"],
            "task": (
                f"Audit campaign \"{c['campaign_name']}\" (id {c['campaign_id']}) "
                f"— compare {window}.\n"
                "1. Performance vs the comparison window: spend, clicks, "
                "conversions, CPA. Flag anomalies.\n"
                "2. Budget pacing and obvious waste (high spend, zero conversions).\n"
                "3. The single biggest fix for THIS campaign, with an estimated "
                "weekly $ impact (say 'unquantified' if the data can't support "
                "a number).\n"
                "Be concise and specific with numbers."
            ),
        }
        for c in selected
    ]


def _account_plan_prompt(
    goal: str, selected: list[dict], excluded: list[dict], cap: int,
) -> str:
    roster = [
        f"- {r['id']} ({r['name']}): {r['specialty']}"
        for r in list_roles()
        if r["id"] != "director"
    ]
    campaign_lines = [
        f"- {c['campaign_id']} · \"{c['campaign_name']}\" · recent spend ${c['spend']:.2f}"
        for c in selected
    ]
    excl = ""
    if excluded:
        excl = (
            "\nNOT in scope this run (over the campaign cap, lowest recent spend): "
            + ", ".join(f"\"{c['campaign_name']}\" ({c['campaign_id']})" for c in excluded)
            + ". Do NOT assign passes to these.\n"
        )
    return (
        "You are the Marketing Director planning an ACCOUNT-WIDE multi-"
        f"specialist audit across the campaigns below.\n\nGOAL: {goal}\n\n"
        f"CAMPAIGNS IN SCOPE ({len(selected)}, cap {cap}):\n"
        + "\n".join(campaign_lines) + "\n" + excl +
        "\nAvailable specialists (pick the ones that fit; tailor each task):\n"
        + "\n".join(roster) + "\n\n"
        "Design the plan. EVERY specialist entry must name the ONE campaign_id "
        "it audits, from the in-scope list. Aim for 1-2 passes per campaign — "
        "lean and focused. This is an ANALYSIS-ONLY run: tools are always [] "
        "(each pass reasons over the campaign data already injected into its "
        "context; no live Google Ads calls, no writes).\n\n"
        "Respond with ONLY a JSON object, no prose, in exactly this shape:\n"
        "```json\n"
        "{\n"
        '  "specialists": [\n'
        '    {"role_id": "analytics_analyst", "campaign_id": "123", "model": "opus", "tools": [], "task": "..."}\n'
        "  ],\n"
        '  "debate_focus": "cross-campaign conflicts the team should hunt for"\n'
        "}\n```"
    )


def _normalize_account_specialists(
    specialists: list, selected: list[dict],
) -> list[dict]:
    """Validate the Director's account plan. Every pass must target exactly
    one in-scope campaign (unknown/missing campaign_id → dropped); tools are
    FORCED to [] — account runs are analysis-only, no Google Ads write/mutate
    surface; passes per campaign are capped. Tasks get a campaign prefix so
    persisted reports stay attributable without a schema change."""
    names = {c["campaign_id"]: c["campaign_name"] for c in selected}
    cleaned: list[dict] = []
    per_campaign: dict[str, int] = {}
    for s in specialists or []:
        if not isinstance(s, dict):
            continue
        cid = str(s.get("campaign_id") or "").strip()
        if cid not in names:
            logger.info("account plan: dropping pass with out-of-scope campaign_id %r", cid)
            continue
        if per_campaign.get(cid, 0) >= _ACCOUNT_MAX_PASSES_PER_CAMPAIGN:
            logger.info(
                "account plan: dropping extra pass for campaign %s (cap %d per campaign)",
                cid, _ACCOUNT_MAX_PASSES_PER_CAMPAIGN,
            )
            continue
        per_campaign[cid] = per_campaign.get(cid, 0) + 1
        s = dict(s)
        s["campaign_id"] = cid
        s["campaign_name"] = names[cid]
        if s.get("tools"):
            logger.info(
                "account plan: stripping tools %s from %s — account runs are analysis-only",
                s.get("tools"), s.get("role_id"),
            )
        s["tools"] = []
        task = str(s.get("task") or "").strip()
        if cid not in task:
            task = (
                f"[Campaign: \"{names[cid]}\" · id {cid}]\n{task}"
                if task else f"Audit campaign \"{names[cid]}\" (id {cid})."
            )
        s["task"] = task
        cleaned.append(s)
    return cleaned


def _account_synthesis_prompt(
    goal: str, selected: list[dict], excluded: list[dict],
    reports_block: str, debate_block: str,
) -> str:
    audited = "\n".join(
        f"- {c['campaign_id']} · \"{c['campaign_name']}\" · recent spend ${c['spend']:.2f}"
        for c in selected
    )
    excl = ""
    if excluded:
        excl = (
            "\nEXCLUDED from this run (campaign cap — name them in your summary): "
            + ", ".join(f"\"{c['campaign_name']}\" ({c['campaign_id']})" for c in excluded)
        )
    return (
        "You are the Marketing Director. Your team has finished an ACCOUNT-WIDE audit.\n\n"
        f"GOAL: {goal}\n\n"
        f"CAMPAIGNS AUDITED:\n{audited}{excl}\n\n"
        f"=== SPECIALIST REPORTS (per campaign) ===\n{reports_block}\n\n"
        f"=== CROSS-CAMPAIGN DEBATE ===\n{debate_block or '(no debate round)'}\n\n"
        "Deliver ONE ranked account-level report as a FIX LIST, not prose.\n\n"
        "FIRST output exactly one fenced ```json block with this shape:\n"
        "```json\n"
        "{\n"
        '  "findings": [\n'
        "    {\n"
        '      "title": "imperative fix, e.g. Cut wasted spend on <term>",\n'
        '      "campaign_ids": ["123"],\n'
        '      "evidence": "1-3 sentences with the numbers that prove it",\n'
        '      "dollar_impact_wk": 120.0,\n'
        '      "action_category": "budget|bids|status|geo|search_terms|audit|report|other",\n'
        '      "recommended_action": "the specific change to make"\n'
        "    }\n"
        "  ],\n"
        '  "total_recoverable_wk": 120.0,\n'
        '  "summary": "one-paragraph executive summary"\n'
        "}\n"
        "```\n"
        "Rules: sort findings by dollar_impact_wk descending. dollar_impact_wk "
        "is the estimated weekly $ recovered or gained — use null when it is "
        "honestly unquantifiable; NEVER invent a number. Include cross-campaign "
        "findings (budget cannibalization, keyword collisions, audience "
        "overlap) with every affected campaign_id listed.\n\n"
        "AFTER the JSON block, write the short human version: a "
        "\"Total recoverable: $X/wk\" line, then the ranked fix list — one "
        "line per finding."
    )


def _coerce_impact(value: Any) -> Optional[float]:
    """Best-effort weekly-$ coercion. None/unparseable → None (explicit
    'unquantified' in the contract — never a fabricated 0-vs-null ambiguity)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    if isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if m:
            try:
                return round(float(m.group(0)), 2)
            except ValueError:
                return None
    return None


def _normalize_findings(
    parsed: Optional[dict], selected: list[dict], excluded: list[dict],
) -> Optional[dict]:
    """Normalize the Director's synthesis JSON into the account-report
    contract (13.2 persists it; 13.3 turns findings into approvable actions).
    Server-side guarantees — never trust LLM arithmetic or ordering:
    findings sorted by $-impact desc (unquantified last), total recomputed
    from the findings, scope lists always attached. Returns None when there
    is nothing parseable → caller degrades to a prose-only report."""
    if not isinstance(parsed, dict):
        return None
    raw = parsed.get("findings")
    if not isinstance(raw, list):
        return None
    findings: list[dict] = []
    for f in raw:
        if not isinstance(f, dict):
            continue
        title = str(f.get("title") or "").strip()
        if not title:
            continue
        ids = f.get("campaign_ids")
        if ids is None and f.get("campaign_id") is not None:
            ids = [f.get("campaign_id")]
        campaign_ids = (
            [str(i).strip() for i in ids if str(i).strip()]
            if isinstance(ids, list) else []
        )
        category = str(f.get("action_category") or "other").strip().lower()
        if category not in _ACCOUNT_ACTION_CATEGORIES:
            category = "other"
        findings.append({
            "title": title,
            "campaign_ids": campaign_ids,
            "evidence": str(f.get("evidence") or "").strip(),
            "dollar_impact_wk": _coerce_impact(f.get("dollar_impact_wk")),  # None == unquantified
            "action_category": category,
            "recommended_action": str(f.get("recommended_action") or "").strip(),
        })
    if not findings:
        return None
    findings.sort(key=lambda f: (f["dollar_impact_wk"] is None, -(f["dollar_impact_wk"] or 0.0)))
    total = round(sum(f["dollar_impact_wk"] for f in findings if f["dollar_impact_wk"]), 2)
    return {
        "mode": "account",
        "findings": findings,
        "total_recoverable_wk": total,
        "summary": str(parsed.get("summary") or "").strip(),
        "campaigns_audited": selected,
        "campaigns_excluded": _excluded_with_reason(excluded),
    }


def _scope_footer(
    selected: list[dict], excluded: list[dict], cap: int, lookback: int,
) -> str:
    """Deterministic scope section appended to every account-mode report —
    guarantees the report SAYS what was excluded even when the Director's
    JSON couldn't be parsed (no silent truncation, ever)."""
    lines = [
        "---",
        f"ACCOUNT AUDIT SCOPE — {len(selected)} of {len(selected) + len(excluded)} "
        f"active campaigns audited (cap WORKFLOW_MAX_CAMPAIGNS={cap}, ranked by "
        f"last-{lookback}d spend):",
    ]
    for c in selected:
        lines.append(
            f"- audited: \"{c['campaign_name']}\" ({c['campaign_id']}) — ${c['spend']:.2f} spend"
        )
    for c in excluded:
        lines.append(
            f"- EXCLUDED (over cap): \"{c['campaign_name']}\" ({c['campaign_id']}) "
            f"— ${c['spend']:.2f} spend — not analyzed this run"
        )
    return "\n".join(lines)


async def _persist_report(
    run_id: str, phase: str, role_id: Optional[str], role_name: Optional[str],
    task: Optional[str], content: str, cost: float, seq: int,
) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO workflow_reports "
            "(id, run_id, phase, role_id, role_name, task, content, cost, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), run_id, phase, role_id, role_name, task, content, cost, seq),
        )
        await db.commit()
    finally:
        await db.close()


async def _update_run(run_id: str, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE workflow_runs SET {cols}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _run_agent(
    *,
    out: asyncio.Queue,
    run_id: str,
    phase: str,
    role_id: str,
    task: str,
    model: str,
    tools: Optional[list[str]],
    account_id: str,
    campaign_id: Optional[str],
    campaign_name: Optional[str],
    conversation_id: Optional[str],
    seq: int,
) -> dict:
    """Run ONE specialist via stream_agent_response, streaming tagged events to
    `out` and returning {role_id, role_name, content, cost}."""
    role = get_role(role_id)
    role_name = role.name if role else role_id
    await out.put({
        "type": "agent_start", "phase": phase, "role_id": role_id,
        "role_name": role_name, "task": task, "seq": seq,
        "campaign_id": campaign_id, "campaign_name": campaign_name,
    })
    parts: list[str] = []
    cost = 0.0
    try:
        async for event in stream_agent_response(
            user_message=task,
            account_id=account_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            conversation_id=conversation_id,
            model=model,
            active_role=role_id,
            tool_allowlist=tools,
        ):
            etype = event.get("type")
            if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                chunk = event.get("content", "")
                parts.append(chunk)
                await out.put({"type": "agent_text", "phase": phase,
                               "role_id": role_id, "content": chunk})
            elif etype == "tool_call":
                await out.put({"type": "agent_tool", "phase": phase,
                               "role_id": role_id, "name": event.get("name", "")})
            elif etype == "done":
                cost = float(event.get("cost") or 0.0)
            elif etype == "error":
                await out.put({"type": "agent_text", "phase": phase, "role_id": role_id,
                               "content": f"\n\n_[error: {event.get('message','')}]_"})
    except Exception as e:
        logger.warning("workflow agent %s failed: %s", role_id, e)
        await out.put({"type": "agent_text", "phase": phase, "role_id": role_id,
                       "content": f"\n\n_[agent failed: {e}]_"})
    content = "".join(parts).strip()
    await _persist_report(run_id, phase, role_id, role_name, task, content, cost, seq)
    await out.put({"type": "agent_done", "phase": phase, "role_id": role_id,
                   "role_name": role_name, "cost": cost, "chars": len(content), "seq": seq,
                   "campaign_id": campaign_id, "campaign_name": campaign_name})
    return {"role_id": role_id, "role_name": role_name, "content": content, "cost": cost,
            "campaign_id": campaign_id, "campaign_name": campaign_name, "seq": seq}


async def _run_group(
    specs: list[dict], *, out: asyncio.Queue, run_id: str, phase: str,
    account_id: str, campaign_id: Optional[str], campaign_name: Optional[str],
    conversation_id: Optional[str], seq_start: int,
) -> list[dict]:
    """Run a group of agents concurrently (capped) and collect their results.

    A spec may carry its own campaign_id/campaign_name (account mode fans out
    per campaign); absent, the group-level binding applies — the existing
    per-campaign behaviour, byte-for-byte."""
    sem = asyncio.Semaphore(_MAX_PARALLEL)

    async def _guarded(spec: dict, seq: int) -> dict:
        async with sem:
            return await _run_agent(
                out=out, run_id=run_id, phase=phase,
                role_id=spec["role_id"], task=spec["task"],
                model=spec.get("model", "opus"), tools=spec.get("tools"),
                account_id=account_id,
                campaign_id=spec.get("campaign_id") or campaign_id,
                campaign_name=spec.get("campaign_name") or campaign_name,
                conversation_id=conversation_id, seq=seq,
            )

    tasks = [asyncio.create_task(_guarded(s, seq_start + i)) for i, s in enumerate(specs)]
    results: list[dict] = []
    for t in asyncio.as_completed(tasks):
        results.append(await t)
    # Restore plan order (as_completed yields by finish time). Sort by seq —
    # role_id alone collapses when account mode runs the same role on
    # multiple campaigns.
    results.sort(key=lambda r: r.get("seq", 0))
    return results


async def run_workflow(
    *,
    goal: str,
    account_id: str,
    campaign_id: Optional[str] = None,
    campaign_name: Optional[str] = None,
    budget: Optional[float] = None,
    timeframe: Optional[str] = None,
    plan_override: Optional[dict] = None,
) -> AsyncIterator[dict]:
    """Run the full Director-orchestrated workflow, yielding SSE-ready events."""
    run_id = str(uuid.uuid4())
    budget = float(budget or _DEFAULT_BUDGET)
    spent = 0.0
    out: asyncio.Queue = asyncio.Queue()

    # Account mode (Story 13.1): no campaign binding at all → plan across
    # active campaigns. A campaign_name without an id keeps the legacy
    # campaign-ish behaviour (downstream agents resolve by name).
    account_mode = campaign_id is None and not campaign_name
    cap = _max_campaigns()
    selected_campaigns: list[dict] = []
    excluded_campaigns: list[dict] = []

    # Timeframe shapes the comparison window every specialist analyses, and how
    # far back the pre-fetch syncs. Folded into the goal so the Director plans
    # period-appropriate tasks.
    tf_cfg = _timeframe_cfg(timeframe)
    if timeframe:
        goal = f"{goal}\n\nTIMEFRAME: {timeframe} — compare {tf_cfg['window']}."

    # One conversation for the run so each specialist's report persists into
    # the campaign's role_notes (debate + synthesis benefit, and the campaign
    # memory stays warm for normal chat afterwards).
    conv_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (id, account_id, campaign_id, campaign_name, title) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, account_id, campaign_id, campaign_name,
             f"Workflow: {goal[:60]}"),
        )
        await db.execute(
            "INSERT INTO workflow_runs "
            "(id, account_id, campaign_id, campaign_name, conversation_id, goal, status, budget, timeframe) "
            "VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)",
            (run_id, account_id, campaign_id, campaign_name, conv_id, goal, budget, timeframe),
        )
        await db.commit()
    finally:
        await db.close()

    yield {"type": "workflow_start", "run_id": run_id, "goal": goal,
           "campaign_id": campaign_id, "campaign_name": campaign_name,
           "budget": budget, "timeframe": timeframe,
           "mode": "account" if account_mode else "campaign"}

    try:
        # ── Phase 0: pre-fetch (rate-limit firewall) ──────────────────
        yield {"type": "phase", "phase": "prefetch", "status": "start",
               "label": "Pre-fetching campaign data (one batched sync)"}
        if settings.SYNC_ENABLED and account_id:
            try:
                # A4: sync_account was rewritten (A1) to a single account-wide
                # GAQL upsert with the REAL campaign_daily_metrics columns, so
                # this Phase-0 pre-fetch now ACTUALLY writes rows + the
                # sync_state ledger (it silently failed for months on the old
                # ghost-column path). The audit below reads fresh local data.
                from app.services.sync_engine import sync_account
                res = await sync_account(account_id, days=tf_cfg["lookback"])
                yield {"type": "phase", "phase": "prefetch", "status": "done",
                       "label": f"Synced {res.get('campaigns_synced', 0)} campaigns · "
                                f"agents now read local data"}
            except Exception as e:
                logger.warning("workflow pre-fetch failed (continuing on local data): %s", e)
                yield {"type": "phase", "phase": "prefetch", "status": "done",
                       "label": "Pre-fetch skipped — using existing local data"}
        else:
            yield {"type": "phase", "phase": "prefetch", "status": "done",
                   "label": "Sync disabled — using existing local data"}

        # ── WS5 premise gate: verify the live page/form/tracking state ──
        # Reuses the WS2 fetch so the whole team (Director + specialists +
        # debate + synthesis) reasons from the REAL page, not an unverified
        # premise. Folded into `goal` because goal threads into every phase.
        # NEVER crashes the run.
        if campaign_id:
            yield {"type": "phase", "phase": "verify", "status": "start",
                   "label": "Verifying live landing-page / form / tracking state"}
            premise_block = ""
            try:
                from app.services.agent import fetch_ad_landing_pages
                premise_block = await fetch_ad_landing_pages(account_id, campaign_id)
            except Exception as e:
                logger.warning("workflow premise verify failed: %s", e)
                premise_block = ""
            if premise_block:
                goal = (
                    f"{goal}\n\n=== VERIFIED PREMISE (live page/form/tracking "
                    f"state, this session) ===\n{premise_block}\n"
                    "Ground every page/form/tracking claim in THIS. Do NOT diagnose "
                    "off an unverified page assumption."
                )
                yield {"type": "phase", "phase": "verify", "status": "done",
                       "label": "Premise verified — live page state pinned for the team"}
            else:
                goal = (
                    f"{goal}\n\n=== PREMISE UNVERIFIED — do NOT assert page/form/"
                    "tracking facts ===\nThe live landing page could not be fetched "
                    "this session. Do NOT claim the page has/lacks a form or that "
                    "tracking is/isn't firing — flag it as unverified and recommend a fetch."
                )
                yield {"type": "phase", "phase": "verify", "status": "done",
                       "label": "Premise UNVERIFIED — team told not to assert page facts"}

        # ── Account mode: enumerate + cap the campaign roster ─────────
        if account_mode:
            selected_campaigns, excluded_campaigns = await _select_account_campaigns(
                account_id, tf_cfg["lookback"], cap,
            )
            yield {"type": "account_scope", "cap": cap,
                   "selected": selected_campaigns,
                   "excluded": _excluded_with_reason(excluded_campaigns),
                   "total_active": len(selected_campaigns) + len(excluded_campaigns)}
            if not selected_campaigns:
                msg = ("Account-wide audit found no ENABLED campaigns for this "
                       "account — nothing to audit.")
                await _update_run(run_id, status="error", stop_reason=msg[:300])
                yield {"type": "error", "run_id": run_id, "message": msg}
                return

        # ── Phase 1: Director plans ───────────────────────────────────
        yield {"type": "phase", "phase": "plan", "status": "start",
               "label": ("Marketing Director planning the account-wide audit"
                         if account_mode else "Marketing Director planning the audit")}
        plan: dict
        if plan_override:
            plan = plan_override
        else:
            if account_mode:
                plan_prompt = _account_plan_prompt(goal, selected_campaigns,
                                                   excluded_campaigns, cap)
            else:
                roster = [
                    f"- {r['id']} ({r['name']}): {r['specialty']}"
                    for r in list_roles()
                    if r["id"] != "director"
                ]
                plan_prompt = (
                    "You are the Marketing Director planning a multi-specialist audit "
                    f"of this campaign.\n\nGOAL: {goal}\n\n"
                    "Available specialists (pick the ones that fit; tailor each task):\n"
                    + "\n".join(roster) + "\n\n"
                    "Design the plan. For each specialist write a SPECIFIC task prompt "
                    "for THIS campaign, choose a model (haiku=cheap/simple, "
                    "sonnet=standard, opus=hard reasoning), and a tool allowlist. "
                    "Prefer tools=[] (analysis-only over the campaign data already in "
                    "their context) to avoid Google Ads API rate limits — only grant "
                    "tools when the task truly needs a live write or a fetch not in context.\n"
                    "The GOAL may include a VERIFIED PREMISE (live page/form/tracking "
                    "state) — task specialists to ground their claims in it, not in "
                    "assumptions, and keep each specialist tight (a few bullets).\n\n"
                    "Respond with ONLY a JSON object, no prose, in exactly this shape:\n"
                    "```json\n"
                    "{\n"
                    '  "specialists": [\n'
                    '    {"role_id": "analytics_analyst", "model": "opus", "tools": [], "task": "..."}\n'
                    "  ],\n"
                    '  "debate_focus": "what conflicts the team should hunt for"\n'
                    "}\n```"
                )
            plan_parts: list[str] = []
            async for event in stream_agent_response(
                user_message=plan_prompt, account_id=account_id,
                campaign_id=campaign_id, campaign_name=campaign_name,
                conversation_id=conv_id, model="fable", active_role="director",
                tool_allowlist=[],  # planning is pure reasoning
            ):
                if event.get("type") in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                    plan_parts.append(event.get("content", ""))
                elif event.get("type") == "done":
                    spent += float(event.get("cost") or 0.0)
            parsed = _extract_json("".join(plan_parts))
            plan = parsed if (parsed and isinstance(parsed.get("specialists"), list)
                              and parsed["specialists"]) else None
            if plan is None:
                logger.info("workflow %s: Director plan unparseable — using default ritual", run_id)
                if account_mode:
                    plan = {"specialists": _default_account_specialists(
                                selected_campaigns, tf_cfg["window"]),
                            "debate_focus": _DEFAULT_ACCOUNT_DEBATE_FOCUS}
                else:
                    plan = {"specialists": _DEFAULT_SPECIALISTS, "debate_focus": _DEFAULT_DEBATE_FOCUS}

        if account_mode:
            # Validate per-campaign binding, force analysis-only tools, cap
            # passes per campaign. An empty result degrades to the default
            # per-campaign ritual rather than failing.
            specialists = _normalize_account_specialists(
                plan.get("specialists") or [], selected_campaigns,
            ) or _default_account_specialists(selected_campaigns, tf_cfg["window"])
            debate_focus = plan.get("debate_focus") or _DEFAULT_ACCOUNT_DEBATE_FOCUS
        else:
            specialists = plan.get("specialists") or _DEFAULT_SPECIALISTS
            debate_focus = plan.get("debate_focus") or _DEFAULT_DEBATE_FOCUS
        # Normalise + resolve role names for the UI.
        for s in specialists:
            r = get_role(s.get("role_id", ""))
            s["role_name"] = r.name if r else s.get("role_id", "Specialist")
            s.setdefault("model", "opus")
            s.setdefault("tools", [])
            s.setdefault("task", goal)
            # WS5 — cap length + force disconfirmation on every specialist,
            # whether the task came from the Director or a default ritual.
            s["task"] = s["task"] + _SPECIALIST_TASK_SUFFIX
        await _update_run(run_id, plan_json=json.dumps(plan))
        await _persist_report(run_id, "plan", "director", "Marketing Director",
                              goal, json.dumps(plan, indent=2), 0.0, 0)
        yield {"type": "plan", "specialists": [
            {"role_id": s["role_id"], "role_name": s["role_name"],
             "model": s["model"], "tools": s["tools"], "task": s["task"],
             "campaign_id": s.get("campaign_id"),
             "campaign_name": s.get("campaign_name")}
            for s in specialists
        ], "debate_focus": debate_focus}
        yield {"type": "phase", "phase": "plan", "status": "done",
               "label": f"Plan ready · {len(specialists)} specialists"}
        yield {"type": "budget", "spent": round(spent, 4), "budget": budget}

        # ── Phase 2: specialists run (parallel, capped) ───────────────
        yield {"type": "phase", "phase": "specialists", "status": "start",
               "label": f"Running {len(specialists)} specialists"}

        async def _drain_group(specs, phase, seq_start):
            """Run a group and forward its queued events as we go."""
            runner = asyncio.create_task(_run_group(
                specs, out=out, run_id=run_id, phase=phase,
                account_id=account_id, campaign_id=campaign_id,
                campaign_name=campaign_name, conversation_id=conv_id,
                seq_start=seq_start,
            ))
            while not runner.done() or not out.empty():
                try:
                    ev = await asyncio.wait_for(out.get(), timeout=0.1)
                    yield ev
                except asyncio.TimeoutError:
                    continue
            yield {"__results__": await runner}

        reports: list[dict] = []
        async for ev in _drain_group(specialists, "specialists", 1):
            if "__results__" in ev:
                reports = ev["__results__"]
            else:
                yield ev
        spent += sum(r["cost"] for r in reports)
        yield {"type": "phase", "phase": "specialists", "status": "done",
               "label": "All specialist reports in"}
        yield {"type": "budget", "spent": round(spent, 4), "budget": budget}

        def _peer_block(exclude_role: str) -> str:
            return "\n\n".join(
                f"### {r['role_name']} report:\n{r['content']}"
                for r in reports if r["role_id"] != exclude_role and r["content"]
            )

        # ── Phase 3: debate / cross-examine ───────────────────────────
        debate_results: list[dict] = []
        if len(reports) > 1 and spent < budget:
            yield {"type": "phase", "phase": "debate", "status": "start",
                   "label": ("Cross-campaign debate — hunting account-level conflicts"
                             if account_mode else "Team cross-examining for conflicts")}
            if account_mode:
                # One unbound pass per distinct role: each reads EVERY
                # campaign's reports and hunts conflicts ACROSS campaigns
                # (budget cannibalization, keyword collisions, overlap).
                tagged_block = "\n\n".join(
                    f"### {r['role_name']} on \"{r.get('campaign_name') or 'account'}\" "
                    f"({r.get('campaign_id') or 'account'}):\n{r['content']}"
                    for r in reports if r["content"]
                )
                distinct_roles = list(dict.fromkeys(
                    r["role_id"] for r in reports if r["content"]
                ))
                debate_specs = [{
                    "role_id": rid,
                    "model": "opus",
                    "tools": [],
                    "task": (
                        "You audited individual campaigns in an account-wide "
                        "review. Below are ALL per-campaign reports from the "
                        f"team.\n\nFOCUS: {debate_focus}\n\n{tagged_block}\n\n"
                        "Respond with: (1) CROSS-CAMPAIGN conflicts (budget "
                        "cannibalization, keyword collisions, audience overlap, "
                        "recommendations that contradict each other), (2) which "
                        "campaign should win each conflict and why, (3) account-"
                        "level issues no single-campaign report caught. Be "
                        "specific and brief." + _DEBATE_DISCONFIRM_SUFFIX
                    ),
                } for rid in distinct_roles]
            else:
                debate_specs = [{
                    "role_id": r["role_id"],
                    "model": "opus",
                    "tools": [],
                    "task": (
                        f"You already produced your report. Now review your PEERS' "
                        f"reports below and cross-examine them.\n\nFOCUS: {debate_focus}\n\n"
                        f"{_peer_block(r['role_id'])}\n\n"
                        "Respond with: (1) conflicts you see between your view and "
                        "theirs, (2) where you concede they're right, (3) anything "
                        "they all missed. Be specific and brief." + _DEBATE_DISCONFIRM_SUFFIX
                    ),
                } for r in reports if r["content"]]
            async for ev in _drain_group(debate_specs, "debate", 100):
                if "__results__" in ev:
                    debate_results = ev["__results__"]
                else:
                    yield ev
            spent += sum(r["cost"] for r in debate_results)
            yield {"type": "phase", "phase": "debate", "status": "done",
                   "label": "Debate complete"}
            yield {"type": "budget", "spent": round(spent, 4), "budget": budget}
        elif spent >= budget:
            yield {"type": "phase", "phase": "debate", "status": "done",
                   "label": "Skipped debate — budget reached, going to synthesis"}

        # ── Phase 4: Marketing Director synthesis ─────────────────────
        yield {"type": "phase", "phase": "synthesis", "status": "start",
               "label": ("Marketing Director synthesising the account report"
                         if account_mode else "Marketing Director reconciling into final plan")}
        if account_mode:
            reports_block = "\n\n".join(
                f"## {r['role_name']} — \"{r.get('campaign_name') or 'account'}\" "
                f"({r.get('campaign_id') or 'account'}) — REPORT\n{r['content']}"
                for r in reports if r["content"]
            )
        else:
            reports_block = "\n\n".join(
                f"## {r['role_name']} — REPORT\n{r['content']}" for r in reports if r["content"]
            )
        debate_block = "\n\n".join(
            f"## {r['role_name']} — CROSS-EXAMINATION\n{r['content']}"
            for r in debate_results if r["content"]
        )
        if account_mode:
            synth_task = _account_synthesis_prompt(
                goal, selected_campaigns, excluded_campaigns,
                reports_block, debate_block,
            )
        else:
            synth_task = (
                f"You are the Marketing Director. Your team has finished its audit.\n\n"
                f"GOAL: {goal}\n\n"
                f"=== SPECIALIST REPORTS ===\n{reports_block}\n\n"
                f"=== TEAM CROSS-EXAMINATION ===\n{debate_block or '(no debate round)'}\n\n"
                "Deliver the FINAL reconciled plan: resolve every conflict the team "
                "raised (state your ruling and why), then give a prioritised action "
                "list (what to do first, expected impact, owner role). Be decisive. "
                "GATE: the plan must be consistent with the VERIFIED PREMISE in the "
                "GOAL above — do NOT endorse any recommendation built on an "
                "unverified page/form/tracking claim; if the premise was unverified, "
                "say so and make verifying it the first action."
            )
        synth_parts: list[str] = []
        synth_cost = 0.0
        async for event in stream_agent_response(
            user_message=synth_task, account_id=account_id,
            campaign_id=campaign_id, campaign_name=campaign_name,
            conversation_id=conv_id, model="fable", active_role="director",
            tool_allowlist=[],
        ):
            etype = event.get("type")
            if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                chunk = event.get("content", "")
                synth_parts.append(chunk)
                yield {"type": "agent_text", "phase": "synthesis",
                       "role_id": "director", "content": chunk}
            elif etype == "tool_call":
                yield {"type": "agent_tool", "phase": "synthesis",
                       "role_id": "director", "name": event.get("name", "")}
            elif etype == "done":
                synth_cost = float(event.get("cost") or 0.0)
        final_output = "".join(synth_parts).strip()
        spent += synth_cost

        # ── Account mode: cross-campaign rollup contract ──────────────
        # Normalize the Director's findings JSON into the structure 13.2
        # persists and 13.3 acts on; unparseable output degrades to a
        # prose-only report (never fails the run). The deterministic scope
        # footer is appended EITHER way so the report always says which
        # campaigns were excluded by the cap.
        account_report: Optional[dict] = None
        if account_mode:
            normalized = _normalize_findings(
                _extract_json(final_output), selected_campaigns, excluded_campaigns,
            )
            parse_ok = normalized is not None
            if normalized is None:
                logger.info("workflow %s: account synthesis JSON unparseable — prose-only report", run_id)
                normalized = {
                    "mode": "account",
                    "findings": [],
                    "total_recoverable_wk": 0.0,
                    "summary": "",
                    "campaigns_audited": selected_campaigns,
                    "campaigns_excluded": _excluded_with_reason(excluded_campaigns),
                }
            normalized["parse_ok"] = parse_ok
            account_report = normalized
            footer = _scope_footer(selected_campaigns, excluded_campaigns,
                                   cap, tf_cfg["lookback"])
            final_output = f"{final_output}\n\n{footer}" if final_output else footer
            await _persist_report(
                run_id, "account_rollup", "director", "Marketing Director",
                "Cross-campaign rollup — structured findings (account mode)",
                json.dumps(account_report), 0.0, 998,
            )
            # Story 13.2: persist as THE latest account report so the homepage
            # reads it instantly (latest-wins UPSERT on account_id). Best-effort
            # — a persistence hiccup must never fail an otherwise-good run.
            try:
                from app.services import account_report_store
                await account_report_store.save_latest(account_id, run_id, account_report)
            except Exception as e:  # pragma: no cover — defensive
                logger.warning("account report persist failed for run %s: %s", run_id, e)

        await _persist_report(run_id, "synthesis", "director", "Marketing Director",
                              synth_task[:500], final_output, synth_cost, 999)
        yield {"type": "phase", "phase": "synthesis", "status": "done",
               "label": ("Account report ready" if account_mode else "Final plan ready")}

        await _update_run(run_id, status="done", final_output=final_output, cost=round(spent, 4))
        done_event = {"type": "workflow_done", "run_id": run_id, "cost": round(spent, 4),
                      "budget": budget, "final_output": final_output, "stop_reason": "natural"}
        if account_report is not None:
            done_event["account_report"] = account_report
        yield done_event

    except Exception as e:
        logger.exception("workflow %s failed: %s", run_id, e)
        await _update_run(run_id, status="error", stop_reason=str(e)[:300], cost=round(spent, 4))
        yield {"type": "error", "run_id": run_id, "message": str(e)}
