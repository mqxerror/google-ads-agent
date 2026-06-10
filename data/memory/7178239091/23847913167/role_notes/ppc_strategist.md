# Ppc Strategist Notes

**Last updated:** 2026-06-08 11:37

**Task:** Deep performance analysis for "MapleRoots — Citizenship by Descent (US)":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown
The daily data in context only covers May 16–17. I need May 18–19 for a proper trend analysis. Let me pull fresh daily metrics.Now let me get ad group breakdown by day and keyword-level metrics for the full picture.Got all the data. Here's the complete analysis.
# Deep Performance Analysis — MapleRoots (May 16–18, 2026)
Campaign age: **3 days** | Total spend: **$440.93** | Conversions: **3**
## 1. Trend Analysis
| Date | Impr | Clicks | Cost | Conv | CTR | CPC | Impr Share | Budget Lost IS | Rank Lost IS |
|------|------|--------|------|------|-----|-----|-----------|---------------|-------------|
### Inflection Points
1. **May 16 → 17: Ramp-up** — Ads enabled evening of May 16. May 17 was first full day: 40x volume jump. CTR jumped 3.8% → 7.0% (excellent for search).
2. **May 17 evening: GTM trigger fix** — Changed event from `gf_form_submit` → `gf_submit`. All 3 conversions appeared on May 18. This was the single most impactful fix so far.
3. **May 18: Budget constraint emerged** — Impression share dropped to 32.8% with **24.1% lost to budget** (vs 0% on May 16–17). Google capped impressions because the campaign already overspent. This is new — the budget wasn't limiting before.
**Key concern:** Rank lost IS improved from 58% → 43% (good), but budget lost IS went 0% → 24% (bad). The campaign is now **budget-constrained** — you're leaving ~24% of available impressions on the table because of the $100/day budget at $1.25 CPC.
## 2. Ad Group Breakdown
| Ad Group | Clicks | Cost | Conv | CPA | CTR | % of Spend | Budget Target | Verdict |
|----------|--------|------|------|-----|-----|-----------|--------------|---------|
### Day-over-Day by Ad Group
|----|--------------|--------------|---|-------------|
**AG4 is cannibalizing the campaign.** It consumes 58.6% of spend (3.9x its 15% allocation) because the phrase-match keyword `"how to get canadian citizenship by descent"` matches thousands of search queries. Even at the reduced $0.60 bid (applied today), it will still dominate until AG1/AG2/AG3 exact-match keywords build quality score momentum.
**AG2 Grandparent has the best CPA signal** — 1 full conversion on $101 spend. With fractional attribution, it may be contributing to more paths than shown.
**AG5 Cajun is dead.** 1 impression in 3 days. The keywords (`cajun canadian citizenship`, `acadian descendants canada`) have near-zero search volume. This ad group needs a different approach or should be paused.
## 3. Keyword Efficiency Map
### Converting Keywords (winners)
| Keyword | AG | Clicks | Cost | Conv | CPA | QS |
|---------|-----|--------|------|------|-----|-----|
**Best performer:** `[canadian citizenship through grandparents]` at $20.90 CPA — this is within the $20–35 target range from the build plan. This keyword should get a bid increase.
### High-Spend Losers (0 conversions, $15+ spend)
| Keyword | AG | Clicks | Cost | Conv | QS | Action |
|---------|-----|--------|------|------|-----|--------|
**No keyword should be paused yet.** At 3 days and 3 total conversions, even the "losers" above don't have statistically significant samples. The CPA is artificially inflated because conversions only started May 18 post-GTM fix. Give it 7 more days.
### Untested Potential (0 clicks, 0 impressions)
| Keyword | AG | Why Zero |
|---------|-----|---------|
The 8 keywords added today will start collecting data over the next 48h.
## 4. Quality Score Audit
| QS | Keyword | AG | Clicks | Cost | Impact |
|-----|---------|-----|--------|------|--------|
### QS Impact Assessment
**Two keywords below QS 5 account for $28.81 in spend** (6.5% of total). Minor impact.
**The real QS problem is the two QS 5 keywords accounting for $236.65 (53.7% of total spend).** A QS of 5 is "average" — it means you're paying roughly market rate. Improving these to QS 7 would reduce CPC by ~20-30%, saving ~$50-70 over the same click volume.
**How to improve QS on the top spenders:**
- `[citizenship by descent canada]` (QS 4) — likely low expected CTR and landing page experience. The landing page is a 13,000px article with a form buried at the bottom. Google sees poor engagement signals.
- `"how to get canadian citizenship by descent"` (QS 5) — ad relevance may be diluted because this phrase-match keyword triggers for hundreds of query variants, many of which don't perfectly match the RSA headlines.
**Bottom line:** QS improvements are meaningful but secondary to fixing budget allocation and CPC. The eligibility quiz (P2 dev task) would improve landing page experience score across ALL keywords simultaneously.
## 5. Search Term Quality
From the 40 visible search terms (7-day window):
| Category | Visible Spend | % of Visible | Est. Total Spend* |
|----------|--------------|-------------|-------------------|
**Wasted spend estimate: ~$35–45 over 3 days** on non-descent generic queries.
*Google hides ~60% of search terms under privacy thresholds. The 40 visible terms represent ~$107 of $441 total spend (24%). Extrapolating the 8% waste rate suggests $35 total waste, but hidden terms may skew higher since Google tends to aggregate low-impression generic queries.*
**Post-cleanup projection:** The 13 negative keywords added today (7 new + 6 from May 17) should cut generic bleed by ~80%. Remaining waste should drop to <3% of spend going forward.
## 6. Budget Allocation Analysis
### Current vs. Target
| Ad Group | Target % | Actual % | Δ | Daily $ Target | Daily $ Actual |
|----------|---------|---------|---|---------------|---------------|
**AG4 takes 4x its allocation.** The phrase-match keyword is a volume magnet. Even with the bid reduction to $0.60 today, it will still dominate because it matches far more queries than any exact-match keyword in other ad groups.
### Impression Share Breakdown (May 18)
| Metric | Value |
|--------|-------|
| Total impression share | 32.8% |
| Lost to rank | 43.2% |
| Lost to budget | **24.1%** |
**Budget is now a real constraint.** On May 18, you lost 24.1% of impressions to budget — that's ~470 impressions you didn't show for. At the current 7.2% CTR, that's ~34 missed clicks. At $1.25 CPC, you'd need ~$42 more daily budget to capture them.
**However:** the right fix isn't more budget — it's lower CPCs. When the AG4 bid reduction ($1.29 → $0.60) takes effect, daily spend should drop from ~$175 to ~$110–130, which will naturally resolve the budget constraint.
## 7. Strategic Recommendations
### #1: Wait 5 More Days Before Any Structural Changes
**Impact: HIGH | Effort: ZERO**
The campaign is 3 days old with 3 conversions — all post-GTM fix (effectively 1 day of conversion data). Today's changes (AG4 bid → $0.60, 8 new keywords, 7 new negatives) haven't had time to impact the data yet.
**What to expect by May 25:**
- AG4's bid reduction will redistribute spend toward AG1/AG2/AG3
- New exact-match keywords will start collecting impressions
- Negatives will filter generic waste
- With ~7 days of conversion data, CPA trends become meaningful
**Do not:** change bids again, pause ad groups, switch bidding strategy, or add more keywords until May 25 at the earliest.
### #2: Boost Bid on [canadian citizenship through grandparents] → $0.85
**Impact: MEDIUM-HIGH | Effort: 2 minutes**
This is your **best-performing keyword**: $20.90 CPA, 1 full conversion, 17 clicks. At $0.65 bid it's competitive but a modest increase to $0.85 would help it win more auctions — especially since AG2 has the best CTR (7.5%) and the only full conversion.
This is the one bid change I'd make now. Everything else should wait.
### #3: Pause AG5 Cajun — Reallocate Budget to AG1/AG3
**Impact: MEDIUM | Effort: 5 minutes**
AG5 generated **1 impression in 3 days** across 8 keywords. The Cajun/Acadian citizenship angle has near-zero search volume. This ad group will never contribute at current keyword selections.
**Options:**
- **Option A (recommended):** Pause AG5 entirely. Its $3.50/day allocation is better spent increasing AG1 and AG3's share.
- **Option B:** Research broader Cajun-related terms that might have volume (e.g., "french canadian ancestry", "acadian heritage") — but these risk being informational, not commercial.
### Summary Scorecard
|--------|---------|-------------------|-----|
**The campaign's fundamentals are strong** — 7% CTR, clean search terms, massive volume (74K+ monthly searches). The three bottlenecks are:
1. **CPC too high** → AG4 bid fix applied today, expect improvement by May 21
2. **Landing page friction** → form buried at 11,363px, no quiz; P0/P1 dev fixes pending
3. **Too early for conclusions** → 3 conversions in 1 effective day isn't enough to optimize against
Check back May 25 for the next structural review.
— *PPC Strategist*

