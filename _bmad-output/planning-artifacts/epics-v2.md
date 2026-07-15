---
stepsCompleted: [01-prerequisites, 02-epic-design, 03-stories, 04-validation]
inputDocuments: [_bmad-output/planning-artifacts/prd-v2.md, _bmad-output/planning-artifacts/architecture-v2.md]
workflowType: 'epics-and-stories'
lastStep: 4
---

# Google Ads Agent V2 - Epic Breakdown

**Author:** Wassim
**Date:** 2026-04-03
**Version:** 2.0
**Status:** Living — last Tier-2 reconcile 2026-07-14 (feature-log rows 2026-06-02 → 2026-07-14 folded back)
**Scope:** Phase 1 (Foundation Upgrade) + Phase 1.5/1.6 epics + § "Shipped Unplanned" ledger

---

## FR Coverage Map (Phase 1 Only)

| FR | Epic |
|----|------|
| FR1.7-1.11 (Multi-account, onboarding) | Epic 1 |
| FR1.1-1.6 (Setup, credentials) | Epic 1 |
| FR2.7-2.11 (Charts, phases, virtual scroll) | Epic 3 |
| FR3.7-3.13 (Conversations, search, intelligence) | Epic 4 |
| FR4.7-4.9 (Auto-generated guidelines, goals, phases) | Epic 5 |
| FR5.1, FR5.5-5.8 (Campaign creation, bulk ops, search terms) | Epic 6 |
| FR6.2-6.4 (Charts, dashboard, comparison) | Epic 3 |
| NFR-P7-P11, NFR-S6-S7, NFR-M5-M7 | Epic 7 |

---

## Epic List

> **Phase-1 status (reconciled 2026-07-14):** Epics 1–6 shipped with the V2
> upgrade (complete by early April 2026, MCP wired 2026-04-04). Epic 7 (public
> release preparation) remains open.

### Epic 1: Multi-Account Foundation & Smart Onboarding
Upgrade the database, credentials, and account management to support multiple Google Ads accounts with encrypted credential storage, per-account data isolation, and smart onboarding that auto-generates guidelines. This is the foundation everything else builds on.
**FRs covered:** FR1.7, FR1.8, FR1.9, FR1.10, FR1.11, NFR-S6

### Epic 2: Marketing Intelligence Layer
Build the service that detects campaign goals, phases, and surfaces proactive insights. This enriches both the agent's system prompt (Layer 0) and the dashboard UI.
**FRs covered:** FR3.11, FR3.12, FR3.13, FR2.10

### Epic 3: Performance Dashboards & Charts
Add performance charts, period comparisons, anomaly highlighting, and the agency dashboard with cross-account health overview.
**FRs covered:** FR2.7, FR2.8, FR2.9, FR2.11, FR6.2, FR6.3, FR6.4

### Epic 4: Conversation System Upgrade
Upgrade from single-thread to multi-thread conversations with full-text search, conversation persistence per account, and conversation templates.
**FRs covered:** FR3.8, FR3.9, FR3.10

### Epic 5: Enhanced Guidelines & Auto-Generation
Upgrade guidelines to support auto-generation from onboarding scan, structured goal/phase fields, and per-account namespacing.
**FRs covered:** FR4.7, FR4.8, FR4.9

### Epic 6: Advanced Campaign Editing
Enable full campaign creation from briefs, bulk operations, search term management with AI categorization, and ad copy workshop.
**FRs covered:** FR5.1 (enhanced), FR5.5, FR5.6, FR5.7, FR5.8, FR3.7 (tiered confirmation)

### Epic 7: Public Release Preparation
Cross-platform testing, CI pipeline, contributing guide, README polish, install script hardening, and V1→V2 migration.
**FRs covered:** NFR-M5, NFR-M6, NFR-M7, NFR-R7, NFR-S7

### Epic 8: PMax Finalization — SHIPPED 2026-06-10→11
Close the loop from the existing PMaxWizard (709 lines), `routers/pmax.py`, and `asset_groups` table (V12) to a live end-to-end Performance Max campaign create — budget, asset group, audience signals, review, enable. ~70% built; finish, harden, verify against a real account.
**Source:** PRD §8 Phase 1.5 (2026-06-10) · `research/product-roadmap.md` coverage workstream
**Status:** all 4 stories shipped + live-verified (campaign 23934110143 created PAUSED on 7178239091); hardened by three live-bug rounds — see the story status notes below.

### Epic 9: MCP Plan Tools — SHIPPED 2026-06-10
Expose Scheduled Plans on the HTTP MCP bridge (`app/mcp_server.py`): `create_plan`, `list_plans`, `approve_plan`, `skip_plan`, `run_plan_now`. Reuses the existing scheduler/REST logic and bearer-token auth so plans can be created and approved from any Claude Code session.
**Source:** PRD §8 Phase 1.5 (2026-06-10) · roadmap Phase A0

### Epic 10: Shopping Campaigns — NOT STARTED (as of 2026-07-14)
Greenfield: Merchant Center account linking, product feed awareness, listing group structure, and a Shopping campaign creation flow (builder stage + tools). Completes the sellable campaign-type coverage (Search ✓, PMax ✓ after Epic 8, Shopping). The only open Phase-1.5 item.
**Source:** PRD §8 Phase 1.5 (2026-06-10) · roadmap coverage workstream

### Epic 13: Account Director Global Audit + Homepage v2 — SHIPPED 2026-07-04→05
The homepage becomes the surface of ONE owned agent flow: the Account Director reads ALL active campaigns via an account-wide mode of the existing workflow orchestrator and produces ONE money-ranked, approvable fix list — persisted, staleness-labelled, refreshed by a weekly Scheduled Plans ritual. The home layout reforms to "clean" (one column, summoned chat, icon rail, progressive disclosure) using the existing OKLCH tokens — no re-skin.
**Source:** PRD §8 Phase 1.6 (2026-07-04) · `research/homepage-redesign-brief.md` (THE ENGINE + DESIGN DIRECTION Wassim-locked)
**Numbering note:** Epics 11 (video engine) and 12 (Studio redesign) are reserved by the Studio track — planned in `research/` briefs and tracked via feature-log rows, not in this file; both have since SHIPPED — see § "Shipped Unplanned" below. 13 is the next free number.
**Status:** all 8 stories shipped (13.1–13.4 backend 2026-07-04; 13.5–13.8 homepage 2026-07-04→05) — see the story status notes below. Its data pipeline was rebuilt under Dashboard v2.1 (2026-07-12, § "Shipped Unplanned").

---

## Epic 1: Multi-Account Foundation & Smart Onboarding

**Goal:** Upgrade the data layer to support multiple accounts with isolation, encrypted credentials, and smart onboarding that auto-scans new accounts and generates initial guidelines.

**Depends on:** Nothing (foundation epic)
**Blocks:** All other epics

---

### Story 1.1: V2 Database Schema Migration

As a developer,
I want the SQLite database upgraded to V2 schema with per-account partitioning,
So that all data is isolated per account and the system supports multiple accounts.

**Acceptance Criteria:**

**Given** the app starts for the first time with a V1 database
**When** the migration runs
**Then** new tables are created: `accounts_v2`, `account_credentials`, `campaign_goals`, `alerts`, `playbooks`, `schema_version`
**And** existing V1 tables get an `account_id` column populated with the default account ID from `.env`
**And** a `messages_fts` FTS5 virtual table is created for full-text search
**And** all indexes from the V2 architecture schema are created
**And** `schema_version` table records version 2
**And** if the database is already V2, migration is skipped

**Technical notes:**
- Migration detected by checking `schema_version` table existence
- Default account ID read from `GOOGLE_ADS_LOGIN_CUSTOMER_ID` in `.env`
- Existing guidelines files moved to `data/guidelines/{account_id}/`

---

### Story 1.2: Encrypted Credential Store

As a user,
I want my Google Ads credentials stored securely with encryption,
So that sensitive data is protected even if someone accesses my machine.

**Acceptance Criteria:**

**Given** a user provides Google Ads credentials
**When** credentials are stored
**Then** they are encrypted using Fernet symmetric encryption before writing to SQLite
**And** the encryption key is derived from a machine-specific identifier (stable across restarts)
**And** `CredentialStore.get_credentials(account_id)` returns decrypted credentials
**And** `CredentialStore.store_credentials(account_id, creds)` encrypts and stores
**And** the `.env` file is still loaded as a fallback if no DB credentials exist (V1 compat)

**Technical notes:**
- `backend/app/services/credentials.py` — new service
- Use `cryptography.Fernet` (already in dependencies via `authlib`)
- Key derived from `uuid.getnode()` (MAC address) + PBKDF2

---

### Story 1.3: Multi-Account Management API

As an agency user,
I want to add, list, and remove Google Ads accounts,
So that I can manage multiple client accounts from one installation.

**Acceptance Criteria:**

**Given** the app is running
**When** I call `POST /api/accounts` with credentials
**Then** the credentials are validated by querying accessible accounts
**And** the account record is created in `accounts_v2` table
**And** credentials are stored encrypted in `account_credentials` table
**And** the account hierarchy is discovered and stored

**Given** multiple accounts are connected
**When** I call `GET /api/accounts`
**Then** all connected accounts are returned with name, ID, level, and last synced time

**Given** an account exists
**When** I call `DELETE /api/accounts/{id}`
**Then** the account and all associated data (conversations, cache, guidelines, alerts) are removed

**Technical notes:**
- New router: `backend/app/routers/accounts.py`
- Validation: attempt a lightweight API call with the provided credentials
- Hierarchy discovery reuses existing `GoogleAdsService.get_accessible_accounts()`

---

### Story 1.4: Account Switcher UI

As a user,
I want to switch between accounts in the sidebar,
So that I can manage different clients without restarting the app.

**Acceptance Criteria:**

**Given** multiple accounts are connected
**When** I click the account switcher in the header/sidebar
**Then** a dropdown shows all connected accounts with names
**And** selecting an account loads its campaigns, guidelines, and conversations
**And** the switch completes in under 1 second
**And** the previously selected campaign is deselected on account switch
**And** the chat panel starts a new conversation in the new account's context

