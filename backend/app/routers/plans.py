"""Scheduled Plans endpoints.

CRUD + lifecycle for the Scheduled Plans feature. The scheduler service
(app/services/scheduler.py) fires due plans; these endpoints create/list them
and drive the approve / skip / snooze / run-now / pause lifecycle the UI needs.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.database import get_db
from app.services import scheduler

router = APIRouter(prefix="/api/plans", tags=["plans"])


class PlanCreate(BaseModel):
    account_id: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    conversation_id: str | None = None
    title: str
    action_detail: str
    context_snippet: str | None = None
    action_category: str = "other"
    mode: str | None = None              # auto | approval; inferred if omitted
    schedule_type: str = "once"          # once | recurring
    run_at: str | None = None            # ISO datetime (once)
    recurrence: str | None = None        # e.g. weekly:mon:09:00 (recurring)
    timezone: str = "UTC"
    created_by: str = "user"


class PlanPatch(BaseModel):
    title: str | None = None
    action_detail: str | None = None
    action_category: str | None = None
    mode: str | None = None
    run_at: str | None = None
    recurrence: str | None = None
    status: str | None = None            # only for pause/resume (paused|scheduled)


class ExtractRequest(BaseModel):
    account_id: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    text: str                            # the chat message to turn into a plan


def _row(r) -> dict:
    return dict(r)


@router.post("")
async def create_plan(body: PlanCreate) -> dict:
    pid = str(uuid.uuid4())
    mode = body.mode or scheduler.infer_mode(body.action_category)
    # Resolve first fire time.
    if body.schedule_type == "recurring":
        nxt = scheduler.compute_next_run(body.recurrence)
        next_run = nxt.isoformat(sep=" ", timespec="seconds") if nxt else None
    else:
        next_run = (body.run_at or "").replace("T", " ").replace("Z", "").strip() or None
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO scheduled_plans
               (id, account_id, campaign_id, campaign_name, conversation_id, title,
                action_detail, context_snippet, action_category, mode, schedule_type,
                run_at, recurrence, timezone, status, next_run_at, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'scheduled',?,?)""",
            (pid, body.account_id, body.campaign_id, body.campaign_name, body.conversation_id,
             body.title, body.action_detail, body.context_snippet, body.action_category, mode,
             body.schedule_type, next_run if body.schedule_type == "once" else None,
             body.recurrence, body.timezone, next_run, body.created_by),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM scheduled_plans WHERE id = ?", (pid,))
        return _row(await cur.fetchone())
    finally:
        await db.close()


@router.get("")
async def list_plans(account_id: str = Query(...), campaign_id: str | None = Query(None)) -> list[dict]:
    db = await get_db()
    try:
        conds, params = ["account_id = ?"], [account_id]
        if campaign_id:
            conds.append("campaign_id = ?"); params.append(campaign_id)
        cur = await db.execute(
            f"SELECT * FROM scheduled_plans WHERE {' AND '.join(conds)} "
            f"ORDER BY (status IN ('awaiting_approval','failed')) DESC, next_run_at IS NULL, next_run_at",
            params,
        )
        return [_row(r) for r in await cur.fetchall()]
    finally:
        await db.close()


@router.get("/upcoming")
async def upcoming(account_id: str = Query(...), limit: int = Query(50)) -> list[dict]:
    """Cross-campaign timeline for the dashboard."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, campaign_id, campaign_name, title, action_category, mode, status, "
            "schedule_type, recurrence, next_run_at FROM scheduled_plans "
            "WHERE account_id = ? AND status NOT IN ('done') "
            "ORDER BY (status IN ('awaiting_approval','failed')) DESC, next_run_at IS NULL, next_run_at LIMIT ?",
            (account_id, limit),
        )
        return [_row(r) for r in await cur.fetchall()]
    finally:
        await db.close()


@router.get("/{plan_id}")
async def get_plan(plan_id: str) -> dict:
    plan = await scheduler.get_plan(plan_id)
    if not plan:
        return {"error": "not found"}
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT status, result, cost, started_at, finished_at FROM scheduled_plan_runs "
            "WHERE plan_id = ? ORDER BY started_at DESC LIMIT 20", (plan_id,))
        plan["runs"] = [_row(r) for r in await cur.fetchall()]
    finally:
        await db.close()
    return plan


@router.patch("/{plan_id}")
async def patch_plan(plan_id: str, body: PlanPatch) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        return await get_plan(plan_id)
    # If schedule changed, recompute next_run_at.
    if "recurrence" in fields:
        nxt = scheduler.compute_next_run(fields["recurrence"])
        fields["next_run_at"] = nxt.isoformat(sep=" ", timespec="seconds") if nxt else None
    elif "run_at" in fields:
        fields["next_run_at"] = fields["run_at"].replace("T", " ").replace("Z", "").strip()
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
    return await get_plan(plan_id)


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str) -> dict:
    db = await get_db()
    try:
        await db.execute("DELETE FROM scheduled_plan_runs WHERE plan_id = ?", (plan_id,))
        await db.execute("DELETE FROM scheduled_plans WHERE id = ?", (plan_id,))
        await db.commit()
    finally:
        await db.close()
    return {"deleted": plan_id}


@router.post("/{plan_id}/approve")
async def approve(plan_id: str) -> dict:
    return await scheduler.approve_plan(plan_id)


@router.post("/{plan_id}/skip")
async def skip(plan_id: str) -> dict:
    return await scheduler.skip_plan(plan_id)


@router.post("/{plan_id}/snooze")
async def snooze(plan_id: str, hours: int = Query(24)) -> dict:
    return await scheduler.snooze_plan(plan_id, hours)


@router.post("/{plan_id}/run-now")
async def run_now(plan_id: str) -> dict:
    return await scheduler.run_now(plan_id)


@router.post("/extract")
async def extract(body: ExtractRequest) -> dict:
    """Turn a chat message into a prefilled plan draft (title, action, category,
    suggested date). Cheap Haiku call; the UI lets the user edit before saving."""
    from app.services.agent import stream_agent_response
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = (
        "Extract a single schedulable action from this agent message. Respond with "
        "ONLY JSON: {\"title\": short label, \"action_detail\": the instruction to run, "
        "\"action_category\": one of budget|bids|status|geo|search_terms|audit|report|other, "
        "\"suggested_run_at\": YYYY-MM-DD or null, \"recurrence\": null or like 'weekly:mon:09:00'}. "
        f"Today is {today}.\n\nMESSAGE:\n{body.text[:2000]}"
    )
    parts: list[str] = []
    async for ev in stream_agent_response(
        user_message=prompt, account_id=body.account_id,
        campaign_id=body.campaign_id, campaign_name=body.campaign_name,
        model="haiku", active_role="director", tool_allowlist=[],
    ):
        if ev.get("type") == "text":
            parts.append(ev.get("content", ""))
    raw = "".join(parts)
    draft = {"title": "", "action_detail": body.text[:300], "action_category": "other",
             "suggested_run_at": None, "recurrence": None}
    try:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            parsed = json.loads(m.group(0))
            draft.update({k: parsed.get(k, draft[k]) for k in draft})
    except Exception:
        pass
    draft["mode"] = scheduler.infer_mode(draft.get("action_category"))
    return draft
