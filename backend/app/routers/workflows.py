"""Workflow endpoints — Director-orchestrated multi-agent audits.

POST /api/workflows/run              → run + stream the workflow (SSE)
POST /api/workflows/runs/{id}/stop   → cooperatively cancel a running run
GET  /api/workflows/runs             → list past runs for an account
GET  /api/workflows/runs/{run_id}    → one run + all its phase reports

Homepage read model (Story 13.2):
GET  /api/accounts/{account_id}/account-report → latest account audit + fast
                                                  signals + staleness metadata

Account mode (Story 13.1): POST /run with campaign_id=null (and no
campaign_name) runs the Team Audit ACCOUNT-WIDE — the Director plans across
active campaigns (capped by WORKFLOW_MAX_CAMPAIGNS, highest recent spend
first), specialists fan out per campaign, and synthesis emits ONE ranked
account report with structured findings. The completed report persists as the
LATEST account report (`account_reports` table) so the homepage reads it in
<1s with zero Google Ads calls. Account runs are analysis-only.

RELIABILITY (Story 13.2): execution is DECOUPLED from the SSE stream — the run
executes in a detached background task (`workflow_runner.start`) that runs to
completion regardless of client connection; the SSE endpoint is a VIEWER that
tails the run's events (`workflow_runner.subscribe`). Closing the stream does
NOT cancel the run. A startup + periodic sweeper reaps orphaned "running"
zombies. See app/services/workflow_runner.py.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import get_db
from app.services import account_report_store, fast_signals, finding_actions, workflow_runner
from app.services import metrics_store
from app.services.freshness import compute_freshness

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowRunRequest(BaseModel):
    account_id: str
    campaign_id: str | None = None   # None (with no campaign_name) → account-wide audit
    campaign_name: str | None = None
    goal: str = (
        "Full daily + weekly + ad-copy audit, then team-reconcile the three "
        "reports into one prioritised action plan, resolving any conflicts."
    )
    budget: float | None = None
    timeframe: str | None = None  # daily | weekly | monthly | quarterly | yearly | lifetime


@router.post("/run")
async def start_workflow(body: WorkflowRunRequest) -> StreamingResponse:
    """Launch the workflow in a detached background task, then stream its
    events as SSE. Execution survives a client disconnect — the stream is a
    viewer over the run's event hub, not the run itself."""

    # Start the run (returns once the run_id is known — a few ms). If it fails
    # to start at all, surface that as a one-shot error event so the client
    # isn't left hanging.
    try:
        run_id = await workflow_runner.start(
            goal=body.goal,
            account_id=body.account_id,
            campaign_id=body.campaign_id,
            campaign_name=body.campaign_name,
            budget=body.budget,
            timeframe=body.timeframe,
        )
    except Exception as e:  # pragma: no cover — defensive
        async def _err_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return StreamingResponse(_err_stream(), media_type="text/event-stream")

    async def event_stream():
        # Tail the run's events (replay buffer + live). The orchestrator already
        # emitted workflow_start into the hub before start() returned, so the
        # client sees the full run from the beginning — same event shape as before.
        async for event in workflow_runner.subscribe(run_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict:
    """Cooperatively cancel a running workflow and mark the row stopped."""
    return await workflow_runner.stop(run_id)


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
            f"timeframe, cost, budget, stop_reason, created_at, updated_at, "
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


# ── Homepage read model (Story 13.2) ──────────────────────────────────
# A SEPARATE router (no /api/workflows prefix) so the path reads naturally as
# an account resource. Mounted alongside the workflows router in main.py.

account_router = APIRouter(prefix="/api/accounts", tags=["account-report"])


@account_router.get("/{account_id}/account-report")
async def get_account_report(
    account_id: str,
    include_signals: bool = Query(True),
) -> dict:
    """Latest persisted account audit + always-fresh fast signals + staleness.

    Answers from local SQLite only — zero Google Ads calls, zero agent runs.
    When no audit exists yet, `report.exists` is False (the homepage collapses
    to its zero-state). Fast signals are computed live-but-local every call, so
    the fix-list strip has fresh pacing/waste/approval items even before the
    first deep audit runs.
    """
    report = await account_report_store.get_latest(account_id)
    payload: dict = {"account_id": account_id, "report": report}
    if include_signals:
        payload["fast_signals"] = await fast_signals.get_signals(account_id)
    payload["freshness"] = await compute_freshness(account_id)
    # Self-heal (A4): after answering from SQLite, kick a background refresh if
    # the data is stale. Non-blocking — the payload above is already built.
    from app.services.sync_engine import maybe_kick_sync
    await maybe_kick_sync(account_id)
    return payload


# ── Findings → approvable actions (Story 13.3) ────────────────────────
# The fix-list strip: each persisted finding + fast-signal becomes a concrete
# proposed ACTION, and the three buttons (Approve / Approve once / Deny) route
# through the EXISTING plan/approval + scope-guard path — never a direct write.


class FindingDecision(BaseModel):
    decision: str            # approve | approve_once | deny


@account_router.get("/{account_id}/actions")
async def list_account_actions(
    account_id: str,
    include_denied: bool = Query(False),
) -> dict:
    """Money-ranked fix list for the homepage: every finding/fast-signal as a
    proposed action + its decision state (proposed / approved / denied).

    Denied items are suppressed by default; advisory (non-automatable) findings
    are present but flagged `actionable: false` (info only, no Approve button).
    Answers from local SQLite — zero Google Ads calls."""
    return await finding_actions.list_actions(account_id, include_denied=include_denied)


@account_router.post("/{account_id}/actions/{finding_key}/decide")
async def decide_account_action(
    account_id: str,
    finding_key: str,
    body: FindingDecision,
) -> dict:
    """Apply one of [Approve] [Approve once] [Deny] to a finding.

    approve / approve_once create a Scheduled Plan through the normal lifecycle
    (gated categories park for sign-off; auto categories fire now through the
    scope-guarded path). deny persists a dismissal so the finding stops
    surfacing until a re-audit changes it. Never writes to Google Ads directly.
    """
    return await finding_actions.decide(account_id, finding_key, body.decision)


# ── Period-over-period KPI overview (Story 13.7) ──────────────────────
# The homepage KPI cards: 4 metrics (Spend · Conversions · CPA · Conv rate),
# each = current window value + prior-window value + honest Δ%, plus a per-day
# series for sparklines. Account-wide rollup of ENABLED campaigns, computed
# from local `campaign_daily_metrics` only — zero Google Ads calls.


@account_router.get("/{account_id}/metrics/overview")
async def get_metrics_overview(
    account_id: str,
    days: int = Query(7, ge=1, le=365),
) -> dict:
    """Period-over-period KPI rollup for the homepage cards.

    Returns the 4 KPIs (Spend, Conversions, CPA, Conv rate) for the current
    `days`-length window and the equal window immediately before it, each as
    `{value, prev_value, delta_pct}`, plus a per-day `series` for the current
    window (sparklines). ENABLED campaigns only; local SQLite only.

    Zero-state honest: an empty account returns a valid shape with null values
    (not zeros), CPA/Conv-rate are null when their denominator is 0, and
    `delta_pct` is null whenever the prior window is empty or zero — never a
    fabricated delta, never a divide-by-zero.
    """
    overview = await metrics_store.get_overview(account_id, days=days)
    overview["freshness"] = await compute_freshness(account_id)
    # Self-heal (A4): kick a background refresh if stale (non-blocking).
    from app.services.sync_engine import maybe_kick_sync
    await maybe_kick_sync(account_id)
    return overview


# ── Push updates: per-account SSE event channel (Story C1) ────────────
# The dashboard is stale-by-default; instead of polling, the frontend opens ONE
# EventSource per account and invalidates the affected React-Query caches when an
# event arrives. Events are pushed by the sync engine (`sync_completed`), the
# roster diff (`external_change`), and (future) the plan executor
# (`mutation_applied`) / audits (`audit_completed`). See services/account_events.py.
#
# Event envelope (JSON per `data:` line):
#   {"type": "connected"}                                           on open
#   {"type": "sync_completed", "domain": "metrics",
#    "data_through_date": "2026-07-11"}                             after a sync
#   {"type": "external_change", "count": 3}                         roster diff
# Plus periodic `: keepalive` comment lines (~25s) so idle proxies don't drop
# the connection. The channel is open-ended — it tails until the CLIENT closes.

import asyncio  # noqa: E402  (local to the SSE machinery below)

from app.services import account_events  # noqa: E402

_SSE_KEEPALIVE_SECONDS = 25.0


@account_router.get("/{account_id}/events")
async def account_events_stream(account_id: str) -> StreamingResponse:
    """SSE channel for one account: pushes `sync_completed` / `external_change`
    events so the dashboard refreshes without a reload. Open-ended — tails live
    until the client disconnects."""

    async def event_stream():
        # Announce the connection so the client can flip its "connecting" state.
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        agen = account_events.subscribe(account_id)
        try:
            while True:
                try:
                    # Wait for the next event, but wake every keepalive interval
                    # to emit a comment line so proxies keep the idle stream open.
                    event = await asyncio.wait_for(
                        agen.__anext__(), timeout=_SSE_KEEPALIVE_SECONDS
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except StopAsyncIteration:  # pragma: no cover — subscribe() never ends
                    break
        finally:
            await agen.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@account_router.get("/{account_id}/external-changes")
async def list_account_external_changes(
    account_id: str,
    limit: int = Query(20, ge=1, le=200),
) -> dict:
    """Out-of-band ("changed outside the app") roster changes for AgentActivity.

    Newest-first rows: each is a campaign field (status / bidding_strategy /
    budget_micros) that changed between two roster syncs without an app-side
    mutation — the answer to "why does the account look different?" (Story C5).
    Answers from local SQLite — zero Google Ads calls.
    """
    from app.services import external_change
    changes = await external_change.list_external_changes(account_id, limit=limit)
    return {"account_id": account_id, "external_changes": changes}
