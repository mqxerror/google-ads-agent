"""Workflow endpoints — Director-orchestrated multi-agent audits.

POST /api/workflows/run   → stream the full workflow (SSE)
GET  /api/workflows/runs  → list past runs for an account
GET  /api/workflows/runs/{run_id} → one run + all its phase reports
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import get_db
from app.services.workflow_orchestrator import run_workflow

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowRunRequest(BaseModel):
    account_id: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    goal: str = (
        "Full daily + weekly + ad-copy audit, then team-reconcile the three "
        "reports into one prioritised action plan, resolving any conflicts."
    )
    budget: float | None = None
    timeframe: str | None = None  # daily | weekly | monthly | quarterly | yearly | lifetime


@router.post("/run")
async def start_workflow(body: WorkflowRunRequest) -> StreamingResponse:
    """Run the workflow and stream phase/agent events as SSE."""

    async def event_stream():
        try:
            async for event in run_workflow(
                goal=body.goal,
                account_id=body.account_id,
                campaign_id=body.campaign_id,
                campaign_name=body.campaign_name,
                budget=body.budget,
                timeframe=body.timeframe,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:  # pragma: no cover — defensive
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs")
async def list_runs(
    account_id: str = Query(...),
    campaign_id: str | None = Query(None),
    limit: int = Query(20),
) -> list[dict]:
    db = await get_db()
    try:
        conds = ["account_id = ?"]
        params: list = [account_id]
        if campaign_id:
            conds.append("campaign_id = ?")
            params.append(campaign_id)
        params.append(limit)
        cur = await db.execute(
            f"SELECT id, account_id, campaign_id, campaign_name, goal, status, "
            f"timeframe, cost, budget, created_at, updated_at, "
            f"(final_output IS NOT NULL AND final_output != '') AS has_output "
            f"FROM workflow_runs WHERE {' AND '.join(conds)} "
            f"ORDER BY created_at DESC LIMIT ?",
            params,
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM workflow_runs WHERE id = ?", (run_id,))
        run = await cur.fetchone()
        if not run:
            return {"error": "not found"}
        cur = await db.execute(
            "SELECT phase, role_id, role_name, task, content, cost, seq, created_at "
            "FROM workflow_reports WHERE run_id = ? ORDER BY seq, created_at",
            (run_id,),
        )
        reports = [dict(r) for r in await cur.fetchall()]
        run_d = dict(run)
        if run_d.get("plan_json"):
            try:
                run_d["plan"] = json.loads(run_d["plan_json"])
            except Exception:
                pass
        run_d["reports"] = reports
        return run_d
    finally:
        await db.close()
