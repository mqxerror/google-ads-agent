---
stepsCompleted: [01-init, 02-discovery, 03-success, 04-journeys, 05-domain, 06-innovation, 07-project-type, 08-scoping, 09-functional, 10-nonfunctional, 11-complete]
inputDocuments: [CAMPAIGN_GUIDELINES.md, MENA_CAMPAIGN_GUIDELINES.md, GREECE_CAMPAIGN_GUIDELINES.md, google-ads-mcp/TRACKER.md, google-ads-mcp/CLAUDE.md]
documentCounts:
  briefs: 1
  research: 1
  brainstorming: 0
  projectDocs: 3
workflowType: 'prd'
lastStep: 11
projectType: 'web_app'
domainComplexity: 'general'
track: 'bmad-method'
---

# Product Requirements Document - Google Ads Campaign Manager

**Author:** Wassim
**Date:** 2026-03-26
**Version:** 1.0
**Status:** Complete

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

### Problem

Google Ads campaign management currently relies on Claude Desktop as a general-purpose chat interface connected to a custom MCP server with 90+ services. While functional, this approach has significant limitations:

- **No persistent UI** - Every session starts from scratch; there is no visual campaign browser, no dashboard, no persistent guidelines display. The user must re-explain context or rely on the agent re-reading files each session.
- **No campaign context awareness** - Claude Desktop does not automatically load campaign-specific guidelines, rules, or historical context when discussing a campaign. The user must manually instruct the agent to read `CAMPAIGN_GUIDELINES.md` and related files.
- **No visual overview** - Campaign performance, account hierarchy, and ad group structure are only visible as text responses. There are no charts, tables with sorting/filtering, or at-a-glance dashboards.
- **No account/campaign selector** - Switching between accounts or campaigns requires typing customer IDs and campaign IDs in chat rather than clicking through a navigation tree.
- **No guidelines editor** - Campaign guidelines (currently markdown files like `CAMPAIGN_GUIDELINES.md`, `MENA_CAMPAIGN_GUIDELINES.md`, `GREECE_CAMPAIGN_GUIDELINES.md`) must be edited externally. Changes are not automatically reflected in agent context.

### Solution

A **purpose-built local web application** for Google Ads campaign management that combines:

1. **Visual campaign browser** with account/campaign tree navigation, inline metrics, and campaign settings display
2. **AI agent chat** powered by the Claude Code SDK, connected to the existing Google Ads MCP server (90+ services) with automatic campaign context injection
3. **Browser automation** via Chrome MCP - the same agent can navigate to GTM, landing pages, and external web UIs to perform tasks that go beyond the Google Ads API (e.g., setting up conversion tags, auditing landing pages, inspecting GTM containers)
4. **Campaign guidelines editor** with a markdown editor that auto-injects relevant guidelines into the AI agent's context when a campaign is selected
5. **Performance dashboards** with charts and date-range comparison
6. **Full local operation** using the existing Claude Code subscription and Google Ads API credentials - no additional API costs or cloud services

### Target Users

- **Primary:** Wassim - Google Ads campaign manager for Mercan Group (Portugal Golden Visa, Greece Golden Visa, MENA Golden Visa campaigns)
- **Secondary:** Other Google Ads managers who use the same MCP server infrastructure

### Key Differentiator

The "campaign personality" system - editable per-campaign guidelines and notes that the AI agent automatically loads as context before responding. This means the agent inherently knows each campaign's rules (e.g., "NEVER use form_submit as a primary conversion goal", "wait minimum 7 days before evaluating results") without the user having to repeat them.

---

## 2. Project & Domain Classification

| Attribute | Value |
|-----------|-------|
| **Project Type** | `web_app` (Single Page Application) |
| **Domain** | Digital Marketing / Google Ads Management |
| **Complexity** | Medium |
| **Classification** | Brownfield-adjacent |
| **BMAD Track** | BMad Method |

### Brownfield Context

This is a **new web application** that integrates deeply with an existing codebase:

- **Existing:** Google Ads MCP server (`google-ads-mcp/`) with 90 implemented services (87.4% of Google Ads API coverage), OAuth authentication client, campaign guidelines markdown files
- **New:** Web frontend, backend API layer, AI agent orchestration, local database, guidelines editor

The MCP server is not being rewritten - it is consumed as-is by the Claude Code SDK agent, exactly as it runs in Claude Desktop today.

---

## 3. Success Criteria

### User Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily workflow completion | Manage all campaigns from the web app without opening Claude Desktop or Google Ads UI | User can complete a full daily review cycle (check metrics, ask questions, make adjustments) within the app |
| Campaign context switch time | Under 3 clicks to switch from one campaign to another with full context loaded | Click account -> click campaign -> guidelines auto-loaded |
| Guidelines discoverability | Agent always has campaign-specific rules loaded | Zero instances of agent making changes that violate campaign guidelines |

### Business Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time saved per session | 30%+ reduction in time spent managing campaigns | Fewer messages needed to accomplish the same tasks vs. Claude Desktop |
| Error reduction | Zero guideline violations by the AI agent | All campaign changes comply with the relevant guidelines document |
| Campaign coverage | 100% of active campaigns documented with guidelines | Every campaign in the account has a guidelines file |

