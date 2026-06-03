# Ppc Strategist Notes

**Last updated:** 2026-06-02 15:37

**Task:** Bid strategy review for "Greece Golden Visa - Turkey":

1. Current bid strategy and how long it's been active
2. Is the campaign in learning phase? If so, when will it exit?
3. Conversion volume analy

**Critical Details:** GTM-WZKDXFH8
Let me pull the bidding strategy details — this isn't in the context data.The MCP tools are erroring. Let me try the GAQL query tool with a simpler query.MCP tools are consistently failing. Let me work with what I know from context and prior sessions.
## Bid Strategy Review — Greece Golden Visa Turkey (23758877756)
**PPC Strategist | 2026-05-20**
### 1. Current Bid Strategy & Duration
From the campaign guidelines and prior sessions, this campaign uses **Maximize Conversions** (same as the main Greece GV campaign which runs Maximize Conversions with $60 Target CPA). The campaign was created/launched around early May 2026, making the strategy **~3 weeks old** — though 8 of those days were dark (May 11–18), so effective runtime is closer to **12 days**.
I couldn't pull the exact strategy details due to MCP tool errors. If you can confirm the bidding strategy type, I can sharpen this analysis.
### 2. Learning Phase Status
**Effectively YES — the campaign is in a quasi-learning state**, but not the formal Google "Learning" badge:
- **0 conversions** in the campaign's entire lifetime (99 clicks, $467.59 spent)
- Conversion tracking was **broken until today** (GTM-WZKDXFH8 Version 12 just published)
- The algorithm has had **zero conversion signals** to learn from — it's been bidding blind
Even if Google doesn't show "Learning" status, the bidding algorithm has no conversion data to optimize against. It's functionally in a worse state than learning — it's **uninformed**.
**When will it exit?** The clock starts NOW (conversion tracking live as of today). Google needs **~15 conversions in 30 days** for Maximize Conversions to stabilize. At the current volume (~5 clicks/day), even an optimistic 10% conversion rate gives ~1 conversion every 2 days = ~15 conversions in 30 days. Realistically, expect **4–6 weeks** before the algorithm has usable signal.
### 3. Conversion Volume Analysis
| Metric | Value | Threshold | Verdict |
|--------|-------|-----------|---------|
**Verdict: This campaign does NOT have enough data for automated bidding.** Maximize Conversions with 0 conversions is the worst possible scenario — the algorithm has no signal, so it bids aggressively on whatever Google's broad model suggests, resulting in $69.95 clicks on QS 1 keywords.
### 4. Should We Switch? — YES
**Current state: Maximize Conversions with 0 conversions = algorithm bidding blind.**
This is the root cause of the $69.95 click and the $16.21 average CPC today. Without conversion data, Maximize Conversions defaults to aggressive auction behavior with no guardrails.
**Recommended switch: Manual CPC with Enhanced CPC (eCPC) OFF**
| Why Manual CPC | Rationale |
|----------------|-----------|
| Full CPC control | You set the max bid per keyword — no $69 surprises |
| Appropriate for 0-conversion campaigns | Per account guidelines: "fewer than 15 conversions/month → Manual CPC or Maximize Clicks with cap" |
| Collect clean data | Let conversion tracking prove itself over 2–4 weeks with controlled spend |
| Preserve budget | At $10 max CPC, you get ~8-10 clicks/day instead of 1-2 inflated clicks |
**Suggested max CPC bids by ad group:**
| Ad Group | Suggested Max CPC | Rationale |
|----------|-------------------|-----------|
**Do NOT switch to Target CPA yet.** There's no CPA data to set a target from. Target CPA with 0 historical conversions will either not spend at all (if target is too low) or overspend wildly (if target is too high). We need 15–30 conversions first.
### 5. When to Switch Back to Automated
**Milestone plan:**
| Phase | Conversions | Action |
|-------|-------------|--------|
### 6. CPA Comparison (Projected)
|----------|-------------|-------------|---------------------------|---------------|
These are estimates based on the pre-dark CPC average ($4.13) and assuming conversion tracking now works. Manual CPC gives the most predictable spend and the best chance of collecting clean conversion data.
### Recommendation
**Switch from Maximize Conversions → Manual CPC** with these bids:
- yunanistan-golden-visa: $8.00
- yunanistan-oturum-gayrimenkul: $6.00
- greece-golden-visa-en: $5.00
This is a **high-impact change**. Want me to execute it?
After 30+ conversions (est. 4–6 weeks), we reassess and move to automated bidding with real data backing it.
— *PPC Strategist*

