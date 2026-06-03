# Campaign Chronicle: Build: https://www.mercan.com/panama-qualified-investor-program
Last updated: 2026-06-02

## Timeline

### May 2026
- **May 31** — [GTM Specialist] Compared Popsixle (Shopify ecommerce CAPI SaaS) to our bespoke dual-layer lead-gen tracking stack; confirmed our system is fundamentally different — transactional ecommerce vs. high-ticket GCLID-attributed form leads, client-side gtag + GTM safety net vs. server-side CAPI, Google Ads-first vs. Meta/Google/TikTok.
- **May 26** — [Agency Director] Panama QIP: Executed 2 rounds of cleanup (May 24–25) — added 11 campaign-level negatives, paused 6+ low-QS/irrelevant keywords, removed 5 misplaced positives from AG4, reduced AG2 bid $3.00→$2.50, confirmed no headline pinning, reduced landing page form 13→4 fields.
- **May 26** — [Analytics Analyst] Clarity analysis confirmed 94% tracking coverage (271 sessions vs 287 GA clicks, May 21-26) on Panama QIP page; zero form interactions across all sessions despite 2 highly-engaged (15-30+ min) visits — form abandonment is pre-engagement, not mid-completion.
- **May 26** — [Analytics Analyst] Clarity MCP confirmed pointing to wrong project (`3149465520228862` / goldenvisas.mercan.com) instead of mercan.com Panama LP (`56xm2r94rk`); fix requires generating new API token from correct Clarity project and restarting MCP server.
- **May 26** — [Agency Director] GA4 MCP still pulling data from wrong project (goldenvisas `3149465520228862` instead of mercan.com `56xm2r94rk`); root cause identified as stale JWT token — new token must be generated from correct project dashboard.
- **May 26** — [Agency Director] Found that MCP Clarity is configured with project ID `3149465520228862` (goldenvisas.mercan.com), not the Panama LP project `56xm2r94rk` — this explains 0 sessions returned from all Clarity queries. Fix requires a new API token for `56xm2r94rk` in `data/mcp_config.json`.
- **May 25** — [Video Script Generator] User asked: Write 1 variant(s) of a 15-second video ad script.

Brief: Target audiences: US-based HNW investors
- **May 25** — [Agency Director] Executed CRITICAL section for Panama QIP campaign: removed 5 dangerous AG4 keywords, added 4 campaign-level negatives + 1 AG4 negative, paused 3 keywords ("panama permanent residency" AG2, "move to panama from us" AG3, "golden visa panama" AG1). Proceeded to HIGH #7 (unpin government partnership headlines from RSA position 2) but MCP lacks RSA pin editing support — switched to browser automation.
- **May 25** — [Agency Director] Team session run on AG4 (Panama Investment Real Estate): confirmed 5 suspicious keywords (hotel, etc.) are live enabled positive keywords; IS at 63.8% with 36.2% lost to Ad Rank, 0% lost to budget.
- **May 25** — [Search Term Hunter] Panama QIP (23871240619) deep analysis: 5-day window (May 21–25), 241 clicks, $753.58 spent, 0 conversions; inflection on May 23 (impressions 519→797, spend $268 vs $150 target); CPC creeping $2.89→$3.24; May 24 negatives/bid cuts (AG2 to $2.50) showing early volume reduction on May 25.
- **May 25** — [PPC Strategist] Panama QIP daily review (May 24): cost $223 vs $150/day target (+48% overspend, second consecutive day after $268 on May 23), but monthly pacing ~$4,522 projected vs $4,560 cap — no action needed. Flagged 3 keywords spending $80–$152 with zero conversions (panama residency for americans, panama resident visa, panama permanent residency program).
- **May 24** — [Agency Director] User asked: done im signed in
- **May 24** — [Agency Director] Planned ad extensions for Panama QIP campaign (23871240619): 4 sitelinks (Santa Maria Residences, Territorial Tax Benefits, October 2026 Deadline, Speak to a Panama Advisor) and 6 callouts drafted, pending Google Ads sign-in to execute via browser.
- **May 24** — [Agency Director] Added 7 campaign-level negative keywords (pensionado, retirement, friendly nations, etc.), paused 3 bad keywords across AG2/AG3 (including "us expats in panama"), and initiated form submission test on Panama landing page to verify conversion tracking.
- **May 24** — [Agency Director] PPC team session run on MapleRoots Panama QIV: Search IS 62.5% with 37.5% lost to Ad Rank (not budget), AG2 over-serving at 58% of spend vs 25% planned — QS 1-2 keywords identified as root cause, AG2 keyword surgery recommended over negatives alone.
- **May 24** — [Search Term Hunter] Panama QIP (23871240619) first performance snapshot at 3.5 days live: 1,722 impressions, 181 clicks, $562.02 spent, 0 conversions, avg CPC $3.10. AG2 consuming 58% of budget vs planned 25%; AG1 (Core) underserving at 9% vs planned 50%.
- **May 21** — [Agency Director] User asked: why the click is so expensive even more then the use location. 80), here's why they're high for a US-targeted campaign:

