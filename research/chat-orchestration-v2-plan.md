# Chat Orchestration v2 — Build Plan

**Status:** PLANNING (BMAD-compatible — sections 10.x are epic/story seeds)
**Date:** 2026-07-12 · **Amended 2026-07-12 (post-approval):** + Epic 0 P0 stop/bleed hotfix, F7 root-cause (§1.1), first-class stop/isolation stories (1.5 / 1.6 / 2.6 / 3.4, in the MVP cut), Epic 8 "Director of Directors" (§13)
**Source of truth for the "why":** the Panama QIP failure thread (`~/Downloads/Panama QIP  Qualified Investor Program_2026-07-08.md`) + `research/agent-quality-hardening-plan.md` (WS1–WS5, shipped).
**Prime directive:** the Director is the ONLY voice in chat. Everything else is visible, live, collapsible *activity* — never a wall of text, never a fake persona monologue, never a stale-data diagnosis.

---

## 0. The five design decisions (read this first)

| # | Decision | One-line rationale |
|---|---|---|
| D1 | **Keep SSE; kill per-request coupling.** Chat streaming moves onto the detached-runner + replay-hub pattern that `workflow_runner.py` already proved (`_RunHub`, workflow_runner.py:47-77). No WebSocket. | The whole stack is one-directional server→client; user input/stop are separate POSTs today and stay that way. WS buys nothing and costs a second transport, a reconnect protocol, and proxy/testing complexity. |
| D2 | **A new `chat_orchestrator.py` service — the Director as a real-time router** — layered ON TOP of `stream_agent_response()` (agent.py:841), reusing `_run_agent`/`_run_group` from workflow_orchestrator.py:557-653 verbatim. The Team-Audit orchestrator is NOT replaced; chat orchestration is a sibling with a triage gate so cheap questions stay cheap. | The CLI-subprocess loop is proven ($8.43 full audits, per-agent cost tracking, MCP scope guard). The post-mortem failure was *chat* having no orchestration at all — a single persona roleplaying, or a one-call fake "TEAM SESSION" (ChatInput.tsx:190). |
| D3 | **Recall-before-run.** A new Task Ledger service unifies prior outputs (workflow_reports, scheduled_plan_runs, session_summaries, role_notes) into one queryable, staleness-scored surface the Director MUST consult before dispatching anyone. | "Yesterday's Search Term Hunter run" already exists in three tables; nothing reads them at chat time today. Re-running is the expensive default; recalling must become the cheap default. |
| D4 | **Provenance manifest + claim gate.** Every context block gets a machine-readable source tag (`LIVE_API(ts)` / `LOCAL_STORE(synced_at)` / `MEMORY(date)` / `PAGE_FETCH(ts)` / `USER`); a deterministic post-pass validates every ID-shaped claim in the Director's final answer against the manifest and rewrites unverified ones into explicit "not verified" text. Extends WS2–WS5 from prompt-discipline to hard guarantee. | The Panama thread cited GTM-WZKDXFH8 / AW-826329520 / AW-959555504 from memory for 10+ messages; prompt rules alone demonstrably bend. |
| E5 | **Personas become structured contractors, not essayists.** Role files get a fixed section structure (identity / workflow / OUTPUT CONTRACT / few-shot slots / RULE 0), specialists return **JSON findings** (claims + sources + confidence + disconfirming-fact), tool scoping and model tier become per-persona defaults enforced by the existing `LANGAR_AGENT_TOOL_ALLOWLIST` middleware. | The Director can only resolve conflicts mechanically if specialist output is structured. Prose reports made the 7-persona session "verbose, mostly agreeing" (WS5 post-mortem). |
| D6 | **Account-level orchestration = recursive composition, not a new engine.** The "Director of Directors" (Epic 8, §13) fans an account-chat turn out into **campaign sub-turns that are real turns** — own `turn_id`, `chat_turns.parent_turn_id`, own hub, the full §5 state machine run locally per campaign — then reconciles. No second orchestrator, no shared mutable state across campaigns. | Everything hard about cross-campaign work (memory isolation, budget, stop, replay) is already solved per-turn; nesting turns inherits all of it for free. A bespoke account engine would re-litigate every guarantee. |
| D7 | **Stop is a first-class turn operation; isolation is by construction, not by discipline.** Every event is keyed `(conversation_id, turn_id)`; hubs are per-turn; a viewer can physically only subscribe to its own conversation's turns. Stop = cooperative task-cancel + **process-group kill** of every CLI child in the turn (workflow_runner's stop discipline, generalized). | Today's chat "never stops" and bleeds replies into other campaigns' windows — a live bug (F7, §1.1) rooted in conversation-keyed buffers, an unkeyed frontend state, and a kill that can't reach continuations or parallel children. Prompt rules can't fix transport identity; keys can. |

**MVP cut (what Wassim sees first, ~11–14 dev-days):** Epic 0 (P0 stop/bleed hotfix — ships day 1, pre-v2) + Epic 1 incl. stop/isolation stories 1.5–1.6 + Epic 2 stories 2.1–2.4 + 2.6 + Epic 3 stories 3.1–3.2 + 3.4 — i.e. a daily-report-style question in normal chat produces a *live activity stream* (Director thought → ledger recall → ≤2 specialists running in parallel with streaming previews → one Director answer), on the new event protocol, behind a per-conversation toggle — **and every running thing has a working stop button, with streams physically unable to bleed across chats** (F7 is a live bug today; stop/isolation is table-stakes UX, not polish). Accuracy hard-gate and persona overhaul follow.

---

## 1. What actually failed in the Panama thread (mechanism-level)

Each failure below maps to a v2 subsystem. File refs are to the *current* code that produced the behavior.

| # | Failure in the exhibit | Mechanism today | v2 fix |
|---|---|---|---|
| F1 | PPC Strategist opened with "the form silently rejects country codes" — a June-1 finding asserted on July 8 as current fact; root cause (`/lp/` page) unexamined for 10+ messages until the user volunteered it. | Role notes are injected wholesale by `build_campaign_context()` (campaign_memory.py:597-660). WS3 now labels >7d notes `⚠️ STALE` (campaign_memory.py:32, 636-648) and WS2 fetches landing pages (agent.py:733-784) — but nothing *forces* the model to reconcile stale memory against the live fetch, and nothing surfaces the discrepancy to the user. | §5 RECALL step scores staleness *before* the LLM sees anything, emits a visible `memory_recall` event ("using June-1 CRO notes — 37 days old — re-verifying"), and §7 blocks final claims not grounded in the manifest. |
| F2 | "Personas rambled in sequence": the TEAM SESSION was ONE model call roleplaying 7 specialists via `---ROLE:` markers (client prompt template at ChatInput.tsx:190-201, rendered by `TeamOrRegularContent`, ChatMessage.tsx:368-425). No parallelism, no real disagreement, no tools per persona. | The chat path has no orchestrator; the real orchestrator (workflow_orchestrator.py) is only reachable from the Team Audit tab. | §5 replaces the fake team session with real dispatch through `_run_group`; ChatInput's team template is deleted (story 7.2). |
| F3 | "Watched a spinner then got a wall of text": the CRO Specialist's landing-page-switch turn is ~40 lines of narrated tool thrash (ad-blocker modal loop) delivered as one blob. | `stream_agent_response` emits whole text blocks per assistant message (CLI stream-json without partial messages, agent.py:1482-1509); ChatPanel shows only a pulsing "N running" line (ChatMessage.tsx:241-253). | §4 event protocol (agent_progress w/ tool + narration), §6 live activity ledger, and optional `--include-partial-messages` token streaming (story 1.4). |
| F4 | Execution dead-end: "no MCP tool to change ad URL" — CRO Specialist then spent a full turn in browser thrash. | WS1 has since shipped the in-place mutate (`update_ad_final_urls`, operations.py:523-571) — but nothing tells the Director what execution surface exists per intent. | §9 persona tool cards + Director capability map (story 6.4). |
| F5 | Specific IDs (GTM-WZKDXFH8, AW-826329520/959555504, Clarity `56xm2r94rk`, conversion labels) recited from memory as fact. | WS4 is a prompt rule (agent.py:1294-1311, roles.py:260, 333) — advisory only. | §7 claim gate: deterministic, not prompt-hopeful. |
| F6 | The Director never used prior task outputs — e.g. the Search Term Hunter cites "un-actioned since May 25 and again Jun 24" cleanups that lived only in old reports. | Prior outputs persist (workflow_reports V15, scheduled_plan_runs V17, session_summaries, role_notes) but no chat-time reader exists. | §8 Task Ledger. |
| F7 | **LIVE BUG (2026-07-12, not from the Panama thread).** Wassim, verbatim: *"how we stop an agent that start … because now it NEVER STOPS and his reply can be seen in ANOTHER chat window in ANOTHER campaign."* | Three compounding mechanisms, verified in §1.1: (a) one unkeyed frontend `messages` state with three writers that never check conversation identity; (b) backend buffers keyed by conversation only, replayed from cursor 0, no turn identity; (c) a stop that kills only the currently-registered CLI child — continuations relaunch past it, parallel specialists overwrite its key, and a queued message auto-*resumes* the session the user just killed. | Epic 0 (P0 hotfix, pre-v2) + stories 1.5 (per-turn stop), 1.6 (isolation by construction), 2.6 (per-specialist stop), 3.4 (stop UI). |