---

## Session Log

### 2026-05-21 13:47 — we should optimize the quality score and never let it 1 whats the plan?

**Task:** we should optimize the quality score and never let it 1 whats the plan?
## Quality Score Optimization Plan — Greece Golden Visa Turkey
**Current state:** 4 keywords at QS 1, 2 at QS 2, rest at 3-5. The QS 1 keywords are costing you 5-10x what they should.
### Current QS Map
| Keyword | QS | Ad Group | Problem |
|---------|:--:|----------|---------|
### The 3 QS Levers (and what's broken)
QS = **Ad Relevance** + **Landing Page Experience** + **Expected CTR**
| Component | Status | Fix |
|-----------|--------|-----|
| **Expected CTR** | ⚠️ Low because ad copy doesn't match search intent | Improves automatically once ad relevance improves |
**Root cause is clear: Turkish keywords are served English ads.** That's a QS killer — Google sees zero keyword-to-ad-copy match.
### The Plan (3 phases)
#### Phase 1: Turkish RSAs for Turkish Ad Groups (do now)
Create new Turkish-language RSAs for the two Turkish ad groups. The English ad group keeps its current ads.
**Ad Group: yunanistan-golden-visa** (QS 1-5, 109 clicks)
| # | Turkish Headline | Rationale |
|---|-----------------|-----------|
| # | Turkish Description |
|---|-------------------|
| 1 | Yunanistan Golden Visa ile AB oturma izni alın. 250.000€'dan başlayan gayrimenkul yatırımı. Ücretsiz danışmanlık için hemen arayın. |
| 2 | Aileniz için güvenli bir gelecek planlayın. Yunanistan'da gayrimenkul yatırımı yaparak AB oturma izni kazanın. 3700+ yatırımcı bize güvendi. |
| 3 | Uzman ekibimiz tüm süreçte yanınızda. Yunanistan altın vize programı hakkında ücretsiz bilgi alın. Hemen başlayın! |
| 4 | Yunanistan'da mülk sahibi olun, AB oturma izni kazanın. Yatırım danışmanlığı için ücretsiz randevu alın. |
**Ad Group: yunanistan-oturum-gayrimenkul** (QS 1-5, 51 clicks)
Same 15 headlines with slight keyword emphasis shifts:
| # | Adjusted Headlines |
|---|-------------------|
| 4–15 | Same as above (shared headlines work for both groups) |
Same 4 descriptions (they cover both ad groups' keyword themes).
#### Phase 2: Pause the Old English RSAs in Turkish Ad Groups (after new ads approved)
Once the Turkish RSAs are approved and serving (~24-48 hours), pause the English RSAs in:
- yunanistan-golden-visa (ad 809379571597)
- yunanistan-oturum-gayrimenkul (ad 809379572116)
Keep the English RSA in greece-golden-visa-en (ad 809344396278) — that ad group has English keywords.
#### Phase 3: Monitor QS Recovery (7-14 days)
| Day | Expected QS Change |
|-----|-------------------|
| Day 1-3 | Ad Relevance improves (Turkish ads match Turkish keywords) |
| Day 3-7 | Expected CTR improves (better CTR from relevant ads) |
| Day 7-14 | Landing Page Experience re-scored (already Turkish LP) |
| Day 14+ | Target: all keywords QS 4+ |
### QS Prevention Rules Going Forward
1. **Language match is mandatory** — every ad group's RSA must be in the same language as its keywords
2. **QS check on every new keyword** — before adding a keyword, confirm there's an ad with that language/theme in the ad group
3. **QS 2 = investigation trigger** — don't wait for QS 1. If any keyword drops to 2, check ad relevance and LP match immediately
4. **Weekly QS scan** — pull keyword QS every Monday and flag anything below 4
### Approval Needed
This is a **medium-impact change** (new ads, same landing page and targeting). Want me to:
1. Create the Turkish RSAs for both ad groups now?
2. Wait to pause the English RSAs until the new Turkish ones are approved?
Say the word and I'll execute Phase 1.
— *PPC Strategist*

### 2026-06-02 15:33 — Daily + weekly performance audit of Greece Golden Visa - Turkey (23758877756) us

**Task:** Daily + weekly performance audit of Greece Golden Visa - Turkey (23758877756) using ONLY the 14-day data in context (May 19→Jun 2). 1) Day-by-day read: confirm the May 20 CPC disaster ($16.21/$81.03) 
## Daily + Weekly Performance Audit — Greece Golden Visa Turkey (23758877756)
**PPC Strategist | 2026-06-02 | 14-day window May 19 → Jun 2**
### 1. Day-by-Day Read — the May 20 disaster vs. the Manual CPC band
| Date | Cost | CPC | Note |
|------|------|-----|------|
**Confirmed:** Every single day after May 21 sits inside **$2.56–$6.08** — exactly the Turkey-normal range. The Manual CPC fix held for 12 straight days. **Zero drift.** The May 20 $16.21 CPC was a one-time auto-bid + QS-1 event, not a trend.
### 2. Weekly Roll-Up
|--------|------|------|------|
**14-day totals:** **$620.69 spend · 142 clicks · 1 conversion · blended CPC $4.37 · CPA $620.69.**
> Note: the question cites "290 clicks" — the daily table in context sums to **142 clicks** over these 14 days. The 313-click figure in the ad-group block is **lifetime** (since the early-May launch), not this window. I'm using the 142 the daily data supports. CPA of $620.69 is correct against $620.69 / 1 conv.
CPC trending **down** week-over-week (-16%), CTR holding ~7.5%. The auction is healthy and predictable. The problem is not the auction — it's the **single conversion**.
### 3. Bidding Verdict — KEEP Manual CPC
**Do NOT move to automated bidding.** Per account guidelines and the playbook:
- Maximize Conversions / Target CPA needs **15+ conversions in a rolling 30 days** to optimize.
- This campaign has **1 conversion in 14 days**. Auto-bidding would bid blind again — exactly what caused the May 20 $81 day.
- **Revisit threshold:** once the campaign logs **≥15 conversions in 30 days** (realistically 4–6 weeks at current volume *if* CVR improves), reassess Target CPA. Not before.
Manual CPC is the correct, disciplined choice right now. Stay the course.
### 4. Budget Allocation — Reallocate Away from the EN Group
Lifetime ad-group spend (since launch — note this is *not* the 14-day figure):
| Ad Group | Clicks | Spend | Conv | CPA | Verdict |
|----------|--------|-------|------|-----|---------|
**Recommendation — pause `greece-golden-visa-en`:**
- It's an **English** ad group (only 1 ENABLED RSA, `809344396278`) targeting **Türkiye-located** users. The Turkish groups carry all the intent and the only conversion.
- $241 spent, **0 conversions**, on broad English Greece terms that overlap the wrong-audience pattern (see the `properties for sale` waste flagged by Search Term Hunter).
- Pausing it redirects that ~$0.50–$1/day of wasted budget into the two Turkish groups where the converting intent lives.
**Proposed reallocation** (within the existing daily budget — no budget increase):
- **yunanistan-golden-visa** → primary, keep the strongest bids; it has the conversion signal.
- **yunanistan-oturum-gayrimenkul** → give the saved EN spend here; on-language, cheap CPC, untested headroom.
- **greece-golden-visa-en** → **PAUSE.**
Pausing an ad group is a **medium-impact** change — and the GTM Specialist held this exact item (#4) on Jun 2 pending a double-check. **Want me to pause `greece-golden-visa-en` now, or are you still verifying it?**
**Bottom line:** The auction is fixed and stable — CPC band $2.56–$6.08, CTR ~7.5%, CPC trending down. The remaining problem is the **0.7% CVR / 1 conversion** (a landing-page funnel issue per CRO, not a bidding issue). Don't touch the bid strategy. Pause the dead EN group, feed the Turkish groups, and let the form fixes do the heavy lifting.
— *PPC Strategist*

### 2026-06-02 15:37 — You already produced your report. Now review your PEERS' reports below and cross

**Task:** You already produced your report. Now review your PEERS' reports below and cross-examine them.

FOCUS: Reconcile the central conflict: is the 1-conv-in-14-days / 0.34% CVR a TRACKING problem (analytic
## PPC Strategist — Cross-Examination
### 1. Conflicts with my view
**Search Term Hunter: "Add negatives NOW" + "Add keywords NOW"**
I partially disagree on sequencing. The one-change-per-day rule means the team can't add negatives, pause the EN group, AND add keyword-level bid caps on the same day — and Search Term Hunter's "Now" column has six simultaneous actions. Before any execution, we need a day-by-day calendar. My sequencing proposal:
- **Day 1 (today):** Campaign-level negatives only (`properties for sale`, `nasıl alınır`, `ekşi`, `emekli`, `ev fiyatları`, `nedir`) — these are low-impact, no structural risk
- **Day 2:** Pause `greece-golden-visa-en` (medium-impact, requires confirmation)
- **Day 3:** Keyword-level bid caps on the two QS-1 terms ($3–4 ceiling)
- **Jun 4+:** RSA headline pins + citizenship-pathway keyword adds together (same intent cluster, coordinate with Creative Director)
Nobody on the team proposed this calendar. That's the operational gap.
**Analytics Analyst: "Don't touch bidding"**
Agreed — and I said this first. No conflict. But the Analyst's framing implies the form fix is the *only* lever. I'd add: the EN group pause is also a conversion-rate lever — removing $241 of zero-converting spend raises the **campaign-level CVR** mechanically even before the form is fixed. These are not mutually exclusive.
### 2. Where I concede
**Analytics Analyst is right on the CVR denominator.** I used the 14-day window (0.70%); the post-fix window (0.75%) is more honest. Lifetime 0.32% is misleading because ~179 of those clicks hit a broken tracking setup. I'll use 0.75% as the baseline going forward.
**Analytics Analyst's CRM reconciliation point is valid and I missed it.** I called the May 23 conversion "signal" without flagging that it hasn't been matched against a real Gravity Forms lead row. That's a 30-minute reconciliation task — check the GF entry log for a submission timestamped ~May 23, match to the GCLID. If no row exists, the "1 conversion" is a measurement artifact and the CVR disc
**Creative Director is right on EN group pause rationale.** I flagged the $241/0-conv problem; they added the LP mismatch framing (English ad → Turkish page) which is the cleaner argument. Conceded — their framing is stronger than mine.
### 3. What the team collectively missed
**Critical: Language targeting "Czech" has never been verified live.** Context data shows `Languages: English, Czech`. GTM Specialist notes say English + Turkish was set May 19. These cannot both be true. If Czech is still active, Google may be partially allocating impressions against Czech-speaker signal in Türkiye — a near-zero audience that wastes match quality. More importantly, if Turkish was
**The Manual CPC budget mechanics are broken in the team's reallocation logic.** Both Creative Director and I said "redirect EN budget to Turkish groups." Under Manual CPC with no daily budget constraint (we're spending $30–50/day, not hitting a cap), pausing EN doesn't move money anywhere — it just goes unspent. To actually redirect it, we'd need to either raise bids on the Turkish groups or incr
**May 30–31 anomaly unaddressed.** May 30: 7 clicks, $17.91. May 31: 3 clicks, $18.25. That's 30–65% below the campaign's daily average, on consecutive days. No one flagged whether this is a weekend pattern (May 30 = Friday, May 31 = Saturday) or a signal of something structural. If this is a weekend dip, the campaign may benefit from a bid schedule — lower bids Fri–Sun, concentrate spend Mon–Thu 
**Prioritized sequence (team consensus position):**
| Day | Action | Owner | Type |
|-----|--------|-------|------|
| Today | Verify language targeting live (read-only API check) | PPC | Verify |
The form fix (9→3 fields + dead-click bugs) sits outside this table — it's the highest-leverage action in the entire campaign but belongs to the LP team, not the ads team. That brief should go out today in parallel.
— *PPC Strategist*
