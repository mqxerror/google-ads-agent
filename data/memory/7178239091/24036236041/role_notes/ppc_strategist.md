# Ppc Strategist Notes

**Last updated:** 2026-07-21 13:33

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
