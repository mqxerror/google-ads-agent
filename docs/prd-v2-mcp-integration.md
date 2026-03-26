# PRD v2: Bundle MCP Services + Full Power Google Ads Manager

**Author:** Wassim
**Date:** 2026-03-26
**BMAD Track:** BMad Method
**Status:** Draft

---

## 1. Executive Summary

### Problem

The webapp currently makes basic GAQL queries through the `google-ads` Python SDK — covering only ~5% of what the Google Ads API can do (list campaigns, metrics, keywords, ads). Meanwhile, a full **87-service MCP server** already exists in a separate folder with capabilities for campaign creation, keyword planning, audience management, conversion tracking, bidding strategies, experiments, batch operations, and more.

These two codebases are disconnected:
- The webapp can **read** data but can't **act** on it
- The MCP server can do everything but has no UI
- Moving or deleting the MCP folder breaks the planned AI chat integration
- A team member cloning the repo wouldn't have the MCP services

### Solution

**Bundle the MCP server's 87 services directly into the webapp** as a Python package, creating a single self-contained application that:

1. **Exposes all 87 services as REST endpoints** for the web UI (direct operations)
2. **Runs the MCP server for the Claude Code SDK agent** (AI chat operations)
3. **Updates all imports to the latest Google Ads API version** (v23 → latest stable)
4. **Is faster than the Google Ads UI** — local execution, no round-trips to Google's frontend servers, cached data, batch operations
5. **Architected for multi-API support** — Google Analytics, GTM API, Meta Ads can be added as additional service packages

### Why Faster Than Google Ads UI

| Operation | Google Ads UI | This App |
|-----------|--------------|----------|
| Load campaign list | 3-5 seconds (full page render + React hydration + API) | <1 second (API-only, cached, no UI framework overhead) |
| Switch campaigns | 2-3 seconds (page navigation) | Instant (SPA, data cached) |
| Change budget | 4+ clicks (campaign → settings → edit → save → confirm) | 1 chat message or 1 click |
| Add 10 keywords | 10 × (click add → type → save) = 2-3 minutes | 1 chat message: "add these 10 keywords" |
| Create campaign | 15+ step wizard, 5-10 minutes | Chat: describe what you want, AI creates it |
| Review search terms | Navigate → filter → scroll → select → add negatives | One table view + bulk actions |
| Change bidding strategy | 3 screens, confirm dialogs | 1 click or 1 chat message |
| Keyword planning | Separate tool, export/import CSV | Built-in, results feed directly into campaigns |

---

## 2. Project Classification

| Attribute | Value |
|-----------|-------|
| Project Type | `web_app` (SPA with integrated service layer) |
| Domain | Google Ads Management / Digital Marketing |
| Complexity | High (87 services, API version migration, dual-mode architecture) |
| Classification | Brownfield (merging two existing codebases) |
| BMAD Track | BMad Method |

---

## 3. Architecture: How It All Fits Together

### Current State (v1)

```
Frontend (React) → Backend (FastAPI) → google-ads SDK (5 basic queries)

Separate: google-ads-mcp/ (87 services, not connected)
```

### Target State (v2)

```
┌────────────────────────────────────────────────────────────────┐
│                    google-ads-webapp/                            │
│                                                                  │
│  frontend/ (React SPA)                                          │
│    ├── Campaign Browser (reads via REST)                        │
│    ├── Direct Actions UI (budget, status, keywords via REST)    │
│    └── AI Chat Panel (streams via SSE)                          │
│                                                                  │
│  backend/                                                        │
│    ├── app/ (FastAPI web layer)                                  │
│    │   ├── routers/          ← REST endpoints for UI            │
│    │   │   ├── campaigns.py  ← Uses google_ads_services         │
│    │   │   ├── keywords.py   ← Uses google_ads_services         │
│    │   │   ├── ads.py        ← Uses google_ads_services         │
│    │   │   ├── planning.py   ← Uses google_ads_services         │
│    │   │   └── chat.py       ← Spawns Claude Code agent         │
│    │   └── services/                                             │
│    │       └── agent.py      ← Claude Code SDK + MCP server     │
│    │                                                             │
│    ├── google_ads/           ← BUNDLED MCP SERVICES (87)        │
│    │   ├── sdk_client.py     ← Auth (shared by web + MCP)       │
│    │   ├── utils.py          ← Helpers                           │
│    │   ├── services/         ← 87 service implementations       │
│    │   │   ├── campaign/     ← Campaign CRUD, drafts, experiments│
│    │   │   ├── ad_group/     ← Ad groups, ads, keywords         │
│    │   │   ├── planning/     ← Keyword planning, reach planning │
│    │   │   ├── conversions/  ← Conversion tracking, uploads      │
│    │   │   ├── audiences/    ← User lists, custom audiences      │
│    │   │   ├── bidding/      ← Strategies, seasonality           │
│    │   │   └── ... (14 categories)                               │
│    │   ├── servers/          ← FastMCP tool wrappers             │
│    │   └── mcp_main.py       ← MCP server entry point           │
│    │                                                             │
│    └── .env                  ← Credentials                       │
│                                                                  │
│  data/                                                           │
│    ├── app.db                ← SQLite                            │
│    └── guidelines/           ← Campaign guidelines .md           │
└────────────────────────────────────────────────────────────────┘
```

