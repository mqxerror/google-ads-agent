# Ppc Strategist Notes

**Last updated:** 2026-06-03 12:20

**Task:** Run stage 5 for campaign build

**Critical Details:** GTM-WZKDXFH8, https://www.mercan.com/panama-qualified-investor-program`, AW-959555504, AW-826329520
Stage 5 — PPC Strategist builds the campaign in Google Ads. I have everything from the prior 4 stages. Let me design the structure and execute.
## Campaign Build Plan
**Campaign:** Panama QIP — Qualified Investor Program
**Type:** Search | **Bidding:** Manual CPC (no conversion history yet — per guidelines, need 15+ conversions/month for automated bidding)
**Budget:** $150/day | **Status:** PAUSED
**Network:** Search only (no Display)
**Targeting:** United States, English
**Final URL:** `https://www.mercan.com/panama-qualified-investor-program`
**4 Ad Groups** from Search Term Hunter + Creative Director copy:
- AG1: Panama Investor Visa (Core) — 9 keywords, 50% budget priority
- AG2: Panama Residency — 7 keywords, 25%
- AG3: Panama Tax & Expat — 6 keywords, 15%
- AG4: Panama Investment Real Estate — 3 keywords, 10%
**25 campaign-level negatives + 5 AG4-level negatives**
Starting the build now — I'll create budget first, then campaign, then ad groups + keywords + ads in parallel.Budget created: `customers/7178239091/campaignBudgets/15597181660`. Now creating the campaign.Campaign created: **ID 23871240619** (PAUSED). Now creating all 4 ad groups.Creating all 4 ad groups in parallel. Setting CPC bids proportional to budget allocation and expected CPCs.All 4 ad grou
| Ad Group | ID | Max CPC |
|---|---|---|
Now adding keywords to all 4 ad groups in parallel.AG2, AG3, AG4 keywords all added successfully. AG1 hit a **LEGAL_REQUIREMENTS policy violation** on "panama qualified investor program" — the batch failed. Let me retry AG1 without that keyword (we can request a policy exemption for it later).AG1: 8 of 9 keywords added (excluding "panama qualified investor program" — needs policy exemption). Now c
## Campaign Build Complete — Panama QIP
**Campaign:** Panama QIP — Qualified Investor Program
**Campaign ID:** 23871240619
**Status:** PAUSED (ready for your go-ahead to enable)
### What was built:
| Component | Details | Status |
|---|---|---|
| **Campaign** | Search, Manual CPC, PAUSED | ✅ |
| **Location** | United States | ✅ |
| **Language** | English | ✅ |
### Ad Groups:
| Ad Group | ID | Max CPC | Keywords | RSA | AG Negatives |
|---|---|---|---|---|---|
### Issues to resolve before enabling:
1. **"panama qualified investor program" [Exact]** — hit a LEGAL_REQUIREMENTS policy violation. This is the exact program name and is exemptible. You'll need to request an exemption in the Google Ads UI (Policy Manager → Request Review), or we can skip it since the phrase match keywords in AG1 will catch similar queries.
2. **Conversion action** — per the CRO Specialist, the landing page has GTM-WZKDXFH8 and two Google Ads pixels (AW-826329520, AW-959555504), but we need to **verify a Panama-specific conversion action exists** and is set as PRIMARY for this campaign. Without this, we'll be flying blind on CPA. Want me to check the conversion actions registry and set one up?
3. **Landing page CRO fixes** (recommended but not blocking): slash the 13-field form to 3-4 fields, replace "See if you qualify" with "Speak with a Panama Advisor", change "Submit" to "Request My Free Consultation".
### Next steps — your call:
- **Enable the campaign?** Say the word and I'll flip it to ENABLED.
- **Set up Panama conversion action?** I can create one scoped to the `/panama-qualified-investor-program` thank-you page.
- **Request policy exemption** for the blocked keyword?
— *PPC Strategist*

---

## Session Log

### 2026-05-21 13:02 — Deep performance analysis for "[SELECT A CAMPAIGN FIRST]":

1. **Trend Analysis*

**Task:** Deep performance analysis for "[SELECT A CAMPAIGN FIRST]":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown**: Which ad gr
## Panama QIP (23871240619) — Performance Analysis
**There is no performance data to analyze.** This campaign was created yesterday (May 20) and has zero impressions, zero clicks, and zero conversions across all 4 ad groups. Quality scores haven't populated yet.
### Critical Issue: All 4 Ads Are PAUSED
The campaign itself was enabled yesterday, but **every RSA is status PAUSED**:
| Ad Group | Ad ID | Status |
|----------|-------|--------|
**The campaign cannot serve any impressions because there are no active ads.** This is why we have zero data after ~24 hours live.
### Recommended Action
Enable all 4 ads so the campaign can start serving. Once we have 7+ days of data (per change management rules), I can run a real performance analysis covering all 7 dimensions you asked about.
**Want me to enable all 4 ads now?** This is a medium-impact action — confirming before proceeding.
— *PPC Strategist*