### Technical Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| MCP tool coverage | All 90+ tools accessible through the web app | Agent can invoke any tool available in the current MCP server |
| Response time | Sub-2 second for data queries, streaming AI within 1s first-token | Measured from user action to visible response |
| Reliability | App recovers gracefully from API errors, auth expiry, network issues | No data loss, clear error messages, auto-retry where appropriate |

### MVP Definition

The MVP is reached when a user can:
1. Open the web app and select a Google Ads account
2. Browse campaigns with visible metrics
3. Ask the AI agent questions about a campaign and receive contextually-aware responses
4. View and edit campaign guidelines that are automatically loaded into AI context

### Growth Definition

Growth is reached when the app also provides:
- Performance dashboards with charts
- Search term analysis tools
- Multi-conversation history with campaign tags
- Bulk operations

### Vision Definition

The vision is reached when the app supports:
- Automated rules engine (scheduled AI-driven optimizations)
- Campaign templates and cloning
- Multi-user collaboration
- Mobile-responsive design

---

## 4. User Journeys

### Journey 1: Daily Campaign Review (Primary)

**Actor:** Campaign Manager
**Frequency:** Daily
**Goal:** Review campaign performance and make data-driven adjustments

```
1. Open web app (localhost)
2. See account overview with all campaigns listed
3. Click on "Mercan Group Main Account" (7178239091)
4. See campaign list with inline metrics:
   - Portugal Golden Visa: $200/day, 45 clicks, 3 conv, $15 CPA
   - Greece Golden Visa: $200/day, 30 clicks, 5 conv, $12 CPA
   - MENA Golden Visa: $30/day, 10 clicks, 0 conv
5. Click "Portugal Golden Visa" campaign
6. See campaign detail panel:
   - Status, budget, bidding strategy
   - Ad groups tree with keywords
   - Performance chart (last 7/14/30 days)
   - Guidelines panel showing campaign-specific rules
7. Open chat panel (right side)
   - Agent auto-loads Portugal GV guidelines as context
   - "The PGV LP-CT conversion tag was fixed on March 19.
      Can you check if we've recorded any conversions since then?"
   - Agent invokes MCP tools, streams response with data
8. Based on response, ask agent to make adjustment:
   - "Switch bidding to Maximize Conversions with target CPA $50"
   - Agent checks guidelines (wait 7 days rule), confirms timing is OK
   - Agent executes change, updates change log in guidelines
9. Close app
```

### Journey 2: Campaign Guidelines Management

**Actor:** Campaign Manager
**Frequency:** As needed (after changes, weekly review)
**Goal:** Update campaign rules and notes that guide AI behavior

```
1. Navigate to campaign in sidebar
2. Click "Guidelines" tab
3. See formatted markdown view of campaign guidelines
4. Click "Edit" to switch to markdown editor
5. Add new entry to Change Log section
6. Update bidding strategy rules based on new data
7. Save - guidelines file updated on disk
8. Return to chat - agent now has updated context
9. Verify: ask agent "what's the current bidding rule for this campaign?"
   - Agent correctly cites the updated guideline
```

### Journey 3: New Campaign Setup

**Actor:** Campaign Manager
**Frequency:** Monthly
**Goal:** Create a new campaign with proper guidelines

```
1. Open chat panel
2. "I need to create a new Search campaign for EB3 Brazil targeting
   US audiences with a $100/day budget"
3. Agent asks clarifying questions:
   - Landing page URL?
   - Conversion action to use?
   - Bidding strategy preference?
4. Agent creates campaign via MCP tools
5. App prompts: "Create guidelines file for this campaign?"
6. Click "Yes" - pre-populated template based on CAMPAIGN_GUIDELINES.md format
7. Edit campaign-specific sections (conversion tracking, keywords plan, etc.)
8. Save guidelines - new campaign now has AI context
```

### Journey 4: Weekly Performance Review

**Actor:** Campaign Manager
**Frequency:** Weekly
**Goal:** Compare performance across all campaigns and identify issues

```
1. Open app to dashboard view
2. See all campaigns with week-over-week comparison
3. Identify underperforming campaign (MENA: 0 conversions)
4. Click into MENA campaign
5. Open chat: "Why is MENA not converting? Check search terms and landing page"
6. Agent loads MENA guidelines, queries search terms, analyzes data
7. Agent suggests: "The search terms show informational queries in Arabic.
   Consider adding negative keywords for [list]. Also, the landing page
   doesn't have an Arabic version - this may hurt conversion rate."
8. Review suggestions against MENA guidelines
9. Approve changes through chat or direct UI
```

### Journey 5: GTM Tag Setup via Browser Automation

**Actor:** Campaign Manager
**Frequency:** Per campaign launch or when debugging conversion tracking
**Goal:** Set up or fix GTM conversion tags using the AI agent's browser automation