### Dual-Mode Access

Every Google Ads operation is accessible two ways:

1. **REST API (for the web UI):**
   ```
   POST /api/campaigns/create → calls CampaignService.create_campaign()
   POST /api/keywords/add → calls KeywordService.add_keywords()
   PUT /api/campaigns/{id}/budget → calls BudgetService.update_budget()
   ```
   The FastAPI routers import service classes directly from `google_ads/services/`.

2. **MCP Server (for the AI chat agent):**
   ```
   User: "Create a new search campaign targeting US with $100/day budget"
   → Claude Code SDK → MCP Server → CampaignService + BudgetService + CriterionService
   ```
   The Claude Code SDK spawns `google_ads/mcp_main.py` which registers all 87 services as MCP tools.

Both modes use the **same service classes and SDK client** — one codebase, two interfaces.

---

## 4. Phased Implementation

### Phase 1: Bundle & Integrate (Foundation)

**Goal:** Copy MCP services into the webapp, verify they work, expose high-impact services as REST endpoints.

**Steps:**
1. Copy `google-ads-mcp/src/` into `backend/google_ads/`
2. Copy `google-ads-mcp/main.py` as `backend/google_ads/mcp_main.py`
3. Update Python path and imports (`src.` → `google_ads.`)
4. Verify MCP server starts from new location
5. Replace the current basic `google_ads.py` service with imports from the bundled services
6. Add REST endpoints for the most impactful operations:
   - Campaign CRUD (create, update status, update budget, pause/enable)
   - Keyword management (add, pause, remove, change match type)
   - Ad management (create responsive search ads, pause, enable)
   - Search term report
   - Change history

**Frontend additions for Phase 1:**
- Quick action buttons on campaigns (Pause, Enable, Edit Budget)
- Inline keyword management (add/pause/remove directly in the table)
- Inline ad management
- Search terms tab with "Add as Negative" buttons

**Priority services to expose as REST (20 services):**

| Service | REST Endpoints | UI Feature |
|---------|---------------|------------|
| campaign | POST create, PUT update, PUT status | Campaign creation, quick status toggle |
| budget | PUT update | Edit budget inline |
| ad_group | POST create, PUT update | Ad group management |
| ad_group_criterion (keyword) | POST add, PUT status, DELETE | Keyword add/pause/remove |
| ad_group_ad | POST create, PUT status | Ad creation, pause/enable |
| campaign_criterion | POST add (location, language, negative KW) | Targeting management |
| search (GAQL) | POST query | Search terms, custom reports |
| conversion | GET list, POST create | Conversion action management |
| campaign_conversion_goal | PUT update | Set campaign conversion goals |
| bidding_strategy | GET list, PUT update | Change bidding strategy |

### Phase 2: AI Chat Integration

**Goal:** Connect Claude Code SDK to the bundled MCP server so the chat agent can use all 87 tools.

**Steps:**
1. Install `claude_code_sdk` (or `claude-code-sdk`) Python package
2. Create `backend/app/services/agent.py` that spawns Claude Code agent
3. Configure agent with `google_ads/mcp_main.py` as MCP server
4. Auto-inject campaign guidelines into agent system prompt
5. Stream agent responses via SSE to the frontend chat panel
6. Add tool confirmation mode for mutations

### Phase 3: Speed Optimizations

**Goal:** Make the app noticeably faster than Google Ads UI.

**Features:**
- **Aggressive caching** — campaign structure cached, metrics cached with short TTL
- **Batch operations** — change 10 keywords in one API call (batch_job service)
- **Prefetching** — when user selects a campaign, prefetch ad groups, keywords, ads in parallel
- **Optimistic UI** — show the change immediately, confirm async
- **Keyboard shortcuts** — Cmd+P pause campaign, Cmd+E enable, Cmd+N new keyword
- **Bulk actions** — select multiple keywords → bulk pause/enable/remove

### Phase 4: API Version Update

**Goal:** Update all 87 services from v23 to the latest stable version.

