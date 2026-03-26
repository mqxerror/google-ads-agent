---
stepsCompleted: [01-prerequisites, 02-epic-design, 03-stories, 04-validation]
inputDocuments: [docs/prd.md, docs/architecture.md, docs/ux-design.md]
workflowType: 'epics-and-stories'
lastStep: 4
---

# Google Ads Campaign Manager - Epic Breakdown

**Author:** Wassim
**Date:** 2026-03-26
**Version:** 1.0
**Status:** Complete

---

## Requirements Inventory

### Functional Requirements

| ID | Requirement | Phase |
|----|-------------|-------|
| FR1.1 | Setup wizard for Google Ads API credentials | MVP |
| FR1.2 | Validate credentials by querying accessible accounts | MVP |
| FR1.3 | Display account hierarchy as navigable tree | MVP |
| FR1.4 | Switch between client accounts within a session | MVP |
| FR1.5 | Store account configurations in encrypted SQLite | MVP |
| FR1.6 | Detect and handle expired OAuth refresh tokens | MVP |
| FR2.1 | Display all campaigns in sortable, filterable list | MVP |
| FR2.2 | Show campaign metrics (impressions, clicks, conversions, cost, CPA) | MVP |
| FR2.3 | Drill into campaign → ad groups tree | MVP |
| FR2.4 | Display keywords, ads, assets with inline status and metrics | MVP |
| FR2.5 | Filter campaigns by status, name, type | MVP |
| FR2.6 | Show campaign settings in detail panel | MVP |
| FR2.7 | Performance charts for selected campaign | Growth |
| FR2.8 | Date range comparison | Growth |
| FR3.1 | Chat interface with streaming AI responses | MVP |
| FR3.2 | Agent powered by Claude Code SDK with MCP server | MVP |
| FR3.3 | Auto-load campaign guidelines into AI context | MVP |
| FR3.4 | Auto-load global rules into AI context | MVP |
| FR3.5 | All 90+ MCP tools accessible to agent | MVP |
| FR3.6 | Display tool invocations with expandable details | MVP |
| FR3.7 | Confirmation mode for mutating operations | MVP |
| FR3.8 | Persist conversation history in SQLite | Growth |
| FR3.9 | Multiple conversation threads per campaign | Growth |
| FR3.10 | Search conversation history | Growth |
| FR4.1 | Display guidelines in formatted markdown view | MVP |
| FR4.2 | Markdown editor for guidelines | MVP |
| FR4.3 | Store guidelines as .md files on filesystem | MVP |
| FR4.4 | Support existing CAMPAIGN_GUIDELINES.md structure | MVP |
| FR4.5 | Create guidelines from template for new campaigns | MVP |
| FR4.6 | Auto-save with debounce | MVP |
| FR4.7 | Updated guidelines reflected in AI context on next message | MVP |
| FR5.1 | Create campaigns via AI chat | MVP |
| FR5.2 | Modify campaign settings via AI or direct UI | MVP |
| FR5.3 | Manage keywords via AI or UI | MVP |
| FR5.4 | Create/manage responsive search ads via AI | MVP |
| FR5.5 | Search term reports with negative keyword management | Growth |
| FR5.6 | Manage conversion actions and tracking | Growth |
| FR5.7 | Warn when multiple change types in same day | MVP |
| FR5.8 | Auto-log changes to guidelines Change Log | Growth |
| FR6.1 | Campaign performance overview with date ranges | MVP |
| FR6.2 | Conversion tracking status display | Growth |
| FR6.3 | Impression share metrics | Growth |
| FR6.4 | Change history from Google Ads API | Growth |
| FR6.5 | Export campaign data to CSV | Growth |

| FR7.1 | AI agent has access to Chrome browser automation via Chrome MCP | MVP |
| FR7.2 | Agent can navigate to external web UIs (GTM, Google Ads UI, landing pages) | MVP |
| FR7.3 | Browser actions displayed with distinct browser icon in chat | MVP |
| FR7.4 | Agent intelligently decides API vs browser tools based on task | MVP |
| FR7.5 | Browser automation requires Chrome with claude-in-chrome extension | MVP |
| FR7.6 | Setup wizard includes optional Chrome MCP configuration | MVP |
| FR7.7 | Graceful fallback to API-only mode when Chrome unavailable | MVP |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-P1 | App loads in under 2 seconds |
| NFR-P2 | Route navigation under 500ms |
| NFR-P5 | AI first-token under 1 second |
| NFR-P8 | 5-minute cache TTL |
| NFR-S1 | Encrypted credential storage |
| NFR-S3 | Localhost-only endpoints |
| NFR-I1 | MCP server integration via Claude Code SDK |
| NFR-I2 | Direct sdk_client for read-only queries |
| NFR-I3 | Filesystem guidelines in existing format |
| NFR-R1 | Graceful Google Ads API error handling |
| NFR-R2 | OAuth token refresh detection |
| NFR-M2 | New MCP tools automatically available |

### Additional Requirements (from Architecture & UX)

| Source | Requirement |
|--------|-------------|
| Arch AD-3 | SSE for chat streaming |
| Arch AD-4 | SQLite for all structured data |
| Arch AD-6 | Monorepo with frontend/ + backend/ |
| UX | Three-panel layout (sidebar + content + chat) |
| UX | Dark mode default with light mode support |
| UX | Cmd+K command palette |
| UX | Keyboard shortcuts for power user navigation |

