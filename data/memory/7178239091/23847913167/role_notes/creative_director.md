# Creative Director Notes

**Last updated:** 2026-06-02 12:30

**Task:** review ad copy and the top combination running since the campaign started
Let me pull the actual RSA ad copy and asset-level performance data from the API.Let me pull the RSA ad copy details and asset performance data in parallel.Now let me pull the top headline/description combinations Google is actually showing.Large result set. Let me read the combination data to find the top-performing ones.The combination view only returns asset IDs, not text. I need to map asset I
# Ad Copy Review — MapleRoots (May 16-17, 2026)
## Campaign-Wide Ad Status
| Ad Group | Ad ID | Ad Strength | Impressions | Clicks | CTR | Status |
|----------|-------|-------------|-------------|--------|-----|--------|
All 5 RSAs approved, all "GOOD" ad strength, all asset labels "PENDING" (Google needs more data to rate individual assets). No policy issues.
## Top Headline/Description Combinations (by impressions)
Google tested **121 unique combinations** in just 2 days — that's healthy rotation.
### #1 Combo — AG4 (4 impressions, top served)
| Position | Text |
|----------|------|
| **H1** | Bill C-3 Changed the Rules |
| **H2** | Citizenship by Descent Guide |
| **D1** | Parent, grandparent, or great-grandparent path — we assess which applies to you. |
| **D2** | Bill C-3 restored citizenship for many descendants. Find out if you qualify today. |
### #2 Combo — AG2 (3 impressions)
| Position | Text |
|----------|------|
| **H1** | Grandparent Path to Canada |
| **H2** | Grandparents Were Canadian? |
| **D1** | Canadian grandparent? You may already be a citizen. Free eligibility consultation. |
| **D2** | Bill C-3 removed the first-generation limit. Grandparent path now open. Free consult. |
### #3 Combo — AG1 (1 impression each — 27 combos, all at 1 impr)
| Position | Text |
|----------|------|
| **H1** | Parent or Grandparent Path |
| **D1** | Canadian parent, grandparent, or great-grandparent? You may already qualify. |
| **D2** | Bill C-3 restored citizenship for descendants. Free consultation — no obligation. |
### #4 Combo — AG3 (1 impression)
| Position | Text |
|----------|------|
| **H1** | Bill C-3 May Cover You |
| **H2** | Great-Grandparent Canadian? |
| **D1** | Bill C-3 opened paths beyond grandparents. See if your great-grandparent line works. |
| **D2** | Quebec parish records & pre-1947 files are our specialty. Free case assessment. |
## Creative Director Assessment
### What's Working
1. **Ad strength "GOOD" across all 5 RSAs** — Google sees enough headline variety and relevance. This is the minimum we want; "EXCELLENT" is the target but "GOOD" at launch is solid.
2. **121 combinations tested in 2 days** — Google is actively rotating, which means the headline pool has sufficient variety. No near-duplicate penalty.
3. **AG1 CTR = 7.7%** (2/26) — small sample but the strongest signal. The "Core Descent" messaging is resonating. "Parent or Grandparent Path" as H1 with the Bill C-3 description is performing.
4. **Bill C-3 headlines dominating rotation** — Google is favoring Bill C-3 references in H1/H2 across all ad groups. This confirms the Competitor Intel finding: Bill C-3 is news-worthy and CTR-driving.
### What's Concerning
1. **AG2 Grandparent: 21 impressions, 0 clicks (0% CTR)** — The top combo "Grandparent Path to Canada" + "Grandparents Were Canadian?" is all-question, no action. Both headlines are exploratory rather than outcome-driven. Compare to AG1's 7.7% CTR — AG1 leads with the **pathway** ("Parent or Grandparent Path"), while AG2 leads with a **question** that may feel too vague.
2. **AG4's top combo doesn't mention "free"** — The highest-impression combo leads with "Bill C-3 Changed the Rules" + "Citizenship by Descent Guide". Neither headline contains the free consultation USP. Meanwhile AG4 is consuming 57% of spend. The copy isn't pulling its weight to differentiate from organic results.
3. **No emotional hooks in top combos** — "You May Already Be Canadian", "Lost Canadian? We Can Help", "Are You Already Canadian?" — these identity/discovery headlines haven't surfaced in the top combinations yet. Google may be suppressing them because they don't match keyword intent as closely. This is expected early on but worth monitoring.
4. **AG5 Cajun: zero impressions** — The identity-first messaging ("Cajun or Acadian Heritage?", "French-Canadian Ancestors?") hasn't been tested at all. This is a keyword volume issue (the Cajun terms are very low volume), not a copy issue.
### Recommendations
| # | Action | Rationale | Impact |
|---|--------|-----------|--------|
### On the "Eligibility" Language
Per my evolved skill notes, I normally ban eligibility language ("Check Eligibility", "See If You Qualify") for golden visa campaigns because there's no qualification gate — financial capacity IS qualification.
**This campaign is different.** Canadian citizenship by descent has a genuine eligibility question — you either have the ancestral chain or you don't. "Check Your Eligibility" is factually accurate here. The landing page IS an eligibility quiz. No correction needed.
### Bottom Line
The copy is healthy. Ad strength is GOOD, Google is rotating 121 combos, and the Bill C-3 angle is dominating. **The campaign's problem isn't creative — it's the CPC anomaly ($1.22 vs $0.45-$0.75 bids) and AG4's budget cannibalization.** Fix those structural issues first. Creative optimization becomes meaningful after 1,000+ impressions per ad group, which at current pace is ~5-7 days away.
— *Creative Director*

