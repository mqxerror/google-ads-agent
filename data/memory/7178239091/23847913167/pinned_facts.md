# Pinned Facts: Campaign 23847913167

<!-- Facts listed here are ALWAYS included in agent context. -->
<!-- They never expire from the conversation window. -->

- **Campaign ID:** 23847913167 — every recommendation must be scoped to THIS campaign only.
- **Currency:** USD (account billing currency). Convert any £/€ benchmark to USD before recommending.
- **Status:** Brand-new campaign created 2026-05-15. Until at least 7 days and 100+ impressions exist, **do not invent CPA/CPC/QS baselines** — say explicitly that there isn't enough data yet.
- **Daily budget: $130/day** (budget ID `15581336301`, verified via API 2026-06-02). NOT $100 — the $100 in early build notes was a stale draft value. At $130/day the campaign's ~$127/day actual spend is ON budget (slightly under), NOT a 27% overspend. Do not call $127/day an overspend; do not re-anchor to $100.
- **WAITING WINDOW until 2026-06-09.** Leak fix + AG3/AG2 bid block shipped 2026-06-02. Per guidelines (1 change-type/day, 7 clean days before reading) do NOT stack new changes during the window. First honest review/scale date = **Jun 9**. Full plan: `scaling_waiting_plan.md`.
- **Staged-scale gates (the "boost"):** $130 → **$170 (Jun 9)** → $220 (Jun 16) → $260 (Jun 23+), each step gated on **CPA ≤ $55**. Do NOT jump straight to $260.
- **Bidding switch deferred:** Manual CPC → Maximize Conversions is qualified (58 conv/mo) but held ~7–10 days until the `through parents` signal is clean. Flag the switch date at the Jun 9 review.
