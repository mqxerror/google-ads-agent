# Google Ads API — Application Design Document

**Prepared for:** Google Ads API Standard Access Application
**Applicant:** PixelCrafted Media
**Website:** https://pixelcraftedmedia.com
**Developer Token MCC:** 689-594-9945 (MQXDev Manager Account)
**Contact:** mqxdev@gmail.com
**Date:** April 2026

---

## 1. Application Overview

**Application Name:** Google Ads Campaign Manager

**Description:**
Google Ads Campaign Manager is a private, internal web application built by PixelCrafted Media to manage Google Ads campaigns for our agency's client accounts. The tool combines a campaign browsing interface, an AI-assisted chat agent, and direct Google Ads API access to streamline day-to-day campaign management, keyword optimization, and performance reporting across our managed accounts.

The application runs locally on the agency operator's machine and is not publicly accessible. It is not a SaaS product — it is an internal productivity tool used exclusively by authorized agency staff.

**Problem it solves:**
Managing multiple client Google Ads accounts across different campaign types (Search, Display), industries (immigration, professional services), and optimization goals requires jumping between campaign dashboards, keyword tools, and reporting interfaces. This application consolidates those workflows into one interface powered by a team of specialized AI agents — each with deep expertise in a specific domain of Google Ads management.

---

## 2. Who Uses the Application

| User Type | Description |
|-----------|-------------|
| Agency Owner / Operator | Primary user. Manages all client accounts. Runs the application on a local machine. |
| Agency Staff (future) | Additional team members who will use the tool to manage assigned client accounts. |

The application is **not** accessible by end clients or the general public. Client Google Ads accounts are managed on behalf of clients through the agency's MCC structure.

**Account Structure:**

| Level | Account ID | Account Name |
|-------|-----------|-------------|
| Manager (MCC) | 689-594-9945 | MQXDev |
| Sub-Manager | 719-264-8347 | Wassim |
| Client Account 1 | 717-823-9091 | Mercan Group Main Account |
| Client Account 2 | (planned) | New client — immigration niche |
| Client Account 3 | (planned) | New client — professional services |

---

## 3. How the Application Uses the Google Ads API

The application uses the **Google Ads Python Client Library (v29.2.0)** with OAuth2 credentials stored locally. All API calls are made server-side from the Python FastAPI backend — no API credentials are ever exposed to the browser.

### 3.1 API Operations Performed

| Category | Operations | Purpose |
|----------|-----------|---------|
| **Reporting & Search** | `GoogleAdsService.Search` / `SearchStream` | Fetch campaign metrics, ad group data, keyword performance, search term reports, impression data |
| **Campaign Management** | `CampaignService.MutateCampaigns` | Create, update, pause/enable campaigns |
| **Budget Management** | `CampaignBudgetService.MutateCampaignBudgets` | Create and update campaign budgets |
| **Ad Group Management** | `AdGroupService.MutateAdGroups` | Create and update ad groups |
| **Keyword Management** | `AdGroupCriterionService.MutateAdGroupCriteria` | Add keywords, update bids, remove keywords, add negative keywords |
| **Ad Creation** | `AdGroupAdService.MutateAdGroupAds` | Create and update responsive search ads (RSA) |
| **Conversion Tracking** | `ConversionActionService.MutateConversionActions` | Create and manage conversion actions |
| **Bidding Strategies** | `BiddingStrategyService.MutateBiddingStrategies` | Create Target CPA, Target ROAS, Maximize Conversions strategies |
| **Targeting / Geo** | `GeoTargetConstantService.SuggestGeoTargets` | Suggest location IDs for geographic targeting |
| **Recommendations** | `RecommendationService.GetRecommendations`, `ApplyRecommendation` | Fetch and apply Google optimization recommendations |
| **Keyword Planning** | `KeywordPlanIdeaService.GenerateKeywordIdeas` | Keyword research and search volume estimates |
| **Customer Management** | `CustomerService.ListAccessibleCustomers` | List accounts accessible under the MCC |
| **Audience Management** | `UserListService`, `AudienceService` | Create and manage remarketing and custom audiences |
| **Campaign Criteria** | `CampaignCriterionService.MutateCampaignCriteria` | Add location targeting, language targeting, negative keyword lists |