### 1.1 F7 in detail — the never-stops / cross-campaign bleed mechanism (code-verified)

**Bleed vector 1 — one shared `messages` state, three writers, zero identity checks.** ChatPanel holds a single `messages` array for whatever chat is displayed (ChatPanel.tsx:26). Three independent async writers mutate it:
- The **send reader** (`actualSend`, ChatPanel.tsx:501-574) streams the POST response in a `while(true)` loop with no check that the displayed conversation still equals the one it sent to. The campaign-switch effect (ChatPanel.tsx:260-275) clears `conversationId`/`messages` on a switch but **never aborts `abortControllerRef`** — the old reader keeps running against the new campaign's window: its error path *appends* unconditionally (ChatPanel.tsx:584-588) and its `finally` flips `isResponding` for whichever chat is now open (ChatPanel.tsx:590-592).
- The **reconnect reader** (ChatPanel.tsx:198-238) fires on every `conversationId` change, fetches `/agent/stream?cursor=0`, adds a placeholder assistant bubble (ChatPanel.tsx:208-212) and streams into shared state; its `cancelled` flag is only consulted *after* the next chunk arrives (ChatPanel.tsx:217), so already-applied writes stand.
- The worst: the **`chat:display` poller** (ChatPanel.tsx:622-639) — after a Builder/handoff display event it calls `setMessages(msgs)` with the *handed-off* conversation's messages every 2 s for up to 5 minutes (ChatPanel.tsx:641). The timer is never cleared on a conversation or campaign switch (the effect's deps, ChatPanel.tsx:657, never change), so another campaign's reply **literally overwrites the open window** every 2 seconds.

**Bleed vector 2 — backend buffers have no turn identity.** `_agent_buffers` is a process-local dict keyed by conversation_id alone (chat.py:35-38); both the POST stream (chat.py:366-380) and the reconnect endpoint (chat.py:691-709) replay it from cursor 0. And if a message is sent while a task is already running for that conversation, **no new task starts** — the new POST silently attaches to the *old* task's buffer (chat.py:358-363), so the previous prompt's answer streams out as the reply to the new one.

**"NEVER STOPS" — a stop endpoint exists but can't win.** `POST /conversations/{id}/stop` (chat.py:396-400) calls `stop_agent` (agent.py:152-167), which terminates only the CLI child currently registered in `_running_procs[conversation_id]`:
- **No process group.** The Popen has no `start_new_session` (agent.py:1565), so `terminate()` never reaches the CLI's own children (google-ads MCP via uv, chrome MCP via npx, headless Chrome) — they orphan and keep working.
- **The continuation race.** `_run_cli` detects a user stop only as *key absence* in `_running_procs` (agent.py:1657-1660). If the stop lands between segments — the entry already popped by the `finally` (agent.py:1669-1671), or the segment just ended `max_turns` — the continuation loop (agent.py:1674-1701) relaunches a fresh `--resume` subprocess (up to 5 continuations / $25, config.py:64-65) that the user's kill never touched.
- **Parallel specialists share one key.** Workflow dispatch passes the *same* conversation_id to every specialist (workflow_orchestrator.py:584-593); registration is last-writer-wins (agent.py:1566-1567), so with 2 concurrent subprocesses a stop can only ever reach one — and possibly the wrong one.
- **The resurrection chain.** `user_stopped` is in `_RESUMABLE_STOPS` (agent.py:516) and the session id is persisted (agent.py:1731). ChatPanel's queue drains the moment `isResponding` flips false (ChatPanel.tsx:420-429) — so a message queued before the stop fires automatically and **auto-resumes the very session the user just killed** (agent.py:1426, 1526-1538). Stop → drain → resume: it never stops.

---

## 2. Current-state inventory (what v2 builds on — verified file:line)

**Backend — the LLM loop (reuse as-is):**
- `stream_agent_response()` agent.py:841 — layered context assembly (Layers 0–9, agent.py:914-973), system prompt build (agent.py:979-1311), token-budget allocation (agent.py:1352-1393 via `token_counter.allocate_budget`), CLI subprocess with auto-continuation/resume/cost-cap/Opus-fallback (`_run_cli`, agent.py:1511-1703), event types emitted today: `routing, context_meta, text, tool_call, tool_result, resumed, continuation, done, error` (agent.py:874-882, 1409-1414, 1482-1509, 1574-1584, 1695).
- Campaign scope + tool allowlist enforced physically via env (`LANGAR_BOUND_CAMPAIGN_ID`, `LANGAR_AGENT_TOOL_ALLOWLIST`, agent.py:1452-1477) → `CampaignScopeMiddleware` in `google_ads/mcp_main.py`.
- WS2 live page fetch: `fetch_ad_landing_pages()` agent.py:733-784 (cap 3 URLs, agent.py:724), wired into `_get_campaign_data()` at agent.py:597-606 and 655-662.
- Guardrail prompt block (WS2/WS3/WS4): agent.py:1294-1311.

**Backend — the multi-agent loop (reuse with small extensions):**
- `run_workflow()` workflow_orchestrator.py:656 — phases prefetch (715-731), WS5 premise gate (738-765), Director plan w/ JSON contract + default-ritual fallback (783-879), parallel specialists via `_run_group` (881-910, `_MAX_PARALLEL = 2` at :62), debate w/ disconfirm suffix (918-977, suffixes :151-165), synthesis (979-1035), per-phase persistence to `workflow_reports` (:525-539).
- `workflow_runner.py` — detached task + `_RunHub` replay/fan-out (:47-77), `start/subscribe/stop` (:167-219), zombie sweep (:222-248). **This is the transport skeleton chat v2 adopts.**

**Backend — chat path (replace the streaming plumbing, keep the CRUD):**
- `POST /api/conversations/{id}/message` chat.py:148 — campaign-binding rules (:204-257), background task + module-dict buffers (`_agent_buffers`, chat.py:35-38, 302-390), SSE polling loop every 50 ms (:366-380), reconnect endpoint `GET .../agent/stream?cursor=` (:691-709). Buffers are process-local and never replayed after done → history loses all activity (only final text is persisted at :334-349). Buffers also carry **no turn identity**, and the chat stop (`POST .../stop`, chat.py:396-400 → `stop_agent`, agent.py:152-167) is subprocess-only — see §1.1/F7 for why stop is unreliable and streams bleed today.

**Backend — memory & prior work:**
- `campaign_memory.py`: role_notes staleness (32, 39-55), cross-campaign write guard (:423-466), context builder (:597-660).
- `metrics_store.py`: local-first data (`has_recent_data` :173-184, `format_for_agent` :186-339 with 5-min/30-min/1-h caches).
- `scheduler.py`: plans + runs (`scheduled_plan_runs` results at :321-330), category→role map (:75-84).
- Post-turn writebacks in agent.py: session summary (:1758-1789), chronicle (:1791-1805), decisions + role notes (:1807-1860).
- DB is at **V20** (database.py:991). New tables in this plan = **V21**.

**Frontend:**
- ChatPanel.tsx — fetch-stream SSE parse in `actualSend` (:453-601), reconnect (:186-247), stop (:937-954).
- ChatMessage.tsx — tool summary rows (:46-143), pulsing "live activity" line (:241-253), `TeamOrRegularContent` `---ROLE:` parser (:368-425 — to be retired), INTERNAL_TOOLS hide-list (:40).
- WorkflowPanel.tsx — already renders phase chips + live agent cards off the workflow event stream (`handleEvent` :168-209): the visual grammar to import into chat.
- Design constraints: `frontend/DESIGN.md` — light OKLCH tokens only, quiet tool rows, avatar-lane turns, explicit bans (:99-104) incl. "Do NOT invent a diff/review card or a plan checklist — the backend emits neither event" (v2 *changes the backend*, so new UI elements must ship in lock-step with their real events).

---

## 3. Architecture overview

```
POST /api/conversations/{id}/message
        │  (persist user msg — unchanged binding rules, chat.py:204-257)
        ▼
chat_runner.start(...)  ── detached asyncio task, _RunHub replay buffer
        │                   (lift of workflow_runner.py pattern, keyed by turn_id)
        ▼
chat_orchestrator.run_turn()          ← NEW  backend/app/services/chat_orchestrator.py
  ┌─────────────────────────────────────────────────────────────────┐
  │ S0 TRIAGE     Director-lite classifier: direct | orchestrate    │
  │ S1 RECALL     Task Ledger query → memory_recall events          │
  │ S2 VERIFY     WS2 premise fetch (reuse) → verification event    │
  │ S3 PLAN       Director JSON: specialists[], parallel groups     │
  │ S4 DISPATCH   _run_group (reuse) → agent_* events               │
  │ S5 RESOLVE    conflict detection over structured findings       │
  │ S6 SYNTHESIZE Director speaks (single voice) → final_* events   │
  │ S7 GATE       claim gate over final text (deterministic)        │
  │ S8 WRITEBACK  ledger row + role_notes + summary + chronicle     │
  └─────────────────────────────────────────────────────────────────┘
        │ every state change = one typed SSE event
        ▼
GET /api/conversations/{id}/turns/{turn_id}/stream?cursor=N   (SSE viewer)
POST /api/conversations/{id}/turns/{turn_id}/stop              (kill whole turn — story 1.5)
POST /api/conversations/{id}/turns/{turn_id}/calls/{call_id}/stop  (kill ONE specialist — story 2.6)
        ▼
ChatPanel: Director bubble + collapsible OrchestrationLedger component
```

