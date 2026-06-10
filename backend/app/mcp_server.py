"""
MCP server — exposes this app's conversations/messages to remote Claude
Code sessions over Streamable HTTP at /mcp.

Use case:
  - User chats with a persona (GTM Specialist, PPC Strategist, etc.) here.
  - Persona produces a plan or recommendation.
  - User clicks "Send to Claude Code" in the React UI, which calls
    POST /api/conversations/{id}/handoff and sets awaits_claude_code=1.
  - Claude Code (running on the user's MacBook with SSH + repo access)
    polls via list_conversations(awaits_claude_code=True), reads the
    full thread with get_conversation(), executes the work against the
    actual infrastructure, and posts the result back via post_message().
  - Once done, Claude Code calls resolve_handoff() to clear the flag.

The "claude-code" persona is virtual — it has no system prompt or LLM
backing inside this app. Messages with agent_role='claude_code' render
in the UI like any other agent reply.

Auth: bearer token via the MERCAN_MCP_TOKEN env var (auto-generated if
unset; the token is logged at startup so you can paste it into
`claude mcp add ... --header 'Authorization: Bearer ...'`).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database import get_db
from app.services.roles import ROLES

logger = logging.getLogger(__name__)

# ── Auth ──────────────────────────────────────────────────────────────
# Load .env explicitly: pydantic-settings only assigns to declared fields,
# but we want MERCAN_MCP_TOKEN to be readable from .env without adding it
# to the Settings model.
# mcp_server.py is at backend/app/mcp_server.py — .env is at backend/.env
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_ROOT / ".env", override=False)

MCP_TOKEN = os.environ.get("MERCAN_MCP_TOKEN") or secrets.token_urlsafe(32)


# ── Server ────────────────────────────────────────────────────────────

mcp = FastMCP("google-ads-agent")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool
async def list_conversations(
    limit: int = 20,
    account_id: str | None = None,
    awaits_claude_code: bool | None = None,
) -> str:
    """List conversations. Filter to handoffs awaiting Claude Code with
    awaits_claude_code=true. Defaults to the 20 most-recently-updated."""
    db = await get_db()
    q = (
        "SELECT id, account_id, campaign_id, campaign_name, title, "
        "created_at, updated_at, awaits_claude_code, handoff_note "
        "FROM conversations WHERE 1=1"
    )
    args: list = []
    if account_id:
        q += " AND account_id = ?"
        args.append(account_id)
    if awaits_claude_code:
        q += " AND awaits_claude_code = 1"
    q += " ORDER BY updated_at DESC LIMIT ?"
    args.append(min(int(limit), 100))

    rows: list[dict] = []
    async with db.execute(q, args) as cursor:
        async for r in cursor:
            rows.append(dict(r))
    return json.dumps(rows, indent=2, default=str)


@mcp.tool
async def get_conversation(conversation_id: str) -> str:
    """Read the conversation metadata + all messages in the thread."""
    db = await get_db()
    async with db.execute(
        "SELECT * FROM conversations WHERE id = ?", [conversation_id]
    ) as cur:
        conv_row = await cur.fetchone()
    if not conv_row:
        return json.dumps({"error": "conversation not found", "conversation_id": conversation_id})
    conv = dict(conv_row)

    messages: list[dict] = []
    async with db.execute(
        "SELECT id, role, content, agent_role, agent_role_name, "
        "tool_name, tool_input, tool_output, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        [conversation_id],
    ) as cur:
        async for r in cur:
            messages.append(dict(r))

    return json.dumps(
        {"conversation": conv, "messages": messages},
        indent=2,
        default=str,
    )


@mcp.tool
async def post_message(conversation_id: str, content: str) -> str:
    """Post a message into the thread as the 'claude_code' persona. Content
    is markdown. Updates the conversation's updated_at timestamp so the
    message appears at the top of the user's conversation list."""
    db = await get_db()
    msg_id = "msg_" + secrets.token_hex(8)
    now = _utc_iso()
    await db.execute(
        "INSERT INTO messages "
        "(id, conversation_id, role, content, agent_role, agent_role_name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            msg_id,
            conversation_id,
            "assistant",
            content,
            "claude_code",
            "Claude Code (Wassim's terminal)",
            now,
        ],
    )
    await db.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        [now, conversation_id],
    )
    await db.commit()
    return json.dumps({"posted_message_id": msg_id, "conversation_id": conversation_id})


@mcp.tool
async def resolve_handoff(conversation_id: str) -> str:
    """Clear the awaits_claude_code flag on a conversation. Call this once
    you've responded to a handoff so the chat UI stops showing the pending
    indicator."""
    db = await get_db()
    await db.execute(
        "UPDATE conversations SET awaits_claude_code = 0, handoff_note = NULL WHERE id = ?",
        [conversation_id],
    )
    await db.commit()
    return json.dumps({"resolved": conversation_id})


@mcp.tool
async def list_personas() -> str:
    """List the personas defined in services/roles.py — id, display name,
    specialty (one-line role description), and tools_focus. Useful when
    you want to mimic the same agent voice in your post_message reply."""
    rows = [
        {
            "id": r.id,
            "name": r.name,
            "specialty": r.specialty,
            "tools_focus": list(r.tools_focus),
        }
        for r in ROLES.values()
    ]
    return json.dumps(rows, indent=2)


# ── Scheduled Plans tools (Epic 9) ───────────────────────────────────
# Mirror routers/plans.py + services/scheduler.py so plans can be created,
# inspected, and approved from ANY Claude Code session — the "schedule from
# anywhere" unlock. Money/structural categories (budget|bids|status|geo)
# default to approval mode: the scheduler proposes, a human approves.