### 3.2 AI Agent Integration via Model Context Protocol (MCP)

The application exposes all 87 Google Ads API operations as **MCP (Model Context Protocol) tools**. These tools are made available to the AI agent layer, allowing specialized agents to call Google Ads API operations directly as part of their analysis and execution workflows.

**How MCP works in this application:**
- The Python FastAPI backend runs an embedded **FastMCP server** that wraps every Google Ads service operation as a named tool (e.g., `search_search_campaigns`, `keyword_add_keywords`, `ad_create_responsive_search_ad`)
- The Claude AI agent layer connects to this MCP server and can call any tool autonomously during a conversation
- The agency operator approves high-impact actions (pausing campaigns, changing budgets) before the agent executes them
- All MCP tool calls ultimately invoke the **Google Ads Python Client Library** — MCP is the interface layer, the API is the execution layer

**MCP tool categories exposed:**
- 20+ read/reporting tools (GAQL search, campaign metrics, keyword data, search term reports)
- 15+ campaign and ad group management tools
- 10+ keyword management tools
- 10+ ad creation and management tools
- 10+ targeting, bidding strategy, and conversion tools
- Additional tools for recommendations, keyword planning, audience management

### 3.3 Specialized AI Agents with Marketing Domain Expertise

The application uses **Anthropic Claude** (via the Claude SDK) as the AI backbone, but rather than a single general-purpose assistant, it deploys a roster of **specialized AI agents** — each trained with a distinct marketing role and domain knowledge. The active agent is selected based on the task at hand.

**Deployed specialist agents:**

| Agent Role | Specialty | Key Responsibilities |
|------------|-----------|---------------------|
| **PPC Strategist** | Campaign performance, bid strategy, pacing | Daily performance reviews, bid adjustments, budget pacing, A/B test interpretation |
| **Keyword Specialist** | Keyword research, match types, negative keywords | Search term audits, negative keyword recommendations, keyword expansion |
| **Ad Copy Specialist** | Responsive Search Ad creation and testing | Headline/description analysis, copy frameworks, ad strength optimization |
| **Analytics Analyst** | Conversion tracking, attribution, reporting | Conversion tracking verification, GAQL query authoring, ROAS/CPA analysis |
| **GTM Specialist** | Google Tag Manager, tag implementation | GTM container audits, tag creation, trigger debugging, conversion verification |
| **Competitor Intelligence Analyst** | Auction insights, competitive positioning | Impression share analysis, competitor identification, gap mapping |
| **Agency Director** | Cross-account oversight, strategy | Account health reviews, escalation handling, onboarding new clients |

Each agent is loaded with:
- The relevant campaign guidelines and business context for the active account
- Historical decision logs and change history
- Live campaign data fetched via MCP tools
- Role-specific expertise and analytical frameworks

This multi-agent design ensures that the right domain knowledge is applied to each task — a keyword audit uses the Keyword Specialist's expertise, while conversion tracking issues route to the GTM Specialist.

### 3.4 Query Frequency

The application is designed for **on-demand use** by 1–3 agency operators. API calls are triggered by:
- Manual user actions (browsing campaigns, requesting analysis, executing changes)
- Background sync jobs that run at most once per hour to refresh cached campaign data

The application does **not** run continuous polling or batch operations. It is not a high-volume automated system.

**Estimated monthly API operations:** 30,000–80,000 (well within Standard Access limits)

### 3.5 GAQL Queries Used

The application executes Google Ads Query Language (GAQL) queries via `GoogleAdsService.Search` for:
- Campaign performance metrics (impressions, clicks, cost, conversions, CTR, CPA)
- Ad group and keyword metrics
- Search term reports
- Ad performance data
- Budget pacing data
- Landing page performance

All queries are parameterized and constrained to specific customer IDs in the MCC hierarchy. No cross-account data is mixed.

---

