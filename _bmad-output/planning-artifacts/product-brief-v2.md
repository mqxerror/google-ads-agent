---
type: product-brief
project: Google Ads Agent V2
date: 2026-04-03
author: Wassim
status: draft
previous: docs/product-brief.md
---

# Product Brief - Google Ads Agent V2

## Executive Summary

Google Ads Agent evolves from a personal campaign management tool into the **open-source, AI-native Google Ads campaign manager** for digital marketing agencies and solo marketers. It is free, runs locally, and turns any Google Ads account into an AI-powered workspace where campaigns are understood, monitored, and optimized by an agent that thinks like a senior paid media strategist.

The core differentiator: **this is not a dashboard with a chatbot bolted on**. It is a campaign manager that genuinely understands marketing strategy — account goals, campaign objectives, audience intent, budget allocation, competitive dynamics — and can read, analyze, AND edit campaigns with the same power as Claude Code edits code.

---

## Vision

> **"Claude Code for Google Ads"** — An AI agent that doesn't just answer questions about your campaigns, it actively manages them with real marketing expertise, full editing capabilities, and deep goal awareness.

The tool ships as a local application that users install and run against their own Google Ads accounts. It uses their existing Claude Code subscription (or Gemini CLI for Google-native users) — zero additional API costs. Agencies install it once per machine and manage all their client accounts through a single, intelligent interface.

---

## Problem Statement

### What exists today (V1 — Personal Tool)

V1 solved Wassim's personal workflow: a local web app replacing Claude Desktop for campaign management. It works — 87 MCP tools, 5-layer memory, campaign browser, guidelines editor, streaming chat. But it was built for one user managing one account group.

### What the market needs

Digital marketing agencies and freelance marketers manage Google Ads across dozens of client accounts. Their daily reality:

1. **No AI-native campaign manager exists** — Google Ads UI is powerful but manual. Third-party tools (Optmyzr, Adalysis, WordStream) add automation rules but lack conversational AI intelligence. None offer an agent that genuinely understands campaign strategy.

2. **Campaign context is lost between sessions** — Every time a marketer opens a tool, they rebuild mental context: what changed yesterday, what's the campaign goal, what experiments are running, what rules must not be broken. Current tools don't remember.

3. **Editing is disconnected from analysis** — You analyze in one view, switch to another to edit. The AI tells you what to change but can't make the change itself, or makes changes without understanding the strategy.

4. **No marketing intelligence in AI tools** — Generic AI assistants can call Google Ads APIs but don't think like marketers. They don't know that a Learning-phase campaign shouldn't have its bid strategy changed, or that a MENA market needs different ad copy rules than a European one.

5. **API cost barrier** — Most AI-powered tools require expensive API subscriptions. Agencies already paying for Claude Code or Gemini shouldn't pay twice.

### Impact of not solving this

- Agencies waste hours per day per account on repetitive analysis
- Junior marketers make costly mistakes (bidding changes during learning phase, wrong match types, budget misallocation)
- Campaign knowledge lives in people's heads, not in the system
- No open-source alternative exists — agencies are locked into expensive SaaS tools

---

## Proposed Solution

### Product Identity

**Google Ads Agent** — The open-source, AI-native campaign manager that thinks like a senior paid media strategist.

### Core Pillars

#### 1. Marketing Intelligence (The Brain)

The agent is not a generic chatbot. It has deep, structured marketing knowledge:

- **Account-level goal awareness** — Understands the overall business objective (lead gen, e-commerce, brand awareness) and how each campaign contributes to it
- **Campaign-level strategy tracking** — Knows each campaign's objective, target CPA/ROAS, current phase (launch, learning, optimization, scaling, sunset), and constraints
- **Cross-campaign reasoning** — Can identify budget cannibalization, audience overlap, attribution conflicts across campaigns
- **Marketing calendar awareness** — Understands seasonality, promotional periods, competitor events
- **Best practices engine** — Built-in knowledge of Google Ads best practices: bidding strategies by objective, match type selection, ad copy frameworks (AIDA, PAS, benefit-driven), landing page alignment, negative keyword hygiene
- **Proactive recommendations** — Doesn't wait to be asked. Surfaces issues and opportunities during daily review

#### 2. Full Editing Capabilities (The Hands)

Like Claude Code can read AND write code, Google Ads Agent can read AND write campaigns:

