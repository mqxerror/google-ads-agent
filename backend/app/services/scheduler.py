"""Scheduled Plans engine.

A plan is a decision (from chat or added manually) bound to a time. The
scheduler ticks once a minute, finds plans whose next_run_at has passed, and
fires them:

- **auto** mode (safe / read actions: search-term cleanup, audits, reports) —
  runs the agent with its normal (campaign-scoped) tools and streams the
  result straight into the originating chat thread. Done.
- **approval** mode (spend / structural: budget, bids, status, geo) — runs
  ANALYSIS-ONLY first (no write tools, zero spend), captures the proposed
  change, and parks the plan in `awaiting_approval`. The user approves from
  the Plans UI, which calls `approve_plan()` to execute with write tools.

Recurring plans re-arm (compute next_run_at) after a successful run. Overdue
plans (e.g. the server was down at fire time) simply fire on the next tick —
nothing is silently missed. Everything reuses `stream_agent_response`, so the
campaign scope guard, cost cap, and resumable sessions all apply for free.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.services.agent import stream_agent_response

logger = logging.getLogger(__name__)

_TICK_SECONDS = 60
_MAX_CONCURRENT = 2
_sem = asyncio.Semaphore(_MAX_CONCURRENT)
_task: asyncio.Task | None = None

# Categories that move money or change campaign structure → gate behind approval.
_APPROVAL_CATEGORIES = {"budget", "bids", "status", "geo"}
# Which specialist runs each category.
_CATEGORY_ROLE = {
    "search_terms": "search_term_hunter",
    "budget": "ppc_strategist",
    "bids": "ppc_strategist",
    "status": "ppc_strategist",
    "geo": "ppc_strategist",
    "audit": "cro_specialist",
    "report": "analytics_analyst",
    "other": None,
}
_DOW = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def infer_mode(category: str | None) -> str:
    return "approval" if (category or "other") in _APPROVAL_CATEGORIES else "auto"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, matches SQLite datetime('now')


def _parse(dt: str | None) -> datetime | None:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt.replace("Z", "").replace("T", " ").strip())
    except Exception:
        return None


def compute_next_run(recurrence: str | None, after: datetime | None = None) -> datetime | None:
    """Next fire time for a recurrence spec like 'daily:09:00', 'weekly:mon:09:00',
    'monthly:15:09:00'. Returns the next occurrence strictly after `after`."""
    if not recurrence:
        return None
    base = after or _now()
    parts = recurrence.split(":")
    kind = parts[0].lower()
    try:
        if kind == "daily":  # daily:HH:MM
            hh, mm = int(parts[1]), int(parts[2])
            cand = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if cand <= base:
                cand += timedelta(days=1)
            return cand
        if kind == "weekly":  # weekly:dow:HH:MM
            dow = _DOW.get(parts[1].lower(), 0)
            hh, mm = int(parts[2]), int(parts[3])
            cand = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
            days_ahead = (dow - cand.weekday()) % 7
            cand += timedelta(days=days_ahead)
            if cand <= base:
                cand += timedelta(days=7)
            return cand
        if kind == "monthly":  # monthly:DD:HH:MM
            day, hh, mm = int(parts[1]), int(parts[2]), int(parts[3])
            cand = base.replace(day=min(day, 28), hour=hh, minute=mm, second=0, microsecond=0)
            if cand <= base:
                month = cand.month % 12 + 1
                year = cand.year + (1 if cand.month == 12 else 0)
                cand = cand.replace(year=year, month=month)
            return cand
    except Exception as e:
        logger.warning("bad recurrence %r: %s", recurrence, e)
    return None


async def _set(plan_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE scheduled_plans SET {cols}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), plan_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _ensure_conversation(plan: dict) -> str:
    """Resolve (or create) the chat thread a plan's run should post into."""
    conv_id = plan.get("conversation_id")
    db = await get_db()
    try:
        if conv_id:
            cur = await db.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
            if await cur.fetchone():
                return conv_id
        conv_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO conversations (id, account_id, campaign_id, campaign_name, title) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, plan["account_id"], plan.get("campaign_id"), plan.get("campaign_name"),
             f"Scheduled: {plan['title'][:50]}"),
        )
        await db.commit()
        return conv_id
    finally:
        await db.close()


