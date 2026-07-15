# Home Page Redesign Brief — "Command Center, not Archive"

> Drafted 2026-07-04 from (a) critique of the current Account Overview and
> (b) the NotFair competitor teardown (notfair.co). Status: BRIEF — enters
> BMAD (`/bmad-edit-prd` → epics/stories) before any code, per the 2026-06-10
> governance rule. Design system: existing Shopify-calm light OKLCH tokens
> (frontend/DESIGN.md) — no new visual language.
>
> **v2 same day (Wassim decision):** the centerpiece is the **Account Director
> global audit** — the homepage is its surface. And the interface must be
> CLEAN: "not like i have now — bulky, not clear, not modern like notfair."
> Both locked below.

## THE ENGINE — "Account Director" global audit (v2, the feature)

One owned agent flow that reads ALL active campaigns and produces ONE ranked
account-level report. This is what NotFair structurally cannot copy (they rent
Claude's chat; no orchestration of their own).

- **Backend mode:** account-wide planning in `workflow_orchestrator.py` —
  `campaign_id=None` already flows through (verified 2026-07-04); add:
  Director plans across active campaigns → fan-out specialist passes
  (per-campaign, parallel, existing personas) → cross-campaign rollup +
  debate → synthesis into a ranked account report.
- **Output contract:** every finding = quantified, approvable ACTION with
  $-impact/wk estimate + affected campaign(s) + [Approve / Approve once /
  Deny] wiring into the existing plan/approval + scope-guard path. Findings
  sorted by $ impact; header = "Total recoverable: $X/wk". Fix lists, not
  reports.
- **Persistence:** account-level report rows (analogous to campaign reports)
  so the homepage strip reads the LATEST audit instantly (no live run on
  page load); staleness label ("audited 2h ago · Run again").
- **Ritual:** Scheduled Plans entry "Weekly account audit" (auto lane) —
  the NotFair-validated cadence, but actually executed by our team.
- **Homepage strip = this report.** The deterministic fix-list aggregator
  (pacing/waste/disapproved/tracking) remains as fast always-fresh signals;
  the Account Director report is the deep ranked layer above it.

## DESIGN DIRECTION — "clean" made concrete (v2, the law)

What "bulky/unclear" is today: permanent 3-pane chrome (campaign tree + dense
content + always-open chat rail), card-borders everywhere, raw lifetime
totals, an archive (Conversation Map) as the main surface, zero-state metrics.

The rules for v2 (layout/density reform — tokens stay Shopify-calm light):

1. **One column, one focus.** The page leads with the Account Director fix
   list. Everything else is secondary and below. No competing panels.
2. **Chat is summoned, not parked.** Kill the always-open right rail on the
   home page: floating button + ⌘K opens the existing chat as an overlay/
   drawer. (Campaign pages may keep their rail; the HOME does not.)
3. **Sidebar collapses to an icon rail** by default on home; campaign tree is
   a flyout. Reclaim the width for the fix list.
4. **Tables over card grids.** NotFair's demo pattern: compact table, generous
   row height, subtle dividers, threshold chips, ONE bulk-action bar. Kill
   border-boxes-inside-boxes; whitespace does the separation.
5. **Progressive disclosure.** A finding row = one line (icon · title ·
   $-impact · actions). Click expands the specialist's evidence/reasoning.
   Nothing verbose is visible by default.
6. **Few numbers, big type.** 4 KPIs max (Spend · Conversions · CPA · CVR),
   value + Δ% + sparkline, quiet labels. Never a grid of raw totals.
7. **Zero-state discipline.** Nothing renders empty ("0% success rate" ban).
   Empty strip = strip absent; the page collapses gracefully to a calm state.
8. **Trust line under every write surface:** "Every write is reviewed. Every
   write is reversible."

## Why (current-page diagnosis, from Wassim's 2026-07-04 screenshot)
1. KPI cards are context-free totals (no window, no delta, no trend).
2. "Agent Performance 0% (0/0)" renders before data exists → looks broken.
3. Conversation Map (archive) dominates the page; it answers "where did I
   talk," not "what should I do."
4. Nothing demands action: pending approvals, budget pacing, wasted spend,
   upcoming Scheduled Plans — none surfaced.
5. Campaigns are only a sidebar tree; no ranked performance view.

## Competitor context (NotFair, verified 2026-07-04)
- NotFair = MCP layer rented into Claude/Codex chat; **no owned dashboard**
  publicly. Their appeal is *framing*: "Fix lists, not reports", "Live
  context. Not yesterday's report", money-ranked recoverable-spend demos,
  Approve/Approve-once/Deny, undo-able change log, threshold+bulk campaign
  table. Pricing: Free / $79 Growth / $499–999 Managed (5% ROI guarantee).
- We are already stronger on: persona team + Team Audit, Studio creative,
  campaign-bound memory, Scheduled Plans, campaign CREATION (PMax wizard),
  tracking depth. The redesign should *surface* these, not hide them.

## Layout (top → bottom)

```
┌ Header: account · date-range picker (7d default, persisted) · Create Campaign ┐
├ ① NEEDS ATTENTION strip (hero)                                                │
│   money-ranked fix list, each row = issue + $/wk impact + inline actions      │
│   [Approve] [Approve once] [Deny] / [Review in chat]                          │
│   sources: pending plan approvals · budget pacing alerts · wasted-spend       │
│   (search-terms $ w/ 0 conv) · disapproved ads · tracking gaps                │
│   footer: "Total recoverable: $X/wk". Rows render only if they exist.         │
├ ② KPI cards w/ context (4): Spend · Conversions · CPA · Conv rate             │
│   each = value + Δ% vs prior period + sparkline (efficiency > volume)         │
├ ③ CAMPAIGNS (centerpiece): ranked rows/cards, active first, sort by spend     │
│   name · status chip · spend · conv · CPA · trend spark · threshold flag      │
│   (⚠ below target) · last agent action · [Chat] [Report]                      │
│   bulk bar when flags exist: "Pause all N / Pick which" (approval-gated)      │
├ ④ AGENT ACTIVITY (replaces Agent Performance + Conversation Map)              │
│   a) Change log w/ undo: chg id · campaign · ts · before→after · [Revert]     │
│      copy: "Every write is reviewed. Every write is reversible."              │
│   b) Upcoming: next Scheduled Plans + "Weekly search-term review due" ritual  │
│   c) Recent threads (last 5 only, "View all" → Conversations page)            │
└ Conversation Map MOVES to its own page (nav item), off the home.              ┘
```

## Rules
- Every metric has a time window + comparison delta. No naked lifetime totals.
- No zero-state metrics: "Agent Performance" appears only after ≥1 measured
  action; empty attention-strip = strip invisible (page collapses gracefully).
- Every persona/audit output that reaches the home page ends as a quantified,
  approvable ACTION (fix list), not prose.
- All writes from the home page go through the existing approval/scope-guard
  path — the strip/bulk actions are shortcuts to it, never bypasses.

## Adopted from NotFair (mapped)
1. Recoverable-spend ranked fix list → section ①.
2. Approve / Approve once / Deny inline → ① rows.
3. Undo-able change log + trust copy → ④a (needs backend change-log w/
   before→after values + revert where the API supports it).
4. CPA/ROAS + deltas on cards → ②.
5. Threshold flags + "Pause all N / Pick which" → ③.
6. "Fix lists, not reports" framing → ① + persona output contract.
7. Weekly-ritual card tied to Scheduled Plans → ④b.

## Where we intentionally differ
- We SHOW our own dashboard (NotFair rents Claude's chat) — our chat rail stays.
- Creation surfaces stay prominent (Create Campaign, Studio) — NotFair can't
  create campaigns at all.
- Persona team visibility: last-agent-action on campaign rows + agent feed.

## Backend prerequisites (size before stories)
- Fix-list aggregator endpoint (pending plans + pacing + search-term waste +
  disapproved ads + tracking flags) with $ impact estimates.
- Change-log table w/ before→after snapshot + revert executor (approval-gated).
- Period-over-period metrics endpoint (current vs prior window + daily series
  for sparklines).

## Competitive intel for the roadmap (Track A)
NotFair pricing ($79 Growth; $499+ Managed w/ 5% ROI guarantee) sits ABOVE our
sketched $29/$99 — pricing room exists. Their six use-cases (wasted spend,
negative automation, disapproved diagnosis, tracking audit, weekly search-term
review, cross-platform ROAS) read as a validated demand list we already cover
or can cover; use them in A5 packaging copy.