---

## Session Log

### 2026-05-17 18:34 — As the CRO Specialist, run a comprehensive 12-point CRO audit for "MapleRoots — 

**Task:** As the CRO Specialist, run a comprehensive 12-point CRO audit for "MapleRoots — Citizenship by Descent (US)":

WORKFLOW:
1. Find the landing page URL from the campaign's ads (final_urls)
2. Run the FU

**Critical Details:** AW-826329520, https://immigration.ca/canadian-citizenship-by-descent-calculator/, https://www.mercan.com/canadian-citizenship-by-descent`., GTM-WZKDXFH8, https://www.mercan.com/canadian-citizenship-by-descent
I'll run the full 12-point CRO audit. The landing page URL from the campaign context is `https://www.mercan.com/canadian-citizenship-by-descent`. Let me start by opening the page and running parallel diagnostics.Let me start by opening the landing page and running the Lighthouse audit in parallel.Chrome isn't running. Let me launch it.Chrome launched. Let me wait a moment and then open the page.Pa
# CRO Audit — MapleRoots Landing Page
**URL:** https://www.mercan.com/canadian-citizenship-by-descent
**Audit Date:** 2026-05-17 | **CRO Score: 66/100 (MODERATE)**
<!-- STRUCTURED_DATA_START -->
<!-- STRUCTURED_DATA_END -->
## Executive Summary
### What's Working
1. **Exceptional page speed** — TTFB 87ms, load <1 second, zero CLS
2. **Premium design** — dark navy/gold, professional, mobile-responsive
3. **Strong trust signals** — RCIC regulated, 37 years, 50K+ clients, government source citations
4. **Comprehensive content** — 8 well-structured sections covering benefits, eligibility, process, comparison
5. **Floating CTA** — "Request a consultation" persists across the entire 13,500px page
6. **All tracking tags firing** — GTM, Google Ads, Clarity, Facebook Pixel confirmed
### What's Broken
| Priority | Issue | Impact |
|----------|-------|--------|
### The #1 Problem: This Page Is Built for Readers, Not Converters
The page is an excellent **information resource** — but it's optimized for someone doing research, not someone clicking a Google Ad about eligibility. The conversion mechanism (a form buried at 11,363px with 8 fields) doesn't match the intent of paid traffic users who searched "check canadian citizenship eligibility."
**The competitor gets this right.** Immigration.ca's calculator IS the page — you land, you answer questions, you get an assessment. Zero scrolling required.
### Immediate Action Plan
| # | Action | Effort | Impact |
|---|--------|--------|--------|
**Test #4 today.** If the conversion is firing correctly, we have a CRO problem. If it's NOT firing, we have a tracking problem that's masking all performance data.
— *CRO Specialist*

