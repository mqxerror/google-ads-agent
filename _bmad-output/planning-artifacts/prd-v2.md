---
stepsCompleted: [01-init, 02-discovery, 03-success, 04-journeys, 05-domain, 06-innovation, 07-project-type, 08-scoping, 09-functional, 10-nonfunctional, 11-complete]
inputDocuments: [docs/prd.md, docs/architecture.md, docs/ux-design.md, docs/epics.md, _bmad-output/planning-artifacts/product-brief-v2.md]
workflowType: 'prd'
lastStep: 11
projectType: 'web_app'
domainComplexity: 'specialized'
track: 'bmad-method'
---

# Product Requirements Document - Google Ads Agent V2

**Author:** Wassim
**Date:** 2026-04-03
**Version:** 2.0
**Status:** Draft
**Previous Version:** docs/prd.md (V1)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project & Domain Classification](#2-project--domain-classification)
3. [Success Criteria](#3-success-criteria)
4. [User Journeys](#4-user-journeys)
5. [Domain Analysis](#5-domain-analysis)
6. [Innovation & Competitive Analysis](#6-innovation--competitive-analysis)
7. [Project Type Deep Dive](#7-project-type-deep-dive)
8. [Scoping & Phasing](#8-scoping--phasing)
9. [Functional Requirements](#9-functional-requirements)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Technical Architecture Summary](#11-technical-architecture-summary)

---

## 1. Executive Summary

### What Changed from V1

V1 was a personal tool for one user (Wassim) managing one account group (Mercan Group). V2 transforms this into an **open-source, AI-native Google Ads campaign manager** designed for digital marketing agencies, freelance PPC managers, and in-house marketing teams worldwide.

The core shift: **from "dashboard with a chatbot" to "Claude Code for Google Ads"** — an AI agent that thinks like a senior paid media strategist, can read AND write campaigns, understands marketing strategy at the account and campaign level, and works across any number of client accounts.

### Problem

Digital marketing agencies manage dozens of Google Ads accounts with no AI-native tooling. Existing solutions are either:
- **Manual** (Google Ads UI) — powerful but slow, no AI intelligence
- **Rules-based SaaS** (Optmyzr, Adalysis) — expensive ($200-800/mo), cloud-dependent, no conversational AI
- **Generic AI** (ChatGPT + API) — no campaign context, no persistent memory, no editing capabilities, requires API costs

No tool exists that combines **deep marketing intelligence + full campaign editing + persistent memory + local-first architecture + free/open-source**.

### Solution

Google Ads Agent V2: a locally-installed application where an AI agent powered by Claude Code CLI (or Gemini CLI) manages Google Ads campaigns with:

1. **Marketing Intelligence** — Understands account goals, campaign objectives, phases (launch/learning/scaling/sunset), seasonality, and best practices. Makes proactive recommendations.
2. **Full Editing** — Creates campaigns from briefs, edits bids/budgets/ads/keywords, manages search terms, executes bulk operations — like Claude Code edits code.
3. **Persistent Memory** — 5-layer context system (business context, campaign guidelines, recent history, session summaries, live data) that remembers everything across sessions.
4. **Multi-Account Scale** — Manages 100+ client accounts with per-account isolation, agency dashboard, and health monitoring.
5. **Zero Cost** — Uses existing Claude Code subscription. No API keys. No SaaS fees. 100% local.

### Target Users

| Segment | Size | Key Need |
|---------|------|----------|
| **Digital Marketing Agencies** (2-50 people) | Primary | Manage 10-100+ client accounts efficiently with AI |
| **Freelance PPC Managers** | Secondary | Efficiency multiplier for 3-15 accounts, can't afford SaaS tools |
| **In-house Marketing Teams** | Tertiary | AI-powered optimization without agency fees |
| **Wassim / Mercan Group** | Early adopter | Dog-fooding, validates multi-campaign workflows |

### Key Differentiator

**"Campaign Personality System"** — Editable per-campaign guidelines that become the AI's memory and judgment system. The agent knows each campaign's rules, goals, history, and constraints without being told. No other tool offers this.

---

## 2. Project & Domain Classification

| Attribute | V1 | V2 |
|-----------|-----|-----|
| **Project Type** | `web_app` (SPA) | `web_app` (SPA) — no change |
| **Domain** | Google Ads Management | Google Ads Management + Marketing Strategy |
| **Complexity** | Medium | High |
| **Classification** | Brownfield-adjacent | Brownfield upgrade |
| **Target Audience** | Single user | Public open-source |
| **BMAD Track** | BMad Method | BMad Method |

### Brownfield Context

V2 builds on the complete V1 codebase:
- **Existing:** Full React frontend, FastAPI backend, 87 MCP tools, 5-layer memory, guidelines system, SQLite database, campaign browser, streaming chat
- **Upgrade:** Marketing intelligence layer, multi-account support, enhanced editing, agency features, performance dashboards, onboarding system
- **Unchanged:** MCP server codebase (consumed as-is), Python/React tech stack, local-first architecture, Claude Code SDK integration

---

## 3. Success Criteria

### User Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily multi-account review | Review 10+ accounts in under 30 minutes | Time from app open to "all accounts checked" |
| Campaign context switch | Under 2 clicks to switch accounts + campaigns with full context | Account click → campaign click → guidelines + data loaded |
| Guideline violations | Zero AI-initiated guideline violations | Monitor agent actions against campaign rules |
| New account onboarding | Under 5 minutes from credentials to first AI conversation | Time from setup wizard start to first meaningful agent response |
| Agency adoption | 3+ agency teams using it in production within 6 months | Opt-in telemetry or community reports |

### Business Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time savings | 50%+ reduction in campaign management time vs manual workflow | A/B comparison of task completion times |
| GitHub adoption | 500+ stars within 3 months of public launch | GitHub star count |
| Active installations | 50+ within 6 months | Opt-in anonymous telemetry |
| Community contributions | 10+ community playbooks, 5+ PRs merged | GitHub activity tracking |

### Technical Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| App load time | < 2 seconds | Lighthouse / manual testing |
| AI first-token | < 1 second | SSE timestamp delta |
| Account scale | 100+ accounts without degradation | Performance testing with synthetic data |
| Install success rate | 95%+ on first attempt | Install script exit code tracking |
| Cross-platform | Works on macOS, Linux, Windows (WSL) | CI matrix testing |

### Phase Definitions

**Phase 1 — Foundation Upgrade (V2 MVP):**
User can install the app, connect multiple Google Ads accounts, get AI-powered marketing intelligence with goal awareness, edit campaigns through the agent, see performance dashboards, and search conversation history.

**Phase 2 — Agency Features:**
Agency dashboard across all accounts, shared playbooks, export/reporting, conversation templates, community playbook marketplace.

**Phase 3 — Ecosystem:**
Gemini CLI support, plugin system, custom MCP marketplace, mobile companion, API for external integrations.

---

## 4. User Journeys

### Journey 1: Agency Morning Review (Primary)

**Actor:** Agency Account Manager
**Frequency:** Daily
**Goal:** Review all client accounts and surface issues before the day starts

```
1. Open Google Ads Agent (localhost)
2. See agency dashboard: all connected accounts with health indicators
   - Client A: Spend on pace, conversions +12% WoW, no alerts
   - Client B: WARNING — CPA spiked 40%, budget 80% spent at noon
   - Client C: Healthy, but search terms need review (7 days since last audit)
3. Click Client B (the alert)
4. Agent auto-opens with context: "Client B's CPA spiked from $25 to $35 today.
   Root cause: 3 broad match keywords are matching irrelevant queries.
   Recommend adding these negative keywords: [list]. Shall I apply them?"
5. Review suggestions against Client B's guidelines (auto-loaded)
6. Approve: "Yes, add those negatives"
7. Agent executes, updates change log in guidelines
8. Click back to dashboard → Client C
9. Agent: "Search terms haven't been reviewed in 7 days. Starting audit..."
10. Agent surfaces 15 irrelevant terms with suggested negatives and match types
11. Approve in bulk → agent applies all, logs in guidelines
12. Dashboard shows all green. Morning review complete in 15 minutes.
```

### Journey 2: New Client Onboarding

**Actor:** Agency Owner / Account Manager
**Frequency:** Monthly
**Goal:** Connect a new client's Google Ads account and get the AI agent up to speed

```
1. Click "Add Account" in sidebar
2. Enter Google Ads credentials (dev token, OAuth, customer ID)
3. App validates and discovers account hierarchy
4. Smart onboarding begins:
   a. Agent scans all campaigns, ad groups, keywords, conversion actions
   b. Agent auto-generates initial campaign guidelines for each active campaign:
      - Detected goal: Lead Generation (based on conversion actions)
      - Detected phase: Optimization (based on campaign age + data volume)
      - Detected strategy: Target CPA at $30 (from bid strategy settings)
      - Key metrics summary: Last 30 days performance
      - Keyword structure overview
   c. Agent creates BUSINESS_CONTEXT.md with account summary
5. Review auto-generated guidelines: "These look good, but add a note that
   Client D has a strict $5000/month budget cap across all campaigns"
6. Agent updates guidelines with budget constraint
7. Account is ready — full AI context from day one
```

### Journey 3: Campaign Creation from Brief

**Actor:** Account Manager
**Frequency:** Weekly
**Goal:** Build a complete campaign from a marketing brief

```
1. Select client account
2. Open chat: "Create a new Search campaign for EB5 Investor Visa targeting
   US accredited investors. Budget $150/day, goal is lead gen via form fills.
   Landing page: mercan.com/eb5-program"
3. Agent thinks like a strategist:
   - "For EB5 targeting accredited investors, I recommend:
     - 3 ad groups: [Brand], [Intent-High], [Research]
     - Match types: Exact for brand, Phrase for high-intent, Broad for research
     - Bid strategy: Maximize Conversions (no tCPA initially, let it learn)
     - Negative keyword seed list: [informational terms, competitor brands]
     - RSA with 15 headlines and 4 descriptions per ad group
     
     Shall I build this out? I'll show you each component before executing."
4. User approves
5. Agent creates: campaign → ad groups → keywords → negative keywords → ads
6. Each step shown as tool calls with expandable details
7. Agent auto-generates campaign guidelines file
8. Agent: "Campaign created. I've set it to PAUSED so you can review before launch.
   Guidelines file created with all settings documented. Ready to enable?"
```

### Journey 4: Ad Copy Workshop

**Actor:** Account Manager / Copywriter
**Frequency:** Weekly
**Goal:** Optimize responsive search ad copy with AI assistance

```
1. Select campaign → ad group → view current ads
2. Open chat: "The CTR on Ad Group 'High Intent' is 3.2% but the account
   average is 5.1%. Help me improve the ad copy."
3. Agent analyzes:
   - Current headlines and their performance (if available)
   - Landing page content (via Chrome MCP if configured)
   - Competitor ads insights (from Auction Insights data)
   - Campaign guidelines (approved messaging, banned phrases)
4. Agent proposes new headlines with rationale:
   - "Current H1 'Golden Visa Portugal' — generic, no differentiator
     Proposed: 'Portugal Golden Visa — Fast-Track EU Residency'
     Why: Adds benefit (EU Residency) and urgency (Fast-Track)"
5. User iterates: "Make H3 more action-oriented"
6. Agent revises, user approves
7. Agent updates the RSA via API, logs change in guidelines
```

### Journey 5: Weekly Performance Report

**Actor:** Agency Account Manager
**Frequency:** Weekly
**Goal:** Generate a performance summary across accounts for internal or client use

```
1. Open agency dashboard
2. Click "Weekly Report" for Client A
3. Agent generates report:
   - Week-over-week metrics comparison
   - Top performing campaigns and ad groups
   - Budget pacing and forecast
   - Key changes made this week (from guidelines change logs)
   - Recommendations for next week
4. Report displayed in formatted view
5. Export to CSV or copy as markdown for client email
```

### Journey 6: Search Term Deep Dive

**Actor:** Account Manager
**Frequency:** Weekly
**Goal:** Audit search terms and manage negative keywords systematically

```
1. Select campaign
2. Click "Search Terms" tab or ask agent: "Audit search terms for last 7 days"
3. Agent fetches search terms with metrics
4. Agent categorizes automatically:
   - HIGH VALUE: Converting terms not yet added as keywords
   - IRRELEVANT: Terms that should be negated (with suggested match type)
   - MONITOR: Borderline terms that need more data
5. Table view with agent's recommendations inline
6. Select negatives to add → choose match type → one-click apply
7. Agent logs all changes to guidelines
```

### Journey 7: First-Time Setup (New User)

**Actor:** Any new user
**Frequency:** Once
**Goal:** Install and configure Google Ads Agent from scratch

```
1. Clone repo and run: bash install.sh
   - Script auto-installs Node.js (via nvm), uv, dependencies
   - No manual prerequisite installation needed
2. Run: bash start.sh
3. Browser opens to localhost:5173
4. Setup wizard:
   a. Enter Google Ads credentials (with link to documentation on how to get them)
   b. App validates credentials, discovers accounts
   c. Select which accounts to manage
   d. Smart onboarding runs: auto-scans campaigns, generates initial guidelines
5. Main app loads with:
   - Sidebar showing account hierarchy
   - Dashboard with campaign overview
   - Chat panel ready with full context
6. First interaction: Agent greets user with account summary
   "Welcome! I've analyzed your account. You have 5 active campaigns
    across 2 accounts. Here's what I noticed:
    - Campaign X has high CPA ($45 vs target $30) — want me to investigate?
    - Campaign Y's search terms haven't been reviewed in 14 days
    - All conversion tracking appears healthy"
```

### Journey 8: Bulk Operations

**Actor:** Account Manager
**Frequency:** As needed
**Goal:** Make changes across multiple campaigns or ad groups at once

```
1. Open chat: "Pause all campaigns with CPA above $50 across Client A's account"
2. Agent queries all campaigns, filters by CPA > $50
3. Agent shows list: "Found 3 campaigns:
   - Campaign X: CPA $62
   - Campaign Y: CPA $55
   - Campaign Z: CPA $51
   Pause all three?"
4. User confirms
5. Agent pauses all three, logs in each campaign's guidelines
6. Or via UI: select multiple campaigns → right-click → "Pause selected"
```

### Journey 9: Goal-Aware Strategy Adjustment

**Actor:** Senior Strategist
**Frequency:** Monthly
**Goal:** Adjust account strategy based on business goals

```
1. Select client account
2. Open chat: "The client wants to shift from lead volume to lead quality.
   They only want leads from accredited investors (net worth $1M+).
   Adjust the account strategy."
3. Agent understands the goal shift and proposes:
   - "I recommend the following strategic changes:
     1. Switch bid strategy from Max Conversions to Target CPA ($75)
     2. Tighten keyword match types (remove broad, add more exact)
     3. Add income-related negatives (free, cheap, affordable)
     4. Update ad copy to emphasize 'accredited investors' qualification
     5. Adjust location targeting to high-income zip codes
     
     WARNING: Campaigns PGV-1 and PGV-2 are in learning phase.
     Per guidelines, bid strategy changes should wait 7 more days.
     I'll queue those changes and execute on [date]."
4. User approves the phased approach
5. Agent executes immediate changes, schedules deferred ones
6. Agent updates account-level business context and all campaign guidelines
```

---

## 5. Domain Analysis

### Google Ads API Landscape

The Google Ads API v23 (SDK v29.2.0) remains the primary data source. The existing MCP server provides 87 of 103 possible services (84.5% coverage).

**Service categories:** Account (11), Campaign (17), Ad Groups (15), Audiences (10), Bidding (5), Conversions (11), Assets (10), Planning (9), Data Import (5), Metadata (3), Product Integration (5), Shared Resources (4).

### Marketing Intelligence Domain Model

V2 introduces a structured marketing knowledge layer that V1 lacked:

```
Account
├── Business Context
│   ├── Industry / Vertical
│   ├── Business Model (lead gen, e-commerce, brand, local)
│   ├── Budget Constraints (monthly cap, pacing rules)
│   └── Key Performance Indicators (target CPA, ROAS, volume)
│
├── Campaign Strategy
│   ├── Objective (conversions, traffic, awareness, engagement)
│   ├── Phase (launch, learning, optimization, scaling, sunset)
│   ├── Phase Rules (e.g., "don't change bid strategy during learning")
│   ├── Target Metrics (CPA, ROAS, impression share)
│   ├── Audience Definition (demographics, intent signals)
│   └── Competitive Position (auction insights, market share)
│
├── Campaign Guidelines (existing V1 system, enhanced)
│   ├── Global Rules (change management, bidding policy, conversion tracking)
│   ├── Per-Campaign Sections (overview, ad groups, keywords, negatives, history)
│   ├── Change Log (auto-populated by agent)
│   └── Playbook Reference (which playbook template was used)
│
└── Marketing Calendar
    ├── Seasonal Events (Black Friday, New Year, industry events)
    ├── Promotional Periods (sales, launches, deadlines)
    └── Review Cadence (daily/weekly/monthly tasks)
```

### Campaign Phase Detection

The agent automatically determines campaign phase from live data:

| Phase | Detection Signal | Agent Behavior |
|-------|-----------------|----------------|
| **Launch** | Campaign age < 14 days, limited conversion data | Conservative: don't change bid strategy, gather data, optimize keywords |
| **Learning** | Bid strategy recently changed, < 30 conversions in lookback | Hands-off: monitor only, warn against changes, track learning progress |
| **Optimization** | Stable data, clear performance patterns | Active: suggest bid adjustments, keyword refinement, ad copy tests |
| **Scaling** | CPA below target, budget not fully spent | Growth: recommend budget increases, new keywords, audience expansion |
| **Sunset** | Declining performance, no strategic fit | Careful: recommend reducing budget or pausing, document learnings |

### Multi-Account Architecture

```
Installation (single machine)
├── Account A (Client)
│   ├── Credentials (.env or encrypted DB)
│   ├── Campaigns + Live Data
│   ├── Guidelines (filesystem)
│   ├── Conversations (SQLite)
│   └── Session Summaries
│
├── Account B (Client)
│   ├── ... (fully isolated)
│
└── Agency Dashboard
    ├── All-account health overview
    ├── Alert aggregation
    └── Cross-account metrics
```

### Playbook System

Community-shareable campaign strategy templates:

| Playbook | Use Case | Contents |
|----------|----------|----------|
| **Lead Gen — Professional Services** | Law firms, consulting, agencies | Campaign structure, keyword strategy, landing page guidelines, CPA targets |
| **E-commerce — Product Feed** | Shopping campaigns, product-based | Feed optimization, ROAS targets, seasonal adjustments |
| **Local Services** | Plumbers, dentists, contractors | Location targeting, call tracking, local keyword patterns |
| **SaaS / Software** | Free trial, demo request funnels | Long-tail keywords, competitor targeting, value prop framework |
| **Real Estate / Investment** | Immigration, property, financial | High-value lead qualification, compliance-sensitive ad copy |
| **Brand Awareness** | Display, YouTube, Discovery | Reach optimization, frequency capping, audience building |

---

## 6. Innovation & Competitive Analysis

### V2 Innovations Beyond V1

**1. Marketing Intelligence Layer**

V1 had a "campaign personality" system (guidelines as AI context). V2 adds genuine marketing reasoning:
- **Goal-aware decisions** — Agent knows the account's business model and each campaign's objective. It won't optimize for clicks when the goal is conversions.
- **Phase-aware behavior** — Agent detects campaign phase and adapts. Won't suggest bid changes during learning phase.
- **Cross-campaign reasoning** — Identifies budget cannibalization, audience overlap, attribution conflicts.
- **Proactive surfacing** — Doesn't wait to be asked. On morning review, surfaces: "CPA spiked 40% on Campaign X — here's why and what to do."

**2. Full Editing (Claude Code for Google Ads)**

V1 had basic operations (pause/enable, budget, keywords). V2 enables the agent to build and modify campaigns end-to-end:
- Create complete campaigns from a brief (structure, ad groups, keywords, ads, targeting, bidding)
- Edit any campaign element through natural language
- Bulk operations across campaigns
- Ad copy workshop with iterative refinement
- Smart safeguards (confirmation tiers based on impact level)

**3. Smart Onboarding**

V1 required manual guidelines creation. V2 auto-generates them:
- Scans account structure on first connect
- Detects campaign goals from conversion actions and bid strategies
- Identifies campaign phases from age and data volume
- Generates initial guidelines with detected settings
- Creates business context document from account analysis

**4. Agency Scale**

V1 was single-account. V2 supports agency workflows:
- Multi-account dashboard with health indicators
- Per-account isolation (credentials, data, guidelines, conversations)
- Cross-account alerting (budget pacing, CPA spikes, conversion drops)
- Shared playbook system for consistent campaign management

**5. Community Playbooks**

Open-source templates that encode marketing best practices:
- Pre-built campaign structures for common verticals
- Keyword research starting points
- Ad copy frameworks
- Bidding strategy recommendations by objective
- Negative keyword seed lists

### Competitive Landscape

| Feature | Google Ads UI | Optmyzr ($208-832/mo) | Adalysis ($149-499/mo) | Generic AI + API | **Google Ads Agent V2** |
|---------|:---:|:---:|:---:|:---:|:---:|
| Campaign browsing | Yes | Yes | Yes | No | **Yes** |
| AI analysis | Limited recs | Rules-based | Rules-based | Generic, no context | **Deep, goal-aware** |
| Campaign editing | Manual UI | Rules-based | Rules-based | No | **AI + UI, full lifecycle** |
| Marketing intelligence | No | Partial | Partial | Generic | **Deep, structured** |
| Campaign memory | No | Config only | No | No | **5-layer persistent** |
| Goal / phase awareness | No | Manual config | No | No | **Auto-detected** |
| Multi-account | Yes (MCC) | Yes | Yes | No | **Yes, with dashboard** |
| Bulk operations | Yes | Yes | Yes | No | **Yes (AI + UI)** |
| Ad copy optimization | Manual | Templates | Suggestions | Generic | **Workshop with iteration** |
| Search term management | Yes | Yes | Yes | No | **AI-categorized + one-click** |
| Playbook templates | No | Partial | No | No | **Community-driven** |
| Smart onboarding | No | No | No | No | **Auto-generated guidelines** |
| Cost | Free | $208-832/mo | $149-499/mo | $20+/mo API | **Free** |
| Data privacy | Google cloud | Third-party cloud | Third-party cloud | Third-party cloud | **100% local** |
| Open source | No | No | No | No | **Yes (MIT)** |
| Extensible | No | No | No | No | **87+ MCP tools** |

---

## 7. Project Type Deep Dive

### Application Type: Single Page Application (SPA) — Local Install

| Attribute | Decision | Rationale |
|-----------|----------|-----------|
| **Rendering** | Client-side SPA | Local tool, no SSR/SEO needed (even for public release — users install locally) |
| **Framework** | React 19 + TypeScript 5.9 | Keep V1 stack, mature ecosystem, rich component libraries |
| **Build Tool** | Vite 8 | Fast HMR, proven in V1 |
| **Styling** | Tailwind CSS 4 + shadcn/ui | Keep V1 stack, utility-first, accessible components |
| **State** | Zustand 5 (global) + TanStack Query 5 (server) | Keep V1 stack, proven patterns |
| **Backend** | Python FastAPI | Keep V1 stack, Google Ads SDK is Python-native, MCP server is Python |
| **Database** | SQLite (aiosqlite) | Keep V1 stack, zero-config, local-first |
| **AI Runtime** | Claude Code SDK (Python) | Keep V1 stack, CLI subscription model |
| **Charts** | Recharts or Tremor | New: needed for performance dashboards |
| **Tables** | TanStack Table | New: needed for bulk operations, better data display |

### Performance Targets

| Metric | V1 Target | V2 Target | Notes |
|--------|-----------|-----------|-------|
| Initial load | < 2s | < 2s | Same |
| Route navigation | < 500ms | < 300ms | Faster for multi-account switching |
| Campaign list render | < 500ms | < 500ms (1000+ campaigns) | Must handle agency-scale lists |
| AI first-token | < 1s | < 1s | Same |
| AI stream throughput | 50+ tok/s | 50+ tok/s | Same |
| Account switch | N/A | < 1s | New: full context reload |
| Dashboard load (all accounts) | N/A | < 3s | New: aggregate metrics |
| Smart onboarding | N/A | < 60s | New: initial account scan |
| Chart rendering | N/A | < 500ms | New: performance dashboards |

### Browser Matrix

| Browser | Support Level |
|---------|---------------|
| Chrome Latest 2 | Full (required for Chrome MCP) |
| Edge Latest 2 | Full |
| Firefox Latest 2 | Full |
| Safari Latest | Best-effort |

### Platform Matrix

| Platform | Support Level |
|----------|---------------|
| macOS (Apple Silicon + Intel) | Full |
| Linux (Ubuntu 22+, Debian 12+) | Full |
| Windows 10+ (native + WSL) | Full |

---

## 8. Scoping & Phasing

### Phase 1: Foundation Upgrade (V2 MVP)

**Goal:** Transform the personal tool into a public-ready, agency-capable campaign manager with marketing intelligence.

| Feature | Description | Priority |
|---------|-------------|----------|
| Marketing Intelligence Layer | Goal awareness, phase detection, proactive recommendations | P0 |
| Smart Onboarding | Auto-scan accounts, generate initial guidelines, detect campaign phases | P0 |
| Performance Dashboards | Charts for metrics over time, WoW comparison, anomaly highlighting | P0 |
| Enhanced Campaign Editing | Create campaigns from briefs, bulk keyword management, ad copy workshop | P0 |
| Multi-Account Support | Account switcher, per-account data isolation, credentials management | P0 |
| Conversation History + Search | Persist all conversations, full-text search, campaign tagging | P0 |
| Search Term Manager | AI-categorized terms, one-click negatives, audit tracking | P0 |
| Agency Dashboard | All-account overview with health indicators and alerts | P1 |
| Bulk Operations | Multi-campaign/ad-group actions (pause, budget adjust, keyword changes) | P1 |
| Cross-Platform Polish | Verified install scripts for macOS, Linux, Windows | P0 |
| Public Repo Preparation | README, contributing guide, issue templates, CI | P0 |

**Out of scope for Phase 1:**
- Gemini CLI support
- Community playbook marketplace
- Mobile companion
- Plugin system
- Client-facing reports with branding

### Phase 2: Agency Features

**Goal:** Full agency workflow support with team knowledge sharing and client reporting.

| Feature | Description | Priority |
|---------|-------------|----------|
| Shared Playbooks | Create, install, and share campaign strategy templates | P1 |
| Export & Reporting | CSV export, PDF summaries, change logs for client reporting | P1 |
| Conversation Templates | Pre-built prompts: "daily review", "weekly report", "search term audit" | P1 |
| Auto Change Logging | Agent auto-logs all changes to campaign guidelines with timestamps | P1 |
| Marketing Calendar | Seasonal events, promotional periods, review cadence tracking | P2 |
| Impression Share Metrics | Lost IS by rank/budget, competitive positioning | P2 |
| Change History (Google Ads) | Pull change history from Google Ads API change events | P2 |

### Phase 3: Ecosystem

**Goal:** Expand the tool's reach with alternative AI backends, extensibility, and community features.

| Feature | Description | Priority |
|---------|-------------|----------|
| Gemini CLI Support | Alternative AI backend for Google ecosystem users | P2 |
| Plugin System | Custom workflow plugins for agency-specific needs | P3 |
| Custom MCP Tools | Marketplace for community-built MCP tools | P3 |
| Community Playbook Portal | Web-based sharing of playbook templates | P3 |
| Mobile Companion | Read-only dashboard for on-the-go monitoring | P3 |
| External API | REST API for external integrations (Slack alerts, custom dashboards) | P3 |

### Explicit Non-Goals (All Phases)

- Cloud/SaaS deployment (stays local-first forever)
- Automated bidding algorithms (use Google's native strategies)
- Landing page builder (agent can audit pages, not build them)
- Full GTM replacement (agent uses browser for specific GTM tasks)
- Social media ads (Google Ads only — scope may expand later)
- Direct Anthropic API usage (CLI subscription only, unless user explicitly wants API)

---

## 9. Functional Requirements

### FR Group 1: Account Management

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR1.1 | Setup wizard for Google Ads API credentials with step-by-step documentation links | Phase 1 | Enhanced |
| FR1.2 | Validate credentials by querying accessible accounts | Phase 1 | V1 |
| FR1.3 | Display account hierarchy as navigable tree (Manager → Sub-Manager → Client) | Phase 1 | V1 |
| FR1.4 | Switch between client accounts within a session without re-authenticating | Phase 1 | V1 |
| FR1.5 | Store account configurations in local SQLite with credential encryption | Phase 1 | V1 |
| FR1.6 | Detect and handle expired OAuth refresh tokens with re-auth flow | Phase 1 | V1 |
| FR1.7 | **Support multiple MCC accounts** (agencies with multiple manager accounts) | Phase 1 | **New** |
| FR1.8 | **Per-account data isolation** (guidelines, conversations, summaries in separate namespaces) | Phase 1 | **New** |
| FR1.9 | **Account health indicators** (spend pacing, CPA trend, conversion health) on account list | Phase 1 | **New** |
| FR1.10 | **Smart onboarding**: auto-scan new account, detect campaign goals/phases, generate initial guidelines | Phase 1 | **New** |
| FR1.11 | **Account removal** with cleanup of associated data (guidelines, conversations, cache) | Phase 1 | **New** |

### FR Group 2: Campaign Browsing

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR2.1 | Display all campaigns in sortable, filterable list with inline metrics | Phase 1 | V1 |
| FR2.2 | Show metrics: impressions, clicks, conversions, cost, CPA, CTR, ROAS for selectable date range | Phase 1 | Enhanced |
| FR2.3 | Drill into campaign → ad groups → keywords/ads tree view | Phase 1 | V1 |
| FR2.4 | Display keywords with quality score, match type, status, metrics | Phase 1 | V1 |
| FR2.5 | Filter campaigns by status, name, type, performance thresholds | Phase 1 | Enhanced |
| FR2.6 | Show campaign settings (bidding, budget, targeting, conversions) in detail panel | Phase 1 | V1 |
| FR2.7 | **Performance charts**: line charts for metrics over time (7d, 14d, 30d, 90d, custom) | Phase 1 | **New** |
| FR2.8 | **Period comparison**: compare current vs previous period with delta indicators | Phase 1 | **New** |
| FR2.9 | **Anomaly highlighting**: visually flag metrics that deviate >20% from trailing average | Phase 1 | **New** |
| FR2.10 | **Campaign phase badge**: display detected phase (Launch/Learning/Optimization/Scaling/Sunset) | Phase 1 | **New** |
| FR2.11 | **Virtual scrolling** for campaign/keyword lists with 1000+ items | Phase 1 | **New** |

### FR Group 3: AI Agent Chat

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR3.1 | Streaming chat with real-time AI responses via SSE | Phase 1 | V1 |
| FR3.2 | Agent powered by Claude Code SDK with Google Ads MCP server | Phase 1 | V1 |
| FR3.3 | Auto-load campaign guidelines into AI context when campaign selected | Phase 1 | V1 |
| FR3.4 | Auto-load global rules + business context into AI context | Phase 1 | V1 |
| FR3.5 | All 87+ MCP tools accessible to agent | Phase 1 | V1 |
| FR3.6 | Tool invocation transparency with expandable details | Phase 1 | V1 |
| FR3.7 | **Tiered confirmation**: high-impact changes require explicit approval, low-impact auto-execute with notification | Phase 1 | **Enhanced** |
| FR3.8 | **Persist conversation history** in SQLite with campaign/account tagging | Phase 1 | **Promoted from Growth** |
| FR3.9 | **Multiple conversation threads** per campaign | Phase 1 | **Promoted from Growth** |
| FR3.10 | **Full-text search** across conversation history | Phase 1 | **Promoted from Growth** |
| FR3.11 | **Marketing intelligence in system prompt**: goal awareness, phase detection, best practices engine | Phase 1 | **New** |
| FR3.12 | **Proactive recommendations**: agent surfaces issues without being asked during daily review | Phase 1 | **New** |
| FR3.13 | **Cross-campaign reasoning**: agent can compare campaigns, detect cannibalization, suggest budget reallocation | Phase 1 | **New** |
| FR3.14 | **Model selector**: Claude Sonnet (fast), Opus (deep), Haiku (cheap) | Phase 1 | V1 |
| FR3.15 | **Conversation templates**: pre-built prompt sequences for common tasks (daily review, search term audit) | Phase 2 | **New** |
| FR3.16 | **Gemini CLI support**: alternative AI backend option | Phase 3 | **New** |

### FR Group 4: Campaign Guidelines Management

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR4.1 | Display guidelines in formatted markdown view | Phase 1 | V1 |
| FR4.2 | Markdown editor with syntax highlighting and preview | Phase 1 | V1 |
| FR4.3 | Guidelines stored as .md files, backward-compatible with V1 format | Phase 1 | V1 |
| FR4.4 | Support existing structure (Global Rules, Per-Campaign sections) | Phase 1 | V1 |
| FR4.5 | Create guidelines from template for new campaigns | Phase 1 | V1 |
| FR4.6 | Auto-save with debounce, changes reflected in AI context immediately | Phase 1 | V1 |
| FR4.7 | **Auto-generated guidelines** from smart onboarding scan | Phase 1 | **New** |
| FR4.8 | **Campaign goal field** in guidelines (lead gen, e-commerce, brand, etc.) with structured format | Phase 1 | **New** |
| FR4.9 | **Campaign phase field** in guidelines (auto-detected, manually overridable) | Phase 1 | **New** |
| FR4.10 | **Auto change logging**: agent appends to Change Log section after every modification | Phase 2 | **New** |
| FR4.11 | **Playbook integration**: apply a community playbook template to generate campaign guidelines | Phase 2 | **New** |

### FR Group 5: Campaign Operations (Editing)

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR5.1 | **Create campaigns from natural language brief** (full structure: ad groups, keywords, ads, targeting, bidding) | Phase 1 | **Enhanced** |
| FR5.2 | Modify campaign settings (budget, bidding, status) via AI or UI | Phase 1 | V1 |
| FR5.3 | Manage keywords (add, pause, change match type) via AI or UI | Phase 1 | V1 |
| FR5.4 | Create and manage responsive search ads via AI | Phase 1 | V1 |
| FR5.5 | **Search term manager**: AI-categorized terms (high-value, irrelevant, monitor) with one-click negative application | Phase 1 | **New** |
| FR5.6 | **Ad copy workshop**: generate, compare, iterate on RSA headlines/descriptions with marketing frameworks | Phase 1 | **New** |
| FR5.7 | **Bulk operations**: pause/enable/delete multiple campaigns, adjust bids across ad groups, bulk negative keywords | Phase 1 | **New** |
| FR5.8 | **Smart safeguards**: warn on high-impact changes (budget >20%, bid strategy change, pausing active campaigns) | Phase 1 | **Enhanced** |
| FR5.9 | Guideline-aware enforcement: agent checks rules before executing changes | Phase 1 | V1 Enhanced |
| FR5.10 | Conversion action management and tracking status | Phase 2 | V1 Growth |
| FR5.11 | **Scheduled changes**: queue changes for future execution (e.g., "change bid strategy after learning phase ends") | Phase 2 | **New** |

### FR Group 6: Data Display & Reporting

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR6.1 | Campaign performance overview with date range selector (today, 7d, 14d, 30d, 90d, custom) | Phase 1 | V1 Enhanced |
| FR6.2 | **Performance charts**: line/bar charts for spend, clicks, conversions, CPA over time | Phase 1 | **New** |
| FR6.3 | **Week-over-week comparison** with delta indicators (green/red) | Phase 1 | **New** |
| FR6.4 | **Agency dashboard**: all-account grid with health indicators, spend pacing, alert badges | Phase 1 | **New** |
| FR6.5 | **Conversion tracking status** per campaign with health indicator | Phase 2 | V1 Growth |
| FR6.6 | **Impression share metrics** and competitive positioning | Phase 2 | V1 Growth |
| FR6.7 | **Change history** from Google Ads API change events | Phase 2 | V1 Growth |
| FR6.8 | **Export to CSV** (campaigns, keywords, search terms, performance data) | Phase 2 | V1 Growth |
| FR6.9 | **PDF/Markdown report generation** for client-facing summaries | Phase 2 | **New** |

### FR Group 7: Browser Automation (Chrome MCP)

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR7.1 | Chrome MCP integration for browser-based tasks (GTM, landing pages) | Phase 1 | V1 |
| FR7.2 | Agent navigates to external web UIs for beyond-API tasks | Phase 1 | V1 |
| FR7.3 | Browser actions displayed with distinct browser icon in chat | Phase 1 | V1 |
| FR7.4 | Agent intelligently decides API vs browser tools per task | Phase 1 | V1 |
| FR7.5 | Graceful fallback to API-only when Chrome unavailable | Phase 1 | V1 |
| FR7.6 | Setup wizard includes optional Chrome MCP configuration | Phase 1 | V1 |
| FR7.7 | **Landing page analysis**: check tracking tags, form functionality, page speed | Phase 1 | **Enhanced** |

### FR Group 8: Community & Sharing

| ID | Requirement | Phase | Delta |
|----|-------------|-------|-------|
| FR8.1 | **Playbook templates**: bundled set of campaign strategy templates by vertical | Phase 2 | **New** |
| FR8.2 | **Import/export playbooks**: share as JSON/YAML bundles | Phase 2 | **New** |
| FR8.3 | **Community playbook portal**: browse and install community-contributed templates | Phase 3 | **New** |
| FR8.4 | **Contributing guide**: documentation for community contributors | Phase 1 | **New** |

---

## 10. Non-Functional Requirements

### Performance

| ID | Requirement | Target | Delta |
|----|-------------|--------|-------|
| NFR-P1 | Application initial load | < 2 seconds | Same |
| NFR-P2 | Route navigation | < 300ms | Tighter |
| NFR-P3 | Campaign list render (1000+ campaigns) | < 500ms | Higher scale |
| NFR-P4 | Google Ads API data fetch | < 3 seconds | Same |
| NFR-P5 | AI first-token latency | < 1 second | Same |
| NFR-P6 | AI streaming throughput | 50+ tok/s | Same |
| NFR-P7 | Account switch (full context reload) | < 1 second | **New** |
| NFR-P8 | Dashboard load (all accounts) | < 3 seconds | **New** |
| NFR-P9 | Smart onboarding scan | < 60 seconds per account | **New** |
| NFR-P10 | Chart rendering | < 500ms | **New** |
| NFR-P11 | Cache TTL | 5 minutes (configurable) | Same |

### Security

| ID | Requirement | Delta |
|----|-------------|-------|
| NFR-S1 | Credentials encrypted in SQLite or OS keychain | Same |
| NFR-S2 | No data transmitted beyond Google Ads API and Claude/Gemini CLI | Enhanced |
| NFR-S3 | Localhost-only endpoints | Same |
| NFR-S4 | No credentials in logs or conversation history | Same |
| NFR-S5 | SQLite file permissions (owner-only) | Same |
| NFR-S6 | **Per-account credential isolation** (no cross-account credential leakage) | **New** |
| NFR-S7 | **No telemetry by default** (opt-in only, anonymous, no PII) | **New** |

### Integration

| ID | Requirement | Delta |
|----|-------------|-------|
| NFR-I1 | Google Ads MCP server via Claude Code SDK | Same |
| NFR-I2 | Direct GoogleAdsSdkClient for read-only queries | Same |
| NFR-I3 | Filesystem guidelines in existing markdown format | Same |
| NFR-I4 | Claude Code CLI as primary AI runtime | Same |
| NFR-I5 | .env file format for credentials | Same |
| NFR-I6 | Chrome MCP as optional second MCP server | Same |
| NFR-I7 | Chrome MCP optional (graceful fallback) | Same |
| NFR-I8 | **Gemini CLI as alternative AI runtime** | **New (Phase 3)** |

### Reliability

| ID | Requirement | Delta |
|----|-------------|-------|
| NFR-R1 | Graceful Google Ads API error handling with clear messages | Same |
| NFR-R2 | OAuth token expiry detection with re-auth flow | Same |
| NFR-R3 | Conversation state recovery after restart | Same |
| NFR-R4 | Guidelines auto-save with debounce | Same |
| NFR-R5 | Claude Code SDK connection failure recovery | Same |
| NFR-R6 | **Account switching preserves unsaved work** (warn before switching with changes) | **New** |
| NFR-R7 | **Cross-platform reliability** (verified on macOS, Linux, Windows) | **New** |

### Maintainability

| ID | Requirement | Delta |
|----|-------------|-------|
| NFR-M1 | Clean frontend/backend separation with API contract | Same |
| NFR-M2 | New MCP tools auto-available without app changes | Same |
| NFR-M3 | Guidelines format backward-compatible | Same |
| NFR-M4 | Single configuration location (SQLite + .env) | Same |
| NFR-M5 | **Contributing guide and code style documentation** | **New** |
| NFR-M6 | **CI pipeline**: lint, type-check, test on PR | **New** |
| NFR-M7 | **Semantic versioning** for public releases | **New** |

---

## 11. Technical Architecture Summary

### System Overview

```
+----------------------------------------------------+
|            React SPA (Vite 8)                       |
|  +----------+ +---------+ +-------------------+    |
|  | Campaign | | Chat    | | Agency Dashboard  |    |
|  | Browser  | | Panel   | | + Charts          |    |
|  +----+-----+ +----+----+ +--------+----------+    |
|       |             |               |               |
+-------+-------------+---------------+--------------+
        |             |               |
   REST API      SSE Stream     REST API
        |             |               |
+-------+-------------+---------------+--------------+
|          Python FastAPI Backend                      |
|  +----------+ +------------------+ +--------------+ |
|  | Data API | | Agent Service    | | Marketing    | |
|  | (direct) | | (Claude Code SDK)| | Intelligence | |
|  +----+-----+ +--------+---------+ +------+-------+ |
|       |                 |                  |         |
+-------+-----------------+------------------+---------+
        |                 |                  |
        v                 v                  v
  Google Ads API    Claude Code CLI    SQLite + Files
  (via sdk_client)  + MCP Servers:     (guidelines,
                      ├─ google-ads    conversations,
                      │  (87 tools)    summaries,
                      └─ chrome-mcp    account data)
                         (optional)
```

### What Changes from V1

| Component | V1 | V2 |
|-----------|-----|-----|
| **Frontend** | 3-panel layout (sidebar + content + chat) | + agency dashboard, + charts, + search term manager, + bulk ops UI |
| **Backend** | 5 routers, 27 endpoints | + dashboard router, + onboarding service, + marketing intelligence service |
| **Database** | Single namespace | Per-account partitioning (account_id foreign key on all tables) |
| **Agent** | 5-layer memory, reactive | + marketing intelligence in system prompt, + proactive mode, + cross-campaign reasoning |
| **Guidelines** | Manual creation, plain markdown | + auto-generated, + structured goal/phase fields, + auto change logging |
| **Config** | Single .env | Multiple account credentials, per-account .env or encrypted DB |
| **Install** | Works on macOS/Linux/Windows | + verified CI matrix, + one-command including prerequisites |

### New Backend Services

| Service | Purpose |
|---------|---------|
| `MarketingIntelligenceService` | Goal detection, phase detection, proactive recommendation engine |
| `OnboardingService` | Account scan, guideline generation, campaign analysis |
| `DashboardService` | Aggregate metrics across accounts, health scoring, alerts |
| `SearchTermService` | AI-powered categorization, negative keyword suggestions |
| `BulkOperationsService` | Multi-entity operations with preview and confirmation |
| `ExportService` | CSV/PDF generation for reports |

### Data Model Changes

```sql
-- V2: Account isolation
ALTER TABLE conversations ADD COLUMN account_id TEXT;
ALTER TABLE messages ADD COLUMN account_id TEXT;
ALTER TABLE session_summaries ADD COLUMN account_id TEXT;
ALTER TABLE cache ADD COLUMN account_id TEXT;

-- V2: New tables
CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  name TEXT,
  mcc_id TEXT,
  credentials_encrypted TEXT,
  created_at TIMESTAMP,
  last_synced TIMESTAMP
);

CREATE TABLE campaign_goals (
  campaign_id TEXT PRIMARY KEY,
  account_id TEXT,
  objective TEXT,        -- lead_gen, ecommerce, brand, local
  phase TEXT,            -- launch, learning, optimization, scaling, sunset
  phase_detected_at TIMESTAMP,
  target_cpa REAL,
  target_roas REAL,
  monthly_budget_cap REAL,
  notes TEXT
);

CREATE TABLE alerts (
  id INTEGER PRIMARY KEY,
  account_id TEXT,
  campaign_id TEXT,
  type TEXT,             -- cpa_spike, budget_pacing, conversion_drop, search_term_review
  severity TEXT,         -- warning, critical
  message TEXT,
  created_at TIMESTAMP,
  dismissed_at TIMESTAMP
);

CREATE TABLE playbooks (
  id TEXT PRIMARY KEY,
  name TEXT,
  vertical TEXT,
  content TEXT,          -- JSON/YAML bundle
  source TEXT,           -- built-in, community, custom
  installed_at TIMESTAMP
);
```

### API Contract (New/Changed Endpoints)

| Method | Path | Description | Phase |
|--------|------|-------------|-------|
| GET | `/api/dashboard` | Agency dashboard: all accounts with health indicators | Phase 1 |
| GET | `/api/accounts/{id}/health` | Single account health summary | Phase 1 |
| POST | `/api/accounts` | Add new account (credentials + auto-onboard) | Phase 1 |
| DELETE | `/api/accounts/{id}` | Remove account and associated data | Phase 1 |
| POST | `/api/accounts/{id}/onboard` | Trigger smart onboarding for existing account | Phase 1 |
| GET | `/api/accounts/{id}/campaigns/{id}/goals` | Get campaign goal/phase data | Phase 1 |
| PUT | `/api/accounts/{id}/campaigns/{id}/goals` | Update campaign goal/phase | Phase 1 |
| GET | `/api/accounts/{id}/campaigns/{id}/charts` | Performance chart data | Phase 1 |
| GET | `/api/accounts/{id}/alerts` | Active alerts for account | Phase 1 |
| POST | `/api/accounts/{id}/alerts/{id}/dismiss` | Dismiss an alert | Phase 1 |
| GET | `/api/search-terms/{campaign_id}/analysis` | AI-categorized search terms | Phase 1 |
| POST | `/api/operations/bulk` | Bulk operation (pause, enable, budget adjust) | Phase 1 |
| GET | `/api/conversations/search?q=` | Full-text search across conversations | Phase 1 |
| GET | `/api/playbooks` | List available playbooks | Phase 2 |
| POST | `/api/playbooks/{id}/apply` | Apply playbook to campaign | Phase 2 |
| GET | `/api/export/{account_id}/csv` | Export account data to CSV | Phase 2 |
| GET | `/api/export/{account_id}/report` | Generate PDF/markdown report | Phase 2 |

---

*Next step: Architecture review for V2, then Epic breakdown with implementation stories.*