```
1. Select campaign in sidebar (e.g., Portugal Golden Visa)
2. Open chat: "The PGV LP-CT conversion tag isn't firing.
   Can you check the GTM container and fix it?"
3. Agent loads campaign guidelines (knows GTM container ID: GTM-KWFH5X9T)
4. Agent uses Chrome MCP to:
   - Navigate to tagmanager.google.com
   - Open the correct container
   - Inspect the conversion tag and its trigger
   - Identify the issue (e.g., jQuery vs native event listener mismatch)
5. Tool call blocks show browser actions:
   - 🌐 chrome: navigate → tagmanager.google.com
   - 🌐 chrome: read_page → Container tags list
   - 🌐 chrome: javascript_tool → Inspect tag configuration
6. Agent reports findings with diagnosis
7. Agent asks: "I can fix this by updating the Custom HTML tag.
   Should I make the change and publish a new GTM version?"
8. User approves → agent edits the tag via browser and publishes
9. Agent updates the campaign guidelines Change Log with the fix details
```

### Journey 6: Landing Page Audit

**Actor:** Campaign Manager
**Frequency:** Per campaign launch or periodic audit
**Goal:** Verify landing page has correct tracking tags and conversion setup

```
1. Select campaign, open chat
2. "Audit the landing page for the Portugal Golden Visa campaign"
3. Agent reads guidelines (knows LP URL: mercan.com/business-immigration/portugal-golden-visa-program/)
4. Agent uses Chrome MCP to:
   - Navigate to the landing page
   - Read page source/content
   - Check for Google Ads tag, GTM container, GA4 tag
   - Verify form exists and check submission behavior
5. Tool call blocks show browser actions with 🌐 icons
6. Agent reports: "Tags found: AW-826329520 ✓, GTM-KWFH5X9T ✓, GA4 ✓.
   Form: Gravity Forms #23, AJAX submission.
   Conversion Linker: Present."
7. Agent updates guidelines Landing Page Tag Audit section
```

### Journey 7: Initial Setup

**Actor:** Admin / First-time User
**Frequency:** Once
**Goal:** Configure the application to connect to Google Ads

```
1. Open web app for first time
2. Setup wizard detects no configuration
3. Enter Google Ads credentials:
   - Developer token
   - OAuth client ID and secret
   - Refresh token
   - Login customer ID (MCC)
4. App validates credentials by querying accessible accounts
5. See list of accessible accounts - select which to manage
6. App creates initial configuration (stored locally in SQLite)
7. For each selected account, option to:
   - Import existing guidelines files
   - Create new guidelines from template
8. Setup complete - redirected to main app
```

---

## 5. Domain Analysis

### Google Ads API Landscape

The Google Ads API v23 (SDK v29.2.0) is the primary data source. The existing MCP server provides 90 of 103 possible services (87.4% coverage).

**Service Categories and Counts:**

| Category | Implemented | Total | Coverage |
|----------|-------------|-------|----------|
| Account Management | 11 | 11 | 100% |
| Ad Groups & Ads | 15 | 15 | 100% |
| Assets | 7 | 10 | 70% |
| Audiences & Targeting | 8 | 10 | 80% |
| Bidding & Budgets | 5 | 5 | 100% |
| Campaign Management | 17 | 17 | 100% |
| Conversions | 11 | 11 | 100% |
| Data Import | 5 | 5 | 100% |
| Metadata | 3 | 3 | 100% |
| Planning | 9 | 9 | 100% |
| Product Integration | 5 | 5 | 100% |
| Shared Resources | 4 | 4 | 100% |

### Account Hierarchy (Current)

```
Manager (MCC): 6895949945 - MQXDev
  └─ Sub-Manager: 7192648347 - Wassim
       └─ Client: 7178239091 - Mercan Group Main Account
            ├─ Portugal Golden Visa (23636342079) - ENABLED
            ├─ PGV Impression Share (14815079674) - ENABLED
            ├─ EB3 Brazil (20043943331) - ENABLED
            ├─ PGV Fund Experiment (21705602620) - ENABLED
            ├─ PGV Trial 490 (21957819991) - ENABLED
            ├─ PGV Maximize Click Test (21987116063) - ENABLED
            ├─ PGV Test Q2 (22396489815) - ENABLED
            ├─ Greece Golden Visa (22551124974) - ENABLED
            ├─ Greece GV Max Conv (22807384760) - ENABLED
            └─ MENA Golden Visa (23688200557) - ENABLED
       └─ Client: 1949155935 - (unnamed)
            └─ MSG Experts (paused)
```

### Campaign Guidelines System

Campaign guidelines are stored as markdown files with a specific structure:

1. **Global Rules** - Apply to all campaigns (change management, conversion tracking, negative keyword policy, bidding strategy rules)
2. **Per-Campaign Sections** - Campaign-specific settings, conversion tracking, ad groups, keywords, negative keywords, performance history, known issues, change log, fix plans
3. **Region-Specific Files** - `MENA_CAMPAIGN_GUIDELINES.md` (Arabic campaigns), `GREECE_CAMPAIGN_GUIDELINES.md` (Greece campaigns)

This structure must be preserved in the web app's guidelines editor, as it serves as the "single source of truth" that both the human and AI agent reference.

### Known API Constraints

- The MCP server imports from `google.ads.googleads.v20` types but the SDK returns v23 service clients. The web app must be aware of this when making direct API calls.
- Google Ads API has rate limits and quota restrictions that must be respected.
- OAuth refresh tokens can expire and need re-authentication flow.
- Conversion tracking involves GTM integration - the AI agent can interact with GTM through browser automation (Chrome MCP) for tag setup, debugging, and publishing.