`stream_agent_response()` remains the ONLY way any LLM call is made (Director triage, Director plan, each specialist, synthesis) — same CLI subprocess, same cost caps, same MCP scoping, same resume semantics. No Anthropic SDK migration (decision reaffirmed from `project_workflow_orchestrator.md`).

---

## 4. Transport + event protocol

### 4.1 SSE vs WebSocket — decision: SSE (unchanged transport, upgraded contract)

| Criterion | SSE (keep) | WebSocket |
|---|---|---|
| Direction needed | Server→client only. User input = POST `/message`; stop = POST `/stop` (chat.py:396-400); approval (future) = POST. | Bidirectional — unneeded. |
| Reconnect/replay | Already solved twice in this codebase: buffer+cursor (chat.py:691-709) and `_RunHub` replay (workflow_runner.py:65-74). `Last-Event-ID` native to SSE. | Must be hand-built (ping/pong, resume tokens). |
| Existing client code | 3 fetch-stream parsers already in prod (ChatPanel :500-574, reconnect :214-237, WorkflowPanel :146-157). | New client stack. |
| Infra | Plain HTTP; works through the Vite proxy and any future reverse proxy untouched. | Proxy upgrade headers, sticky sessions if ever multi-process. |
| Failure mode | Stream dies → client re-GETs with cursor; run unaffected (detached task). | Socket dies → session state renegotiation. |

**Verdict:** WebSocket solves a problem this product does not have. The perceived "spinner then wall of text" was never a transport limitation — it was (a) whole-block text events, (b) no intermediate orchestration events, (c) the run living inside the request generator. All three are fixed within SSE.

### 4.2 Endpoint changes