**Technical notes:**
- Enhance `appStore.ts` with `selectedAccountId` and `connectedAccounts`
- TanStack Query cache is keyed by account ID (no cache collision between accounts)
- Frontend routes updated: `/accounts/{id}/campaigns/...`

---

### Story 1.5: Smart Onboarding — Account Scan

As a user,
I want new accounts to be automatically scanned when I add them,
So that I don't have to manually set up campaign context from scratch.

**Acceptance Criteria:**

**Given** a new account is added via `POST /api/accounts`
**When** credentials are validated successfully
**Then** `OnboardingService.scan_account()` runs automatically
**And** it fetches all campaigns with metrics (last 30 days) via direct SDK
**And** it fetches ad groups, keywords, and conversion actions per campaign
**And** it detects each campaign's goal (lead_gen, ecommerce, brand, traffic) from conversion actions and bid strategy
**And** it detects each campaign's phase (launch, learning, optimization, scaling, sunset)
**And** scan results are stored in `campaign_goals` table
**And** scan completes in under 60 seconds for a typical account (10-20 campaigns)
**And** scan progress is streamed to the frontend (SSE or polling)

**Technical notes:**
- `backend/app/services/onboarding.py` — new service
- Uses `GoogleAdsService` directly (not AI agent) for speed and zero cost
- Goal detection: check conversion action names + bid strategy type
- Phase detection: check campaign age, conversion volume, bid strategy change recency

---

### Story 1.6: Smart Onboarding — Auto-Generate Guidelines

As a user,
I want initial guidelines generated automatically from the account scan,
So that the AI agent has context from the very first conversation.

**Acceptance Criteria:**

**Given** an account scan is complete
**When** guidelines generation runs
**Then** a `BUSINESS_CONTEXT.md` file is created in `data/guidelines/{account_id}/`
**And** it contains: account overview, campaign summary table, key metrics, auto-generated date
**And** a `CAMPAIGN_GUIDELINES.md` file is created with per-campaign sections
**And** each campaign section includes: detected goal, detected phase, bid strategy, budget, top keywords, conversion actions
**And** guidelines follow the existing V1 markdown format (backward compatible)
**And** files include a note: "Auto-generated. Edit to add business context and constraints."
**And** generated files are shown to the user for review before the main app loads

**Technical notes:**
- Guidelines generated deterministically (no AI needed)
- Uses scan data from Story 1.5
- Template rendering with f-strings (simple, no template engine needed)

---

### Story 1.7: Add Account Setup Wizard UI

As a new user or agency adding a new client,
I want a step-by-step wizard to add an account,
So that setup is guided and error-proof.

**Acceptance Criteria:**

**Given** the user clicks "Add Account" or opens the app for the first time
**When** the wizard displays
**Then** Step 1: Enter credentials (dev token, client ID, secret, refresh token, login customer ID) with helper links
**And** Step 2: Validate (shows spinner, then success with account hierarchy or error with clear message)
**And** Step 3: Onboarding scan (shows progress: scanning campaigns, detecting goals, generating guidelines)
**And** Step 4: Review generated guidelines (preview with edit option)
**And** Step 5: Done — redirects to main app with account selected
**And** the wizard works for both first-time setup and adding additional accounts

**Technical notes:**
- Enhance existing `SetupWizard` component with new steps
- Reuse V1 credential form, add onboarding scan steps

---

## Epic 2: Marketing Intelligence Layer

**Goal:** Build the service that detects campaign goals, phases, and generates proactive insights that feed into both the agent's system prompt and the dashboard UI.

**Depends on:** Epic 1 (needs `campaign_goals` table, account data)

---

### Story 2.1: Campaign Goal Detection Service

