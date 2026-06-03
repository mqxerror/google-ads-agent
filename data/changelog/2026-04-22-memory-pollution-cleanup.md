---
date: 2026-04-22
type: fix
title: Campaign memory cleanup + cross-campaign pollution guard
tags: [memory, agent-quality, currency]
---

The agent was occasionally saving analysis for **one campaign into another campaign's notes** — for example, a deep Portugal USA review ended up in the UK campaign's notes folder. Once the notes were polluted, every later question about that campaign got back a confused, mixed-currency report.

**What changed for you:**

- Two polluted note files were quarantined with a full audit trail (no data deleted — moved to `_quarantine/`).
- Each campaign's notes now start with a clear scope header so you can verify at a glance which campaign the analysis belongs to.
- A guard is now in place: if the agent's analysis mentions a different campaign's ID, the note is auto-redirected to the correct folder before saving.
- The new UK campaign's pinned facts now state explicitly that there isn't enough historical data yet — agents are forbidden from inventing CPA/CPC baselines for it.
- An "Account currency: USD" anchor is loaded at the top of every conversation, so reports stop drifting between $ and £.
- Every campaign data block now starts with a `Currency: USD` line so each specialist sees the unit inline.

**Result:** the next "how is X campaign doing?" should be scoped, in dollars, and based on real data — not borrowed numbers from another campaign.