- `POST /api/conversations/{id}/message` → returns **JSON `{turn_id}` immediately** (~ms), having started the detached run. (Compat: keep streaming from the POST response for one release behind `?stream=1` so old clients don't break — story 1.2.)
- `GET /api/conversations/{id}/turns/{turn_id}/stream?cursor=N` → SSE viewer over the turn's hub (replay from cursor, then tail). Closing NEVER kills the run — the exact `workflow_runner.subscribe` contract (workflow_runner.py:188-203). The endpoint 404s unless the turn actually belongs to `{id}` — cross-conversation subscription is impossible by URL shape (story 1.6).
- `POST /api/conversations/{id}/turns/{turn_id}/stop` — **per-turn stop** (story 1.5): idempotent; cooperative task-cancel (mirrors workflow_runner.stop :206-219) PLUS process-group kill of every CLI child registered under the turn. Legacy `POST /conversations/{id}/stop` stays as an alias that stops the conversation's active turn.
- `POST /api/conversations/{id}/turns/{turn_id}/calls/{call_id}/stop` — **per-specialist stop** (story 2.6): kills one running specialist's process group; the Director continues with the rest.
- **Persistence (new, V21):** `chat_turns` (turn_id, conversation_id, campaign_id, **parent_turn_id** — nullable, set only on Epic-8 campaign sub-turns, NULL for every top-level turn, mode `direct|orchestrated|delegated`, status, cost, started_at, finished_at, final_message_id) + `chat_turn_events` (turn_id, seq, type, payload JSON, created_at). Events are flushed in batches (every ~20 events / 500 ms) so history replay works after restart — fixing the process-local `_agent_buffers` loss (chat.py:35-38). Old `messages` rows gain `turn_id` (nullable — legacy rows keep rendering exactly as today). Baking `parent_turn_id` into V21 now costs one nullable column and saves Epic 8 a second migration.

### 4.3 Event envelope

Every SSE `data:` line is one JSON object:

```json
{ "v": 2, "conversation_id": "c-41ab", "turn_id": "t-9f31", "seq": 17,
  "ts": "2026-07-12T14:03:21.412Z", "type": "agent_progress", "payload": { } }
```

- `v:2` lets the client branch; **all v1 event types keep flowing untouched inside direct-mode turns** (`routing, context_meta, text, tool_call, tool_result, resumed, continuation, done, error`) so nothing existing regresses.
- `seq` is the hub cursor (monotonic per turn). Reconnect = `?cursor=<last seq>`.
- **Every event is keyed `(conversation_id, turn_id)`** — the isolation invariant (D7, story 1.6). A client applies an event to its state ONLY when both match what it subscribed to; the server never fans a turn's events anywhere but that turn's own hub. This is what makes F7's bleed structurally impossible rather than merely fixed.

### 4.4 New event types (the v2 vocabulary)

| type | emitted by | payload (abridged) |
|---|---|---|
| `turn_start` | runner | `{mode, campaign_id, campaign_name, model}` |
| `director_thought` | S0/S1/S3/S5 | `{text, stage}` — short first-person planning lines, the "thoughts" Wassim asked to watch |
| `memory_recall` | S1 | `{source, ref_id, role_id, age_days, staleness, decision: "reuse"\|"reverify"\|"ignore", summary}` |
| `verification` | S2/S7 | `{kind: "landing_page"\|"ids"\|"metrics", status: "verified"\|"failed"\|"skipped", detail}` |
| `plan` | S3 | `{specialists:[{call_id, role_id, role_name, task, model, tools, reason}], parallel_groups:[[call_id,…]]}` |
| `agent_called` | S4 | `{call_id, role_id, role_name, task, model, tools, reused_from?: ref_id}` |
| `agent_progress` | S4 | `{call_id, kind: "text"\|"tool", content?, tool?: {source,name,input_summary}}` |
| `agent_result` | S4 | `{call_id, role_id, status: "ok"\|"failed"\|"stopped", cost, duration_ms, findings:[{id, claim, severity, confidence, sources:[…], disconfirmed_by}], summary}` — `stopped` = user killed this call (story 2.6); partial text preserved |
| `conflict` | S5 | `{id, between:[call_id,call_id], topic, positions:[{call_id, stance}], }` |
| `decision` | S5/S6 | `{conflict_id?, ruling, rationale, decided_by:"director"}` |
| `final_start` / `final_chunk` / `final_done` | S6 | chunks of the ONE Director message; `final_done: {message_id, cost_total, duration_ms, agents_used, conflicts_resolved}` |
| `claim_gate` | S7 | `{checked, passed, rewritten:[{claim, reason}]}` |
| `turn_done` / `turn_error` | runner | terminal; `turn_done.stop_reason` mirrors today's done event fields (agent.py:1695) |
| `turn_stopped` | stop endpoint (story 1.5) | terminal; `{stopped_by:"user", calls_killed:[call_id,…], partial_persisted:true}` — emitted exactly once, after every child process is confirmed dead |

Epic 8's account-level events (`fanout_preview`, `fanout_decision`, `campaign_turn_start`, `campaign_progress`, `campaign_turn_done`) are specified with their relay rules in §13.3 — same envelope, parent's `(conversation_id, turn_id)` keys.

Worked example (the Panama "daily report" ask):

```json
{"v":2,"turn_id":"t-9f31","seq":2,"type":"director_thought","payload":{"stage":"recall","text":"Daily report request. Checking what the team already produced for Panama QIP…"}}
{"v":2,"turn_id":"t-9f31","seq":3,"type":"memory_recall","payload":{"source":"workflow_reports","ref_id":"wr-77c2","role_id":"search_term_hunter","age_days":1,"staleness":"fresh","decision":"reuse","summary":"Yesterday's search-term hunt: 3 negatives proposed, $28.86/wk waste on 'panama golden visa'"}}
{"v":2,"turn_id":"t-9f31","seq":4,"type":"memory_recall","payload":{"source":"role_notes","ref_id":"cro_specialist.md","role_id":"cro_specialist","age_days":37,"staleness":"stale","decision":"reverify","summary":"June-1 form finding — STALE, will not be asserted without live fetch"}}
{"v":2,"turn_id":"t-9f31","seq":5,"type":"verification","payload":{"kind":"landing_page","status":"verified","detail":"https://www.mercan.com/panama-qualified-investor-program → HTTP 200 · form signal YES · tracking token YES (fetched 14:03Z)"}}
{"v":2,"turn_id":"t-9f31","seq":6,"type":"plan","payload":{"specialists":[{"call_id":"c1","role_id":"analytics_analyst","task":"Yesterday vs 7-day avg…","model":"sonnet","tools":[],"reason":"metrics fresh in local store — analysis-only"},{"call_id":"c2","role_id":"ppc_strategist","task":"Budget pacing given…","model":"opus","tools":[],"reason":"pacing judgment"}],"parallel_groups":[["c1","c2"]]}}
{"v":2,"turn_id":"t-9f31","seq":9,"type":"agent_progress","payload":{"call_id":"c1","kind":"text","content":"Spend yesterday $96.40 vs $101.20 avg…"}}
{"v":2,"turn_id":"t-9f31","seq":14,"type":"agent_result","payload":{"call_id":"c1","ok":true,"cost":0.31,"duration_ms":41200,"findings":[{"id":"f1","claim":"CPA week avg $1,280 — zero conv in last 7d","severity":"high","confidence":0.9,"sources":[{"tag":"LOCAL_STORE","ts":"2026-07-12T13:58Z"}],"disconfirmed_by":"a conversion recorded after 13:58Z sync"}],"summary":"Traffic healthy, conversions zero — consistent with funnel-shape diagnosis"}}
{"v":2,"turn_id":"t-9f31","seq":16,"type":"conflict","payload":{"id":"k1","between":["c1","c2"],"topic":"budget action","positions":[{"call_id":"c1","stance":"hold budget, funnel is the blocker"},{"call_id":"c2","stance":"throttle to $55/day now"}]}}
{"v":2,"turn_id":"t-9f31","seq":17,"type":"decision","payload":{"conflict_id":"k1","ruling":"Throttle via ad-group pause, not budget line","rationale":"Same spend reduction, zero learning-phase debate, reversible","decided_by":"director"}}
{"v":2,"turn_id":"t-9f31","seq":18,"type":"final_start","payload":{}}
```

---

## 5. Orchestration engine (`backend/app/services/chat_orchestrator.py`)

### 5.1 State machine

States: `TRIAGE → RECALL → VERIFY → PLAN → DISPATCH → RESOLVE → SYNTHESIZE → GATE → WRITEBACK → DONE`, with two short-circuit edges:
- `TRIAGE → DIRECT` (no orchestration: today's exact single-persona path — the vast majority of turns).
- Any state → `DEGRADE` (budget/error): synthesize with whatever is in hand, mirroring workflow_orchestrator's degrade-not-fail stance (:24, :975-977).

State lives in the module-level run registry (task + hub, like workflow_runner._hubs/_tasks :81-82) plus the V21 `chat_turns` row (status column updated per state, so a restart shows honest `failed/stale` turns via the same zombie-sweep idea, workflow_runner.py:222-248).

### 5.2 S0 TRIAGE — keep cheap things cheap

Two-stage gate, deliberately conservative about invoking orchestration:

1. **Heuristic pre-gate (0 LLM calls):** reuse `classify_intent()` (roles.py:916-971). Gear 1 lookups, greetings, mid-conversation follow-ups (`isn't that`, `ok do it`, short replies < ~90 chars referencing the running context), and Studio/video intents → `DIRECT` mode (today's path, single `stream_agent_response` call, active_role resolved as now).
2. **Director triage call (1 haiku call, tools=[]):** for the remainder, a ≤300-token prompt: *"User asked X. Prior-work ledger headlines: […]. Respond JSON `{mode: "direct"|"orchestrate", reason, needs: ["metrics_review","page_check","search_terms",…]}`"*. Unparseable → `DIRECT` (safe default). The Panama "we spent 3k with 1 lead — what exactly?" ask triages to `orchestrate` because it demands diagnosis + spend judgment + page truth.

The chat composer also gets an explicit "Ask the team" toggle (maps to `force_mode=orchestrate`) replacing the fake TEAM SESSION template (ChatInput.tsx:190-201, deleted in story 7.2).

### 5.3 S1 RECALL — Task Ledger first (see §8 for the service)

`task_ledger.recall(account_id, campaign_id, needs, query_text)` returns scored entries. The orchestrator emits one `memory_recall` event per considered entry with an explicit `decision`:
- `reuse` — fresh per the staleness matrix (§8.2): its summary is injected into the plan prompt as PRIOR WORK, and the Director is told NOT to re-dispatch that specialist for the same question.
- `reverify` — stale: injected but tagged, and the plan prompt REQUIRES either a live pull in that lane or an explicit "unverified" label downstream.
- `ignore` — irrelevant (below similarity threshold).

This is the direct fix for F1/F6: the recall is *visible* ("using yesterday's Search Term Hunter run — fresh") and *binding*.

### 5.4 S2 VERIFY — premise gate, lifted

Reuse `fetch_ad_landing_pages()` (agent.py:733) exactly as workflow_orchestrator does (:738-765), but only when triage `needs` includes `page_check` OR any recall entry touching page/form/tracking came back `reverify` (don't tax every turn with 3 HTTP fetches). Result is pinned into the plan+specialist prompts as the VERIFIED PREMISE block and registered in the provenance manifest (§7) as `PAGE_FETCH(ts)` — or the UNVERIFIED warning variant (workflow_orchestrator.py:758-765) when the fetch fails.

### 5.5 S3 PLAN — Director plans the *minimal* team

Prompt contract = the campaign-mode plan prompt (workflow_orchestrator.py:800-822) with three deltas:
1. **PRIOR WORK section** (ledger reuse/reverify entries) + instruction: "Do not dispatch a specialist to redo work marked reuse; cite it instead."
2. **Hard cap:** ≤3 specialists per chat turn (env `CHAT_ORCH_MAX_SPECIALISTS=3`); the full 7-persona sweep stays in the Team Audit tab. Empty/unparseable plan → degrade to `DIRECT` (answer solo) — NOT to the 3-specialist default ritual, which is a workflow-tab behavior.
3. Every specialist entry must carry `reason` (surfaced in the `plan`/`agent_called` events so the activity stream reads like delegation, not magic).

Model: `fable` for the plan call (as today, workflow_orchestrator.py:828); specialists default per-persona tier (§9.3).

### 5.6 S4 DISPATCH — reuse `_run_group`

Import and call `_run_group` (workflow_orchestrator.py:621-653) with `out` wired to the turn hub, translating its `agent_start/agent_text/agent_tool/agent_done` into `agent_called/agent_progress/agent_result` envelopes. Parallel where the plan groups them (`_MAX_PARALLEL=2` respected — each agent is a ~256 MB CLI subprocess, workflow_orchestrator.py:60-62). Persist each specialist output to `workflow_reports` with `run_id = turn_id` and a new `origin='chat'` column (V21) so the Team Audit history and the Task Ledger both see chat-dispatched work.

**Specialist output contract (new):** each specialist task gets `_SPECIALIST_TASK_SUFFIX` (workflow_orchestrator.py:151-158) REPLACED by the v2 JSON contract suffix: report ≤200 words PLUS a fenced ```json findings block `{findings:[{claim, severity, confidence, sources:[{tag, ts, detail}], disconfirmed_by}], summary}`. Parsed with `_extract_json` (workflow_orchestrator.py:168-185); parse failure degrades to prose (findings=[]) — never a crash.

### 5.7 S5 RESOLVE — conflicts as data, Director decides

No debate round in chat (latency; debate stays a Team Audit feature). Instead:
- Deterministic pass over structured findings: same-topic findings (keyword overlap on claim text + shared entity ids) with opposing directional stances (increase/decrease, pause/keep, etc. — small verb lexicon) → `conflict` events.
- The synthesis prompt receives the conflict list and MUST emit a `decision` per conflict ("state your ruling and why" — same contract as workflow synthesis, workflow_orchestrator.py:1008-1010). Rulings are parsed from a fenced JSON block in the synthesis output and re-emitted as `decision` events; unparseable → the prose still stands, no decision events (degrade, don't fail).

### 5.8 S6 SYNTHESIZE — one voice

One `stream_agent_response(active_role="director", tools=[])` call whose prompt = user question + prior-work citations + specialist findings JSON + conflicts + verified premise. Streamed out as `final_chunk`s. THIS text (and only this) is persisted as the assistant `messages` row (tagged with `turn_id`, `agent_role='director'`), so:
- conversation history stays a clean user↔Director dialogue (Layer-3 recall, agent.py:390-431, never re-ingests specialist walls);
- specialist detail lives in `chat_turn_events`/`workflow_reports` for the expandable ledger, exactly once.

### 5.9 S7/S8 — gate + writeback

Gate: §7. Writeback: §8.3. Then `turn_done`.

### 5.10 Cost & runtime budget

Per-turn envelope: `CHAT_ORCH_MAX_COST_USD` (default **$5**) and `CHAT_ORCH_MAX_RUNTIME_MIN` (default **6**) — far under the workflow's $50/20-min (workflow_orchestrator.py:68, workflow_runner.py:85-88) because this is conversational. Crossing either mid-dispatch → cancel outstanding specialists → SYNTHESIZE with what's in hand + an honest note in the final answer. Existing per-call caps (`AGENT_MAX_TOTAL_COST_USD=25`, config.py:63-65) still bound each subprocess.

---

## 6. Chat UI spec (Shopify-calm light; frontend/DESIGN.md is law)

### 6.1 Anatomy of an orchestrated turn

```
┌ user bubble (unchanged, accent-soft, right)                        ┐
│                                                                    │
│ [Director avatar] Agency Director            · streaming dot      │
│ ├─ OrchestrationLedger  (new component, replaces nothing —        │
│ │   appears ONLY on v2 turns)                                     │
│ │   ● Checked prior work        2 found · 1 stale       14:03    │
│ │       ↳ quiet rows: "Search Term Hunter, yesterday — reused"    │
│ │         "CRO notes, 37d — re-verifying" (warning-soft chip)     │
│ │   ● Verified landing page     form ✓ · tracking ✓               │
│ │   ● Analytics Analyst  ▸      running · $0.31                   │
│ │       ↳ expanded: live streaming preview (3-line clamp,        │
│ │         .studio-prose, mono tool rows for agent_progress/tool)  │
│ │   ● PPC Strategist     ▸      done · 41s                        │
│ │   ● Conflict: budget action   Analyst vs Strategist             │
│ │       ↳ Director ruling: "throttle via ad-group pause" (accent) │
│ ├──────────────────────────────────────────────────────────────── │
│ │  Director's answer (normal .studio-prose, streams as today)     │
│ └  provenance footnote chips: LIVE 14:03 · PAGE 14:03 · MEM Jun-1 │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2 Behaviour rules

- **Live:** ledger rows appear as events land; the active row carries the `.studio-pulse` dot (same idiom as tool rows, DESIGN.md:86-88 / ChatMessage.tsx:57-63). Specialist rows auto-expand while streaming (WorkflowPanel does this on `agent_start`, :189) and auto-collapse on `agent_result`.
- **After completion:** the whole ledger collapses to ONE summary row — `▸ Orchestrated · 2 specialists · 1 conflict resolved · 58s · $0.84` — expandable forever (events replay from `chat_turn_events`). The Director's prose is what the eye lands on.
- **Direct-mode turns render exactly as today** (no ledger). No layout shift between modes beyond the ledger block's presence.
- **Streaming affordances:** `final_chunk`s use the existing `.studio-caret`; if story 1.4 (partial messages) ships, specialist previews get token-level flow too, else block-level (current behavior) is acceptable inside the clamped preview.
- **Tokens only:** ledger rows are `bg-surface-2`/`-3` + hairline `border-border`; staleness chip = `warning-soft`; verification = `success`/`danger` dots; conflict rows use `text-text` + a `Gavel`-style icon, ruling line in `text-accent`. No new cards-with-icon grids, no side-stripes, no gradients (DESIGN.md bans :99-104).
- **Failure honesty:** a specialist error renders a `danger` dot + "failed — Director proceeding without it" (never a green check on failure, DESIGN.md:88).

### 6.3 Components & wiring

- `frontend/src/components/chat/OrchestrationLedger.tsx` (new) — pure renderer over an ordered event list; used both live (stream) and in history (fetch `GET /turns/{id}/events`).
- ChatPanel `actualSend` gains the two-step flow: POST → `{turn_id}` → open the turn SSE (one shared `parseSse` util extracted from the three existing hand-rolled parsers: ChatPanel :500-574, :214-237, WorkflowPanel :146-157).
- ChatMessage renders the ledger when `message.turnId` is set and events exist; `TeamOrRegularContent`'s `---ROLE:` path stays only for legacy rows (never produced anew).
- Reconnect after refresh: existing status endpoint pattern (ChatPanel :186-247) becomes `GET /turns/active?conversation_id=` → resubscribe by cursor. Because the run is detached, mid-orchestration refresh loses nothing.

---

## 7. Accuracy layer — from prompt rules to guarantees

### 7.1 Provenance manifest (built server-side during context assembly)

While assembling layers (agent.py:914-973) and orchestration inputs, the builder records every injected data block into a per-turn manifest:

```json
{ "entries": [
  {"tag":"LOCAL_STORE","ts":"2026-07-12T13:58Z","kind":"metrics","ids":["22996208317"],"detail":"campaign_daily_metrics sync"},
  {"tag":"PAGE_FETCH","ts":"2026-07-12T14:03Z","kind":"landing_page","urls":["https://www.mercan.com/panama-qualified-investor-program"]},
  {"tag":"MEMORY","ts":"2026-06-01","kind":"role_notes","role":"cro_specialist","stale":true},
  {"tag":"LIVE_API","ts":"2026-07-12T14:04Z","kind":"tool_result","tool":"search__execute_query","ids":["AW-826329520"]}
]}
```

- `LIVE_API` entries are appended at stream time from `tool_result` events (agent.py:1508-1509) — a cheap regex over tool outputs harvests ID-shaped tokens (`GTM-[A-Z0-9]+`, `AW-\d+`, `G-[A-Z0-9]+`, 10+-digit campaign/criterion ids, conversion labels — reuse the pattern set from `_condense_for_memory`, agent.py:798-806).
- Each context layer header now carries its tag inline (e.g. `=== LIVE CAMPAIGN DATA [LOCAL_STORE · synced 13:58Z] ===`), so the model *sees* the same taxonomy the gate enforces — prompt and enforcement stop being two different worlds.

### 7.2 The claim gate (S7 — deterministic, runs on the Director's final text only)

1. Extract ID-shaped claims from the final answer (same regex family).
2. Each ID must appear in a manifest entry with tag `LIVE_API` or `PAGE_FETCH` or `LOCAL_STORE` (fresh), or in a `MEMORY` entry **already labeled in the text** (the sentence must contain a source marker like "(from …, <date>)").
3. Violations are REWRITTEN, not silently dropped: `GTM-WZKDXFH8` → `a GTM container (ID not verified this session — pull it before relying on it)`, and a `claim_gate` event reports `{checked, passed, rewritten:[…]}` so the ledger shows the gate ran. Persisted message = gated text.
4. **Refusal path:** if triage `needs` included `page_check` but S2 verification failed, the synthesis prompt already carries the UNVERIFIED premise block; the gate additionally hard-blocks any "the page has/lacks X" assertion (sentence-level match on form/tracking/page vocabulary) → rewritten to "page state UNVERIFIED this session (fetch failed) — I won't assert page facts; recommend re-fetch". This is WS2's rule (agent.py:1296-1302) made mechanical.

Scope discipline: the gate targets **IDs, URLs, and page-state assertions** — the categories that actually burned us (F1, F5). It does NOT try to verify arithmetic or every number (false-positive machine); metric provenance is handled by the inline layer tags + footnote chips (§6.1).

### 7.3 Specialist-level grounding

Specialist findings JSON requires `sources:[{tag, ts}]` per claim (§5.6). Findings with empty sources are accepted but marked `confidence: unsourced` and the Director's synthesis prompt instructs: unsourced findings may motivate a VERIFY action but never a recommendation. (Conservative first cut; tighten later if specialists over-claim.)

---

## 8. Smart memory — the Task Ledger

### 8.1 Service (`backend/app/services/task_ledger.py`, new)

One read API over the four existing stores (NO new write path for v1 — the ledger is a view, so nothing can drift):

| Source | Table/files | What it contributes |
|---|---|---|
| Team Audit + chat-dispatched specialist reports | `workflow_reports` (+ V21 `origin` col) joined to `workflow_runs`/`chat_turns` | role_id, task, content, cost, created_at |
| Scheduled plan runs | `scheduled_plans` + `scheduled_plan_runs` (scheduler.py:321-330) | category, result text, fired_at — "yesterday's Search Term Hunter run" lives here |
| Session summaries | `session_summaries` (agent.py:497-510) | compact per-turn conclusions |
| Role notes | `data/memory/{acct}/{camp}/role_notes/*.md` (campaign_memory.py:329-338) | latest per-role state + `**Last updated:**` age (campaign_memory.py:39-55) |

`recall(account_id, campaign_id, needs, query_text, limit=8)` → entries scored by (a) need/category match (scheduler's `_CATEGORY_ROLE` map :75-84 reused in reverse), (b) keyword overlap with the query (same scorer as `message_selector`), (c) recency. Each entry returns `{source, ref_id, role_id, created_at, age_days, staleness, summary(≤300 chars), content_ref}`.

### 8.2 Staleness matrix (single source of truth, constants module — used by ledger, recall events, and prompts)

| Data class | Fresh | Stale → action |
|---|---|---|
| Landing page / form / tracking state | this-session fetch ONLY | always `reverify` (WS2 stands) |
| Daily metrics | local sync < 24h (`has_recent_data`, metrics_store.py:173-184 uses days=2 today — tighten to 1 for recall decisions) | trigger `sync_account` in S2 (bounded, same as workflow prefetch :715-731) |
| Search terms | < 3 days (matches the 3-day pull, agent.py:679-695) | re-pull lane or dispatch hunter |
| Specialist analysis/report | < 7 days (align with `ROLE_NOTES_STALE_DAYS`, campaign_memory.py:32) | `reverify` — reusable as *context*, not as *current fact* |
| Decisions/chronicle/pinned facts | never stale (they're history/constants) | n/a |
| IDs (GTM/AW/G-/labels) | this-session live pull ONLY | claim gate (§7) |

### 8.3 Writeback (S8) — close the loop so tomorrow's recall is better

After `final_done`:
1. `workflow_reports` rows already persisted per specialist (S4) — the ledger sees them immediately.
2. ONE session summary for the turn: Director's decisions + conflicts resolved (existing writer, agent.py:1758-1789, invoked once for the turn — specialists suppressed from Layer-4 writes to avoid summary spam).
3. Role notes: each dispatched specialist's findings appended via `append_role_notes` (campaign_memory.py:504-559) with the JSON findings serialized compactly (pollution guard :423-466 applies untouched).
4. Chronicle line (agent.py:1791-1805) tagged `[orchestrated]`.
5. `chat_turns` row finalized (cost, agents_used, conflicts) — the future "what did orchestration cost me this week" query.

---

## 9. Persona skill upgrades ("optimize their skills level")

### 9.1 Role file structure v2 (backwards-compatible superset of `data/roles/{role_id}.md`, roles.py:771-811)

```
--- (frontmatter: id, name, avatar, specialty, model_tier, tool_scope) ---
## IDENTITY        (voice, seniority — 5 lines max)
## EXPERTISE       (the current deep-knowledge block, pruned)
## WORKFLOW        (numbered, tool-explicit; references live context blocks by name)
## OUTPUT CONTRACT (the JSON findings block spec + ≤200-word prose rule + disconfirm line)
## FEW-SHOT        (0–3 examples: task → ideal findings JSON; empty slots shipped, Wassim fills — same Phase-3 lever deferred in feedback_prompt_quality_principles)
## RULE 0          (non-overridable: ID integrity, verify-before-diagnose, campaign lock, brand-name ban)
```

Loader change: `load_role_overrides` (roles.py:771) parses the two new frontmatter keys; sections are concatenated in order with RULE 0 last (hard-rules-at-end lever). All 10 built-in personas get migrated files; built-in Python strings remain the fallback.

### 9.2 Per-persona tool scoping — from advisory to enforced

`Role.tools_focus` (roles.py:34) is currently decoration. v2: when the orchestrator (or a scheduler-fired role turn) runs a specialist WITHOUT an explicit plan allowlist, `tool_scope` from the role file feeds `tool_allowlist` → `LANGAR_AGENT_TOOL_ALLOWLIST` (agent.py:1474-1477) → physically enforced by the MCP middleware. Defaults:

| Persona | tool_scope default | model_tier default |
|---|---|---|
| director | [] in plan/synthesis (pure reasoning, as today workflow :829, :1022) | fable |
| analytics_analyst | [] (context analysis) | sonnet |
| search_term_hunter | ["search_term", "negative"] (read + negative-add only) | haiku→sonnet (haiku for scheduled scans, sonnet in chat) |
| ppc_strategist | [] analysis / ["budget","bid","status"] only on approved execution turns | opus |
| creative_director | ["ad_", "asset"] | sonnet |
| cro_specialist | chrome + [] ads tools | sonnet |
| gtm_specialist | gtm + chrome | sonnet |
| pmax_strategist | ["pmax","asset_group","asset","campaign"] | opus |
| competitor_intel / growth_hacker | [] | sonnet |

(Exact strings validated against the middleware's substring matching at build time — story 6.2 acceptance includes the 4-case allowlist test rerun from `project_workflow_orchestrator.md`.)

### 9.3 Sharpening content (per-persona pass, one story each batch)

- Prune each prompt's "use the X endpoint" residue (e.g. roles.py:102-104, :140-141 reference legacy REST endpoints, not MCP) — personas should reference the context blocks and MCP tools that actually exist.
- Add the OUTPUT CONTRACT + disconfirm line natively (today bolted on per-task by workflow suffixes :151-165 — keep the suffixes for safety, but native contracts make solo chat turns structured too).
- Director gets a **capability map** section: what execution surface exists (e.g. "ad final-URL in-place update EXISTS: `update_ad_final_urls`", operations.py:523) so F4-style dead-end thrash is answered from knowledge, not discovery.
- Few-shot slots wired but shipped empty (Wassim supplies exemplars; the loader injects them verbatim).

---

## 10. Phased delivery — epics & stories

Estimates are focused dev-days (backend-heavy days assume tests alongside; this codebase's norm). **Σ ≈ 38–46 days. MVP = E0 + E1 (incl. 1.5–1.6) + E2.1–2.4 + 2.6 + E3.1–3.2 + 3.4 ≈ 11–14 days.** Epic 0 is deliberately pre-v2 and ships the moment it's green.

### Epic 0 — P0 hotfix: stop that stops + streams that stay home (SHIPS NOW, pre-v2) — **1 d**
F7 is burning Wassim today; none of this waits for the turn runner. One story, three surgical patches, zero v2 dependencies (ChatPanel.tsx + agent.py only):
- **0.1** *(≤1 d, P0)*
  (a) **Frontend identity guard:** every stream writer captures its `convId` at start and checks it against a `conversationIdRef` before ANY `setMessages` (send reader ChatPanel.tsx:501-574, reconnect reader :198-238, `chat:display` poller :622-639); the campaign-switch effect (:260-275) and conversation switches abort `abortControllerRef` and clear the poller timer. Kills all three bleed writers from §1.1.
  (b) **Backend stop hardening:** `subprocess.Popen(..., start_new_session=True)` (agent.py:1565) + `os.killpg(…, SIGTERM→SIGKILL)` in `stop_agent` (agent.py:152-167) so MCP/Chrome children die with the CLI; add a `_stop_requested: set[conversation_id]` that `stop_agent` sets and `_run_cli` consults at the top of every segment AND in the continue-decision (agent.py:1674-1701) — closes the between-segments relaunch race.
  (c) **No auto-resurrection:** ChatPanel `onStop` (:937-954) also clears `messageQueue`, so a queued message can't auto-fire and resume the just-killed session (the :420-429 drain + agent.py:516/1426 chain).
  Acceptance: start a long turn → stop → confirm no `claude` or MCP child survives (`pgrep`), no continuation launches, no queued send fires; switch campaigns mid-stream → zero writes land in the new window.
  Explicitly NOT in scope: turn-keyed buffers/history replay — that's E1; the hotfix makes stop reliable and bleed impossible, not history perfect.

### Epic 1 — Turn runner + event protocol (foundation) — **6.5 d**
- **1.1** `chat_runner.py`: detached turn task + `_RunHub`-style hub + `chat_turns`/`chat_turn_events` (V21 migration incl. `messages.turn_id`, `chat_turns.parent_turn_id`, `workflow_reports.origin`); zombie sweep for turns. *(2 d)*
- **1.2** Endpoints: POST `/message` → `{turn_id}` (with `?stream=1` legacy passthrough); GET `/turns/{id}/stream?cursor`; GET `/turns/active`. Direct-mode turns wrap today's `stream_agent_response` events in v2 envelopes. (Stop endpoints land in 1.5.) *(1.5 d)*
- **1.3** Frontend: shared `parseSse` util; ChatPanel two-step send + cursor reconnect; envelope-aware event handling (v1 payloads keep rendering identically). *(1 d)*
- **1.4** *(stretch, 0.5 d)* `--include-partial-messages` on the CLI cmd (agent.py:1432-1439) behind env flag → token-level `text` deltas; fallback verified when the installed CLI lacks the flag.
- **1.5** **Per-turn stop.** `POST /api/conversations/{id}/turns/{turn_id}/stop` — idempotent (terminal turn → 200 `{status:"already_done"}`). Cancels the detached turn task cooperatively (workflow_runner.stop discipline, :206-219) AND process-group-kills every live CLI child registered for the turn in a new `(turn_id, call_id)`-keyed process registry (replaces conversation-keyed `_running_procs` on v2 paths; fixes the last-writer-wins overwrite, agent.py:1566-1567). A turn-scoped stop flag defeats the continuation relaunch race by construction. Emits one terminal `turn_stopped` event; `chat_turns.status='stopped'`; partial specialist output persisted to `workflow_reports` and the partial Director text (if any) persisted labeled **"stopped by user"**. Stop does NOT auto-resume — resume stays consume-once on an explicit user message (agent.py:1426 semantics unchanged). If the turn is an Epic-8 parent, stop cascades to all child sub-turns. *(1 d)*
- **1.6** **Isolation by construction.** Envelope carries `(conversation_id, turn_id)` (§4.3); hubs registered per turn; `GET /turns/{turn_id}/stream` 404s when the turn doesn't belong to the path's conversation; ChatPanel subscribes ONLY to its own conversation's turns, every state write identity-guarded, readers/pollers torn down on conversation or campaign switch (generalizes Epic 0's guard onto the v2 transport; retires the `chat:display` poller in favor of turn subscription). **Acceptance test (the F7 regression gate):** two concurrent turns in two campaigns' conversations — each window receives only its own turn's events end-to-end; `POST .../stop` on one turn → the other stream is byte-identical to an undisturbed run and completes; the stopped turn's window shows `turn_stopped`, the other never sees it. *(1 d)*

### Epic 2 — Orchestration engine — **8 d**
- **2.1** `chat_orchestrator.py` skeleton: state machine, TRIAGE (heuristic + haiku call), DIRECT passthrough, budget/runtime caps, DEGRADE paths. *(1.5 d)*
- **2.2** Task Ledger v1 (`task_ledger.py` read-only view over the 4 stores + staleness matrix constants) + RECALL events. *(1.5 d)*
- **2.3** PLAN (≤3 specialists, prior-work contract) + DISPATCH via `_run_group` reuse + event translation + `workflow_reports(origin='chat')` persistence. *(2 d)*
- **2.4** SYNTHESIZE single-voice + persistence of the Director-only message; VERIFY step (WS2 reuse, conditional). *(1 d)*
- **2.5** RESOLVE: findings-JSON specialist contract + conflict detection + decision parsing/events. *(1 d)*
- **2.6** **Per-specialist stop.** `POST /api/conversations/{id}/turns/{turn_id}/calls/{call_id}/stop` — kills exactly ONE running specialist's process group via its `(turn_id, call_id)` registry entry; idempotent. Its ledger row goes terminal `agent_result{status:"stopped"}` with partial text preserved; the Director is NOT restarted — dispatch continues with remaining results, and the synthesis prompt receives `SPECIALIST STOPPED BY USER: {role} — findings unavailable; state the gap explicitly in your answer`. Stopping the last running specialist ends DISPATCH, not the turn — synthesis still runs on what's in hand (same degrade-not-fail stance as §5.10). *(1 d)*

### Epic 3 — Live activity UI — **5 d**
- **3.1** `OrchestrationLedger.tsx`: recall/verification/agent rows, live pulse, streaming previews (3-line clamp), auto-expand/collapse, DESIGN.md-compliant. *(2 d)*
- **3.2** Post-completion collapse row + history replay (`GET /turns/{id}/events`) + ChatMessage integration via `turn_id`. *(1.5 d)*
- **3.3** Conflict/decision rows + provenance footnote chips + claim-gate row. *(1 d)*
- **3.4** **Stop affordances.** A stop control on the turn header (wired to 1.5) and a per-row stop on every RUNNING specialist activity row (wired to 2.6). Stopped rows render the honest terminal state — `danger` dot + "stopped by user — Director proceeding without it" (never a green check, DESIGN.md:88); the turn-level stop renders the partial answer + "stopped by user" note. Direct-mode turns get the same header stop (routes to 1.5, which reaps the single CLI child). *(0.5 d)*

### Epic 4 — Accuracy hard-gate — **3.5 d**
- **4.1** Provenance manifest builder in context assembly + inline layer tags + LIVE_API harvesting from tool_results. *(1.5 d)*
- **4.2** Claim gate (extract → check → rewrite → `claim_gate` event) on Director finals; unit-tested against the Panama exhibit's ID set as fixtures. *(1.5 d)*
- **4.3** Refusal path for failed page verification (sentence-level page-claim block). *(0.5 d)*

### Epic 5 — Smart-memory writeback + recall polish — **2.5 d**
- **5.1** S8 writeback (single turn summary, specialist role-notes append, chronicle tag, turn finalize). *(1 d)*
- **5.2** Recall scoring tune + `reuse` short-circuit ("answered entirely from yesterday's run" — zero dispatch) + metrics sync trigger on stale metrics. *(1.5 d)*

### Epic 6 — Persona skill upgrade — **4 d**
- **6.1** Role file v2 loader (frontmatter tiers/scopes, sectioned concat, RULE 0 last). *(1 d)*
- **6.2** Enforced per-persona tool scopes + allowlist validation tests. *(1 d)*
- **6.3** Content pass: migrate all 10 personas to v2 files, prune legacy endpoint refs, native output contracts, Director capability map. *(1.5 d)*
- **6.4** Few-shot slots + docs for Wassim to fill. *(0.5 d)*

### Epic 7 — Migration, compat, eval — **3 d**
- **7.1** Legacy compat sweep: old conversations render untouched (null `turn_id`); scheduler (`scheduler._run_agent` :196-228) and workflow orchestrator continue on direct `stream_agent_response` unaffected; `?stream=1` shim removal criteria. *(1 d)*
- **7.2** Retire fake TEAM SESSION: ChatInput template (ChatInput.tsx:190) → "Ask the team" force-orchestrate toggle; `TeamOrRegularContent` kept for legacy rows only. *(0.5 d)*
- **7.3** **Panama replay eval:** scripted harness feeds the exhibit's 9 user messages through v2 against recorded fixtures; asserts (a) stale June-1 finding surfaces as `reverify` not fact, (b) landing-page URL mismatch (`/lp/`) found in ≤1 turn via VERIFY, (c) no unverified ID in any final, (d) each turn ≤3 specialists. This is the definition of done for the whole feature. *(1.5 d)*

### Epic 8 — Director of Directors: account chat → campaign directors → one reconciled answer — **8 d** *(full spec: §13)*
- **8.1** Account-turn triage + fan-out planning: `delegate` mode in S0 for account-level (unbound) conversations; campaign selection (user-named or Director-proposed from active campaigns); `fanout_preview` event + `POST /turns/{turn_id}/fanout` approve/decline endpoint (the "campaigns touched" gate — nothing spawns before approval). *(1.5 d)*
- **8.2** Sub-turn lifecycle: spawn each campaign sub-turn via `chat_runner.start` into that campaign's persistent delegation conversation (real turn, `parent_turn_id` set, full §5 machine locally, per-sub-turn $5/6-min envelope untouched); parent aggregate budget envelope + degrade (cancel outstanding sub-turns, reconcile what's in hand); parent stop cascade (extends 1.5). *(2 d)*
- **8.3** Event relay: child-hub → parent-hub namespaced mirror events (`campaign_turn_start` / `campaign_progress` / `campaign_turn_done`), headline-only filter (no token spam); expand-in-UI lazily subscribes to the child turn's own stream/events endpoint — no event duplication in storage. *(1 d)*
- **8.4** Cross-campaign reconcile + synthesis: union of sub-turn findings (entries namespaced by campaign_id), §5.7 conflict detection extended with cross-campaign resource conflicts, Account Director synthesis with per-campaign sections + cross-campaign rulings, claim gate over the union of namespaced manifests, account-level writeback (NO campaign namespace writes from the parent — campaign_memory.py:423-466 stays law). *(1.5 d)*
- **8.5** Account chat UI: parent ledger grouped by campaign — collapsible per-campaign sections ("● Panama QIP — Director working…" live), expand → full sub-turn ledger, post-completion per-campaign collapse rows, fan-out approval card. *(2 d)*

### Rollout order & gating
0. **E0 ships NOW** — pre-v2, independent of everything below; it's a bug fix, not a feature.
1. E1 behind nothing (pure plumbing, direct mode byte-equivalent; stop + isolation land here and also protect direct mode).
2. E2+E3 behind per-conversation toggle `orchestration=v2` (default OFF) → Wassim dogfoods on Panama QIP.
3. E4 default ON for all modes once E2 stable (the gate also protects direct mode).
4. E5–E6 iterate; flip default ON; E7.3 green = ship.
5. **E8 last** — requires E1–E3 stable plus at least one campaign dogfooded through v2; exposed only via the account-level chat's "Ask all campaigns" affordance, so single-campaign chat never pays its complexity.

---

## 11. Risks & mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | **Latency/cost inflation** — every chat message becoming a multi-agent run (triage + N subprocesses + synthesis could hit 2–4 min, $1–3/turn). | Triage double-gate defaults to DIRECT; ≤3 specialist cap; ledger `reuse` short-circuit; $5/6-min turn envelope with degrade-to-synthesis; live activity stream makes the wait *feel* purposeful (the original complaint was blind waiting, not waiting per se). |
| R2 | **Subprocess pressure** — chat orchestration + Team Audit + scheduler could stack CLI children (~256 MB each). | One global dispatch semaphore shared with `_MAX_PARALLEL` (lift to a module both import); chat turns queue behind it; scheduler already caps at 2 (scheduler.py:39-40). |
| R3 | **Claim gate false positives** — legit, freshly-pulled IDs rewritten because harvesting missed them. | Harvest from tool_results AND page fetches AND local-store formatting; rewrite (never delete) with explicit reason; `claim_gate` event makes every rewrite visible; fixture tests from the Panama IDs; week-one monitor via `chat_turn_events`. |
| R4 | **Director misroutes triage** (orchestrates trivia / answers complex asks solo). | Heuristic pre-gate handles the obvious 80%; haiku triage JSON-or-DIRECT default; "Ask the team" manual override; triage decisions logged in `chat_turns.mode` for tuning. |
| R5 | **Findings-JSON contract erodes prose quality or fails to parse.** | Contract asks for prose ≤200 words THEN the JSON block (prose survives parse failure); `_extract_json` fallback path proven in the plan phase (workflow_orchestrator.py:834-844). |
| R6 | **Event/schema drift between chat and Team Audit UIs.** | Single translation layer in chat_orchestrator (workflow events → v2 envelope); WorkflowPanel untouched in v1 of this build; a later story can migrate it onto the same envelope. |
| R7 | **DB growth from `chat_turn_events`.** | Batched writes; retention sweep (drop event payloads >90 d, keep `chat_turns` headers); events are compact JSON (text chunks capped, previews truncated at 500 chars like tool_results today, agent.py:1509). |
| R8 | **Compaction/backend-restart mid-turn.** | Detached task + persisted events → viewer replays what exists; turn sweep marks orphans `failed/stale` honestly (never a zombie spinner — the workflow_runner lesson, :1-27). |
| R9 | **Hierarchical fan-out multiplies subprocesses** — an account turn spawning 3 campaign sub-turns, each dispatching specialists, could stack 6+ CLI children (~256 MB each) or deadlock a shared semaphore. | The global CLI semaphore (R2) is acquired ONLY for leaf `stream_agent_response` calls and never held across an await on a child — no nesting, no deadlock by construction; `ACCOUNT_ORCH_MAX_CAMPAIGNS=3`, sub-turn concurrency 2, delegated sub-turns capped at ≤2 specialists (§13.4) → worst case stays ≤ the semaphore size; the fan-out approval gate shows the blast radius before anything spawns. |

---

## 12. Open design calls for Wassim (flag, don't assume)

1. **Turn budget** — $5/6-min default OK, or tighter for daily use?
2. **Persona model tiers** (§9.2 table) — approve/adjust before E6.3 bakes them in.
3. **Few-shot exemplars** — supply 2–3 "best answer" samples per key persona (analytics, strategist, hunter) when E6.4 lands; slots ship empty otherwise.
4. **"Ask the team" affordance copy** — toggle vs slash-command vs both.
5. Whether scheduled plans should ALSO route through the orchestrator (recall+gate for scheduled runs) — deliberately out of scope here; natural follow-on epic.
6. **Epic 8 fan-out gate + budgets** — always require the approval click before spawning campaign sub-turns, or auto-proceed when it's a single campaign / under ~$5 est.? And are the parent defaults OK: `ACCOUNT_ORCH_MAX_CAMPAIGNS=3`, aggregate `ACCOUNT_ORCH_MAX_COST_USD=$15`, `ACCOUNT_ORCH_MAX_RUNTIME_MIN=10`? (Per-sub-turn stays $5/6-min regardless.)

---

## 13. Epic 8 spec — Director of Directors (account chat → campaign directors → one answer)

The account-level chat (a conversation with NO bound campaign — today's full-tool-surface path, agent.py:1462-1468) gets an Account Director who can delegate INTO campaign contexts. Everything here is composition of machinery this plan already builds — D6: sub-turns are real turns, and every per-turn guarantee (state machine, budget, stop, hub, replay, claim gate) is inherited rather than re-implemented.

### 13.1 The shape of an account-orchestrated turn

```
Account conversation (campaign_id NULL) — user asks e.g.
"How did Panama and Citizenship do this week, and where should the next $50/day go?"
        │
   S0 TRIAGE (account variant): direct | orchestrate | DELEGATE {campaigns:[…]}
        │ delegate
   fanout_preview event  →  user approves (gate)  →  spawn sub-turns
        │
  ┌─────┴──────────────────────┐
  ▼                            ▼
Panama sub-turn            Citizenship sub-turn        ← REAL turns: own turn_id,
(chat_runner.start,        (chat_runner.start,           chat_turns.parent_turn_id = parent,
 full §5 machine:           full §5 machine)             own hub, own $5/6-min envelope
 recall→verify→dispatch                                  (§5.10 applies PER SUB-TURN)
 →resolve→synthesize
 →gate→writeback, all
 LOCAL to Panama)
  │        headline events relayed, namespaced           │
  └────────────► parent hub ◄────────────────────────────┘
        │
   parent RESOLVE: cross-campaign conflict detection over the union of findings
   parent SYNTHESIZE: Account Director speaks ONCE (per-campaign sections + rulings)
   parent GATE: claim gate over the UNION of namespaced sub-turn manifests
   parent WRITEBACK: account-level only — never a campaign namespace
```

### 13.2 Sub-turn mechanics (each rule maps to existing law)

- **Where a sub-turn lives:** each campaign gets ONE persistent, auto-created **delegation conversation** (bound to the campaign, titled "Account delegations", reused across account turns). Sub-turns are ordinary turns inside it, so the conversation-binding rules (chat.py:204-257) apply verbatim, the campaign's own chat surface shows delegated work in history, and user threads are never polluted with machine-initiated turns.
- **Campaign context, physically scoped:** every subprocess a sub-turn launches carries `LANGAR_BOUND_CAMPAIGN_ID` for ITS campaign (agent.py:1463-1466) — the MCP scope guard needs zero changes to police delegated work.
- **Memory isolation preserved:** a sub-turn's S8 writeback (§8.3) writes ONLY its own campaign's namespaces — the cross-campaign write guard (campaign_memory.py:423-466) **stays law, untouched**. The parent writes exactly: the account conversation's Director message, its own `chat_turns` row, and ONE account-level session summary + chronicle line tagged `[account-orchestrated]`. The parent NEVER touches role_notes/decisions of any campaign — findings it wants to keep already live in each sub-turn's own writeback.
- **Local machine, local recall:** each campaign Director runs §5 in full against its own Task Ledger — Panama's recall never sees Citizenship's role notes. Reuse short-circuits (§5.3) work per campaign, so an account daily-report can be answered mostly from yesterday's per-campaign runs at near-zero dispatch.
- **The fan-out gate:** before ANY sub-turn spawns, the parent emits `fanout_preview` `{campaigns:[{campaign_id, name, reason, est_cost}], aggregate_cap, est_total}` and parks in a `WAITING_FANOUT` state; `POST /api/conversations/{id}/turns/{turn_id}/fanout {approve: true|false, campaigns?:[…]}` (user may prune the list). Decline → the Account Director answers from account-level data only and says so. Timeout (2 min) → same decline path, honestly labeled. (Default always-gate; auto-proceed threshold = open call §12.6.)
- **Failure honesty:** a sub-turn that errors or blows its envelope degrades exactly like a specialist does today — `campaign_turn_done{status:"failed"}`, and the parent synthesis must state "Citizenship: delegation failed — no findings this turn."

### 13.3 Event relay — namespaced bubbling into the parent hub

Sub-turns publish to their OWN hubs (turn-keyed, D7 intact). A relay task per child subscribes to the child hub and republishes **headline events only** into the parent hub, wrapped and namespaced (parent's `(conversation_id, turn_id)` on the envelope):

| parent event | wraps child event(s) | payload |
|---|---|---|
| `campaign_turn_start` | `turn_start` | `{sub_turn_id, campaign_id, campaign_name}` — renders "Panama Director working…" |
| `campaign_progress` | `director_thought, memory_recall, verification, plan, agent_called, agent_result, conflict, decision, claim_gate` | `{sub_turn_id, campaign_id, inner_type, summary}` — one-line status per child milestone |
| `campaign_turn_done` | `turn_done / turn_error / turn_stopped` | `{sub_turn_id, campaign_id, status, cost, agents_used, duration_ms}` |

Deliberately NOT relayed: `agent_progress` and `final_chunk` token streams — the parent ledger shows status lines, and expanding a campaign section lazily subscribes the UI to the child turn's own `/stream` / `/events` endpoints for full detail. Events are stored once, on the child turn (R7 stays bounded); the parent persists only its own wrapper events.

### 13.4 Budgets, concurrency, stop

- **Per-sub-turn:** the §5.10 envelope applies unchanged — `CHAT_ORCH_MAX_COST_USD=$5` / 6 min each, with the sub-turn's own degrade-to-synthesis.
- **Parent aggregate:** `ACCOUNT_ORCH_MAX_CAMPAIGNS=3`, `ACCOUNT_ORCH_MAX_COST_USD=$15`, `ACCOUNT_ORCH_MAX_RUNTIME_MIN=10`. Crossing either → cancel outstanding sub-turns (their partial work persists, labeled), reconcile what's in hand, honest note in the final.
- **Concurrency:** sub-turns run max 2 concurrent; delegated sub-turns get `CHAT_ORCH_MAX_SPECIALISTS=2` (vs 3 for user-initiated turns). The global CLI semaphore (R2) is acquired per leaf `stream_agent_response` call only, never held while awaiting a child — no hierarchical deadlock possible (R9).
- **Stop cascades:** `POST .../turns/{parent_turn_id}/stop` (story 1.5) stops every child sub-turn first (each emits its own `turn_stopped`, partial work persisted per campaign), then the parent. Stopping ONE campaign's sub-turn from the parent ledger (`POST .../turns/{sub_turn_id}/stop` — it's a real turn, the endpoint already exists) leaves the others running; the parent reconciles without it and notes the gap.

### 13.5 Cross-campaign reconciliation

- Sub-turn results return as each campaign Director's synthesized answer PLUS its findings JSON, every entry namespaced with `campaign_id`.
- Parent RESOLVE = §5.7's deterministic pass over the union, extended with one cross-campaign class: **shared-resource contention** (both campaigns claiming the same account-level budget headroom, overlapping geo/keyword expansion, conflicting account-level settings) → `conflict` events with positions attributed per campaign.
- Parent SYNTHESIZE: ONE Account Director message — per-campaign sections in a fixed order, then cross-campaign rulings (`decision` events, same parse contract as §5.7). Only this message persists to the account conversation.
- Parent GATE: §7 claim gate runs over the union of the sub-turns' provenance manifests, entries carrying `campaign_id` — an ID verified in Panama's sub-turn is a verified ID in the parent answer; an ID from neither manifest gets rewritten as always.

### 13.6 Account chat UI (extends §6, same tokens)

- The parent `OrchestrationLedger` groups rows **by campaign**: one collapsible section per sub-turn — header `● Panama QIP · Director working… · $1.20` with `.studio-pulse` while live; inside, quiet `campaign_progress` status lines. Expand → lazy-load the child turn's full ledger (its own event replay). After completion each section collapses to `▸ Panama QIP · 2 specialists · 1 conflict · 74s · $1.85`, and the whole turn to the standard one-row summary.
- The fan-out gate renders as an approval card (campaign checklist + est cost + Approve / Answer-without-delegating) — a real backend-emitted event per DESIGN.md:99-104's ban on invented cards.
- Sub-turn stop buttons per campaign section header; parent stop on the turn header (13.4 cascade semantics).