### FR Coverage Map

| FR | Epic |
|----|------|
| FR1.1-1.6 | Epic 1 (Setup & Configuration) |
| FR2.1-2.6 | Epic 3 (Campaign Browser) |
| FR2.7-2.8 | Epic 7 (Performance Dashboards) |
| FR3.1-3.7 | Epic 4 (AI Chat) |
| FR7.1-7.7 | Epic 4 (AI Chat) |
| FR3.8-3.10 | Epic 7 (Performance Dashboards) |
| FR4.1-4.7 | Epic 5 (Guidelines Management) |
| FR5.1-5.4, FR5.7 | Epic 6 (Campaign Operations) |
| FR5.5-5.6, FR5.8 | Epic 7 (Performance Dashboards) |
| FR6.1 | Epic 3 (Campaign Browser) |
| FR6.2-6.5 | Epic 7 (Performance Dashboards) |
| NFR-P, NFR-S, NFR-I | Epic 1 + Epic 2 (infrastructure) |
| UX Layout | Epic 2 (App Shell) |

---

## Epic List

### Epic 1: Project Setup & Backend Foundation
Bootstrap the project with both frontend and backend scaffolding, Google Ads API connectivity, and credential management. After this epic, the backend can connect to Google Ads and serve data.
**FRs covered:** FR1.1, FR1.2, FR1.5, FR1.6, NFR-S1, NFR-I2, NFR-I5

### Epic 2: App Shell & Navigation
Build the three-panel layout shell (sidebar, content area, chat panel) with routing and navigation. After this epic, the user sees the app structure and can navigate between views.
**FRs covered:** FR1.3, FR1.4, UX layout requirements, NFR-P1, NFR-P2

### Epic 3: Campaign Browser & Data Display
Populate the sidebar and content area with real campaign data from Google Ads. After this epic, the user can browse accounts, campaigns, ad groups, keywords, and ads with metrics.
**FRs covered:** FR2.1, FR2.2, FR2.3, FR2.4, FR2.5, FR2.6, FR6.1

### Epic 4: AI Agent Chat & Browser Automation
Integrate the Claude Code SDK with MCP servers (Google Ads + Chrome) and build the streaming chat interface. After this epic, the user can converse with an AI agent that has access to all 90+ Google Ads tools plus browser automation for GTM, landing pages, and external web UIs.
**FRs covered:** FR3.1, FR3.2, FR3.3, FR3.4, FR3.5, FR3.6, FR3.7, FR7.1, FR7.2, FR7.3, FR7.4, FR7.5, FR7.6, FR7.7

### Epic 5: Campaign Guidelines System
Build the guidelines viewer, editor, and auto-context injection system. After this epic, the user can view/edit campaign guidelines and the AI agent automatically uses them.
**FRs covered:** FR4.1, FR4.2, FR4.3, FR4.4, FR4.5, FR4.6, FR4.7

### Epic 6: Campaign Operations via AI
Enable campaign modifications through the AI agent with guideline enforcement. After this epic, the user can create campaigns, modify settings, and manage keywords/ads through chat.
**FRs covered:** FR5.1, FR5.2, FR5.3, FR5.4, FR5.7

### Epic 7: Growth Features (Phase 2)
Add performance dashboards, conversation history, search term analysis, and data export. This epic covers all Phase 2 / Growth features from the PRD.
**FRs covered:** FR2.7, FR2.8, FR3.8, FR3.9, FR3.10, FR5.5, FR5.6, FR5.8, FR6.2, FR6.3, FR6.4, FR6.5

---

## Epic 1: Project Setup & Backend Foundation

**Goal:** Bootstrap the monorepo with frontend and backend scaffolding, establish Google Ads API connectivity, and implement credential management with a setup wizard.

---

### Story 1.1: Initialize Monorepo with Frontend and Backend Scaffolding

As a developer,
I want the project scaffolded with a React frontend and FastAPI backend in a monorepo structure,
So that I have a working development environment to build upon.

**Acceptance Criteria:**

