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
**Status:** Draft
**Scope:** Phase 1 (Foundation Upgrade)

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

| Order | Epic | Est. Stories | Rationale |
|-------|------|-------------|-----------|
| 1st | Epic 1: Multi-Account Foundation | 7 stories | Foundation — everything depends on this |
| 2nd | Epic 2: Marketing Intelligence | 5 stories | Enriches agent and dashboard |
| 3rd | Epic 5: Guidelines Enhancement | 3 stories | Quick, builds on Epic 1+2 |
| 4th | Epic 4: Conversation Upgrade | 3 stories | Independent, enhances daily workflow |
| 5th | Epic 3: Dashboards & Charts | 5 stories | Visual impact, needs Epic 1+2 data |
| 6th | Epic 6: Advanced Editing | 5 stories | Power features, needs intelligence layer |
| 7th | Epic 7: Public Release | 5 stories | Final polish before launch |

**Total: 7 epics, 33 stories for Phase 1**

---

*Next step: Begin implementation starting with Epic 1, Story 1.1.*
