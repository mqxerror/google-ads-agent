---
type: project-context
project: Google Ads Campaign Manager
date: 2026-03-26
classification: brownfield-adjacent
---

# Project Context - Existing Codebase Reference

## Overview

This web application integrates with an existing Google Ads MCP server. The MCP server is **not being modified** - it is consumed as-is by the Claude Code SDK agent and optionally by direct Python imports for read-only data queries.

## Existing Codebase: Google Ads MCP Server

**Location:** `C:\Users\Wassim\Documents\google ads\google-ads-mcp\`

### Structure

```
google-ads-mcp/
├── main.py                    # MCP server entry point (FastMCP server registration)
├── src/
│   ├── sdk_client.py          # Google Ads SDK client (OAuth, singleton pattern)
│   ├── utils.py               # Shared utilities
│   ├── servers/               # 89+ MCP server implementations (legacy flat structure)
│   └── services/              # Organized service implementations
│       ├── account/           # 11 services (customer, billing, user access, etc.)
│       ├── ad_group/          # 15 services (ad group, ads, keywords, criteria, etc.)
│       ├── assets/            # 10 services (asset, asset group, asset set, etc.)
│       ├── audiences/         # 10 services (user list, custom audience, remarketing, etc.)
│       ├── bidding/           # 5 services (bidding strategy, budget, seasonality, etc.)
│       ├── campaign/          # 17 services (campaign, budget, draft, label, etc.)
│       ├── conversions/       # 11 services (conversion action, upload, goal, etc.)
│       ├── data_import/       # 5 services (batch job, offline data, user data, etc.)
│       ├── metadata/          # 3 services (fields, search, service)
│       ├── planning/          # 9 services (keyword plan, reach plan, ideas, etc.)
│       ├── product_integration/ # 5 services
│       ├── shared/            # 4 services (shared set, label, customizer, etc.)
│       └── targeting/         # 2 services (geo target, negative criterion)
├── tests/                     # 72+ test files
├── refs/                      # Reference docs (fastmcp.llms.txt, googleads.llms.txt)
├── .env                       # Google Ads API credentials
├── TRACKER.md                 # Implementation progress (90/103 = 87.4%)
├── CLAUDE.md                  # Development guidelines
└── pyproject.toml             # uv package management
```

### Key Files for Integration

#### `main.py` (Entry Point)
- Registers all 90+ MCP server instances with the FastMCP framework
- Defines server groups (campaign, ad_group, assets, audiences, bidding, conversions, etc.)
- Contains the complete tool instructions text
- **How the web app uses it:** Claude Code SDK agent connects to this MCP server

#### `src/sdk_client.py` (Google Ads Client)
- Wraps `google.ads.googleads.client.GoogleAdsClient`
- Implements OAuth 2.0 authentication with refresh token flow
- Singleton pattern with lazy initialization
- Loads credentials from `.env` file
- **How the web app uses it:** Backend imports this directly for read-only API queries (bypassing the AI agent for simple data fetching)

#### `.env` (Credentials)
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (6895949945)
- **How the web app uses it:** Shares this file or copies credentials to its own config

### API Version Notes

- MCP server imports types from `google.ads.googleads.v20`
- SDK is v29.2.0 which uses v23 service clients
- When making direct API queries (not through MCP), must use v23 request types
- This is a known issue documented in `CLAUDE.md`

### Service Coverage

- 90 of 103 Google Ads API services implemented (87.4%)
- 100% coverage in: Account, Ad Groups, Bidding, Campaign, Conversions, Data Import, Metadata, Planning, Product Integration, Shared
- Gaps (13 services): Mostly asset-related (asset_group_listing_group_filter, asset_set_asset, customer_asset_set, travel_asset_suggestion) and audience (user_list_customer_type, keyword_theme_constant) plus a few others
- Gaps are in non-critical areas for the current use case

## Existing Campaign Guidelines Files

**Location:** `C:\Users\Wassim\Documents\google ads\`

| File | Purpose | Size |
|------|---------|------|
| `CAMPAIGN_GUIDELINES.md` | Main guidelines: global rules + all campaign sections for Mercan Group | ~350 lines |
| `MENA_CAMPAIGN_GUIDELINES.md` | MENA/Arabic campaign-specific guidelines | Region-specific |
| `GREECE_CAMPAIGN_GUIDELINES.md` | Greece Golden Visa campaign guidelines | Region-specific |
| `ARABIC_CAMPAIGN_PLAN.md` | Arabic campaign planning document | Planning |
| `ARABIC_MENA_CAMPAIGN_PLAN.md` | MENA region campaign plan | Planning |

### Guidelines Structure (from CAMPAIGN_GUIDELINES.md)

```markdown
# Google Ads Campaign Management Guidelines

## Account Structure
(table of Manager, Sub-Manager, Client accounts)

## Global Rules (Apply to ALL Campaigns)
### 1. Change Management
### 2. Conversion Tracking Rules
### 3. Conversion Actions Registry
### 4. Negative Keyword Policy
### 5. Bidding Strategy Rules

## Campaign: [Campaign Name]
### Overview (table of campaign settings)
### Conversion Tracking
### Ad Groups (table)
### Keywords (table)
### Negative Keywords
### Performance History (table with daily metrics)
### Known Issues (numbered list with status)
### Change Log (table with date, change, reason, impact)
### Fix Plan (ordered list of fixes)
```

This structure MUST be preserved by the web app's guidelines editor.

## Account Hierarchy (Current)

```
Manager (MCC): 6895949945 - MQXDev
  └─ Sub-Manager: 7192648347 - Wassim
       ├─ Client: 7178239091 - Mercan Group Main Account (active)
       │    ├─ Portugal Golden Visa (23636342079)
       │    ├─ Greece Golden Visa (22551124974)
       │    ├─ MENA Golden Visa (23688200557)
       │    └─ (7+ other campaigns)
       └─ Client: 1949155935 - (unnamed, MSG Experts - paused)
```

## Integration Points Summary

| Integration | Method | Direction |
|-------------|--------|-----------|
| MCP Server → Claude Code SDK | MCP protocol (stdio) | Bidirectional |
| sdk_client.py → Backend | Python import | Read-only queries |
| .env credentials → Backend | File read | Configuration |
| Guidelines .md → Backend | Filesystem read/write | Bidirectional |
| Backend → Frontend | REST + SSE/WebSocket | Bidirectional |