### Why Investment Immigration Keywords Ar
- **May 21** — [Agency Director] All 4 RSA ads enabled across AG1–AG4 (campaign 23871240619); campaign now fully active and entering auction as of May 21.
- **May 21** — [PPC Strategist] PPC Strategist discovered Panama QIP campaign (23871240619) has zero impressions after 24h live because all 4 RSAs are PAUSED — recommended enabling all ads to allow serving.
- **May 20** — [Agency Director] Stage 7 Agency Director synthesis completed for Panama QIP campaign (ID 23871240619): $150/day budget, 3 ad groups (AG1–AG3), Manual CPC, PAUSED and launch-ready pending go-ahead; GTM Version 13 conversion tracking live.
- **May 20** — [Agency Director] Found that Panama form ID is 11; need to add it to the `programForms` array in the "GF - Push dataLayer on AJAX" GTM tag (currently only covers forms 15, 23, 26 for Portugal + Greece) to fire `gf_submit` for Panama conversions.
- **May 20** — [GTM Specialist] GTM Specialist verified Stage 6 for Panama QIV campaign (ID 23871240619): confirmed "Panama QIV Lead" conversion action (ID 7607343274, PRIMARY, 90-day lookback) already exists and GTM-WZKDXFH8 tag is properly configured (Conversion ID: 826329520, Label: C98tCKqxu6scELCTg4oD, firing on "CE - Panama Form Submit" trigger in container Version 12).
- **May 20** — [PPC Strategist] Panama QIP Search campaign built (ID 23871240619, $150/day, PAUSED): 4 ad groups created (AG1 Core $4.50 CPC, AG2 Residency $3.00, AG3 Tax/Expat $2.50, AG4 Real Estate implied lower), 25+ negatives, budget ID 15597181660.
- **May 20** — [Creative Director] Creative Director wrote full RSA ad copy for Panama QIV campaign across all 4 ad groups (AG1–AG4), leveraging Oct 2026 deadline urgency ($300K→$500K), Plan B emotional angle, and official govt partnership trust signal as primary creative pillars. Copy informed by CRO (13-field form issue), Competitor Intel (undercontested US targeting), and Search Term Hunter (25 keywords, $150/day) findings.
- **May 20** — [Search Term Hunter] Search Term Hunter built 4-ad-group keyword strategy for Panama QIP campaign: AG1 core investor visa terms (~440 searches/mo, $3.50–$5.80 CPC), AG2 residency-by-investment (~390/mo), AG3 tax/asset protection angle, AG4 competitor/deadline terms; total ~1,300 exact-match searches/mo in US with $150/day budget projecting 25–100 clicks/day.
- **May 20** — [Competitor Intel] Competitor Intel mapped Panama QIP competitive landscape: identified Get Golden Visa and Immigrant Invest as top commercial competitors targeting $300K/tax/citizenship angle; flagged 13-field form as #1 conversion killer and "See if you qualify" language as contradicting no-gatekeeping philosophy.
- **May 20** — [CRO Specialist] CRO analysis of mercan.com/panama-qualified-investor-program for Panama QIP campaign build: identified 13-field form as #1 conversion killer (est. 50-70% lead loss), flagged "Submit" CTA as generic, recommended reducing to 3 fields and rewriting button copy; trust signals and H1 value prop rated strong (8/10).

### June 2026
- **Jun 02** — [Agency Director] Campaign scope guard triggered: Director refused team session on "Greece Golden Visa - Turkey" (wrong campaign), correctly enforced Panama QIP (23871240619) boundary. No analysis run; user prompted to confirm correct campaign context before proceeding.
- **Jun 01** — [GTM Specialist] GTM Specialist ran live Chrome MCP test on Panama landing page — identified Gravity Form (8 fields + reCAPTCHA v2/v3) blocking automated submission; confirmed GTM-WZKDXFH8 container connected via Tag Assistant. Full field UIDs extracted; conversion tag fire verification pending reCAPTCHA resolution.
- **Jun 01** — [Agency Director] Enhanced Conversions confirmed "Excellent" setup with Panama QIV Lead (ID 7607343274) wired as Primary+TAG — but coverage chart is flat near 0%, diagnosed as: only 1 conversion in 12 days (near-zero denominator) plus unconfirmed `gf_submit` firing for Gravity Form ID 11.
- **Jun 01** — [Analytics Analyst] User asked: why this step 7. Enhanced Conversions — needs the UI, no API path. There is no MCP tool to toggle En
- **Jun 01** — [Analytics Analyst] User asked: do all except the funnel redesign I need to think about it
- **Jun 01** — [Agency Director] Panama QIV campaign (12-day review): 543 clicks, $1,718.70 spend, 1 conversion, CPA $1,718.70, CVR 0.18%. PPC Strategist flagged structural failure — AG2 eating 50% spend ($865 CPA), AG4 burning 28% at zero conversions, AG1 (core investor intent) starved at 13% — inverse of the original plan.

## Key Metrics Milestones

## Critical Decisions (never expire)