@mcp.tool
async def create_plan(
    account_id: str,
    title: str,
    action_detail: str,
    campaign_id: str | None = None,
    campaign_name: str | None = None,
    action_category: str = "other",
    schedule_type: str = "once",
    run_at: str | None = None,
    recurrence: str | None = None,
    mode: str | None = None,
    context_snippet: str | None = None,
) -> str:
    """Schedule an action the agent will execute (or propose for approval) at a
    set time. action_category: budget|bids|status|geo|search_terms|audit|report|other
    (budget/bids/status/geo are approval-gated by default — they never spend
    before a human approves). schedule_type 'once' needs run_at (ISO datetime,
    UTC); 'recurring' needs recurrence like 'daily:09:00', 'weekly:mon:09:00',
    or 'monthly:15:09:00'. mode overrides the inferred auto|approval."""
    import uuid as _uuid
    from app.services import scheduler as _sched

    pid = str(_uuid.uuid4())
    resolved_mode = mode or _sched.infer_mode(action_category)
    if schedule_type == "recurring":
        nxt = _sched.compute_next_run(recurrence)
        next_run = nxt.isoformat(sep=" ", timespec="seconds") if nxt else None
    else:
        next_run = (run_at or "").replace("T", " ").replace("Z", "").strip() or None
    if not next_run:
        return json.dumps({"error": "no valid run time — give run_at (once) or recurrence (recurring)"})
    db = await get_db()
    await db.execute(
        """INSERT INTO scheduled_plans
           (id, account_id, campaign_id, campaign_name, title, action_detail,
            context_snippet, action_category, mode, schedule_type, run_at,
            recurrence, status, next_run_at, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'scheduled',?,'mcp')""",
        [pid, account_id, campaign_id, campaign_name, title, action_detail,
         context_snippet, action_category, resolved_mode, schedule_type,
         next_run if schedule_type == "once" else None, recurrence, next_run],
    )
    await db.commit()
    return json.dumps({
        "created": pid, "mode": resolved_mode, "next_run_at": next_run,
        "note": "approval-gated — the agent will propose the change and wait for sign-off"
                if resolved_mode == "approval" else "auto — executes at the scheduled time",
    })


@mcp.tool
async def list_plans(
    account_id: str,
    campaign_id: str | None = None,
    include_done: bool = False,
) -> str:
    """List scheduled plans (needs-attention first). Shows status
    (scheduled|due|running|awaiting_approval|done|failed|paused), mode,
    next run, last result, and any proposed_change awaiting approval."""
    db = await get_db()
    q = ("SELECT id, campaign_id, campaign_name, title, action_category, mode, "
         "schedule_type, recurrence, status, next_run_at, last_run_at, "
         "last_result, last_cost, proposed_change FROM scheduled_plans "
         "WHERE account_id = ?")
    args: list = [account_id]
    if campaign_id:
        q += " AND campaign_id = ?"
        args.append(campaign_id)
    if not include_done:
        q += " AND status != 'done'"
    q += (" ORDER BY (status IN ('awaiting_approval','failed')) DESC, "
          "next_run_at IS NULL, next_run_at LIMIT 100")
    rows: list[dict] = []
    async with db.execute(q, args) as cur:
        async for r in cur:
            d = dict(r)
            # Keep long text fields readable in tool output
            for k in ("last_result", "proposed_change"):
                if d.get(k) and len(d[k]) > 600:
                    d[k] = d[k][:600] + "…"
            rows.append(d)
    return json.dumps(rows, indent=2, default=str)


@mcp.tool
async def approve_plan(plan_id: str) -> str:
    """Approve a plan that is awaiting_approval — the agent then EXECUTES the
    proposed change (spend/structural changes only happen after this)."""
    from app.services import scheduler as _sched
    result = await _sched.approve_plan(plan_id)
    return json.dumps(result, default=str)


@mcp.tool
async def skip_plan(plan_id: str) -> str:
    """Decline a plan awaiting approval (or skip its current cycle). Recurring
    plans re-arm to their next scheduled slot; one-time plans close as done."""
    from app.services import scheduler as _sched
    result = await _sched.skip_plan(plan_id)
    return json.dumps(result, default=str)


@mcp.tool
async def run_plan_now(plan_id: str) -> str:
    """Fire a plan immediately instead of waiting for its schedule. Approval-
    gated plans still only PROPOSE (then await approval) — they never spend
    unapproved."""
    from app.services import scheduler as _sched
    result = await _sched.run_now(plan_id)
    return json.dumps(result, default=str)


# ── Auth middleware ───────────────────────────────────────────────────


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject any request whose Authorization header isn't 'Bearer <token>'."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self.token}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


# ── Mount onto FastAPI ────────────────────────────────────────────────
#
# FastMCP's streamable HTTP transport uses an internal anyio task group
# that must be initialised during the parent ASGI app's startup. We do
# that by chaining mcp_app.lifespan into the parent FastAPI's lifespan
# (see main.py). The mcp_app instance is created once at import time so
# both main.py and mount_mcp() reference the same object.

mcp_app = mcp.http_app(path="/")
mcp_app.add_middleware(BearerAuthMiddleware, token=MCP_TOKEN)

# Exported so main.py can do `async with mcp_lifespan(app):` inside its
# own lifespan contextmanager.
mcp_lifespan = mcp_app.lifespan


def mount_mcp(app: FastAPI) -> str:
    """Mount the pre-built MCP ASGI sub-app at /mcp on the given FastAPI
    instance. The parent app MUST chain `mcp_lifespan` into its lifespan
    or requests will 500 with 'task group not initialized'.

    Returns the auth token so the caller can log it on startup.
    """
    app.mount("/mcp", mcp_app)
    logger.info("MCP server mounted at /mcp (bearer auth required)")
    return MCP_TOKEN