**Steps:**
1. Check latest google-ads SDK version and what API version it defaults to
2. Update `pyproject.toml` dependency
3. Grep all v23 imports, update to latest version
4. Run type checker (pyright) to catch breaking changes
5. Update proto type references
6. Test critical services (campaign, keywords, ads, conversions)

### Phase 5: Multi-API Support (Future)

**Architecture for adding other APIs:**

```
backend/
├── google_ads/        # Google Ads services (87)
├── analytics/         # Google Analytics 4 (future)
│   ├── sdk_client.py
│   ├── services/
│   └── mcp_main.py
├── tag_manager/       # GTM API (future)
│   ├── services/
│   └── mcp_main.py
├── meta_ads/          # Meta/Facebook Ads (future)
│   ├── sdk_client.py
│   ├── services/
│   └── mcp_main.py
└── app/               # FastAPI web layer (combines all)
```

Each API gets its own package with the same pattern:
- `sdk_client.py` — authentication
- `services/` — service implementations
- `mcp_main.py` — MCP server for AI agent access

The Claude Code agent would connect to multiple MCP servers:
```python
mcp_servers=[
    {"name": "google-ads", "command": "python", "args": ["google_ads/mcp_main.py"]},
    {"name": "analytics", "command": "python", "args": ["analytics/mcp_main.py"]},
    {"name": "chrome", "command": "...", "args": ["..."]},
]
```

---

## 5. Functional Requirements (v2 additions)

### FR Group 8: Direct Campaign Operations (REST)

| ID | Requirement | Phase |
|----|-------------|-------|
| FR8.1 | User can create a new campaign via a form or AI chat, specifying name, type, budget, bidding strategy, location targets, language | Phase 1 |
| FR8.2 | User can pause/enable campaigns with one click from the campaign list | Phase 1 |
| FR8.3 | User can edit campaign budget inline (click budget → edit → save) | Phase 1 |
| FR8.4 | User can change bidding strategy from campaign settings panel | Phase 1 |
| FR8.5 | User can add keywords directly from the keyword table (text + match type → add) | Phase 1 |
| FR8.6 | User can pause/enable/remove keywords with checkboxes + bulk action button | Phase 1 |
| FR8.7 | User can create responsive search ads from a form (headlines + descriptions) | Phase 1 |
| FR8.8 | User can view search terms report and add negatives with one click + reason | Phase 1 |
| FR8.9 | All mutations auto-log to the campaign guidelines Change Log section | Phase 1 |
| FR8.10 | User can view change history (from Google Ads API change_event resource) | Phase 1 |

### FR Group 9: Batch & Bulk Operations

| ID | Requirement | Phase |
|----|-------------|-------|
| FR9.1 | User can select multiple campaigns and bulk pause/enable | Phase 3 |
| FR9.2 | User can paste a list of keywords (one per line) and bulk add to an ad group | Phase 3 |
| FR9.3 | User can bulk edit keyword match types | Phase 3 |
| FR9.4 | Batch operations use the Google Ads batch_job service for large changes (>100 operations) | Phase 3 |

### FR Group 10: Keyword Planning (built-in)

| ID | Requirement | Phase |
|----|-------------|-------|
| FR10.1 | User can generate keyword ideas from seed keywords using the keyword_plan_idea service | Phase 1 |
| FR10.2 | User can see search volume, competition, and bid estimates for keyword ideas | Phase 1 |
| FR10.3 | User can add selected keyword ideas directly to an ad group with one click | Phase 1 |

### FR Group 11: AI Agent with Full Service Access

| ID | Requirement | Phase |
|----|-------------|-------|
| FR11.1 | AI agent has access to all 87 Google Ads services via MCP | Phase 2 |
| FR11.2 | AI agent auto-loads campaign guidelines as context | Phase 2 |
| FR11.3 | AI agent can chain multiple services in one conversation turn (e.g., create campaign + add keywords + set conversion goal) | Phase 2 |
| FR11.4 | User can toggle confirmation mode for AI mutations | Phase 2 |

---

## 6. Non-Functional Requirements (v2 additions)

### Performance (Speed targets)

| Operation | Target | How |
|-----------|--------|-----|
| Campaign list load | <500ms | Cached, delta updates |
| Switch campaign | <200ms | Prefetched data |
| Pause/enable campaign | <1s UI response | Optimistic update + async API call |
| Add keyword | <1s | Direct API call, no batch overhead |
| Bulk add 50 keywords | <3s | Batch job service |
| Keyword ideas | <2s | Direct keyword_plan_idea service |
| AI first-token | <1s | Claude Code SDK streaming |
| Search terms report | <2s | Cached GAQL query |

### Architecture