## 4. Application Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Agency Operator                     │
│              (local browser session)                 │
└────────────────────┬────────────────────────────────┘
                     │ HTTP (localhost)
┌────────────────────▼────────────────────────────────┐
│            React Frontend (Vite/TypeScript)          │
│   Campaign Browser | Chat Panel | Guidelines Editor  │
└────────────────────┬────────────────────────────────┘
                     │ REST API / WebSocket (localhost:8000)
┌────────────────────▼────────────────────────────────┐
│            Python FastAPI Backend                    │
│  ┌─────────────┐  ┌───────────────────────────────┐  │
│  │ Campaign    │  │     AI Agent Layer             │  │
│  │ Router      │  │  ┌─────────────────────────┐  │  │
│  └──────┬──────┘  │  │  Anthropic Claude SDK   │  │  │
│         │         │  │  (claude-sonnet-4-6)     │  │  │
│  ┌──────┐         │  └────────────┬────────────┘  │  │
│  │Guide-│         │               │ selects agent  │  │
│  │lines │         │  ┌────────────▼────────────┐  │  │
│  │Mgr   │         │  │  Specialized Agents     │  │  │
│  └──────┘         │  │  PPC Strategist         │  │  │
│                   │  │  Keyword Specialist     │  │  │
│                   │  │  Ad Copy Specialist     │  │  │
│                   │  │  Analytics Analyst      │  │  │
│                   │  │  GTM Specialist         │  │  │
│                   │  │  Competitor Intel       │  │  │
│                   │  │  Agency Director        │  │  │
│                   │  └────────────┬────────────┘  │  │
│                   └───────────────┼───────────────┘  │
│                                   │ MCP tool calls    │
│         ┌─────────────────────────▼───────────────┐  │
│         │   FastMCP Server (87 Google Ads tools)   │  │
│         └─────────────────────────┬───────────────┘  │
│                                   │                   │
│         ┌─────────────────────────▼───────────────┐  │
│         │   Google Ads Python Client Library       │  │
│         │   (v29.2.0, OAuth2)                      │  │
│         └─────────────────────────┬───────────────┘  │
└───────────────────────────────────┼───────────────────┘
                                    │ HTTPS (Google Ads API)
                         ┌──────────▼──────────┐
                         │  Google Ads API v19  │
                         └─────────────────────┘
```

**Key architectural properties:**
- Entire application runs on localhost — no external server
- API credentials never leave the local machine
- OAuth2 tokens stored encrypted in a local `.env` file
- SQLite database for conversation history and settings (no cloud database)
- No third-party data sharing

---

## 5. Data Handling and Security

### 5.1 Data Storage

| Data Type | Storage Location | Retention |
|-----------|-----------------|-----------|
| OAuth2 access/refresh tokens | Local `.env` file (git-ignored) | Until revoked |
| Developer token | Local `.env` file | Until revoked |
| Campaign metrics cache | Local SQLite database | 1 hour TTL |
| Conversation history | Local SQLite database | User-controlled |
| Campaign guidelines | Local filesystem (markdown files) | Persistent |

### 5.2 Security Controls

- No API credentials are stored in source control (`.env` is git-ignored)
- No API data is transmitted to third parties
- Application is accessible only on localhost — no public network exposure
- OAuth2 scopes are limited to `https://www.googleapis.com/auth/adwords` (required minimum)
- Client account data is isolated per account ID — no cross-account data mixing

### 5.3 Data Used

The application reads and writes the following Google Ads data:
- Campaign configuration (name, status, budget, bidding strategy, targeting)
- Performance metrics (impressions, clicks, cost, conversions, CTR, CPA, ROAS)
- Keywords (text, match type, bid, quality score)
- Ads (headlines, descriptions, status, performance)
- Search terms (query text, match type, clicks, cost)
- Conversion actions (name, type, value settings)
- Geographic targets

This data is used exclusively for:
1. Displaying campaign performance to the agency operator
2. Providing AI-powered analysis and recommendations
3. Executing approved campaign changes on behalf of the client

---

## 6. Compliance with Google Ads API Terms of Service

### 6.1 Terms of Service Compliance