- **Campaign creation** — Build complete campaigns from a brief (structure, ad groups, keywords, ads, targeting, bidding)
- **Inline editing** — Edit bids, budgets, ad copy, keywords, targeting directly through the agent or UI
- **Bulk operations** — Pause/enable multiple campaigns, apply bid adjustments across ad groups, bulk negative keyword management
- **Ad copy workshop** — Generate, A/B test, and iterate on responsive search ad headlines and descriptions
- **Search term management** — Review search terms, auto-suggest negatives with match types, one-click apply
- **Smart safeguards** — Confirmation required for high-impact changes (budget >20% change, pausing active campaigns, changing bid strategies). Low-impact changes (adding negatives, updating ad copy) can be auto-applied.

#### 3. Multi-Account Agency Support (The Scale)

- **Account switcher** — Manage multiple Google Ads accounts (MCC + child accounts) from one interface
- **Per-account/per-campaign memory** — Guidelines, strategies, history isolated per account
- **Agency dashboard** — Overview of all accounts with health indicators (spend pacing, conversion trends, quality score drift)
- **Client-ready reporting** — Export campaign summaries, performance snapshots, change logs
- **Team knowledge base** — Shared guidelines and playbooks that persist across team members

#### 4. CLI-Native Architecture (The Foundation)

- **Claude Code subscription** — No API key needed. Uses existing CLI subscription
- **Gemini CLI support** — For users in the Google ecosystem (future)
- **MCP tool ecosystem** — 87+ Google Ads API tools, extensible with custom tools
- **Local-first** — All data on user's machine. No cloud dependency. No data leaves the laptop.
- **Open source** — Free forever. Community-driven development.

---

## Target Users

### Primary: Digital Marketing Agencies (2-50 person teams)

- Manage 10-100+ Google Ads accounts across clients
- Mix of senior strategists and junior account managers
- Need consistency in campaign management practices
- Want to leverage AI without expensive SaaS subscriptions
- Value data privacy (client data stays local)

### Secondary: Freelance PPC Managers

- Manage 3-15 client accounts solo
- Need efficiency multiplier (AI does the grunt work)
- Can't afford premium tools ($500+/month)
- Want professional-grade capabilities

### Tertiary: In-house Marketing Teams

- Manage their company's Google Ads
- Want AI-powered optimization without agency fees
- Need a tool that learns their specific business context

### Early Adopter / Testing: Wassim (Mercan Group)

- Current V1 user, dog-fooding the upgrade
- Managing Portugal, Greece, MENA Golden Visa campaigns
- Validates multi-campaign, multi-region workflows

---

## Key Differentiators

| Capability | Google Ads UI | Optmyzr/Adalysis | Generic AI (ChatGPT) | **Google Ads Agent** |
|------------|:---:|:---:|:---:|:---:|
| Campaign browsing | Yes | Yes | No | **Yes** |
| AI analysis | No | Rules-based | Yes (no context) | **Yes (deep context)** |
| Campaign editing | Yes (manual) | Yes (rules) | No | **Yes (AI + UI)** |
| Marketing intelligence | No | Partial | Generic | **Deep, structured** |
| Campaign memory | No | Partial | No | **5-layer persistent** |
| Goal awareness | No | Config-based | No | **Automatic** |
| Cost | Free | $200-800/mo | $20-200/mo API | **Free (CLI sub)** |
| Data privacy | Google servers | Third-party cloud | Third-party cloud | **100% local** |
| Open source | No | No | No | **Yes** |
| Extensible (MCP) | No | No | No | **Yes (87+ tools)** |

---

## What's New in V2 (Delta from V1)

### New Capabilities

1. **Marketing Intelligence Layer** — Campaign goal tracking, phase detection, strategy-aware recommendations, proactive alerts
2. **Full Campaign Editing** — Create campaigns from briefs, bulk operations, ad copy workshop, inline editing
3. **Multi-Account Support** — Agency dashboard, account health overview, per-account isolation
4. **Performance Dashboards** — Charts, trends, comparisons, anomaly detection
5. **Conversation System Upgrade** — Multi-thread per campaign, full-text search, conversation templates ("daily review", "weekly report", "search term audit")
6. **Smart Onboarding** — Auto-analyze account structure on first connect, generate initial guidelines, detect campaign goals from existing data
7. **Export & Reporting** — CSV export, PDF campaign summaries, change logs
8. **Gemini CLI Support** — Alternative AI backend for Google-ecosystem users
9. **Community Playbooks** — Shared guideline templates (e-commerce, lead gen, local services, SaaS)

