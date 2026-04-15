---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Context, data management & agent intelligence overhaul for Google Ads agent'
session_goals: 'Campaign decision memory, API vs DB data serving, background data sync, UX redesign, dynamic role/skill loading'
selected_approach: 'user-selected'
techniques_used: ['First Principles + Five Whys', 'Cross-Pollination + What If Scenarios', 'SCAMPER']
ideas_generated: 43
session_active: false
workflow_completed: true
---

# Brainstorming Session Results

**Facilitator:** Mqxerrormac16
**Date:** 2026-04-08

## Session Overview

**Topic:** Context, data management & agent intelligence overhaul for the Google Ads agent

**Goals:**
1. **Campaign Decision Memory** — Better persistence and recall of decisions made per campaign across sessions
2. **API vs Database Investigation** — Why the app always hits Google Ads API instead of serving from local cache
3. **Background Data Sync** — Daily background download of campaign data, serve from DB instead of API
4. **UX Redesign** — Better layout, more creative and polished user experience
5. **Dynamic Role/Skill Loading** — Load specialized personas on demand (Campaign Manager, GTM Senior, Analytics Expert, etc.) for specific tasks

## Technique Selection

**Approach:** User-Selected Techniques
**Selected Techniques:**

- **Round 1: First Principles + Five Whys** — Data architecture and memory model from fundamentals
- **Round 2: Cross-Pollination + What If Scenarios** — UX ideas and role-loading concepts from other tools/industries
- **Round 3: SCAMPER** — Systematic iteration and refinement of best ideas

---

## Complete Idea Inventory (43 Ideas)

### THEME A: Agent Identity & Autonomy (Ideas #1, #2, #3, #15, #37)

**Pattern:** Transform the agent from a reporting tool to an autonomous marketing specialist that acts.

| # | Idea | Description |
|---|------|-------------|
| 1 | **Expert Identity, Not Tool Identity** | The agent should feel like hiring a senior PPC manager who already knows your account — a colleague, not a dashboard |
| 2 | **Action-First, Not Report-First** | Default is DO, not suggest. "I paused this keyword because [reason]" instead of "I recommend pausing" |
| 3 | **User-Controlled Autonomy Level** | Toggle: Auto-Execute vs Approve-First. Configurable per action type (auto-pause keywords, ask before budget changes) |
| 15 | **Action Queue with Trust Levels** | Three tiers — Inform Only (new users), Act & Report (established), Autonomous (full trust). Granular per action type |
| 37 | **Agent Initiates, User Responds** | Flip the flow — agent monitors and initiates ("CPA climbing, want me to investigate?"), user becomes approver not driver |

### THEME B: BMAD-Style Marketing Agency Team (Ideas #4, #5, #6, #7, #12, #36)

**Pattern:** A full digital agency team loaded on demand, each role with deep expertise and live intelligence.

| # | Idea | Description |
|---|------|-------------|
| 4 | **Digital Agency Team Roles** | PPC Strategist, Search Term Hunter, Creative Director, Analytics Analyst, Competitor Intel, GTM Specialist, Growth Hacker — each with own system prompt |
| 5 | **Live Marketing Intelligence Feed** | Each role searches web for current trends, algorithm changes, benchmarks. Not frozen in training data |
| 6 | **White-Label Agency Experience** | Client sees a full team — "Your PPC Strategist reviewed your campaign" — with names, avatars, specialties. Scales Langar AI as a service |
| 7 | **Role-Triggered Intelligence (3 tiers)** | Auto-research (2-3s quick search before responding), Background digest (daily scrape of key sources), Deep research (thorough investigation on demand) |
| 12 | **Hybrid 3-Gear System** | Director answers quick Qs directly, loads role inline for advisory, spawns sub-agent for deep tasks. Matches tool to task size |
| 36 | **Eliminate Generic System Prompt** | Each role carries its own prompt. No role gets context it doesn't need. Smaller prompts = faster + more room for data |

### THEME C: Data Architecture — Background Sync & DB-First (Ideas #8, #9, #35)

**Pattern:** Eliminate API calls during conversation. Sync in background, read from database.

| # | Idea | Description |
|---|------|-------------|
| 8 | **Background Sync Engine** | App starts + every 6h: pull campaign data from Google Ads API → write to DB. Agent reads DB only. API = sync source, DB = read source |
| 9 | **Campaign Snapshot Timeline** | Every sync creates a snapshot. Agent can trend: "CPA was $12 last week, now $18 — here's what changed." DB becomes time-series, not just cache |
| 35 | **Eliminate Direct API Calls During Chat** | Zero API calls in conversation. "Last synced: 2h ago" indicator. Manual refresh button for real-time needs. Responses go from 5-10s to <1s |

