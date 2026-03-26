---
stepsCompleted: [01-init, 02-context-analysis, 03-starter-template, 04-architectural-decisions, 05-design-patterns, 06-data-integration, 07-validation, 08-complete]
inputDocuments: [docs/prd.md, docs/ux-design.md, docs/product-brief.md, docs/project-context.md]
workflowType: 'architecture'
lastStep: 8
projectType: 'web_app'
---

# Architecture Document - Google Ads Campaign Manager

**Author:** Wassim
**Date:** 2026-03-26
**Version:** 1.0
**Status:** Complete

---

## Table of Contents

1. [Project Context Analysis](#1-project-context-analysis)
2. [Technology Stack](#2-technology-stack)
3. [Architectural Decisions](#3-architectural-decisions)
4. [Design Patterns & Architecture](#4-design-patterns--architecture)
5. [Data & Integration Architecture](#5-data--integration-architecture)
6. [API Contracts](#6-api-contracts)
7. [Validation & Completeness](#7-validation--completeness)

---

## 1. Project Context Analysis

### Requirements Overview

#### Functional Requirements Summary

The PRD defines 30 functional requirements across 6 groups:

| Group | Count | Critical for Architecture |
|-------|-------|---------------------------|
| FR1: Account Management | 6 | OAuth flow, credential storage, account hierarchy discovery |
| FR2: Campaign Browsing | 8 | Google Ads API data fetching, caching, real-time display |
| FR3: AI Agent Chat | 10 | Claude Code SDK integration, streaming, MCP server connection |
| FR4: Guidelines Management | 7 | Filesystem read/write, markdown processing, context injection |
| FR5: Campaign Operations | 8 | Mutating API calls through AI agent, change logging |
| FR6: Data Display | 5 | Metrics aggregation, date range queries, charting |

#### Non-Functional Requirements Summary

| Category | Key Constraints |
|----------|----------------|
| **Performance** | <2s app load, <1s AI first-token, <3s API fetch, 5-min cache TTL |
| **Security** | Encrypted credential storage, localhost-only, no data exfiltration |
| **Integration** | MCP server as-is via Claude Code SDK, direct sdk_client for reads |
| **Reliability** | Graceful API errors, auth token refresh, conversation recovery |

#### Scale & Complexity

| Dimension | Scale |
|-----------|-------|
| Users | 1 (local, single user) |
| Accounts | 1-5 Google Ads accounts |
| Campaigns | 10-100 per account |
| Keywords | 100-10,000 per account |
| Concurrent API calls | Low (single user, sequential operations) |
| AI conversations | 1 active, unlimited history |
| Data retention | Local SQLite, unbounded (user manages) |

### Technical Constraints & Dependencies

| Constraint | Impact |
|------------|--------|
| **Claude Code SDK** is the AI runtime | Backend must spawn and manage Claude Code agent processes |
| **MCP server runs as-is** | No modifications to `google-ads-mcp/`; connect via MCP protocol |
| **Google Ads API v23** with v20 types | Direct queries must use v23 imports; MCP handles its own version |
| **Local-only deployment** | No cloud infra, no Docker required, runs as development server |
| **Windows platform** | File paths use backslashes, scripts must be cross-platform where possible |
| **Existing `.env` credentials** | Must read from or share with `google-ads-mcp/.env` |

### Cross-Cutting Concerns

1. **Authentication** - OAuth 2.0 token management (refresh, expiry detection, re-auth flow)
2. **Error handling** - Google Ads API errors, Claude Code SDK failures, filesystem errors
3. **Caching** - Campaign data caching with configurable TTL to reduce API calls
4. **Streaming** - SSE transport for AI chat responses from backend to frontend
5. **State management** - Global app state (selected account/campaign) synchronized across all components
6. **File watching** - Guidelines files may be edited externally; detect changes

---

## 2. Technology Stack

### Chosen Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Frontend** | React | 19+ | Mature ecosystem, component model fits three-panel layout |
| **Frontend Language** | TypeScript | 5.x | Type safety, IDE support, refactoring confidence |
| **Build Tool** | Vite | 6.x | Fast HMR, simple config, ESBuild for speed |
| **UI Components** | shadcn/ui | Latest | Customizable, Tailwind-native, copy-paste ownership |
| **Styling** | Tailwind CSS | 4.x | Utility-first, consistent design tokens, dark mode |
| **State (Client)** | Zustand | 5.x | Simple, lightweight, no boilerplate |
| **State (Server)** | TanStack Query | 5.x | Caching, refetching, stale-while-revalidate |
| **Routing** | React Router | 7.x | Standard SPA routing |
| **Tables** | TanStack Table | 8.x | Headless, virtual scrolling, sorting/filtering |
| **Charts** | Recharts | 2.x | React-native, composable, time-series support |
| **Markdown** | @uiw/react-md-editor | 4.x | View + edit modes, table support, lightweight |
| **Backend** | FastAPI | 0.115+ | Async-first, WebSocket/SSE native, Python ecosystem |
| **Backend Language** | Python | 3.11+ | Matches MCP server, Claude Code SDK is Python |
| **Database** | SQLite | Via aiosqlite | Zero-config, file-based, async support |
| **ORM** | SQLModel | 0.0.22+ | FastAPI-native, SQLAlchemy + Pydantic hybrid |
| **AI Agent** | Claude Code SDK | Latest | `claude_code_sdk` Python package |
| **Google Ads** | google-ads-python | 29.2.0 | Existing SDK, shared with MCP server |
| **Process Management** | uvicorn | 0.34+ | ASGI server for FastAPI |

### Project Structure

```
google-ads-webapp/
├── docs/                          # BMAD documents (PRD, UX, Architecture, Epics)
│
├── frontend/                      # React SPA
│   ├── src/
│   │   ├── main.tsx              # App entry point
│   │   ├── App.tsx               # Root component with layout
│   │   ├── components/
│   │   │   ├── ui/               # shadcn/ui components (Button, Card, etc.)
│   │   │   ├── layout/           # Header, Sidebar, ChatPanel, ContentArea
│   │   │   ├── campaign/         # CampaignList, CampaignDetail, MetricCard
│   │   │   ├── chat/             # ChatMessage, ToolCallBlock, ContextBadge
│   │   │   ├── guidelines/       # GuidelinesViewer, GuidelinesEditor
│   │   │   └── setup/            # SetupWizard steps
│   │   ├── hooks/                # Custom React hooks
│   │   │   ├── useAccounts.ts    # Account data fetching
│   │   │   ├── useCampaigns.ts   # Campaign data fetching
│   │   │   ├── useChat.ts        # Chat state + SSE connection
│   │   │   └── useGuidelines.ts  # Guidelines CRUD
│   │   ├── stores/               # Zustand stores
│   │   │   ├── appStore.ts       # Global state (selectedAccount, selectedCampaign)
│   │   │   └── chatStore.ts      # Chat messages, threads, streaming state
│   │   ├── lib/                  # Utilities
│   │   │   ├── api.ts            # API client (fetch wrapper)
│   │   │   └── utils.ts          # Formatting, date helpers
│   │   └── types/                # TypeScript interfaces
│   │       ├── campaign.ts       # Campaign, AdGroup, Keyword, Ad types
│   │       ├── chat.ts           # Message, ToolCall, Thread types
│   │       └── account.ts        # Account, Credential types
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                       # Python FastAPI backend
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── config.py             # Configuration management
│   │   ├── database.py           # SQLite connection + models
│   │   ├── routers/
│   │   │   ├── accounts.py       # Account management endpoints
│   │   │   ├── campaigns.py      # Campaign data endpoints
│   │   │   ├── chat.py           # AI chat SSE endpoint
│   │   │   ├── guidelines.py     # Guidelines CRUD endpoints
│   │   │   └── setup.py          # Setup/credential endpoints
│   │   ├── services/
│   │   │   ├── google_ads.py     # Google Ads API wrapper (imports sdk_client)
│   │   │   ├── agent.py          # Claude Code SDK agent management
│   │   │   ├── guidelines.py     # Guidelines file operations
│   │   │   └── cache.py          # Campaign data cache layer
│   │   ├── models/
│   │   │   ├── database.py       # SQLModel definitions
│   │   │   └── schemas.py        # Pydantic request/response schemas
│   │   └── utils/
│   │       ├── google_ads_helpers.py  # Query builders, metric formatting
│   │       └── markdown.py       # Markdown parsing for guidelines sections
│   ├── pyproject.toml            # uv package management
│   └── .env                      # Backend config (MCP server path, DB path)
│
├── data/                          # Local data directory
│   ├── app.db                    # SQLite database
│   └── guidelines/               # Campaign guidelines .md files
│       ├── campaign_guidelines.md
│       ├── mena_campaign_guidelines.md
│       └── greece_campaign_guidelines.md
│
└── scripts/
    ├── dev.sh                    # Start both frontend + backend
    └── setup.sh                  # Initial project setup
```

---

## 3. Architectural Decisions

### AD-1: Claude Code SDK as AI Agent Runtime

#### Context

The AI agent needs to access 90+ Google Ads MCP tools, stream responses, and handle tool-use loops. Three options: (A) Claude API directly with manual tool definitions, (B) Claude Code SDK with MCP server, (C) Local LLM.

#### Decision

Use the **Claude Code SDK** (`claude_code_sdk` Python package) to spawn agent subprocesses that connect to the existing MCP server.

#### Rationale

- Uses existing Claude Code subscription (no additional API costs)
- Natively supports MCP server connections (same protocol as Claude Desktop)
- Handles tool-use loops, streaming, and context management
- New MCP tools are automatically available without web app changes
- Battle-tested in Claude Desktop for this exact MCP server

#### Implementation

```python
# backend/app/services/agent.py
from claude_code_sdk import ClaudeCodeAgent, AgentConfig

async def create_agent_session(system_prompt: str) -> ClaudeCodeAgent:
    mcp_servers = [
        {
            "name": "google-ads",
            "command": "uv",
            "args": ["run", "python", "main.py"],
            "cwd": settings.MCP_SERVER_PATH
        }
    ]

    # Add Chrome MCP if configured and available
    if settings.CHROME_MCP_ENABLED:
        mcp_servers.append({
            "name": "chrome",
            "command": settings.CHROME_MCP_COMMAND,
            "args": settings.CHROME_MCP_ARGS
        })

    config = AgentConfig(
        mcp_servers=mcp_servers,
        system_prompt=system_prompt,
        model="claude-sonnet-4-6"  # configurable
    )
    return ClaudeCodeAgent(config)
```

#### Implications

- Backend must manage Claude Code agent subprocess lifecycle
- Streaming responses come from the SDK and must be forwarded via SSE to frontend
- Agent startup has latency (~1-2s for MCP server initialization, plus Chrome MCP if enabled)
- Must handle agent process crashes gracefully
- Chrome MCP is optional - agent works with Google Ads MCP alone

---

### AD-2: Direct Google Ads SDK for Read-Only Data

#### Context

The UI needs campaign data (metrics, structure) for the campaign browser. Two options: (A) Always go through the AI agent, (B) Direct API calls for reads, AI agent for writes/analysis.

#### Decision

Use **direct Google Ads SDK calls** (`GoogleAdsSdkClient` imported from the existing MCP server codebase) for read-only data fetching. Use the AI agent only for analysis, recommendations, and mutating operations.

#### Rationale

- Read-only queries are faster without AI agent overhead (~500ms vs ~3-5s)
- Reduces Claude API token usage for simple data fetching
- Campaign browser needs structured data, not natural language responses
- AI agent is reserved for its strengths: analysis, multi-step operations, guideline-aware decisions

#### Implementation

```python
# backend/app/services/google_ads.py
import sys
sys.path.insert(0, settings.MCP_SERVER_PATH)
from src.sdk_client import GoogleAdsSdkClient

class GoogleAdsService:
    def __init__(self):
        self.client = GoogleAdsSdkClient()

    async def get_campaigns(self, customer_id: str) -> list[Campaign]:
        # Direct GAQL query for campaign list with metrics
        query = """
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.budget.amount_micros,
                   metrics.impressions, metrics.clicks,
                   metrics.conversions, metrics.cost_micros
            FROM campaign
            WHERE campaign.status != 'REMOVED'
            ORDER BY campaign.name
        """
        return await self._execute_query(customer_id, query)
```

#### Implications

- Backend has a dependency on the MCP server's `src/` directory (added to Python path)
- Must handle the v20/v23 type mismatch when constructing queries
- Credentials are shared via `.env` file (single source of truth)
- Cache layer sits between this service and the API endpoints

---

### AD-3: SSE for Chat Streaming (Not WebSocket)

#### Context

AI agent responses must stream token-by-token to the frontend. Options: (A) WebSocket, (B) Server-Sent Events (SSE), (C) Long polling.

#### Decision

Use **Server-Sent Events (SSE)** for streaming chat responses from backend to frontend.

#### Rationale

- SSE is simpler than WebSocket for unidirectional streaming (server → client)
- Native browser support via `EventSource` API
- HTTP-based, works through any proxy/reverse proxy without special config
- User messages are sent via regular POST requests (no need for bidirectional socket)
- FastAPI has excellent SSE support via `StreamingResponse`

#### Implementation

```python
# backend/app/routers/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

@router.post("/chat/{conversation_id}/message")
async def send_message(conversation_id: str, message: ChatMessage):
    # Save user message, prepare context
    ...

    async def event_stream():
        async for event in agent.stream(message.content):
            if event.type == "text":
                yield f"data: {json.dumps({'type': 'text', 'content': event.text})}\n\n"
            elif event.type == "tool_call":
                yield f"data: {json.dumps({'type': 'tool_call', 'name': event.name, 'input': event.input})}\n\n"
            elif event.type == "tool_result":
                yield f"data: {json.dumps({'type': 'tool_result', 'name': event.name, 'output': event.output})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Frontend consumption:
```typescript
// frontend/src/hooks/useChat.ts
const eventSource = new EventSource(`/api/chat/${conversationId}/message`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'text': appendToMessage(data.content); break;
    case 'tool_call': addToolCall(data); break;
    case 'tool_result': updateToolCall(data); break;
    case 'done': closeStream(); break;
  }
};
```

#### Implications

- User messages sent via POST, responses streamed via SSE (two separate HTTP mechanisms)
- SSE auto-reconnects on network interruption
- Must handle SSE connection cleanup when user navigates away or starts a new message

---

### AD-4: SQLite for All Structured Local Data

#### Context

The app needs to store conversations, preferences, cached metrics, and account configs locally.

#### Decision

Use **SQLite** (via `aiosqlite` + `SQLModel`) for all structured data. Use the **filesystem** only for guidelines `.md` files and the `.env` credentials file.

#### Rationale

- Zero configuration, no database server to run
- Single file (`data/app.db`), easy to backup/move
- Async support via `aiosqlite`
- SQLModel provides type-safe models that work with both FastAPI and SQLAlchemy
- Sufficient for single-user, local application

#### Implications

- No concurrent write contention (single user)
- Database migrations handled via simple schema version checks on startup
- SQLite WAL mode enabled for better read concurrency during streaming

---

### AD-5: Guidelines as Filesystem Markdown (Not Database)

#### Context

Campaign guidelines could be stored in SQLite or as markdown files on the filesystem.

#### Decision

Keep guidelines as **markdown files on the filesystem**, matching the existing format.

#### Rationale

- Backward compatible with existing `CAMPAIGN_GUIDELINES.md` files
- Files can be edited externally (VS Code, any text editor)
- Version controllable with git
- The markdown format is the "single source of truth" that both human and AI reference
- Converting to database would break the existing workflow and add migration complexity

#### Implementation

```python
# backend/app/services/guidelines.py
class GuidelinesService:
    def __init__(self, guidelines_dir: Path):
        self.dir = guidelines_dir

    async def get_guidelines(self, filename: str) -> str:
        path = self.dir / filename
        return path.read_text(encoding='utf-8')

    async def save_guidelines(self, filename: str, content: str):
        path = self.dir / filename
        path.write_text(content, encoding='utf-8')

    async def get_campaign_section(self, filename: str, campaign_name: str) -> str:
        # Parse markdown, extract the section for the specific campaign
        content = await self.get_guidelines(filename)
        return self._extract_campaign_section(content, campaign_name)
```

#### Implications

- File watching needed to detect external edits (optional, can use poll-on-access)
- Guidelines parsing needed to extract campaign-specific sections for AI context injection
- User can choose to point the app at the existing guidelines directory or copy files to `data/guidelines/`

---

### AD-6: Monorepo with Separate Frontend/Backend

#### Context

How to organize the codebase: monorepo or separate repos.

#### Decision

**Monorepo** with `frontend/` and `backend/` directories under a single project root.

#### Rationale

- Single git repository, single version history
- Dev script can start both servers with one command
- Shared types/contracts can be referenced across both
- Simpler for a single-developer project
- No need for npm workspaces or Python namespace packages - just two directories

#### Implications

- Frontend runs on Vite dev server (port 5173)
- Backend runs on uvicorn (port 8000)
- Vite proxy config forwards `/api/*` to the backend during development
- Production: Vite builds static files, FastAPI serves them + API

---

### AD-7: Chrome MCP for Browser Automation

#### Context

Some campaign management tasks go beyond the Google Ads API: GTM tag setup/debugging, landing page auditing, conversion tag verification, and accessing Google Ads UI-only features. Currently in Claude Desktop, the agent uses the Chrome MCP (claude-in-chrome extension) to handle these tasks.

#### Decision

Support the **Chrome MCP server as an optional second MCP server** alongside the Google Ads MCP. The agent is configured with both and intelligently decides which tools to use based on the task.

#### Rationale

- Eliminates the need to fall back to Claude Desktop for browser-dependent tasks (GTM, landing page audits)
- The Chrome MCP is already used successfully in Claude Desktop for this exact workflow
- No additional development needed on the MCP side - both servers run as-is
- Optional: the app works fully for API-based tasks without Chrome running
- The agent naturally decides when to use API vs browser tools based on the task

#### Implementation

The Chrome MCP is configured in the agent service as an optional second MCP server (see AD-1 implementation). Configuration is stored in the `config` table:

```python
# backend/app/config.py
class Settings:
    CHROME_MCP_ENABLED: bool = True  # configurable via setup wizard
    CHROME_MCP_COMMAND: str = "npx"  # or direct path to chrome MCP executable
    CHROME_MCP_ARGS: list[str] = ["-y", "@anthropic/claude-chrome-mcp"]
```

Tool call events from Chrome MCP are tagged with a `source: "chrome"` field so the frontend can display them with a distinct browser icon:

```python
# In the SSE stream, browser tool calls include source metadata
yield f'data: {json.dumps({
    "type": "tool_call",
    "source": "chrome",  # vs "google-ads" for API tools
    "name": event.name,
    "input": event.input
})}\n\n'
```

#### Implications

- Chrome must be running with the claude-in-chrome extension for browser tasks
- Agent startup is slightly slower when Chrome MCP is enabled (~1s additional)
- Browser actions are visible to the user in the tool call blocks (full transparency)
- If Chrome is not available, the agent gracefully falls back to API-only mode
- GTM edits and landing page changes done through the browser are real actions - confirmation mode is important here
- The agent can chain API + browser tools in a single response (e.g., check conversion status via API, then inspect GTM via browser)

---

## 4. Design Patterns & Architecture

### Architecture Pattern: Client-Server SPA with AI Agent Sidecar

```
┌─────────────────────────────────────────────────────┐
│                     FRONTEND                         │
│                  React SPA (Vite)                    │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Zustand   │  │ TanStack │  │ SSE Client       │  │
│  │ Store     │  │ Query    │  │ (Chat Stream)    │  │
│  │ (UI state)│  │ (data)   │  │                  │  │
│  └──────────┘  └────┬─────┘  └────────┬─────────┘  │
│                      │                 │             │
└──────────────────────┼─────────────────┼─────────────┘
                       │ REST            │ SSE
                       ▼                 ▼
┌──────────────────────┴─────────────────┴─────────────┐
│                     BACKEND                           │
│                FastAPI (Python)                       │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ REST Routers  │  │ Chat Router  │  │ Guidelines │ │
│  │ (accounts,    │  │ (SSE stream) │  │ Router     │ │
│  │  campaigns)   │  │              │  │ (CRUD)     │ │
│  └───────┬──────┘  └──────┬───────┘  └─────┬──────┘ │
│          │                │                  │        │
│  ┌───────▼──────┐  ┌──────▼───────┐  ┌─────▼──────┐ │
│  │ GoogleAds    │  │ Agent        │  │ Guidelines │ │
│  │ Service      │  │ Service      │  │ Service    │ │
│  │ (direct SDK) │  │ (Claude Code)│  │ (filesystem│ │
│  └───────┬──────┘  └──────┬───────┘  └─────┬──────┘ │
│          │                │                  │        │
│  ┌───────▼──────┐  ┌──────▼───────┐  ┌─────▼──────┐ │
│  │ Cache Layer  │  │ MCP Servers  │  │ Local .md  │ │
│  │ (SQLite)     │  │ (subprocs)   │  │ files      │ │
│  └───────┬──────┘  └──┬──────┬───┘  └────────────┘ │
│          │             │      │                       │
└──────────┼─────────────┼──────┼───────────────────────┘
           │             │      │
           ▼             ▼      ▼
    Google Ads API  Claude   Chrome Browser
    (REST/gRPC)     API      (GTM, landing pages)
                (via Claude Code)
```

### Request Flow Patterns

#### Pattern 1: Data Read (Campaign List)

```
Frontend                  Backend                    Google Ads API
   │                        │                            │
   │  GET /api/campaigns    │                            │
   │───────────────────────>│                            │
   │                        │  Check cache (SQLite)      │
   │                        │──────────┐                 │
   │                        │          │ Cache hit?       │
   │                        │<─────────┘                 │
   │                        │                            │
   │                        │  [If cache miss]           │
   │                        │  GAQL query via sdk_client  │
   │                        │───────────────────────────>│
   │                        │  Campaign data              │
   │                        │<───────────────────────────│
   │                        │  Update cache               │
   │                        │                            │
   │  JSON response         │                            │
   │<───────────────────────│                            │
```

#### Pattern 2: AI Chat Message (API + Browser)

```
Frontend                  Backend                    Claude Code SDK       MCP Servers
   │                        │                            │               (Google Ads + Chrome)
   │  POST /api/chat/msg    │                            │                    │
   │───────────────────────>│                            │                    │
   │                        │  Load guidelines           │                    │
   │                        │  Build system prompt       │                    │
   │                        │  Send to agent             │                    │
   │                        │───────────────────────────>│                    │
   │                        │                            │  Tool call         │
   │  SSE: tool_call        │                            │───────────────────>│
   │<───────────────────────│  (forwarded)               │                    │
   │                        │                            │  Tool result       │
   │  SSE: tool_result      │                            │<───────────────────│
   │<───────────────────────│  (forwarded)               │                    │
   │                        │                            │  Text tokens       │
   │  SSE: text (streaming) │                            │<───────────────────│
   │<───────────────────────│  (forwarded)               │                    │
   │                        │                            │                    │
   │  SSE: done             │  Save to conversation DB   │                    │
   │<───────────────────────│                            │                    │
```

#### Pattern 3: Guidelines Edit

```
Frontend                  Backend                    Filesystem
   │                        │                            │
   │  PUT /api/guidelines   │                            │
   │  {filename, content}   │                            │
   │───────────────────────>│                            │
   │                        │  Write .md file            │
   │                        │───────────────────────────>│
   │                        │  Success                   │
   │                        │<───────────────────────────│
   │                        │  Invalidate agent context  │
   │  200 OK                │                            │
   │<───────────────────────│                            │
   │                        │                            │
   │  [Next chat message]   │                            │
   │  POST /api/chat/msg    │                            │
   │───────────────────────>│                            │
   │                        │  Re-load updated guideline │
   │                        │  Inject into system prompt │
   │                        │  ...                       │
```

### Cross-Cutting Concerns Implementation

#### Error Handling Strategy

```python
# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

@app.exception_handler(GoogleAdsException)
async def google_ads_error_handler(request: Request, exc: GoogleAdsException):
    return JSONResponse(
        status_code=502,
        content={
            "error": "google_ads_error",
            "message": str(exc),
            "errors": [e.message for e in exc.failure.errors]
        }
    )

@app.exception_handler(AgentConnectionError)
async def agent_error_handler(request: Request, exc: AgentConnectionError):
    return JSONResponse(
        status_code=503,
        content={
            "error": "agent_unavailable",
            "message": "Claude Code agent is not available. Check your subscription and network."
        }
    )
```

#### Caching Strategy

```python
# backend/app/services/cache.py
class CacheService:
    def __init__(self, db: AsyncSession, ttl_seconds: int = 300):
        self.db = db
        self.ttl = ttl_seconds

    async def get_or_fetch(self, key: str, fetch_fn: Callable) -> Any:
        cached = await self.db.get(CacheEntry, key)
        if cached and (time.time() - cached.fetched_at) < self.ttl:
            return json.loads(cached.data)
        fresh_data = await fetch_fn()
        await self._store(key, fresh_data)
        return fresh_data
```

#### Authentication Token Management

```python
# backend/app/services/google_ads.py
class GoogleAdsService:
    async def _ensure_valid_token(self):
        try:
            # Attempt a lightweight API call to verify token
            await self._get_customer_info(self.login_customer_id)
        except GoogleAdsException as e:
            if "AUTHENTICATION_ERROR" in str(e):
                raise TokenExpiredError("OAuth refresh token has expired. Re-authentication required.")
            raise
```

---

## 5. Data & Integration Architecture

### Data Model Overview

#### SQLite Schema

```sql
-- Account configurations
CREATE TABLE accounts (
    id TEXT PRIMARY KEY,           -- Google Ads customer ID
    name TEXT NOT NULL,
    parent_id TEXT,                -- Parent account ID (for hierarchy)
    level TEXT NOT NULL,           -- 'manager', 'sub_manager', 'client'
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES accounts(id)
);

-- App configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Keys: mcp_server_path, chrome_mcp_enabled, chrome_mcp_command, guidelines_dir, default_account, theme, cache_ttl

-- Conversation threads
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,           -- UUID
    account_id TEXT,
    campaign_id TEXT,              -- NULL for account-level conversations
    campaign_name TEXT,
    title TEXT,                    -- Auto-generated or user-set
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Chat messages
CREATE TABLE messages (
    id TEXT PRIMARY KEY,           -- UUID
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,            -- 'user', 'assistant', 'tool_call', 'tool_result'
    content TEXT NOT NULL,
    tool_name TEXT,                -- For tool_call/tool_result messages
    tool_source TEXT,              -- 'google-ads' or 'chrome' (which MCP server)
    tool_input TEXT,               -- JSON string for tool_call
    tool_output TEXT,              -- JSON string for tool_result
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Cached campaign data
CREATE TABLE cache (
    key TEXT PRIMARY KEY,          -- e.g., "campaigns:7178239091" or "keywords:23636342079"
    data TEXT NOT NULL,            -- JSON
    fetched_at REAL NOT NULL       -- Unix timestamp
);

-- Guidelines file metadata
CREATE TABLE guidelines_meta (
    filename TEXT PRIMARY KEY,
    campaign_id TEXT,
    campaign_name TEXT,
    last_modified REAL,            -- Unix timestamp from filesystem
    sections TEXT                  -- JSON array of section names found
);
```

#### SQLModel Definitions

```python
# backend/app/models/database.py
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
import uuid

class Account(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    parent_id: Optional[str] = Field(default=None, foreign_key="account.id")
    level: str  # 'manager', 'sub_manager', 'client'
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Conversation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    account_id: Optional[str] = Field(default=None, foreign_key="account.id")
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Message(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id")
    role: str  # 'user', 'assistant', 'tool_call', 'tool_result'
    content: str
    tool_name: Optional[str] = None
    tool_source: Optional[str] = None  # 'google-ads' or 'chrome'
    tool_input: Optional[str] = None  # JSON
    tool_output: Optional[str] = None  # JSON
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Integration Points

#### Integration 1: Google Ads MCP Server ↔ Claude Code SDK

```
Connection: MCP protocol over stdio
Direction: Bidirectional (tool calls + results)
Configuration:
  - Command: "uv run python main.py"
  - CWD: {MCP_SERVER_PATH} (e.g., "../google ads/google-ads-mcp")
  - The MCP server's .env provides Google Ads credentials
Lifecycle:
  - Agent process spawned per chat session (or pooled)
  - MCP server starts as subprocess of the agent
  - Both terminate when the chat session ends
```

#### Integration 1b: Chrome MCP Server ↔ Claude Code SDK (Optional)

```
Connection: MCP protocol over stdio
Direction: Bidirectional (tool calls + results)
Configuration:
  - Command: configurable (e.g., "npx -y @anthropic/claude-chrome-mcp")
  - Requires Chrome running with claude-in-chrome extension
  - Configured in app settings, disabled by default until user enables
Tools provided:
  - navigate: Go to URL in Chrome tab
  - read_page: Extract page content
  - get_page_text: Get page text content
  - javascript_tool: Execute JavaScript in page context
  - form_input: Fill form fields
  - find: Search for elements on page
  - tabs_create_mcp: Create new browser tab
  - tabs_context_mcp: Get current tab context
Lifecycle:
  - Chrome MCP starts alongside Google Ads MCP when agent is spawned
  - If Chrome is not running, Chrome MCP fails gracefully
  - Agent continues with Google Ads MCP only
Use cases:
  - GTM container inspection and tag editing
  - Landing page tag audits
  - Conversion tag verification
  - Google Ads UI-only settings
```

#### Integration 2: Backend ↔ Google Ads API (Direct)

```
Connection: gRPC via google-ads-python SDK
Direction: Read-only queries
Configuration:
  - Imports GoogleAdsSdkClient from MCP server's src/
  - Shares .env credentials file
  - Uses GAQL (Google Ads Query Language) for structured queries
Usage:
  - Campaign list with metrics
  - Ad group/keyword/ad structure
  - Search term reports
  - Change history
Caching:
  - Results cached in SQLite with configurable TTL (default 5 min)
  - Cache invalidated after AI agent performs mutations
```

#### Integration 3: Backend ↔ Local Filesystem (Guidelines)

```
Connection: Direct file I/O
Direction: Bidirectional (read/write)
Path: Configurable, default: {PROJECT_ROOT}/data/guidelines/
Format: Markdown (.md) files
Operations:
  - List all .md files in directory
  - Read file content
  - Write file content (with atomic write via temp file + rename)
  - Parse markdown to extract campaign-specific sections
  - Watch for external modifications (poll mtime on access)
```

#### Integration 4: Frontend ↔ Backend

```
Connection: HTTP (REST + SSE)
Base URL: http://localhost:8000/api
Authentication: None (localhost only)

REST Endpoints: Standard JSON request/response
SSE Endpoint: POST /api/chat/{id}/message → StreamingResponse

CORS: Configured for localhost:5173 (Vite dev server)
Proxy: Vite dev server proxies /api/* to backend in development
```

### System Context Injection Flow

This is the core architectural feature - how campaign guidelines become AI context:

```python
# backend/app/services/agent.py

async def build_system_prompt(
    account_id: str,
    campaign_id: Optional[str],
    guidelines_service: GuidelinesService
) -> str:
    parts = []

    # 1. Base instructions
    parts.append(BASE_AGENT_INSTRUCTIONS)

    # 2. Account context
    parts.append(f"You are managing Google Ads account {account_id}.")

    # 3. Global rules (from main guidelines file)
    global_rules = await guidelines_service.get_global_rules("campaign_guidelines.md")
    if global_rules:
        parts.append(f"## Global Campaign Rules\n\n{global_rules}")

    # 4. Campaign-specific guidelines (if campaign selected)
    if campaign_id:
        campaign_section = await guidelines_service.get_campaign_section(
            "campaign_guidelines.md", campaign_id
        )
        if campaign_section:
            parts.append(f"## Campaign-Specific Guidelines\n\n{campaign_section}")

        # Check for region-specific guidelines
        for region_file in ["mena_campaign_guidelines.md", "greece_campaign_guidelines.md"]:
            region_section = await guidelines_service.get_campaign_section(
                region_file, campaign_id
            )
            if region_section:
                parts.append(f"## Regional Guidelines\n\n{region_section}")

    return "\n\n---\n\n".join(parts)
```

---

## 6. API Contracts

### REST API Endpoints

#### Accounts

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/accounts` | List all configured accounts | `Account[]` |
| GET | `/api/accounts/{id}` | Get account details | `Account` |
| POST | `/api/accounts/discover` | Discover accessible accounts using credentials | `Account[]` |
| POST | `/api/setup/credentials` | Save Google Ads API credentials | `{success: bool}` |
| GET | `/api/setup/status` | Check if app is configured | `{configured: bool}` |

#### Campaigns

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/accounts/{id}/campaigns` | List campaigns with metrics | `Campaign[]` |
| GET | `/api/campaigns/{id}` | Campaign detail with settings | `CampaignDetail` |
| GET | `/api/campaigns/{id}/adgroups` | Ad groups with metrics | `AdGroup[]` |
| GET | `/api/campaigns/{id}/keywords` | All keywords with metrics | `Keyword[]` |
| GET | `/api/campaigns/{id}/ads` | All ads with assets | `Ad[]` |
| GET | `/api/campaigns/{id}/metrics` | Metrics for date range | `MetricsSeries` |

Query params: `date_from`, `date_to`, `sort`, `filter`

#### Chat

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/conversations` | List conversations | `Conversation[]` |
| POST | `/api/conversations` | Create conversation | `Conversation` |
| GET | `/api/conversations/{id}/messages` | Get message history | `Message[]` |
| POST | `/api/conversations/{id}/message` | Send message + stream response | `SSE stream` |

SSE event types:
```
data: {"type": "text", "content": "Based on..."}
data: {"type": "tool_call", "id": "tc_1", "source": "google-ads", "name": "get_campaign", "input": {...}}
data: {"type": "tool_call", "id": "tc_2", "source": "chrome", "name": "navigate", "input": {"url": "..."}}
data: {"type": "tool_result", "id": "tc_1", "source": "google-ads", "output": {...}, "status": "success"}
data: {"type": "tool_result", "id": "tc_2", "source": "chrome", "output": {...}, "status": "success"}
data: {"type": "done", "message_id": "msg_123"}
data: {"type": "error", "message": "Agent connection failed"}
```
Note: `source` field identifies which MCP server the tool belongs to ("google-ads" or "chrome"), enabling the frontend to display browser actions with a distinct icon.

#### Guidelines

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/guidelines` | List all guidelines files | `GuidelineFile[]` |
| GET | `/api/guidelines/{filename}` | Get file content | `{filename, content, lastModified}` |
| PUT | `/api/guidelines/{filename}` | Update file content | `{filename, lastModified}` |
| POST | `/api/guidelines` | Create new guidelines file | `{filename}` |
| GET | `/api/guidelines/{filename}/section/{campaign_id}` | Get campaign section | `{content}` |

### Key TypeScript Interfaces (Frontend)

```typescript
// frontend/src/types/campaign.ts
interface Campaign {
  id: string;
  name: string;
  status: 'ENABLED' | 'PAUSED' | 'REMOVED';
  channelType: string;
  budget: { amountMicros: number; deliveryMethod: string };
  biddingStrategy: string;
  metrics: CampaignMetrics;
}

interface CampaignMetrics {
  impressions: number;
  clicks: number;
  ctr: number;
  costMicros: number;
  conversions: number;
  cpa: number;
  impressionSharePercent?: number;
  lostImpressionShareRank?: number;
  lostImpressionShareBudget?: number;
}

// frontend/src/types/chat.ts
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  createdAt: string;
}

interface ToolCall {
  id: string;
  source: 'google-ads' | 'chrome';  // which MCP server
  name: string;
  input: Record<string, any>;
  output?: Record<string, any>;
  status: 'pending' | 'success' | 'error';
}

interface ChatStreamEvent {
  type: 'text' | 'tool_call' | 'tool_result' | 'done' | 'error';
  content?: string;
  id?: string;
  source?: 'google-ads' | 'chrome';  // which MCP server
  name?: string;
  input?: Record<string, any>;
  output?: Record<string, any>;
  status?: string;
  message?: string;
}
```

---

## 7. Validation & Completeness

### Architecture Review Checklist

| Concern | Addressed | How |
|---------|-----------|-----|
| All FRs have a clear implementation path | Yes | Data reads via direct SDK, operations via AI agent, guidelines via filesystem |
| AI agent can access all 90+ MCP tools | Yes | Claude Code SDK connects to existing MCP server as-is |
| Browser automation available for beyond-API tasks | Yes | Chrome MCP as optional second MCP server (AD-7) |
| Guidelines auto-injection works | Yes | System prompt built dynamically from guidelines files per campaign |
| Streaming chat works end-to-end | Yes | Claude Code SDK → Backend SSE → Frontend EventSource |
| Credentials are secure | Yes | Encrypted in SQLite or shared via .env (localhost only) |
| No external data leakage | Yes | All endpoints localhost-only, no external connections except Google Ads API + Claude API |
| Existing files are backward compatible | Yes | Guidelines stay as markdown, .env shared, MCP server unmodified |
| New MCP tools auto-available | Yes | Claude Code SDK discovers tools from MCP server at connection time |
| Error handling at all boundaries | Yes | Google Ads errors, agent errors, filesystem errors all have handlers |
| Cache invalidation on mutations | Yes | Agent mutation detection triggers cache invalidation |

### Readiness Assessment

| Area | Status | Notes |
|------|--------|-------|
| Technology choices validated | Ready | All technologies are mature, well-documented, compatible |
| Data model complete | Ready | SQLite schema covers all MVP data needs |
| API contracts defined | Ready | REST + SSE endpoints cover all frontend needs |
| Integration patterns clear | Ready | Four integration paths (Google Ads MCP, Chrome MCP, direct SDK, filesystem) well-defined |
| Deployment model | Ready | Local dev server (Vite + uvicorn), no cloud needed |
| Security model | Ready | Localhost-only, encrypted credentials, no multi-user concerns |

### Known Risks

| Risk | Mitigation |
|------|------------|
| Claude Code SDK API may change | Pin SDK version, abstract behind AgentService interface |
| MCP server startup latency (~1-2s) | Pool/reuse agent sessions, lazy initialization |
| Google Ads API quota limits | Cache aggressively, batch queries where possible |
| SQLite write concurrency during streaming | WAL mode, single-writer pattern, queue mutations |
| Guidelines file conflicts (external edit during web edit) | Last-write-wins with mtime check, warn user |
| Chrome not running when browser task requested | Agent detects Chrome MCP unavailability, informs user to start Chrome, continues in API-only mode |
| Browser actions affect real external systems (GTM) | Confirmation mode covers browser mutations; tool transparency shows all actions |
