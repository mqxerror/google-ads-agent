# Decision Log: Campaign 22551124974

<!-- FORMAT: | Date | Action | Reason | Outcome | Role | -->

| Date | Action | Reason | Outcome | Role |
|------|--------|--------|---------|------|
| 2026-06-03 13:17 | - This builds naturally on your **paused V2 campaign (`23722199501`)** — add the metro location targeting + income/audience layers there, or I can spin up a dedicated geo-segmented variant. Either way I'll keep writes on the correct campaign only. | User asked: im planning a campaign in Silicon Valley in usability like Indiana and high paid workers in there who might have h1b visa or similar that could be can | pending | analytics_analyst |
| 2026-06-03 13:17 | Which campaign should this live on — the paused **V2 (`23722199501`)**, or a new dedicated geo campaign? | User asked: im planning a campaign in Silicon Valley in usability like Indiana and high paid workers in there who might have h1b visa or similar that could be can | pending | analytics_analyst |
| 2026-06-03 14:19 | I'll resolve the actual geo-target IDs first, then run the team session referencing the verified data.Now let me resolve the metro geo-target IDs in parallel.Verified the geo-target IDs via the Google Ads API. Here's the team session built on real data. | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:19 | The geo IDs are resolved and verified against the API — here are the canonical **city-level** targets (use these IDs, not state): | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:19 | My structural objection before anyone gets excited: **this cannot go on the locked campaign 22551124974** — that's US-nationwide Maximize Conversions with 767 conversions and a settled algorithm. Don't bolt 12 metros + income overlays onto it; you'll reset its learning. This belongs on the **paused  | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:19 | These are the same IDs from my prior report, now API-confirmed — good. Two refinements from the data: | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:19 | I maintain my earlier open question, still unanswered: **which campaign?** PPC Strategist says V2 and I agree — but Wassim hasn't confirmed. Nothing should be written until he does. | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:22 | Agreeing with reuse-V2 — and a clone would inherit nothing useful on search terms anyway, since the negative list is keyword-level, not portable cleanly. The bigger "start today" risk: V2's 13 existing negatives (`free`, `cheap`, `scam`, `job`, `jobs`, `work permit`, `student visa`, `tourist visa`,  | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:22 | **This is the hard blocker on "start today" — and it overrides everything above.** V2's landing page is `goldenvisas.mercan.com/greece` — a **different domain** from the verified `www.mercan.com/greece-golden-visa/`. The verified Greece tag (label `hMe8CLPl184aELCTg4oD`, conv action `7144337715`, co | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:22 | 1. **HARD BLOCKER — tracking (GTM + CRO).** V2's LP `goldenvisas.mercan.com/greece` is a different domain than the verified tag. Conv action `7561175650` has **no firing tag installed** there. Launching today = repeat of the March $200/day-no-data failure. **Tag must be installed + Chrome-verified b | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:22 | - **Today:** I install + verify the conv tag on goldenvisas (with your OK), add the metro negatives, set Tier-1-pair geo + Manual/Max-Clicks bidding on V2 — all while it stays PAUSED. | User asked: TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that s | pending | director |
| 2026-06-03 14:28 | Good news first — **switching the LP to `www.mercan.com/greece-golden-visa/` clears the hard blocker.** That page already has the verified Greece conversion tag firing (label `hMe8CLPl184aELCTg4oD`, conv action `7144337715`, GTM-KWFH5X9T, end-to-end tested 2026-03-19). No new tag install needed — tr | User asked: the landing page should be only this one https://www.mercan.com/greece-golden-visa and we need the geo targeting done properly as discussed | pending | cro_specialist |
| 2026-06-03 14:28 | **Everything you're asking for — the LP swap and the metro geo targeting — was unanimously scoped by the team to V2 (`23722199501`)**, the purpose-built paused campaign. Applying 4–12 metro geo + bid modifiers to `22551124974` would do exactly what the whole team warned against: **geo-restrict and r | User asked: the landing page should be only this one https://www.mercan.com/greece-golden-visa and we need the geo targeting done properly as discussed | pending | cro_specialist |
| 2026-06-03 14:33 | Understood — you're starting fresh, so the campaign-binding conflict is gone. Here's the complete, ready-to-paste geo-targeting report. All geo IDs below were API-verified in this account earlier today, so you can drop them straight into the creation tool. | User asked: i need only those people there the rich guys i doint care about histpry we can start fresh if needed , can you give the geoi targeting report in detai | pending | analytics_analyst |
| 2026-06-03 14:33 | ### 1. Geo targets — canonical, API-verified IDs | User asked: i need only those people there the rich guys i doint care about histpry we can start fresh if needed , can you give the geoi targeting report in detai | pending | analytics_analyst |
| 2026-06-03 14:33 | / **Landing page** / `https://www.mercan.com/greece-golden-visa/` / Verified conversion tag already fires here (label `hMe8CLPl184aELCTg4oD`, conv action `7144337715`) — tracking solved, no install needed / | User asked: i need only those people there the rich guys i doint care about histpry we can start fresh if needed , can you give the geoi targeting report in detai | pending | analytics_analyst |