async def _post_message(conv_id: str, role: str, content: str, campaign_id: str | None,
                        agent_role: str | None = None, agent_role_name: str | None = None) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, campaign_id, agent_role, agent_role_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conv_id, role, content, campaign_id, agent_role, agent_role_name),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?", (conv_id,)
        )
        await db.commit()
    finally:
        await db.close()


async def _run_agent(plan: dict, *, instruction: str, analysis_only: bool, model: str = "sonnet") -> tuple[str, float]:
    """Run one agent turn for a plan, persisting it into the origin chat thread."""
    conv_id = await _ensure_conversation(plan)
    campaign_id = plan.get("campaign_id")
    role = _CATEGORY_ROLE.get(plan.get("action_category") or "other")
    prompt = instruction
    if plan.get("context_snippet"):
        prompt = f"{instruction}\n\nOriginating decision context:\n{plan['context_snippet']}"
    await _post_message(conv_id, "user", f"[Scheduled plan] {plan['title']}", campaign_id)
    parts: list[str] = []
    cost = 0.0
    role_name = None
    async for ev in stream_agent_response(
        user_message=prompt,
        account_id=plan["account_id"],
        campaign_id=campaign_id,
        campaign_name=plan.get("campaign_name"),
        conversation_id=conv_id,
        model=model,
        active_role=role,
        tool_allowlist=[] if analysis_only else None,
    ):
        t = ev.get("type")
        if t == "text":
            parts.append(ev.get("content", ""))
        elif t == "routing":
            role_name = ev.get("role_name")
        elif t == "done":
            cost = float(ev.get("cost") or 0.0)
    text = "".join(parts).strip()
    if text:
        await _post_message(conv_id, "assistant", text, campaign_id, role, role_name)
    return text, cost


async def _fire(plan: dict) -> None:
    """Execute one due plan (called under the concurrency semaphore)."""
    pid = plan["id"]
    run_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO scheduled_plan_runs (id, plan_id, status) VALUES (?, ?, 'running')",
            (run_id, pid),
        )
        await db.commit()
    finally:
        await db.close()

    try:
        if plan["mode"] == "approval":
            # Analysis-only: propose the change, do NOT execute. Park for sign-off.
            instruction = (
                f"A scheduled plan is due: \"{plan['action_detail']}\". DO NOT make any "
                f"changes yet. Inspect the current campaign state and produce the exact "
                f"proposed change as a one-line diff (e.g. 'daily budget $100 -> $150') "
                f"plus a 2-3 sentence rationale. This will be shown to the user for approval."
            )
            text, cost = await _run_agent(plan, instruction=instruction, analysis_only=True)
            await _set(pid, status="awaiting_approval", proposed_change=text,
                       last_run_at=_now().isoformat(sep=" ", timespec="seconds"),
                       last_result=text, last_cost=cost, run_count=plan["run_count"] + 1)
            await _finish_run(run_id, "awaiting_approval", text, cost)
        else:
            # Auto: execute with normal (campaign-scoped) tools.
            instruction = (
                f"A scheduled plan is due: \"{plan['action_detail']}\". Carry it out now on "
                f"this campaign, then report what you did with concrete specifics."
            )
            text, cost = await _run_agent(plan, instruction=instruction, analysis_only=False)
            await _complete(plan, text, cost)
            await _finish_run(run_id, "done", text, cost)
    except Exception as e:
        logger.exception("plan %s failed: %s", pid, e)
        await _set(pid, status="failed", last_result=f"Run failed: {e}"[:500],
                   last_run_at=_now().isoformat(sep=" ", timespec="seconds"))
        await _finish_run(run_id, "failed", str(e)[:500], 0.0)


async def _complete(plan: dict, text: str, cost: float) -> None:
    """Mark a fired plan done, re-arming if recurring."""
    pid = plan["id"]
    now_s = _now().isoformat(sep=" ", timespec="seconds")
    fields = dict(last_run_at=now_s, last_result=text, last_cost=cost,
                  run_count=plan["run_count"] + 1, proposed_change=None)
    if plan["schedule_type"] == "recurring":
        nxt = compute_next_run(plan.get("recurrence"))
        if nxt:
            fields.update(status="scheduled", next_run_at=nxt.isoformat(sep=" ", timespec="seconds"))
        else:
            fields.update(status="done")
    else:
        fields.update(status="done")
    await _set(pid, **fields)


