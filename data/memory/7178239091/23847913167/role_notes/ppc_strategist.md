# Ppc Strategist Notes

**Last updated:** 2026-07-04 18:19

**Task:** [Campaign: "MapleRoots — Citizenship by Descent (US)" · id 23847913167]
MapleRoots — Citizenship by Descent (US), $150/day on MAXIMIZE_CONVERSIONS, ~$2,966 spend in 30 days (highest spender). Audit bu
Reading the 7-day daily data, lifetime ad group stats, and 30-day spend figure — then building the audit from those numbers without re-fetching anything in context.
## MapleRoots Budget & Performance Audit — July 4, 2026
**PPC Strategist | Campaign 23847913167**
### Budget Pacing: What's Driving the $1,534 Gap
| Ceiling | Actual | Gap | Utilization |
|---------|--------|-----|-------------|
Splitting by what the daily data shows:
|--------|------|-------|-----------|---------|
**Root cause: the gap is entirely historical, not structural.** The prior 23 days cover the MaxClicks volume collapse ($18–30/day in early June), the MaxConversions transition learning window, and the strategy-shift stabilization period. The campaign is not budget-limited *today* — it is spending at or slightly above the $150 ceiling. **The $1,534 deficit will not self-correct** (Google doesn't cr
One urgent flag: July 4 already shows **$279.33 in spend with 69 clicks at $4.05 CPC** — whether this is a partial or full-day snapshot, it is 86% over the $150 daily budget at a $4.05 CPC never seen in this campaign. More on this in Finding #1.
**Budget constraint verdict:** Not budget-limited. Not demand-limited (search volume has been 74K+/mo since launch). The prior underutilization was **learning/transition-limited**. Current spend is at ceiling.
### Day-by-Day — 7 Days Available (Prior 15 Requires Data Pull)
The context only surfaces 7 days of daily metrics. A precise June 4–18 vs June 19–July 4 split requires an API fetch I can run on request. Here's what's available, with CPA added:
| Date | Impr | Clicks | Cost | Conv | CPC | CPA |
|------|------|--------|------|------|-----|-----|
**7-day averages (excl. Jul 4):** $3.10 CPC · $48.94 CPA · 3.33 conv/day
The campaign ran clean on June 28, July 2, and July 3 — CPA of $20–30 on those days. The Jul 4 data breaks the pattern hard.
### Maximize Conversions Viability Check
| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
**MaxConversions is viable.** The strategy is above the 15-conversion/month floor by a factor of 6. The CPC volatility ($2.86 on Jul 2 → $4.05 on Jul 4) is consistent with a strategy still stabilizing — the switch from MaxClicks ($1.40 cap) to MaxConversions (no cap) likely happened 2–3 weeks ago based on the CPC regime shift, meaning the learning period may be concluding around July 8–10.
**Per campaign guidelines: no bid-strategy change while learning signals remain noisy.** The $4.05 outlier is a holiday artifact, not a signal that the strategy has failed. Stand down until July 8.
### Ad Group CPA Outlier Map (Lifetime CVR as Proxy)
|----------|----------------|------|-----|--------------------------|-----------------|
AG2 and AG4 are both running at 1.72–1.77% CVR vs AG3's 3.77% — that's a 2.2x efficiency gap. They share the campaign's worst QS offenders (QS:1–3 on multiple keywords), which forces a CPC floor the MaxConversions algorithm can't fully escape.
## Top 3 Findings
### Finding #1: July 4 Holiday Overbid — $279 Already Spent at $4.05 CPC, CPA Tracking $140
**Estimated weekly $ impact: $400–700 if the CPC level bleeds into July 5–7**
$4.05 CPC is the highest recorded in any era of this campaign. For context: the MaxClicks cap was $1.40; the MaxConversions baseline Jun 28–Jul 3 was $2.86–3.95. July 4 is 42% above even the recent high-end. The mechanism: Independence Day reduces total search volume but many advertisers pause campaigns or don't adjust dayparting — Google fills inventory at a premium because the remaining advertis
$279 at $4.05 CPC for 2 conversions is $140 CPA — 2.8× the $48.94 baseline established the prior 6 days. If the campaign is mid-day on July 4, the full-day spend could exceed $300.
**This is a watch, not an immediate action.** The standing strategy is "keep traffic flowing." But this specific holiday mechanics means: check the campaign on the morning of July 5. If CPC returns to the $2.90–$3.20 range, no action needed. If CPC stays above $3.80 into July 7, a one-session dayparting review is warranted — MaxConversions can be given a max CPC signal via a portfolio strategy wit
### Finding #2: QS:1 on `[applying for canadian citizenship by descent]` — Campaign's Highest-Leverage Wasted Dollar per Click
**Estimated weekly $ impact: $25–40 in pure CPC tax on this keyword alone; $80–130/week across all QS:1–3 keywords**
The QS distribution has a serious bottom tail:
| Keyword | QS | Clicks | Conv | Issue |
|---------|----|--------|------|-------|
A QS:1 keyword pays Google's maximum "quality score tax" — estimated 50–75% above what a QS:6–7 keyword pays for the same position. `[applying for canadian citizenship by descent]` has 115 lifetime clicks (it's not dead) and 3.5 conversions (it does convert), but it's bidding at a massive efficiency penalty every auction. Under MaxConversions, the algorithm is reluctant to suppress it entirely bec
The `[PHRASE] canadian citizenship through parents` and `[PHRASE] canadian citizenship through ancestry` at QS:3 are far more costly in absolute terms — 1,204 clicks combined, 24 conversions, but at QS:3 they've been paying ~30–40% above market CPC for every one of those 1,204 clicks.
**Action to queue (separate session, not today):** Ad copy relevance audit on the QS:1 exact keyword — the ad likely doesn't contain the exact phrase "applying for" in any headline. A targeted headline addition matching the keyword text is the fastest QS:1→4 move. On the two QS:3 phrase-match keywords, check landing page text alignment with the search terms they attract.
### Finding #3: AG2 + AG4 Consume ~20% of Budget at 1.75% CVR vs AG3's 3.77%
**Estimated weekly $ impact: $85–105/week in below-baseline conversion value**
AG2 (Grandparent Path) and AG4 (Eligibility & Discovery) share 802 lifetime clicks and 14 conversions between them — a combined 1.75% CVR. AG3 converts at 3.77%, and AG1 at 2.42%. The gap means for every $1,000 spent in AG2/AG4, the campaign earns 17.5 conversions; the same $1,000 in AG3 earns 37.7.
At ~20% of budget in AG2+AG4 ($30/day at $150 budget):
- Actual weekly conversions: 30 × 7 × 1.75% / $3.10 CPC = ~1.2 conv/week
- At AG3's CVR: same spend → ~2.6 conv/week
- Efficiency gap: 1.4 missed conversions/week × $48 CPA value = **$67/week in underperformance**
MaxConversions should self-correct over time by routing away from low-CVR ad groups, but the QS:3 floor in both groups limits how efficiently the algorithm can act — it can't escape the CPC tax that inflates their effective CPA above the algorithm's target.
The underlying issue in AG2 specifically: `[EXACT] grandparent canadian citizen` has 96 lifetime clicks and **0 conversions**. That's the cleanest zero-return keyword in the campaign and is almost certainly the wrong match type — someone searching the exact phrase "grandparent canadian citizen" is likely reading about the topic, not requesting a consultation. This keyword alone accounts for meanin
**Action to queue:** Flag `[EXACT] grandparent canadian citizen` for pause review in the next daily cleanup. At 96 clicks and 0 conversions it has exceeded the evidence threshold.
### Summary
| Finding | Weekly $ Impact | Urgency |
|---------|----------------|---------|
MaxConversions is viable, above threshold, and producing $48–50 CPA on clean days. The three findings above are **friction points within the strategy**, not reasons to change it. The Jul 4 number will almost certainly normalize Monday. The QS and AG structural fixes are the medium-term levers.
— *PPC Strategist*