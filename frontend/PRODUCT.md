# PRODUCT.md — google-ads-agent (frontend framing)

## What this is
A chat-driven, multi-persona Google Ads strategist. The operator talks to an
agency-style team of named specialists (a Director who routes, plus a PPC
Strategist, Search Term Hunter, Creative Director, Analytics Analyst,
Competitor Intel, GTM Specialist, Growth Hacker, Video Script Generator, and
CRO Specialist). The agent has live access to the Google Ads API, a GTM/GA4
tracking surface, browser automation, and a Marketing Studio for ad creative.

It is both a Mercan internal tool (the LangarAI orchestrator delegates to it)
and a standalone product Wassim is building to sell to agencies.

## Who uses it
Agency owners and PPC operators — often non-engineers — who manage paid search
for clients (Mercan's own focus is the immigration / golden-visa niche). They
read dense campaign data in daylight and want a calm, document-like surface,
not a flashy dark dashboard.

## Voice
- **Plain, specific, evidence-first.** Numbers and concrete recommendations
  over adjectives. Never invent metrics.
- **Each persona has a distinct lens** but speaks in the same calm register —
  identity comes from the name + avatar tint, not loud colored chips.
- **No em dashes in UI chrome.** Marketing/legal copy supplied by the user is
  used verbatim.

## Surfaces (frontend)
- **Chat panel** (`components/layout/ChatPanel.tsx`) — the primary surface:
  persona registry, model selector (Fable 5 default/Sonnet/Opus/Haiku), Templates, Roles, Team
  sessions, Video creator, conversation history + full-text search, export,
  the ContextBadge token-budget meter, the MemoryPanel (pinned facts +
  decision log), the action-vs-internal tool split, full-screen, resize,
  message queueing, and the "Send to Claude Code" handoff.
- **Dashboard / campaign tables / setup / settings / Studio** — supporting
  surfaces that share the same token system.

## Design north star
Google-ads' feature-rich chat wearing the Shopify CRO agent's calm light skin:
one light token system, quiet tool rows, `.studio-prose` markdown, a gentle
streaming caret, and collapsed color sprawl. See `DESIGN.md` for the visual
system. This is a re-skin layer — every existing feature and prop contract is
preserved; no backend, SSE, or workflow changes.