async def _finish_run(run_id: str, status: str, result: str, cost: float) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE scheduled_plan_runs SET status=?, result=?, cost=?, finished_at=datetime('now') WHERE id=?",
            (status, result[:4000] if result else None, cost, run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def approve_plan(plan_id: str) -> dict:
    """User approved a gated plan → execute it for real with write tools."""
    plan = await get_plan(plan_id)
    if not plan or plan["status"] != "awaiting_approval":
        return {"error": "plan not awaiting approval"}
    await _set(plan_id, status="running")
    run_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute("INSERT INTO scheduled_plan_runs (id, plan_id, status) VALUES (?, ?, 'running')", (run_id, plan_id))
        await db.commit()
    finally:
        await db.close()
    try:
        instruction = (
            f"The user APPROVED this scheduled change: \"{plan['action_detail']}\". "
            f"Apply it now on this campaign and confirm exactly what you changed."
        )
        text, cost = await _run_agent(plan, instruction=instruction, analysis_only=False)
        await _complete(plan, text, cost)
        await _finish_run(run_id, "done", text, cost)
        return {"status": "done", "result": text, "cost": cost}
    except Exception as e:
        logger.exception("approve plan %s failed: %s", plan_id, e)
        await _set(plan_id, status="failed", last_result=f"Apply failed: {e}"[:500])
        await _finish_run(run_id, "failed", str(e)[:500], 0.0)
        return {"error": str(e)}


async def skip_plan(plan_id: str) -> dict:
    """Decline a gated plan; recurring ones re-arm to their next slot."""
    plan = await get_plan(plan_id)
    if not plan:
        return {"error": "not found"}
    if plan["schedule_type"] == "recurring":
        nxt = compute_next_run(plan.get("recurrence"))
        await _set(plan_id, status="scheduled",
                   next_run_at=nxt.isoformat(sep=" ", timespec="seconds") if nxt else None,
                   proposed_change=None)
    else:
        await _set(plan_id, status="done", last_result="Skipped by user.", proposed_change=None)
    return {"status": "skipped"}


async def snooze_plan(plan_id: str, hours: int = 24) -> dict:
    nxt = _now() + timedelta(hours=hours)
    await _set(plan_id, status="scheduled", next_run_at=nxt.isoformat(sep=" ", timespec="seconds"))
    return {"status": "snoozed", "next_run_at": nxt.isoformat(sep=" ", timespec="seconds")}


async def run_now(plan_id: str) -> dict:
    plan = await get_plan(plan_id)
    if not plan:
        return {"error": "not found"}
    await _set(plan_id, status="running")
    asyncio.create_task(_fire({**plan, "status": "running"}))
    return {"status": "running"}


async def get_plan(plan_id: str) -> dict | None:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM scheduled_plans WHERE id = ?", (plan_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def tick() -> int:
    """Find and fire all due plans. Returns how many were fired."""
    now_s = _now().isoformat(sep=" ", timespec="seconds")
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM scheduled_plans WHERE status = 'scheduled' "
            "AND next_run_at IS NOT NULL AND next_run_at <= ? ORDER BY next_run_at LIMIT 20",
            (now_s,),
        )
        due = [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()
    if not due:
        return 0
    # Claim each (status->running) before firing so a second tick can't double-fire.
    for p in due:
        await _set(p["id"], status="running")

    async def _guarded(p):
        async with _sem:
            await _fire(p)

    # Fire in the background so the tick loop isn't blocked. create_task needs a
    # coroutine, not the Future that gather() returns — wrap it.
    async def _run_all():
        await asyncio.gather(*[_guarded(p) for p in due], return_exceptions=True)

    asyncio.create_task(_run_all())
    logger.info("scheduler fired %d due plan(s)", len(due))
    return len(due)


async def _loop() -> None:
    logger.info("scheduled-plans scheduler started (tick %ds)", _TICK_SECONDS)
    while True:
        try:
            await tick()
        except Exception as e:
            logger.warning("scheduler tick error: %s", e)
        await asyncio.sleep(_TICK_SECONDS)


def start_scheduler() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


def stop_scheduler() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
