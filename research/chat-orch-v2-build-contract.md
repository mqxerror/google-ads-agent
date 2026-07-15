# Chat Orchestration v2 — SHARED BUILD CONTRACT (ground truth, verified 2026-07-12)

This file pins the exact code facts every build subagent must honor. It is the single
source of truth for cross-module contracts so parallel work does not drift. Read it
FIRST, alongside `research/chat-orchestration-v2-plan.md` (the spec).

Working dir for backend commands: `/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/backend`
Backend venv: `.venv` — activate `source .venv/bin/activate`. Tests = **stdlib unittest** (NO pytest installed).
Run tests: `python -m unittest discover -s tests -t . -q`   (baseline = 125 green)
Frontend dir: `/Users/mqxerrormac16/Documents/LangarAI/google-ads-agent/frontend` — typecheck: `npx tsc -b`

## CRITICAL CORRECTIONS TO THE PLAN
- **DB is already at V21** (`sync_state` migration, database.py:1002). The plan says "V21 migration"
  but that number is TAKEN. Our new tables ship as **V22**. (Flag in report.)
- `_run_agent`/`_run_group` (workflow_orchestrator.py:555-653) pass the SHARED `conversation_id`
  to `stream_agent_response`, which registers the Popen under `conversation_id` in `_running_procs`
  (last-writer-wins across parallel specialists — the F7 bug). For per-specialist stop we add an
  OPTIONAL distinct process-registry key threaded through the call chain (see PROC REGISTRY below).

## MIGRATION V22 (database.py — follow the exact V19/V20/V21 block pattern, `if version < 22:`)
Three tables/columns, all additive & idempotent:
1. `chat_turns` (turn_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, campaign_id TEXT,
   parent_turn_id TEXT,  -- nullable; Epic-8 sub-turns only; NULL for top-level (bake in now)
   mode TEXT NOT NULL DEFAULT 'direct',  -- direct|orchestrated|delegated
   status TEXT NOT NULL DEFAULT 'running',  -- running|done|failed|stopped|stale
   cost REAL NOT NULL DEFAULT 0, agents_used INTEGER DEFAULT 0, conflicts INTEGER DEFAULT 0,
   started_at TEXT DEFAULT (datetime('now')), finished_at TEXT, final_message_id TEXT,
   stop_reason TEXT)  + index on (conversation_id, started_at DESC).
2. `chat_turn_events` (turn_id TEXT NOT NULL, seq INTEGER NOT NULL, type TEXT NOT NULL,
   payload TEXT, created_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (turn_id, seq))
   + index on (turn_id, seq).
3. `ALTER TABLE messages ADD COLUMN turn_id TEXT;`  (nullable — legacy rows keep rendering)
4. `ALTER TABLE workflow_reports ADD COLUMN origin TEXT DEFAULT 'workflow';`  ('chat' for chat-dispatched)
`INSERT OR IGNORE INTO schema_version (version) VALUES (22)`.

## EVENT ENVELOPE (§4.3) — every SSE `data:` line is ONE JSON object:
`{"v":2,"conversation_id":str,"turn_id":str,"seq":int,"ts":iso8601,"type":str,"payload":{...}}`
- seq = monotonic per turn (the hub cursor). Reconnect = `?cursor=<last seq>`.
- v1 event types keep flowing UNTOUCHED inside direct-mode turns, wrapped in this envelope:
  routing, context_meta, text, tool_call, tool_result, resumed, continuation, done, error.
- v2 types (§4.4): turn_start, director_thought, memory_recall, verification, plan,
  agent_called, agent_progress, agent_result, conflict, decision, final_start, final_chunk,
  final_done, claim_gate, turn_done, turn_error, turn_stopped.

## PROC REGISTRY (the stop backbone — Epic 1.5/1.6/2.6)
Add to agent.py a v2 process registry keyed by `(turn_id, call_id)`:
  `_turn_procs: dict[tuple[str,str], set[subprocess.Popen]] = {}`
  `_turn_stop_requested: set[tuple[str,str]] = set()`   # (turn_id, call_id) OR (turn_id, "*") for whole-turn
- `stream_agent_response` gains an OPTIONAL param `proc_key: tuple[str,str] | None = None`.
  When set, `_run_cli` ALSO registers/deregisters the Popen under `_turn_procs[proc_key]` and checks
  `_turn_stop_requested` for both `proc_key` and `(proc_key[0], "*")` at the segment-top guard AND the
  continue-decision guard (mirror the existing `_stop_requested` sites at agent.py:1560 and :1732).
  Epic 0's conversation-keyed path stays intact and unchanged for direct/legacy callers.
- `stop_turn(turn_id)` → adds `(turn_id,"*")` to `_turn_stop_requested`, killpg every proc whose key[0]==turn_id.
- `stop_call(turn_id, call_id)` → adds `(turn_id,call_id)`, killpg only `_turn_procs[(turn_id,call_id)]`.
- Reuse Epic 0's killpg helper logic (SIGTERM→wait(2)→SIGKILL, os.getpgid). Popen already has
  start_new_session=True (agent.py:1608).
- call_id for a DIRECT-mode turn = the string "director" (single child). For specialists = the plan's call_id (c1,c2..).