### 2026-06-02 12:30 — Ad copy workshop for "MapleRoots — Citizenship by Descent (US)":

1. Review all 

**Task:** Ad copy workshop for "MapleRoots — Citizenship by Descent (US)":

1. Review all current responsive search ads — headlines and descriptions
2. Identify which ads/ad groups have the lowest CTR
3. For th
I'll pull the actual RSA copy and per-ad CTR — that text isn't in my context, only ad IDs and URLs are. Let me load the search tool.Pulled the live RSA copy and per-ad CTR for all 5 ad groups. Here's the workshop.
## 1. Current RSAs — Status & CTR (post-LP-switch ads, live since May 26)
| Ad Group | Ad ID | Impr | Clicks | **CTR** | Conv | Ad Strength |
|---|---|---|---|---|---|---|
## 2. Lowest CTR — the real diagnosis
- **AG2 — Grandparent (7.69%, 0 conv)** is the weakest ad with real volume, and it matches the campaign-long story: AG2 is the $141-CPA problem child.
- **AG4 (0%) is NOT a copy problem** — it has 9 impressions because the PPC team intentionally throttled it to a $0.35 bid. Rewriting AG4 copy won't move anything while it's bid-suppressed. Skip it.
- **AG1 dropped to AVERAGE ad strength** — and it's 64% of spend. That's actually a higher-leverage fix than AG2's tiny volume (flagged at the bottom).
**Why AG2 underperforms — copy diagnosis:** 4 of its 15 headlines are near-duplicate "grandparent" permutations ("Grandparent? Apply Now" / "Grandparent Path to Canada" / "Citizenship Via Grandparent" / "Grandparents Were Canadian?"). Google ignores near-duplicates, so the rotation pool is effectively shrunk. It's also **missing the proven discovery hook** ("You May Already Be Canadian"), has **no
Note on eligibility language: per my May 17 ruling on this campaign, eligibility/qualify wording is *allowed here* — Canadian descent has a genuine ancestral-chain question, unlike the golden-visa campaigns. So I'm keeping it in play.
## 3–5. Proposed AG2 rewrites (replace the 4 redundant grandparent headlines)
### 5 new headlines (≤30 chars) — one per framework
| # | Framework | Headline | Chars | Rationale |
|---|---|---|---|---|
### 2 new descriptions (≤90 chars)
| # | Framework | Description | Chars |
|---|---|---|---|
**Pinning:** keep H1 pinned to the grandparent keyword (`Grandparent Path to Canada` or `Citizenship Via Grandparent`), H2 to the trust signal (`RCIC-Led Application`). Leave headlines #1–5 above unpinned so Google rotates them against the keyword.
## Higher-leverage flag: AG1 is AVERAGE strength
AG1 carries 64% of spend and 62% of conversions but its ad strength slipped to **AVERAGE** — likely headline redundancy (it has "Speak With an Advisor" + "Free Consultation Today" + "Get a Canadian Passport" + "185+ Visa-Free Countries" competing). Lifting it to GOOD touches far more impressions than fixing AG2. I'd recommend a parallel 3-headline swap there.
**Want me to:**
1. Apply the AG2 swaps above (replace the 4 redundant grandparent headlines with #1–5, add D1–D2)?
2. Also do the AG1 AVERAGE→GOOD pass?
I'll show you the exact AG1 swaps before touching it. Nothing changes until you approve.
— *Creative Director*