### 2026-05-25 13:34 — Daily review for "[SELECT A CAMPAIGN FIRST]":

1. How did yesterday compare to t

**Task:** Daily review for "[SELECT A CAMPAIGN FIRST]":

1. How did yesterday compare to the 7-day average? Flag any anomalies.
2. Are we on pace for monthly budget? Any pacing issues?
3. Any keywords with high
## Panama QIP (23871240619) — Daily Review, May 25
### 1. Yesterday (May 24) vs. 7-Day Average
|--------|--------|-----------|---|
**Anomaly: Overspend.** May 24 cost $223 on a $150/day budget — Google spent 49% over target. This is allowed (Google can spend up to 2x daily budget on any single day) but it's notable. May 23 was also high at $268. Two consecutive overspend days = pacing risk.
**Today (May 25, partial):** $68.05 from 233 impressions/21 clicks — tracking lighter, likely weekend effect.
### 2. Budget Pacing
| Metric | Value |
|--------|-------|
| Monthly budget | $4,500 ($150 × 30) |
| Spent May 21–25 (5 days) | **$753.58** |
| Daily run rate | $150.72/day |
| Projected month-end | ~$4,522 |
**On pace** — monthly spend is within Google's billing-period cap (30.4 × $150 = $4,560). The May 23-24 overspend days are offset by today's lighter pace. No action needed.
### 3. High-Spend Keywords, Zero Conversions
| Keyword | Clicks | Cost | Issue |
|---------|--------|------|-------|
**Note:** 0 conversions across ALL 241 clicks is consistent with a 13-field form on a $300K program. Tracking is confirmed working (verified yesterday). The form is the bottleneck, not the keywords.
### 4. Top Converting Search Terms
**Zero conversions exist.** Cannot identify winners. Skipping.
### 5. Immediate Actions
| # | Action | Urgency | Rationale |
|---|--------|---------|-----------|
### Bottom Line
Campaign fundamentals are healthy (10%+ CTR, $3.10 CPC, 62.5% IS, 0% budget-lost). The negatives and keyword removals from yesterday will reduce waste going forward. **The only thing that will produce conversions is fixing the 13-field form** — that's the #1 priority above all else.
No tactical changes needed today. Check back Tuesday (May 27) for post-negative-keyword impact.
— *PPC Strategist*

### 2026-06-03 12:20 — Analyze the currently selected campaign "Greece Golden Visa V2" — its structure,

**Task:** Analyze the currently selected campaign "Greece Golden Visa V2" — its structure, keywords, match types, ad copy, bidding strategy, and performance data.

Then create a NEW campaign based on what's wor
I have to stop you before I start — this request is for a **different campaign** than the one I'm bound to.
**Campaign lock:** This conversation is bound to **Panama QIP — Qualified Investor Program (ID 23871240619)** for its entire life. Every piece of LIVE CAMPAIGN DATA in my context (the day-by-day metrics, AG1–AG4, the 19 Panama keywords, the search terms) is Panama's. I have **zero** data on "Greece Golden Visa V2" in context, and the hard rule is: I operate only on this campaign ID and never silen
This is the same boundary that triggered on June 2 (the "Greece Golden Visa - Turkey" slip).
So here are your real options:
**1. You actually want to build the new Greece/Silicon-Valley-Indian campaign** → that's legitimate, but it needs to happen in a conversation bound to the Greece reference campaign (or an unbound/creation context), not this Panama-locked one. Open a session selected on **Greece Golden Visa V2** and paste this exact brief — I'll pull its real structure, keywords, match types, RSAs, bid strategy, an
**2. You meant to do this for Panama** (copy-paste slip — the brief mentions Greece, not Panama, so I doubt it) → say so and I'll work entirely within Panama QIP.
**3. You want me to use Panama QIP as the proven reference** to model a *new* campaign → I can do that, since Panama is my locked campaign and I'd be reading *its* data. But note Panama is a weak template right now: **2 conversions in 13 days, $2,030 spend, CPA ≈ $1,015, 0.18–0.34% CVR** — it has a conversion-path problem (the form/phone-validation wall), so I'd be copying structure, not success.
One quick note on the brief itself: I think you mean **Indian nationals in Silicon Valley** (H-1B/visa-maintenance pain), not "Indiana" the state — worth confirming before any build, because it completely changes geo-targeting and ad copy.
Which path do you want? I won't touch anything until you confirm scope.
— *PPC Strategist*
