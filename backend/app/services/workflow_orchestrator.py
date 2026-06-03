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
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
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
        "model": "sonnet",
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
        "model": "sonnet",
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
        "model": "sonnet",
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
            if etype == "text":
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
                   "role_name": role_name, "cost": cost, "chars": len(content), "seq": seq})
    return {"role_id": role_id, "role_name": role_name, "content": content, "cost": cost}


async def _run_group(
    specs: list[dict], *, out: asyncio.Queue, run_id: str, phase: str,
    account_id: str, campaign_id: Optional[str], campaign_name: Optional[str],
    conversation_id: Optional[str], seq_start: int,
) -> list[dict]:
    """Run a group of agents concurrently (capped) and collect their results."""
    sem = asyncio.Semaphore(_MAX_PARALLEL)

    async def _guarded(spec: dict, seq: int) -> dict:
        async with sem:
            return await _run_agent(
                out=out, run_id=run_id, phase=phase,
                role_id=spec["role_id"], task=spec["task"],
                model=spec.get("model", "sonnet"), tools=spec.get("tools"),
                account_id=account_id, campaign_id=campaign_id,
                campaign_name=campaign_name, conversation_id=conversation_id, seq=seq,
            )

    tasks = [asyncio.create_task(_guarded(s, seq_start + i)) for i, s in enumerate(specs)]
    results: list[dict] = []
    for t in asyncio.as_completed(tasks):
        results.append(await t)
    # Restore plan order (as_completed yields by finish time).
    order = {s["role_id"]: i for i, s in enumerate(specs)}
    results.sort(key=lambda r: order.get(r["role_id"], 0))
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
           "budget": budget, "timeframe": timeframe}

    try:
        # ── Phase 0: pre-fetch (rate-limit firewall) ──────────────────
        yield {"type": "phase", "phase": "prefetch", "status": "start",
               "label": "Pre-fetching campaign data (one batched sync)"}
        if settings.SYNC_ENABLED and account_id:
            try:
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

        # ── Phase 1: Director plans ───────────────────────────────────
        yield {"type": "phase", "phase": "plan", "status": "start",
               "label": "Marketing Director planning the audit"}
        plan: dict
        if plan_override:
            plan = plan_override
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
                "tools when the task truly needs a live write or a fetch not in context.\n\n"
                "Respond with ONLY a JSON object, no prose, in exactly this shape:\n"
                "```json\n"
                "{\n"
                '  "specialists": [\n'
                '    {"role_id": "analytics_analyst", "model": "sonnet", "tools": [], "task": "..."}\n'
                "  ],\n"
                '  "debate_focus": "what conflicts the team should hunt for"\n'
                "}\n```"
            )
            plan_parts: list[str] = []
            async for event in stream_agent_response(
                user_message=plan_prompt, account_id=account_id,
                campaign_id=campaign_id, campaign_name=campaign_name,
                conversation_id=conv_id, model="opus", active_role="director",
                tool_allowlist=[],  # planning is pure reasoning
            ):
                if event.get("type") == "text":
                    plan_parts.append(event.get("content", ""))
                elif event.get("type") == "done":
                    spent += float(event.get("cost") or 0.0)
            parsed = _extract_json("".join(plan_parts))
            plan = parsed if (parsed and isinstance(parsed.get("specialists"), list)
                              and parsed["specialists"]) else None
            if plan is None:
                logger.info("workflow %s: Director plan unparseable — using default ritual", run_id)
                plan = {"specialists": _DEFAULT_SPECIALISTS, "debate_focus": _DEFAULT_DEBATE_FOCUS}

        specialists = plan.get("specialists") or _DEFAULT_SPECIALISTS
        debate_focus = plan.get("debate_focus") or _DEFAULT_DEBATE_FOCUS
        # Normalise + resolve role names for the UI.
        for s in specialists:
            r = get_role(s.get("role_id", ""))
            s["role_name"] = r.name if r else s.get("role_id", "Specialist")
            s.setdefault("model", "sonnet")
            s.setdefault("tools", [])
            s.setdefault("task", goal)
        await _update_run(run_id, plan_json=json.dumps(plan))
        await _persist_report(run_id, "plan", "director", "Marketing Director",
                              goal, json.dumps(plan, indent=2), 0.0, 0)
        yield {"type": "plan", "specialists": [
            {"role_id": s["role_id"], "role_name": s["role_name"],
             "model": s["model"], "tools": s["tools"], "task": s["task"]}
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
                   "label": "Team cross-examining for conflicts"}
            debate_specs = [{
                "role_id": r["role_id"],
                "model": "sonnet",
                "tools": [],
                "task": (
                    f"You already produced your report. Now review your PEERS' "
                    f"reports below and cross-examine them.\n\nFOCUS: {debate_focus}\n\n"
                    f"{_peer_block(r['role_id'])}\n\n"
                    "Respond with: (1) conflicts you see between your view and "
                    "theirs, (2) where you concede they're right, (3) anything "
                    "they all missed. Be specific and brief."
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
               "label": "Marketing Director reconciling into final plan"}
        reports_block = "\n\n".join(
            f"## {r['role_name']} — REPORT\n{r['content']}" for r in reports if r["content"]
        )
        debate_block = "\n\n".join(
            f"## {r['role_name']} — CROSS-EXAMINATION\n{r['content']}"
            for r in debate_results if r["content"]
        )
        synth_task = (
            f"You are the Marketing Director. Your team has finished its audit.\n\n"
            f"GOAL: {goal}\n\n"
            f"=== SPECIALIST REPORTS ===\n{reports_block}\n\n"
            f"=== TEAM CROSS-EXAMINATION ===\n{debate_block or '(no debate round)'}\n\n"
            "Deliver the FINAL reconciled plan: resolve every conflict the team "
            "raised (state your ruling and why), then give a prioritised action "
            "list (what to do first, expected impact, owner role). Be decisive."
        )
        synth_parts: list[str] = []
        synth_cost = 0.0
        async for event in stream_agent_response(
            user_message=synth_task, account_id=account_id,
            campaign_id=campaign_id, campaign_name=campaign_name,
            conversation_id=conv_id, model="opus", active_role="director",
            tool_allowlist=[],
        ):
            etype = event.get("type")
            if etype == "text":
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
        await _persist_report(run_id, "synthesis", "director", "Marketing Director",
                              synth_task[:500], final_output, synth_cost, 999)
        yield {"type": "phase", "phase": "synthesis", "status": "done", "label": "Final plan ready"}

        await _update_run(run_id, status="done", final_output=final_output, cost=round(spent, 4))
        yield {"type": "workflow_done", "run_id": run_id, "cost": round(spent, 4),
               "budget": budget, "final_output": final_output, "stop_reason": "natural"}

    except Exception as e:
        logger.exception("workflow %s failed: %s", run_id, e)
        await _update_run(run_id, status="error", stop_reason=str(e)[:300], cost=round(spent, 4))
        yield {"type": "error", "run_id": run_id, "message": str(e)}