---

## 6. Innovation & Competitive Analysis

### What Makes This Different

**1. AI Agent as Primary Interface**

Unlike traditional Google Ads management tools (Google Ads UI, Optmyzr, WordStream, Adalysis) that are form-based dashboards, this application treats the AI agent as the primary interaction mode. The campaign browser and dashboards are supporting context - the agent handles the complex operations.

This inverts the typical SaaS pattern: instead of "dashboard with a chat widget", this is "AI agent with a dashboard context."

**2. Campaign Guidelines as AI Context (Campaign Personality System)**

No existing tool offers editable per-campaign rules that automatically become part of the AI's working context. The guidelines system means:
- The AI knows "NEVER use form_submit as a primary conversion goal for any campaign" without being told
- The AI knows "wait minimum 7 days before evaluating results" and will push back on premature changes
- The AI knows each campaign's specific conversion actions, keyword structure, and historical issues
- When guidelines are updated, the AI's behavior immediately reflects the changes

This is the core innovation: **the campaign guidelines are the AI's memory and judgment system.**

**3. MCP Service Bridge via Claude Code SDK**

Rather than building a custom AI agent from scratch, this app uses the Claude Code SDK to spawn an agent that connects to the existing MCP server. This means:
- All 90+ Google Ads tools are available to the AI agent automatically
- No tool definitions need to be manually maintained - the MCP server is the single source of truth
- New MCP tools added to the server are immediately available in the web app
- The same agent quality and tool-use capability as Claude Desktop

**4. Browser Automation for Beyond-API Tasks**

The Google Ads API doesn't cover everything. GTM tag management, landing page auditing, competitor research, and PageSpeed analysis all require browser interaction. Today in Claude Desktop, the agent uses the Chrome MCP to handle these tasks - navigating to GTM, editing tags, publishing containers, inspecting landing pages.

This app preserves that capability by configuring the Chrome MCP as a second MCP server alongside the Google Ads MCP. The agent intelligently decides when to use API tools vs browser tools based on the task. Use cases include:
- **GTM tag setup and debugging** - Navigate to GTM, inspect containers, edit Custom HTML tags, publish versions (exactly how the PGV LP-CT jQuery fix was done)
- **Landing page auditing** - Check which tags are installed, verify form submissions, inspect conversion tracking setup
- **Google Ads UI-only features** - Access settings or views not available through the API
- **External research** - Check competitor ads, review PageSpeed scores, inspect landing page content

**5. Local-First Architecture**

All data stays local. No cloud backend, no user accounts, no data sharing. This is critical for a tool that handles advertising credentials and campaign strategy.

### Competitive Landscape

| Feature | Google Ads UI | Optmyzr | WordStream | This App |
|---------|--------------|---------|------------|----------|
| Campaign management | Full | Partial | Partial | Full (via AI + MCP) |
| AI-powered operations | Limited (recommendations) | Rule-based | Rule-based | Full conversational AI |
| Per-campaign guidelines | None | None | None | Core feature |
| Contextual AI memory | None | None | None | Auto-loaded guidelines |
| Browser automation | N/A | None | None | GTM, landing pages, external UIs |
| Local operation | No (cloud) | No (SaaS) | No (SaaS) | Yes |
| Cost | Free | $249+/mo | $49+/mo | Free (uses existing subscriptions) |
| Customizable tools | No | Limited | No | 90+ MCP + Chrome tools |

---

## 7. Project Type Deep Dive

### Application Type: Single Page Application (SPA)

| Attribute | Decision | Rationale |
|-----------|----------|-----------|
| **Rendering** | Client-side SPA | Local tool, no SSR/SEO needed |
| **Framework** | React + TypeScript | Mature ecosystem, rich component libraries |
| **Build Tool** | Vite | Fast HMR, simple configuration |
| **Browser Support** | Modern only (Chrome, Edge, Firefox latest) | Local tool, user controls the browser |
| **Responsive Design** | Desktop-first, tablet-responsive | Primary use on desktop, occasional tablet |
| **SEO** | Not applicable | Local tool, not publicly accessible |
| **Real-time** | Yes - AI streaming + live data refresh | SSE for chat streaming, periodic data refresh |
| **Accessibility** | WCAG AA basic | Single-user tool, but follow sensible defaults |

### Browser Matrix

| Browser | Version | Support Level |
|---------|---------|---------------|
| Chrome | Latest 2 | Full |
| Edge | Latest 2 | Full |
| Firefox | Latest 2 | Full |
| Safari | Latest | Best-effort |

### Performance Targets

| Metric | Target |
|--------|--------|
| Initial load | < 2 seconds |
| Route navigation | < 500ms |
| Campaign data fetch | < 3 seconds (API-dependent) |
| AI first-token | < 1 second |
| AI stream throughput | 50+ tokens/second |
| Campaign list render (100+ campaigns) | < 500ms |

---

## 8. Scoping & Phasing

### Phase 1: MVP - Core Problem Solved

**Goal:** Replace Claude Desktop as the daily campaign management interface.

**Timeline estimate:** This phase delivers the minimum viable product.

**Features:**