PixelCrafted Media confirms:
- The application will be used only for managing accounts to which PixelCrafted Media has authorized access through the MCC structure
- We do not scrape, resell, or commercially redistribute Google Ads data
- All API usage is for legitimate campaign management purposes
- The application does not automate ad serving or click fraud in any form
- Changes to client campaigns are made only with client authorization

### 6.2 Rate Limiting

The application implements:
- Response caching with 1-hour TTL to minimize redundant API calls
- Rate limit detection — when a 429 (RESOURCE_EXHAUSTED) error is returned, cached data is served and the user is notified
- No parallel bulk queries — operations are sequential and on-demand

### 6.3 Required API Access

We are requesting Standard Access because:
1. Basic Access (~15,000 operations/day) is insufficient for active campaign management across 3+ accounts
2. Daily dashboards, keyword audits, search term reviews, and optimization workflows require consistent API availability throughout the business day
3. As the agency grows to additional clients, operation volume will increase proportionally

---

## 7. Business Context

**PixelCrafted Media** is a digital marketing agency specializing in Google Ads campaign management for small and medium businesses. We are an early-stage agency with:

- 1 active client account (Mercan Group — immigration consulting)
- 2 additional client accounts onboarding soon (professional services and immigration niches)
- All accounts managed through our MCC (MQXDev, ID: 689-594-9945)

Our primary use case is Search campaign management: keyword strategy, negative keyword audits, bid optimization, ad copy testing, conversion tracking setup, and performance reporting.

The Google Ads Campaign Manager tool is our internal system of record for all Google Ads work. It replaces manual Google Ads UI workflows with an integrated AI-assisted management environment, improving accuracy and reducing the time required to execute best-practice campaign management.

---

## 8. Sample Workflow Demonstrating API Usage

**Workflow: Weekly Keyword Audit (with Specialized Agent + MCP)**

1. Agency operator opens the application and selects client account (717-823-9091)
2. Application fetches campaign list via `GoogleAdsService.Search` (GAQL query for campaigns + metrics)
3. Operator selects "Greece Golden Visa" campaign and types: *"Run a keyword audit"*
4. Application routes the request to the **Keyword Specialist** agent, loading it with campaign guidelines, business context, and the current campaign's data
5. The Keyword Specialist calls the MCP tool `search_search_keywords` to fetch keyword performance data
6. The agent calls `google_ads_search_google_ads` with a custom GAQL query to retrieve the 30-day search term report
7. The Keyword Specialist analyzes the data using its domain expertise — identifying high-spend zero-conversion keywords and irrelevant search term patterns
8. The agent presents a prioritized list of recommended negative keywords with strategic rationale
9. Operator approves the recommendation
10. The Keyword Specialist calls the MCP tool `campaign_criterion_add_negative_keyword_criteria` to execute the change
11. Operator reviews the confirmation; the change is logged in campaign guidelines

**API calls in this workflow:** ~4 read queries (via MCP tools) + 1 write mutation. All on-demand, agent-driven, with operator approval for write actions.

---

## 9. Contact and Verification

| Field | Value |
|-------|-------|
| Company | PixelCrafted Media |
| Website | https://pixelcraftedmedia.com |
| MCC Account ID | 689-594-9945 |
| Developer Token Email | mqxdev@gmail.com |
| Application Type | Internal agency tool (private, not public-facing) |
| Commercial Product? | No |
| Third-Party AI? | Yes — Anthropic Claude (currently claude-sonnet-4-6). Gemini integration planned for future versions. |
| Specialized Agents? | Yes — 7 domain-specific marketing agents (PPC Strategist, Keyword Specialist, Ad Copy Specialist, Analytics Analyst, GTM Specialist, Competitor Intelligence Analyst, Agency Director) |
| MCP Integration? | Yes — all 87 Google Ads API operations are exposed as Model Context Protocol tools, allowing agents to query and execute API calls autonomously with operator approval for high-impact actions |

---

*This document was prepared to support the Google Ads API Standard Access application for PixelCrafted Media. All information is accurate as of April 2026.*