### THEME D: Memory & Context — Claude Code Native (Ideas #27, #28, #29, #32, #33, #38, #39, #40, #41, #42, #43)

**Pattern:** Leverage Claude Code's own memory system. Per-campaign memory files, smart compaction, dream-mode optimization.

| # | Idea | Description |
|---|------|-------------|
| 27 | **Decision Log Replaces Chat Memory** | Store structured decisions (ACTION/REASON/OUTCOME) instead of raw chat messages. 10 decision entries > 10 truncated messages |
| 28 | **Smart Compression Over Truncation** | Replace `content[:500]` with LLM-compressed summaries. Same context window, 5x more useful information |
| 29 | **Unified Campaign Context Object** | Merge goals + decisions + snapshots + role notes + active actions into one structured object. Single source of truth |
| 32 | **Sliding Window + Pinned Facts** | Recent messages slide off, but "pinned facts" never expire. "Client wants CPA under $10" persists across all sessions and roles |
| 33 | **5-Layer → 3-Layer Streamlined** | Layer A: Campaign Context Object (DB), Layer B: Role Prompt (on demand), Layer C: Conversation Window (compressed + pins). No API calls |
| 38 | **Per-Campaign Memory Directories** | File-based memory per campaign: `memory/{account}/{campaign}/` with MEMORY.md index, decisions.md, pinned_facts.md, role_notes_*.md |
| 39 | **Conversation Compaction as Feature** | Before auto-compaction, agent saves key decisions/findings to memory files. Compaction makes conversation lighter, nothing important lost |
| 40 | **Dream Mode — Background Memory Optimization** | Nightly process: review memories, correlate with performance data, consolidate duplicates, identify cross-campaign patterns, clean stale entries |
| 41 | **Smart Pre-Compaction Save** | Intercept before context limit. Structured save of decisions → decisions.md, pins → pinned_facts.md, findings → role_notes. Then let compaction happen |
| 42 | **Memory-Aware Prompt Assembly** | Read MEMORY.md index → load only files relevant to current role + task → append compressed conversation. Slim, fast, no API |
| 43 | **Cross-Campaign Dream Insights** | Dream mode finds patterns across campaigns: "Broad match on 'visa' keywords wastes budget in ALL campaigns." Stored in ACCOUNT_MEMORY.md |

### THEME E: UX — Command Center & Campaign Pulse (Ideas #16-26, #30, #34)

**Pattern:** Dashboard-first, not chat-first. Campaign health at a glance, actions as cards, roles as visible team.

