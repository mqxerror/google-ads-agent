# Ppc Strategist Notes

**Last updated:** 2026-07-20 16:22

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

### 2026-07-06 16:35 — I though we fixed teh languages issues a month ago,
ignore the form we already o

**Task:** I though we fixed teh languages issues a month ago,
ignore the form we already optimized it what about the headline why the changes?
Short version: you're crossing **two different "language" fixes**. One is real and working. The other never actually applied — which is why it still looks broken.
## 1. Language TARGETING — no, it was never actually fixed
The live targeting on this campaign right now reads: **`Languages: English, Czech`.**
Here's what happened. On **May 19** the GTM Specialist removed Korean and "added Turkish" — but used language constant **`1021`**. That ID is **Czech**, not Turkish. Turkish is **`1037`**. So the fix a month ago swapped Korean → **Czech** while everyone recorded it as "Turkish added." That single wrong digit is why 3 specialists kept re-flagging "English, Czech" on Jun 2, Jun 8, and Jul 4 — it was
Impact: near-zero — almost nobody in Türkiye has their Google UI set to Czech, so you're leaning on "English" to catch Turkish speakers. It's a QS/relevance suppressor, and it costs nothing to correct.
**This is a 30-second fix:** remove Czech (`1021`), add Turkish (`1037`). Want me to execute it? (Targeting change — I'll confirm the live criteria with one query, then apply.)
## 2. The HEADLINE changes — a completely separate lever, and this one worked
The headline changes have nothing to do with campaign targeting. They fix **ad-copy relevance**:
- Turkish keywords (`yunanistan golden visa`, `oturum izni`) were being served **English** headlines → Google saw zero keyword-to-copy overlap → **Ad Relevance "Below Average" → QS 1 → 5–10x CPC premium** (that's what caused the $69.95 click on May 20).
- **Fix (done May 21):** built Turkish RSAs `809590104375` + `809625956041`, paused the English ones. Both are live now.
Proof it's working — QS climbed since:
| Keyword | Then (QS) | Now (QS) |
|---|---|---|
**One gap remains:** the extra citizenship headlines planned for Jun 4 ("Ev Alarak Oturma İzni", "7 Yılda Vatandaşlığa Yol") appear **never added** — proof: `yunanistan ev alarak oturma izni` is **still QS 1** (5 clicks, 0 conv). That's the last stuck keyword.
**Bottom line:** headline/copy fix = real and working. Targeting fix = botched a month ago (Czech, not Turkish). Say the word and I'll (a) correct Czech→Turkish and (b) add the two citizenship headlines — different change types, so they don't collide under one-change-per-day.
— *PPC Strategist*

### 2026-07-14 15:45 — Structural 'why it sucks' synthesis from context data only — no tool calls. Rank

**Task:** Structural 'why it sucks' synthesis from context data only — no tool calls. Rank the causes of zero leads by $ impact using the fresh 15-day daily table: 1) CPC/spend discipline is slipping — Jul 6 ($

**Critical Details:** GTM-WZKDXFH8
## Structural Breakdown — Why This Campaign Has Zero Leads ($1,057 / 15 Days)
**Ranked by dollar impact:**
**#1 — CPC band breach + impression spike: ~$300 excess over 3 days**
Jul 6 jumped to 439 impressions (vs. 44–170 surrounding days) and $172.82 spend. Jul 7–8 ran $127–119. CPC ceiling certified at $6.08; Jul 6 ($6.40), Jul 8 ($6.64), Jul 10 ($6.77), Jul 12 ($7.27), Jul 14 ($7.06) all breach it. Most plausible trigger: the Jul 6 citizenship keyword additions (ev almak vatandaşlık, ev alınca vatandaşlık, oturum için ev almak) expanded matching into noisier, higher-CP
**#2 — Informational waste: ~$121 of visible 7-day search spend (41%)**
şartları cluster alone: $44.28 + $21.70 + $12.50 + $0.57 + $0.83 = **$79.88**. nedir: $28.35. nasıl alınır: $11.83. ekşi: $1.14. Researchers, never converts. Extrapolated ~$259/15d.
**#3 — EN group still ENABLED: ~$60–90/15d wasted**
`greece-golden-visa-en` (198513892027): $361 lifetime / 0 conversions. English ad → Turkish LP. Pause deferred since Jun 2, now 42 days overdue.
**#4 — Czech targeting: $0 direct, QS drag amplifies #1**
Constant 1021 (Czech) still live, Turkish (1037) never applied. Fix: one API call.
**Execution calendar (one-change-per-day; analyst's browser GTM check runs in parallel):**
| Day | Action | Type |
|-----|--------|------|
*Conditional: If browser check (GTM-WZKDXFH8 on mercan.com/tr/yunanistan-altin-vize) confirms tracking is broken, freeze Jul 17 bid changes until restored — don't optimize spend on a campaign that can't record conversions.*
— *PPC Strategist*

### 2026-07-14 15:47 — Orchestrated finding

{
  "summary": "$1,057 / 15 days / 0 leads: a 3-day CPC+spend spike (~$300 excess, Jul 6-8) and ~$121/week in informational waste are the dollar leaders; pause EN group and add \u015fartlar\u0131 negatives recover the most spend fastest, Czech fix costs nothing and should go first today.",
  "findings": [
    {
      "claim": "CPC band breached since Jul 6 \u2014 certified ceiling $6.08, but Jul 12 hit $7.27 and Jul 14 $7.06 \u2014 driven by a 3-day impression/spend spike (~$300 excess) plausibly from Jul 6 keyword additions expanding into noisier match territory",
      "severity": "high",
      "confidence": 0.7,
      "sources": [
        "15-day daily table in context",
        "Jul 6 decision log: 3 PHRASE keywords added to oturum-gayrimenkul group"
      ],
      "disconfirmed_by": "API pull confirming no keyword additions or bid raises around Jul 5-6",
      "id": "c3-f0"
    },
    {
      "claim": "~41% of visible 7-day search spend (~$121 of $292) is informational \u2014 \u015fartlar\u0131 cluster $79.88, nedir $28.35, nas\u0131l al\u0131n\u0131r $11.83, ek\u015fi $1.14 \u2014 zero conversion probability by query intent",
      "severity": "high",
      "confidence": 0.92,
      "sources": [
        "7-day search term table in context (2026-07-14)"
      ],
      "disconfirmed_by": "Any of these terms recording a conversion in account history",
      "id": "c3-f1"
    },
    {
      "claim": "greece-golden-visa-en (198513892027) continues burning ~$60-90 in this 15-day window with 0 conversions due to English ad \u2192 Turkish LP mismatch; pause deferred 42 days",
      "severity": "medium",
      "confidence": 0.88,
      "sources": [
        "Ad group data: $361.22 lifetime / 0 conv",
        "Ad 809344396278 final_url: mercan.com/tr/yunanistan-altin-vize",
        "Chronicle: pause held since Jun 2"
      ],
      "disconfirmed_by": "Ad group showing any conversion in a fresh API pull",
      "id": "c3-f2"
    },
    {
      "claim": "Czech language tar

### 2026-07-14 16:55 — Arbitrate the user's structural fork using ONLY context data: (A) clone this cam

**Task:** Arbitrate the user's structural fork using ONLY context data: (A) clone this campaign keeping only what works vs (B) prune in place — AND design the $50/day hard cap. Key facts to use: campaign runs M
**Verdict: B — prune in place.**
On Manual CPC there is no algorithmic state to reset. What cloning costs vs. buys:
- **Costs:** fresh ad approvals (24–48hr + re-review risk), QS history erased (`golden vize` QS 5, `altın vize` QS 6, `greece golden visa program` QS 8 — all earned, all gone)
- **Buys:** nothing — no smart-bidding learning phase exists to protect or restart
**Budget math — the agreed cuts hit $50/day before touching the dial:**
| Move | Daily savings |
|---|---|
| Pause EN group (198513892027) | ~$6–9/day |
| şartları PHRASE + nedir PHRASE + nasıl alınır PHRASE + ekşi EXACT negatives (Jul 14 PPC synthesis) | ~$18/day |
| **Combined** | **~$24–27/day** |
~$70/day avg − $25 ≈ **$45/day** — already at target. Set $50/day cap only to block Jul-6-style spikes ($172.82, $152.70). **>20% reduction from current ceiling — explicit confirm required before executing.**
**One-change-per-day order:**
- Day 1: 4 campaign negatives (şartları PHRASE, nedir PHRASE, nasıl alınır PHRASE, ekşi EXACT)
- Day 2: Pause EN group + set $50/day budget
- Day 3: Czech (1021) → Turkish (1037)
- Day 4: Add `golden visa yunanistan` PHRASE at $5 bid; cap Jul-6 citizenship keywords at $5 within the certified band

### 2026-07-14 16:57 — Orchestrated finding

{
  "summary": "Prune in place (B) \u2014 Manual CPC makes cloning pointless; execute EN pause + 4 negatives to reach ~$45/day naturally, then set $50/day cap as spike guardrail (explicit confirm required).",
  "findings": [
    {
      "claim": "Prune in place (B) is correct \u2014 on Manual CPC, cloning resets earned QS history with zero algorithmic benefit and adds re-approval delay; the identical structural outcome is achievable in place",
      "severity": "high",
      "confidence": 0.93,
      "sources": [
        "Live roster: MANUAL_CPC confirmed 2026-07-14",
        "QS data in context: QS 5/6/8 on key terms",
        "Jul 14 PPC structural synthesis: same cuts executable in-place"
      ],
      "disconfirmed_by": "Evidence that an automated smart-bidding strategy is actually active, making a clean-slate learning reset worthwhile",
      "id": "c1-f0"
    },
    {
      "claim": "EN pause (~$6-9/day) + \u015fartlar\u0131-cluster negatives (~$18/day) saves ~$24-27/day, bringing ~$70/day average spend to ~$43-46/day \u2014 hitting $50 target before the budget setting is changed",
      "severity": "high",
      "confidence": 0.86,
      "sources": [
        "15-day daily table: $1,057/15d = $70.5/day avg",
        "Jul 14 Search Term Hunter: \u015fartlar\u0131 $79.88 + nedir $28.35 + nas\u0131l al\u0131n\u0131r $11.83 = $120.06/week (~$18/day)",
        "EN group context: $361 lifetime at ~$6-9/day run rate"
      ],
      "disconfirmed_by": "Live API pull showing current daily budget is already \u2264$50, making the budget change moot",
      "id": "c1-f1"
    },
    {
      "claim": "$50/day hard cap is required as spike guardrail \u2014 Jul 6 ($172.82) and Jul 12 ($152.70) show the campaign can 2-3x its average spend; this is a >20% change requiring explicit user confirm before execution",
      "severity": "medium",
      "confidence": 0.95,
      "sources": [
        "15-day daily table: Jul 6 $172.82, Jul 12 $152.70",
        "Account rule: >20% budge

### 2026-07-17 11:32 — Own the user's three-part fork: fix vs switch-to-Meta, $40/day budget, clone vs 

**Task:** Own the user's three-part fork: fix vs switch-to-Meta, $40/day budget, clone vs reduce. (1) The user explicitly asked for FRESH lifetime data — run ONE lifetime GAQL pull (campaign + ad_group level: c
I'll run the one lifetime GAQL pull the task requires, then reconcile. Let me load the google-ads query tool.The stream tool isn't in my allowed set. Let me use the allowed query tool.**Lifetime pull blocked** — the GAQL tool rejected both call forms (allowlist expects `search__execute_query`, loaded tool is `search_execute_query`; underscore mismatch). Reconciling instead against today's synced s
## PPC Strategist — Three-Part Fork | Greece GV Turkey (23758877756)
**1. Lifetime reconciliation (synced today).** $371.13 + $2,706.57 + $710.31 = **$3,788.01 / 734 clicks / 3 conv = $1,263/lead** — matches the cited baseline exactly. All 3 conversions sit in `yunanistan-golden-visa`; EN group ($371) and `oturum-gayrimenkul` ($710) are 0-conv.
**2. Clone vs prune — REUSE verdict B, prune in place.** Manual CPC has no learning state to reset; cloning erases earned QS (golden vize 5, altın vize 6, greece golden visa program 8) and adds 24–48h re-approval for zero gain. **Updated budget math:** Jul 3–17 avg = $1,223/15 = **$81.5/day**. EN pause (−$6–9) + 4 negatives (−$18) → ~$54–57/day, still ~$15 over. Close to $40 via bid-cap the 3 Jul-
**3. Meta vs fix.** The fixes were agreed Jun 2/Jul 14 and **never executed** — the campaign has never run in fixed form, so switching now tests nothing and forfeits earned QS. **Rule:** execute prune, run 14 days at $40/day (~$560); ≥1 verified lead → keep+optimize; 0 conv with tracking confirmed → pivot to Meta.
**Calendar (one change/day):** D1 — 4 campaign negatives (şartları PHRASE, nedir PHRASE, nasıl alınır PHRASE, ekşi EXACT); D2 — pause EN group `198513892027` + set $40/day (CONFIRM); D3 — Czech 1021→Turkish 1037; D4 — bid-cap Jul-6 citizenship keywords $4 + add "golden visa yunanistan" PHRASE at $5.

### 2026-07-17 11:33 — Orchestrated finding

{
  "summary": "Prune in place (never clone), cut to $40/day via EN pause + 4 negatives + Jul-6 bid-caps ($40 cap needs confirm), and fix-don't-switch: run 14 days at $40 and pivot to Meta only if 0 verified conversions.",
  "findings": [
    {
      "claim": "Lifetime reconciles to $3,788 / 734 clicks / 3 conv = $1,263/lead, with all 3 conversions in the yunanistan-golden-visa ad group",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "2026-07-17 15:24 synced ad-group lifetime totals (live GAQL pull blocked by tool-allowlist underscore mismatch)"
      ],
      "disconfirmed_by": "A successful lifetime GAQL pull returning materially different cost/conv totals",
      "id": "c1-f0"
    },
    {
      "claim": "Prune in place \u2014 do NOT clone; Manual CPC has no learning state and cloning erases earned QS 4/5/6/8",
      "severity": "high",
      "confidence": 0.93,
      "sources": [
        "Jul 14 arbitration (verbatim)",
        "MANUAL_CPC confirmed in roster 2026-07-17",
        "keyword QS in context"
      ],
      "disconfirmed_by": "Evidence an automated bidding strategy is actually active",
      "id": "c1-f1"
    },
    {
      "claim": "EN pause (\u2212$6-9) + 4 negatives (\u2212$18) reach ~$55/day; bid-caps on Jul-6 citizenship keywords + a hard $40/day budget close the gap to $40",
      "severity": "high",
      "confidence": 0.85,
      "sources": [
        "Jul 3-17 daily table = $1,223/15 = $81.5/day",
        "Jul 14 Hunter waste math"
      ],
      "disconfirmed_by": "Live pull showing current daily budget already \u2264$40",
      "id": "c1-f2"
    },
    {
      "claim": "Fix beats switching to Meta \u2014 the diagnosed fixes were never executed, so run 14 days at $40/day and pivot only if 0 conv with tracking verified",
      "severity": "high",
      "confidence": 0.82,
      "sources": [
        "Chronicle: EN pause/negatives/Czech fix agreed Jun 2 & Jul 14, no execution entries",
        "$20K-100K deal valu

### 2026-07-17 11:35 — Orchestrated finding

{
  "summary": "",
  "findings": []
}

### 2026-07-20 16:22 — Answer 'how is the campaign doing since the changes' — but FIRST audit whether t

**Task:** Answer 'how is the campaign doing since the changes' — but FIRST audit whether the agreed changes actually shipped, using ONLY the 2026-07-20 live data in context (no tool calls). Evidence to check ag
**Nothing shipped. We are still at Day 0 for campaign changes** — the premise "since the changes" has to be corrected before any performance read.
|---|---|---|
**7-day read (Jul 14–20):** $599.01 spend / 89 clicks / **0 conv**. Run-rate **$85.57/day** — 2.1× the $40 target and *slightly above* the $81.5/day baseline I set Jul 17. Spend is not down, it's up ~5%. CPC breached the certified $2.56–$6.08 band on **6 of 7 days** ($6.57–$7.49); only Jul 19 ($5.85) held inside. Conversion drought now **26 days** (last conv Jun 24).
**Bottom line:** it's performing exactly as before — ~$85/day, zero leads — because it was never touched. Only two *read-only* items closed Jul 19: browser JS-render check PASSED, PRIMARY flag CLOSED (per Jul 19 Director reconciliation). Measurement doubt is gone, so the drought is a real traffic/funnel problem — Day 1 is more urgent, not less. Execute.
— *PPC Strategist*

### 2026-07-20 16:22 — Orchestrated finding

{
  "summary": "Zero calendar changes shipped \u2014 we're at Day 0; last 7 days = $599/89 clicks/0 conv at $85.57/day (above target AND baseline), CPC breaching band 6 of 7 days, 26-day drought; measurement is now cleared so execute the negatives.",
  "findings": [
    {
      "claim": "None of the Day 1-4 calendar changes shipped \u2014 budget still $120/day, EN group still ENABLED, targeting still English+Czech, negatives blocked; campaign is at Day 0",
      "severity": "high",
      "confidence": 0.98,
      "sources": [
        "Live roster: Greece Golden Visa - Turkey $120.0/d MANUAL_CPC",
        "Ad-group list: 198513892027 ENABLED 70 clicks",
        "Targeting line: Turkiye | English, Czech",
        "Search Term Hunter Jul 18 execution report: allowlist underscore mismatch, Day 1 NOT applied"
      ],
      "disconfirmed_by": "A live pull showing budget=$40, EN group PAUSED, or Turkish (1037) applied",
      "id": "c1-f0"
    },
    {
      "claim": "Spend has not fallen \u2014 7-day run-rate is $85.57/day, above both the $40 target (2.1x) and the $81.5/day Jul-17 baseline",
      "severity": "high",
      "confidence": 0.99,
      "sources": [
        "Jul 14-20 daily table: $599.01 / 89 clicks summed",
        "Jul 17 baseline computation $1,223/15=$81.5/day"
      ],
      "disconfirmed_by": "A recount of the daily table totaling materially less than $599 over the 7 days",
      "id": "c1-f1"
    },
    {
      "claim": "CPC is running hot \u2014 6 of 7 days ($6.57-$7.49) breach the certified $2.56-$6.08 band; only Jul 19 ($5.85) held",
      "severity": "medium",
      "confidence": 0.95,
      "sources": [
        "Jul 14-20 daily CPC column",
        "Certified band $2.56-$6.08 from Jun 2 PPC audit"
      ],
      "disconfirmed_by": "Bid caps proven live that would pull CPC back under $6.08",
      "id": "c1-f2"
    },
    {
      "claim": "Execute Day 1 (4 campaign negatives) now \u2014 26-day conversion drought is a confirmed real traffic/funnel 
