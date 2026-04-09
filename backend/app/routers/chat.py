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
from app.services.agent import stream_agent_response, stop_agent
from app.services.guidelines import GuidelinesService
from app.services.roles import list_roles, classify_intent, get_role_detail, save_role_override, delete_role_override
from app.config import settings

router = APIRouter(prefix="/api", tags=["chat"])

_guidelines_svc = GuidelinesService(settings.GUIDELINES_DIR)


# ── Conversations CRUD ──────────────────────────────────────────────


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    account_id: str | None = Query(None),
    campaign_id: str | None = Query(None),
) -> list[ConversationResponse]:
    db = await get_db()
    try:
        conditions = []
        params: list = []
        if account_id:
            conditions.append("account_id = ?")
            params.append(account_id)
        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur = await db.execute(
            f"SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as message_count "
            f"FROM conversations c {where} ORDER BY c.updated_at DESC LIMIT 50",
            params,
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
                message_count=r["message_count"],
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
        column_names = [desc[0] for desc in cur.description] if cur.description else []
        has_agent_role = "agent_role" in column_names
        return [
            ChatMessageResponse(
                id=r["id"],
                conversation_id=r["conversation_id"],
                role=r["role"],
                content=r["content"],
                created_at=r["created_at"] or "",
                agent_role=r["agent_role"] if has_agent_role else None,
                agent_role_name=r["agent_role_name"] if has_agent_role else None,
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
        agent_role_id: str | None = None
        agent_role_name: str | None = None

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
            elif event.get("type") == "routing":
                agent_role_id = event.get("role_id")
                agent_role_name = event.get("role_name")

        # Persist the full assistant response with role attribution
        full_text = "".join(full_text_parts)
        if full_text:
            db2 = await get_db()
            try:
                await db2.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, tool_input, agent_role, agent_role_name) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        assistant_msg_id,
                        conversation_id,
                        "assistant",
                        full_text,
                        json.dumps(tool_calls_json) if tool_calls_json else None,
                        agent_role_id,
                        agent_role_name,
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


@router.post("/conversations/{conversation_id}/stop")
async def stop_agent_task(conversation_id: str) -> dict:
    """Abort a running agent subprocess for this conversation."""
    stopped = stop_agent(conversation_id)
    return {"stopped": stopped}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    """Delete a conversation and its messages."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await db.commit()
        return {"deleted": True}
    finally:
        await db.close()


@router.get("/conversations/search")
async def search_conversations(
    q: str = Query(..., min_length=1),
    account_id: str | None = Query(None),
):
    """Full-text search across conversation messages using FTS5."""
    db = await get_db()
    try:
        # Build query with optional account filter
        if account_id:
            cur = await db.execute(
                """SELECT m.id as message_id, m.conversation_id, m.content, m.created_at,
                          c.title, c.campaign_name, c.account_id
                   FROM messages_fts fts
                   JOIN messages m ON m.rowid = fts.rowid
                   JOIN conversations c ON c.id = m.conversation_id
                   WHERE messages_fts MATCH ? AND c.account_id = ?
                   ORDER BY rank
                   LIMIT 20""",
                (q, account_id),
            )
        else:
            cur = await db.execute(
                """SELECT m.id as message_id, m.conversation_id, m.content, m.created_at,
                          c.title, c.campaign_name, c.account_id
                   FROM messages_fts fts
                   JOIN messages m ON m.rowid = fts.rowid
                   JOIN conversations c ON c.id = m.conversation_id
                   WHERE messages_fts MATCH ?
                   ORDER BY rank
                   LIMIT 20""",
                (q,),
            )
        rows = await cur.fetchall()
        results = []
        for r in rows:
            content = r["content"]
            # Create snippet around the match
            snippet = content[:200] + ("..." if len(content) > 200 else "")
            results.append({
                "message_id": r["message_id"],
                "conversation_id": r["conversation_id"],
                "content_snippet": snippet,
                "campaign_name": r["campaign_name"],
                "title": r["title"],
                "created_at": r["created_at"] or "",
            })
        return results
    except Exception as e:
        # FTS5 might not have data yet
        return []
    finally:
        await db.close()


# ── Roles ──────────────────────────────────────────────────────────


@router.get("/roles")
async def get_available_roles():
    return {"roles": list_roles()}


@router.get("/roles/{role_id}")
async def get_role_details(role_id: str):
    detail = get_role_detail(role_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Role not found")
    return detail


@router.put("/roles/{role_id}")
async def update_role(role_id: str):
    """Update a role's system prompt, name, or specialty."""
    import json
    from starlette.requests import Request
    # Read raw body since we don't have a schema for this
    # The frontend sends { name?, specialty?, system_prompt?, avatar? }
    detail = get_role_detail(role_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"status": "use_put_with_body"}


@router.post("/roles/{role_id}/customize")
async def customize_role(role_id: str, body: dict):
    """Customize a role's prompt, name, or specialty. Saves to data/roles/{role_id}.md."""
    detail = get_role_detail(role_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Role not found")
    save_role_override(role_id, body)
    return {"status": "saved", "role_id": role_id}


@router.delete("/roles/{role_id}/customize")
async def reset_role(role_id: str):
    """Reset a role to its default prompt."""
    deleted = delete_role_override(role_id)
    return {"status": "reset" if deleted else "no_override", "role_id": role_id}


@router.post("/roles/classify")
async def classify_message_intent(body: ChatMessageRequest):
    return classify_intent(body.content)


# ── Tool confirmation ──────────────────────────────────────────────


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
