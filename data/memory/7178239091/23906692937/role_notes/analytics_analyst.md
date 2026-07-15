# Analytics Analyst Notes

**Last updated:** 2026-07-04 23:16

**Task:** Audit campaign "Greece GV — Plan B — Search — US Tier-1" (id 23906692937) — compare the most recent period vs the period before it.
1. Performance vs the comparison window: spend, clicks, conversions,

**Critical Details:** GTM-KWFH5X9T
## Analytics Analyst — Greece GV Plan B | Period Audit | 2026-07-04
### 1. Period-vs-Period Performance
Splitting the 14-day window into two 7-day blocks:
|---|---|---|---|
| CPA | ∞ | ∞ | — |
**Anomaly — impression collapse, spend mostly held:** Impressions fell 65% but spend only dropped 25%. The rising CTR is an artifact — fewer impressions means only the highest-intent auctions cleared, not a real CTR improvement. CPC is unchanged, so Google kept winning expensive clicks but on a much narrower inventory. This is consistent with reduced impression share, likely from increased competi
### 2. Budget Pacing and Waste
**Pacing:** Daily spend in P1 ran $85–$117/day (avg $102 — near budget ceiling). P2 collapsed Jun 27–30 ($29–$58/day) then recovered Jul 1–3 ($115–$117). Today (Jul 4, partial): $102 on 7 clicks by mid-day — on pace to hit or exceed budget.
**Waste — this is the real story.** AG3 (EU / Second Residency by Investment) is driving 61% of all-time spend:
| Ad Group | Clicks | Spend | Conv | % of Total Spend |
|---|---|---|---|---|
AG3's broad EU-level keywords ("residency by investment europe," "eu golden visa real estate," "eu residency for americans") are matching to every EU program on the planet. The search term report confirms it:
|---|---|---|---|
**Visible country-leakage waste in the last 7 days alone: ~$160.** This is only the top 40 terms — the real figure is higher.
### 3. Single Biggest Fix
**Add country-level PHRASE negatives at the campaign level.**
The terms above confirm AG3's keywords are matching across all EU golden visa programs. None of these clicks are Greece prospects. Adding the following as Phrase negatives stops the bleed immediately — zero downside risk since these terms have no path to Greece conversion:
Negatives to add: `"portugal"`, `"spain"`, `"albania"`, `"latvia"`, `"malta"`, `"cyprus"`, `"croatia"`, `"montenegro"`, `"greece reddit"` (the last one appears as 0-click but is low-quality informational).
**Estimated weekly impact: ~$130–$200 saved** on visible country-leakage terms. The actual recovery is likely higher once the full 40+ search terms in the report are accounted for.
This is a low-impact action per campaign rules — based on actual search term data, no confirmation needed. I can execute immediately.
**One flag before I close:** 0 conversions after $3,256 spend and 232 clicks is not a tracking failure (GTM-KWFH5X9T + action 7144337715 were verified end-to-end 2026-03-19). It is a funnel problem — AG3 is eating most of the budget on comparison-stage, program-agnostic searches that are not Greece-intent. The country negatives are fix #1; the deeper fix is AG3 bid containment once the waste is cl
Want me to execute the country negatives now?
— Analytics Analyst