As an AI agent,
I want to know each campaign's business objective,
So that I can make goal-appropriate recommendations (e.g., don't optimize for clicks when goal is conversions).

**Acceptance Criteria:**

**Given** a campaign has conversion actions and a bid strategy configured
**When** `MarketingIntelligenceService.detect_campaign_goal()` is called
**Then** it returns one of: `lead_gen`, `ecommerce`, `brand`, `traffic`, `local`, `unknown`
**And** detection logic:
  - Conversion actions containing "purchase", "transaction", "sale" → `ecommerce`
  - Conversion actions containing "lead", "form", "submit", "contact", "call" → `lead_gen`
  - Bid strategy `MAXIMIZE_CLICKS` or `TARGET_IMPRESSION_SHARE` → `traffic` or `brand`
  - Campaign type `DISPLAY` or `VIDEO` with awareness-type conversions → `brand`
**And** detected goal is stored in `campaign_goals` table
**And** goal can be manually overridden by the user via `PUT /api/accounts/{id}/campaigns/{id}/goals`

**Technical notes:**
- `backend/app/services/marketing_intelligence.py` — new service
- Goal detection runs during onboarding AND on-demand refresh

---

### Story 2.2: Campaign Phase Detection

As an AI agent,
I want to know each campaign's lifecycle phase,
So that I adapt my behavior (e.g., don't change bid strategies during learning phase).

**Acceptance Criteria:**

**Given** a campaign has performance data
**When** `MarketingIntelligenceService.detect_campaign_phase()` is called
**Then** it returns one of: `launch`, `learning`, `optimization`, `scaling`, `sunset`
**And** detection logic:
  - Campaign age < 14 days → `launch`
  - Bid strategy changed in last 14 days OR < 30 conversions in lookback → `learning`
  - CPA below target AND budget not fully spent → `scaling`
  - CPA consistently above target, declining impressions → `sunset`
  - Otherwise → `optimization`
**And** phase is stored in `campaign_goals` table with `phase_detected_at` timestamp
**And** phase can be manually overridden

**Technical notes:**
- Bid strategy change detection: compare current strategy to what was recorded in guidelines change log, or use Google Ads change history if available
- Phase rules are documented constants (not magic numbers)

---

### Story 2.3: Proactive Insights Engine

As a user reviewing my accounts,
I want the system to surface issues and opportunities without me asking,
So that I don't miss critical problems.

**Acceptance Criteria:**

**Given** account data is available
**When** `MarketingIntelligenceService.generate_proactive_insights()` runs
**Then** it detects and creates alerts for:
  - **CPA spike**: 7-day CPA > 30% above 30-day average → `warning`
  - **Budget pacing**: Spend rate tracking to exhaust budget before month end → `warning`
  - **Conversion drop**: 7-day conversions down 50%+ vs prior 7 days → `critical`
  - **Search term review overdue**: Last review > 7 days ago → `info`
  - **Phase change**: Campaign moved to a new phase → `info`
  - **Quality score drift**: Average QS dropped below 5 → `warning`
**And** alerts are stored in the `alerts` table with severity, message, and recommendation
**And** duplicate alerts for the same issue are not created (deduplicated by type + campaign)
**And** alerts can be dismissed or marked resolved

---

### Story 2.4: Marketing Intelligence Prompt Enrichment

As an AI agent,
I want marketing intelligence injected into my system prompt (Layer 0),
So that I have goal/phase context before the user even asks a question.

**Acceptance Criteria:**

**Given** a user sends a chat message for a specific campaign
**When** the agent's system prompt is constructed
**Then** Layer 0 is prepended with:
  - Campaign objective (e.g., "Lead Generation")
  - Campaign phase (e.g., "Optimization") with phase-specific rules
  - Active alerts for this campaign
  - Account-level context (monthly budget, campaign count, cross-campaign notes)
**And** phase rules clearly state what the agent should and should not do:
  - `launch`: "Gather data, don't change bid strategy, monitor closely"
  - `learning`: "Hands off bid strategy, warn user against changes"
  - `optimization`: "Safe to adjust bids, budgets, keywords, ad copy"
  - `scaling`: "Recommend budget increases, new keywords, audience expansion"
  - `sunset`: "Recommend reducing budget or pausing, document learnings"
**And** Layer 0 adds ~500 tokens to the system prompt

**Technical notes:**
- Modify `backend/app/services/agent.py` to call `marketing_intelligence.enrich_agent_prompt()` before building the full system prompt
- Layer 0 comes before Layer 1 (business context)

---

### Story 2.5: Campaign Phase Badge in UI

As a user browsing campaigns,
I want to see each campaign's detected phase as a visual badge,
So that I can quickly understand each campaign's lifecycle status.

**Acceptance Criteria:**

**Given** campaigns are displayed in the sidebar or campaign list
**When** a campaign has a detected phase in `campaign_goals`
**Then** a colored badge is shown next to the campaign name:
  - `launch` → blue badge
  - `learning` → yellow badge
  - `optimization` → green badge
  - `scaling` → purple badge
  - `sunset` → gray badge
**And** hovering over the badge shows the phase description and rules
**And** clicking the badge opens a dialog to manually override the phase

**Technical notes:**
- New `<PhaseBadge>` component
- Phase data fetched alongside campaign list

---

## Epic 3: Performance Dashboards & Charts

**Goal:** Add visual performance analytics with charts, period comparison, anomaly detection, and an agency-wide dashboard.

**Depends on:** Epic 1 (multi-account), Epic 2 (health indicators, alerts)

---

### Story 3.1: Campaign Performance Charts

As a user viewing a campaign,
I want to see performance charts (spend, clicks, conversions, CPA) over time,
So that I can visually identify trends and anomalies.

**Acceptance Criteria:**

**Given** a campaign is selected
**When** the Performance tab or overview panel is shown
**Then** line charts display for selectable metrics: impressions, clicks, conversions, cost, CPA, CTR, ROAS
**And** time range is selectable: 7d, 14d, 30d, 90d, custom
**And** charts render in under 500ms
**And** data points are per-day granularity
**And** charts use Recharts with responsive sizing

**Technical notes:**
- New endpoint: `GET /api/accounts/{id}/campaigns/{id}/charts?metric=cost,cpa&period=30d`
- Backend: query Google Ads API with `segments.date` for daily breakdown
- Frontend: new `<PerformanceChart>` component using Recharts

---

### Story 3.2: Period-over-Period Comparison

As a user,
I want to compare current metrics against the previous period,
So that I can see if performance is improving or declining.

**Acceptance Criteria:**

**Given** a date range is selected (e.g., last 7 days)
**When** the comparison view is enabled
**Then** metrics show current vs previous period (e.g., this week vs last week)
**And** delta indicators show green (up) or red (down) with percentage change
**And** CPA/cost deltas are inverted (lower is green, higher is red)
**And** comparison works for all selectable time ranges

**Technical notes:**
- Backend fetches two date ranges in a single GAQL query using date segmentation
- Frontend: `<PeriodComparison>` component with delta badges

---

### Story 3.3: Anomaly Highlighting

As a user,
I want metrics that deviate significantly from their average highlighted visually,
So that I notice problems without manually scanning numbers.

**Acceptance Criteria:**

**Given** campaign metrics are displayed
**When** a metric deviates more than 20% from its 30-day trailing average
**Then** it is highlighted with a visual indicator:
  - Cost/CPA above average → red highlight
  - Conversions/CTR below average → red highlight
  - Positive deviations → green highlight
**And** hovering shows: "CPA $35.20 is 42% above 30-day average ($24.80)"
**And** highlighting applies in both metric cards and chart views

**Technical notes:**
- Trailing averages computed from cached 30-day data
- Threshold configurable (default 20%)

---

### Story 3.4: Agency Dashboard

As an agency user with multiple accounts,
I want a dashboard showing all accounts at a glance,
So that I can quickly identify which accounts need attention.

**Acceptance Criteria:**

**Given** multiple accounts are connected
**When** I open the app (default view)
**Then** the agency dashboard shows a grid of account cards
**And** each card shows: account name, active campaign count, spend (30d), conversions (30d), average CPA, health badge
**And** health badge: green (all healthy), yellow (warnings exist), red (critical alerts)
**And** clicking an account card navigates to that account's campaign view
**And** an alert summary bar at the top shows total warnings/criticals across all accounts
**And** dashboard loads in under 3 seconds (parallel account queries)

**Technical notes:**
- New router: `backend/app/routers/dashboard.py`
- New service: `backend/app/services/dashboard.py` — aggregates across accounts
- Frontend: new `<AgencyDashboard>` component at route `/`
- Per-account health computed by `MarketingIntelligenceService`

---

### Story 3.5: Virtual Scrolling for Large Lists

As a user with 1000+ keywords or campaigns,
I want lists to remain fast and responsive,
So that the app doesn't lag on large accounts.

**Acceptance Criteria:**

**Given** a keyword list has 1000+ items
**When** the list renders
**Then** only visible rows are in the DOM (virtual scrolling)
**And** scrolling is smooth at 60fps
**And** initial render completes in under 500ms
**And** sorting and filtering work on the full dataset

**Technical notes:**
- Migrate `<KeywordTable>` to TanStack Table with `@tanstack/react-virtual`
- Apply same pattern to campaign lists if needed

---

## Epic 4: Conversation System Upgrade

**Goal:** Upgrade from single-thread to multi-thread conversations with persistence, search, and campaign tagging.

**Depends on:** Epic 1 (account_id partitioning)

---

### Story 4.1: Multi-Thread Conversations

As a user,
I want multiple conversation threads per campaign,
So that I can have separate discussions for different topics (daily review, keyword audit, ad copy).

**Acceptance Criteria:**

**Given** a campaign is selected
**When** I view the chat panel
**Then** a conversation list shows all threads for this campaign (most recent first)
**And** I can create a new conversation with a title
**And** I can switch between conversations by clicking
**And** each conversation maintains its own message history
**And** conversations are tagged with account_id and campaign_id

**Technical notes:**
- Enhance existing `conversations` and `messages` tables (already have the schema)
- Frontend: add `<ConversationList>` component to chat panel sidebar
- Zustand chatStore tracks `activeConversationId`

---

### Story 4.2: Full-Text Conversation Search

As a user,
I want to search across all my conversation history,
So that I can find past discussions about specific topics or recommendations.

**Acceptance Criteria:**

**Given** conversations exist with messages
**When** I type in the conversation search bar
**Then** results show matching messages with highlighted snippets
**And** results include: conversation title, message snippet, date, campaign name
**And** clicking a result opens the conversation at that message
**And** search works across all accounts or can be scoped to current account
**And** search responds in under 200ms for typical queries

**Technical notes:**
- SQLite FTS5: messages are indexed on insert in `messages_fts` virtual table
- New endpoint: `GET /api/conversations/search?q=keyword&account_id=`
- Frontend: `<ConversationSearch>` component with real-time results

---

### Story 4.3: Conversation Persistence Upgrade

As a user,
I want all conversations saved and recoverable across app restarts,
So that I never lose conversation context.

**Acceptance Criteria:**

**Given** a conversation is active
**When** the app is closed and reopened
**Then** all conversations are still available with full message history
**And** the last-active conversation per campaign is auto-selected on return
**And** tool call blocks are preserved with their expand/collapse state metadata
**And** conversation list shows: title, last message preview, timestamp, message count

**Technical notes:**
- V1 already persists conversations; this story enhances the UI for browsing history
- Add `message_count` and `last_message_preview` to conversation list queries

---

## Epic 5: Enhanced Guidelines & Auto-Generation

**Goal:** Upgrade guidelines to support auto-generation, structured goal/phase fields, and per-account namespacing.

**Depends on:** Epic 1 (account namespacing, onboarding), Epic 2 (goal/phase detection)

---

### Story 5.1: Per-Account Guidelines Namespacing

As a user with multiple accounts,
I want each account's guidelines stored separately,
So that there's no name collision and data stays isolated.

**Acceptance Criteria:**

**Given** multiple accounts are connected
**When** guidelines are read or written
**Then** files are stored in `data/guidelines/{account_id}/`
**And** the guidelines service resolves paths with account_id prefix
**And** V1 migration moves existing flat files into the default account's folder
**And** `GET /api/accounts/{id}/guidelines` returns only that account's files
**And** the `guidelines_meta` table includes `account_id` in the primary key

**Technical notes:**
- Modify `GuidelinesService` to accept `account_id` parameter
- Migration in Story 1.1 handles moving existing files

---

### Story 5.2: Structured Goal & Phase Fields in Guidelines

As a user editing guidelines,
I want campaign goal and phase visible and editable in the guidelines,
So that the AI agent and I share the same understanding of campaign strategy.

**Acceptance Criteria:**

**Given** a campaign has a guidelines file
**When** the guidelines are displayed
**Then** a structured header section shows:
  - Campaign Goal: [dropdown: Lead Gen, E-commerce, Brand, Traffic, Local, Other]
  - Campaign Phase: [dropdown: Launch, Learning, Optimization, Scaling, Sunset]
  - Target CPA / Target ROAS (numeric inputs)
  - Monthly Budget Cap (numeric input)
**And** changes to these fields update both the guidelines markdown AND the `campaign_goals` table
**And** the markdown format includes these fields as structured YAML frontmatter or a dedicated section
**And** the AI agent reads these fields as part of Layer 0 (marketing intelligence)

**Technical notes:**
- Guidelines format enhanced with a structured section at the top
- Parse structured fields separately from free-form markdown
- Keep backward compatible: V1 files without these fields still work

---

### Story 5.3: Auto-Generated Guidelines Review UI

As a user during onboarding,
I want to review and edit auto-generated guidelines before they're saved,
So that I can correct any inaccuracies from the automated scan.

**Acceptance Criteria:**

**Given** the onboarding scan has generated guidelines
**When** the review step is shown
**Then** I see a side-by-side view: left = auto-generated markdown preview, right = editable text
**And** I can edit any section before saving
**And** detected goals and phases are shown as editable fields above the markdown
**And** clicking "Save & Continue" writes the files to disk
**And** clicking "Regenerate" re-runs the scan and regeneration

**Technical notes:**
- Reuse existing `<GuidelinesEditor>` component in the setup wizard flow
- Add preview mode for side-by-side comparison

---

## Epic 6: Advanced Campaign Editing

**Goal:** Enable full campaign lifecycle management through the AI agent: creation from briefs, bulk operations, search term management, and ad copy workshop.

**Depends on:** Epic 2 (marketing intelligence for smart suggestions), Epic 4 (conversations for interaction)

---

### Story 6.1: Campaign Creation from Brief

As a user,
I want to describe a campaign in natural language and have the agent build it,
So that I can create complete campaigns without manually configuring every setting.

**Acceptance Criteria:**

**Given** an account is selected and I'm in a chat conversation
**When** I describe a campaign: "Create a Search campaign for EB5 investor visa, budget $150/day, targeting US accredited investors, goal is lead gen"
**Then** the agent proposes a complete campaign structure:
  - Campaign settings (name, type, budget, bid strategy)
  - Ad group structure with rationale
  - Keywords per ad group with match types
  - Negative keyword seed list
  - RSA headlines and descriptions per ad group
**And** the agent shows the plan and waits for approval (high-impact confirmation)
**And** on approval, the agent creates all components via MCP tools
**And** each step is shown as a tool call block in the chat
**And** the agent creates the campaign as PAUSED (user must manually enable)
**And** the agent auto-generates a guidelines file for the new campaign

**Technical notes:**
- This leverages existing MCP tools (campaign creation, keyword management, ad creation)
- The marketing intelligence prompt (Layer 0) guides the agent's strategy recommendations
- Agent's system prompt includes: "When creating campaigns, always create as PAUSED and generate guidelines"

---

### Story 6.2: Search Term Manager

As a user,
I want to review search terms with AI-powered categorization,
So that I can quickly identify irrelevant terms and add negatives.

**Acceptance Criteria:**

**Given** a campaign is selected
**When** I open the Search Terms tab
**Then** search terms (last 7 days) are fetched and displayed in a table
**And** the agent auto-categorizes each term:
  - **High Value**: Converting or high-CTR terms not yet added as keywords (green)
  - **Irrelevant**: Non-converting terms with high cost, unrelated intent (red)
  - **Monitor**: Borderline terms that need more data (yellow)
**And** irrelevant terms show a suggested negative keyword match type (exact, phrase, broad)
**And** I can select multiple terms and click "Add as Negatives" to apply in bulk
**And** all added negatives are logged in the campaign's guidelines Change Log

**Technical notes:**
- New endpoint: `GET /api/accounts/{id}/campaigns/{id}/search-terms/analysis`
- Categorization logic in `SearchTermService`:
  - Irrelevant: 0 conversions AND (cost > $10 OR impressions > 100)
  - High value: conversions > 0 AND not already a keyword
  - Monitor: everything else
- For AI-enhanced categorization: optionally pass terms through the agent for intent analysis
- Frontend: `<SearchTermManager>` component with tabbed view and bulk actions

---

### Story 6.3: Bulk Operations

As a user managing many campaigns,
I want to make changes across multiple campaigns at once,
So that I can efficiently manage large accounts.

**Acceptance Criteria:**

**Given** I'm viewing the campaign list
**When** I select multiple campaigns (checkboxes) or use the chat command "Pause all campaigns with CPA above $50"
**Then** I can apply bulk actions:
  - Pause/Enable selected campaigns
  - Adjust budgets (set to $X or increase/decrease by %)
  - Add negative keywords to all selected campaigns
**And** a confirmation dialog shows all planned changes before execution
**And** changes execute in parallel and show individual success/failure
**And** all changes are logged in each campaign's guidelines

**Technical notes:**
- New endpoint: `POST /api/operations/bulk`
- Frontend: checkbox column in campaign table, bulk action toolbar
- Agent can also trigger bulk ops through natural language

---

### Story 6.4: Ad Copy Workshop

As a user,
I want to iteratively improve ad copy with AI assistance,
So that I can create higher-performing responsive search ads.

**Acceptance Criteria:**

**Given** I'm viewing a campaign's ads or I ask the agent to help with ad copy
**When** I say "Help me improve the ad copy for ad group X"
**Then** the agent analyzes:
  - Current headlines and descriptions
  - Landing page content (via Chrome MCP if available)
  - Campaign guidelines (approved messaging, brand voice, banned phrases)
  - Campaign goal and target audience
**And** proposes new headlines/descriptions with rationale per item
**And** I can iterate: "Make H3 more urgent" → agent revises
**And** on approval, the agent updates the RSA via MCP tools
**And** changes are logged in guidelines

**Technical notes:**
- Uses existing MCP tools for ad creation/update
- Marketing intelligence prompt helps agent understand brand voice and audience
- No special UI needed — this happens entirely through the chat interface

---

### Story 6.5: Tiered Confirmation System

As a user,
I want different confirmation levels for different types of changes,
So that low-risk changes are fast and high-risk changes are safe.

**Acceptance Criteria:**

**Given** the agent is about to execute a tool call
**When** the tool is categorized as:
  - **High impact** (budget >20% change, bid strategy change, campaign create/pause): ALWAYS confirm
  - **Medium impact** (keyword add, ad create, targeting change): confirm by default, auto-approve option
  - **Low impact** (negative keyword add, guideline update, label add): auto-execute, notify user
**Then** high-impact shows a prominent confirmation dialog with impact summary
**And** medium-impact shows an inline confirmation in the chat
**And** low-impact executes immediately with a small notification
**And** the user can configure their preference (always confirm, smart, never confirm) in settings

**Technical notes:**
- `CONFIRMATION_TIERS` dict in agent service (see architecture doc)
- Frontend: different confirmation UI per tier
- User preference stored in `config` table

---

## Epic 7: Public Release Preparation

**Goal:** Prepare the project for open-source public release with cross-platform testing, CI, documentation, and V1 migration.

**Depends on:** All other epics (this is the final polish)

---

### Story 7.1: Cross-Platform Install Script Hardening

As a user on any platform (macOS, Linux, Windows),
I want the install script to work reliably on the first attempt,
So that I can get started without debugging installation issues.

**Acceptance Criteria:**

**Given** a fresh machine with Python 3.12+ installed
**When** I run `bash install.sh` (or `install.bat` on Windows)
**Then** Node.js is installed/upgraded if needed (via nvm on Mac/Linux, winget on Windows)
**And** uv is installed if needed
**And** backend dependencies are installed via `uv sync`
**And** frontend dependencies are installed via `npm install`
**And** `.env` template is created if not present
**And** data directories are created
**And** the script exits 0 on success with clear completion message
**And** the script provides actionable error messages on failure

**Technical notes:**
- Install scripts already handle Node.js and uv auto-install (done in current session)
- Add smoke test at end: start backend briefly, check health endpoint, then stop
- Test on macOS (Apple Silicon), Ubuntu 22.04, Windows 11

---

### Story 7.2: CI Pipeline

As a contributor,
I want automated checks on every PR,
So that code quality is maintained.

**Acceptance Criteria:**

**Given** a PR is opened on GitHub
**When** CI runs
**Then** backend checks pass: `ruff check`, `mypy`, `pytest`
**And** frontend checks pass: `eslint`, `tsc --noEmit`, `vite build`
**And** install script test passes on all platforms (matrix: ubuntu, macos, windows)
**And** CI completes in under 5 minutes

**Technical notes:**
- `.github/workflows/ci.yml`
- Use `astral-sh/setup-uv@v4` for Python, `actions/setup-node@v4` for Node
- Backend tests: unit tests for services (mock Google Ads API)
- Frontend tests: type-check and build (no e2e yet)

---

### Story 7.3: Contributing Guide & Documentation

As a potential contributor,
I want clear documentation on how to set up the development environment and contribute,
So that I can submit PRs without guessing.

**Acceptance Criteria:**

**Given** someone clones the repo
**When** they read CONTRIBUTING.md
**Then** they know: how to set up dev environment, how to run tests, code style expectations, PR process
**And** README.md is updated for V2: new features, agency use case, screenshots, architecture overview
**And** LICENSE file exists (MIT)
**And** issue templates exist for: bug report, feature request

**Technical notes:**
- `CONTRIBUTING.md`, `LICENSE`, `.github/ISSUE_TEMPLATE/`
- README: keep it concise, link to docs for details

---

### Story 7.4: V1 → V2 Migration

As an existing V1 user,
I want my data preserved when upgrading to V2,
So that I don't lose my conversations, guidelines, or configuration.

**Acceptance Criteria:**

**Given** a V1 installation exists with data
**When** V2 starts for the first time
**Then** database migration runs automatically (Story 1.1)
**And** existing credentials from `.env` are encrypted into the DB
**And** existing guideline files are moved to `data/guidelines/{account_id}/`
**And** existing conversations get `account_id` populated
**And** the user sees a one-time migration notice: "Upgraded to V2. Your data has been preserved."
**And** V1 is still usable if migration fails (rollback safety)

**Technical notes:**
- Migration is idempotent (safe to run multiple times)
- Backup `app.db` before migration
- Log migration steps for debugging

---

### Story 7.5: Opt-In Anonymous Telemetry

As a project maintainer,
I want to know how many people are using the tool,
So that I can prioritize features based on real usage.

**Acceptance Criteria:**

**Given** the app is running
**When** first launch after install
**Then** a dialog asks: "Help improve Google Ads Agent by sharing anonymous usage data?"
**And** user can choose Yes or No
**And** if Yes: send anonymous events (app start, feature usage counts — NO PII, NO campaign data)
**And** if No: no data is ever sent
**And** choice is stored in `config` table and can be changed in settings
**And** telemetry endpoint is open-source and auditable

**Technical notes:**
- Simple HTTP POST to a public analytics endpoint (e.g., Plausible, or self-hosted)
- Events: `app_start`, `account_count`, `feature_used:{feature_name}`
- NO: account IDs, campaign data, credentials, conversation content, IP addresses

---

## Epic 8: PMax Finalization (Phase 1.5)

Close the wizard → live (PAUSED) PMax campaign loop. Gap audit 2026-06-10:
campaign/budget/asset-group creation work; flow breaks at asset linking because
the wizard passes local upload UUIDs where the orchestrator expects Google Ads
asset resource names; audience signals are collected but never attached.

### Story 8.1: Image Asset Bridge (local upload → Google Ads asset)

As an operator finishing the PMax wizard,
I want my uploaded logos/images turned into real Google Ads image assets,
So that asset-group linking succeeds and the campaign actually materialises.

**Acceptance Criteria:**

**Given** a wizard bundle whose `logos`/`images` entries are local upload UUIDs
**When** the PMax orchestrator runs its asset step
**Then** each local UUID's file bytes are pushed via `AssetService.create_image_asset()`
**And** the returned `customers/.../assets/...` resource name replaces the UUID in the bundle
**And** entries that are already resource names pass through unchanged
**And** asset-group linking uses only resource names (no more garbage-id API rejections)

**Technical notes:** orchestrator-side bridge (not in the generic upload endpoint);
files read from the assets.py upload storage path; rollback pattern preserved.

**Status note (2026-06-10→11):** implemented, then hardened through three
live-bug rounds: (a) asset group now created ATOMICALLY with all
AssetGroupAsset links in one mutate (Google validates PMax asset minimums at
creation); rollback uses REMOVE operations for campaign AND budget; (b) every
local image is center-cropped to the slot's EXACT Google aspect pre-flight
(`_fit_image_for_slot` + IMAGE_SLOT_SPECS, below-min → clean 422); (c) upload
dedupe re-keyed `(uuid, slot-aspect)` so one image in two different-aspect
slots uploads per-aspect, and google-resource pass-throughs are GAQL-verified
pre-flight. Regression tests in `backend/tests/test_pmax_resubmit.py`.

### Story 8.2: Audience Signals Attachment

**Given** a bundle with non-empty `audience_signals`
**When** asset linking has succeeded
**Then** signals are attached via `AssetGroupSignalService.mutate_asset_group_signals()`
**And** a bundle without signals skips the step silently.

**Status note (2026-06-10):** implemented — signals attached post-link (search
themes + audiences, best-effort warnings); the wizard collects and sends
signal hints. Live-verified alongside 8.3.

### Story 8.3: PAUSED-safe create + step-level error surface

**Given** any orchestrator failure mid-flow
**When** the error is returned to the wizard
**Then** it names the exact step that failed and what was rolled back
**And** the campaign is always created PAUSED and never auto-enabled
**And** enabling remains a human action (UI or explicit agent command).

**Status note (2026-06-10):** implemented same-day under Wassim's one-time
autonomous-execution authorization. Live-verified later the same day: campaign
23934110143 created PAUSED on 7178239091 (attempt 1 failed only on
DUPLICATE_CAMPAIGN_NAME from a pre-existing orphan and auto-removed its own
budget — rollback proven live). Step-aware `PMaxStepError` + rollback report
surface to the wizard as 502 detail. Wizard UX also gained "Draft with
Creative Director" (`POST /pmax/draft-copy`, landing-page-grounded, server
re-enforces ≤30/≤90 char limits), a campaign-brief field, and "why is Next
disabled" hints.

### Story 8.4: PMax video generator + YouTube upload

As an operator on the wizard's Video step,
I want a slideshow ad video generated from my chosen images with an
agent-written script, uploaded straight to YouTube,
So that the "≥1 YouTube video" PMax requirement never blocks campaign creation.

**Acceptance Criteria:**

**Given** 3-8 source images picked from the library (StepImages selections preseeded)
**When** I click "Write script & preview storyboard"
**Then** the script_generator role drafts a 20-30s storyboard (6-8 scenes:
logo/hero/broll/stat/cta) grounded in the brief + fetched landing page
**And** every scene shows its caption AND spoken line, both editable, via job+poll
**And** broll scenes only reference the operator's images (invalid refs round-robin recovered)

**Given** an approved storyboard
**When** I click "Render video"
**Then** generate_storyboard_reel (Hyperframes) renders in a background job with
progress polling, per-scene TTS sync on by default
**And** the MP4 lands in ad_assets with account_id set and previews inline

**Given** a rendered asset
**When** YouTube is not yet connected
**Then** "Connect YouTube" opens a one-time Google consent (youtube.upload scope,
localhost callback) and the refresh token persists to data/youtube_token.json
(chmod 600, gitignored)
**And** once connected, "Upload to YouTube" pushes the video as UNLISTED via
resumable videos.insert (worker thread) and the returned video id auto-appends
to the wizard's videoIds — manual ID paste stays available.

**Status note (2026-06-11):** implemented. Endpoints: POST/GET
/api/pmax/video/draft[/{id}], POST/GET /api/pmax/video/render[/{id}],
GET /api/youtube/{status,auth-url,oauth-callback}, POST /api/youtube/upload.
Live-verified: draft (grounded scenes off goldenvisas.mercan.com) + render
(asset 30f99346, 12.8s, account_id set). YouTube upload mock-tested only — no
refresh token exists until Wassim runs the one-time connect; OAuth client may
need http://localhost:8000/api/youtube/oauth-callback registered if it is a
Web (not Desktop) client, and the YouTube Data API enabled on the project.

**Extension (2026-06-11):** YouTube metadata generators — `POST
/api/pmax/video/metadata` (3 grounded title options ≤95c + description,
server-truncated) and `POST /api/pmax/video/frames` (ffmpeg stills →
thumbnail candidates); `/api/youtube/upload` accepts description +
thumbnail_asset_id (Pillow re-encode <2MB/1280px; unverified-channel 403
degrades to a warning, never fails the upload). The video step later gained
higgsfield AI scenes and a Soul talking intro via the video-engine track
(§ "Shipped Unplanned" — Epic 11 P1/P2).

---

## Epic 9: MCP Plan Tools (Phase 1.5)

Expose Scheduled Plans on the HTTP MCP bridge so plans can be created and
approved from any Claude Code session.

### Story 9.1: Plan tools on the bridge

As a user in any Claude Code session connected to the agent's MCP,
I want create_plan / list_plans / approve_plan / skip_plan / run_plan_now tools,
So that I can schedule and govern agent actions without opening the app.

**Acceptance Criteria:**

**Given** the MCP is connected with a valid bearer token
**When** I call `create_plan` with category budget|bids|status|geo
**Then** the plan is created approval-gated (mode=approval) and never executes spend before `approve_plan`
**And** `create_plan` with search_terms|audit|report|other defaults to auto mode
**And** one-time plans require `run_at`, recurring require a valid `recurrence` (daily/weekly/monthly forms)
**And** `list_plans` orders needs-attention (awaiting_approval|failed) first and truncates long text fields
**And** `approve_plan`/`skip_plan`/`run_plan_now` mirror the REST lifecycle exactly (same scheduler functions)

**Status note (2026-06-10):** implemented + verified (10 tools registered on the
bridge, plan tools present; service restarted healthy).

---

## Epic 10: Shopping Campaigns (Phase 1.5)

Greenfield. Completes sellable campaign-type coverage (Search ✓, PMax ✓ via
Epic 8, Shopping). Stories below are the planning baseline; expand/adjust at
implementation time.

### Story 10.1: Merchant Center linking

**Given** an account with a Google Merchant Center account
**When** the user links it (or the agent detects an existing link)
**Then** the link status + merchant id are stored per account and surfaced in the UI
**And** a missing link produces a clear, actionable error (not a silent failure).

### Story 10.2: Product feed awareness

**Given** a linked Merchant Center
**When** the agent loads campaign context
**Then** feed health (approved/disapproved product counts, top categories) is
available to personas and the campaign builder.

### Story 10.3: Shopping campaign creation flow

**Given** a linked Merchant Center with approved products
**When** the user runs the Shopping flow in the Campaign Builder (new type tile)
**Then** a Shopping campaign is created PAUSED with budget, priority, and
listing-group structure (all-products baseline, optional category splits)
**And** money-affecting settings respect the approval-gate philosophy.

### Story 10.4: Listing group management tools

Agent tools to inspect/split/negate listing groups post-launch (parity with
keyword management in Search).

### Story 10.5: Builder + MCP surface

Shopping appears in the Campaign Builder type picker and (later) as MCP draft
tools, matching the PMax pattern.

---

## Epic 13: Account Director Global Audit + Homepage v2 (Phase 1.6)

The homepage becomes the surface of ONE owned agent flow. Backend first: an
account-wide mode of the existing Team Audit engine
(`backend/app/services/workflow_orchestrator.py` — `campaign_id` is already
`Optional` end-to-end, verified 2026-07-04) that fans out per-campaign
specialist passes and synthesizes ONE ranked account report, persisted so the
home renders instantly. Frontend second: the "clean" layout reform per the
brief's DESIGN DIRECTION — one column, summoned chat, icon rail, progressive
disclosure, zero-state discipline. Tokens stay Shopify-calm light OKLCH
(`frontend/DESIGN.md`); this is layout reform, NOT a re-skin.

**Source:** PRD §8 Phase 1.6 (2026-07-04) · `research/homepage-redesign-brief.md`
**Depends on:** shipped foundations only — workflow orchestrator (V15), Scheduled Plans + scheduler (V17), campaigns table (V11), campaign_daily_metrics store, outcome tracker
**Build order:** 13.1 → 13.4 (backend engine + contracts), then 13.5 → 13.8 (homepage surfaces)

---

### Story 13.1: Account-wide planning mode in the workflow orchestrator

As an operator,
I want the Team Audit to run across the whole account when no campaign is bound,
So that the Director produces one ranked account-level report instead of per-campaign silos.

**Acceptance Criteria:**

**Given** `run_workflow()` is invoked with `campaign_id=None`
**When** the Director plans (Phase 1)
**Then** it plans ACROSS active campaigns: the roster is read from the `campaigns` table (`campaigns_repo.py`, V11 single source of truth), and the plan assigns per-campaign specialist passes
**And** each specialist pass executes with the concrete `campaign_id` it audits (existing `_run_group`/`_run_agent` params), so role notes, campaign memory, and `CampaignScopeMiddleware` stay campaign-bound per pass

**Given** all per-campaign passes complete
**When** the rollup runs
**Then** a cross-campaign debate phase surfaces conflicts (budget cannibalization, audience overlap, keyword collisions) and synthesis produces ONE ranked account report

**Given** an account with many active campaigns
**When** an account-wide run starts
**Then** campaigns per run are capped (new setting, e.g. `WORKFLOW_MAX_CAMPAIGNS`, default ~5, selected by recent spend; skipped campaigns are named in the report)
**And** the existing per-run cost cap (`WORKFLOW_MAX_COST_USD` → `_DEFAULT_BUDGET`) still degrades the run to synthesis-with-what-we-have rather than hard-failing; `_MAX_PARALLEL` unchanged
**And** Phase 0 stays ONE batched `sync_account()` pre-fetch serving every pass (no per-campaign re-sync)

**Files likely touched:** `backend/app/services/workflow_orchestrator.py`, `backend/app/routers/workflows.py`, `backend/app/services/campaigns_repo.py`, `backend/app/config.py`

**Status note (2026-07-04):** SHIPPED. `WORKFLOW_MAX_CAMPAIGNS=5` cap with
excluded campaigns NAMED (deterministic scope footer + `account_scope` SSE
event — no silent truncation); account runs are analysis-only (tools FORCED
`[]` on every pass); one UNBOUND cross-campaign debate pass per role;
synthesis emits structured findings JSON normalized server-side ($-desc sort,
total RECOMPUTED, never trusts LLM math); unparseable synthesis degrades to
prose-only. Beyond spec: `WORKFLOW_MAX_COST_USD` was materialized in Settings
— the documented env knob had never actually bound (pydantic ignored it).

---

### Story 13.2: Account report persistence + homepage read API

As the homepage,
I want the LATEST account audit persisted and instantly readable,
So that no live agent run ever happens on page load.

**Acceptance Criteria:**

**Given** an account-mode synthesis completes
**When** the run finishes
**Then** the ranked report persists as account-level rows (new `account_reports` table or a `workflow_runs`-derived read model — DB migration V19; latest-wins read semantics), analogous to campaign reports

**Given** the homepage loads
**When** it calls the latest-report endpoint (e.g. `GET /api/workflows/account-report/latest?account_id=`)
**Then** it returns the report + structured findings + `generated_at` + staleness metadata (age in minutes/hours for the "audited 2h ago · Run again" label)
**And** the endpoint answers from local SQLite in <1s — zero Google Ads API calls, zero agent runs

**Given** the fast-signals lane
**When** the homepage fix list is assembled
**Then** a deterministic aggregator merges always-fresh items with $-impact estimates: pending plan approvals (`plans` table), budget pacing alerts + search-term waste ($ with 0 conv, from `campaign_daily_metrics` / local search-term data), disapproved ads, tracking gaps — these render below/alongside the Account Director findings
**And** no report + no signals → an explicit empty payload the UI collapses (zero-state discipline)

**Files likely touched:** `backend/app/database.py` (V19), `backend/app/routers/workflows.py`, `backend/app/services/workflow_orchestrator.py`, `backend/app/services/metrics_store.py`, `backend/app/routers/plans.py` (read reuse)

**Status note (2026-07-04):** SHIPPED — V19 `account_reports` (latest-wins
UPSERT) + `GET /api/accounts/{id}/account-report` with staleness metadata +
`services/fast_signals.py` deterministic lane (pending approvals, budget
pacing, wasted spend, tracking gaps; ENABLED-only, $ only where honestly
derivable). Shipped WITH a runner-reliability fix the story didn't plan:
`services/workflow_runner.py` decouples execution from the SSE response
(detached task + replay hub — a client disconnect no longer orphans the run as
an eternal "running" zombie; startup + periodic zombie sweep added).

---

### Story 13.3: Findings → approvable actions contract

As an operator,
I want every finding to be a quantified, approvable ACTION,
So that the home page is a fix list, not prose.

**Acceptance Criteria:**

**Given** the account-mode synthesis prompt
**When** the Director produces the final report
**Then** it must emit structured findings JSON per finding: title, evidence summary, `dollar_impact_wk`, affected campaign id(s), `action_category` (the scheduler taxonomy: budget | bids | status | geo | search_terms | audit | report | other), proposed action detail — findings sorted by $-impact, report total = "Total recoverable: $X/wk"
**And** unparseable synthesis output degrades to a prose-only report (reuse the `_extract_json` fallback pattern — never fail the run)

**Given** a finding row's actions
**When** the user clicks [Approve]
**Then** a Scheduled Plan is created via the existing lifecycle (`routers/plans.py` + `scheduler.infer_mode()`): money/structure categories arrive approval-gated and execute only through `approve_plan()`
**And** [Approve once] creates a one-time plan (`run_at`=now) through the same gates; [Deny] marks the finding dismissed on the report row (excluded from the recoverable total, retained for audit)

**Given** any approved action executes
**When** the agent runs it
**Then** execution is per-campaign via `stream_agent_response` with the finding's campaign binding — `CampaignScopeMiddleware` is never bypassed; nothing on the homepage writes directly

**Files likely touched:** `backend/app/services/workflow_orchestrator.py`, `backend/app/routers/plans.py`, `backend/app/services/scheduler.py`, `backend/app/database.py` (finding dismissal state), `backend/app/services/agent.py` (reference only — scope guard path)

**Status note (2026-07-04):** SHIPPED — `services/finding_actions.py` + V20
`finding_actions` table. Actionable = scheduler taxonomy + ≥1 target campaign
(gating via `scheduler.infer_mode`, never overridden); advisory-only findings
surface info-only with `advisory_reason` (no mutation fabricated); Deny is a
tombstone keyed on a STABLE `finding_key` (sha1 of source|category|campaigns|
title — a deny sticks across re-audits until the finding's identity changes).
Endpoints: `GET /api/accounts/{id}/actions`, `POST .../actions/{finding_key}/decide`.

---

### Story 13.4: "Weekly account audit" Scheduled Plans ritual (auto lane)

As an operator,
I want the account audit to run itself weekly,
So that the fix list is fresh every week without me remembering to fire it.

**Acceptance Criteria:**

**Given** a plan with `action_category="audit"`, account scope (`campaign_id=None`), recurring recurrence (`weekly:mon:09:00` form)
**When** the scheduler fires it
**Then** it runs the account-wide workflow (Story 13.1) in the AUTO lane — analysis-only, no write tools, zero spend actions
**And** completion persists a new latest account report (Story 13.2) and the plan re-arms per existing recurring logic

**Given** the Plans UI or the homepage
**When** the user clicks "Enable weekly account audit"
**Then** the ritual plan is seeded one-click, with duplicate seeding prevented (max one active ritual per account)

**Given** the server was down at fire time or the run fails
**When** the next tick occurs
**Then** existing scheduler semantics apply — overdue plans fire on the next tick, failed runs surface needs-attention-first in the plans list

**Files likely touched:** `backend/app/services/scheduler.py`, `backend/app/routers/plans.py`, `backend/app/services/workflow_orchestrator.py`, `frontend/src/components/plans/PlansPanel.tsx`

**Status note (2026-07-04):** SHIPPED — `_run_account_audit` routes account-
scoped `audit` plans through the 13.2 workflow runner IN-PROCESS (not a
self-HTTP call); auto lane inherent (`infer_mode('audit')` = auto); idempotent
seeder `POST /api/plans/account-audit` (dup-guard returns the existing active
ritual); weekly recurring re-arm via existing `_complete()` logic. No
migration needed (V17 schema already supported account scope).

---

### Story 13.5: Homepage v2 shell — one column, summoned chat, icon rail

As an operator,
I want a clean single-focus home page,
So that the first thing I see is what to fix, not chrome.

**Acceptance Criteria:**

**Given** the home page renders
**When** an account is selected
**Then** it is ONE column led by the fix-list strip — the current `AccountOverview` composition in `ContentArea.tsx` (lifetime-total KPI cards + OutcomeDashboard + ConversationGraph + campaign grid) is replaced by the v2 layout with no competing panels
**And** the header shows: account · date-range picker (7d default, persisted) · Create Campaign

**Given** the chat
**When** on the HOME page
**Then** no always-open right rail: a floating button and ⌘K (existing `CommandPalette.tsx` path) summon the existing `ChatPanel` as an overlay/drawer; campaign pages keep their rail unchanged

**Given** the sidebar
**When** on the HOME page
**Then** it collapses to an icon rail by default and the campaign tree opens as a flyout (`Sidebar.tsx`), reclaiming width for the fix list

**Given** any empty data state
**When** the page composes
**Then** zero-state discipline holds — nothing renders empty ("0% success rate" ban), empty sections are absent, and the trust line "Every write is reviewed. Every write is reversible." appears under write surfaces
**And** all styling uses existing `frontend/DESIGN.md` OKLCH tokens — no new visual language, no dark

**Files likely touched:** `frontend/src/components/layout/ContentArea.tsx`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/components/layout/ChatPanel.tsx`, `frontend/src/components/layout/Header.tsx`, `frontend/src/components/CommandPalette.tsx`, `frontend/src/stores/appStore.ts`, `frontend/src/App.tsx`, `frontend/src/components/dashboard/HomeV2.tsx` (new)

**Status note (2026-07-04, tightened 2026-07-05):** SHIPPED — HomeV2 one-column
stack (FixListStrip / KpiCards / CampaignsRanked / AgentActivity),
HomeChatDock floating button + ⌘K overlay (home only), icon-rail sidebar with
campaign-tree flyout, Conversation Map moved to its own Conversations page.
2026-07-05 tighten pass: AgentActivity 4 blocks → 2 (interleaved "Recent
activity" cap 5 + slim Upcoming cap 3), CampaignsRanked top-6 disclosure +
ENABLED-only default scope toggle, vertical rhythm compressed.

---

### Story 13.6: Fix-list strip (hero)

As an operator,
I want a money-ranked fix list with inline approvals at the top of the home page,
So that I act on the account's biggest recoverable dollars in seconds.

**Acceptance Criteria:**

**Given** the latest account report + fast signals (Story 13.2)
**When** the strip renders
**Then** findings are money-ranked with header "Total recoverable: $X/wk" and a staleness label ("audited 2h ago · Run again") — Run again fires the account-wide workflow (reusing the `WorkflowPanel.tsx` / `/api/workflows/run` SSE path) and streams progress

**Given** a finding row
**When** displayed
**Then** it is one line: icon · title · $-impact/wk · affected-campaign chips · actions; clicking expands the specialist's evidence/reasoning (progressive disclosure — nothing verbose by default)
**And** inline [Approve] [Approve once] [Deny] call the Story 13.3 contract; [Review in chat] opens the summoned chat overlay pre-seeded with the finding

**Given** multiple approvable rows are selected
**When** the bulk bar appears
**Then** ONE bulk-action bar handles them (NotFair table pattern: compact table, generous row height, subtle dividers, threshold chips — no border-boxes-inside-boxes)

**Given** no findings exist
**When** the page composes
**Then** the strip is absent and the page collapses gracefully

**Files likely touched:** `frontend/src/components/dashboard/FixListStrip.tsx` (new), `frontend/src/lib/api.ts`, `frontend/src/components/workflow/WorkflowPanel.tsx` (run-again reuse), `frontend/src/components/plans/planHelpers.ts`

**Status note (2026-07-04):** SHIPPED — money-ranked rows w/ progressive
disclosure, inline [Approve][Approve once][Deny] against the 13.3 contract,
"needs sign-off" hint on gated rows, advisory rows button-less, [Review in
chat] pre-seeds the summoned chat. Deviation: denied rows are hidden on
refetch with NO fake Undo (the contract has no un-deny — spec's documented
fallback). Decision-state field is `status`, not `decision` (followed real
backend shapes, live-verified against :8000).

---

### Story 13.7: KPI cards with period deltas + sparklines

As an operator,
I want 4 context-rich KPI cards,
So that I see performance direction at a glance instead of naked lifetime totals.

**Acceptance Criteria:**

**Given** the local metrics store
**When** the homepage requests KPIs
**Then** a new period-over-period endpoint rolls up `campaign_daily_metrics` account-wide: current window vs prior window totals + per-day series for sparklines, window driven by the header date-range picker (7d default) — local SQLite only, no live Google Ads calls

**Given** the cards render
**When** data exists for the window
**Then** exactly 4 cards: Spend · Conversions · CPA · Conv rate — each value + Δ% vs prior period + sparkline, quiet labels, big type
**And** CPA/cost delta colors are inverted (lower = green); every metric displays its time window

**Given** a card has no data in the window
**When** the page composes
**Then** it does not render a zero-state (zero-state discipline)

**Files likely touched:** `backend/app/routers/reports.py` or `backend/app/routers/campaigns.py` (endpoint home — decide at build), `backend/app/services/metrics_store.py`, `frontend/src/components/dashboard/KpiCards.tsx` (new), `frontend/src/components/charts/PerformanceChart.tsx` (sparkline reuse), `frontend/src/lib/api.ts`

**Status note (2026-07-04):** SHIPPED — `GET
/api/accounts/{id}/metrics/overview?days=` (endpoint landed on the existing
account router in `workflows.py`; logic in `metrics_store.py`): 4 KPIs each
{value, prev_value, delta_pct} + per-day series, ENABLED-only, local SQLite
only. Zero-state honest throughout: nulls not zeros, delta null when the
prior window is empty (no fabricated deltas). KpiCards rewired to it on
2026-07-04 (replacing the interim two-fetch rollup).

---

### Story 13.8: Campaigns ranked section + Agent activity (Conversation Map to its own page)

As an operator,
I want ranked campaigns and an undo-able agent activity feed below the fix list,
So that the home answers "what should I do" and "what did the agent do" — not "where did I talk".

**Acceptance Criteria:**

**Given** the CAMPAIGNS section
**When** it renders
**Then** rows are ranked (active first, sorted by spend — `campaigns` table joined with `campaign_daily_metrics`): name · status chip · spend · conv · CPA · trend spark · threshold flag (⚠ below target) · last agent action · [Chat] [Report]
**And** when threshold flags exist, a bulk bar offers "Pause all N / Pick which" routed through the approval-gated plans path (Story 13.3 — never direct writes)

**Given** the AGENT ACTIVITY section (replaces Agent Performance + Conversation Map on home)
**When** it renders
**Then** (a) a change log with before→after values from the `recommendations` baseline snapshots (`outcome_tracker.py`) and [Revert] where the underlying tool supports an inverse operation (approval-gated; rows without inverse support show no revert), with the trust copy beneath; (b) Upcoming: next Scheduled Plans + weekly-ritual due card; (c) Recent threads (last 5 only, "View all" → Conversations page)
**And** "Agent Performance" (`OutcomeDashboard.tsx`) appears only after ≥1 measured action

**Given** the Conversation Map
**When** v2 ships
**Then** `ConversationGraph.tsx` moves to its own routed page with a nav item and is removed from the home

**Files likely touched:** `frontend/src/components/dashboard/CampaignsRanked.tsx` (new), `frontend/src/components/dashboard/AgentActivity.tsx` (new), `frontend/src/components/dashboard/{CampaignActivityFeed,OutcomeDashboard,ConversationGraph}.tsx`, `frontend/src/App.tsx`, `backend/app/routers/{outcomes,activity,plans}.py`, `backend/app/services/outcome_tracker.py` (revert executor — inverse-op coverage decided at build time)

**Status note (2026-07-04):** SHIPPED with two honesty deviations from the AC:
(a) the change log renders **read-only** — NO [Revert]: no inverse-op/undo
endpoint exists in the backend, so no affordance that would 404 was built;
(b) NO trend-spark column — the campaigns payload carries no per-day field,
so nothing was faked. Threshold flags are payload-derived only ("No
conversions"; "High CPA" relative to the account's blended CPA, only when a
real converting baseline exists); bulk "Pause N" routes one approval-gated
`status` plan per campaign through the 13.3 path. Before→after outcomes read
`GET /api/accounts/{id}/outcomes` ("measuring…" until the post-window lands).

---

## Shipped Unplanned (reconciled 2026-07-14 — tracked via research plans + feature log)

Work that shipped 2026-06-02 → 2026-07-14 without pre-written stories in this
file. Each track's authoritative spec lives in its `research/` plan; entries
below are the story-style reconcile record. Detailed per-session rows: `_bmad-output/feature-log.md` § Reconciled.

### Epic 11: Video Engine (Higgsfield scenes → Soul segments → finished video)
**Source:** `research/video-engine-plan.md` · reserved number per the Epic-13 numbering note

- **11.P1 — Higgsfield storyboard scenes (2026-06-11):** `{type:"higgsfield"}` scenes in the storyboard renderer via `services/higgsfield_scene.py` — prompt-hash clip cache in `ad_assets` (**V18**, zero-credit re-renders), CLI submit + mezzanine normalize (1080p/30fps) + freeze-frame tail; `premium_reel` xfade splice; PMax engine prefs (allow_higgsfield default OFF, model forced server-side, scene cap 2) + degrade-to-broll.
- **11.P2 — Soul talking segment + segment-timeline dispatcher (2026-07-04):** no lipsync model exists on the CLI → the plan's stated NON-LIPSYNC presenter fallback shipped: Soul still → veo3 image-to-video motion pass → script rides the per-scene VO bed. New `services/video_engine.py` (segments {storyboard|higgsfield|soul} COMPILED to one flat storyboard → existing normalize+xfade pipeline; caps 1 soul + 2 higgsfield) + `routers/video_engine.py` (`/estimate` + `/render` job+poll). Soul intro toggles in StudioPanel + PMaxWizard.
- **11.FV — Finished-video planner 15/30/60s (2026-07-07):** `plan_scenes(target_seconds, model_id)` auto-plans N clips at each model's MAX legal clip length (Veo enum-snap vs Kling int-cap); `MAX_HIGGSFIELD_SCENES` 2→8; whole-script VO sizes to the stitched duration; StudioPanel "Single clip / Finished video" sub-mode with a debounced credit gate ("Generate finished video (≈ N cr)" — no silent burn).

### Epic 12: Studio (panel, catalog, library, souls)
**Source:** `research/studio-redesign-brief.md` (APPROVED 2026-06-11) · reserved number per the Epic-13 numbering note

- **12.1 + 12.4 — Phase A (2026-06-11):** `GET /api/studio/models` server-side catalog (`services/model_catalog.py`, per-model duration/aspect constraints, liveness-cached, never 502s) + `StudioPanel.tsx` shared 480px slide-over (modes image|video|copy; `context` prop is the ONLY google-ads coupling — decoupling addendum honored) + PMax wiring (slots + YT thumbnail + copy drafting through the panel; post-crop preview at Google's exact ratio with "will be cropped" flag).
- **12.2 + 12.3 — Phase B (2026-06-11):** `AssetLibrary.tsx` (filter rail, search, detail modal, 2-up compare, offset pagination) + `SoulCreator.tsx` (guided 3-step train flow on the existing soul backend; no invented credit numbers) + hub slim-down (Library/Souls/Presets tabs + ONE Create button); `HiggsfieldGenerator.tsx` + `SoulCharactersPanel.tsx` deleted; off-palette tints killed to DESIGN.md tokens.

### Studio Redesign MVP: Two Studios, One Director
**Source:** `research/studio-redesign-plan.md` (drafted 2026-07-13; supersedes the Epic-12 brief's *layout*, its invariants still bind)

- **Epic A — the fork (2026-07-13):** `/studio` → StudioRouter → StudioHome (three door cards: AI Video "12 models · credits" / Kinetic "local · free" / Image) + 4 new routes; hub buttons removed.
- **Backend core + Brand Avatar (2026-07-13):** **V23** `studio_video_projects` (source of truth for storyboards — survives refresh/tab-close by design) + `brand_avatars`; `video_director` role (model-aware storyboard contract, VO-pacing word budgets, RULE 0) + `services/video_director.py` turn (context → scoped campaign-Director consult, 90s DEGRADE-not-block → decompose → 3 concepts → model-aware storyboard with server-side clamp/8-scene cap) + `routers/video_director.py` CRUD; cost/render stay OUTSIDE the LLM turn.
- **Epic B + C4 — AI Video workspace (2026-07-13):** 3-zone workspace (SETUP rail / STORYBOARD canvas / Director dock), model gallery sheet, per-scene cards + cost-gate footer (Render button always carries the credit total), dock rides the v2 turn transport (cursor-replay reconnect).
- **Epic D — Kinetic recomposition (2026-07-13):** 3 lanes (Brand Reel / Premium Reel incl. Brand Story / Presenter with ScriptGenerator folded in); render payloads verified byte-identical to legacy. Deviation: `VideoCreator.tsx` KEPT (plan §9.3 said delete — `ChatInput.tsx` still mounts it for the chat video flow; Kinetic no longer imports it).
- **Follow-ups (2026-07-14):** draft-stage timeout 45s→150s with a structured retryable error + "Retry draft" button; campaign dropdown `<optgroup>` Active/Paused; brief sources (Brief / From campaign / From landing page — **V24** `brief_source`); honest render failures (`error_class` taxonomy, auth pre-flight `GET /api/studio/auth-status`, logged-out disables Render); honest cost estimate (failed estimate can never render at a literal 0); URL-as-source-of-truth after project create (refresh-proof).

### Chat Orchestration v2 (MVP + accuracy hard-gate)
**Source:** `research/chat-orchestration-v2-plan.md` (2026-07-12) — born from the Panama QIP post-mortem

- **Epic 0 — stop/bleed P0 hotfix (2026-07-12):** frontend identity guards on every async chat writer (kills three cross-campaign bleed vectors by construction); backend `start_new_session` + process-group SIGTERM→SIGKILL + `_stop_requested` flag (closes the between-segments relaunch race); per-conversation proc registry retyped to sets (stop reaches every parallel child); stop no longer auto-resurrects via the queue drain.
- **Epic 1 — turn runner + event protocol (2026-07-12):** `chat_runner.py` detached turn tasks + replay hubs; **V22** `chat_turns`/`chat_turn_events` + `messages.turn_id` + `workflow_reports.origin`; `POST /message` → `{turn_id}` with `?stream=1` legacy passthrough; `GET /turns/{id}/stream?cursor`.
- **Epics 2+3 — orchestrated mode MVP (2026-07-12):** `chat_orchestrator.py` state machine (TRIAGE double-gate → RECALL → VERIFY → PLAN ≤3 specialists → DISPATCH → RESOLVE → SYNTHESIZE Director-only voice → GATE → WRITEBACK) + `task_ledger.py` recall over the 4 prior-output stores with the §8.2 staleness matrix; $5/6-min budget DEGRADE; frontend `OrchestrationLedger` live-activity UI + per-specialist stop; per-conversation toggle, default OFF (direct mode byte-identical).
- **Epic 4 — claim gate + provenance (2026-07-14):** `provenance.py` manifest (LIVE_API/PAGE_FETCH/LOCAL_STORE/MEMORY; `verified_ids()` excludes bare memory) + `claim_gate.py` deterministic post-pass — unverified ID tokens REWRITTEN in place, material numbers flagged (derived-math guard avoids false positives), page-state assertions traced to a real fetch; **the persisted message is the gated text**. Replaced the S7 stub.
- **Deferred (still open in the plan):** 1.4 token-level previews; 3.3 conflict/decision rows (render seams present); Epic 5 writeback polish; Epic 6 persona overhaul; Epic 7 migration/eval (incl. the Panama replay eval); Epic 8 Director of Directors.

### Dashboard v2.1: Always-Fresh Data + Clarity + Effortless Home
**Source:** `research/dashboard-freshness-clarity-plan.md` (2026-07-12) — root cause: the scheduled metrics sync had written ZERO rows since April (ghost-column INSERT swallowed by a bare except) while burning ~3,300 API ops/run

- **Epic A — the data is real again (2026-07-12, A1–A5):** sync rewrite to ONE read-only GAQL `search_stream` per account (~3,300 ops → 2); **V21** `sync_state` ledger keyed on `data_through_date` NEVER `synced_at`; watchdog + heartbeat + timeout fence + backoff + boot-sync; freshness envelopes on the home endpoints + `<FreshnessChip>` + `useSyncNow`; self-heal `maybe_kick_sync` (single-flight, stampede-guarded, reads never block on Google); cache honesty (stale-serve marked, no laundering re-stamps, upsert stops NULLing roster fields).
- **Epic B — every number explains itself (2026-07-12, B1–B5):** KpiCards three-state honesty (pipeline-stale renders VISIBLY amber instead of vanishing); `InfoHover` explainers with real window dates; CampaignsRanked neutral "no data yet" chip; FixListStrip dual staleness ("audited Xh ago · on data through …"); B4 live-truth campaign header (`LiveHeadChip` — live control-plane read preferred over roster cache) + scheduler live pre-read before approval analysis AND apply; B5 context bar (CID only — currency/tz not exposed client-side, nothing fabricated).
- **Epic C — push + effortless home (2026-07-12, C1–C5):** `useAccountEvents` SSE invalidation (`sync_completed`/`external_change`); C2 home-as-default-route (killed the last-campaign restore hijack; `/campaign/:id` deep links; `lastCampaignId` powers "Continue where you left off"); C3 keyboard chords (`g h`/`g c`/`g p`/Esc) + palette Navigate group + rail Home; C4 skeletons + parallel prefetch; C5 "Changed outside the app" block + absolute-time hovers. Also killed the B2 bidding-strategy fallback LIE (`bidding_strategy || campaign_type` → honest '—').
- **Deferred:** B2 `new` chip (created_at false-positive risk on rebuilt DBs); C5 change_event GAQL attribution; currency/tz in the context bar; small-window table scroll.

### Agent Quality Hardening (WS1–WS5)
**Source:** `research/agent-quality-hardening-plan.md` — Panama QIP post-mortem P0s

- **WS1 (2026-07-08):** `ad_update_ad_final_urls` MCP tool + `POST /api/operations/ad/final-urls` — in-place landing-page switch preserving pins/history/ad-id (was: destructive delete+recreate).
- **WS2–WS5 (2026-07-08):** verify-before-diagnose (`fetch_ad_landing_pages` injected into BOTH campaign-context paths + global guardrail); role-notes freshness (⚠️ STALE >7d, labeled never dropped); ID integrity (no conversion/GTM/AW- ID unless live-pulled this session); Team Audit premise gate + ~200-word cap + forced "What would change my conclusion:" line. Additive only — no persona prompt rewritten.

### MCP Tool-Surface Hardening (2026-07-05)
**Source:** unplanned P0 audit gap-fixes + harness (feature-log rows)

- **Keyword status tool:** `update_ad_group_criterion_status` (pause/enable a keyword — the agent previously could not).
- **Ad-extension creators:** `create_sitelink_asset` / `create_callout_asset` / `create_structured_snippet_asset` / `create_call_asset` — mcp_main advertised these; the tools didn't exist.
- **Audit Phase 2:** un-stubbed `attach_shared_set_to_campaigns` (working code sat under a stray `NotImplementedError`); fake-success stubs (value-rule/data-link/batch add-ops) converted to honest `NotImplementedError`s — the agent can no longer believe a mutation happened when nothing did; capability blurbs corrected.
- **Fail-closed dry-run harness:** `dry_run.py` + `validate_all_tools.py` force `validate_only` at the SDK layer on every mutate (unforceable → quarantined, never sent); widened with real-resource harvest to 314 tools / 237 mutates → after fixing the 9 real bugs it surfaced: **90 PASS / 0 FAIL / 147 SKIP**, zero unflagged mutates ever executed.

### Platform / misc (unplanned)

- **2026-06-02:** app-wide re-skin to Shopify-calm light (OKLCH token layer; `frontend/DESIGN.md` + `PRODUCT.md` born).
- **2026-06-10:** default model Opus 4.8 → **Fable 5** (`claude-fable-5[1m]`; plain fallback; aliases kept).
- **2026-06-11:** CLI discovery prefers the native Claude binary over stale npm cli.js in every subprocess spawn.
- **2026-07-06:** Panama QIP + Greece GV Oman/Jordan keyword research client deliverables (read-only live Keyword Planner pulls; zero fabricated numbers).
- **2026-07-14:** legacy chat `?stream=1` restore (P0 "thinks forever" fix) + ChatPanel scope-bug fix unblocking `vite build`.

---

## Dependency Graph

```
Epic 1: Multi-Account Foundation ──────┐
    │                                  │
    ├───► Epic 2: Marketing Intelligence
    │         │
    ├───► Epic 3: Dashboards & Charts ◄─┘
    │
    ├───► Epic 4: Conversation Upgrade
    │
    ├───► Epic 5: Guidelines Enhancement ◄── Epic 2
    │
    └───► Epic 6: Advanced Editing ◄── Epic 2, Epic 4
              │
              ▼
         Epic 7: Public Release Prep (depends on all)
```

## Implementation Order

| Order | Epic | Est. Stories | Rationale | Status (2026-07-14) |
|-------|------|-------------|-----------|---------------------|
| 1st | Epic 1: Multi-Account Foundation | 7 stories | Foundation — everything depends on this | Done |
| 2nd | Epic 2: Marketing Intelligence | 5 stories | Enriches agent and dashboard | Done |
| 3rd | Epic 5: Guidelines Enhancement | 3 stories | Quick, builds on Epic 1+2 | Done |
| 4th | Epic 4: Conversation Upgrade | 3 stories | Independent, enhances daily workflow | Done |
| 5th | Epic 3: Dashboards & Charts | 5 stories | Visual impact, needs Epic 1+2 data | Done |
| 6th | Epic 6: Advanced Editing | 5 stories | Power features, needs intelligence layer | Done |
| 7th | Epic 7: Public Release | 5 stories | Final polish before launch | **Open** |
| 8th | Epic 8: PMax Finalization | 4 stories | ~70% built — fastest coverage win (Phase 1.5) | Shipped 2026-06-10→11 |
| 9th | Epic 9: MCP Plan Tools | 1 story | Small, unlocks scheduling from any Claude Code | Shipped 2026-06-10 |
| 10th | Epic 10: Shopping Campaigns | 5 stories | Greenfield — largest Phase 1.5 lift | **Open** |
| 11th | Epic 13: Account Director + Homepage v2 | 8 stories | Homepage becomes the audit's surface (Phase 1.6); backend engine 13.1–13.4 before UI 13.5–13.8 | Shipped 2026-07-04→05 |

**Total: 7 epics, 33 stories for Phase 1 · +3 epics / 10 stories (Phase 1.5, stories added 2026-06-10; Epics 8–9 shipped same day, Epic 10 pending)**

**Phase 1.6 (2026-07-04): +1 epic (Epic 13) / 8 stories — Account Director global audit + Homepage v2. SHIPPED 2026-07-04→05.**

**Phase 1.7 (reconciled 2026-07-14): the § "Shipped Unplanned" ledger above — Epics 11/12 + Studio Redesign MVP, Chat Orchestration v2 (E0/E1/E2-3/E4), Dashboard v2.1 (A/B/C), WS1–WS5 hardening, MCP tool-surface hardening. Specs live in their `research/` plans; PRD §8 Phase 1.7 is the summary.**

---

*Open items (2026-07-14): Epic 7 (public release), Epic 10 (Shopping), and the deferred remainders listed per-track in § "Shipped Unplanned" (Chat-orch Epics 5–8, Dashboard deferred chips/attribution, Studio Virality/Clipper + lipsync presenter).*
