---
stepsCompleted: [01-init, 02-context-analysis, 03-starter-template, 04-architectural-decisions, 05-design-patterns, 06-data-integration, 07-validation, 08-complete]
inputDocuments: [_bmad-output/planning-artifacts/prd-v2.md, _bmad-output/planning-artifacts/product-brief-v2.md, docs/architecture.md]
workflowType: 'architecture'
lastStep: 8
projectType: 'web_app'
---

# Architecture Document - Google Ads Agent V2

**Author:** Wassim
**Date:** 2026-04-03
**Version:** 2.0
**Status:** Living — §1–§10 are the April 2026 V2 design (kept as written); §11 is the as-built delta ledger, last reconciled 2026-07-14
**Previous Version:** docs/architecture.md (V1)

---

## Table of Contents

1. [V2 Architecture Delta](#1-v2-architecture-delta)
2. [Technology Stack](#2-technology-stack)
3. [Architectural Decisions](#3-architectural-decisions)
4. [System Architecture](#4-system-architecture)
5. [Data Architecture](#5-data-architecture)
6. [Service Architecture](#6-service-architecture)
7. [API Contracts](#7-api-contracts)
8. [Frontend Architecture](#8-frontend-architecture)
9. [AI Agent Architecture](#9-ai-agent-architecture)
10. [Cross-Cutting Concerns](#10-cross-cutting-concerns)
11. [Shipped Delta Ledger (V2.1+, reconciled 2026-07-14)](#11-shipped-delta-ledger-v21-reconciled-2026-07-14)

---

## 1. V2 Architecture Delta

### What stays the same

| Component | Rationale |
|-----------|-----------|
| React 19 + TypeScript frontend | Mature, no reason to change |
| Python FastAPI backend | Google Ads SDK is Python, MCP server is Python |
| SQLite via aiosqlite | Zero-config, local-first, sufficient for local scale |
| Claude Code CLI as AI runtime | **Core principle: CLI subscription only, no API** |
| MCP server consumed as-is | 87 tools, no modifications |
| SSE for chat streaming | Simple, proven, HTTP-based |
| Filesystem markdown guidelines | Backward-compatible, editable externally, git-friendly |
| Monorepo (frontend/ + backend/) | Single repo, coordinated deployment |

### What changes

| Component | V1 | V2 | Why |
|-----------|-----|-----|-----|
| **Scale model** | 1 user, 1-5 accounts | Multi-account, agency scale (100+ accounts) | Public release for agencies |
| **Database schema** | Single namespace | Per-account partitioning (account_id FK) | Account isolation |
| **Agent intelligence** | Reactive (answer questions) | Proactive (surface issues, goal-aware, phase-aware) | Marketing intelligence |
| **Guidelines** | Manual creation only | Auto-generated + manual editing | Smart onboarding |
| **Data display** | Tables only | Tables + charts + dashboards | Performance visibility |
| **Operations** | Basic (pause, budget, keywords) | Full lifecycle (create campaigns, bulk ops, ad copy) | Editing parity |
| **Conversations** | Single thread, no search | Multi-thread, full-text search, campaign tagging | History management |
| **Frontend** | 3-panel fixed layout | + agency dashboard, + search term manager, + charts | Agency features |
| **Config** | Single .env | Multi-account credentials in encrypted SQLite | Multiple clients |

### What is explicitly NOT changing

| Constraint | Detail |
|------------|--------|
| **No Anthropic API** | Agent runs through Claude Code CLI only. Users pay via CLI subscription, NOT API keys. No `anthropic` SDK import for chat. |
| **No cloud backend** | 100% local. No SaaS, no hosted service, no remote database. *(Superseded 2026-06-10 for the hosted-MCP track only — see PRD §8 Phase 1.5 note: the app stays local-first, but the MCP bridge becomes hostable, token-secured.)* |
| **No Docker requirement** | Direct install via `bash install.sh`. No containers. |
| **CLI-first AI** | The Claude Code CLI subprocess model stays. Future Gemini CLI support follows the same pattern (CLI binary, not API). |

---

## 2. Technology Stack

### Retained Stack (V1 → V2)

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Frontend Framework | React | 19 | Same |
| Frontend Language | TypeScript | 5.9 | Same |
| Build Tool | Vite | 8 | Same |
| UI Components | shadcn/ui + Radix | Latest | Same |
| Styling | Tailwind CSS | 4.2 | Same |
| Client State | Zustand | 5 | Same |
| Server State | TanStack Query | 5 | Same |
| Routing | React Router | 7 | Same |
| Markdown Editor | @uiw/react-md-editor | 4 | Same |
| Backend Framework | FastAPI | 0.115+ | Same |
| Backend Language | Python | 3.12+ | Same |
| Database | SQLite (aiosqlite) | Latest | Same |
| ORM | SQLModel | Latest | Same |
| Google Ads SDK | google-ads-python | 29.2.0 | Same |
| MCP Framework | fastmcp | 3.2 | Same |
| AI Runtime | Claude Code CLI | Latest | **CLI only, no API** |
| Process Manager | uvicorn | 0.43+ | Same |
| Package Manager (Python) | uv | Latest | Same |
| Package Manager (JS) | npm | 10+ | Same |

### New Dependencies (V2)

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Charts | **Recharts** | 2.x | Performance dashboards, time-series charts |
| Tables (enhanced) | **TanStack Table** | 8.x | Virtual scrolling, bulk selection, advanced filtering |
| Search | **SQLite FTS5** | Built-in | Full-text search across conversations |
| PDF Export | **markdown-pdf** or **pdfkit** | Latest | Client-facing report generation (Phase 2) |
| CSV Export | **Python csv** (stdlib) | Built-in | Data export |
| Icons | **Lucide React** | Latest | Already in V1, extended for new UI elements |

### What We Are NOT Adding

| Technology | Why Not |
|------------|---------|
| `anthropic` Python SDK | **No API usage.** Agent runs through Claude Code CLI subprocess. |
| `openai` / any API SDK | Same — CLI only. |
| Docker / Docker Compose | Users install directly. No containerization overhead. |
| PostgreSQL / MySQL | SQLite is sufficient for local-first, single-machine use. |
| Redis | No need for distributed cache. SQLite cache is fine. |
| Next.js / SSR framework | Local SPA, no SEO needed. |
| Electron | Runs in browser. No need to bundle a browser. |

---

## 3. Architectural Decisions

### AD-1: Claude Code CLI as Agent Runtime (REINFORCED)

#### Context

V2 must decide how the AI agent communicates with Claude models. Options:
- (A) Anthropic API directly (`anthropic` SDK) — requires API key, per-token billing
- (B) Claude Code CLI subprocess — uses CLI subscription, no per-token cost
- (C) Claude Code SDK Python package — wraps the CLI, same subscription model

#### Decision

**Stay with Claude Code CLI subprocess** (same as V1). The `claude_code_sdk` Python package wraps the CLI, which is fine. But the critical constraint is: **the agent MUST use the user's Claude Code subscription, NOT an Anthropic API key**.

#### Rationale

- Users already pay for Claude Code subscription ($20/mo Pro, $100/mo Max, $200/mo Team)
- No additional API costs — this is the tool's core economic advantage
- CLI handles authentication, rate limiting, model routing, MCP server management
- Future Gemini CLI support follows the same pattern (CLI binary, not API)
- This is what makes the tool genuinely **free** for users who already have Claude Code

#### Implementation

```python
# backend/app/services/agent.py — V2
# CRITICAL: We spawn the Claude Code CLI process directly.
# We do NOT import or use the `anthropic` SDK for chat.
# The user's Claude Code subscription handles all billing.

import subprocess
import shutil

_NODE_PATH = shutil.which("node") or "node"
_CLI_JS = _find_cli_js()  # Finds Claude Code CLI entry point

async def _run_agent(prompt: str, system_prompt: str, model: str, mcp_config: dict):
    """Spawn Claude Code CLI as subprocess. Uses CLI subscription, not API."""
    cmd = [
        str(_NODE_PATH), str(_CLI_JS),
        "--output-format", "stream-json",
        "--model", model,
        "--max-turns", "15",
        "--verbose",
    ]
    
    # MCP servers configured via --mcp-config
    cmd.extend(["--mcp-config", json.dumps(mcp_config)])
    
    # System prompt via --system-prompt
    cmd.extend(["--system-prompt", system_prompt])
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    # Send user prompt via stdin (avoids shell escaping issues)
    proc.stdin.write(prompt)
    proc.stdin.close()
    
    # Stream JSON responses from stdout
    for line in proc.stdout:
        yield json.loads(line)
```

#### Implications

- No `anthropic` SDK in requirements (for chat)
- Agent startup has ~1-2s latency (CLI process + MCP server init)
- Must handle CLI not found, subscription expired, rate limiting
- Future Gemini CLI support: same subprocess pattern, different binary

#### Future: Gemini CLI Support (Phase 3)

```python
# Same pattern, different CLI binary
if ai_backend == "gemini":
    cmd = [shutil.which("gemini"), "chat", "--stream", ...]
elif ai_backend == "claude":
    cmd = [str(_NODE_PATH), str(_CLI_JS), ...]
```

---

### AD-2: Direct Google Ads SDK for Reads (UNCHANGED)

Same as V1. Use `GoogleAdsSdkClient` for read-only data fetching (campaign browser, metrics, account hierarchy). AI agent reserved for analysis, recommendations, and writes.

**V2 Enhancement:** Direct SDK also used for:
- Smart onboarding scan (bulk account analysis)
- Dashboard aggregation (cross-account metrics)
- Alert detection (CPA spike checks, budget pacing)

---

### AD-3: SSE for Chat Streaming (UNCHANGED)

Same as V1. Server-Sent Events for streaming agent responses to frontend.

---

### AD-4: SQLite with Per-Account Partitioning (ENHANCED)

#### Context

V1 used a single SQLite database with no account isolation. V2 must support 100+ accounts with data isolation.

#### Decision

**Single SQLite database with `account_id` foreign key** on all account-specific tables. NOT separate databases per account.

#### Rationale

- Single file is simpler to manage, backup, migrate
- SQLite handles this scale easily (100 accounts * 1000 campaigns = 100K rows — trivial)
- FTS5 full-text search works across a single database
- Cross-account queries (agency dashboard) are simple JOINs
- Per-account isolation achieved via query filtering, not physical separation

#### Implications

- All queries must include `WHERE account_id = ?` filtering
- Migration script adds `account_id` column to existing V1 tables
- Index on `account_id` for all tables

---

### AD-5: Guidelines Filesystem with Account Namespacing (ENHANCED)

#### Context

V1 stored all guidelines in a flat `data/guidelines/` directory. V2 must support per-account guidelines without name collisions.

#### Decision

**Namespace guidelines by account ID** in the filesystem:

```
data/
├── guidelines/
│   ├── 7178239091/                    # Mercan Group
│   │   ├── BUSINESS_CONTEXT.md
│   │   ├── CAMPAIGN_GUIDELINES.md
│   │   └── MENA_CAMPAIGN_GUIDELINES.md
│   ├── 1234567890/                    # Client B
│   │   ├── BUSINESS_CONTEXT.md
│   │   └── CAMPAIGN_GUIDELINES.md
│   └── _playbooks/                    # Shared playbook templates
│       ├── lead-gen-professional.md
│       └── ecommerce-shopping.md
```

#### Rationale

- Clear separation per account
- Files still editable externally, git-friendly
- Backward compatible: V1 migration moves existing files into first account's folder
- Playbooks are global (shared across accounts)

#### Migration from V1

```python
# On first V2 startup, if flat guidelines exist:
# 1. Detect existing files in data/guidelines/
# 2. Move them into data/guidelines/{default_account_id}/
# 3. Log the migration
```

---

### AD-6: Marketing Intelligence as a Service Layer (NEW)

#### Context

V2 needs campaign goal detection, phase awareness, proactive recommendations, and cross-campaign reasoning. Where does this logic live?

#### Decision

New **`MarketingIntelligenceService`** that sits between the data layer and the agent service. It analyzes campaign data and enriches the agent's system prompt with marketing context.

#### Rationale

- Separates marketing logic from agent orchestration
- Can be tested independently (input: campaign data → output: intelligence report)
- Enriches both the agent's prompt AND the dashboard UI
- Runs on direct SDK data (fast), not through the AI agent (expensive)

#### Implementation

```python
# backend/app/services/marketing_intelligence.py

class MarketingIntelligenceService:
    """Analyzes campaign data to produce marketing intelligence."""
    
    async def detect_campaign_phase(self, campaign_data: dict) -> CampaignPhase:
        """Detect launch/learning/optimization/scaling/sunset from data signals."""
        age_days = (date.today() - campaign_data["start_date"]).days
        conversions_30d = campaign_data["conversions_30d"]
        bid_strategy_changed = campaign_data.get("bid_strategy_change_date")
        
        if age_days < 14:
            return CampaignPhase.LAUNCH
        if bid_strategy_changed and (date.today() - bid_strategy_changed).days < 14:
            return CampaignPhase.LEARNING
        if conversions_30d > 30 and campaign_data["cpa"] < campaign_data.get("target_cpa", float("inf")):
            return CampaignPhase.SCALING
        # ... more heuristics
    
    async def detect_campaign_goal(self, campaign_data: dict) -> CampaignGoal:
        """Infer goal from conversion actions and bid strategy."""
        conversion_actions = campaign_data["conversion_actions"]
        bid_strategy = campaign_data["bid_strategy"]
        
        if any("purchase" in c["name"].lower() for c in conversion_actions):
            return CampaignGoal.ECOMMERCE
        if any("lead" in c["name"].lower() or "form" in c["name"].lower() for c in conversion_actions):
            return CampaignGoal.LEAD_GEN
        if bid_strategy == "MAXIMIZE_CLICKS":
            return CampaignGoal.TRAFFIC
        return CampaignGoal.UNKNOWN
    
    async def generate_proactive_insights(self, account_id: str) -> list[Insight]:
        """Surface issues and opportunities without being asked."""
        insights = []
        campaigns = await self._get_campaign_data(account_id)
        
        for campaign in campaigns:
            # CPA spike detection
            if campaign["cpa_7d"] > campaign["cpa_30d"] * 1.3:
                insights.append(Insight(
                    type="cpa_spike",
                    severity="warning",
                    campaign_id=campaign["id"],
                    message=f"CPA spiked {((campaign['cpa_7d']/campaign['cpa_30d'])-1)*100:.0f}% vs 30-day average",
                    recommendation="Review search terms for irrelevant matches"
                ))
            
            # Budget pacing
            days_in_month = 30
            day_of_month = date.today().day
            expected_spend_pct = day_of_month / days_in_month
            actual_spend_pct = campaign["cost_mtd"] / campaign["monthly_budget"]
            if actual_spend_pct > expected_spend_pct * 1.2:
                insights.append(Insight(
                    type="budget_pacing",
                    severity="warning",
                    campaign_id=campaign["id"],
                    message=f"Spending {actual_spend_pct*100:.0f}% of monthly budget by day {day_of_month}",
                    recommendation="Consider reducing daily budget to avoid early exhaustion"
                ))
            
            # Search term review cadence
            last_review = campaign.get("last_search_term_review")
            if last_review and (date.today() - last_review).days > 7:
                insights.append(Insight(
                    type="search_term_review",
                    severity="info",
                    campaign_id=campaign["id"],
                    message=f"Search terms not reviewed in {(date.today() - last_review).days} days"
                ))
        
        return insights
    
    async def enrich_agent_prompt(self, account_id: str, campaign_id: str) -> str:
        """Generate marketing intelligence block for the agent's system prompt."""
        campaign = await self._get_campaign_data_single(account_id, campaign_id)
        phase = await self.detect_campaign_phase(campaign)
        goal = await self.detect_campaign_goal(campaign)
        insights = await self.generate_proactive_insights(account_id)
        
        return f"""
## Marketing Intelligence

**Campaign Goal:** {goal.value}
**Campaign Phase:** {phase.value}
**Phase Rules:** {PHASE_RULES[phase]}

### Active Alerts
{self._format_insights(insights, campaign_id)}

### Strategic Context
- Account monthly budget: ${campaign.get('monthly_budget', 'N/A')}
- Campaign CPA trend: ${campaign['cpa_7d']:.2f} (7d) vs ${campaign['cpa_30d']:.2f} (30d)
- Conversion volume: {campaign['conversions_7d']} (7d), {campaign['conversions_30d']} (30d)
"""
```

---

### AD-7: Multi-Account Credential Management (NEW)

#### Context

V1 used a single `.env` file for one set of credentials. V2 must support multiple Google Ads accounts, each potentially with different credentials (different MCC accounts for different agency clients).

#### Decision

**Store credentials in encrypted SQLite** with the account record. Keep `.env` as the initial/default credential source for backward compatibility.

#### Implementation

```python
# backend/app/services/credentials.py
from cryptography.fernet import Fernet
import os

class CredentialStore:
    """Encrypted credential storage in SQLite."""
    
    def __init__(self, encryption_key: bytes = None):
        # Key derived from machine-specific source or user-provided passphrase
        self.fernet = Fernet(encryption_key or self._derive_key())
    
    def _derive_key(self) -> bytes:
        """Derive encryption key from machine ID + app secret."""
        # Use a stable machine identifier + fixed salt
        import hashlib, base64
        machine_id = str(uuid.getnode())  # MAC address as stable ID
        key = hashlib.pbkdf2_hmac('sha256', machine_id.encode(), b'google-ads-agent', 100000)
        return base64.urlsafe_b64encode(key)
    
    async def store_credentials(self, account_id: str, credentials: dict):
        encrypted = self.fernet.encrypt(json.dumps(credentials).encode())
        await db.execute(
            "INSERT OR REPLACE INTO account_credentials (account_id, credentials_encrypted) VALUES (?, ?)",
            (account_id, encrypted)
        )
    
    async def get_credentials(self, account_id: str) -> dict:
        row = await db.fetchone(
            "SELECT credentials_encrypted FROM account_credentials WHERE account_id = ?",
            (account_id,)
        )
        return json.loads(self.fernet.decrypt(row[0]))
```

#### Migration from V1

On first V2 startup:
1. Read existing `backend/.env` credentials
2. Create default account record in SQLite
3. Encrypt and store credentials in `account_credentials` table
4. `.env` file kept for backward compatibility (still loaded if DB has no credentials)

---

### AD-8: Smart Onboarding via Direct SDK (NEW)

#### Context

When a new account is connected, V2 should auto-analyze campaigns and generate initial guidelines. This could go through the AI agent (expensive, slow) or direct SDK (fast, free).

#### Decision

Use **direct Google Ads SDK** for the onboarding scan. Generate guidelines using **deterministic logic** (not AI), then optionally refine with AI agent.

#### Rationale

- SDK scan is fast (~5-10s for full account) and costs nothing
- Guidelines generation from structured data doesn't need AI creativity
- AI agent can be used afterward to refine (optional, user-initiated)
- Keeps onboarding working even if Claude Code CLI is not installed yet

#### Implementation

```python
# backend/app/services/onboarding.py

class OnboardingService:
    """Auto-analyze new accounts and generate initial guidelines."""
    
    async def scan_account(self, account_id: str) -> AccountScan:
        """Full account scan using direct SDK."""
        ads_service = GoogleAdsService(account_id)
        
        scan = AccountScan(account_id=account_id)
        scan.campaigns = await ads_service.get_campaigns(account_id)
        
        for campaign in scan.campaigns:
            campaign.ad_groups = await ads_service.get_adgroups(account_id, campaign.id)
            campaign.conversion_actions = await ads_service.get_conversion_actions(account_id)
            campaign.phase = await marketing_intel.detect_campaign_phase(campaign)
            campaign.goal = await marketing_intel.detect_campaign_goal(campaign)
        
        return scan
    
    async def generate_guidelines(self, scan: AccountScan) -> dict[str, str]:
        """Generate markdown guidelines from scan data. No AI needed."""
        files = {}
        
        # Business context
        files["BUSINESS_CONTEXT.md"] = self._generate_business_context(scan)
        
        # Campaign guidelines
        files["CAMPAIGN_GUIDELINES.md"] = self._generate_campaign_guidelines(scan)
        
        return files
    
    def _generate_business_context(self, scan: AccountScan) -> str:
        return f"""# Business Context

## Account Overview
- **Account ID:** {scan.account_id}
- **Account Name:** {scan.account_name}
- **Active Campaigns:** {len([c for c in scan.campaigns if c.status == 'ENABLED'])}
- **Total Monthly Spend:** ${sum(c.cost_30d for c in scan.campaigns):,.2f}

## Campaign Summary
{self._campaigns_table(scan.campaigns)}

## Key Metrics (Last 30 Days)
- Total Conversions: {sum(c.conversions_30d for c in scan.campaigns)}
- Average CPA: ${self._avg_cpa(scan.campaigns):.2f}
- Total Impressions: {sum(c.impressions_30d for c in scan.campaigns):,}

---
*Auto-generated by Google Ads Agent on {date.today().isoformat()}. Edit to add business context, goals, and constraints.*
"""
```

---

## 4. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React SPA)                     │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐   │
│  │ Agency   │ │ Campaign │ │ Chat     │ │ Search Term     │   │
│  │Dashboard │ │ Browser  │ │ Panel    │ │ Manager         │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬─────────┘   │
│       │             │            │                │              │
│  ┌────┴─────────────┴────────────┴────────────────┴──────────┐  │
│  │  Zustand (UI state)  +  TanStack Query (server state)     │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │ REST + SSE
                               ▼
┌──────────────────────────────┴───────────────────────────────────┐
│                     BACKEND (FastAPI)                             │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      API ROUTERS                             │ │
│  │  dashboard | accounts | campaigns | chat | guidelines |      │ │
│  │  operations | search-terms | setup | export                  │ │
│  └───┬──────────┬──────────┬──────────┬──────────┬─────────────┘ │
│      │          │          │          │          │                │
│  ┌───▼────┐ ┌──▼─────┐ ┌──▼─────┐ ┌──▼──────┐ ┌▼────────────┐ │
│  │Dashboard│ │Google  │ │Agent   │ │Guide-   │ │Marketing    │ │
│  │Service  │ │Ads     │ │Service │ │lines    │ │Intelligence │ │
│  │         │ │Service │ │(CLI)   │ │Service  │ │Service      │ │
│  └───┬─────┘ └──┬─────┘ └──┬─────┘ └──┬──────┘ └┬────────────┘ │
│      │          │          │          │          │               │
│  ┌───▼──────────▼──────────┼──────────▼──────────▼─────────────┐│
│  │              DATA LAYER                                      ││
│  │  SQLite (aiosqlite)  +  Filesystem (.md)  +  Cache          ││
│  └──────────────────────────┼──────────────────────────────────┘│
│                              │                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       Google Ads API    Claude Code CLI   Chrome Browser
       (REST/gRPC)       (subprocess)      (optional MCP)
                         ├─ google-ads MCP
                         └─ chrome MCP
```

### Request Flow: Agent Chat (CLI Subprocess)

```
User types message
        │
        ▼
Frontend POST /api/conversations/{id}/message
        │
        ▼
Backend receives message
        │
        ├─ 1. Load account credentials from encrypted SQLite
        ├─ 2. Load guidelines (filesystem: data/guidelines/{account_id}/)
        ├─ 3. Load recent conversation history (SQLite: last 10 messages)
        ├─ 4. Load session summaries (SQLite: last 5 per campaign)
        ├─ 5. Fetch live campaign data (Google Ads SDK → cache)
        ├─ 6. Generate marketing intelligence (phase, goal, insights)
        ├─ 7. Build system prompt (all 6 layers above)
        │
        ▼
Spawn Claude Code CLI subprocess
        │
        ├─ stdin: user message
        ├─ args: --model, --mcp-config, --system-prompt, --output-format stream-json
        │
        ▼
CLI process runs (uses user's Claude Code subscription)
        │
        ├─ Reads MCP tools from google-ads MCP server
        ├─ Optionally reads Chrome MCP tools
        ├─ Streams JSON events to stdout
        │
        ▼
Backend reads stdout line-by-line
        │
        ├─ text → SSE event to frontend
        ├─ tool_call → SSE event (with source: google-ads | chrome)
        ├─ tool_result → SSE event
        │
        ▼
Frontend renders streaming response
        │
        ▼
On completion:
        ├─ Save full message to SQLite
        ├─ Generate session summary if response > 500 chars
        ├─ Update alert state if issues resolved
        └─ CLI process exits
```

### Request Flow: Agency Dashboard

```
Frontend GET /api/dashboard
        │
        ▼
DashboardService
        │
        ├─ For each connected account:
        │   ├─ Check cache (SQLite)
        │   ├─ If stale: fetch via GoogleAdsService (direct SDK)
        │   ├─ Compute health indicators
        │   └─ Check active alerts
        │
        ▼
Return aggregated dashboard data
        │
        ├─ Account list with health badges
        ├─ Total spend across accounts
        ├─ Active alerts sorted by severity
        └─ Per-account: campaign count, conversions, CPA
```

### Request Flow: Smart Onboarding

```
User adds new account credentials
        │
        ▼
POST /api/accounts (credentials)
        │
        ▼
Backend validates credentials (test API call)
        │
        ▼
OnboardingService.scan_account()
        │
        ├─ Fetch all campaigns via direct SDK
        ├─ Fetch ad groups, keywords, conversion actions
        ├─ Detect campaign phases and goals
        ├─ Generate health assessment
        │
        ▼
OnboardingService.generate_guidelines()
        │
        ├─ Create BUSINESS_CONTEXT.md (deterministic, no AI)
        ├─ Create CAMPAIGN_GUIDELINES.md (deterministic, no AI)
        ├─ Write to data/guidelines/{account_id}/
        │
        ▼
Save account + campaign_goals to SQLite
        │
        ▼
Return scan results to frontend
        │
        ├─ Account summary
        ├─ Campaign list with detected phases/goals
        ├─ Generated guidelines preview
        └─ Agent greeting with account overview
```

---

## 5. Data Architecture

### SQLite Schema (V2)

```sql
-- ═══════════════════════════════════════════════════════
-- MIGRATION: V1 → V2
-- Run on first V2 startup, detected by schema_version
-- ═══════════════════════════════════════════════════════

-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- ACCOUNTS (New in V2)
-- ═══════════════════════════════════════════════════════

CREATE TABLE accounts_v2 (
    id TEXT PRIMARY KEY,              -- Google Ads customer ID (MCC or client)
    name TEXT NOT NULL,
    mcc_id TEXT,                      -- Parent MCC, NULL if this IS the MCC
    level TEXT NOT NULL,              -- 'mcc', 'sub_manager', 'client'
    is_active BOOLEAN DEFAULT 1,
    onboarded_at TIMESTAMP,
    last_synced TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE account_credentials (
    account_id TEXT PRIMARY KEY,
    developer_token_encrypted BLOB,
    client_id_encrypted BLOB,
    client_secret_encrypted BLOB,
    refresh_token_encrypted BLOB,
    login_customer_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════
-- MARKETING INTELLIGENCE (New in V2)
-- ═══════════════════════════════════════════════════════

CREATE TABLE campaign_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    campaign_name TEXT,
    objective TEXT,                    -- lead_gen, ecommerce, brand, traffic, local, unknown
    phase TEXT,                        -- launch, learning, optimization, scaling, sunset
    phase_detected_at TIMESTAMP,
    target_cpa REAL,
    target_roas REAL,
    monthly_budget_cap REAL,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, campaign_id),
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    campaign_id TEXT,                  -- NULL for account-level alerts
    type TEXT NOT NULL,                -- cpa_spike, budget_pacing, conversion_drop, search_term_review, phase_change
    severity TEXT NOT NULL,            -- info, warning, critical
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    recommendation TEXT,
    data_json TEXT,                    -- Additional structured data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dismissed_at TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

CREATE INDEX idx_alerts_account ON alerts(account_id, dismissed_at);
CREATE INDEX idx_alerts_severity ON alerts(severity, created_at);

-- ═══════════════════════════════════════════════════════
-- CONVERSATIONS (Enhanced from V1)
-- ═══════════════════════════════════════════════════════

-- V1 table enhanced with account_id
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,          -- V2: required (was optional in V1)
    campaign_id TEXT,
    campaign_name TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

CREATE INDEX idx_conversations_account ON conversations(account_id, updated_at DESC);

-- V1 table enhanced with account_id
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    account_id TEXT NOT NULL,          -- V2: denormalized for search
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_name TEXT,
    tool_source TEXT,
    tool_input TEXT,
    tool_output TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);

-- Full-text search index (V2 new)
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Session summaries (enhanced from V1)
CREATE TABLE session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    campaign_id TEXT,
    campaign_name TEXT,
    summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

CREATE INDEX idx_summaries_campaign ON session_summaries(account_id, campaign_id, created_at DESC);

-- ═══════════════════════════════════════════════════════
-- CACHE (Enhanced from V1)
-- ═══════════════════════════════════════════════════════

CREATE TABLE cache (
    key TEXT PRIMARY KEY,             -- e.g., "{account_id}:campaigns" or "{account_id}:{campaign_id}:keywords"
    account_id TEXT NOT NULL,
    data TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE INDEX idx_cache_account ON cache(account_id);

-- ═══════════════════════════════════════════════════════
-- PLAYBOOKS (New in V2 Phase 2)
-- ═══════════════════════════════════════════════════════

CREATE TABLE playbooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    vertical TEXT,                     -- lead_gen, ecommerce, local, saas, brand, real_estate
    content TEXT NOT NULL,             -- Markdown template content
    source TEXT DEFAULT 'built-in',   -- built-in, community, custom
    version TEXT,
    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════
-- APP CONFIG (Same as V1)
-- ═══════════════════════════════════════════════════════

CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE guidelines_meta (
    filename TEXT NOT NULL,
    account_id TEXT NOT NULL,
    campaign_id TEXT,
    campaign_name TEXT,
    last_modified REAL,
    sections TEXT,
    PRIMARY KEY (filename, account_id),
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);
```

### Migration Strategy (V1 → V2)

```python
# backend/app/database.py

async def migrate_v1_to_v2(db):
    """One-time migration from V1 schema to V2."""
    
    # 1. Create new tables
    await db.executescript(V2_SCHEMA_SQL)
    
    # 2. Detect default account from .env
    default_account_id = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
    
    # 3. Create account record
    await db.execute(
        "INSERT INTO accounts_v2 (id, name, mcc_id, level) VALUES (?, ?, ?, ?)",
        (default_account_id, "Default Account", None, "mcc")
    )
    
    # 4. Migrate credentials from .env to encrypted DB
    await credential_store.store_credentials(default_account_id, {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": settings.GOOGLE_ADS_CLIENT_ID,
        "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
    })
    
    # 5. Add account_id to existing conversations/messages
    await db.execute(
        "UPDATE conversations SET account_id = ? WHERE account_id IS NULL",
        (default_account_id,)
    )
    await db.execute(
        "UPDATE messages SET account_id = ? WHERE account_id IS NULL",
        (default_account_id,)
    )
    
    # 6. Move guideline files into account folder
    guidelines_dir = Path(settings.GUIDELINES_DIR)
    account_dir = guidelines_dir / default_account_id
    account_dir.mkdir(exist_ok=True)
    for md_file in guidelines_dir.glob("*.md"):
        md_file.rename(account_dir / md_file.name)
    
    # 7. Record migration
    await db.execute("INSERT INTO schema_version (version) VALUES (2)")
```

### Filesystem Structure (V2)

```
google-ads-agent/
├── _bmad/                             # BMad framework
├── _bmad-output/                      # BMad artifacts
├── docs/                              # V1 docs (kept for reference)
├── frontend/                          # React SPA (enhanced)
│   └── src/
│       ├── components/
│       │   ├── ui/                    # shadcn/ui (same)
│       │   ├── layout/               # Header, Sidebar, ChatPanel (enhanced)
│       │   ├── campaign/             # Campaign components (enhanced)
│       │   ├── chat/                 # Chat components (enhanced)
│       │   ├── guidelines/           # Guidelines components (same)
│       │   ├── setup/                # Setup wizard (enhanced)
│       │   ├── dashboard/            # NEW: Agency dashboard
│       │   ├── charts/               # NEW: Performance charts
│       │   └── search-terms/         # NEW: Search term manager
│       ├── hooks/                    # Enhanced + new hooks
│       ├── stores/                   # Enhanced stores
│       ├── lib/                      # Enhanced API client
│       └── types/                    # Enhanced types
│
├── backend/                           # Python FastAPI (enhanced)
│   ├── app/
│   │   ├── main.py                   # Enhanced with migration check
│   │   ├── config.py                 # Enhanced for multi-account
│   │   ├── database.py              # V2 schema + migration
│   │   ├── routers/
│   │   │   ├── accounts.py          # NEW: Multi-account management
│   │   │   ├── campaigns.py         # Enhanced with charts data
│   │   │   ├── chat.py              # Enhanced with search, multi-thread
│   │   │   ├── dashboard.py         # NEW: Agency dashboard
│   │   │   ├── guidelines.py        # Enhanced with account namespacing
│   │   │   ├── operations.py        # Enhanced with bulk ops
│   │   │   ├── search_terms.py      # NEW: Search term analysis
│   │   │   ├── export.py            # NEW: CSV/report export (Phase 2)
│   │   │   └── setup.py             # Enhanced for multi-account setup
│   │   ├── services/
│   │   │   ├── agent.py             # Enhanced with marketing intelligence prompt
│   │   │   ├── google_ads.py        # Enhanced for multi-account
│   │   │   ├── guidelines.py        # Enhanced with account namespacing
│   │   │   ├── cache.py             # Enhanced with account scoping
│   │   │   ├── credentials.py       # NEW: Encrypted credential store
│   │   │   ├── marketing_intelligence.py  # NEW: Goal/phase/insights
│   │   │   ├── onboarding.py        # NEW: Smart onboarding
│   │   │   ├── dashboard.py         # NEW: Cross-account aggregation
│   │   │   └── search_terms.py      # NEW: AI-categorized search terms
│   │   └── models/
│   │       └── schemas.py           # Enhanced with V2 types
│   │
│   ├── google_ads/                   # MCP server (UNCHANGED)
│   ├── pyproject.toml
│   └── .env                          # Backward-compatible, used as fallback
│
├── data/
│   ├── app.db                        # SQLite (V2 schema)
│   └── guidelines/
│       ├── {account_id_1}/           # Per-account guidelines
│       │   ├── BUSINESS_CONTEXT.md
│       │   └── CAMPAIGN_GUIDELINES.md
│       ├── {account_id_2}/
│       │   └── ...
│       └── _playbooks/               # Shared playbook templates
│
├── install.sh / install.bat          # One-command installer (enhanced)
├── start.sh / start.bat              # One-command starter (same)
└── README.md                         # Public-facing documentation
```

---

## 6. Service Architecture

### Service Dependency Graph

```
                    ┌──────────────┐
                    │   Routers    │
                    │  (API layer) │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
    │ Dashboard   │  │ Agent      │  │ Onboarding │
    │ Service     │  │ Service    │  │ Service    │
    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
          │                │                │
    ┌─────▼────────────────▼────────────────▼──────┐
    │           Marketing Intelligence              │
    │           Service                             │
    └─────┬──────────────────────────────┬─────────┘
          │                              │
    ┌─────▼──────┐                ┌──────▼─────┐
    │ GoogleAds   │                │ Guidelines │
    │ Service     │                │ Service    │
    └─────┬──────┘                └──────┬─────┘
          │                              │
    ┌─────▼──────┐                ┌──────▼─────┐
    │ Cache       │                │ Filesystem │
    │ (SQLite)    │                │ (.md files)│
    └─────┬──────┘                └────────────┘
          │
    ┌─────▼──────┐
    │ Google Ads  │
    │ API         │
    └─────────────┘
```

### Service Contracts

| Service | Input | Output | Dependencies |
|---------|-------|--------|-------------|
| `AgentService` | User message + context | Streaming SSE events | Claude Code CLI, MarketingIntelligence, Guidelines, GoogleAds |
| `GoogleAdsService` | Account ID + query params | Campaign data, metrics | Google Ads SDK, Cache |
| `MarketingIntelligenceService` | Campaign data | Phase, goal, insights, prompt enrichment | GoogleAdsService |
| `GuidelinesService` | Account ID + filename | Markdown content, sections | Filesystem |
| `OnboardingService` | Account credentials | Account scan + generated guidelines | GoogleAdsService, MarketingIntelligence, Guidelines |
| `DashboardService` | (none) | All-account health summary | GoogleAdsService, MarketingIntelligence, Alerts |
| `CredentialStore` | Account ID + credentials | Encrypted storage/retrieval | SQLite, cryptography |
| `CacheService` | Cache key + fetch function | Cached or fresh data | SQLite |
| `SearchTermService` | Account ID + campaign ID | Categorized search terms | GoogleAdsService |

---

## 7. API Contracts

### New Endpoints (V2)

#### Dashboard

```
GET /api/dashboard
Response: {
  accounts: [{
    id: string,
    name: string,
    health: "healthy" | "warning" | "critical",
    active_campaigns: number,
    total_spend_30d: number,
    total_conversions_30d: number,
    avg_cpa: number,
    alerts: [{type, severity, message}],
    last_synced: string
  }],
  total_alerts: number,
  total_spend_30d: number
}
```

#### Accounts

```
POST /api/accounts
Body: { developer_token, client_id, client_secret, refresh_token, login_customer_id }
Response: { account: Account, scan: AccountScan }

DELETE /api/accounts/{account_id}
Response: { deleted: true }

POST /api/accounts/{account_id}/onboard
Response: { scan: AccountScan, guidelines_generated: string[] }

GET /api/accounts/{account_id}/health
Response: { health: string, campaigns: [...], alerts: [...] }
```

#### Campaign Goals & Intelligence

```
GET /api/accounts/{account_id}/campaigns/{campaign_id}/goals
Response: { objective, phase, target_cpa, target_roas, monthly_budget_cap, notes }

PUT /api/accounts/{account_id}/campaigns/{campaign_id}/goals
Body: { objective?, phase?, target_cpa?, target_roas?, monthly_budget_cap?, notes? }
Response: { updated: CampaignGoal }

GET /api/accounts/{account_id}/campaigns/{campaign_id}/charts
Query: ?metric=cost,clicks,conversions,cpa&period=7d|14d|30d|90d|custom&from=&to=
Response: { labels: string[], datasets: [{label, data: number[]}] }
```

#### Search Terms

```
GET /api/accounts/{account_id}/campaigns/{campaign_id}/search-terms/analysis
Query: ?days=7
Response: {
  high_value: [{term, impressions, clicks, conversions, recommendation}],
  irrelevant: [{term, impressions, clicks, cost, suggested_negative_match_type, reason}],
  monitor: [{term, impressions, clicks, cost, reason}]
}
```

#### Conversation Search

```
GET /api/conversations/search
Query: ?q=search_text&account_id=&campaign_id=&from=&to=
Response: { results: [{conversation_id, message_id, content_snippet, created_at}] }
```

#### Alerts

```
GET /api/accounts/{account_id}/alerts
Query: ?severity=warning,critical&dismissed=false
Response: { alerts: [Alert] }

POST /api/accounts/{account_id}/alerts/{alert_id}/dismiss
Response: { dismissed: true }
```

#### Bulk Operations

```
POST /api/operations/bulk
Body: {
  account_id: string,
  operations: [{
    type: "pause" | "enable" | "budget_adjust" | "add_negative",
    campaign_id: string,
    params: { ... }
  }]
}
Response: { results: [{operation_index, success, error?}] }
```

### Existing Endpoints (Modified for V2)

All existing V1 endpoints gain an `account_id` path parameter:

```
# V1: GET /api/accounts
# V2: GET /api/accounts/{account_id}/hierarchy

# V1: GET /api/accounts/{id}/campaigns
# V2: GET /api/accounts/{account_id}/campaigns (same)

# V1: POST /api/conversations
# V2: POST /api/conversations (body now requires account_id)

# V1: GET /api/guidelines
# V2: GET /api/accounts/{account_id}/guidelines
```

---

## 8. Frontend Architecture

### New Pages / Views

| View | Route | Description |
|------|-------|-------------|
| Agency Dashboard | `/` (default) | All-account overview with health indicators |
| Account View | `/accounts/{id}` | Single account with campaign list |
| Campaign Detail | `/accounts/{id}/campaigns/{campaignId}` | Campaign detail with tabs |
| Search Terms | `/accounts/{id}/campaigns/{campaignId}/search-terms` | AI-categorized search term manager |
| Conversation Search | `/conversations/search` | Full-text search across all conversations |
| Setup Wizard | `/setup` | Multi-account credential setup |
| Settings | `/settings` | App preferences, account management |

### Component Tree (V2 additions highlighted)

```
<App>
├── <AgencyDashboard>           ★ NEW
│   ├── <AccountHealthCard>     ★ NEW (per account)
│   ├── <AlertBanner>           ★ NEW
│   └── <SpendOverviewChart>    ★ NEW
│
├── <AccountView>
│   ├── <Header>
│   │   ├── <AccountSwitcher>   ★ ENHANCED (multi-account)
│   │   ├── <CommandPalette>
│   │   └── <ThemeToggle>
│   ├── <Sidebar>
│   │   ├── <AccountTree>       ★ ENHANCED (multiple accounts)
│   │   ├── <CampaignList>
│   │   │   ├── <CampaignRow>
│   │   │   └── <PhaseBadge>    ★ NEW
│   │   └── <CampaignFilter>
│   ├── <ContentArea>
│   │   ├── <CampaignOverview>
│   │   │   ├── <MetricCards>
│   │   │   ├── <PerformanceChart>  ★ NEW
│   │   │   └── <PeriodComparison>  ★ NEW
│   │   ├── <AdGroupTree>
│   │   ├── <KeywordTable>       ★ ENHANCED (virtual scroll, bulk select)
│   │   ├── <AdsDisplay>
│   │   ├── <SearchTermManager>  ★ NEW
│   │   │   ├── <TermCategoryTabs> (High Value | Irrelevant | Monitor)
│   │   │   ├── <TermTable>
│   │   │   └── <BulkNegativeAction>
│   │   ├── <GuidelinesViewer>
│   │   └── <GuidelinesEditor>
│   └── <ChatPanel>
│       ├── <ConversationList>   ★ ENHANCED (multi-thread, search)
│       ├── <ChatMessages>
│       │   ├── <ChatMessage>
│       │   ├── <ToolCallBlock>
│       │   └── <InsightCard>    ★ NEW (proactive recommendations)
│       ├── <ChatInput>
│       │   ├── <ModelSelector>
│       │   └── <TemplateSelector>  ★ NEW (daily review, audit, etc.)
│       └── <ConversationSearch> ★ NEW
│
└── <SetupWizard>               ★ ENHANCED (multi-account)
```

### State Management (V2)

```typescript
// stores/appStore.ts — V2 enhanced
interface AppState {
  // V1 (kept)
  selectedCampaignId: string | null;
  sidebarCollapsed: boolean;
  chatPanelWidth: number;
  darkMode: boolean;
  
  // V2 (new)
  selectedAccountId: string | null;       // Currently active account
  connectedAccounts: Account[];           // All connected accounts
  dashboardView: boolean;                 // Show agency dashboard vs account view
  alerts: Alert[];                        // Active alerts across accounts
}

// stores/chatStore.ts — V2 enhanced
interface ChatState {
  // V1 (kept)
  messages: ChatMessage[];
  isStreaming: boolean;
  model: string;
  
  // V2 (new)
  conversations: Conversation[];          // All conversations for current account
  activeConversationId: string | null;
  searchQuery: string;
  searchResults: SearchResult[];
}
```

---

## 9. AI Agent Architecture

### System Prompt Structure (V2)

The agent's system prompt is now 6 layers (up from 5 in V1):

```
┌─────────────────────────────────────────────┐
│ Layer 0: Marketing Intelligence (NEW)        │
│ - Campaign goal and objective                │
│ - Campaign phase + phase rules               │
│ - Active alerts and recommendations          │
│ - Cross-campaign context                     │
│ ~500 tokens                                  │
├─────────────────────────────────────────────┤
│ Layer 1: Business Context (V1)               │
│ - Account structure and key info             │
│ - Business-level policies                    │
│ ~2K tokens                                   │
├─────────────────────────────────────────────┤
│ Layer 2: Campaign Guidelines (V1)            │
│ - Global rules + campaign-specific rules     │
│ - Auto-generated + manually edited           │
│ ~3K tokens                                   │
├─────────────────────────────────────────────┤
│ Layer 3: Recent Conversation (V1)            │
│ - Last 10 messages                           │
│ ~1K tokens                                   │
├─────────────────────────────────────────────┤
│ Layer 4: Session Summaries (V1)              │
│ - Last 5 compressed session summaries        │
│ ~500 tokens                                  │
├─────────────────────────────────────────────┤
│ Layer 5: Live Campaign Data (V1)             │
│ - Day-by-day metrics, keywords, search terms │
│ ~3K tokens                                   │
└─────────────────────────────────────────────┘

Total: ~10K tokens system prompt
```

### Layer 0: Marketing Intelligence Prompt

```
## Marketing Intelligence

**Campaign:** Portugal Golden Visa (23636342079)
**Objective:** Lead Generation (form submissions)
**Phase:** Optimization (stable data, 45 conversions in last 30 days)

### Phase Rules
- ✅ Safe to adjust bids and budgets
- ✅ Safe to add/remove keywords
- ✅ Safe to test new ad copy
- ⚠️ Bid strategy changes: proceed with caution (would reset learning)

### Active Alerts
- ⚠️ CPA spiked 35% this week ($18.50 vs $13.70 trailing avg)
  → Recommended: Review search terms for new irrelevant matches
- ℹ️ Search terms not reviewed in 9 days
  → Recommended: Run search term audit

### Account Context
- 3 active campaigns in this account
- Monthly spend: $8,400 across all campaigns
- Account-level goal: Maximize qualified leads for Golden Visa programs
- No budget conflicts detected between campaigns
```

### Confirmation Tiers

```python
# backend/app/services/agent.py

CONFIRMATION_TIERS = {
    # HIGH IMPACT: Always confirm
    "high": [
        "campaign_budget_update",      # Budget change > 20%
        "campaign_status_update",      # Pausing active campaign
        "bid_strategy_update",         # Changing bid strategy
        "campaign_create",             # Creating new campaign
        "campaign_delete",             # Removing campaign
    ],
    
    # MEDIUM IMPACT: Confirm by default, can be auto-approved
    "medium": [
        "keyword_add",                 # Adding keywords
        "keyword_status_update",       # Pausing keywords
        "ad_create",                   # Creating new ads
        "ad_update",                   # Editing ad copy
        "targeting_update",            # Location/language changes
    ],
    
    # LOW IMPACT: Auto-execute, notify user
    "low": [
        "negative_keyword_add",        # Adding negatives
        "search_term_exclude",         # Excluding search terms
        "guideline_update",            # Updating guidelines
        "label_add",                   # Adding labels
    ],
}
```

### Future: Gemini CLI Integration (Phase 3)

```python
# backend/app/services/agent.py — Future abstraction

class AIBackend:
    """Abstract interface for AI CLI backends."""
    
    async def stream(self, prompt: str, system_prompt: str, 
                     mcp_config: dict) -> AsyncIterator[AgentEvent]:
        raise NotImplementedError

class ClaudeCodeBackend(AIBackend):
    """Claude Code CLI subprocess backend."""
    
    async def stream(self, prompt, system_prompt, mcp_config):
        cmd = [str(_NODE_PATH), str(_CLI_JS), 
               "--output-format", "stream-json", ...]
        # ... existing implementation

class GeminiCLIBackend(AIBackend):
    """Gemini CLI subprocess backend (Phase 3)."""
    
    async def stream(self, prompt, system_prompt, mcp_config):
        cmd = [shutil.which("gemini"), "chat", "--stream", ...]
        # ... future implementation

def get_ai_backend(backend_name: str = "claude") -> AIBackend:
    backends = {
        "claude": ClaudeCodeBackend,
        "gemini": GeminiCLIBackend,
    }
    return backends[backend_name]()
```

---

## 10. Cross-Cutting Concerns

### Error Handling Hierarchy

```
User-facing errors (frontend toast/banner)
    ↑
API error responses (FastAPI exception handlers)
    ↑
Service-level exceptions
    ├─ GoogleAdsError (API quota, auth, invalid request)
    ├─ AgentError (CLI not found, subscription expired, timeout)
    ├─ CredentialError (encryption failure, missing credentials)
    ├─ OnboardingError (account scan failed, no campaigns)
    └─ GuidelineError (file not found, parse error)
```

### Caching Strategy (V2)

```python
# Cache keys now include account_id
CACHE_KEYS = {
    "campaigns": "{account_id}:campaigns",
    "campaign_detail": "{account_id}:{campaign_id}:detail",
    "keywords": "{account_id}:{campaign_id}:keywords",
    "search_terms": "{account_id}:{campaign_id}:search_terms",
    "account_health": "{account_id}:health",
    "dashboard": "dashboard:all",
}

# Different TTLs for different data types
CACHE_TTLS = {
    "campaigns": 300,        # 5 minutes (same as V1)
    "campaign_detail": 300,   # 5 minutes
    "keywords": 300,          # 5 minutes
    "search_terms": 3600,     # 1 hour (expensive query)
    "account_health": 600,    # 10 minutes
    "dashboard": 600,         # 10 minutes
}
```

### Security Model

```
┌─────────────────────────────────────────┐
│ Security Boundary: localhost only        │
│                                         │
│  Credentials:                           │
│  ├─ Encrypted in SQLite (Fernet)       │
│  ├─ .env file as fallback (V1 compat)  │
│  └─ Never logged, never in chat history │
│                                         │
│  Data isolation:                        │
│  ├─ Per-account in SQLite (FK)         │
│  ├─ Per-account on filesystem          │
│  └─ No cross-account data leakage      │
│                                         │
│  AI agent:                              │
│  ├─ Claude Code CLI (subscription)     │
│  ├─ No API key in app code             │
│  └─ MCP tools scoped to current acct   │
│                                         │
│  Network:                               │
│  ├─ 0.0.0.0:8000 (backend, local)     │
│  ├─ 0.0.0.0:5173 (frontend, local)    │
│  └─ Outbound only: Google Ads API      │
│                                         │
│  No telemetry by default (opt-in)       │
└─────────────────────────────────────────┘
```

### Performance Budget

| Operation | V1 | V2 Target | Strategy |
|-----------|-----|-----------|----------|
| App load | ~2s | < 2s | Code splitting, lazy routes |
| Account switch | N/A | < 1s | Pre-fetch account data on hover |
| Campaign list (1000 items) | N/A | < 500ms | Virtual scrolling (TanStack Table) |
| Dashboard (10 accounts) | N/A | < 3s | Parallel account queries, cached |
| Chart render | N/A | < 500ms | Recharts with memoization |
| Full-text search | N/A | < 200ms | SQLite FTS5 index |
| Smart onboarding | N/A | < 60s | Parallel campaign scans |

### CI Pipeline (V2 — Public Repo)

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd backend && uv sync
      - run: cd backend && uv run ruff check .
      - run: cd backend && uv run mypy app/
      - run: cd backend && uv run pytest

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npm run type-check
      - run: cd frontend && npm run build

  install-test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - run: bash install.sh
```

---

## 11. Shipped Delta Ledger (V2.1+, reconciled 2026-07-14)

§1–§10 above are the April 2026 V2 design and are kept as written. This
section is the as-built record of what landed on top of it (feature-log rows
2026-06-02 → 2026-07-14, Tier-2 reconcile). Sources of truth for the specs:
`research/chat-orchestration-v2-plan.md`, `research/dashboard-freshness-clarity-plan.md`,
`research/studio-redesign-plan.md`, `research/video-engine-plan.md`,
`research/agent-quality-hardening-plan.md`, PRD §8 Phases 1.5–1.7.

### 11.1 Migration ledger (schema now at V24)

The §5 schema shows the V2 baseline; migrations V3–V17 landed between April
and early July (notably: `campaigns` roster V11, `asset_groups` V12,
`workflow_reports` V15, `scheduled_plans` V17). The June–July delta
(verified against `backend/app/database.py`, `SCHEMA_VERSION = 24`):

| Version | Date | What |
|---------|------|------|
| V18 | 2026-06-11 | `ad_assets.prompt_hash` — Higgsfield clip cache key (zero-credit re-renders) |
| V19 | 2026-07-04 | `account_reports` — latest-wins UPSERT per account (Story 13.2 persistence; homepage reads local, never runs an audit on load) |
| V20 | 2026-07-04 | `finding_actions` — PK (account_id, finding_key); approve/deny decision state incl. deny tombstones that survive re-audits (Story 13.3) |
| V21 | 2026-07-12 | `sync_state` — per (account_id, domain) freshness ledger; UI truth keyed on `data_through_date`, NEVER `synced_at` (Dashboard v2.1 A2) |
| V22 | 2026-07-12 | `chat_turns` + `chat_turn_events` (append-only event log, `seq` = hub cursor) + `messages.turn_id` + `workflow_reports.origin` ('chat' vs 'workflow') — Chat Orchestration v2 turn runner |
| V23 | 2026-07-13 | `studio_video_projects` (storyboard source of truth — survives refresh/tab-close by design) + `brand_avatars` (Studio Redesign backend core) |
| V24 | 2026-07-14 | `studio_video_projects.brief_source` — Brief / From-campaign / From-landing-page draft sources |

### 11.2 New/changed services (beyond the §6 graph)

| Area | Service (backend/app/services/) | Role |
|------|--------------------------------|------|
| Chat v2 | `chat_runner.py` | Detached per-turn task + replay hub (`workflow_runner` pattern); turns survive client disconnects; cursor reconnect |
| Chat v2 | `chat_orchestrator.py` | Orchestrated-mode state machine: TRIAGE → RECALL → VERIFY → PLAN ≤3 specialists → DISPATCH → RESOLVE → SYNTHESIZE (Director-only voice) → GATE → WRITEBACK; $5/6-min budget with DEGRADE-to-synthesize |
| Chat v2 | `task_ledger.py` | Read-only recall over workflow_reports / scheduled_plan_runs / session_summaries / role_notes with the staleness matrix — recall-before-run |
| Chat v2 | `provenance.py` + `claim_gate.py` | Machine-readable source manifest (LIVE_API / PAGE_FETCH / LOCAL_STORE / MEMORY) + deterministic post-pass on Director finals: unverified IDs rewritten in place, material numbers flagged (derived-math guard), page claims traced to a real fetch. **The persisted message is the gated text.** |
| Chat v2 | `agent.py` (hardened) | `start_new_session` + process-group SIGTERM→SIGKILL stop; `_stop_requested` flag closes the continuation relaunch race; per-conversation proc registry holds SETS (stop reaches every parallel child); WS2–WS5 guardrails (live landing-page fetch, role-note staleness labels, ID integrity) |
| Account audit | `workflow_runner.py` | Detached workflow execution + `_RunHub` replay; SSE endpoint is a viewer, not the driver; zombie sweep on boot + periodic |
| Account audit | `account_report_store.py` · `fast_signals.py` · `finding_actions.py` | Report persistence (V19) · deterministic always-fresh signals (local rows only, no LLM, $-impact only where honest) · findings→approvable-actions mapping through the existing plans/scope-guard path (never a direct write) |
| Freshness | `sync_engine.py` (rewritten) · `freshness.py` · `external_change.py` · `account_events.py` | ONE read-only GAQL `search_stream` per account per sync (was ~3,300 ops); freshness envelope math; roster-diff external-change detection; SSE hub for `/accounts/{id}/events` push invalidation |
| Metrics | `metrics_store.py` (extended) | `GET /metrics/overview` period-over-period rollup (ENABLED-only, nulls-not-zeros honesty); as-of header for the agent |
| Studio | `model_catalog.py` · `higgsfield_scene.py` · `video_engine.py` | Server-side model catalog with per-model param contracts (Veo enum vs Kling int) + `plan_scenes` finished-video planner · prompt-hash clip cache + mezzanine normalize · segment timeline {storyboard\|higgsfield\|soul} compiled onto the premium_reel pipeline |
| Studio | `video_director.py` (+ `roles.py` entry, `prompt_drafter.py` staged drafting) | Model-aware Video Director turn: context → scoped campaign-Director consult (90s, DEGRADE-not-block) → decompose → 3 concepts → storyboard with server-side clamp/cap; cost/render OUTSIDE the LLM turn |
| PMax | `youtube_uploader.py` (+ `routers/pmax_video.py`, `routers/youtube.py`) | Storyboard-reel video step; one-time OAuth (token chmod 600, gitignored); resumable unlisted upload + metadata/thumbnails |

**Studio decoupling invariant (2026-06-11, standing):** studio services never
import `google_ads` code — campaign context flows in through props/params
only; Studio is a potential standalone product.

### 11.3 Transport & API additions

| Surface | Contract |
|---------|----------|
| Chat turn transport | `POST /conversations/{id}/message` → `{turn_id}` (legacy `?stream=1` = pre-v2 StreamingResponse passthrough); `GET /turns/{id}/stream?cursor=` SSE with replay; `GET /turns/{id}/events` history; per-turn and per-specialist stop endpoints. Orchestrated mode is per-conversation opt-in, default OFF — direct mode stays byte-identical |
| Account push | `GET /api/accounts/{id}/events` SSE (`sync_completed`, `external_change`) → frontend TanStack-Query invalidation hook |
| Homepage reads | `GET /api/accounts/{id}/account-report` (+freshness, +signals) · `/actions` + `/actions/{finding_key}/decide` · `/metrics/overview?days=` · `/outcomes` · `/external-changes` · campaign `/live-head` (60s TTL live control-plane read) |
| Studio/video | `/api/studio/models` · `/api/studio/auth-status` · `/api/video-engine/{estimate,render}` · `/api/studio/video-projects` CRUD + `/draft` · brand-avatars CRUD · `/api/pmax/video/{draft,render,metadata,frames}` · `/api/youtube/*` |
| MCP (stdio) | `google_ads/mcp_main.py` — 314 discovered tools after the 2026-07-05 hardening (keyword status flip, 4 ad-extension asset creators, fake-success stubs → honest errors); every mutate validated by the fail-closed dry-run harness (`dry_run.py` + `validate_all_tools.py`, `validate_only` forced at the SDK layer; 90 PASS / 0 FAIL / 147 SKIP) |
| MCP (HTTP bridge) | `app/mcp_server.py` — bearer-auth; 10 tools incl. the Epic-9 plan tools (create/list/approve/skip/run_now; money categories arrive approval-gated) |

### 11.4 Operational model (differs from the April assumptions)

| Concern | As-built |
|---------|----------|
| Backend process | macOS **launchd LaunchAgent** (KeepAlive auto-restart) — manage via `launchctl`, not nohup. `.py` changes and `.env` changes require a manual restart (no hot reload) |
| Frontend serving | `vite build` → the FastAPI backend serves the `dist/` bundle at `/`; a code fix isn't live until the bundle is rebuilt AND the browser hard-refreshes (a recurring gotcha — "serving-stale" verdicts are checked before debugging) |
| Default model | Claude CLI subprocess, default `claude-fable-5[1m]` since 2026-06-10 (plain `claude-fable-5` fallback; opus/sonnet/haiku aliases kept); native CLI binary preferred over npm cli.js at every spawn site (2026-06-11) |
| Design system | Shopify-calm light OKLCH token layer (`frontend/DESIGN.md`, 2026-06-02) — tokens only, never dark, no em-dashes in UI copy |
| Write safety | All homepage/agent writes route through Scheduled Plans (`scheduler.infer_mode` gating: budget/bids/status/geo approval-gated) + `CampaignScopeMiddleware`; account-wide audit runs force `tools=[]` (analysis-only by construction) |
| Test discipline | stdlib unittest, real temp SQLite via `init_db`, zero live LLM/Google calls; suite ~256 green as of 2026-07-14; frontend gates: `tsc --noEmit` 0 + `vite build` exit 0 |

---

*§1–§10 next step (historical): Epic breakdown with implementation stories for Phase 1.*
*§11 maintenance: extend this ledger at each Tier-2 reconcile (`_bmad-output/feature-log.md` discipline).*
