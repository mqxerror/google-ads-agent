"""Chat / conversation endpoints — real Claude Code SDK agent."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict

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
from app.services import chat_runner
from app.services.guidelines import GuidelinesService
from app.services.roles import list_roles, classify_intent, get_role_detail, save_role_override, delete_role_override
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# ── Background agent tasks — survive page refresh ──────────────────
# Each conversation can have one running agent task. Events are buffered
# so the frontend can reconnect and get events it missed.

_agent_tasks: dict[str, asyncio.Task] = {}
_agent_buffers: dict[str, list[dict]] = defaultdict(list)
_agent_done: dict[str, bool] = {}
_agent_cursor: dict[str, int] = defaultdict(int)  # per-connection cursor

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
    stream: int = Query(0),
):
    """Send a user message.

    Default (v2): starts a DIRECT-mode turn via chat_runner in a detached
    background task and returns JSON `{turn_id}` immediately. The client then
    opens `GET .../turns/{turn_id}/stream?cursor=N` to view events.

    Legacy (`?stream=1`): the exact pre-v2 StreamingResponse behavior — the run
    is driven inside `_agent_buffers` and events stream straight from the POST
    response. Kept for one release so old clients don't break.
    """
    # Persist user message
    user_msg_id = str(uuid.uuid4())
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        conv = await cur.fetchone()
        if not conv:
            # Auto-heal a dangling conversation id instead of dead-ending with a
            # 404. This happens when the frontend (e.g. the campaign builder or a
            # ChatPanel restored from localStorage) holds a conversation id that
            # no longer exists server-side — a reset DB, a build started in a
            # prior run, or a conversation row that was never persisted. The
            # request body already carries enough context to recreate the row,
            # so resuming the campaign "just works" rather than 404-looping.
            if not body.account_id:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found and no account_id provided to recreate it",
                )
            await db.execute(
                "INSERT OR IGNORE INTO conversations "
                "(id, account_id, campaign_id, campaign_name, title) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    body.account_id,
                    body.campaign_id,
                    body.campaign_name,
                    "Resumed conversation",
                ),
            )
            await db.commit()
            cur = await db.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            conv = await cur.fetchone()
            logger.warning(
                "Recreated dangling conversation %s (account=%s campaign=%s)",
                conversation_id, body.account_id, body.campaign_id,
            )

        # A conversation is bound to ONE campaign for its lifetime. The binding
        # may only be set/changed while the conversation is still empty (its very
        # first message). Once it has history, the conversation's own campaign is
        # authoritative and is NEVER silently rebound to whatever the client sent
        # — doing that corrupts the thread and leaks one campaign's name + memory
        # into another (the "agent still talks about the old campaign" bug, and
        # the mislabeled "Greece chat bound to Panama" rows in the DB).
        cur = await db.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        msg_count = (await cur.fetchone())["n"]

        if msg_count == 0 and body.campaign_id and body.campaign_id != conv["campaign_id"]:
            # First message — bind the conversation to the selected campaign.
            await db.execute(
                "UPDATE conversations SET campaign_id = ?, campaign_name = COALESCE(?, campaign_name) "
                "WHERE id = ?",
                (body.campaign_id, body.campaign_name, conversation_id),
            )
            cur = await db.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            conv = await cur.fetchone()
        elif not conv["campaign_id"] and body.campaign_id:
            # Conversation has history but was never bound to a campaign (e.g. the
            # user started typing before selecting a campaign, then selected one).
            # Promote it now — null→campaign is always safe; only set→different
            # is forbidden (handled by the next branch). Without this an
            # unbound thread stays orphaned forever and the agent never loads
            # the campaign's chronicle/decisions/role-notes — the "agent forgot
            # after a day" symptom.
            await db.execute(
                "UPDATE conversations SET campaign_id = ?, campaign_name = COALESCE(?, campaign_name) "
                "WHERE id = ?",
                (body.campaign_id, body.campaign_name, conversation_id),
            )
            cur = await db.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            conv = await cur.fetchone()
            logger.info(
                "Promoted unbound conversation %s to campaign %s (%s)",
                conversation_id, body.campaign_id, conv["campaign_name"],
            )
        elif (
            msg_count > 0
            and body.campaign_id
            and conv["campaign_id"]
            and body.campaign_id != conv["campaign_id"]
        ):
            # Stale / cross-campaign client. The conversation's own campaign wins
            # — the frontend should have opened a fresh conversation for the
            # other campaign. Log loudly so any remaining client bug is visible.
            logger.warning(
                "Rejected cross-campaign reuse on conversation %s: client sent "
                "campaign=%s but conversation is bound to %s (%s). Using the "
                "conversation's own campaign so the thread stays consistent.",
                conversation_id, body.campaign_id, conv["campaign_id"],
                conv["campaign_name"],
            )

        # Tag the user message with the conversation's authoritative campaign so
        # the thread (and _get_recent_messages) stays internally consistent.
        message_campaign_id = conv["campaign_id"]
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, campaign_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_msg_id, conversation_id, "user", body.content, message_campaign_id),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
    finally:
        await db.close()

    # Load guidelines for context injection
    # Conversation is authoritative for campaign (see binding rule above) so the
    # agent's campaign context always matches the thread it is replying in.
    account_id = body.account_id or conv["account_id"]
    campaign_id = conv["campaign_id"] or body.campaign_id
    campaign_name = conv["campaign_name"] or body.campaign_name

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

    # ── v2 default path: detached turn via chat_runner → {turn_id} ──────
    # A DIRECT-mode turn wraps today's stream_agent_response in v2 envelopes.
    # run_fn yields BARE {type, payload}; the runner stamps the envelope + seq
    # and persists to chat_turn_events. proc_key=(turn_id, "director") routes a
    # per-turn stop to this single child. Direct-mode payloads stay byte-
    # equivalent to today (the v1 event dict, minus its own "type", becomes the
    # payload). We also persist the assistant message + link it to the turn.
    if not stream:
        _model = body.model or "fable"
        _active_role = getattr(body, "active_role", None)
        _attachments = [a.model_dump() for a in (body.attachments or [])]

        # ── Epic 2: orchestrated turn (opt-in via body.orchestrate) ──────
        # An orchestrated turn runs the §5 state machine (triage → recall →
        # verify → plan → dispatch → resolve → synthesize). run_turn yields
        # BARE {type, payload}; the runner stamps the envelope + persists. The
        # DIRECT path below is UNCHANGED (default when orchestrate is False).
        if body.orchestrate:
            async def _orchestrated_run_fn(*, turn_id: str):
                from app.services import chat_orchestrator  # lazy import
                async for ev in chat_orchestrator.run_turn(
                    turn_id=turn_id,
                    user_message=body.content,
                    account_id=account_id,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    conversation_id=conversation_id,
                    base_guidelines=base_guidelines,
                    campaign_guidelines=campaign_guidelines_text,
                    model=body.model or "fable",
                    force_mode="orchestrate",
                ):
                    yield ev

            turn_id = await chat_runner.start(
                _orchestrated_run_fn,
                conversation_id=conversation_id,
                campaign_id=campaign_id,
                mode="orchestrated",
            )
            return {"turn_id": turn_id}

        async def _direct_run_fn(*, turn_id: str):
            assistant_msg_id = str(uuid.uuid4())
            full_text_parts: list[str] = []
            tool_calls_json: list[dict] = []
            agent_role_id: str | None = None
            agent_role_name: str | None = None
            try:
                async for event in stream_agent_response(
                    user_message=body.content,
                    account_id=account_id,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    conversation_id=conversation_id,
                    base_guidelines=base_guidelines,
                    campaign_guidelines=campaign_guidelines_text,
                    model=_model,
                    active_role=_active_role,
                    attachments=_attachments,
                    proc_key=(turn_id, "director"),
                ):
                    etype = event.get("type", "event")
                    payload = {k: v for k, v in event.items() if k != "type"}
                    if etype in ("text", "text_delta"):
                        full_text_parts.append(event.get("content", ""))
                        # RAW direct-mode client SSE path: relabel token-level
                        # `text_delta` → `text` so existing v1 frontend rendering
                        # is unaffected (story 1.4). text_delta stays distinct
                        # only inside the orchestrator translation.
                        etype = "text"
                    elif etype == "tool_call":
                        tool_calls_json.append(event)
                    elif etype == "routing":
                        agent_role_id = event.get("role_id")
                        agent_role_name = event.get("role_name")
                    # Yield the bare event for the runner to wrap. v1 types flow
                    # untouched inside the envelope (§4.3).
                    yield {"type": etype, "payload": payload}
            finally:
                # Persist the assistant message even if the viewer disconnected —
                # runs inside the detached task, so it survives a closed client.
                full_text = "".join(full_text_parts)
                if full_text:
                    db2 = await get_db()
                    try:
                        await db2.execute(
                            "INSERT INTO messages (id, conversation_id, role, content, tool_input, agent_role, agent_role_name, campaign_id, turn_id) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                assistant_msg_id, conversation_id, "assistant", full_text,
                                json.dumps(tool_calls_json) if tool_calls_json else None,
                                agent_role_id, agent_role_name, campaign_id, turn_id,
                            ),
                        )
                        await db2.commit()
                    finally:
                        await db2.close()

        turn_id = await chat_runner.start(
            _direct_run_fn,
            conversation_id=conversation_id,
            campaign_id=campaign_id,
            mode="direct",
        )
        return {"turn_id": turn_id}

    # ── Legacy ?stream=1 path (unchanged) ───────────────────────────────
    # Run agent in background task — survives page refresh
    async def _run_agent_background(conv_id: str):
        """Run agent and buffer events. Persists response even if frontend disconnects."""
        assistant_msg_id = str(uuid.uuid4())
        full_text_parts: list[str] = []
        tool_calls_json: list[dict] = []
        agent_role_id: str | None = None
        agent_role_name: str | None = None

        try:
            async for event in stream_agent_response(
                user_message=body.content,
                account_id=account_id,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                conversation_id=conv_id,
                base_guidelines=base_guidelines,
                campaign_guidelines=campaign_guidelines_text,
                model=body.model or "fable",
                active_role=getattr(body, 'active_role', None),
                attachments=[a.model_dump() for a in (body.attachments or [])],
            ):
                # RAW v1 client SSE path: relabel token-level `text_delta` →
                # `text` before buffering so existing v1 frontend rendering is
                # unaffected (story 1.4).
                if event.get("type") == "text_delta":
                    event = {**event, "type": "text"}
                _agent_buffers[conv_id].append(event)

                if event.get("type") == "text":
                    full_text_parts.append(event.get("content", ""))
                elif event.get("type") == "tool_call":
                    tool_calls_json.append(event)
                elif event.get("type") == "routing":
                    agent_role_id = event.get("role_id")
                    agent_role_name = event.get("role_name")

            # Persist response — this runs even if frontend disconnected
            full_text = "".join(full_text_parts)
            if full_text:
                db2 = await get_db()
                try:
                    await db2.execute(
                        "INSERT INTO messages (id, conversation_id, role, content, tool_input, agent_role, agent_role_name, campaign_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            assistant_msg_id, conv_id, "assistant", full_text,
                            json.dumps(tool_calls_json) if tool_calls_json else None,
                            agent_role_id, agent_role_name, campaign_id,
                        ),
                    )
                    await db2.commit()
                finally:
                    await db2.close()
        except Exception as e:
            _agent_buffers[conv_id].append({"type": "error", "message": str(e)})
        finally:
            _agent_done[conv_id] = True
            _agent_tasks.pop(conv_id, None)

    # Start background task (or reuse if already running)
    if conversation_id not in _agent_tasks or _agent_tasks[conversation_id].done():
        _agent_buffers[conversation_id] = []
        _agent_done[conversation_id] = False
        _agent_tasks[conversation_id] = asyncio.create_task(
            _run_agent_background(conversation_id)
        )

    # Stream events from buffer — frontend can reconnect anytime
    async def event_stream():
        cursor = 0
        while True:
            # Yield any buffered events we haven't sent yet
            buf = _agent_buffers.get(conversation_id, [])
            while cursor < len(buf):
                yield f"data: {json.dumps(buf[cursor])}\n\n"
                cursor += 1

            # Check if agent is done
            if _agent_done.get(conversation_id, False) and cursor >= len(buf):
                break

            # Wait briefly for more events
            await asyncio.sleep(0.05)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── v2 turn viewer + lifecycle endpoints (Epic 1.2/1.5/1.6) ─────────


async def _get_turn_row(turn_id: str) -> dict | None:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM chat_turns WHERE turn_id = ?", (turn_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


@router.get("/conversations/{conversation_id}/turns/active")
async def list_active_turns(conversation_id: str) -> dict:
    """Active turn(s) for this conversation, for reconnect after a refresh."""
    turns = await chat_runner.active_turns(conversation_id)
    return {"conversation_id": conversation_id, "turns": turns}


@router.get("/conversations/{conversation_id}/turns/{turn_id}/events")
async def list_turn_events(conversation_id: str, turn_id: str) -> dict:
    """Full persisted event list for a turn (history replay). 404 if the turn
    doesn't belong to this conversation (the story-1.6 isolation guarantee)."""
    turn = await _get_turn_row(turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn["conversation_id"] != conversation_id:
        raise HTTPException(status_code=404, detail="Turn does not belong to this conversation")
    events = await chat_runner.get_events(turn_id)
    return {"turn_id": turn_id, "status": turn["status"], "events": events}


@router.get("/conversations/{conversation_id}/turns/{turn_id}/stream")
async def stream_turn(conversation_id: str, turn_id: str, cursor: int = Query(0)):
    """SSE viewer over a turn's hub (replay from cursor, then tail). Closing the
    stream never kills the run. 404 if the turn doesn't belong to `{conversation_id}`
    — cross-conversation subscription is impossible by URL shape (story 1.6)."""
    turn = await _get_turn_row(turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn["conversation_id"] != conversation_id:
        raise HTTPException(status_code=404, detail="Turn does not belong to this conversation")

    async def _stream():
        async for env in chat_runner.subscribe(turn_id, cursor):
            yield f"data: {json.dumps(env)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/conversations/{conversation_id}/turns/{turn_id}/stop")
async def stop_turn_endpoint(conversation_id: str, turn_id: str) -> dict:
    """Per-turn stop (story 1.5). Idempotent: a terminal turn returns
    {status:"already_done"}. 404 if the turn isn't this conversation's."""
    turn = await _get_turn_row(turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn["conversation_id"] != conversation_id:
        raise HTTPException(status_code=404, detail="Turn does not belong to this conversation")
    if turn["status"] != "running":
        return {"turn_id": turn_id, "status": "already_done"}
    return await chat_runner.stop_turn(turn_id)


@router.post("/conversations/{conversation_id}/turns/{turn_id}/calls/{call_id}/stop")
async def stop_call_endpoint(conversation_id: str, turn_id: str, call_id: str) -> dict:
    """Per-specialist stop (story 2.6). Kills one call; the turn continues.
    Idempotent. 404 if the turn isn't this conversation's."""
    turn = await _get_turn_row(turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn["conversation_id"] != conversation_id:
        raise HTTPException(status_code=404, detail="Turn does not belong to this conversation")
    return await chat_runner.stop_call(turn_id, call_id)


# ── Tool confirmation ───────────────────────────────────────────────


@router.post("/conversations/{conversation_id}/stop")
async def stop_agent_task(conversation_id: str) -> dict:
    """Abort a running agent for this conversation.

    Legacy alias: prefers stopping the conversation's active v2 turn(s); falls
    back to the Epic-0 conversation-keyed stop_agent for any legacy in-flight
    run driven through _agent_buffers.
    """
    active = await chat_runner.active_turns(conversation_id)
    stopped_turns = []
    for t in active:
        res = await chat_runner.stop_turn(t["turn_id"])
        stopped_turns.append(res.get("turn_id"))
    # Also fire the legacy conversation-keyed stop so an in-flight ?stream=1 run
    # (or any pre-v2 code path) is covered.
    legacy_stopped = stop_agent(conversation_id)
    return {
        "stopped": bool(stopped_turns) or legacy_stopped,
        "turns_stopped": stopped_turns,
        "legacy_stopped": legacy_stopped,
    }


# ── Claude Code handoff ─────────────────────────────────────────────


@router.post("/conversations/{conversation_id}/handoff")
async def handoff_to_claude_code(conversation_id: str, body: dict | None = None) -> dict:
    """Flag a conversation as awaiting Claude Code (the user's terminal
    session). Claude Code polls list_conversations(awaits_claude_code=true)
    via MCP, reads the thread, executes the work, and posts results back.

    Body: { "note": "optional context for Claude Code" }
    """
    from datetime import datetime, timezone

    note = (body or {}).get("note") if isinstance(body, dict) else None
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    cur = await db.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="conversation not found")
    await db.execute(
        "UPDATE conversations SET awaits_claude_code = 1, handoff_note = ?, updated_at = ? "
        "WHERE id = ?",
        (note, now, conversation_id),
    )
    await db.commit()
    return {"ok": True, "conversation_id": conversation_id, "handoff_note": note}


@router.delete("/conversations/{conversation_id}/handoff")
async def clear_handoff(conversation_id: str) -> dict:
    """Clear a handoff flag (the chat UI can call this if the user changes
    their mind before Claude Code picks it up)."""
    db = await get_db()
    await db.execute(
        "UPDATE conversations SET awaits_claude_code = 0, handoff_note = NULL WHERE id = ?",
        (conversation_id,),
    )
    await db.commit()
    return {"ok": True, "conversation_id": conversation_id}


@router.get("/accounts/{account_id}/conversation-graph")
async def get_conversation_graph(account_id: str) -> dict:
    """Build a conversation graph: campaigns → conversations → decisions."""
    db = await get_db()
    try:
        # Get all conversations for this account
        cur = await db.execute(
            """SELECT c.id, c.campaign_id, c.campaign_name, c.title, c.created_at, c.updated_at,
                      (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
               FROM conversations c WHERE c.account_id = ?
               ORDER BY c.updated_at DESC LIMIT 50""",
            (account_id,),
        )
        conversations = [dict(r) for r in await cur.fetchall()]

        # Get decisions linked to conversations
        cur = await db.execute(
            """SELECT id, campaign_id, conversation_id, action, reason, outcome, role, created_at
               FROM decision_log WHERE account_id = ?
               ORDER BY created_at DESC LIMIT 100""",
            (account_id,),
        )
        decisions = [dict(r) for r in await cur.fetchall()]

        # Get distinct roles used
        cur = await db.execute(
            """SELECT DISTINCT agent_role, agent_role_name FROM messages
               WHERE conversation_id IN (SELECT id FROM conversations WHERE account_id = ?)
               AND agent_role IS NOT NULL AND agent_role != ''""",
            (account_id,),
        )
        roles_used = [{"id": r["agent_role"], "name": r["agent_role_name"]} for r in await cur.fetchall()]

        # Get recommendations with outcomes
        cur = await db.execute(
            """SELECT id, campaign_id, conversation_id, action_type, action_detail, outcome, status, executed_at
               FROM recommendations WHERE account_id = ?
               ORDER BY executed_at DESC LIMIT 50""",
            (account_id,),
        )
        recommendations = [dict(r) for r in await cur.fetchall()]

        # Group by campaign
        campaigns: dict[str | None, dict] = {}
        for conv in conversations:
            camp_id = conv["campaign_id"]
            if camp_id not in campaigns:
                campaigns[camp_id] = {
                    "campaign_id": camp_id,
                    "campaign_name": conv["campaign_name"] or "General",
                    "conversations": [],
                    "decision_count": 0,
                }
            campaigns[camp_id]["conversations"].append({
                "id": conv["id"],
                "title": conv["title"],
                "created_at": conv["created_at"],
                "updated_at": conv["updated_at"],
                "message_count": conv["message_count"],
                "decisions": [d for d in decisions if d.get("conversation_id") == conv["id"]],
                "recommendations": [r for r in recommendations if r.get("conversation_id") == conv["id"]],
            })
            campaigns[camp_id]["decision_count"] += len([d for d in decisions if d.get("conversation_id") == conv["id"]])

        return {
            "campaigns": list(campaigns.values()),
            "stats": {
                "total_conversations": len(conversations),
                "total_decisions": len(decisions),
                "total_recommendations": len(recommendations),
                "roles_used": roles_used,
                "campaigns_count": len([c for c in campaigns if c is not None]),
            },
        }
    finally:
        await db.close()


@router.get("/conversations/{conversation_id}/context-usage")
async def get_context_usage(conversation_id: str) -> dict:
    """Return current context usage stats for a conversation."""
    from app.services.token_counter import estimate_tokens
    from app.services.compaction import get_compaction_status

    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT content FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        )
        rows = await cur.fetchall()
        total_message_tokens = sum(estimate_tokens(r["content"]) for r in rows)
        message_count = len(rows)

        estimated_system_tokens = 15_000
        estimated_data_tokens = 10_000
        total_estimated = total_message_tokens + estimated_system_tokens + estimated_data_tokens

        budget = 200_000
        effective = int(budget * 0.85) - 8192
        usage_ratio = total_estimated / effective if effective > 0 else 0

        compaction = await get_compaction_status(conversation_id, usage_ratio)

        return {
            "conversation_id": conversation_id,
            "message_count": message_count,
            "message_tokens": total_message_tokens,
            "total_estimated_tokens": total_estimated,
            "budget": effective,
            "usage_ratio": round(usage_ratio, 3),
            "usage_percent": int(usage_ratio * 100),
            "compaction": compaction,
        }
    finally:
        await db.close()


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


@router.delete("/conversations/{conversation_id}/messages/{message_id}")
async def delete_message(conversation_id: str, message_id: str):
    """Delete a single message from a conversation."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id FROM messages WHERE id = ? AND conversation_id = ?",
            (message_id, conversation_id),
        )
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Message not found")
        await db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        await db.commit()
        return {"deleted": True, "message_id": message_id}
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


# ── Single conversation lookup ─────────────────────────────────────
# Declared AFTER /conversations/search so the static route wins (FastAPI
# matches in declaration order; this {conversation_id} param would otherwise
# capture "search"). The frontend uses this to verify a conversation's
# campaign binding before reusing it for a send.


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str) -> ConversationResponse:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse(
            id=row["id"],
            account_id=row["account_id"],
            campaign_id=row["campaign_id"],
            campaign_name=row["campaign_name"],
            title=row["title"],
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
    finally:
        await db.close()


# ── Agent status — check if agent is running / reconnect ───────────


@router.get("/conversations/{conversation_id}/agent/status")
async def agent_status(conversation_id: str):
    """Check if an agent is running for this conversation."""
    is_running = conversation_id in _agent_tasks and not _agent_tasks[conversation_id].done()
    buffered = len(_agent_buffers.get(conversation_id, []))
    done = _agent_done.get(conversation_id, True)
    return {"running": is_running, "buffered_events": buffered, "done": done}


@router.get("/conversations/{conversation_id}/agent/stream")
async def agent_reconnect(conversation_id: str, cursor: int = 0):
    """Reconnect to a running agent and get events from cursor position."""
    async def reconnect_stream():
        pos = cursor
        while True:
            buf = _agent_buffers.get(conversation_id, [])
            while pos < len(buf):
                yield f"data: {json.dumps(buf[pos])}\n\n"
                pos += 1
            if _agent_done.get(conversation_id, True) and pos >= len(buf):
                break
            await asyncio.sleep(0.05)

    return StreamingResponse(
        reconnect_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


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