## HUB / RUNNER (chat_runner.py — LIFT workflow_runner.py verbatim-structurally)
- `_ChatHub` == `_RunHub` (replay buffer + subscribers + done). Keyed by turn_id in `_chat_hubs`.
- `start(...)` mints turn_id UP FRONT (do NOT wait for a first event — unlike workflow_runner which
  reads run_id off the first event; here WE own the turn_id), inserts the `chat_turns` row, launches
  detached task calling the orchestrator (or direct passthrough), returns turn_id immediately.
- Events flushed to `chat_turn_events` in batches (~20 events / 500ms) so history replay survives restart.
- `subscribe(turn_id)` == workflow_runner.subscribe (replay from cursor then tail; closing never kills run).
  MUST support `?cursor=N` (replay only events with seq > cursor).
- Zombie sweep for chat_turns (mirror sweep_zombies: status='running' & started_at older than threshold → 'stale').
- Budget: `CHAT_ORCH_MAX_COST_USD=5.0`, `CHAT_ORCH_MAX_RUNTIME_MIN=6.0`, `CHAT_ORCH_MAX_SPECIALISTS=3` (config.py).

## ENDPOINTS (chat.py — ADD; keep legacy alias)
- `POST /api/conversations/{id}/message` → returns JSON `{turn_id}` immediately (detached run started).
  Keep `?stream=1` legacy passthrough = today's StreamingResponse behavior for one release (story 1.2 note).
- `GET /api/conversations/{id}/turns/{turn_id}/stream?cursor=N` → SSE viewer; 404 if turn.conversation_id != {id}.
- `GET /api/conversations/{id}/turns/active` → active turn(s) for reconnect.
- `GET /api/conversations/{id}/turns/{turn_id}/events` → JSON event list from chat_turn_events (history replay).
- `POST /api/conversations/{id}/turns/{turn_id}/stop` → per-turn stop (idempotent; 200 {status:"already_done"} if terminal).
- `POST /api/conversations/{id}/turns/{turn_id}/calls/{call_id}/stop` → per-specialist stop (idempotent).
- Legacy `POST /api/conversations/{id}/stop` stays as alias → stops the conversation's active turn.

## _run_group EVENT TRANSLATION (orchestrator DISPATCH, §5.6)
Existing `_run_agent` emits to `out`: agent_start / agent_text / agent_tool / agent_done.
Translate to the turn hub v2 envelopes: agent_start→agent_called, agent_text/agent_tool→agent_progress,
agent_done→agent_result. Persist each specialist to workflow_reports with `origin='chat'`, run_id=turn_id.
Thread `proc_key=(turn_id, call_id)` down so per-specialist stop reaches exactly that child — this means
`_run_group`/`_run_agent` need a new optional `proc_key`/`call_id` param passed to stream_agent_response.

## KEY REUSABLES (verbatim available)
- `_extract_json(text)` workflow_orchestrator.py:168-185 — findings/plan JSON parse (fence-aware).
- `classify_intent(message)` roles.py:916 → {"gear":int,"role_id":str,"confidence":float,"reason":str} — triage pre-gate.
- `fetch_ad_landing_pages(account_id, campaign_id) -> str` agent.py:759 — VERIFY step (never raises).
- `_MAX_PARALLEL = 2` workflow_orchestrator.py:62.
- `_CATEGORY_ROLE` scheduler.py:75 — need→role reverse map for ledger scoring.
- `ROLE_NOTES_STALE_DAYS = 7` campaign_memory.py:32.
- `append_role_notes(account_id, campaign_id, role, notes, section_title)` campaign_memory.py:504 (cross-campaign guard intact).
- `build_campaign_context(account_id, campaign_id, active_role)` campaign_memory.py:597.
- `has_recent_data()` metrics_store.py:173.
- Built-in roles: director, ppc_strategist, search_term_hunter, creative_director, script_generator,
  analytics_analyst, competitor_intel, gtm_specialist, growth_hacker, cro_specialist, pmax_strategist.

## FRONTEND (ChatPanel.tsx layout/, DESIGN.md is law)
- Epic 0 primitives present: conversationIdRef (ChatPanel:89), guardedSetMessages (:527), tearDownChatDisplayPoller (:105).
- ChatMessage type from `@/types`: id, role, content, createdAt, toolCalls, agentRole, agentRoleName,
  agentRoleAvatar, isPending, videoUrl, videoThumbnail. ADD optional `turnId?: string`.
- actualSend SSE loop = ChatPanel:564-637 (the while(true) reader → extract to shared `parseSse` util).
- WorkflowPanel handleEvent switch = WorkflowPanel:168-209 (visual grammar to import).
- Tokens (Tailwind @theme aliases): bg-app, surface, surface-2, surface-3, border, border-strong,
  text, text-muted, text-subtle, accent, accent-hover, accent-soft, on-accent, success(-soft),
  danger(-soft), warning(-soft). Idioms: .studio-pulse, .studio-caret, .studio-prose.
  BANS: no side-stripe borders, no gradients, no glassmorphism, no invented diff/plan cards
  (every UI element must map to a real backend event).
- API base = `/api/` (vite proxy). Typecheck: `npx tsc -b` — MUST show no NEW errors.
