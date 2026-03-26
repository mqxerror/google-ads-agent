"""Chat / conversation endpoints — real Claude Code SDK agent."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.models.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationCreateRequest,
    ConversationResponse,
    ToolConfirmRequest,
)
from app.services.agent import stream_agent_response
from app.services.guidelines import GuidelinesService
from app.config import settings

router = APIRouter(prefix="/api", tags=["chat"])

_guidelines_svc = GuidelinesService(settings.GUIDELINES_DIR)


# ── Conversations CRUD ──────────────────────────────────────────────


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations() -> list[ConversationResponse]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        )
        rows = await cur.fetchall()
        return [
            ConversationResponse(
                id=r["id"],
                account_id=r["account_id"],
                campaign_id=r["campaign_id"],
                campaign_name=r["campaign_name"],
                title=r["title"],
                created_at=r["created_at"] or "",
                updated_at=r["updated_at"] or "",
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(body: ConversationCreateRequest) -> ConversationResponse:
    conv_id = str(uuid.uuid4())
    title = body.title or "New conversation"
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO conversations (id, account_id, campaign_id, campaign_name, title) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, body.account_id, body.campaign_id, body.campaign_name, title),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    return ConversationResponse(
        id=row["id"],
        account_id=row["account_id"],
        campaign_id=row["campaign_id"],
        campaign_name=row["campaign_name"],
        title=row["title"],
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


# ── Messages ────────────────────────────────────────────────────────


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ChatMessageResponse],
)
async def list_messages(conversation_id: str) -> list[ChatMessageResponse]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        rows = await cur.fetchall()
        return [
            ChatMessageResponse(
                id=r["id"],
                conversation_id=r["conversation_id"],
                role=r["role"],
                content=r["content"],
                created_at=r["created_at"] or "",
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/conversations/{conversation_id}/message")
async def send_message(
    conversation_id: str,
    body: ChatMessageRequest,
) -> StreamingResponse:
    """Send a user message and stream back the AI agent response via SSE."""
    # Persist user message
    user_msg_id = str(uuid.uuid4())
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        conv = await cur.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
            (user_msg_id, conversation_id, "user", body.content),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
    finally:
        await db.close()

    # Load guidelines for context injection
    account_id = body.account_id or conv["account_id"]
    campaign_id = body.campaign_id or conv["campaign_id"]
    campaign_name = conv["campaign_name"]

    base_guidelines = None
    campaign_guidelines_text = None
    try:
        # Try to load the main guidelines file
        files = await _guidelines_svc.list_files()
        for f in files:
            fn = f["filename"]
            if "campaign_guidelines" in fn.lower() or "guidelines" in fn.lower():
                content = await _guidelines_svc.read_file(fn)
                global_rules = _guidelines_svc.get_global_rules(content)
                if global_rules:
                    base_guidelines = global_rules
                if campaign_name:
                    section = _guidelines_svc.get_campaign_section(content, campaign_name)
                    if section:
                        campaign_guidelines_text = section
                break
    except Exception:
        pass

    # Stream agent response
    async def event_stream():
        assistant_msg_id = str(uuid.uuid4())
        full_text_parts: list[str] = []
        tool_calls_json: list[dict] = []

        async for event in stream_agent_response(
            user_message=body.content,
            account_id=account_id,
            campaign_name=campaign_name,
            conversation_id=conversation_id,
            base_guidelines=base_guidelines,
            campaign_guidelines=campaign_guidelines_text,
            model=body.model or "sonnet",
        ):
            # Forward each event as SSE
            yield f"data: {json.dumps(event)}\n\n"

            # Accumulate for persistence
            if event.get("type") == "text":
                full_text_parts.append(event.get("content", ""))
            elif event.get("type") == "tool_call":
                tool_calls_json.append(event)

        # Persist the full assistant response
        full_text = "".join(full_text_parts)
        if full_text:
            db2 = await get_db()
            try:
                await db2.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, tool_input) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        assistant_msg_id,
                        conversation_id,
                        "assistant",
                        full_text,
                        json.dumps(tool_calls_json) if tool_calls_json else None,
                    ),
                )
                await db2.commit()
            finally:
                await db2.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Tool confirmation ───────────────────────────────────────────────


@router.post("/conversations/{conversation_id}/confirm/{tool_call_id}")
async def confirm_tool_call(
    conversation_id: str,
    tool_call_id: str,
    body: ToolConfirmRequest,
) -> dict:
    return {
        "conversation_id": conversation_id,
        "tool_call_id": tool_call_id,
        "approved": body.approved,
        "status": "acknowledged",
    }