| Feature | Description | Priority |
|---------|-------------|----------|
| Account Connection | OAuth setup wizard, credential storage, account discovery | P0 |
| Account Selector | Hierarchy view (Manager → Sub-Manager → Client), click to select | P0 |
| Campaign Browser | List all campaigns with status, budget, bidding strategy, key metrics | P0 |
| Campaign Detail | Ad groups, keywords, ads tree view with inline metrics | P0 |
| AI Chat Panel | Streaming chat interface connected to Claude Code SDK + MCP server | P0 |
| Guidelines Viewer | Display per-campaign guidelines in formatted markdown | P0 |
| Guidelines Editor | Edit guidelines in markdown editor, save to filesystem | P0 |
| Auto-Context Injection | When campaign selected, auto-load its guidelines into AI context | P0 |
| Browser Automation | Chrome MCP integration for GTM, landing page audits, external web UIs | P0 |
| Tool Transparency | Show which MCP tools and browser actions the agent invoked and their results | P1 |
| Basic Settings | Configure MCP server path, Chrome MCP path, data directory, preferences | P0 |

**Out of scope for MVP:**
- Performance charts and dashboards
- Search term analysis tool
- Conversation history persistence
- Bulk operations
- Multi-conversation threads

### Phase 2: Growth - Power User Features

**Goal:** Add visual analytics and advanced management capabilities.

**Features:**

| Feature | Description | Priority |
|---------|-------------|----------|
| Performance Dashboard | Charts for spend, clicks, conversions, CPA over time per campaign | P1 |
| Date Range Comparison | Compare metrics across custom date ranges | P1 |
| Search Term Analysis | View search terms, bulk add negatives with reason tracking | P1 |
| Conversation History | Persist conversations in SQLite, tag by campaign, search history | P1 |
| Multi-Thread Chat | Multiple conversation threads per campaign | P2 |
| Change Log Viewer | Visual change history from Google Ads API change events | P2 |
| Bulk Operations | Bulk keyword/ad management with preview and confirmation | P2 |
| Data Export | Export campaign data and reports to CSV/Excel | P2 |

### Phase 3: Expansion - Automation & Scale

**Goal:** Enable automated optimization and scale to multiple accounts.

**Features:**

| Feature | Description | Priority |
|---------|-------------|----------|
| Automated Rules | Schedule AI-driven optimization checks (e.g., daily search term review) | P2 |
| Campaign Templates | Save and clone campaign configurations | P3 |
| Multi-Account Dashboard | Overview across all accounts in a single view | P2 |
| Alert System | Notifications for budget depletion, conversion drops, guideline violations | P2 |
| Mobile Responsive | Full mobile layout for on-the-go monitoring | P3 |
| Team Collaboration | Multi-user support with role-based access (if needed) | P3 |

### Explicit Non-Goals (All Phases)

