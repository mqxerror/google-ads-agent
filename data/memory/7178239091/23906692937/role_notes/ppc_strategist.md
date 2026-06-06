# Ppc Strategist Notes

**Last updated:** 2026-06-04 11:57

**Task:** As the PPC Strategist, design the complete campaign structure:

Landing page: https://www.mercan.com/greece-golden-visa/
Brief: Greece Golden Visa — "Rich Tech Worker / Plan B" Geo Targeting Report
Th
## PPC Strategist — Campaign Blueprint: Greece GV "Plan B" (23906692937)
Read all four prior roles. CRO (LP 7/10, tracking solved via 7144337715, Plan-B framing absent from page), Competitor Intel (Plan-B lane verified open), Search Term Hunter (5 AGs / 38 KWs, Phrase-heavy, no Broad), Creative Director (5 RSAs, AG4 = precarity lead). My job is to fuse these into an executable structure — and to flag where $100/day forces hard tradeoffs.
**Day-0 honesty caveat:** This campaign has zero impressions. I will not invent a CPA/CPC baseline. Where I give numbers, they're *directional estimates* derived from the old Greece campaign's real history (~$4.41 blended CPC, $60 target CPA) and the Analytics Analyst's Tier-1 auction intel ($9–14 CPC) — explicitly labeled as such.
### ⚠️ The structural tension I have to resolve first
The team designed **5 ad groups** for a metro-concentrated, **$9–14 CPC** auction on a **$100/day** budget. Do the math: $100/day ÷ ~$11 CPC ≈ **7–9 clicks/day total**. Split across 5 ad groups, every group starves — none accumulates enough signal to learn, and Max Clicks can't allocate sensibly. **Launching all 5 AGs at $100/day is a fragmentation trap.**
My call: **launch 3 ad groups, hold 2 in reserve.** Concentrate the budget where intent and the brief's edge live. Add AG3/AG5 once daily clicks justify the spread (≈ budget bump to $150–200, or after we kill wasted spend with negatives).
### 1. Campaign settings
| Setting | Value | Rationale |
|---|---|---|
| **Type** | Search (no Display expansion) | Display Network on a fresh HNW search campaign = junk traffic |
| **Status** | **PAUSED** at creation | User enables explicitly (account rule) |
| **Start date** | On user approval (campaign stays paused until then) | |
### 2. Ad group structure — LAUNCH 3, RESERVE 2
| # | Ad Group | Status at launch | Why |
|---|---|---|---|
🚨 **AG4 landing-page dependency (flagged by CRO + Creative Director, I'm escalating it):** AG4's RSAs lead with precarity ("your status shouldn't depend on one employer"), but the LP currently reads as a calm real-estate guide with **no Plan-B block**. If AG4 runs against the current page, the emotional hook breaks on click → Quality Score and conversion both tank. **Decision gate for the Director
### 3. Match-type strategy (per Search Term Hunter — endorsed)
| Ad Group | Match mix | Note |
|---|---|---|
**No Broad match anywhere at launch.** Broad + zero conversion data = the AI-Max waste pattern. Revisit Broad only after ≥15 conversions when Max Conversions can steer it.
**Negative-keyword conflict guard (from Search Term Hunter):** "cheap" as Phrase negative would block AG3's "cheapest eu golden visa." Since AG3 is held in reserve, this is dormant at launch — but when AG3 activates, scope "cheap" as **Exact** negatives only (`[cheap]`, `[cheap visa]`), keep the keyword.
### 4. Bid adjustments — minimal at launch, observe before restricting
| Lever | Launch setting | Why |
|---|---|---|
| **Schedule** | **All hours, no modifier** | No daypart data yet. Collect first. |
**Discipline reminder:** one change-type per day, 7-day minimum before evaluating. No simultaneous bid + bidding-strategy changes.
### 5. Targeting settings
| Setting | Value |
|---|---|
| **Locations (LAUNCH)** | **San Jose `1014226` + Seattle `1027744`** — highest H1B density, slightly cooler auctions than SF/NYC, so $100/day actually buys impression share |
| **Expand next (in order)** | San Francisco `1014221` → New York `1023191` → Dallas `1026339` → Austin `1026201` |
| **Location option** | **"Presence"** (people physically IN location) — NOT "presence or interest." Avoids tourists/researchers of Greece. |
| **Language** | English |
| **Audiences (Observation)** | Custom-intent (EU residency, second passport, golden visa, relocate from US, green-card backlog); In-market (Real Estate Investment, Immigration & Relocation); Affinity (Avid Investors, Frequent Int'l Travelers) |
| **Campaign negatives at launch** | Search Term Hunter's full structural + eligibility/quiz seed list (european visa, visa europea, embajada, trabajo, work permit, sponsor(ship), green card, uscis, lottery, student/tourist visa, asylum, refugee, free, scam, salary + do-i-qualify / am-i-eligible / eligibility / quiz / calculator) — these map 1:1 to proven junk from the old campaign, LOW-impact, ap
### 6. Budget allocation — $100/day across 3 launch ad groups
Max Clicks doesn't take per-ad-group budgets (budget is campaign-level), so allocation is steered via **starting CPC bids** and which AGs are active. Target effective share:
| Ad Group | Target share | ~$/day | Logic |
|---|---|---|---|
At ~$11 blended Tier-1 CPC, that's roughly **3–4 / 3 / 2 clicks per ad group per day** — thin but viable for 2 concentrated metros. This is exactly why I cut to 3 AGs: spreading $100 across 5 would give every group <2 clicks/day and zero learnable signal.
### 7. Expected CPA range & conversion targets — *directional, not a baseline*
I'm explicit that this campaign has no data. Reasoning from known reference points:
- Old Greece campaign: ~$4.41 blended CPC, $60 target CPA (US-wide, mixed metros).
- This campaign: Tier-1 metros at **$9–14 CPC = 2–3× the old click cost**.
- If lead-conversion rate holds in the ~2–4% range (LP is 7/10, message-match risk on AG4):
- **Early CPA likely lands $250–$600** before optimization — *estimate, to be replaced by real data after 30 days.*
- **Is that acceptable?** Yes, within reason. Per business context, Portugal GV tolerates $150–200 CPA and deal value is **$20K–$100K+**. For genuinely qualified HNW Tier-1 leads, a **launch CPA up to ~$300–400 is tolerable** while learning; tighten aggressively after.
**Conversion targets (first 30 days, learning):**
- Volume goal: **accumulate signal, not hit a CPA** — aim for the first **5–10 conversions** to validate which AG converts.
- At ~8 clicks/day × 30 days ≈ 240 clicks → at 2–4% CVR ≈ **5–10 leads/month**. That's the realistic learning-phase ceiling at $100/day in Tier-1 metros.
- **Milestone gate:** at **≥15 conv/30 days**, switch Max Clicks → **Maximize Conversions (Target CPA)** and unlock Broad match testing. Until then, hold.
### Director's execution checklist (build order)
1. `budget__create_campaign_budget` — $100/day ($100,000,000 micros... confirm currency micros at execution)
2. `campaign__create_campaign` — Search, **PAUSED**, Max Clicks + $9 CPC cap, AI-Max/expansion OFF
3. Attach conversion action **7144337715** as primary
4. `ad_group__create_ad_group` ×3 (AG1, AG2, AG4)
5. `keyword__add_keywords` per AG (Search Term Hunter's match types)
6. `ad__create_responsive_search_ad` ×3 (Creative Director's RSAs — keep "€250K" in copy for LP message-match)
7. `campaign_criterion__add_location_criteria` — `1014226`, `1027744`, Presence
8. `campaign_criterion__add_negative_keyword_criteria` — launch seed list
9. Audiences + income → **Observation**
10. Leave PAUSED for GTM Specialist tracking verification → then user enables
**Two open decisions before build:**
1. **AG4 LP gate** — does CRO add the Plan-B above-fold block? (decides AG4 at 25% vs. 10–15% contained test)
2. **Confirm 3-AG launch** vs. forcing all 5 — I strongly recommend 3. If the Director insists on 5, I'd push for a $150–200 budget instead, or accept that no group learns.
I have **not** executed anything — this is a blueprint for your review. Say the word and I'll build it (PAUSED) in the order above. GTM Specialist verifies tracking next.
— PPC Strategist (Dam3oun-Google)

---

## Session Log

### 2026-06-04 11:57 — Daily review for "Greece GV — Plan B — Search — US Tier-1":

1. How did yesterda

**Task:** Daily review for "Greece GV — Plan B — Search — US Tier-1":

1. How did yesterday compare to the 7-day average? Flag any anomalies.
2. Are we on pace for monthly budget? Any pacing issues?
3. Any keyw
## Daily Review — Greece GV Plan B | 2026-06-04
**Campaign is 1 day old (created 2026-06-03). There is no 7-day average to compare against yet.** All analysis below reflects Day 1 only.
### 1. Yesterday vs. 7-Day Average
No 7-day average exists — this is the first day of recorded data.
| Metric | 2026-06-04 |
|---|---|
| Impressions | 4 |
| Clicks | 1 |
| Cost | $6.82 |
| Conversions | 0 |
| CTR | 25% |
| CPC | $6.82 |
**Observation:** $6.82 CPC is within the $9–14 Tier-1 estimate range — actually below it, which is a good early sign. CTR of 25% on 4 impressions is meaningless statistically but not alarming. Volume is as expected for Day 1 in 2 metros with a fresh campaign.
**No anomalies to flag** — this is normal cold-start behavior.
### 2. Monthly Budget Pacing
- **Daily budget:** $100/day
- **Actual Day 1 spend:** $6.82
- **Projected monthly at this rate:** ~$205/month
- **Budgeted monthly:** ~$3,100 ($100 × 31 days)
**Under-spending significantly.** This is expected — the campaign just entered the ad auction and Quality Scores haven't established yet. Google won't push impression share to a fresh campaign immediately. Give it 3–5 days before treating under-spend as a structural problem.
**No pacing action needed today.**
### 3. High-Spend / Zero-Conversion Keywords
Only one keyword fired so far:
| Keyword | Clicks | Cost | Conv |
|---|---|---|---|
**$6.82 on 1 click with 0 conversions is not a signal.** You need minimum 30–50 clicks on a keyword before drawing any conclusion. No action warranted.
### 4. Top 3 Converting Search Terms
**Zero conversions recorded.** No converting search terms to evaluate.
The search terms report shows two terms with 0 clicks each:
- `golden visa greece` — already ADDED as keyword ✅
- `golden visa portugal` — status NONE (not a keyword, correctly excluded — wrong program)
**No search term additions needed.**
### 5. Immediate Actions
**None required today.** The campaign is in its first 24 hours.
The one watch item worth noting: `golden visa portugal` appeared in the search terms report with 0 clicks, but it was triggered by `[PHRASE] golden visa greece`. Keep an eye on this — if it accumulates impressions or clicks in the next 48 hours, add `portugal` as a **Phrase negative** at the campaign level.
**Come back with a meaningful review once you have 7 days and 50+ clicks.** Until then, the only job is to let the campaign breathe and watch for junk search terms in the daily report.
— PPC Strategist