### Upgraded from V1

1. **Memory system** — From 5-layer to goal-aware + cross-campaign reasoning
2. **Guidelines** — From manual markdown to auto-generated + enriched with live data
3. **Operations** — From basic pause/enable to full campaign lifecycle management
4. **UI/UX** — From single-purpose to multi-account, responsive, keyboard-first
5. **Architecture** — From single-user to multi-account with account isolation

---

## Phasing

### Phase 1: Foundation Upgrade (Current Sprint)

- Multi-account management with account isolation
- Marketing intelligence layer (goal tracking, phase detection)
- Performance dashboards with charts
- Enhanced editing capabilities (bulk ops, ad copy workshop)
- Conversation history with search
- Smart onboarding (auto-analyze new accounts)

### Phase 2: Agency Features

- Agency dashboard with account health overview
- Shared guidelines and playbook templates
- Export and reporting (CSV, PDF summaries)
- Conversation templates (daily review, weekly report, audit)
- Community playbooks (e-commerce, lead gen, etc.)

### Phase 3: Ecosystem

- Gemini CLI support as alternative AI backend
- Custom MCP tool marketplace
- Plugin system for agency-specific workflows
- API for external integrations
- Mobile companion (read-only dashboard)

---

## Key Success Metrics

### User Metrics
1. Complete daily review of 10+ accounts in under 30 minutes
2. Zero guideline violations by AI agent
3. 50%+ reduction in time per campaign management session vs manual
4. Successful onboarding of a new account in under 5 minutes

### Product Metrics
1. 500+ GitHub stars within 3 months of public launch
2. 50+ active installations (tracked via opt-in telemetry)
3. 10+ community-contributed playbooks
4. 3+ agency teams using it in production

### Technical Metrics
1. App loads in under 2 seconds
2. AI first-token in under 1 second
3. Supports 100+ accounts per installation without performance degradation
4. Zero data leakage (all data stays local, verifiable by architecture)

---

## Constraints

- Must remain 100% local (no cloud backend, no SaaS)
- Must work with existing Claude Code subscription (no API key required)
- Must preserve backward compatibility with V1 guidelines format
- Must be installable with a single command (`bash install.sh`)
- Must be open source (MIT license)
- Must not require Docker (direct install on macOS, Linux, Windows)
- MCP server codebase consumed as-is (no modifications to Google Ads MCP tools)

---

## Open Questions

1. **Gemini CLI timeline** — When should Gemini support be prioritized? Phase 2 or Phase 3?
2. **Account isolation model** — Separate SQLite databases per account, or single DB with account partitioning?
3. **Telemetry** — Opt-in usage analytics for measuring adoption? What data is acceptable?
4. **Playbook format** — What format for shareable community playbooks? Markdown bundles? JSON config?
5. **Branding** — Keep "Google Ads Agent" or rebrand for public launch? (Consider Google trademark)

---

## Competitive Landscape

| Tool | Type | Price | AI | Local | Open Source |
|------|------|-------|-----|-------|-------------|
| Google Ads UI | Native | Free | No | No | No |
| Optmyzr | SaaS | $208-832/mo | Rules | No | No |
| Adalysis | SaaS | $149-499/mo | Rules | No | No |
| WordStream | SaaS | $49-299/mo | Basic | No | No |
| ChatGPT + API | Generic AI | $20+/mo + API | Generic | No | No |
| **Google Ads Agent** | **Local App** | **Free** | **Deep Marketing AI** | **Yes** | **Yes** |

---

## Why This Wins

1. **Free + Open Source** — No barrier to adoption. Agencies try it risk-free.
2. **Local-first** — Client data never leaves the machine. Agencies love this for compliance.
3. **CLI-native** — No API costs. Uses subscriptions users already pay for.
4. **Marketing intelligence** — Not a generic chatbot. Thinks like a senior PPC strategist.
5. **MCP extensibility** — 87 tools today, community can add more.
6. **Agency-ready** — Multi-account, shared playbooks, team knowledge base.

---

*Next step: PRD creation with detailed functional requirements, then architecture review for V2 changes.*