- Cloud deployment or hosting
- User authentication / multi-tenant system (single local user)
- Google Ads Editor replacement (bulk offline editing)
- Automated bidding algorithm (use Google's native strategies)
- Landing page building or management
- Full GTM UI replacement (agent uses browser automation for specific GTM tasks, not a dedicated GTM management interface)

---

## 9. Functional Requirements

### FR Group 1: Account Management

| ID | Requirement | Phase |
|----|-------------|-------|
| FR1.1 | The system shall provide a setup wizard to configure Google Ads API credentials (developer token, OAuth client ID, client secret, refresh token, login customer ID) | MVP |
| FR1.2 | The system shall validate credentials by querying accessible accounts from the Google Ads API | MVP |
| FR1.3 | The system shall display the account hierarchy (Manager → Sub-Manager → Client) as a navigable tree | MVP |
| FR1.4 | The user shall be able to switch between client accounts within a session without re-authenticating | MVP |
| FR1.5 | The system shall store account configurations in a local SQLite database, with credentials encrypted | MVP |
| FR1.6 | The system shall detect and handle expired OAuth refresh tokens with a re-authentication flow | MVP |

### FR Group 2: Campaign Browsing

| ID | Requirement | Phase |
|----|-------------|-------|
| FR2.1 | The system shall display all campaigns for the selected account in a sortable, filterable list | MVP |
| FR2.2 | Each campaign row shall show: name, status, channel type, daily budget, bidding strategy, and key metrics (impressions, clicks, conversions, cost, CPA) for a selectable date range | MVP |
| FR2.3 | The user shall be able to drill into a campaign to see its ad groups in a tree view | MVP |
| FR2.4 | Each ad group shall display its keywords, ads, and assets with inline status and metrics | MVP |
| FR2.5 | The user shall be able to filter campaigns by status (ENABLED, PAUSED, REMOVED), name search, and campaign type | MVP |
| FR2.6 | The system shall show campaign settings (bidding strategy, budget, location targets, language targets, conversion goals) in a detail panel | MVP |
| FR2.7 | The system shall display performance charts (impressions, clicks, conversions, cost over time) for a selected campaign | Growth |
| FR2.8 | The user shall be able to compare performance across two date ranges | Growth |

### FR Group 3: AI Agent Chat

| ID | Requirement | Phase |
|----|-------------|-------|
| FR3.1 | The system shall provide a chat interface panel that streams AI agent responses in real-time | MVP |
| FR3.2 | The AI agent shall be powered by the Claude Code SDK, configured with the existing Google Ads MCP server | MVP |
| FR3.3 | When a campaign is selected in the browser, the system shall automatically inject that campaign's guidelines file content into the AI agent's system context | MVP |
| FR3.4 | When an account is selected, the system shall inject the global rules section of the main guidelines file into the AI agent's context | MVP |
| FR3.5 | The AI agent shall have access to all tools provided by the Google Ads MCP server (currently 90 services) | MVP |
| FR3.6 | The system shall display which MCP tools the agent invoked during a response, with expandable input/output details | MVP |
| FR3.7 | The user shall be able to see and approve/reject tool invocations before they execute (optional confirmation mode for mutating operations) | MVP |
| FR3.8 | The system shall persist conversation history in SQLite, associated with the campaign/account context | Growth |
| FR3.9 | The user shall be able to create multiple conversation threads, each tagged with campaign context | Growth |
| FR3.10 | The user shall be able to search conversation history by keyword | Growth |

### FR Group 4: Campaign Guidelines Management

| ID | Requirement | Phase |
|----|-------------|-------|
| FR4.1 | The system shall display per-campaign guidelines in a formatted markdown view with proper table rendering | MVP |
| FR4.2 | The system shall provide a markdown editor for creating and editing guidelines files | MVP |
| FR4.3 | Guidelines files shall be stored on the local filesystem as `.md` files, compatible with the existing format (`CAMPAIGN_GUIDELINES.md`) | MVP |
| FR4.4 | The system shall support the existing guidelines structure: Global Rules, Per-Campaign sections (Overview, Conversion Tracking, Ad Groups, Keywords, Negative Keywords, Performance History, Known Issues, Change Log, Fix Plan) | MVP |
| FR4.5 | When a campaign has no guidelines file, the system shall offer to create one from a template based on the existing format | MVP |
| FR4.6 | The system shall auto-save guidelines edits (with debounce) and show save status | MVP |
| FR4.7 | When guidelines are saved, any active AI chat session for that campaign shall use the updated guidelines on the next message | MVP |

### FR Group 5: Campaign Operations

| ID | Requirement | Phase |
|----|-------------|-------|
| FR5.1 | The user shall be able to create new campaigns through the AI chat (conversational creation) | MVP |
| FR5.2 | The user shall be able to modify campaign settings (budget, bidding strategy, status) through the AI chat or a direct edit form | MVP |
| FR5.3 | The user shall be able to manage keywords (add, pause, remove, change match type) through the AI chat or a direct management interface | MVP |
| FR5.4 | The user shall be able to create and manage responsive search ads through the AI chat | MVP |
| FR5.5 | The user shall be able to view search term reports and add negative keywords with reason documentation | Growth |
| FR5.6 | The user shall be able to manage conversion actions and verify conversion tracking status | Growth |
| FR5.7 | The system shall enforce the guidelines' change management rule: warn when multiple change types are attempted in the same day | MVP |
| FR5.8 | The system shall automatically log changes to the campaign's guidelines Change Log section when operations are performed through the AI agent | Growth |

### FR Group 7: Browser Automation (Chrome MCP)

| ID | Requirement | Phase |
|----|-------------|-------|
| FR7.1 | The AI agent shall have access to Chrome browser automation tools via the Chrome MCP server, in addition to the Google Ads MCP server | MVP |
| FR7.2 | The agent shall be able to navigate to external web UIs (GTM, Google Ads UI, landing pages) to perform tasks not available through the Google Ads API | MVP |
| FR7.3 | Browser actions (navigation, page reading, JavaScript execution, form interaction) shall be displayed in the chat panel as tool call blocks with a distinct browser icon | MVP |
| FR7.4 | The agent shall intelligently decide when to use API tools vs browser tools based on the task (e.g., campaign budget change → API; GTM tag edit → browser) | MVP |
| FR7.5 | Browser automation shall require Chrome to be running with the Claude-in-Chrome extension installed | MVP |
| FR7.6 | The setup wizard shall include an optional step to configure the Chrome MCP server path | MVP |
| FR7.7 | The system shall handle Chrome MCP unavailability gracefully - if Chrome is not running, the agent falls back to API-only mode and informs the user that browser tasks are unavailable | MVP |

### FR Group 6: Data Display & Reporting

| ID | Requirement | Phase |
|----|-------------|-------|
| FR6.1 | The system shall display a campaign performance overview with key metrics for selectable date ranges (today, 7d, 14d, 30d, custom) | MVP |
| FR6.2 | The system shall show conversion tracking status per campaign, including which conversion actions are configured and their recent performance | Growth |
| FR6.3 | The system shall display impression share metrics and lost impression share by rank/budget | Growth |
| FR6.4 | The system shall provide a change history view sourced from Google Ads API change events | Growth |
| FR6.5 | The user shall be able to export campaign data to CSV | Growth |

---

## 10. Non-Functional Requirements

### Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-P1 | Application initial load time | < 2 seconds |
| NFR-P2 | Route navigation within app | < 500ms |
| NFR-P3 | Campaign list render (100+ campaigns) | < 500ms |
| NFR-P4 | Google Ads API data fetch (single campaign) | < 3 seconds |
| NFR-P5 | AI agent first-token latency | < 1 second |
| NFR-P6 | AI agent streaming throughput | 50+ tokens/second |
| NFR-P7 | Guidelines file load and render | < 500ms |
| NFR-P8 | Campaign data cache TTL | 5 minutes (configurable) |

### Security

| ID | Requirement |
|----|-------------|
| NFR-S1 | OAuth credentials (developer token, client ID, client secret, refresh token) shall be stored encrypted in the local SQLite database or OS keychain |
| NFR-S2 | No campaign data, credentials, or guidelines shall be transmitted to any server other than Google Ads API and Claude API (via Claude Code SDK) |
| NFR-S3 | The application shall not expose any network endpoints beyond localhost |
| NFR-S4 | API responses containing sensitive data (credentials, tokens) shall not be logged to the console or stored in conversation history |
| NFR-S5 | The SQLite database file shall have restricted file permissions (owner-only read/write) |

### Integration

| ID | Requirement |
|----|-------------|
| NFR-I1 | The application shall integrate with the existing Google Ads MCP server at `google-ads-mcp/` via the Claude Code SDK's MCP server configuration |
| NFR-I2 | The application shall use the existing `GoogleAdsSdkClient` from `google-ads-mcp/src/sdk_client.py` for direct data queries (read-only operations that don't need AI involvement) |
| NFR-I3 | The application shall read and write guidelines files from the local filesystem in the existing markdown format |
| NFR-I4 | The application shall use the Claude Code SDK/CLI as the AI agent runtime, leveraging the user's existing Claude Code subscription |
| NFR-I5 | The application shall be compatible with the existing `.env` file format for Google Ads API credentials |
| NFR-I6 | The application shall support the Chrome MCP server as an optional second MCP server for browser automation (GTM, landing pages, external web UIs) |
| NFR-I7 | The Chrome MCP integration shall be optional - the app functions fully for API-based tasks without Chrome running |

### Reliability

| ID | Requirement |
|----|-------------|
| NFR-R1 | The application shall handle Google Ads API errors (quota exceeded, permission denied, invalid requests) with clear user-facing error messages |
| NFR-R2 | The application shall detect expired OAuth tokens and prompt for re-authentication without losing the current session state |
| NFR-R3 | AI chat sessions shall be recoverable after app restart (conversation state persisted) |
| NFR-R4 | Guidelines editor shall auto-save edits with debounce to prevent data loss |
| NFR-R5 | The application shall handle Claude Code SDK connection failures gracefully (retry, fallback to read-only mode) |

### Maintainability

| ID | Requirement |
|----|-------------|
| NFR-M1 | Frontend and backend shall be cleanly separated with a well-defined API contract |
| NFR-M2 | When new MCP tools are added to the Google Ads MCP server, they shall be automatically available to the AI agent without web app changes |
| NFR-M3 | The guidelines file format shall remain backward-compatible with existing files (no migration needed) |
| NFR-M4 | Configuration shall be stored in a single location (SQLite + .env) with no hardcoded values |

---

## 11. Technical Architecture Summary

### System Overview

```
+----------------------------------+
|         React SPA (Vite)         |
|  +----------+ +---------+       |
|  | Campaign | | Chat    |       |
|  | Browser  | | Panel   |       |
|  +----+-----+ +----+----+       |
|       |             |            |
+-------+-------------+------------+
        |             |
   REST API      WebSocket/SSE
        |             |
+-------+-------------+------------+
|      Python FastAPI Backend       |
|  +----------+ +------------------+|
|  | Data API | | Agent Orchestr.  ||
|  | (direct) | | (Claude Code SDK)||
|  +----+-----+ +--------+---------+|
|       |                 |         |
+-------+-----------------+---------+
        |                 |
        v                 v
  Google Ads API    Claude Code SDK
  (via sdk_client)  + MCP Servers:
                      ├─ google-ads-mcp (90+ API tools)
                      └─ chrome-mcp (browser automation)
```

### Frontend Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | React 18+ with TypeScript | UI rendering and state management |
| Build | Vite | Fast development and bundling |
| State | Zustand (global) + TanStack Query (server state) | Campaign data fetching/caching + UI state |
| Routing | React Router v6 | SPA navigation |
| Chat UI | Custom component with SSE client | Streaming AI responses |
| Markdown | MDXEditor or TipTap | Guidelines viewing and editing |
| Charts | Recharts | Performance dashboards (Phase 2) |
| Tables | TanStack Table | Campaign/keyword data display with sorting/filtering |
| Styling | Tailwind CSS | Utility-first styling |

### Backend Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Python FastAPI | REST API + WebSocket/SSE endpoints |
| Database | SQLite via aiosqlite | Conversations, preferences, cached data, credentials |
| AI Agent | Claude Code SDK (Python: `claude_code_sdk`) | Agent runtime with MCP server access |
| Google Ads | Existing `GoogleAdsSdkClient` | Direct read-only queries (bypass AI for data fetching) |
| Guidelines | Local filesystem (markdown) | Read/write guidelines files |
| Auth | python-dotenv + encrypted storage | Load and manage OAuth credentials |

### AI Agent Architecture

The AI agent is the core of the application. It uses the **Claude Code SDK** to spawn an agent process that:

1. **Connects to multiple MCP servers** - The agent connects to both:
   - **Google Ads MCP server** (`google-ads-mcp/main.py`) - 90+ API tools for campaign management
   - **Chrome MCP server** (optional) - Browser automation tools for GTM, landing pages, and external web UIs
   This mirrors the current Claude Desktop setup where both MCP servers are available.

2. **Receives contextual system prompts** - The backend constructs a system prompt that includes:
   - Global campaign management rules (from the main guidelines file)
   - Campaign-specific guidelines (for the currently selected campaign)
   - Account context (customer IDs, hierarchy)
   - User preferences and notes

3. **Handles streaming responses** - The backend:
   ```
   User message → Backend → Claude Code SDK agent
                              ↓
                         MCP tool calls:
                         ├─ Google Ads API operations
                         └─ Browser actions (GTM, landing pages)
                              ↓
                         Streaming response
                              ↓
                  Backend → SSE/WebSocket → Frontend chat panel
   ```

4. **Provides tool transparency** - Every MCP tool invocation (both API and browser) is captured and forwarded to the frontend, showing the user what the agent did. Browser actions are displayed with a distinct icon.

5. **Supports confirmation mode** - For mutating operations (create campaign, change budget, add keywords, GTM edits), the backend can intercept tool calls and request user confirmation before executing.

6. **Handles Chrome MCP availability** - If Chrome is not running or the Chrome MCP is not configured, the agent operates in API-only mode. Browser-dependent tasks return a clear message asking the user to start Chrome.

### Data Flow

**Read-only operations (campaign data, metrics):**
```
Frontend → FastAPI REST → GoogleAdsSdkClient → Google Ads API → Response → Frontend
```

**AI agent operations (chat, campaign modifications):**
```
Frontend → FastAPI WebSocket/SSE → Claude Code SDK Agent
                                        ↓
                                   MCP Server tools:
                                   ├─ Google Ads MCP → Google Ads API
                                   └─ Chrome MCP → Browser (GTM, landing pages)
                                        ↓
                                   Streamed response → Frontend
```

**Guidelines operations:**
```
Frontend → FastAPI REST → Filesystem (read/write .md files) → Response → Frontend
```

### Local Storage Schema (SQLite)

**accounts:**
- id, customer_id, name, parent_id, level, is_active, created_at

**conversations:**
- id, account_id, campaign_id, title, created_at, updated_at

**messages:**
- id, conversation_id, role (user/assistant/tool), content, tool_calls_json, created_at

**preferences:**
- key, value, updated_at

**cached_metrics:**
- campaign_id, date, metrics_json, fetched_at

### Key Reuse from Existing Codebase

| Component | Source | How Reused |
|-----------|--------|------------|
| Google Ads MCP Server | `google-ads-mcp/` | Runs as-is, connected to Claude Code SDK agent |
| Chrome MCP Server | Claude-in-Chrome extension | Runs as-is, connected as second MCP server for browser automation |
| SDK Client | `google-ads-mcp/src/sdk_client.py` | Imported for direct read-only API queries |
| Service layer | `google-ads-mcp/src/services/` | 90 service classes available through MCP tools |
| Guidelines | `CAMPAIGN_GUIDELINES.md` etc. | Read/written by the web app's guidelines editor |
| OAuth config | `google-ads-mcp/.env` | Shared credentials file |

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol - a protocol for connecting AI agents to tool servers |
| **MCP Server** | The Google Ads MCP server (`google-ads-mcp/`) that wraps 90+ Google Ads API services as MCP tools |
| **Chrome MCP** | MCP server that provides browser automation tools (navigate, read page, execute JavaScript, fill forms) via the Claude-in-Chrome extension |
| **Claude Code SDK** | Anthropic's SDK for building applications powered by Claude agents with tool access |
| **Campaign Guidelines** | Markdown files containing per-campaign rules, conversion tracking setup, keyword lists, change logs, and fix plans |
| **MCC** | My Client Center - Google Ads manager account that oversees sub-accounts |
| **CPA** | Cost Per Acquisition - cost per conversion |
| **GTM** | Google Tag Manager - manages conversion tracking tags |
| **SSE** | Server-Sent Events - one-way streaming from server to client |

## Appendix B: Related Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Campaign Guidelines | `C:\Users\Wassim\Documents\google ads\CAMPAIGN_GUIDELINES.md` | Main guidelines file for all campaigns |
| MENA Guidelines | `C:\Users\Wassim\Documents\google ads\MENA_CAMPAIGN_GUIDELINES.md` | Arabic campaign guidelines |
| Greece Guidelines | `C:\Users\Wassim\Documents\google ads\GREECE_CAMPAIGN_GUIDELINES.md` | Greece campaign guidelines |
| MCP Server Tracker | `C:\Users\Wassim\Documents\google ads\google-ads-mcp\TRACKER.md` | Service implementation status |
| MCP Server README | `C:\Users\Wassim\Documents\google ads\google-ads-mcp\README.md` | Server documentation |
| MCP Dev Guidelines | `C:\Users\Wassim\Documents\google ads\google-ads-mcp\CLAUDE.md` | MCP server development rules |