---

## Session Log

### 2026-05-19 13:51 — execute 2 and 3 a  now

**Task:** execute 2 and 3 a  now
Executing both now — bid boost on the top converter and pausing AG5.I need the criterion ID and ad group IDs. Let me fetch them via the search keywords tool.Good — got the AG5 ID (`199287105289`) and AG2 ID (`199647402914`). Now I need the criterion ID for `[canadian citizenship through grandparents]` in AG2.Found it — criterion `987672831782`, currently at $1.29 (not $0.65 as intended — same anom
## Executed ✅
| # | Action | Detail |
|---|--------|--------|
**Side finding:** That keyword's bid was also $1.29 (not the intended $0.65) — same pattern as the AG4 keyword. The other 4 AG2 keywords are also at $1.29. Looks like bids were set at $1.29 across the board during campaign creation, not $0.45–$0.75 as planned. Want me to correct the remaining AG2 keywords to their target $0.65?
— *PPC Strategist*

### 2026-05-19 13:52 — if we increase the budget to 150 what will be the impact ?

**Task:** if we increase the budget to 150 what will be the impact ?
# Budget Increase Analysis: $100 → $150/day
## Two Scenarios (because today's bid fix changes everything)
### Scenario A: $150 budget at CURRENT CPCs (~$1.25)
*If the AG4 bid reduction ($1.29 → $0.60) hasn't fully kicked in yet*
|--------|---------------|---------|--------|
**Problem:** You're still overpaying per click. More budget = more volume at inflated CPCs. You'd spend $6,200/mo instead of $3,000 target.
### Scenario B: $150 budget AFTER bid fix settles (~$0.65–0.70 CPC)
*2–3 days from now when AG4's $0.60 bid redistributes spend*
|--------|----------------|-----------------|--------|
**This is the good scenario.** At $0.65 CPC you get 50% more clicks for 50% more budget — linear scaling with no CPA inflation.
## My Recommendation: Wait 3 days, then decide
**Don't increase budget today.** Here's why:
1. **The AG4 bid fix ($1.29 → $0.60) was applied hours ago.** It needs 2–3 days to fully redistribute spend across ad groups. By May 22, your avg CPC should be $0.65–0.70, and daily spend will naturally drop from ~$175 to ~$100–110 within the current $100 budget.
2. **At post-fix CPCs, $100/day may be sufficient.** You'd get ~143–154 clicks/day at $0.65–0.70 CPC — similar volume to what you're getting now at inflated CPCs, but at half the cost per click.
3. **If $100 is still budget-constrained after the fix settles (May 22+), THEN bump to $150.** At that point you'd know the true CPC and can calculate the exact ROI of the extra $50/day.
**The $150 budget makes sense IF:**
- Post-fix CPC settles at $0.65–0.70 ✅
- You want to capture the 24% of impressions currently lost to budget ✅
- You're comfortable with ~$4,500/mo spend (vs $3,000 original target) ⚠️
**Decision point: May 22.** I'll flag it in the next review.
— *PPC Strategist*

### 2026-05-19 13:59 — put this in memory se we revised it after 3 days also we need to make our ad big

**Task:** put this in memory se we revised it after 3 days also we need to make our ad bigger we need callout and we need sitselinks , and we need structured whatever
OK — the MCP server doesn't have sitelink/callout/structured snippet tools. I'll need to create them via the Google Ads UI in Chrome. Let me save the memory first, then propose the extension copy for your approval.Now let me update MEMORY.md to reference it.Memory saved. Now here's my proposed ad extensions copy for your approval before I add them in the Google Ads UI:
## Ad Extensions Plan — MapleRoots Campaign
### Sitelinks (4)
|---|---|---|---|
| Free Consultation | No obligation. Expert guidance. | Speak with our team today. | /canadian-citizenship-by-descent |
| Grandparent Path | Canadian grandparent? You qualify | We handle the full process | /canadian-citizenship-by-descent#grandparent |
### Callouts (6, max 25 chars each)
| Callout |
|---|
| Free Consultation |
| 37+ Years Experience |
| RCIC Regulated |
| 50,000+ Clients Served |
| No Obligation |
| Bill C-3 Specialists |
### Structured Snippets
| Header | Values |
|---|---|
| **Services** | Parent Path, Grandparent Path, Great-Grandparent Path, Document Recovery, Case Assessment |
| **Types** | Citizenship by Descent, Bill C-3 Claims, Quebec Parish Records, Pre-1947 Files |
These will make the ads significantly bigger in the SERP — sitelinks alone can double your ad real estate. Callouts add trust signals. Structured snippets show the service breadth.
**Approve** and I'll add them all via the Google Ads UI in Chrome.
— *PPC Strategist*

### 2026-05-19 14:26 — yes I approve

**Task:** yes I approve
Let me check if the MCP server has extension creation tools before using the browser.No extension tools in the MCP server. I'll add them via the Google Ads UI in Chrome. Let me launch Chrome and navigate to the extensions page.Good, tools loaded. Let me navigate to the Google Ads extensions page for this campaign.Need to log in first. Let me click the Mercan Group account.Logged in. I see the acco
Now let me add the **callouts**. Clicking "Create asset".Good — the dropdown is open. Clicking "Callout".Callout form is ready. First let me change "Add to" to Campaign, then fill all 6 callouts. I need to click "Add callout text" twice to get 6 fields (currently 4 visible).Select MapleRoots and click Done.Now add 2 more callout fields (need 6 total, currently have 4), then fill all 6.Now fill all
"Service catalog" is the closest to "Services". Let me use that for the first snippet. I'll click "Service catalog"."Service catalog" is selected. Now I need to close this dropdown and fill in the values. Let me click elsewhere to close it, then fill in the values. I need to add 2 more value fields (we have 3, need 5 total). Let me start filling in the first three values.All 3 values filled. The p
Now for the second structured snippet with header "Types". Let me click "Create asset".The dropdown is open. Let me click "Structured snippet".New structured snippet form. First change "Add to" from Account to Campaign.Need to get the verbose snapshot to find the "Campaign" option.Campaign selector is open. Select MapleRoots and click Done.Campaign set to MapleRoots. Now select header "Types" and 
**MapleRoots — Citizenship by Descent (US) — Ad Extensions Complete**
| Extension Type | Count | Status |
|---|---|---|
**Structured Snippets created:**
1. **Service catalog:** Parent Path, Grandparent Path, Great-Grandparent Path, Document Recovery, Case Assessment
2. **Types:** Citizenship by Descent, Bill C-3 Claims, Quebec Parish Records, Pre-1947 Files
Note: Google Ads doesn't have a "Services" header option — I used **Service catalog** instead, which is the closest match and works well for listing the citizenship pathways.
All 12 new assets are at campaign level (not account level) and are currently "Pending Under review" — Google typically approves these within a few hours.

### 2026-05-19 14:34 — 514-282-9214

**Task:** 514-282-9214
Got it — adding a call extension with **514-282-9214** to the MapleRoots campaign now. Let me open the Google Ads UI.Tab 3 is the Assets/Associations page where I just added the other extensions. Let me navigate there and add the call extension.I can see the Assets page with all the extensions we just created. I need to click the "+" button to create a new asset and select "Call". Let me click the
- **Add to:** Campaign → MapleRoots — Citizenship by Desc...
- **Country:** Canada
- **Phone number:** 5142829214
- **Preview:** Shows "Call 5142829214"
Let me save it.Saved successfully — redirected back to the Assets page. I can also see the structured snippets now show "Eligible" status (approved!). Let me scroll down to verify the call extension appears in the list.The table is sorted by type — Call would be at the bottom. Let me scroll down to check, or filter by Call type.The page didn't scroll — it's a fixed-height table. Let me filter by "
Also great news — the structured snippets that were "Pending Under review" earlier are now showing **"Eligible"** status, meaning Google approved them.
**Call extension added successfully!** Here's the complete summary:
## Call Extension — Done ✅
| Field | Value |
|---|---|
| **Phone** | 514-282-9214 |
| **Country** | Canada |
| **Level** | Campaign (MapleRoots) |
| **Call reporting** | On |
| **Status** | Pending review (typical approval: few hours) |
This adds a "Call" button directly to your ads on mobile, and shows the phone number on desktop. Users can tap to call without visiting the landing page — great for high-intent searchers.
**Updated full extensions inventory for MapleRoots:**
| Extension Type | Count | Status |
|---|---|---|
**Total: 13 campaign-level assets** — your ads should be noticeably larger in the SERP now.
— *PPC Strategist*

### 2026-05-19 14:49 — replace all ads in this campaign to use this landing page https://www.mercan.com

**Task:** replace all ads in this campaign to use this landing page https://www.mercan.com/tr/yunanistan-altin-vize and make sure the tracking is working also

**Critical Details:** https://www.mercan.com/tr/yunanistan-altin-vize`
**Hold on — this needs confirmation before I proceed.**
The current campaign is **MapleRoots — Citizenship by Descent (US)** targeting Americans searching for Canadian citizenship by descent. The new landing page `https://www.mercan.com/tr/yunanistan-altin-vize` appears to be a **Turkish-language Greece Golden Visa page**.
This would mean:
- **Language mismatch**: English-speaking US audience → Turkish landing page
- **Product mismatch**: Canadian citizenship by descent keywords → Greece Golden Visa page
- **All 5 RSAs** (across AG1–AG4) would point to an irrelevant page
- Quality Score would likely drop to 1-2 across all keywords, CPCs would spike, and Google may disapprove ads
**Are you sure you want to do this on the MapleRoots campaign?** Or did you mean:
- A **different campaign** (e.g., a Turkey/Greece GV campaign)?
- Creating a **new campaign** for the Greek Golden Visa targeting Turkish speakers?
Please clarify and I'll execute immediately.
— *PPC Strategist*

### 2026-05-20 13:05 — Daily review for "MapleRoots — Citizenship by Descent (US)":

1. How did yesterd

**Task:** Daily review for "MapleRoots — Citizenship by Descent (US)":

1. How did yesterday compare to the 7-day average? Flag any anomalies.
2. Are we on pace for monthly budget? Any pacing issues?
3. Any key
# Daily Review — MapleRoots (May 20, 2026)
## 1. Yesterday vs. Average
**3-day average** (May 17–19, full campaign days):
|--------|--------------|------------|---|
**Positive anomaly:** CTR is on a consistent upward trend (7.0% → 7.2% → 8.9% → 12.4% today). The ad extensions are likely contributing — larger SERP footprint = better CTR.
**Negative anomaly:** Clicks/impressions declining (3,049 impr May 17 → 1,400 May 19). The AG4 bid cut ($1.29 → $0.60) is reducing AG4 volume. This is expected and intentional — but it hasn't yet been replaced by AG1/AG2/AG3 growth because those bids are still at $1.29.
## 2. Budget Pacing
| Metric | Value |
|--------|-------|
| Budget | $100/day |
| May 19 actual | **$149.56** (50% over) |
| May 17 actual | $259.99 (160% over) |
| Total spend (May 16–20) | **$640.94** |
| Monthly pace (at $150/day avg) | ~$4,500/mo |
| Monthly target | $3,000 |
**Still over-pacing**, but improving daily. May 19 was the best day so far vs. budget ($150 vs. $260 May 17). The AG4 bid cut is working — slowly. AG1/AG2/AG3 still at $1.29 is the remaining issue.
## 3. High-Spend, Zero-Conversion Keywords
| Keyword | Clicks | Est. Cost | Conv |
|---------|--------|-----------|------|
**No action yet** — campaign is 5 days old with 6 total conversions. Statistically meaningless. Flag for review at May 26 if still zero.
## 4. Top 3 Converting Search Terms
| Search Term | Conv | Added as Keyword? |
|-------------|------|-------------------|
**Action needed:** Add `[applying for canadian citizenship by descent]` as exact match to AG1.
## 5. Immediate Actions
| Priority | Action | Impact |
|----------|--------|--------|
**Biggest lever remaining: bid correction on AG1/AG2/AG3.** The AG4 fix was step one. Step two is pulling the other 3 ad groups down from $1.29. Say the word and I'll execute.
— *PPC Strategist*

### 2026-05-20 13:07 — is it safe to switch the bid today while we said two days ago we keep it ?

**Task:** is it safe to switch the bid today while we said two days ago we keep it ?
Good question — and worth being precise about.
**The "3 days" rule was specifically for the budget decision** ($100 → $150). That review date is still May 22. We haven't touched that.
The AG1/AG2/AG3 bid correction is a separate action — and it's not a strategic change, it's **fixing a misconfiguration**. Those bids were supposed to be $0.45–$0.75 at launch but were set at $1.29 incorrectly. Every day we wait costs us inflated CPCs on those ad groups.
**That said:** the AG4 bid change was only applied yesterday (May 19). Stacking another bid change today, 24 hours later, means:
- Google has two overlapping adjustments to process simultaneously
- You can't isolate which change caused what in the data
- Learning signals get muddier
**My recommendation: wait one more day.** Run the AG1/AG2/AG3 bid correction tomorrow (May 21). That gives the AG4 change 48 hours to settle, keeps the May 22 budget decision on schedule, and produces cleaner data. One extra day of $1.29 bids on those 3 ad groups costs roughly $15–20 in excess CPC — worth it for cleaner reads.
**Tomorrow May 21:** Fix AG1/AG2/AG3 bids → $0.45–$0.75
**May 22:** Budget review ($100 → $150 decision)
— *PPC Strategist*

### 2026-05-21 12:08 — Add [applying for canadian citizenship by descent] exact, AG1, $0.65	, 
regardin

**Task:** Add [applying for canadian citizenship by descent] exact, AG1, $0.65	, 
regarding changing bids for the ag1 2 3 what if they collapse like the ag4 ?
Let me add that keyword now.MCP connection issue — I'll retry.MCP server is down. Let me try via the Python SDK directly.**Keyword added to AG1:**
- `[applying for canadian citizenship by descent]` — Exact match, $0.65 bid, criterion ID `651247193404`
Now to your real question:
## Will AG1/AG2/AG3 Collapse Like AG4 Did?
**Short answer: No, and here's why they're fundamentally different.**
AG4 "collapsed" because its volume came from a **phrase-match keyword** (`"how to get canadian citizenship by descent"`) that matched thousands of broad queries. When we cut its bid from $1.29 → $0.60, it lost most of those wide-net auctions. That's not collapse — that's the intended effect. AG4 was a **volume hog eating 58% of budget** on loosely-matched traffic.
AG1/AG2/AG3 are **exact-match dominant**. Their keywords match precisely what users type. Lowering bids on exact match doesn't eliminate volume — it just lowers your cost per click. Google still shows your ad; you just pay less.
**The risk matrix:**
|--------|-----------------|----------------------|
| Match type | Phrase (broad reach) | Mostly Exact |
| Why it had volume | Matched thousands of variants | Matched specific high-volume terms |
| What happens at lower bid | Loses broad queries to competitors | Still wins auctions, just cheaper |
**However — one legitimate risk:** If we cut **too aggressively** (e.g., $0.45 on a keyword where competitors bid $0.80), we'd drop off page 1 and lose impressions. The keyword planner data shows CPCs in this space at $0.17–$0.83, so $0.45–$0.75 is competitive.
**My recommendation: stagger the cuts instead of all at once.**
| Day | Action | Why |
|-----|--------|-----|
This way if any ad group shows an impression drop, we catch it in 24h and adjust — instead of discovering all three tanked simultaneously.
**Want me to start with AG1 → $0.75 today?**
— *PPC Strategist*

### 2026-06-02 12:22 — Daily review for "MapleRoots — Citizenship by Descent (US)":

1. How did yesterd

**Task:** Daily review for "MapleRoots — Citizenship by Descent (US)":

1. How did yesterday compare to the 7-day average? Flag any anomalies.
2. Are we on pace for monthly budget? Any pacing issues?
3. Any key
# Daily Review — MapleRoots (June 2, 2026)
**Note: Today marks the 7-day post-LP switch review date flagged on May 26.**
## 1. Yesterday vs. 7-Day Average
|--------|-------------------|--------------------------|---------|
**Anomaly:** May 30-31 were outlier low days (514 and 416 impressions, $74-64 spend) — likely weekend drop. June 1 is the proper return-to-baseline Monday. No alarm.
**June 1 is a good day** — 3 conversions at ~$46.46 CPA, above the 7-day average by 61%.
## 2. Budget Pacing
| Metric | Value |
|--------|-------|
| June 1 spend | $139.38 (39% over $100/day budget) |
| 14-day avg daily spend | **$127/day** (27% over) |
| June monthly pace | ~$4,170 vs $3,000 target |
Still running over budget. CPC is stuck at $1.05-1.14 — the AG2 bid fixes should have settled by now. The $100/day budget needs to either be accepted as $3,800-4,200/month reality, or the budget decision ($100→$150) should be formalized. **See action items below.**
## 3. High-Spend, Zero-Conversion Keywords
| Keyword | Clicks | Est. Spend | Conv | Action |
|---------|--------|-----------|------|--------|
`"canadian citizenship through parents"` now has 7 conversions on 726 clicks (0.96% CVR) — no longer a zero-conversion concern, but still the lowest CVR in the campaign. Monitor.
## 4. Top 3 Converting Search Terms (last 7 days)
| Search Term | Clicks | Cost | Conv | Added? |
|------------|--------|------|------|--------|
**Action needed:** Add `[my grandfather was born in canada can i get citizenship]` as exact match to AG2 at $0.65 bid. This converted once on 6 clicks — exactly the grandparent-intent traffic AG2 is designed to capture.
## 5. Immediate Actions
| Priority | Action | Effort |
|----------|--------|--------|
**The 7-day LP switch verdict:** 13 conversions in 7 days post-switch (1.86/day) vs 14 in the 7 days pre-switch (2.0/day). **No clear CVR lift yet.** This is likely because the P0 dev fixes (button text, field reduction) haven't shipped — the new LP is above-fold but still has 8 fields and a "Submit" button. Confirm with dev team whether P0 fixes are live.
— *PPC Strategist*

### 2026-06-02 12:45 — do the today task also what about switching the strategy from manual to optimize

**Task:** do the today task also what about switching the strategy from manual to optimized conversion ? also I have a double budget should we upgrade to 260 per day?
Two strategic questions and an execution task. Let me answer the strategy/budget questions first because they determine whether today's bid changes even make sense — then execute.
## 1. Switch Manual → Maximize Conversions? Not today. Here's the sequence.
You now have the volume for it — **27 conv in 14 days ≈ 58/month**, comfortably above the 15-conv/30-day floor. So automated bidding is on the table soon. But switching *today* is the wrong move for three concrete reasons:
1. **It would cancel out two of the three TODAY changes.** Items #2 (raise AG3 bids) and #3 (lower AG2 bids) are *manual* bid moves. The moment you switch to Maximize Conversions, Google sets every bid automatically and those manual adjustments become meaningless. You'd be paying for work the algorithm immediately overrides.
2. **You'd train the algorithm on a polluted signal.** The `through parents` leak (726 clicks, 0.96% CVR) is still feeding bad conversion data. Hand bidding to Google *before* fixing it and it learns to chase the wrong intent. Clean the structure first, then automate on a clean signal.
3. **Learning-phase instability.** Per our guidelines, switching to automated bidding triggers 7–14 days of volatility. Stacking that on top of today's keyword surgery means you can't tell which change caused what.
**Correct order:** fix structure today (Manual) → let it run 7–10 days for a clean signal → *then* switch to Maximize Conversions. I'll flag the switch date once the leak fix settles.
## 2. Double the budget to $260/day? No — that's scaling the leak.
Right now ~45% of AG1's clicks pour into a 0.96%-CVR keyword. Doubling budget **before** fixing that just buys 2× more of the same inefficiency — you'd push toward ~$7,800/mo at today's $66 CPA instead of the ~$52 CPA we can hit post-fix.
The right way to use that doubled budget:
- **Today:** keep $100 (functionally ~$127 with Google's over-delivery).
- **After the leak fix proves out (~7 days):** step to **$150**, not $260. Measure CPA.
- **If CPA holds at ~$50 and impression-share-lost-to-budget is real:** then step toward $200 → $260.
Scaling in steps keeps CPA controlled. Doubling in one jump into an unfixed funnel is how you burn the extra budget. You have the money — let's earn the right to spend it by fixing the funnel first.
Now executing the **TODAY task**. I need the criterion IDs (not in my context) to make these changes. Loading the tools and pulling them.Pulling the criterion IDs and current bids for the keywords I need to touch.The search tool forces a page_size param the API rejects. Let me use the keyword search tool instead.Got the IDs — and one important surprise that changes part of the plan:
**AG3's two winning keywords are already at $1.29, not the ~$0.65 we assumed.** They were never corrected from the launch bid anomaly. So #2 isn't "fix an underbid" — it's "lean harder into the winner." That's still valid (AG3 converts at $33 CPA, half the blended), so I'll nudge them up modestly to win any rank-lost impression share, but flag that AG3's real ceiling is likely search volume — the 
Executing the full TODAY block now under Manual CPC (since we're NOT switching strategy today).Now the last item — add the converting grandparent term as exact to AG2. (Note: a phrase version already exists at $0.65; the exact version gives that precise converting query its own QS and bid control.)Done. All three TODAY items executed under Manual CPC.
## TODAY task — executed ✅
| # | Action | Detail | Status |
|---|--------|--------|--------|
**Two things to know:**
- **AG3 was already bidding $1.29, not $0.65** — the launch anomaly was never fixed there. So I nudged it modestly rather than the planned "+$0.15–0.20 from a low base." AG3's real growth ceiling is probably search volume on bill-c-3 terms, not bid — the higher-leverage AG3 move next sprint is **broadening its keyword set** (more great-grandparent / bill-c-3 spelling variants), which Search Term H
- The exact `through parents` keyword **starts fresh on Quality Score**. Expect a few days of QS rebuild — that's the cost of stopping the leak, and it's worth it.
## Why I did NOT switch bidding or double the budget today
Both are right *eventually*, wrong *now* — and doing them today would have undercut the work above:
- **Maximize Conversions today** would have made items #2 and #3 (the manual bid moves) instantly meaningless, and trained Google's algorithm on the still-dirty signal. → Revisit in **~7–10 days** once the leak fix produces a clean conversion set.
- **$260/day today** would just buy 2× of an unfixed funnel at $66 CPA. → Step to **$150** after the fix proves out, measure, then climb toward $260 if CPA holds ~$50 and you're losing impressions to budget.
**Per guidelines: this was one structural-cleanup block. Hold all other changes for separate days** — the AG1 AVERAGE→GOOD copy trim is next, then the LP P0 fixes. I'll review the leak-fix impact in 7 days and flag the strategy-switch + budget-step decision then.
— *PPC Strategist*

### 2026-06-02 13:02 — I challenge you the daily budget is 130 use a day not a 100

**Task:** I challenge you the daily budget is 130 use a day not a 100
You're right to push me on this — I've been quoting $100 from the build notes without checking the live setting. Let me pull the actual budget from the API.The default page_size param is breaking this tool. Let me try the stream variant.Confirmed — you're right, and I was wrong. Pulled it straight from the API.
**Budget ID `15581336301` = `amount_micros: 130000000` = $130.00/day.** Not $100.
I've been quoting "$100/day" from the May 15 build notes for two weeks without re-checking the live setting. That error poisoned every pacing read I gave you. Here's the corrected picture:
## Corrected Budget Pacing
|--------|--------------------|-----------------------|
**The whole "overspend problem" was an artifact of my stale number.** The campaign isn't over-pacing at all — it's running right at its $130/day budget, actually a hair under. There was never a pacing issue to "formalize" or "accept." I was solving a problem that didn't exist.
## What this changes about the boost plan
This actually *strengthens* the case for the staged scale, because the starting line is higher than I framed it:
| Date | Move | Trigger |
|------|------|---------|
So the stakeholders' "boost" message gets a cleaner answer: we're already at $130, and we scale to $170 → $260 over three weeks gated on CPA — not "we're over budget, let's be careful."
I'm logging this correction to memory so $130 is the anchor going forward and the $100 number stops resurfacing.Memory corrected. The $130/day budget is now pinned with the budget ID and the explicit note that $127/day actual is on-budget, not an overspend — so this won't resurface in future reports.
Bottom line: good catch. The campaign is pacing correctly at $130/day, the leak fix is settling, and the cleaner staged-scale path is $130 → $170 (Jun 9) → $260 over three weeks, gated on CPA ≤ $55.
— *PPC Strategist*

### 2026-06-02 13:10 — updated role and memory about the plan and the waiting plan

**Plan + waiting plan saved to `scaling_waiting_plan.md`** and pinned. Summary:

- **Waiting window → Jun 9.** Leak fix (`[canadian citizenship through parents]` EXACT @ $0.65, neg `"parent was born in canada"` / `"i was born in canada"`), AG3 raise ($1.29→$1.45), AG2 cut ($0.45), and AG2 converter add all shipped 2026-06-02. Per guidelines (1 change-type/day, 7 clean days) the earliest honest review is Jun 9. `[through parents]` EXACT also rebuilds QS — don't stack changes meanwhile.
- **Staged scale (the boost):** budget already $130/day (ID 15581336301). Gated on CPA ≤ $55: $130 → $170 (Jun 9) → $220 (Jun 16) → $260 (Jun 23+).
- **Bidding switch deferred:** Manual → Maximize Conversions qualified (58 conv/mo) but held ~7–10 days for a clean signal; flag switch date at Jun 9 review.
- **Jun 9 checklist:** confirm blended CPA $66→~$52, QS rebuild on the tightened keyword, AG3 impr-share gain, AG2 CPA after cut → if CPA ≤ $55, step to $170 and flag the bidding switch.
- **Still pending (separate days):** AG1 AVERAGE→GOOD copy trim, dev P0 LP fixes (button text, remove field, 5 fields), clean `/lp/`-only Clarity pull.

— *PPC Strategist*

### 2026-06-04 12:21 — Daily review for "MapleRoots — Citizenship by Descent (US)":

1. How did yesterd

**Task:** Daily review for "MapleRoots — Citizenship by Descent (US)":

1. How did yesterday compare to the 7-day average? Flag any anomalies.
2. Are we on pace for monthly budget? Any pacing issues?
3. Any key
# Daily Review — MapleRoots (June 4, 2026)
*Waiting window active: no structural changes until Jun 9.*
## 1. Yesterday (Jun 3) vs. 7-Day Average
|--------|-------|--------------------------|---|
**This is the leak fix working as intended, not an alarm.** The `"canadian citizenship through parents"` phrase match was the campaign's biggest volume driver. Removing it on June 2 cut volume immediately — June 3 was the first full post-fix day. Low impressions + low cost + still 1 conversion = the funnel is running leaner, not broken. Expected pattern for 2–4 more days while Google redistributes
## 2. Budget Pacing
| Metric | Value |
|--------|-------|
| Jun 3 spend | $33.25 — **74% under $130 budget** |
| Jun 1–3 avg | ~$80/day (well under $130) |
| Monthly pace at current rate | ~$2,400 vs $3,900 budget |
**Underperforming budget right now, not overspending.** The volume drop from the leak fix is the cause. This will self-correct as Google re-learns the keyword mix and AG1's exact-match terms build impression share. Don't touch budget until Jun 9 review.
## 3. High-Spend Zero-Conversion Keywords
Both flagged previously — bids already cut to $0.45 on Jun 2. In the waiting window:
| Keyword | Clicks | Spend | Conv | Status |
|---------|--------|-------|------|--------|
No new action. Watching.
## 4. Top Converting Search Terms (last 7 days)
| Search Term | Clicks | Cost | Conv | Added? |
|------------|--------|------|------|--------|
Only 1 converting search term visible in the last 7 days — very light. This is consistent with the post-fix volume drop. The `canada bill c3 application` query is legitimate Bill C-3 intent → flag to add to AG3 at $0.65 when the Jun 9 review opens.
## 5. Immediate Actions
| Priority | Action | When |
|----------|--------|------|
**Bottom line:** The campaign is intentionally quieter this week — that's the leak fix doing its job. Don't mistake lower volume for a problem. Jun 9 is the first honest read on whether CPA improved toward the $55 target. Hold steady.
— *PPC Strategist*

### 2026-06-07 18:39 — we have a 170 budget and we are spending 30 we need a whole year for the full bu

**Task:** we have a 170 budget and we are spending 30 we need a whole year for the full budget spend which is 220
You're right, and this flips the whole plan. The problem isn't budget — it's that we **strangled our own reach** and the budget number is now fiction.
## The real picture
We're not "settling" — we're in a **volume death-spiral**. Impressions have fallen every single day since the leak fix:
| Date | Impr | Clicks | Spend |
|------|------|--------|-------|
That's **-87% spend in 6 days**. At ~$18/day against a $170 budget we're using **~11% of it**. You're spot-on: raising the budget to $220 does *nothing* — you can't spend $170 when reach has collapsed to $18.
## What actually happened
The Jun 2 leak fix **over-corrected**. Converting `"canadian citizenship through parents"` PHRASE → EXACT didn't just plug the leak — it deleted 727 clicks of reach. EXACT only matches that one exact string. And the campaign-level negatives we added (`parent was born in canada`, `i was born in canada`) were *already* enough to block the DIY intent. We threw out the volume with the bathwater.
**The good news that earns us the right to act now:** CPA on the post-leak window (Jun 2–7) is **$48 — under the $55 gate**. The efficiency goal the waiting window was meant to confirm is *already met*. Waiting until Jun 9 while impressions bleed to ~100/day just starves it further.
## The fix is REACH, not budget
Budget stays put — it's not the lever. One change-type today: **restore match coverage on the clusters that actually convert.**
| # | Action | Why |
|---|--------|-----|
I'd **leave through-parents as EXACT** — it converted at only 0.96% ($66+ CPA), above the gate. We restore volume through the *winning* Bill C-3 + ancestry clusters, not the loser.
This is a volume-rescue, not a scale-up — so it overrides the "hold till Jun 9" window. The window's job was to read CPA; we've read it ($48 ✅). Sitting on our hands two more days just bleeds reach.
**Want me to execute items 1–3 now?** Budget stays at current until reach recovers — *then* we talk scaling.
— *PPC Strategist*

### 2026-06-07 18:48 — remove the cut and the strategy from now on we clean search terms daily and keep

**Task:** remove the cut and the strategy from now on we clean search terms daily and keep traffic coming increase the budget to 150 today the June 19 we increase it to 250
Clear directive — executing. Three moves: restore reach, bump budget to $150 today, and schedule the $250 step for Jun 19. Plus the new standing policy (daily search-term cleaning, keep the taps open). Let me load the write tools.Executing all moves in parallel.Done — all three writes succeeded. Now updating memory so the new plan governs future sessions (budget $150, cut removed, daily-clean stra
## Executed ✅
| # | Action | Detail | Status |
|---|--------|--------|--------|
**New standing strategy pinned:** keep traffic flowing, clean search terms **daily** with negatives (reactive) instead of pre-emptively cutting match coverage. The waiting-window hold is lifted.
## Two things you should know
1. **I kept the 2 DIY negatives** (`parent was born in canada`, `i was born in canada`) as guardrails. They block the pure do-it-yourself parent-path searcher while the restored phrase match recaptures the broader volume. Since we now clean daily, I can pull them anytime — but they let us "remove the cut" without fully reopening the $66-CPA leak. Say the word if you want them gone too.
2. **`through parents` is the one to watch.** It was the campaign's volume engine *and* its leak (0.96% CVR, $66 CPA). With daily cleaning that's manageable — but it's the first place I'll look in tomorrow's search-term sweep. The 3 AG3 Bill C-3 adds are pure upside (proven converters, low competition), so the reach recovery should skew toward the *good* volume.
**Expectation setting:** reach won't snap back to 120 clicks/day overnight — the restored phrase keyword starts fresh on Quality Score and needs ~48h to rebuild auction presence. I'd expect clicks to climb from 15 → 40–60 over the next 2–3 days, then toward 80–100 by the weekend. That's what gives the $150 budget (and the Jun-19 $250 step) something real to spend on.
**Heads-up for Jun 19:** before the $250 step fires, I'd want one look at CPA on the rebuilt volume — if reach recovers but CPA drifts above ~$55, doubling the budget would scale inefficiency. I'll flag it that morning either way; your call stands.
— *PPC Strategist*

### 2026-06-08 11:37 — what is the best strategy to quickly get the traffic quickly and keep daily sear

**Task:** what is the best strategy to quickly get the traffic quickly and keep daily search term cleanup does the maximize click works ?
Short answer: **Yes, Maximize Clicks works for exactly this goal — fast traffic + full-budget spend — and it pairs well with daily search-term cleanup. But don't flip it today, and never run it without a max-CPC cap.** Here's the honest breakdown.
## Does Maximize Clicks fit our situation?
**Yes — it's literally the tool for "get traffic fast and spend the budget."** It chases the most clicks your $150 can buy and will fill the budget aggressively. And your new standing policy (daily negatives) is the *perfect* guardrail for it: Max Clicks casts a wider net → daily cleanup prunes the junk. They're complementary, not in tension.
But two hard caveats from this account's own history:
1. **Always set a max-CPC cap.** Per our business context, *"Google can spend up to 2× daily budget with Maximize Clicks (TARGET_SPEND)."* Uncapped, it can also chase $1.80–$2.50 clicks. Our planner range is $0.17–$0.83 and we already pay $1.05–$1.18. **Cap it at ~$1.20** so it buys volume without runaway CPC.
2. **It optimizes for clicks, not conversions** — fine right now because intent is the cleanest in campaign history, but it means CPA discipline rests entirely on the daily cleanup + bid cap.
## Why NOT switch it *today*
The reach collapse wasn't a bidding problem — it was a **coverage** problem (we deleted the `through parents` phrase match Jun 2). We restored that keyword last night, and **it's mid-QS-rebuild — Google needs ~48h before it wins auctions at full strength.** Switching bid strategy on top of a keyword that's still rebuilding QS:
- stacks learning-phase instability on an unsettled signal (can't read what caused what),
- won't manufacture reach the fresh-QS keyword can't yet support today anyway.
Max Clicks accelerates spend into *available* auctions — but our available auctions are throttled by QS for ~24–48h more. So flipping today buys little and muddies the read.
## What I'd actually do — fastest clean path
**Today (same-type manual move, low risk, immediate):** bump the reach keywords to win more of the auctions that *are* live right now —
- `[PHRASE] canadian citizenship through parents` $0.65 → **$0.90**
- the 3 AG3 Bill C-3 adds $0.65 → **$0.85**
That pushes volume immediately while QS rebuilds, no strategy-change instability.
**Jun 9–10 (one clean change):** if reach is still under-spending the $150 budget after the restored keyword settles, **switch to Maximize Clicks with a $1.20 max-CPC cap.** By then the QS is rebuilt, the signal is clean, and Max Clicks has real auctions to fill — that's when it pays off, and it carries us straight into the Jun-19 $250 step with budget the strategy will actually consume.
**Daily cleanup stays on regardless of bid strategy** — it's independent of Manual vs Max Clicks.
Net: **Max Clicks is the right "spend it fast" engine — but it's a Jun 9–10 move, capped at $1.20, after the restored keyword finishes its QS rebuild.** Today, a quick bid bump on the reach keywords gets traffic climbing without the learning-phase hit.
Want me to apply the bid bumps now ($0.90 / $0.85), and pencil the Maximize Clicks + $1.20 cap switch for Jun 9?
— *PPC Strategist*
