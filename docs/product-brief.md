---
type: product-brief
project: Google Ads Campaign Manager
date: 2026-03-26
author: Wassim
---

# Product Brief - Google Ads Campaign Manager

## Vision

A local web application that replaces Claude Desktop as the primary interface for managing Google Ads campaigns. The app combines a visual campaign browser with an AI agent (powered by Claude Code SDK) that has automatic access to per-campaign guidelines and 90+ Google Ads API tools.

## Problem Statement

### Current Workflow (Claude Desktop + MCP Server)

Wassim manages Google Ads campaigns for Mercan Group (Portugal, Greece, MENA Golden Visa programs) through Claude Desktop connected to a custom MCP server with 90 implemented Google Ads API services. While the MCP server is powerful, Claude Desktop's general-purpose UI creates friction:

1. **No persistent context** - Every new session requires re-loading campaign guidelines. The agent doesn't "remember" campaign rules unless explicitly told to read the guidelines file.
2. **No visual navigation** - Switching between campaigns requires typing customer IDs and campaign IDs. There is no click-to-navigate campaign tree.
3. **No visual metrics** - Performance data is returned as text responses. No charts, no sortable tables, no at-a-glance dashboards.
4. **No guidelines integration** - Campaign guidelines exist as external markdown files. The agent doesn't automatically consult them before making changes.
5. **No tool transparency** - When the agent invokes MCP tools, the user sees the final response but not the intermediate tool calls and their outputs.

### Impact

- Time wasted re-explaining context each session
- Risk of the AI agent making changes that violate campaign-specific rules (e.g., changing bidding strategy during stabilization period)
- Inability to quickly compare campaign performance across the account
- No persistent audit trail of AI-recommended changes

## Proposed Solution

A web application running on localhost that provides:

### Core Components

1. **Campaign Browser** (left sidebar)
   - Account hierarchy tree: Manager → Sub-Manager → Client
   - Campaign list with inline metrics (status, budget, clicks, conversions, CPA)
   - Drill-down: Campaign → Ad Groups → Keywords/Ads

2. **AI Chat Panel** (right panel)
   - Streaming chat interface powered by Claude Code SDK
   - Connected to the same MCP server used in Claude Desktop (90+ tools)
   - Automatically loads campaign guidelines when a campaign is selected
   - Shows tool invocations with expandable details
   - Optional confirmation mode for mutating operations

3. **Guidelines Editor** (tab within campaign view)
   - Markdown viewer/editor for per-campaign guidelines
   - Supports the existing CAMPAIGN_GUIDELINES.md format
   - Auto-save with changes immediately reflected in AI context
   - Template for creating guidelines for new campaigns

4. **Campaign Detail Panel** (center content area)
   - Campaign settings and configuration
   - Ad group/keyword/ad tree with metrics
   - Performance charts (Phase 2)

### Technical Approach

- **Frontend:** React + TypeScript + Vite (SPA)
- **Backend:** Python FastAPI
- **AI Agent:** Claude Code SDK with MCP server integration
- **Data:** SQLite (local) + filesystem (guidelines markdown)
- **Reuse:** The entire MCP server codebase runs as-is, connected to the Claude Code SDK agent

### Why Claude Code SDK

The user chose Claude Code SDK as the agent runtime because:
- Uses the existing Claude Code subscription (no additional API costs)
- Natively supports MCP server connections (same as Claude Desktop)
- Handles tool use, streaming, and context management
- New MCP tools are automatically available without web app changes

## Target User

**Primary:** Wassim
- Manages Google Ads for Mercan Group
- Active campaigns: Portugal Golden Visa, Greece Golden Visa, MENA Golden Visa
- Uses campaign guidelines extensively (global rules + per-campaign sections)
- Needs both AI-powered operations (complex changes, analysis) and direct data browsing

## Key Success Metrics

1. Can complete a full daily campaign review cycle without opening Claude Desktop or Google Ads UI
2. AI agent never violates campaign guidelines (zero false moves)
3. 30%+ reduction in time per management session
4. 100% of active campaigns have guidelines files with auto-context injection

## Constraints

- Must run entirely locally (localhost only)
- Must use existing Google Ads API credentials (no new developer accounts)
- Must use existing Claude Code subscription (no Anthropic API key needed)
- Must preserve existing guidelines file format (backward compatible)
- Must not modify the existing MCP server codebase (consume it as-is)