| # | Idea | Description |
|---|------|-------------|
| 16 | **Slack-Style Role Channels** | Each role gets its own channel (#ppc-strategy, #search-terms). See roles working in parallel. Conversations don't tangle |
| 17 | **Linear-Style Action Board** | Kanban: TODO → IN REVIEW → APPROVED → DONE. Trust Level 1 = lands in TODO. Drag to approve. Batch approve |
| 18 | **Spotify "Now Playing" Agent Bar** | Bottom bar: which role is active, what it's doing, progress %. Multiple roles stack. Always know what's happening |
| 19 | **Notion-Style Campaign Workspace** | Campaign = a page with draggable blocks: metrics widget, role card, decisions log, action queue, notes. Chat is one block |
| 20 | **Figma Multi-Cursor Roles** | When multiple roles work simultaneously, see their "cursors" on the dashboard. Agency team feels alive |
| 21 | **Superhuman Command Palette** | Cmd+K → type anything: "audit search terms", "pause keyword visa free", "switch to creative". Power users love this |
| 22 | **Campaign Health Score** | Single score 0-100 per campaign. Green/yellow/red. Factors: CPA trend, budget pace, search waste, quality score. Act on red, ignore green |
| 23 | **Morning Briefing** | On app open: 30-second summary across ALL campaigns. "3 healthy, 1 needs attention. Your action queue has 4 items." |
| 24 | **Role Disagreement** | PPC says "increase budget." Analyst says "cut spend." Director presents both perspectives. Forces better decisions |
| 25 | **Achievement & Progress System** | Campaign quests: "Reduce CPA below $10" / "Find 50 negatives." Gamification mapped to business outcomes |
| 26 | **Campaign Timeline Minimap** | RTS-style minimap of campaign history. Every action plotted. See cause → effect visually |
| 30 | **Campaign Pulse (Combined)** | Health score + briefing + action queue in one view. One glance = health + why + what to do |
| 34 | **Client Report Generator** | Same context that powers the agent auto-generates client reports. Creative Director writes narrative, Analyst provides data. One click PDF |

### THEME F: Hybrid Architecture — Director + Gears (Ideas #10, #11, #13, #14, #31)

**Pattern:** Three-gear routing system with persistent role memory and git-style action history.

| # | Idea | Description |
|---|------|-------------|
| 10 | **Orchestrator + Spawned Specialists** | Director receives message, spawns specialist with focused context. Search Term Hunter gets search data only, not everything |
| 11 | **Skill Loading Into Main Agent** | Load role prompt inline. Agent "becomes" the specialist. Simple, maintains conversation history |
| 13 | **Three-Gear Decision Engine** | Gear 1: Direct (<1s, DB read). Gear 2: Inline Role (2-5s, advisory). Gear 3: Spawned Specialist (10-30s, audits/research). Director auto-picks |
| 14 | **Role Memory Persistence** | When specialist finishes, writes summary to DB. Next load picks up where it left off. "Last audit April 3, found 47 negatives, user approved 42" |
| 31 | **Git-Style Action Log** | Every action = a "commit" with message, timestamp, diff, revert capability. Agent reads its own history. Any action reversible with one click |

---

## Prioritized Build Order

### PHASE 1: Foundation (Week 1-2) — Data & Memory

**Must build first — everything else depends on this.**

| Priority | Ideas | What to Build |
|----------|-------|---------------|
| P0 | #8, #35 | **Background Sync Engine** — Pull campaign data every 6h, store in DB. Eliminate all API calls during chat |
| P0 | #38, #42 | **Per-Campaign Memory Directories** — File-based memory with MEMORY.md index. Memory-aware prompt assembly |
| P0 | #27, #32 | **Decision Log + Pinned Facts** — Replace chat memory with structured decisions. Pinned facts never expire |
| P1 | #33 | **3-Layer Context System** — Replace 5-layer with: Campaign Context Object + Role Prompt + Compressed Conversation |
| P1 | #28 | **Smart Compression** — LLM-compressed message summaries instead of truncation |
| P1 | #9 | **Campaign Snapshots** — Time-series data from sync for trend analysis |

### PHASE 2: Agent Intelligence (Week 3-4) — Roles & Routing

| Priority | Ideas | What to Build |
|----------|-------|---------------|
| P0 | #4, #36 | **Marketing Agency Roles** — System prompts for 7 specialist roles. Each role gets only relevant context |
| P0 | #13, #12 | **3-Gear Director** — Auto-routing: Direct (DB read) / Inline Role / Spawned Specialist |
| P1 | #14 | **Role Memory Persistence** — Roles save findings, pick up where they left off |
| P1 | #7 | **Role-Triggered Intelligence** — Auto-research before responding, background digest, deep research mode |
| P2 | #5 | **Live Marketing Intelligence** — Web search integration for current trends per role |

### PHASE 3: Autonomy & Actions (Week 5-6)

| Priority | Ideas | What to Build |
|----------|-------|---------------|
| P0 | #3, #15 | **Trust Level System** — Per-action-type autonomy: Inform / Act+Report / Autonomous |
| P0 | #31 | **Action Log with Revert** — Git-style commit history for all agent actions |
| P1 | #37 | **Proactive Agent** — Agent monitors and initiates based on alerts |
| P1 | #23 | **Morning Briefing** — Auto-generated summary on app open |

### PHASE 4: UX Overhaul (Week 7-8) — Test as Feature Branches

| Priority | Ideas | What to Build as Separate Branches |
|----------|-------|------------------------------------|
| Branch A | #30, #22 | **Campaign Pulse** — Health scores + briefing + action queue in one view |
| Branch B | #19, #17 | **Notion Workspace + Action Board** — Campaign as page with blocks + kanban actions |
| Branch C | #16, #18 | **Role Channels + Status Bar** — Slack-style channels + Spotify now-playing bar |
| Branch D | #21 | **Command Palette** — Cmd+K power-user interface |

### PHASE 5: Polish & Advanced (Week 9+)

| Priority | Ideas | What to Build |
|----------|-------|---------------|
| P1 | #40, #43 | **Dream Mode** — Nightly memory optimization + cross-campaign insights |
| P1 | #39, #41 | **Smart Compaction** — Pre-compaction save + compaction-as-feature |
| P2 | #6 | **White-Label Agency** — Role avatars, names, client-facing team feel |
| P2 | #34 | **Report Generator** — One-click client reports from campaign context |
| P2 | #24 | **Role Disagreement** — Multi-perspective analysis for complex decisions |
| P3 | #25, #26 | **Gamification + Timeline** — Achievement system + campaign history minimap |
| P3 | #20 | **Multi-Cursor Roles** — Figma-style visual indicators of active roles |

---

## Final Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   BACKGROUND LAYER                      │
│  Data Sync (6h)  │  Dream Mode (nightly)  │  Alerts     │
│  Web Research     │  Memory Consolidation  │  Monitoring │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│            MEMORY LAYER (Claude Code native)            │
│                                                         │
│  memory/{account}/                                      │
│    ├── ACCOUNT_MEMORY.md  (cross-campaign patterns)     │
│    ├── {campaign_A}/                                    │
│    │   ├── MEMORY.md       (index)                      │
│    │   ├── decisions.md    (action log)                  │
│    │   ├── pinned_facts.md (never-expire context)       │
│    │   ├── role_notes_ppc.md                            │
│    │   ├── role_notes_hunter.md                         │
│    │   ├── role_notes_creative.md                       │
│    │   └── profile.md      (goals, phase, budget)       │
│    └── {campaign_B}/...                                 │
│                                                         │
│  DB: campaign_daily_metrics (snapshot timeline)          │
│  DB: action_log (git-style with revert)                 │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              3-LAYER PROMPT ASSEMBLY                    │
│                                                         │
│  Layer A: Campaign Context Object                       │
│    goals + decisions + snapshots + role notes + pins     │
│    (from memory files + DB, never API)                   │
│                                                         │
│  Layer B: Active Role Prompt                            │
│    loaded on demand, only relevant role                  │
│    PPC / Hunter / Creative / Analyst / GTM / Growth     │
│                                                         │
│  Layer C: Compressed Conversation Window                │
│    smart-compressed recent exchanges + pinned facts      │
│    pre-compaction save to memory files                   │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│           AGENCY DIRECTOR (3-Gear Router)               │
│                                                         │
│  Gear 1: DIRECT     │ <1s  │ DB read, quick answers    │
│  Gear 2: INLINE     │ 2-5s │ Load role, advisory/review│
│  Gear 3: SPAWN      │ 10s+ │ Sub-agent, audits/research│
│                                                         │
│  Auto-picks gear based on task intent                   │
│  User can force: "do a deep audit" → Gear 3            │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│              AUTONOMY LAYER                             │
│                                                         │
│  Trust 1: INFORM    │ Queue actions, wait for approval  │
│  Trust 2: ACT+REPORT│ Execute, show what was done       │
│  Trust 3: AUTONOMOUS│ Execute silently, log only        │
│                                                         │
│  Configurable per action type per campaign              │
└───────────────────────────┬─────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    CLIENT UX                            │
│                                                         │
│  Campaign Pulse (health + briefing + actions)           │
│  Role Channels / Workspace blocks                      │
│  Command Palette (Cmd+K)                                │
│  Action Board (kanban with approve/revert)              │
│  Agent Status Bar (now playing)                         │
│  Morning Briefing (proactive summary)                   │
│  Report Generator (one-click client reports)            │
└─────────────────────────────────────────────────────────┘
```

---

## Session Summary

**Total Ideas Generated:** 43
**Techniques Used:** First Principles + Five Whys, Cross-Pollination + What If, SCAMPER
**Themes Identified:** 6 (Agent Identity, Agency Team, Data Architecture, Memory/Context, UX, Hybrid Architecture)
**Build Phases:** 5 phases over ~9+ weeks

**Key Breakthroughs:**
- File-based per-campaign memory using Claude Code's native system — no custom memory infrastructure needed
- Dream mode for overnight memory optimization and cross-campaign learning
- 3-gear routing that matches agent sophistication to task complexity
- Granular trust levels per action type instead of all-or-nothing autonomy
- Campaign health scores that eliminate the need to read raw metrics

**Critical Path:** Phase 1 (data sync + memory) unlocks everything else. Build this first.
