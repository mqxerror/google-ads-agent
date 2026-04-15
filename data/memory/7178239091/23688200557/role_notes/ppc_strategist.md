# Ppc Strategist Notes

**Last updated:** 2026-04-13 11:32

**Task:** Deep performance analysis for "Golden Visa Programs - Arabic (MENA)":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown**: 
# Deep Performance Analysis: Golden Visa Programs - Arabic (MENA)
**Period:** Mar 30 – Apr 12 (14 days) | **PPC Strategist**
## 1. Trend Analysis
### Week-over-Week Comparison
|--------|----------------------|-------------------|-------|
*\*Apr 8's 4 conversions are suspect — conversion tracking issues identified in prior session. Real number likely 2-3.*
### Key Inflection Points
1. **Apr 8 — Bid bumps executed.** Portugal residency → $3.80, Greece residency → $3.00, Arabic Greece keywords → $2.80-3.00. Result: CPC jumped from $1.74 average to $2.24+ and never came back down.
2. **Apr 9-11 — CPC spike zone.** Three consecutive days at $2.19-$2.70 CPC. Daily spend hit $72-77 — more than **2.5x the $30 budget**.
3. **Apr 12 — Ad group restructure.** 3 new program-specific EN groups created, 12 keywords moved out of EN (GCC). Too early to measure impact.
**Verdict:** Impressions and clicks are stable, but **you're paying 26% more per click for the same volume.** The bid bumps overcorrected.
## 2. Ad Group Breakdown
| Ad Group | Clicks | Cost | Conv | CPA | % of Spend | Verdict |
|----------|--------|------|------|-----|------------|---------|
**24.7% of all spend ($251.22) went to ad groups with zero conversions.** That's $251 that could have gone to scaling EN (GCC).
## 3. Keyword Efficiency Map
### Winners (have conversions)
| Keyword | Match | Clicks | Conv | Est. CPA | QS |
|---------|-------|--------|------|----------|-----|
*Note: EN (GCC) has 12 total conversions but they're spread across many search terms matching the broad phrase keywords. The restructure on Apr 12 should give better per-keyword visibility going forward.*
### Losers (high spend, 0 conversions — still enabled)
| Keyword | Match | Clicks | Spend Est. | QS | Action |
|---------|-------|--------|-----------|-----|--------|
### Untested (too few clicks to judge)
| Keyword | Clicks | QS | Notes |
|---------|--------|----|-------|
## 4. Quality Score Audit
### Distribution of All 52 Keywords
| QS | Count | % | Includes |
|----|-------|---|----------|
**Zero keywords at QS 6+.** The campaign's quality score is catastrophically low.
### Impact
- QS 3 means you're paying **~30-50% more per click** than a QS 7 competitor for the same position
- QS 1 keywords are essentially penalized — Google treats them as low relevance
- Root cause: **Arabic landing page (goldenvisas.mercan.com) likely has poor relevance** to Arabic search queries. The page may not contain the exact Arabic terms users are searching for, or the post-click experience (load speed, content match) is weak
- The EN keywords fare slightly better (QS 4) because the English landing page likely matches better
**This is the single biggest structural problem in the campaign.** No amount of keyword optimization fixes a QS problem — it requires landing page improvements.
## 5. Search Term Quality (Last 7 Days)
| Category | Clicks | Cost | % of Visible Spend |
|----------|--------|------|-------------------|
**Irrelevant terms identified:**
- `ireland citizenship by investment`: 3 clicks, $4.48 — negated Apr 12
- `d2 portugal visa`: 2 clicks, $7.24 — negated Apr 12
**Going forward**, the 5 negatives added on Apr 12 (ireland, d2 visa, albania, andorra, bulgaria) should eliminate most waste. Search term hygiene is now **good** — this is no longer the primary problem.
## 6. Budget Allocation
### The Overspend Problem
|--------|-----------------|---------|
Google is spending nearly **double** the intended budget. Root cause: Maximize Clicks with $3.00 max CPC + aggressive keyword bids ($3.80 on portugal residency) + broad match types = Google finds plenty of auctions to enter.
### Where the Money Goes (Approximate)
| Destination | % | Monthly Projection | Conv | Worth It? |
|-------------|---|-------------------|------|-----------|
## 7. Strategic Recommendations
### #1: Pause General Golden Visa - AR
**Impact: HIGH | Effort: 5 minutes**
This group has consumed $195.85 with zero conversions across the entire campaign lifetime. The Arabic generic keywords (الاقامة الذهبية, الجنسية عن طريق الاستثمار) have QS 3 and attract searchers who don't convert. Pausing this saves ~$28/day — which alone brings daily spend close to the $30 target.
### #2: Fix Conversion Tracking
**Impact: CRITICAL | Effort: 1-2 hours**
Without trustworthy conversion data, every optimization decision is compromised. The Apr 8 "4 conversions" are likely inflated by the misconfigured "Greece Golden Visa - Lead Inquiry" action (categorized as PURCHASE, firing on non-lead events). **We need to:**
- Verify "GV Landing Page - Lead Form Submission" fires only on actual form submits
- Disable or fix "Greece Golden Visa - Lead Inquiry"
- Cross-reference reported conversions with actual leads received
Until this is done, the "12 conversions" in EN (GCC) and "3 conversions" in Greece AR cannot be trusted. The real CPA may be significantly worse than $61.64.
### #3: Roll Back Bid Bumps + Fix QS via Landing Page
**Impact: HIGH | Effort: Medium**
The Apr 8 bid increases pushed CPC up 26% without a proportional conversion lift. Meanwhile, the real problem is QS 1-3 across Arabic keywords — you're paying a quality tax on every click.
**Short term (today):** Revert bids to pre-Apr 8 levels:
- portugal residency investment: $3.80 → $3.00
- greece residency investment: $3.00 → $2.50
- الفيزا الذهبية اليونان: $2.80 → $2.00
- الاقامة الذهبية في اليونان: $3.00 → $2.50
**Medium term (this week):** Audit the Arabic landing page at goldenvisas.mercan.com/ar/ — ensure it contains the exact Arabic terms users search for, loads fast on mobile (MENA is mobile-heavy), and has a clear CTA above the fold. QS improvement from 3 → 6 could **cut CPCs 30-40%**.
## Summary Scorecard
| Dimension | Grade | Key Issue |
|-----------|-------|-----------|
| Tracking | **F** | Cannot trust conversion data — inflated |
**Bottom line:** This campaign has two fundamental problems that keyword tweaks can't fix: (1) broken conversion tracking making all data unreliable, and (2) QS 1-3 on Arabic keywords indicating a landing page relevance gap. Fix those two and the campaign economics change completely.
Want me to execute #1 (pause General AR) and #3 (revert bids) now? #2 (tracking fix) requires a browser audit of the landing page tags.
— *PPC Strategist*

---

## Session Log

### 2026-04-13 11:32 — execute and 2 only

**Task:** execute and 2 only
Executing both now. Let me pause General AR and start the conversion tracking audit in parallel.
Good, tools loaded. Let me execute both in parallel — pausing General AR and starting the landing page tag audit.
First I need the ad group ID for General Golden Visa - AR. From prior session data, it's **198342212847**.**#1 Done — General Golden Visa - AR is now PAUSED.** Saves ~$28/day.
Now let me audit the landing page. Let me check what tags are firing.API Error: 500 {"type":"error","error":{"type":"api_error","message":"Internal server error"},"request_id":"req_011Ca21dTzVko8enKrzo3mL4"}
