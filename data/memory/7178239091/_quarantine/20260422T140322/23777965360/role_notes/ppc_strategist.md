# Ppc Strategist Notes

**Last updated:** 2026-04-20 16:30

**Task:** Deep performance analysis for "Portugal Golden Visa - USA - 10-Mar-2026":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown

**Critical Details:** Campaign ID: 23636342079
The data in my context is for the **UK campaign** (23777965360), not the Portugal Golden Visa USA campaign. I need to pull that campaign's data. Let me fetch everything in parallel.Let me pull all the data for the Portugal Golden Visa USA campaign in parallel.Page size issue. Let me use the streaming endpoint instead.Good, I have the daily metrics, ad groups, and keywords. Let me read the search t
# Deep Performance Analysis: Portugal Golden Visa - USA - 10-Mar-2026
**Campaign ID: 23636342079 | Period: Apr 6–19, 2026 (14 days)**
## 1. Trend Analysis (14-Day Daily)
| Date | Impr | Clicks | Cost | Conv | CTR | CPC | Impression Share | Budget Lost IS |
|------|------|--------|------|------|-----|-----|-----------------|---------------|
### Key Inflection Points:
- **Apr 14 anomaly**: Impressions spiked to 260 (vs. ~100-130 avg), IS jumped to 42%, budget lost IS dropped to 50%. This suggests either competition dropped temporarily or a budget increase. Yet CTR cratered to 12.7% — the extra impressions were low-quality.
- **Apr 14–18 improvement**: After the spike, impression share stabilized at 20-22% (up from 11-14% in week 1). Something changed — possibly a budget adjustment or competitor withdrawal.
- **Conversions are sporadic**: Only 2 in 14 days (Apr 11 and Apr 13), then 6 straight days of zero. This is a dangerously thin data set for any automated bidding.
### The #1 Problem: **Budget Strangulation**
This campaign is losing **75–88% of eligible impressions to budget**. You're only showing for ~11–21% of searches. The campaign is burning through its daily budget in a few hours, then going dark for the rest of the day. This means:
- You're missing high-intent evening/weekend searchers
- Google is optimizing for speed of spend, not quality of clicks
- Your 2 conversions came on days where IS was among the lowest (14%, 11.4%) — so even the small window is converting
## 2. Ad Group Breakdown
| Ad Group | Status | Clicks | Cost | Conv | CPA | CTR | CPC | % of Spend |
|----------|--------|--------|------|------|-----|-----|-----|-----------|
### Critical Finding:
**"Portugal Residency" is PAUSED but was your best-performing ad group.** It converted at $682 CPA vs. the main ad group's $2,050 CPA — **3x more efficient**. It also had a higher CTR (26% vs 22.3%).
**"Portugal Citizenship by Investment"** has spent $146 with zero conversions but a lower CPC ($5.83 vs $7.45). Small sample — needs more data before judging.
**"Portugal Golden Visa Fund"** and **"Mercan Brand"** are negligible volume. The Fund group has a 9.1% CTR — something is off with ad relevance or keyword intent there.
## 3. Keyword Efficiency Map
### Winners (converted):
| Keyword | Match | Clicks | Cost | Conv | CPA | QS |
|---------|-------|--------|------|------|-----|-----|
### Losers (high spend, zero conversions):
| Keyword | Match | Clicks | Cost | Conv | QS |
|---------|-------|--------|------|------|-----|
### The Elephant in the Room:
**[EXACT] "portugal golden visa" has consumed $828 (28.5% of total spend) with ZERO conversions.** This is your highest-volume keyword but it's a pure money drain. Combined with the phrase match variant, that's **$1,177 (40.5% of spend) on "portugal golden visa" variants with 0 conversions.**
Meanwhile, the reverse word order **"golden visa portugal"** converted at $277 CPA, and a residency-intent keyword converted at $134.
## 4. Quality Score Audit
| QS | Keywords | Combined Spend | Impact |
|-----|----------|---------------|--------|
**QS impact**: The QS 1 keywords are costing you an estimated 50-100% premium on CPC. At $7+ per click, fixing "permanent residency in portugal" from QS 1 to QS 5+ could save ~$50-80 over the period, or get you more impressions for the same spend. However — it also converted, so don't kill it; fix the relevance.
## 5. Search Term Quality
**224 unique search terms in 14 days** from 296 tracked clicks ($2,158 tracked).
### Waste Assessment:
| Category | Terms | Clicks | Cost | Conv | Verdict |
|----------|-------|--------|------|------|---------|
**Estimated wasted spend: $312–$460 (14–21% of total)** on informational/non-investment-intent terms.
Notable irrelevant search terms to negative:
- "d 7 visa portugal" — D7 is a completely different visa program
- "how to get residency in portugal for eu citizens" — they already have EU residency rights
- "portugal residency requirements" — generic research, not investment buyer
## 6. Budget Allocation Analysis
**Current state**: ~$200/day budget, losing **75–88% of impressions to budget**.
The budget is being consumed primarily by the "Portugal Golden Visa" ad group (70.6%), which has the worst CPA ($2,050). Meanwhile:
- The best-performing ad group ("Portugal Residency" at $682 CPA) is **PAUSED**
- "Portugal Citizenship by Investment" gets only 5% of spend and needs more data
- The budget is too small to even learn — at 2 conversions in 14 days, no automated bidding strategy can optimize
**Budget math**: At ~$200/day and ~28 clicks/day averaging $7.30 CPC, you're getting roughly 28 chances per day to convert. With a ~0.5% conversion rate (2/397), you need **200 clicks per conversion** — meaning one conversion every ~7 days. This is far below the threshold for any meaningful optimization.
## 7. Strategic Recommendations (Prioritized)
### #1: RE-ENABLE "Portugal Residency" Ad Group — HIGH IMPACT, ZERO EFFORT
**Why**: It converted at $682 CPA (3x better than the main ad group) and had higher CTR. It's paused and bleeding money by pushing all traffic to the less efficient "Portugal Golden Visa" ad group.
**Action**: Re-enable immediately. This alone could cut CPA by 30-40%.
### #2: Pause or Restructure the Money-Bleeding Keywords — HIGH IMPACT, LOW EFFORT
**Immediate**:
- **Pause [EXACT] "portugal golden visa"** — $828 spent, 0 conversions. The phrase match variant and "golden visa portugal" are covering this traffic. Or at minimum, drop its bid significantly.
- **Pause [EXACT] "i want to move to portugal from usa"** — $275 spent, 0 conv, QS 5. This is lifestyle intent, not investor intent.
- **Add negative keywords**: "d7 visa", "eu citizens", "digital nomad", "retire", "nhr" (these are wrong-program or wrong-audience terms)
**Estimated savings**: $300-500/14 days, which can be reallocated to converting keywords.
### #3: Fix the Budget Constraint — Highest strategic impact, requires budget decision
**The campaign is invisible 80% of the time.** Two options:
**Option A — Increase budget to $400/day**: This would roughly double impression share from ~15% to ~30%, give you more conversion data, and let Google's algorithm find better times/audiences. At $400/day you'd spend ~$12K/month — still reasonable for a product with $20K-$100K deal value.
**Option B — Cut waste first, then reallocate**: Pausing the money-bleeding keywords (#2 above) could save ~$80-100/day. Combined with re-enabling the Residency ad group, you'd effectively get a "budget increase" without spending more.
**My recommendation**: Do #1 and #2 immediately (today). Then measure for 7 days. If CPA improves but volume is still thin, push for a budget increase to $350-400/day.
### Bonus: Quality Score Fix for "Permanent Residency in Portugal"
This keyword has QS 1 but actually converted. The ad copy in the "Portugal Residency" ad group likely doesn't mention "permanent residency" specifically. Creating an ad variant with "permanent residency" in Headline 1 could push QS from 1 to 5+, reducing CPC by ~30% on this term and getting more impressions. Low effort, moderate upside.
**Bottom line**: This campaign is spending $2,900 every 14 days, getting only 2 conversions at $1,451 CPA. The fix isn't more spend — it's stop funding losers ($1,177 on "portugal golden visa" variants with 0 conversions), re-enable winners (the paused Residency ad group), and negative out the research-phase traffic (14-21% waste). That alone should cut CPA by 40-50% before touching the budget dia
— *PPC Strategist*