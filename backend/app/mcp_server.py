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