| Requirement | Implementation |
|-------------|---------------|
| Single repo, single install | All services bundled in `backend/google_ads/` |
| No external dependencies on other folders | Zero references to `google-ads-mcp/` |
| Team can clone + configure + run | `git clone` → `cp .env.example .env` → `uv sync` → `npm install` → run |
| MCP server runs from inside the webapp | `backend/google_ads/mcp_main.py` is the entry point |
| Services shared between REST and MCP | Both import from `google_ads.services.*` |
| Future APIs follow the same pattern | New API = new package under `backend/` |

---

## 7. File Changes Summary

### New/Moved Files

```
backend/
├── google_ads/                    ← NEW (copied from google-ads-mcp/src/)
│   ├── __init__.py
│   ├── sdk_client.py              ← Copied, updated imports
│   ├── utils.py                   ← Copied
│   ├── mcp_main.py                ← Copied from main.py, updated paths
│   ├── services/                  ← All 87 service implementations
│   │   ├── account/
│   │   ├── ad_group/
│   │   ├── assets/
│   │   ├── audiences/
│   │   ├── bidding/
│   │   ├── campaign/
│   │   ├── conversions/
│   │   ├── data_import/
│   │   ├── metadata/
│   │   ├── planning/
│   │   ├── product_integration/
│   │   ├── shared/
│   │   └── targeting/
│   └── servers/                   ← All 87 FastMCP server wrappers
│
├── app/
│   ├── routers/
│   │   ├── campaigns.py           ← UPDATED: Uses google_ads services
│   │   ├── keywords.py            ← NEW: Keyword CRUD endpoints
│   │   ├── ads.py                 ← NEW: Ad management endpoints
│   │   ├── operations.py          ← NEW: Bulk operations
│   │   ├── planning.py            ← NEW: Keyword planning endpoints
│   │   └── chat.py                ← UPDATED: Claude Code SDK + MCP
│   └── services/
│       ├── google_ads.py          ← UPDATED: Thin wrapper over google_ads/
│       └── agent.py               ← NEW: Claude Code SDK agent service
```

### Import Change Pattern

All 87 service files need one import prefix change:
```python
# Before (in google-ads-mcp):
from src.sdk_client import get_sdk_client
from src.utils import format_customer_id, serialize_proto_message

# After (in google-ads-webapp):
from google_ads.sdk_client import get_sdk_client
from google_ads.utils import format_customer_id, serialize_proto_message
```

This is a simple find-and-replace across all files.

---

## 8. Success Criteria

| Metric | Target |
|--------|--------|
| All 87 services accessible from the webapp | 87/87 working |
| MCP server starts from bundled location | `python google_ads/mcp_main.py --groups all` works |
| REST endpoints cover top 20 operations | 20 endpoints working |
| Campaign budget change | <1 second from click to confirmation |
| Keyword addition | <1 second per keyword |
| No references to external MCP folder | 0 external path references |
| Clone-to-running time | <5 minutes (clone, .env, install, start) |
| AI agent has full 87-tool access | All tools show in chat tool calls |

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Import path changes break services | High | Automated find-and-replace + run pyright |
| v23 API deprecation | Medium | Update to latest in Phase 4, pin SDK version |
| Large repo size (87 services + tests) | Low | Only Python files, no large assets |
| Claude Code SDK API changes | Medium | Abstract behind AgentService interface |
| Rate limiting on direct REST operations | Medium | Queue mutations, show progress |
| Merge conflicts with ongoing MCP development | High | One-time copy, webapp becomes the primary repo |

---

## 10. Implementation Order

```
Phase 1: Bundle & Integrate (1-2 weeks)
  ├── Step 1: Copy MCP services into backend/google_ads/
  ├── Step 2: Fix imports (src. → google_ads.)
  ├── Step 3: Verify MCP server starts from new location
  ├── Step 4: Replace basic google_ads.py with service imports
  ├── Step 5: Add REST endpoints for top 20 operations
  └── Step 6: Add UI for direct operations (pause, budget, add keyword)

Phase 2: AI Chat (1 week)
  ├── Step 1: Install Claude Code SDK
  ├── Step 2: Create agent service with MCP server config
  ├── Step 3: Wire SSE streaming to chat panel
  └── Step 4: Add tool confirmation mode

Phase 3: Speed (1 week)
  ├── Step 1: Aggressive caching layer
  ├── Step 2: Batch operations
  ├── Step 3: Prefetching
  ├── Step 4: Optimistic UI
  └── Step 5: Keyboard shortcuts

Phase 4: API Update (2-3 days)
  ├── Step 1: Update google-ads SDK version
  ├── Step 2: Update all v23 imports to latest
  └── Step 3: Type check + test

Phase 5: Multi-API (future, as needed)
  └── Add analytics/, tag_manager/, meta_ads/ packages
```
