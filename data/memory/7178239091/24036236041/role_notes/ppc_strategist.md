# Ppc Strategist Notes

**Last updated:** 2026-07-23 11:05

**Task:** Write the campaign performance report for Panama QIP — US — Search — v2 (ID 24036236041) strictly from the in-context data. Cover: (1) day-by-day 2026-07-14→16 (73→748→634 impr; 8→49→38 clicks; $33.37

**Critical Details:** https://www.mercan.com/lp/panama-qualified-investor-program`
## Panama QIP — US — Search — v2 | Performance Report | Jul 14–16, 2026
**Day-by-Day Trend**
| Date | Impr | Clicks | Cost | CTR | CPC |
|------|------|--------|------|-----|-----|
CPC rose **+40% in 3 days**; CTR fell **5pp**. Maximize Conversions is bidding up for volume with zero conversion signal to anchor it. **0 conversions on 95 clicks.**
**Spend Allocation — concentration risk**
- Property Investors: $265.75 / 58 clicks / 0 conv → **56% of budget**, driven by generic searchers ("buy property in panama," "homes for sale in panama") — low QIP intent
- Residency Core (Converters): $120.05 / 23 clicks / 0 conv
- RBI Category: $73.46 / 11 clicks / 0 conv
- Investor Program (High Intent): $12.39 / 3 clicks / 0 conv — highest-intent group, lowest share
**Bidding Phase**
Campaign is ~2 days old with 0 conversions. Per phase rules: **no bid-strategy or budget changes.** Flag only: the algorithm has no signal, so it defaults to click volume — Property Investors wins spend by default.
**Critical Landing Page Flag (verified this session)**
Live fetch of `https://www.mercan.com/lp/panama-qualified-investor-program` returned HTTP 200 but **no form signal and no tracking token detected**. If no form is visible or the conversion tag isn't firing, 0 conversions is guaranteed regardless of traffic quality. **Verify form presence and conversion firing before diagnosing this as a traffic or bidding problem.**

---

## Session Log

### 2026-07-16 12:58 — Orchestrated finding

{
  "summary": "$471.66 spent / 95 clicks / 0 conversions in 3 days; primary risk is a landing-page tracking gap (no form or tag detected on live fetch) \u2014 confirm conversion fires before any structural change.",
  "findings": [
    {
      "claim": "Landing page returned no form signal and no tracking token on live fetch \u2014 0 conversions likely reflects a page or tracking gap, not traffic quality",
      "severity": "high",
      "confidence": 0.85,
      "sources": [
        "LIVE LANDING PAGE STATE: form signal: none detected, tracking token: none detected"
      ],
      "disconfirmed_by": "A live form-submit test that confirms the GV Lead conversion fires in GTM confirms tracking is intact",
      "id": "c1-f0"
    },
    {
      "claim": "Property Investors ad group is consuming 56% of spend ($265.75) on generic real-estate intent, not QIP investor intent",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "Ad group data: 58 clicks / $265.75 / 0 conv",
        "Search terms: 'panama real estate', 'homes for sale in panama', 'panama real estate for sale'"
      ],
      "disconfirmed_by": "If these terms produce conversions at learning-phase completion, spend share is justified",
      "id": "c1-f1"
    },
    {
      "claim": "CPC rising +40% ($4.17\u2192$5.84) with CTR falling 5pp signals Maximize Conversions bidding for volume without conversion data",
      "severity": "medium",
      "confidence": 0.85,
      "sources": [
        "Day-by-day metrics Jul 14\u201316"
      ],
      "disconfirmed_by": "CPC stabilizes once the algorithm accumulates enough impression/click signal in the learning phase",
      "id": "c1-f2"
    },
    {
      "claim": "No bid-strategy or budget changes should be made \u2014 campaign is in learning phase, <7 days old, 0 conversions",
      "severity": "low",
      "confidence": 0.95,
      "sources": [
        "Phase rules: Maximize Conversions requires 15+ conv/month; campaign age ~2 days"

### 2026-07-16 17:52 — do you need to tell a Panama QIP lead apart from a Panama Friendly Nations lead 

**Task:** do you need to tell a Panama QIP lead apart from a Panama Friendly Nations lead in your bidding? No
it is accunt defualt i tried to switch campaign goal and it showed only submit ;ead forms nothing sp
## Your instinct is 90% right — one correction, and one missing Google feature that explains what you saw in that Goals screen.
### Locked in: one Panama action for everything
You answered No — you don't need QIP vs Friendly Nations separated in bidding. So the design is final: **Panama QIV Lead serves every Panama campaign, forever.** And yes, when a future Panama campaign uses a different landing page, you extend the *same* action rather than creating a new one. One caveat on the "add an extra URL" part: that works exactly as you describe **if** the action is URL-rule
### The one thing you've got slightly wrong: attribution and goals are two different machines
> "google will always attribute the click id to the right ad anyway"
True — but that solves a different problem than the one account-default goals creates. Two separate mechanisms:
| Machine | Question it answers | Your status |
|---|---|---|
| **Attribution (GCLID)** | *Which campaign gets credit* for a conversion | ✅ Working — always routes to the right ad, you're correct |
| **Goal settings** | *Which conversion events count at all* for this campaign's bidding | ⚠️ Account-default = **every** primary lead action in the account counts |
Attribution never misroutes credit. But with account-default goals, if someone clicks your Panama ad, wanders to the Greece page, and submits *that* form — Greece GV Lead fires, attribution correctly credits your Panama campaign (it owned the click), and Maximize Conversions learns "this Panama search term converts." Attribution did its job perfectly and you still got polluted data. Attribution de
In practice this leak is small — cross-page wandering to another program's form is rare. The bigger pollutant is that **`[DEPRECATED] Greece GV Turkey CP - DO NOT USE` is still ENABLED and primary**, sitting inside the same "Submit lead form" folder every account-default campaign optimizes toward.
### Why the Goals screen "showed only Submit lead forms, nothing specific"
That's not a bug and you didn't miss a menu — it's how Google designed it. The campaign-goals picker operates at the **category folder** level, never the individual action level. Picking "Submit lead form" there would still mean *all six* primary lead actions feed this campaign, so it changes nothing.
The feature you were looking for exists, it's just hidden under a different name: a **custom goal**. In Tools → Conversions → **Goals** (left sidebar) → Create custom goal → you build a goal containing *only* Panama QIV Lead. That custom goal then appears in the campaign's Goals settings as a selectable option. That's the only mechanism in Google Ads that scopes a campaign to a specific action.
### My recommendation
**Do (needs your approval, account-level):** flip `[DEPRECATED] Greece GV Turkey CP` to **secondary**. This cleans the default goal folder for every campaign in the account, touches no campaign's learning phase, and per the Director's earlier note should happen regardless of anything else.
**Do tomorrow, not today (campaign-level):** create the custom goal "Panama QIV Lead" and assign it to this campaign. Reasons for yes: Maximize Conversions is sitting on n=1 — it is maximally sensitive to a single junk signal right now, and a goal change at day 4 is the cheapest it will ever be (at day 30 it costs real learning). Reason for *tomorrow*: the negatives were today's change, and the on
**Don't:** create any new conversion action, ever, for a Panama campaign pointing at a page the existing action can cover. Extend the URL rules (or the GTM trigger) instead.
Nothing here executes without your word — the deprecated-action flip and the custom goal are both changes I'd want you to explicitly approve. Say "do the custom goal tomorrow" and it goes on the log for Jul 17.
*— PPC Strategist*

### 2026-07-21 13:28 — FRESH LIVE PULL + WEEK-1 CPA VERDICT for campaign 24036236041 (customer 71782390

**Task:** FRESH LIVE PULL + WEEK-1 CPA VERDICT for campaign 24036236041 (customer 7178239091) ONLY. Use search_execute_query (NOT google_ads_search_google_ads — it is broken with PAGE_SIZE_NOT_SUPPORTED per GTM
Running the three GAQL reads now — daily, lifetime, and per-ad-group — using `search_execute_query` as specified.Running all three GAQL reads in parallel now.All three reads returned clean. Here's the full week-1 analysis.
## Panama QIP US v2 — Week-1 Verdict | LIVE pull this turn
**LIVE** = fetched this turn. **Cached** = prior session (noted where used).
### Day-by-Day (LIVE)
| Date | Impr | Clicks | Cost | Conv | CPC | Imp Share | Lost-Rank | Lost-Budget |
|---|---|---|---|---|---|---|---|---|
*Jul 21 is a partial day — 13 clicks at time of pull.*
**Second conversion confirmed LIVE: landed Jul 19** (Cached context showed 2 total on Property Investors — now pinned to date).
### Lifetime (LIVE)
- Spend: **$1,499.65** | Clicks: **265** | Conversions: **2**
- **Lifetime CPA: $749.82** — **UNDER the $800 bar** (directional read only; n=2, pinned-fact caveat applies)
### Ad Group Breakdown (LIVE, Jul 14–21)
| Ad Group | Clicks | Cost | Conv | CPA | % Spend |
|---|---|---|---|---|---|
**(a) Week-1 CPA verdict:** $749.82 — directionally **UNDER $800**, driven by 2 conversions both from Property Investors / `[PHRASE] buy property in panama`. Campaign is 7 days old, n=2: this is a directional signal, not a baseline.
**(b) Latitude position gap — the rank bridge:** Latitude sits at avg pos 1.9 vs our 2.8. The cause is explicit in the live data: **47.2% of eligible impressions lost to Ad Rank** (lifetime average). Budget loss (24.5%) is secondary. Ad Rank = bid × QS × context. Our QS profile is weak: `residency visa panama` QS:1, `panama investment visa` QS:1, `panama golden visa` QS:1, `buy property in panama`
**(c) Ranked next moves — all sequenced as "on Jul 23 pull, if X then Y":**
1. **[HIGH] QS repair on low-scoring keywords.** On Jul 23, if rank-lost IS is still ≥45%: rewrite RSA headlines for `residency visa panama`, `panama investment visa`, `panama golden visa` to match keyword intent exactly. Move them to a dedicated tight ad group if current copy doesn't contain those exact phrases. Expected impact: +5–10pp impression share, position closes toward 2.2–2.5 range vs La
2. **[HIGH] Add sitelinks to close the Latitude visibility gap.** Spy report shows Latitude at 1.9 with heavy sitelinks; our 51 ads show none in the spy data. Sitelinks boost Ad Rank via expected CTR. On Jul 23: add 4 sitelinks (e.g., "How the $300K Program Works", "30-Day Processing Timeline", "Book a Free Consultation", "Panama vs Greece — Compare Programs"). This costs nothing in bid terms and 
3. **[MEDIUM] Budget decision on Jul 23.** Jul 17 lost 64.9% of impressions to budget; Jul 16 lost 46.1%. If Jul 23 search-terms pull shows clean traffic and CPA holds directionally under $800: raise daily budget from ~$220 to $300–350. Don't execute before the clean read — the negatives and goal change landed Jul 16, and the first honest read is Jul 23.
4. **[MEDIUM] Property Investors keyword strategy review.** Both conversions came here, but it's 58% of spend on a structurally residential keyword set. On Jul 23: pull search terms for the Jul 16–23 post-negative window. If listing-browse queries still dominate (≥60% of terms): move `[PHRASE] buy property in panama` to exact match only and replace with `[EXACT] buy property panama investment` and
5. **[LOW] Activate `[EXACT] panama qualified investor program` support.** 0 clicks in 7 days on this keyword — it likely exists in the Investor Program (High Intent) group ($12.39, 3 clicks) but the exact query gets no impressions, suggesting QS:2 is killing it in auction. On Jul 23: check impression share for this ad group specifically. If rank-lost >80%: dedicated ad copy containing the exact p
**(d) What the spy data changes about copy strategy given Henley's $100K undercut:**
Don't fight the price. Henley at "$100,000 minimum" is a different product (Citizenship by Investment programs like Dominica/St. Kitts, which Henley also sells — they're misleadingly applying $100K language to a Panama CBI frame). Our $300K is Panama's *official QIP floor*, not a weakness. The counter-frame:
- **Don't**: lower-price messaging or any attempt to match the $100K anchor.
- **Do**: lean into program legitimacy and speed. "Official $300K Panama QIP — Residency in ~30 Days" positions the price as a qualifier, not a cost. The landing page already uses the 30-day hook in H1 (LIVE fetch confirmed: *"Secure Panama Residency Through a $300,000 Investment, in About 30 Days"*) — match this in RSA headlines.
- **Counter Orience**: They're claiming "EU Residency Rights" for Panama (false — Panama is not EU). Don't reference them in ads, but use truth as differentiation: "Panama Residency — No EU Requirement" or "Live, Work, and Travel in Panama — Not Just EU."
- **Latitude at pos 1.9**: They're anchoring $300K and leading with US-investor targeting across all 5 states. The competitive opening is speed and certainty ("~30 Days") which Latitude doesn't appear to lead with in the spy data — make that H1.
*— PPC Strategist*

### 2026-07-21 13:33 — Orchestrated finding

{
  "summary": "Week-1 CPA $749.82 is directionally under the $800 bar on n=2; 47.2% rank-lost IS (low QS) is the primary Latitude gap \u2014 fix is QS repair + sitelinks on Jul 23, not bid increases.",
  "findings": [
    {
      "claim": "Lifetime CPA of $749.82 is directionally under the $800 bar but rests on n=2 conversions \u2014 insufficient to confirm cost efficiency",
      "severity": "medium",
      "confidence": 0.55,
      "sources": [
        "LIVE GAQL: 2 conv / $1,499.65 lifetime, both from Property Investors / [PHRASE] buy property in panama"
      ],
      "disconfirmed_by": "Jul 23 pull shows CPA restating above $800 as more spend accumulates without additional conversions",
      "id": "c1-f0"
    },
    {
      "claim": "47.2% of impressions lost to Ad Rank (LIVE, lifetime) is the primary driver of our 2.8 avg position vs Latitude's 1.9 \u2014 low QS keywords (QS 1\u20133 on residency visa panama, panama investment visa, panama golden visa) are the root cause",
      "severity": "high",
      "confidence": 0.88,
      "sources": [
        "LIVE GAQL: search_rank_lost_impression_share = 0.472 lifetime",
        "keyword QS data: 8 of 25 keywords at QS 1\u20133",
        "PPC Reveal: Latitude 37.5% visibility / pos 1.9 / 119 ads"
      ],
      "disconfirmed_by": "Jul 23 pull shows rank-lost IS dropped below 30% without QS changes \u2014 indicating bid algorithm self-corrected",
      "id": "c1-f1"
    },
    {
      "claim": "Budget exhaustion is a secondary blocker \u2014 Jul 17 lost 64.9% of impressions to budget, Jul 16 lost 46.1% \u2014 a $300\u2013350/day budget is warranted if Jul 23 CPA holds under $800",
      "severity": "medium",
      "confidence": 0.78,
      "sources": [
        "LIVE GAQL: Jul 17 search_budget_lost_impression_share = 0.649, Jul 16 = 0.461",
        "lifetime budget-lost avg = 24.5%"
      ],
      "disconfirmed_by": "Jul 23 pull shows budget-lost IS below 5% on most days \u2014 negatives reducing spend sufficiently t

### 2026-07-22 16:32 — FRESH LIVE PULL + SINCE-JUL-21 VERDICT for campaign 24036236041 (customer 717823

**Task:** FRESH LIVE PULL + SINCE-JUL-21 VERDICT for campaign 24036236041 (customer 7178239091) ONLY. Use search_execute_query verbatim (google_ads_search_google_ads is broken — PAGE_SIZE_NOT_SUPPORTED, per GTM
Running three queries in parallel now — daily metrics, budget, and lifetime totals.Running all three queries in parallel now.All three reads came back live. Here's the tight verdict.
## Panama QIP v2 — Since-Jul-21 Report | LIVE this turn
**Baseline (Jul 21 pull):** $1,499.65 / 265 clicks / 2 conv / CPA $749.82 / IS 28.3% / rank-lost 47.2%
**Daily metrics Jul 19–22 (LIVE):**
| Date | Impr | Clicks | Cost | Conv | IS | Rank-Lost | Budget-Lost |
|---|---|---|---|---|---|---|---|
**Lifetime (LIVE):** $1,689.07 / 296 clicks / 2 conv → **CPA $844.53** — now OVER the $800 bar.
**Budget (LIVE):** `amount_micros = 200,000,000` = **$200/day.** The system does not have a $400 budget. Spend pacing ~$208/day is explained entirely by the $200 cap. If you've changed it recently, the read reflects the setting at pull time.
**(a) No-leads read**
Last conversion: Jul 19. Jul 20–21 = full days with 0 conversions. Jul 22 = partial day (10 clicks at pull time), so that zero doesn't count yet. n=2 caveat holds — you cannot declare decay on two data points. But with lifetime CPA at $844.53 and climbing, this is the first signal that the $800 bar is in jeopardy if a third conversion doesn't land soon. Restatement window (up to 90 days) means Jul
**(b) IS-27% diagnosis — the binding constraint is Ad Rank, NOT budget**
The live numbers make this unambiguous. Jul 22: rank-lost **79.2%**, budget-lost **0.6%**. Budget is eating less than 1% of eligible impressions today. Raising budget from $200 to $400 buys back ~0.6 percentage points of IS. Rank-lost is stealing 79.2 points. The two constraints are not close — **QS is the problem, not budget.** This pattern has been worsening all week: rank-lost was 56.1% on Jul 
**Important clarification on the $400 claim:** the live budget is $200/day. If you intended to set $400, either the update didn't save or it's a different campaign. Do not raise budget until the QS fix is in — it won't help IS at 79% rank-lost.
**(c) Jul 23 is tomorrow — approved moves are ready**
Jul 23 is the 7-day mark post-negatives + goal change. All three freeze-locked packages are ready to execute in sequence (one change type per day):
1. **RSA keyword-mirroring rewrites** — Creative Director's 15-headline bank with per-ad-group H1 pins ($300K + ~30 Days mirroring LP h1). Targets ad relevance on QS:1 keywords (`residency visa panama`, `panama investment visa`). This is the primary rank-lost fix.
2. **6 sitelinks** — Creative Director's spec: `$300K Investment Threshold`, `How Panama QIP Works`, `30-Day Timeline`, `Free Consultation`, `Panama vs Other Programs`, `Official Government Program`. Closes asset-depth gap vs Latitude's 119-ad battery, lifts expected CTR component of Ad Rank independently of QS.
3. **`[EXACT] panama permanent residency by investment`** — Competitor Intel identified 16 advertisers, zero Mercan presence. Add to Investor Program (High Intent) ad group.
Execute RSAs + sitelinks together (both ad-side, not bid-side — same change type). `[EXACT]` keyword is a separate change type; execute the following day.
Do not touch budget or bids on Jul 23. The rank-lost trajectory needs a QS intervention first. If after 7 days the RSA rewrites move ad relevance to Above Average and rank-lost drops below 50%, then raising budget makes sense. Not before.
*— PPC Strategist*

### 2026-07-22 16:35 — Orchestrated finding

{
  "summary": "Budget is $200/day (not $400), rank-lost IS is 79% and worsening, CPA is $844 and over the bar \u2014 the fix is tomorrow's RSA rewrites on Jul 23, not a budget increase.",
  "findings": [
    {
      "claim": "Live budget is $200/day \u2014 the user's claimed $400 budget is not reflected in the system; the spend-vs-IS gap is explained by budget being at cap, not underspend",
      "severity": "high",
      "confidence": 0.99,
      "sources": [
        "LIVE GAQL: campaign_budget.amount_micros = 200,000,000 = $200/day"
      ],
      "disconfirmed_by": "A second live pull showing amount_micros = 400,000,000 \u2014 would mean the update saved after this pull",
      "id": "c1-f0"
    },
    {
      "claim": "Raising budget will not recover IS \u2014 rank-lost is 79.2% on Jul 22 vs budget-lost of 0.6%; the binding constraint is Ad Rank/QS, not spend cap",
      "severity": "high",
      "confidence": 0.97,
      "sources": [
        "LIVE GAQL: Jul 22 search_rank_lost_impression_share = 0.792, search_budget_lost_impression_share = 0.006"
      ],
      "disconfirmed_by": "Post-RSA-rewrite QS pull showing keywords moving to Above Average ad relevance and rank-lost dropping below 40% \u2014 at which point budget becomes the next binding constraint",
      "id": "c1-f1"
    },
    {
      "claim": "Lifetime CPA has crossed $800 at $844.53 \u2014 directionally over the bar with no new conversions since Jul 19; n=2, restatement still possible",
      "severity": "medium",
      "confidence": 0.75,
      "sources": [
        "LIVE GAQL: lifetime cost_micros = 1,689,069,024 / 2 conversions = $844.53",
        "Last conv: Jul 19; Jul 20\u201321 full days at 0"
      ],
      "disconfirmed_by": "A Jul 20 or Jul 21 conversion restating in-platform within the next 48 hours \u2014 would bring CPA back under $800",
      "id": "c1-f2"
    },
    {
      "claim": "Rank-lost IS is trending worse week-over-week (56% \u2192 79%) \u2014 QS decay without an ad-copy fix

### 2026-07-22 16:44 — i said ai have an increase in budget i can go to 400

**Task:** i said ai have an increase in budget i can go to 400
Understood, Wassim — that one's on me. You weren't claiming $400 was already set; you're telling me you have approval to take this campaign **up to $400/day**. The live read stands at $200/day, and the headroom is yours to deploy whenever we choose. Noted and logged.
My recommendation: **hold the $400 for ~72 hours.** Deploying it today buys almost nothing — here's the math from this session's live pull:
- **Jul 22: budget-lost = 0.6%, rank-lost = 79.2%.** Doubling budget attacks the 0.6%. The extra $200/day cannot buy impressions Google won't rank us for — Ad Rank is the gate right now, not money.
- **~86% of active spend is still house-shopper/wrong-program traffic** (Search Term Hunter's post-negative verdict this session). At the current mix, $400/day means roughly $170/day *more* going to listing-browse clicks.
- **CPA just crossed your bar at $844.53** with nothing since Jul 19. Doubling spend into dirty traffic moves that number the wrong way.
There's also a sequencing conflict: a budget change is its own change type, and today's slot belongs to the negative batch (still pending your "go" from my last message).
**When the $400 goes in — the exact trigger:**
| Day | Move |
|---|---|
| Today, on your go | Re-push the phrase negatives + new batch (eb5an, casa solution, viviun, etc.) |
| Jul 23 | RSA keyword-mirrored rewrites + 6 sitelinks — the direct attack on the 79% rank-lost |
| Jul 24 | `buy property in panama` → EXACT + investment-intent replacements |
| **Rank-lost < ~50% + clean search terms** (realistic read: Jul 26–28) | **Budget → $400/day.** At that point budget becomes the binding constraint again, and the increase buys real impression share in the auctions Latitude is winning — not more house-shoppers. |
That's the plan I'd sign my name to: make the traffic worth doubling down on first, then double down. Your $400 is the weapon for *after* the QS fix — spent then, it's the move that closes the impression-share gap; spent now, it subsidizes waste.
That said, it's your account. If you want $400 live today regardless, say **"set 400 now"** and I'll execute the budget update and verify it live in the same turn. And either way — I still need your **"go"** on the negatives batch; that's today's highest-value, zero-risk move.
*— PPC Strategist*

### 2026-07-22 16:46 — explain more and the 27% impression share is not a budget problem — it's a Quali

**Task:** explain more and the 27% impression share is not a budget problem — it's a Quality Score collapse, with 79% of eligible impressions now lost to Ad Rank and less than 1% lost to budget.
Good — this is the most important concept in the whole diagnosis, and it's worth ten minutes to really get it. Everything below uses the live numbers from this session's pull; no new data needed. Let me build it from the ground up.
## 1. What "impression share" actually counts
Every time someone in the US types one of your keywords, Google runs an instant auction to decide which ads show. Your **impression share** is simply:
> the number of auctions your ad actually appeared in ÷ the number of auctions you were *eligible* to appear in
Your 27% (period average — the daily trend is worse: 36% on Jul 19 down to 20% on Jul 22) means: for every 100 searches you could have shown on, your ad showed 27 times. **73 searches went by where a potential Panama investor searched, and your ad was invisible.**
The critical part: Google tells you *why* you missed the other 73. There are only two possible reasons, and they have completely different fixes.
## 2. The two ways to lose an auction
| Lost to... | What it means | The fix |
|---|---|---|
| **Budget** | Your ad *would have won* the auction, but your daily budget was already spent — Google stopped entering you into auctions to avoid overspending | More money |
| **Rank** | You were entered into the auction with money available — and **lost it**. Your Ad Rank score was too low to earn a spot | Better ads, not more money |
These are mutually exclusive per auction. And here is your live split for Jul 22:
- **Lost to rank: 79.2%**
- **Lost to budget: 0.6%**
Read that literally: out of 100 eligible searches, you showed on ~20, you lost **79 because Google judged your ad not good enough to show**, and you lost **less than 1** because money ran out. Your budget was almost never the reason you were absent. That's why I said doubling to $400 "attacks the 0.6%" — the extra $200/day can only buy back auctions lost to budget, and there's essentially nothing 
## 3. What Ad Rank is — and why you can't just outbid a quality problem
For every auction, Google scores every advertiser:
Quality Score (QS) is Google's 1–10 rating of how relevant you are to that exact search, built from three things: **expected clickthrough rate** (do people click your ad?), **ad relevance** (do the ad's words match the search?), and **landing page experience**.
Now the math that explains everything. Take `panama investment visa`, where your QS is **1** and 17 advertisers compete:
| Advertiser | Bid | QS | Ad Rank |
|---|---|---|---|
Same bid, they beat you 8-to-1. To *tie* them on Ad Rank at QS 1, you'd need to bid roughly **$40 per click**. That's what "structural" means: at QS 1–2, no sane bid or budget closes the gap. Money multiplies quality — and anything times one is still small.
Your live QS profile on the auctions that matter: `panama investment visa` **QS 1**, `panama golden visa` **QS 1**, `panama residency by investment` **QS 1**, `residency visa panama` **QS 2**, `panama real estate investment` **QS 2**, `panama qualified investor program` (exact) **QS 3**. These are precisely the auctions where Latitude sits at position 1.9 — and precisely where Google is refusing t
## 4. Why it's *collapsing* rather than just sitting low
Rank-lost went **56% → 65% → 79%** across Jul 19–22. That acceleration is a feedback loop, and the dirty traffic is fueling it:
1. `[PHRASE] buy property in panama` keeps matching house-shopper searches ("real estate panama city panama", "houses for sale in panama" — ~86% of active spend per the Hunter's verdict this session)
2. A house-shopper sees an ad about a $300K residency program → many don't click, and the ones who do never convert
3. Google reads that weak engagement as "this advertiser's ads aren't what searchers want" → **expected CTR falls**
4. Expected CTR is a QS input → QS falls → Ad Rank falls → you show less often and in worse positions → CTR degrades further → repeat
Meanwhile the ad-relevance component is weak for a separate reason: your RSA headlines don't contain the exact keyword phrases. When someone searches "residency visa panama" and the headline doesn't say those words, Google scores relevance down before a single click happens.
## 5. Why this ordering of fixes — each move maps to one component of the score
| Move (planned day) | Which lever it pulls |
|---|---|
| Negatives batch + `buy property in panama` → EXACT (today / Jul 24) | Stops matching junk queries → stops the expected-CTR bleeding at its source |
| RSA rewrites, keyword-mirrored H1s (Jul 23) | **Ad relevance** — the fastest QS component to move; headline literally contains the search phrase |
| 6 sitelinks (Jul 23) | Ad assets raise Ad Rank directly and lift expected CTR (bigger, richer ad on the page) |
| **Then** budget → $400 | Only once rank-lost drops below ~50% does budget become the thing standing between you and impressions — at that point the $400 buys real share in the Latitude auctions instead of more house-shopper clicks |
One way to hold the whole thing in your head: **impression share is a door, and there are two locks on it. The budget lock is open — 0.6%. The quality lock is bolted shut — 79%. More money just means standing at the locked door holding more cash.** Fix the ads and the traffic first; then the money opens real doors.
The scoreboard to watch after Jul 23's changes land: **rank-lost trending down** (79% → below 50%) and QS on those five keywords moving off 1–2. The moment those move, I'll flag it — that's the day your $400 goes in.
*— PPC Strategist*

### 2026-07-23 11:03 — SINCE-YESTERDAY LIVE VERDICT for campaign 24036236041 (customer 7178239091) ONLY

**Task:** SINCE-YESTERDAY LIVE VERDICT for campaign 24036236041 (customer 7178239091) ONLY. Use search_execute_query verbatim (google_ads_search_google_ads is broken — PAGE_SIZE_NOT_SUPPORTED). Pull live: (1) d
Pulling the three live reads now — daily Jul 21–23 with IS metrics, lifetime totals, and budget. Loading the tool first.Running all three live reads in parallel now.Live reads back. Here's the tight status.
## Panama QIP v2 — Jul 23 Morning Read | LIVE this turn
**Baseline (cited, Jul 22 session):** $1,689.07 / 296 clicks / 2 conv / CPA $844.53 / rank-lost 77.0% / budget-lost 0% / $200/day
**Daily Jul 21–23 (LIVE):**
| Date | Impr | Clicks | Cost | Conv | IS | Rank-Lost | Budget-Lost |
|---|---|---|---|---|---|---|---|
**Lifetime (LIVE):** $1,835.41 / 328 clicks / **3 conversions → CPA $611.80** — back well under the $800 bar.
**Three findings:**
- **New conversion today (Jul 23 partial).** 3rd conversion landed this morning; CPA drops from $844.53 to $611.80. n=3, restatement window still open, but direction is right.
- **Rank-lost bending down.** 64.9% → 77.0% → **65.8%** today. Jul 22's 77% peak was largely pre-negative (batch went in at 17:24 that day); Jul 23's early read shows the negatives are pulling rank-lost back toward the Jul 21 level. Not conclusive on a partial day, but it's the right signal.
- **Budget still $200/day confirmed.** Jul 22 spent only $98.77 — the negatives cut enough junk queries that Google couldn't spend the cap. That's the batch working, not a budget problem. Today is tracking similarly ($80.39 by mid-afternoon).
**Today's slot (Jul 23) — awaiting your "go":** Creative Director's freeze-locked RSA package: keyword-mirrored H1 pins per ad group (`$300,000 Investment` / `Panama Residency in ~30 Days` matching the LP h1), H2 `Licensed Immigration Advisors`, 12 shared rotation headlines, 4 descriptions, plus 6 sitelinks (`$300K Investment Threshold`, `How Panama QIP Works`, `30-Day Processing Timeline`, `Free 
**Jul 24 slot:** `buy property in panama` PHRASE → EXACT + replacements (pending your approval as that day arrives).
**Budget → $400:** hold until rank-lost confirms below ~50% (Jul 26–28 read, or sooner if Jul 23 RSAs accelerate the QS move).
Today is also the **7-day mark since the Jul 16 negatives + custom-goal change** — first clean read window, and a conversion landed on it.
*— PPC Strategist*

### 2026-07-23 11:05 — Orchestrated finding

{
  "summary": "Third conversion landed today, CPA back to $611.80; rank-lost early read improving to 65.8% from 77% \u2014 negatives are working; RSA package is today's slot, awaiting your go.",
  "findings": [
    {
      "claim": "Third conversion landed Jul 23 (partial day); lifetime CPA is now $611.80 \u2014 well under the $800 bar",
      "severity": "high",
      "confidence": 0.85,
      "sources": [
        "LIVE GAQL: lifetime cost_micros=1,835,409,465 / 3 conversions = $611.80",
        "Jul 23 partial row: 1 conv / 87 impr / 18 clicks / $80.39"
      ],
      "disconfirmed_by": "Conversion restatement removing it in the next 72 hours \u2014 would push CPA back above $800",
      "id": "c1-f0"
    },
    {
      "claim": "Rank-lost IS is bending down (77.0% Jul 22 \u2192 65.8% Jul 23 partial) \u2014 early signal the Jul 22 negative batch is reducing junk query eligibility",
      "severity": "high",
      "confidence": 0.65,
      "sources": [
        "LIVE GAQL: Jul 21 rank-lost 64.9%, Jul 22 77.0%, Jul 23 65.8%",
        "Jul 22 spend only $98.77 vs $200 cap \u2014 negatives cut eligible auction pool"
      ],
      "disconfirmed_by": "End-of-day Jul 23 read showing rank-lost back above 75% \u2014 would mean today's partial IS is misleading and QS hasn't improved",
      "id": "c1-f1"
    },
    {
      "claim": "Budget stays at $200/day confirmed; $400 deployment trigger is rank-lost sustainably below ~50%",
      "severity": "medium",
      "confidence": 0.99,
      "sources": [
        "LIVE GAQL: campaign_budget.amount_micros = 200,000,000"
      ],
      "disconfirmed_by": "Nothing \u2014 budget is a live-verified fact, not an inference",
      "id": "c1-f2"
    }
  ]
}