**Given** an empty project directory at `C:\Users\Wassim\Documents\google-ads-webapp\`
**When** the scaffolding is complete
**Then** the following structure exists:
- `frontend/` with Vite + React + TypeScript configured
- `backend/` with FastAPI + Python project configured via `pyproject.toml` (uv)
- `frontend/` runs on `localhost:5173` with hot reload
- `backend/` runs on `localhost:8000` with auto-reload
- Vite proxy config forwards `/api/*` requests to the backend
- A dev script (`scripts/dev.sh`) starts both servers
**And** `frontend/` has Tailwind CSS and shadcn/ui initialized
**And** `backend/` has FastAPI with a health check endpoint `GET /api/health` returning `{"status": "ok"}`
**And** both servers start without errors

**Technical notes:**
- Frontend: `npm create vite@latest -- --template react-ts`
- Backend: `uv init` with FastAPI, uvicorn, aiosqlite, sqlmodel, python-dotenv
- shadcn/ui: `npx shadcn@latest init` with New York style, dark theme

---

### Story 1.2: Set Up SQLite Database with Schema

As a developer,
I want a SQLite database initialized with the required schema,
So that the application has persistent local storage for accounts, conversations, cache, and config.

**Acceptance Criteria:**

**Given** the backend is running
**When** the application starts for the first time
**Then** a SQLite database is created at `data/app.db`
**And** the following tables exist: `accounts`, `config`, `conversations`, `messages`, `cache`, `guidelines_meta`
**And** the database uses WAL mode for better concurrent read performance
**And** SQLModel models for all tables are defined in `backend/app/models/database.py`
**And** a database initialization function runs on app startup to create tables if they don't exist

**Technical notes:**
- Use SQLModel for ORM definitions (see Architecture doc Section 5)
- Use aiosqlite for async SQLite access
- Schema matches the SQL definitions in the Architecture doc

---

### Story 1.3: Implement Google Ads API Connection Service

As a developer,
I want a backend service that connects to the Google Ads API using the existing MCP server's SDK client,
So that the app can fetch campaign data directly without going through the AI agent.

**Acceptance Criteria:**

**Given** the MCP server path is configured (e.g., `../google ads/google-ads-mcp`)
**When** the `GoogleAdsService` is initialized
**Then** it imports `GoogleAdsSdkClient` from the MCP server's `src/sdk_client.py`
**And** it can execute GAQL queries against the Google Ads API
**And** it handles authentication errors by raising a `TokenExpiredError`
**And** it handles API quota errors with appropriate error messages
**And** it includes a `discover_accounts()` method that lists all accessible customer accounts

**Technical notes:**
- Add MCP server's `src/` to Python path via `sys.path.insert`
- GoogleAdsSdkClient loads credentials from `.env` (shared with MCP server)
- Use v23 request types for direct queries (not v20)

---

### Story 1.4: Build Credential Setup API and Wizard UI

As a user,
I want a setup wizard to enter my Google Ads API credentials and verify they work,
So that I can configure the app on first launch.

**Acceptance Criteria:**

**Given** the app is opened for the first time (no credentials configured)
**When** the setup wizard is displayed
**Then** I can enter: developer token, OAuth client ID, client secret, refresh token, login customer ID
**And** clicking "Validate" calls `POST /api/setup/credentials` which tests the credentials
**And** on success, credentials are stored (encrypted or in config) and the wizard shows discovered accounts
**And** on failure, a clear error message is shown (e.g., "Invalid refresh token", "Developer token not approved")
**And** `GET /api/setup/status` returns `{configured: true}` after successful setup
**And** the wizard includes an optional step to configure browser automation:
  - "Enable Chrome MCP for browser tasks (GTM, landing pages)?"
  - If yes, configure Chrome MCP command/path
  - Note: "Requires Chrome running with the claude-in-chrome extension"
**And** the app redirects to the main workspace after setup completes

**Technical notes:**
- Frontend: `SetupWizard` component with 3-4 steps (credentials, validate, select accounts, optional browser setup)
- Backend: `POST /api/setup/credentials` stores config, `GET /api/setup/status` checks config exists
- Credentials stored in `config` table (consider encrypting sensitive values)
- Chrome MCP config stored in `config` table: `chrome_mcp_enabled`, `chrome_mcp_command`, `chrome_mcp_args`
- Alternatively, the wizard can point to an existing `.env` file path

---

### Story 1.5: Implement Data Caching Layer

As a developer,
I want a caching layer that stores Google Ads API responses in SQLite,
So that the frontend loads data quickly without hitting the API on every request.

**Acceptance Criteria:**

**Given** the cache service is configured with a TTL (default 5 minutes)
**When** a data request is made (e.g., campaign list)
**Then** if cached data exists and is within TTL, the cached data is returned immediately
**And** if cached data is expired or missing, a fresh API call is made and the result is cached
**And** cache entries are stored in the `cache` table with key, JSON data, and timestamp
**And** cache can be manually invalidated (e.g., after AI agent performs a mutation)
**And** the TTL is configurable via the `config` table

**Technical notes:**
- `CacheService` class with `get_or_fetch(key, fetch_fn)` method
- Cache keys follow pattern: `{resource}:{customer_id}:{optional_id}`

---

## Epic 2: App Shell & Navigation

**Goal:** Build the three-panel layout with sidebar navigation, account/campaign selection, and routing so the user has a navigable workspace.

---

### Story 2.1: Build Three-Panel Layout Shell

As a user,
I want to see a three-panel workspace when I open the app,
So that I can navigate campaigns on the left, see details in the center, and chat on the right.

**Acceptance Criteria:**

**Given** the app is loaded and credentials are configured
**When** the main workspace renders
**Then** I see three panels: sidebar (280px), content area (flexible), chat panel (400px)
**And** a header bar (48px) with the app name, account selector, and settings icon
**And** the sidebar is collapsible to a 48px icon rail via a collapse button
**And** the chat panel is resizable via a drag handle (min 320px, max 600px)
**And** the layout uses the dark theme by default (as per UX design)
**And** the layout is responsive: at <1100px, sidebar collapses to rail automatically

**Technical notes:**
- Use CSS Grid or Flexbox for the three-panel layout
- ResizablePanel component with drag handle for chat panel width
- Store sidebar collapsed state and chat panel width in Zustand store
- Tailwind dark mode via `class` strategy

---

### Story 2.2: Implement Account Selector and Campaign Sidebar

As a user,
I want to see my Google Ads accounts and campaigns in the sidebar,
So that I can select which campaign to work with.

**Acceptance Criteria:**

**Given** accounts have been discovered during setup
**When** the sidebar loads
**Then** I see the account hierarchy: Manager → Sub-Manager → Client accounts
**And** under each client account, I see its campaigns with status dots (green=enabled, yellow=paused)
**And** each campaign shows a budget chip (e.g., "$200/d")
**And** clicking a campaign highlights it in the sidebar and updates the content area
**And** the header dropdown shows the current account name and allows switching
**And** the sidebar has a search/filter input at the top to find campaigns by name

**Technical notes:**
- `GET /api/accounts` to fetch account tree
- `GET /api/accounts/{id}/campaigns` to fetch campaigns per account
- Use TanStack Query for data fetching with stale-while-revalidate
- Zustand store holds `selectedAccountId` and `selectedCampaignId`
- Sidebar component tree: AccountTree → AccountNode → CampaignNode

---

### Story 2.3: Set Up Routing and Navigation State

As a user,
I want the URL to reflect the selected campaign so I can bookmark or refresh without losing context,
So that navigation state persists.

**Acceptance Criteria:**

**Given** the app uses React Router
**When** I select a campaign
**Then** the URL updates to `/campaigns/{campaignId}`
**And** refreshing the page at this URL restores the selected campaign
**And** the sidebar highlights the correct campaign from the URL
**And** navigating to `/` shows the account overview (all campaigns summary)
**And** navigating to `/setup` shows the setup wizard
**And** browser back/forward buttons work for campaign navigation

**Technical notes:**
- Routes: `/` (overview), `/campaigns/:id` (campaign detail), `/setup` (wizard)
- React Router v7 with path parameters
- Zustand store syncs with URL params on mount

---

### Story 2.4: Implement Command Palette (Cmd+K)

As a power user,
I want a command palette triggered by Cmd+K,
So that I can quickly search and navigate to any campaign or action.

**Acceptance Criteria:**

**Given** I am anywhere in the app
**When** I press Cmd+K (or Ctrl+K on Windows)
**Then** a search overlay appears in the center of the screen
**And** I can type to search campaigns by name
**And** search results show campaign name, status, and account name
**And** pressing Enter navigates to the selected campaign
**And** pressing Escape closes the palette
**And** results update as I type (debounced 200ms)

**Technical notes:**
- Use shadcn/ui `Command` component (built on cmdk)
- Index campaigns from TanStack Query cache for instant search
- Keyboard navigation: arrow keys to select, Enter to navigate, Escape to close

---

## Epic 3: Campaign Browser & Data Display

**Goal:** Populate the content area with real campaign data from the Google Ads API, showing metrics, ad group structure, keywords, and ads.

---

### Story 3.1: Build Campaign List API Endpoint

As a developer,
I want a backend endpoint that returns campaign data with metrics for a given account,
So that the frontend can display the campaign list.

**Acceptance Criteria:**

**Given** a valid account ID
**When** `GET /api/accounts/{id}/campaigns?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD` is called
**Then** it returns a JSON array of campaigns with: id, name, status, channelType, budget, biddingStrategy, and metrics (impressions, clicks, ctr, cost, conversions, cpa)
**And** the response uses the cache layer (returns cached data if within TTL)
**And** date range defaults to last 7 days if not specified
**And** removed campaigns are excluded by default (filterable via `?include_removed=true`)

**Technical notes:**
- GAQL query selecting campaign + metrics fields for the date range
- Convert `amount_micros` to dollars in the response (divide by 1,000,000)
- Cache key: `campaigns:{customer_id}:{date_from}:{date_to}`

---

### Story 3.2: Build Campaign Overview UI

As a user,
I want to see a campaign overview with metric cards and settings when I select a campaign,
So that I can quickly understand the campaign's current state.

**Acceptance Criteria:**

**Given** I have selected a campaign in the sidebar
**When** the campaign detail view loads
**Then** I see metric cards at the top showing: Impressions, Clicks, CTR, Cost, Conversions, CPA
**And** each metric card shows the value and a trend indicator (% change vs previous period)
**And** below the metrics, I see campaign settings: status, budget, bidding strategy, location targets, language targets, conversion goals
**And** a date range selector allows choosing: Today, 7d, 14d, 30d, Custom
**And** changing the date range updates all metrics

**Technical notes:**
- `MetricCard` component with value, label, trend props
- `MetricCardRow` renders 6 cards horizontally
- `CampaignSettings` displays the campaign configuration
- Date range stored in component state, triggers refetch via TanStack Query

---

### Story 3.3: Build Ad Group Tree and Keyword/Ad Tables

As a user,
I want to drill into a campaign to see its ad groups, keywords, and ads,
So that I can understand the campaign structure in detail.

**Acceptance Criteria:**

**Given** I am viewing a campaign
**When** I look at the Overview tab
**Then** I see an expandable ad group tree showing: ad group name, status, keyword count, ad count, and inline metrics
**And** clicking an ad group expands it to show its keywords and ads
**When** I click the "Keywords" tab
**Then** I see a full sortable table of all keywords across all ad groups with: keyword text, match type, ad group, status, quality score, impressions, clicks, conversions, CPA
**And** I can sort by any column and filter by status/match type
**When** I click the "Ads" tab
**Then** I see a list of all ads with: headlines, descriptions, status, metrics

**Technical notes:**
- Backend endpoints: `GET /api/campaigns/{id}/adgroups`, `GET /api/campaigns/{id}/keywords`, `GET /api/campaigns/{id}/ads`
- Use TanStack Table for the keyword table with virtual scrolling for large datasets
- AdGroupTree component with collapsible nodes
- Tab bar using shadcn/ui Tabs component

---

### Story 3.4: Implement Date Range Selector

As a user,
I want to select different date ranges for campaign metrics,
So that I can analyze performance over different periods.

**Acceptance Criteria:**

**Given** I am viewing a campaign
**When** I click the date range selector
**Then** I see preset options: Today, Yesterday, Last 7 days, Last 14 days, Last 30 days, This month
**And** I can select a custom date range with start and end date pickers
**And** selecting a date range updates all metrics, cards, and tables on the page
**And** the selected date range persists when switching between tabs (Overview, Keywords, Ads)
**And** the date range is stored in the URL query params for bookmarkability

**Technical notes:**
- shadcn/ui Popover with preset buttons + date picker
- Date range state in Zustand store or URL search params
- TanStack Query uses date range as cache key part

---

## Epic 4: AI Agent Chat & Browser Automation

**Goal:** Integrate the Claude Code SDK with multiple MCP servers (Google Ads + Chrome) and build a streaming chat interface that provides campaign-aware AI assistance with browser automation for beyond-API tasks.

---

### Story 4.1: Implement Claude Code SDK Agent Service with Multi-MCP Support

As a developer,
I want a backend service that spawns Claude Code SDK agent sessions connected to both the Google Ads MCP server and optionally the Chrome MCP server,
So that the chat feature has an AI agent with access to all 90+ API tools plus browser automation.

**Acceptance Criteria:**

**Given** the MCP server path is configured
**When** the agent service is initialized
**Then** it can spawn a Claude Code SDK agent process configured with the Google Ads MCP server
**And** if Chrome MCP is enabled in settings, the agent is also configured with the Chrome MCP server
**And** the agent can receive user messages and stream responses
**And** the agent has access to all tools provided by both MCP servers
**And** the agent's system prompt can be dynamically set (for guidelines injection)
**And** agent processes are properly terminated when sessions end
**And** agent connection failures are handled with clear error messages
**And** if Chrome MCP fails to connect (Chrome not running), the agent continues with Google Ads MCP only and logs a warning

**Technical notes:**
- Use `claude_code_sdk` Python package
- Google Ads MCP config: `{"command": "uv", "args": ["run", "python", "main.py"], "cwd": MCP_PATH}`
- Chrome MCP config: `{"command": "npx", "args": ["-y", "@anthropic/claude-chrome-mcp"]}` (configurable)
- Chrome MCP is optional - controlled by `chrome_mcp_enabled` in config table
- Stream events include: text tokens, tool calls (with source tag), tool results
- Consider agent session pooling for performance (optional)

---

### Story 4.2: Build Chat SSE Endpoint

As a developer,
I want a backend endpoint that accepts user messages and streams AI responses via SSE,
So that the frontend can display streaming chat.

**Acceptance Criteria:**

**Given** a conversation ID and user message
**When** `POST /api/conversations/{id}/message` is called with `{content: "..."}`
**Then** it returns an SSE stream with events:
- `{"type": "text", "content": "token..."}` for text tokens
- `{"type": "tool_call", "id": "...", "source": "google-ads|chrome", "name": "...", "input": {...}}` for tool invocations
- `{"type": "tool_result", "id": "...", "source": "google-ads|chrome", "output": {...}, "status": "success|error"}` for tool results
- `{"type": "done", "message_id": "..."}` when complete
- `{"type": "error", "message": "..."}` on failure
**And** each tool call event includes a `source` field identifying which MCP server it came from ("google-ads" or "chrome")
**And** the user message is saved to the `messages` table before streaming starts
**And** the complete assistant response is saved to the `messages` table after streaming ends

**Technical notes:**
- FastAPI `StreamingResponse` with `media_type="text/event-stream"`
- Async generator that yields SSE-formatted events
- System prompt built from guidelines before calling agent

---

### Story 4.3: Build Chat Panel UI with Streaming

As a user,
I want a chat panel on the right side of the workspace where I can converse with the AI agent,
So that I can ask questions and request operations on my campaigns.

**Acceptance Criteria:**

**Given** the chat panel is visible
**When** I type a message and press Enter (or click Send)
**Then** my message appears in the chat history
**And** the AI response streams in token-by-token below my message
**And** tool call blocks appear inline during the response (showing tool name)
**And** the chat auto-scrolls as new content arrives
**And** I can scroll up to view history while streaming continues
**And** the input is disabled while the agent is responding
**And** the chat panel shows a loading indicator while waiting for first token

**Technical notes:**
- `ChatPanel` component with message list, input area
- `ChatMessage` component renders markdown content
- Connect to SSE endpoint via `fetch` + `ReadableStream` (not EventSource, since it's a POST)
- Auto-scroll logic: scroll to bottom unless user has scrolled up

---

### Story 4.4: Implement Tool Call Transparency UI

As a user,
I want to see which MCP tools the AI agent used and what data it received,
So that I understand what actions the agent took and can verify the results.

**Acceptance Criteria:**

**Given** the AI agent invokes MCP tools during a response
**When** a tool call event is received
**Then** a collapsible block appears in the chat showing the tool name and a brief summary
**And** clicking the block expands it to show: tool name, source (API or browser), input parameters (JSON), output result (JSON), execution status (success/error)
**And** Google Ads API tool calls use a purple accent color with a wrench icon (🔧)
**And** Chrome browser tool calls use a teal accent color with a globe icon (🌐) and show the URL being accessed as a subtitle
**And** multiple tool calls in a single response each get their own block
**And** failed tool calls show an error icon and the error message

**Technical notes:**
- `ToolCallBlock` component with collapsible Radix Collapsible
- `source` field from SSE event determines icon and color styling
- JSON displayed with syntax highlighting (simple <pre> with colored tokens)
- Tool call state tracked in chat store: pending → success/error
- Browser tool calls extract URL from input for display as subtitle

---

### Story 4.5: Implement Context Badge and Auto-Context Injection

As a user,
I want to see which campaign guidelines are loaded into the AI agent's context,
So that I know the agent is aware of the campaign's rules.

**Acceptance Criteria:**

**Given** I have selected a campaign in the sidebar
**When** the chat panel updates
**Then** a context badge at the top of the chat panel shows: campaign name, "Guidelines loaded", last modified date
**And** clicking the badge expands to show which guideline sections were injected (e.g., "Global Rules", "Portugal Golden Visa section")
**When** I send a message
**Then** the backend builds a system prompt that includes:
  1. Base agent instructions
  2. Global campaign rules from the main guidelines file
  3. Campaign-specific section from the guidelines file
  4. Region-specific guidelines if applicable (MENA, Greece)
**And** the AI agent responds with awareness of these guidelines

**Technical notes:**
- `ContextBadge` component in chat panel header
- Backend `build_system_prompt()` function (see Architecture doc Section 5)
- Guidelines parsing: extract section by campaign name/ID from markdown

---

### Story 4.6: Implement Confirmation Mode for Mutations

As a user,
I want the option to approve or reject AI tool calls that modify campaign data,
So that I can prevent accidental changes.

**Acceptance Criteria:**

**Given** confirmation mode is enabled (toggle in chat panel footer)
**When** the AI agent attempts to invoke a mutating MCP tool (create, update, delete operations)
**Then** the tool call block shows "Awaiting confirmation" with Approve/Reject buttons
**And** clicking Approve executes the tool call and continues the response
**And** clicking Reject skips the tool call and the agent is informed it was rejected
**When** confirmation mode is disabled
**Then** all tool calls execute automatically (current behavior)

**Technical notes:**
- Classify MCP tools as read-only vs mutating based on tool name patterns
- Google Ads: Read-only (get_*, list_*, search_*) auto-execute; mutating (create_*, update_*, remove_*, mutate_*) wait for confirmation
- Chrome MCP: Read-only (read_page, get_page_text, tabs_context_mcp, find) auto-execute; mutating (form_input, javascript_tool with side effects, navigate to edit pages) wait for confirmation
- SSE event type: `{"type": "confirmation_required", "tool_call": {...}, "source": "google-ads|chrome"}`
- Frontend sends `POST /api/conversations/{id}/confirm/{tool_call_id}` with `{approved: true/false}`

---

## Epic 5: Campaign Guidelines System

**Goal:** Build the guidelines viewer, editor, and auto-context injection so users can manage per-campaign rules that the AI agent uses.

---

### Story 5.1: Build Guidelines API Endpoints

As a developer,
I want backend endpoints for listing, reading, and writing guidelines files,
So that the frontend can display and edit campaign guidelines.

**Acceptance Criteria:**

**Given** a guidelines directory is configured
**When** `GET /api/guidelines` is called
**Then** it returns a list of all `.md` files with: filename, last modified timestamp, file size
**When** `GET /api/guidelines/{filename}` is called
**Then** it returns the file content as a string with the last modified timestamp
**When** `PUT /api/guidelines/{filename}` is called with `{content: "..."}`
**Then** the file is written atomically (temp file + rename) and the new last modified time is returned
**When** `POST /api/guidelines` is called with `{filename: "...", campaign_name: "..."}`
**Then** a new guidelines file is created from a template with the campaign name pre-filled

**Technical notes:**
- `GuidelinesService` class in `backend/app/services/guidelines.py`
- Atomic write: write to `.tmp` file then `os.replace()` to target
- Template based on the existing `CAMPAIGN_GUIDELINES.md` structure

---

### Story 5.2: Build Guidelines Viewer (Formatted Markdown)

As a user,
I want to view campaign guidelines in a nicely formatted markdown view,
So that I can read tables, headings, and rules clearly.

**Acceptance Criteria:**

**Given** I have selected a campaign and clicked the "Guidelines" tab
**When** the guidelines viewer loads
**Then** I see the campaign's guidelines file rendered as formatted markdown
**And** tables are rendered as HTML tables with proper alignment
**And** headings, bold, italic, lists, and code blocks render correctly
**And** the viewer shows a toolbar with: [View] [Edit] toggle, and "Last saved: {timestamp}"
**And** if no guidelines file exists for this campaign, a "Create Guidelines" button is shown

**Technical notes:**
- Use @uiw/react-md-editor in preview mode or react-markdown with remark-gfm for tables
- Map campaign ID/name to guidelines filename (e.g., search for campaign name in all files)

---

### Story 5.3: Build Guidelines Editor (Markdown Edit Mode)

As a user,
I want to edit campaign guidelines in a markdown editor,
So that I can update rules, add change log entries, and modify campaign-specific sections.

**Acceptance Criteria:**

**Given** I am on the Guidelines tab in View mode
**When** I click the "Edit" toggle
**Then** the view switches to a split-pane markdown editor (edit on left, preview on right)
**And** I can type markdown with syntax highlighting
**And** changes are auto-saved with a 2-second debounce
**And** the save indicator shows "Saving..." during debounce and "Saved ✓" after save completes
**And** if the file was modified externally since I loaded it, a warning is shown before overwriting
**And** pressing Escape or clicking "View" switches back to the formatted view

**Technical notes:**
- @uiw/react-md-editor with controlled value
- Debounced save: `useDebouncedCallback` from use-debounce or manual implementation
- Check `lastModified` on save to detect external modifications

---

### Story 5.4: Create Guidelines Template for New Campaigns

As a user,
I want to create a guidelines file for a new campaign from a template,
So that I don't have to write the structure from scratch.

**Acceptance Criteria:**

**Given** a campaign has no associated guidelines file
**When** I click "Create Guidelines" on the Guidelines tab
**Then** a new file is created with the template structure:
  - Overview table (Campaign ID, Account, Status, Budget, Bidding, Landing Page)
  - Conversion Tracking section
  - Ad Groups section
  - Keywords section
  - Negative Keywords section
  - Performance History section
  - Known Issues section
  - Change Log section
**And** the campaign name and ID are pre-filled from the selected campaign data
**And** the editor opens in Edit mode so I can fill in the details
**And** the file is saved to the guidelines directory

**Technical notes:**
- Template matches existing `CAMPAIGN_GUIDELINES.md` per-campaign section format
- Pre-fill campaign data from the `GET /api/campaigns/{id}` endpoint

---

## Epic 6: Campaign Operations via AI

**Goal:** Enable campaign modifications through the AI agent with guideline enforcement, so users can create campaigns, change settings, and manage keywords/ads conversationally.

---

### Story 6.1: Enable Campaign Modifications Through Chat

As a user,
I want to ask the AI agent to modify campaign settings (budget, bidding, status),
So that I can manage campaigns conversationally with guideline awareness.

**Acceptance Criteria:**

**Given** the AI agent has campaign guidelines loaded
**When** I ask "Change the budget to $250/day"
**Then** the agent identifies the correct MCP tool (e.g., `mutate_campaign`)
**And** the agent checks guidelines before executing (e.g., "only one change type per day")
**And** if guidelines allow, the tool executes and the agent confirms the change
**And** if guidelines prohibit, the agent explains why (e.g., "Stabilization period active until March 26")
**And** the campaign data in the content area refreshes after a successful mutation
**And** the cache is invalidated for the affected campaign

**Technical notes:**
- Cache invalidation: after any successful mutating tool call, invalidate cache for that customer_id
- Frontend: listen for tool_result events with mutating tools → trigger TanStack Query invalidation
- The agent naturally checks guidelines because they're in the system prompt

---

### Story 6.2: Enable Keyword and Ad Management Through Chat

As a user,
I want to ask the AI agent to add, pause, or remove keywords and ads,
So that I can manage campaign content conversationally.

**Acceptance Criteria:**

**Given** a campaign is selected and guidelines are loaded
**When** I ask "Add the keyword [portugal golden visa 2025] as exact match to the Portugal Golden Visa ad group"
**Then** the agent invokes the appropriate MCP tool to add the keyword
**And** the agent confirms the action with the keyword details
**When** I ask "Pause the keyword 'portugal residency for us citizens'"
**Then** the agent pauses the correct keyword and confirms
**When** I ask "Create a new responsive search ad for the Portugal Golden Visa ad group"
**Then** the agent asks for headlines and descriptions (or generates suggestions)
**And** creates the ad via MCP tools

**Technical notes:**
- Relies on existing MCP tools: `mutate_ad_group_criterion`, `mutate_ad_group_ad`, etc.
- The agent handles the tool selection; the web app just needs to forward messages and display results
- Keyword/ad tables in the content area should refresh after mutations

---

### Story 6.3: Implement Change Management Warning

As a user,
I want the app to warn me when I'm making multiple types of changes in the same day,
So that I follow the guidelines' change management rule.

**Acceptance Criteria:**

**Given** the campaign guidelines state "NEVER make more than ONE type of change per day"
**When** the AI agent has already executed a mutation of type A (e.g., budget change) today
**And** I request a mutation of type B (e.g., keyword change) on the same campaign
**Then** the agent warns: "A budget change was already made today. The guidelines recommend only one type of change per day. Do you want to proceed anyway?"
**And** I can choose to proceed or cancel

**Technical notes:**
- Track mutations per campaign per day in the `messages` table (filter by date + tool_call role)
- Classify mutation types: budget, bidding, keywords, ads, conversion, targeting
- The agent can check this via guidelines context + its own memory of the conversation
- Alternatively, the backend can inject "changes made today" into the system prompt

---

## Epic 7: Growth Features (Phase 2)

**Goal:** Add performance dashboards, conversation history persistence, search term analysis, and data export for power-user workflows.

---

### Story 7.1: Build Performance Dashboard with Charts

As a user,
I want to see campaign performance charts showing metrics over time,
So that I can identify trends and make data-driven decisions.

**Acceptance Criteria:**

**Given** I am viewing a campaign
**When** I look at the Performance section (new tab or below overview)
**Then** I see line charts for: Daily impressions, Daily clicks, Daily cost, Daily conversions, Daily CPA
**And** each chart shows the selected date range with data points per day
**And** I can hover over data points to see exact values
**And** I can toggle which metrics are visible
**And** I can compare two date ranges side by side (e.g., this week vs last week)

**Technical notes:**
- Backend: `GET /api/campaigns/{id}/metrics?date_from=...&date_to=...` returns time-series data
- Frontend: Recharts LineChart with multiple series
- Date range comparison: two API calls, overlay on same chart with different colors

---

### Story 7.2: Implement Conversation History Persistence

As a user,
I want my chat conversations saved and browsable,
So that I can reference past interactions and decisions.

**Acceptance Criteria:**

**Given** I have had multiple conversations
**When** I click a "History" section in the chat panel
**Then** I see a list of past conversations with: title, campaign name, date, message count
**And** clicking a conversation loads its full message history
**And** I can create new conversation threads (clears chat, keeps context)
**And** I can search conversations by keyword
**And** conversations are tagged with the campaign they were about

**Technical notes:**
- `GET /api/conversations?account_id=...&campaign_id=...` with pagination
- `GET /api/conversations/{id}/messages` to load history
- Auto-generate conversation titles from the first user message (truncated)
- Search via SQL LIKE on message content

---

### Story 7.3: Build Search Term Analysis View

As a user,
I want to view search term reports and add negative keywords with documented reasons,
So that I can refine targeting following the guidelines' negative keyword policy.

**Acceptance Criteria:**

**Given** I am viewing a campaign
**When** I access the "Search Terms" tab (or section)
**Then** I see a table of search terms with: search term, match type, campaign, ad group, impressions, clicks, conversions, cost
**And** I can sort and filter the table
**And** each search term has an "Add as Negative" button
**And** clicking the button opens a form to: select match type ([EXACT], [PHRASE], [BROAD]), enter a reason for adding the negative
**And** the negative keyword is added via the AI agent or direct API call
**And** the reason is logged in the guidelines file's negative keywords section

**Technical notes:**
- Backend: GAQL query for `search_term_view` resource
- Negative keyword addition follows guidelines policy (prefer EXACT match)
- Log to guidelines file via `PUT /api/guidelines/{filename}` with appended content

---

### Story 7.4: Implement Data Export to CSV

As a user,
I want to export campaign data to CSV,
So that I can analyze it in spreadsheets or share with others.

**Acceptance Criteria:**

**Given** I am viewing campaign data (metrics, keywords, ads, search terms)
**When** I click an "Export CSV" button
**Then** a CSV file is downloaded with the currently visible data
**And** the file includes all columns visible in the table
**And** the filename includes the campaign name and date range
**And** numeric values are properly formatted (not micros)

**Technical notes:**
- Frontend-side CSV generation from TanStack Table data
- Use a simple CSV library (e.g., papaparse) or manual string building
- Download via Blob URL

---

### Story 7.5: Add Conversion Tracking Status and Impression Share Metrics

As a user,
I want to see conversion tracking status and impression share data for each campaign,
So that I can verify tracking is working and understand my ad visibility.

**Acceptance Criteria:**

**Given** I am viewing a campaign
**When** I look at the campaign details
**Then** I see a "Conversion Tracking" section showing:
  - Each conversion action assigned to this campaign
  - Action name, type, status, and recent conversion count
  - Whether it's PRIMARY or SECONDARY
**And** I see impression share metrics:
  - Search impression share (%)
  - Lost impression share (rank) (%)
  - Lost impression share (budget) (%)
**And** these are displayed as metric cards or in the settings section

**Technical notes:**
- GAQL queries for `campaign_conversion_goal` and campaign metrics including impression share fields
- Display matches the conversion actions registry format from CAMPAIGN_GUIDELINES.md

---

## Validation

### Requirements Coverage Check

| Epic | FRs Covered | Status |
|------|-------------|--------|
| Epic 1 | FR1.1, FR1.2, FR1.5, FR1.6, NFR-S1, NFR-I2, NFR-I5 | Complete |
| Epic 2 | FR1.3, FR1.4, UX layout, NFR-P1, NFR-P2 | Complete |
| Epic 3 | FR2.1-2.6, FR6.1 | Complete |
| Epic 4 | FR3.1-3.7, FR7.1-7.7 | Complete |
| Epic 5 | FR4.1-4.7 | Complete |
| Epic 6 | FR5.1-5.4, FR5.7 | Complete |
| Epic 7 | FR2.7-2.8, FR3.8-3.10, FR5.5-5.6, FR5.8, FR6.2-6.5 | Complete |

**All 51 functional requirements are covered (including FR7 browser automation group).**
**All critical non-functional requirements are addressed in Epics 1-2.**

### Story Independence Check

Each story can be completed by a single developer without depending on future stories within the same epic. Dependencies flow forward: Epic 1 → Epic 2 → Epic 3/4/5 → Epic 6 → Epic 7.

### Acceptance Criteria Completeness

All stories include Given/When/Then acceptance criteria with technical implementation notes referencing the Architecture document.

### Epic Execution Order

```
Epic 1: Project Setup & Backend Foundation
  └─ Epic 2: App Shell & Navigation
       ├─ Epic 3: Campaign Browser & Data Display
       ├─ Epic 4: AI Agent Chat
       └─ Epic 5: Campaign Guidelines System
            └─ Epic 6: Campaign Operations via AI
                 └─ Epic 7: Growth Features
```

Epics 3, 4, and 5 can be developed in parallel after Epic 2 is complete.
