# Analytics Analyst Notes

**Last updated:** 2026-07-24 11:50

**Task:** Assess the 0-conversions reading using ONLY in-context evidence. Critical flag: the LIVE landing page fetch this session for https://www.mercan.com/lp/panama-qualified-investor-program returned HTTP 2

**Critical Details:** GTM-injected
## Measurement Caveat — 0 Conversions (Jul 14–16)
**95 clicks / $471.66 / 0 conversions — root cause unconfirmed, but two gaps demand immediate verification before trusting this number:**
**1. Landing page form/tracking — verification gap**
Live fetch this session returned HTTP 200 but `form signal: none detected` and `tracking token: none detected`. The heuristic cannot pierce JS-rendered content or GTM-injected tags, so this is **not a confirmed outage** — but it raises the probability that either (a) the form doesn't render without JS execution, or (b) the conversion tag isn't firing. Either condition guarantees 0 recorded convers
**2. No dedicated Panama QIP conversion action found in the registry**
Global rules require every campaign to have its own PRIMARY WEBPAGE conversion action. The in-context registry lists actions for Portugal GV, Greece GV, and EB3 Brazil — **no Panama QIP entry appears**. If this campaign is optimizing against a secondary or incorrect action (or none at all), Maximize Conversions has no valid signal.
**Action required before any budget/bid interpretation:**
- Render the landing page in a real browser and confirm the form is visible
- Pull the live conversion actions assigned to this campaign and verify a PRIMARY WEBPAGE action exists and is firing on form submit

---

## Session Log

### 2026-07-16 12:58 — report campaign performance use new serach terms report

**Task:** report campaign performance use new serach terms report

**Critical Details:** GTM-loaded
Reporting from the data already in context — no re-fetch needed.
# Panama QIP — US — Search — v2 · Performance Report
**Campaign 24036236041 · Account 7178239091 · 2026-07-14 → 07-16 (3 days) · USD**
## Headline
**$471.66 spent, 95 clicks, 0 conversions — but the zero is not the story.** At 95 clicks with a multi-day attribution window on a $300K investment product, 0 conversions is statistically expected noise, not a failure signal. The real finding is in the search terms: **roughly half the budget is buying Panama home-shoppers, not investors.**
## 1. WHAT happened
| Date | Impr | Clicks | Cost | Conv | CTR | CPC |
|---|---|---|---|---|---|---|
Two directional signals in 48 hours: **CPC is up 40%** ($4.17 → $5.84) while **CTR is down 45%** (11.0% → 6.0%). Paying more for progressively less relevant traffic.
**Spend is flowing inversely to intent:**
| Ad group | Clicks | Cost | % of spend | Conv |
|---|---|---|---|---|
Your highest-intent ad group took **2.6% of budget**. `[panama qualified investor program]` (exact) has **0 clicks**. The loosest keyword in the account — `[PHRASE] buy property in panama` — took **51 of 95 clicks (54%)**, roughly **$233** at the ad group's $4.58 average CPC.
## 2. WHY — the search terms report
Of the 40 terms visible, here is what the money actually bought:
| Intent bucket | Clicks | Cost | Example terms |
|---|---|---|---|
**One click out of 25 in the visible sample was on-program.** The rest are consumers browsing houses — `realtor.com`, `encuentra24`, and Panama's retiree/vacation-home markets (Boquete, Coronado, Pedasi, El Valle). Someone typing "homes for sale in panama city panama" is buying a house. Someone qualified for QIP is deploying $300K for residency. These are different people, and right now you're pay
**Root cause:** `buy property in panama` on phrase match. Phrase matching is semantic in 2026 — it treats "buy property in panama" as equivalent to "houses for sale in panama." The keyword *concept* is on-thesis (QIP is a real-estate investment). The *match type* is doing the damage.
**Secondary:** `friendly nations visa panama` produced a click while the Friendly Nations Visa ad group is PAUSED — another keyword caught it and routed the searcher to QIP messaging. Small leak, but it means FNV demand is live and currently landing on the wrong ad.
**Bidding:** Maximize Conversions with **zero conversion history** has no model to optimize against. Per account rules, Max Conversions needs ~15 conv/30 days to function. That's the likeliest driver of the rising CPC — it's bidding blind.
## 3. Two things I could NOT verify (flagging, not diagnosing)
- **Landing page form.** The live fetch of `mercan.com/lp/panama-qualified-investor-program` returned HTTP 200 with correct title/H1, but **no form signal and no tracking token in the raw HTML**. This does *not* prove they're absent — a JS-injected form or GTM-loaded tag wouldn't appear in a static fetch. But it's unverified, and at $220/day it should be confirmed in a live browser before the next
- **Panama conversion action.** The conversion registry has entries for Portugal GV and Greece GV — **no Panama-specific action is listed**. Account rule requires each campaign have its own dedicated PRIMARY conversion action. I have no Panama action ID confirmed this session — **ID not verified; pull it before relying on it.**
## 4. NOW WHAT — prioritized, one change type at a time
**Today — verify (blocks everything else):** confirm the LP form renders and fires, and confirm which conversion action this campaign is optimizing toward. If the form path is broken, no keyword work matters.
**Next — negatives (low impact, reversible, ~50% of waste).** All grounded in real search term data, no assumptions:
- *Exact:* `[panama real estate]`, `[real estate in panama]`, `[panama real estate for sale]`, `[panama city panama real estate]`, `[panama homes for sale]`
- *Phrase:* `"homes for sale"`, `"houses for sale"`, `"house for sale"`, `"condos for sale"`, `"condo for sale"`, `"apartments for sale"`, `"realtor"`, `"encuentra24"`, `"boquete"`, `"coronado"`, `"pedasi"`, `"el valle"`, `"panama pacifico"`, `"chile"`
I'm deliberately **not** blocking `retiring in panama` or `pensionado` — a wealthy American retiring to Panama with $300K is a plausible QIP buyer. Watch, don't block.
**Then — wait 7 days, then reassess bidding.** If conversions stay at 0 with clean traffic, Maximize Conversions is the wrong tool at this volume; Maximize Clicks with a CPC cap (~$5) is the account-rule-compliant alternative. Don't touch bidding the same day as the negatives.
## Data caveats
- The visible top-40 accounts for **25 of 95 clicks (~26%)** — the other ~70 clicks sit in the untruncated tail. The negative list above is directionally sound but not exhaustive. **Say the word and I'll pull the full search terms report via GAQL** to complete it before we push anything.
- All 3 days are inside the attribution window. Conversion counts will restate upward.
- No historical CPA/CPC baseline exists for this campaign — it's 3 days old. I'm not importing benchmarks from other campaigns.
**Want me to (a) pull the full search terms tail, (b) push the negative list, or (c) verify the LP form in the browser first?** My recommendation is (c) → (a) → (b).
*— Analytics Analyst*

### 2026-07-16 12:58 — Orchestrated finding

{
  "summary": "0 conversions is most likely a tracking gap (no confirmed Panama QIP PRIMARY conversion action + unverifiable form/tag on live fetch) \u2014 verify conversion setup before interpreting performance or letting Maximize Conversions continue spending.",
  "findings": [
    {
      "claim": "0 conversions is likely caused by a missing or misfiring dedicated conversion action for Panama QIP, not by traffic quality",
      "severity": "high",
      "confidence": 0.65,
      "sources": [
        "in-context conversion registry has no Panama QIP PRIMARY WEBPAGE entry",
        "LIVE fetch: form signal none detected, tracking token none detected",
        "global rules: every campaign requires its own PRIMARY conversion action"
      ],
      "disconfirmed_by": "A live form-submit test that shows the GV Lead conversion (or a Panama-specific action) firing in the network requests",
      "id": "c3-f0"
    },
    {
      "claim": "Maximize Conversions is bidding blind \u2014 zero conversion signal in 2 days means the algorithm defaults to click volume, inflating CPC and misallocating budget to low-intent property-search queries",
      "severity": "high",
      "confidence": 0.85,
      "sources": [
        "0 conversions across all ad groups",
        "CPC +40% in 3 days (4.17\u21925.84)",
        "Property Investors absorbing 56% of spend on generic real estate terms"
      ],
      "disconfirmed_by": "Confirmed tracking outage \u2014 if conversions are being recorded elsewhere (e.g. secondary action) the algorithm may have some signal not visible in this report",
      "id": "c3-f1"
    },
    {
      "claim": "Conversion lag is NOT the primary explanation here \u2014 the landing page tracking verification gap is a more urgent hypothesis",
      "severity": "medium",
      "confidence": 0.75,
      "sources": [
        "campaign is only 2 days old so lag is plausible, but the fetch showing no tracking token is a stronger signal",
        "no Panama-specific c

### 2026-07-16 13:13 — Update your Measurement Caveat (cite your existing Jul 14-16 report — do NOT red

**Task:** Update your Measurement Caveat (cite your existing Jul 14-16 report — do NOT redo it) given new user evidence: a lead arrived with a click ID, so the landing-page form renders and captures GCLID (the 
## Measurement Caveat — Updated (Jul 16, post-lead-with-GCLID)
**Citing my Jul 14–16 report (95 clicks / $471.66 / 0 conv) — not redoing it.**
The form-existence flag is resolved. A lead arriving with a GCLID confirms the page renders, the form submits, and the click ID is captured downstream. That closes half the gap.
The conversion-recording gap remains open:
- **No verified Panama QIP PRIMARY WEBPAGE action in the registry.** The registry shows Portugal GV, Greece GV, and EB3 Brazil. If no PRIMARY action is mapped to this campaign, that lead's form submit is either (a) recording to a SECONDARY action (which doesn't feed Maximize Conversions) or (b) not recording at all in Google Ads.
- **Attribution lag.** Even if the action fires correctly, conversions restate for 24–72 hours. This lead may appear in-platform by tomorrow — 0 today is not 0 final.
- **Primary vs secondary distinction.** GA4 `form_submit` (ID 6953214477) is account-level SECONDARY — it fires on every form on mercan.com and is explicitly excluded as a campaign goal per account rules. If that's the only thing recording this lead, Maximize Conversions sees nothing.
**Bidding read unchanged:** the +40% CPC / falling CTR pattern stands until a PRIMARY action is confirmed receiving conversions. The algorithm is still bidding blind.
**What closes the case:** the GTM Specialist's live GAQL pull of the conversion actions assigned to campaign 24036236041 — if it shows a PRIMARY WEBPAGE action with a URL rule matching `/lp/panama-qualified-investor-program`, and that action has ≥1 conversion within 72 hours of the lead, the gap is closed.
*— Analytics Analyst*

### 2026-07-16 13:17 — Orchestrated finding

{
  "summary": "Form and GCLID are confirmed working; the open question is whether a PRIMARY WEBPAGE conversion action exists for this campaign \u2014 that single GAQL lookup resolves everything.",
  "findings": [
    {
      "claim": "Form and GCLID capture are confirmed working \u2014 the 'no form signal' flag from the static fetch is resolved by the live lead outcome",
      "severity": "low",
      "confidence": 0.95,
      "sources": [
        "User report: lead received with GCLID attached"
      ],
      "disconfirmed_by": "N/A \u2014 this is now confirmed by outcome",
      "id": "c2-f0"
    },
    {
      "claim": "Google Ads still showing 0 conversions because no Panama QIP PRIMARY WEBPAGE conversion action is verified in the campaign registry \u2014 the lead may be recording to a secondary action (or not recording at all in-platform)",
      "severity": "high",
      "confidence": 0.8,
      "sources": [
        "In-context conversion registry: Portugal GV, Greece GV, EB3 Brazil \u2014 no Panama QIP PRIMARY WEBPAGE entry",
        "Account rule: each campaign must have its own dedicated PRIMARY WEBPAGE action; SECONDARY actions do not feed Maximize Conversions"
      ],
      "disconfirmed_by": "GTM Specialist GAQL pull this session shows a ENABLED PRIMARY WEBPAGE action with URL matching /lp/panama-qualified-investor-program assigned to campaign 24036236041",
      "id": "c2-f1"
    },
    {
      "claim": "Attribution lag alone could explain 0 in-platform conversions \u2014 the GCLID lead may restate within 24\u201372 hours regardless of action mapping",
      "severity": "medium",
      "confidence": 0.7,
      "sources": [
        "Account knowledge: high-ticket investment products carry multi-day attribution windows; conversions restate for several days per account rules"
      ],
      "disconfirmed_by": "72 hours elapse with no conversion appearing in platform \u2014 at that point lag is exhausted and mapping gap is the live hypothesis",
      "id"

### 2026-07-16 14:11 — Update your Measurement Caveat (cite your existing Jul 14–16 report — 95 clicks 

**Task:** Update your Measurement Caveat (cite your existing Jul 14–16 report — 95 clicks / $471.66 / 0 conv — do NOT redo it) with the decisive new fact fetched live this turn: a 'Panama QIV Lead' conversion a
## Measurement Caveat — Updated (Jul 16, post-GCLID + live registry)
**Citing my Jul 14–16 report (95 clicks / $471.66 / 0 conv) — not redone.**
**Finding c2-f1 is disconfirmed.** "Panama QIV Lead" (id 7607343274) exists, ENABLED, PRIMARY. The remembered registry was stale. The account-level gap is closed.
**Remaining explanations for 0 in-platform conversions, re-ranked by probability:**
- **(b) Attribution lag — most likely.** Campaign is 3 days old; high-ticket attribution windows run 24–72h. The GCLID lead may simply restate by ~Jul 19. GTM Specialist's pull would show: action 7607343274 has ≥1 conversion in the last 7 days against this campaign's GCLID.
- **(c) Selective optimization — medium priority.** If the campaign's goal settings exclude 7607343274, Maximize Conversions is still blind even though the action exists. GTM Specialist's pull would show: `campaign_conversion_goal` query returns 7607343274 with `biddable = true` for campaign 24036236041.
- **(a) Tag/URL rule not firing — lower now.** GCLID in CRM is strong evidence the form submits. GTM Specialist's pull would show: 0 conversion events recorded against 7607343274 in the last 7 days despite the confirmed submit.
**Bidding read revised:** if (c) is clear AND (b) is the live cause, the +40% CPC / falling CTR is ordinary learning-phase behavior — the algorithm is accumulating click signal and will anchor once the first conversion surfaces. Still no bid/budget changes; campaign is 3 days old, phase rules hold.
**Spend flag (no re-analysis):** Jul 16 live table now shows 712 impr / 52 clicks / **$379.29** vs. the $222.10 in the original report — day 3 restated significantly hotter. Daily run rate is tracking above $220/day.
*— Analytics Analyst*

### 2026-07-16 14:13 — Orchestrated finding

{
  "summary": "Registry gap disconfirmed \u2014 7607343274 exists and is PRIMARY; 0 conversions is most likely attribution lag (lead may restate by Jul 19), with campaign-level goal mapping as the one unverified risk still needing the GTM Specialist's GAQL pull.",
  "findings": [
    {
      "claim": "Attribution lag (24\u201372h) is now the primary explanation for 0 recorded conversions \u2014 the GCLID lead may restate against action 7607343274 by Jul 19",
      "severity": "medium",
      "confidence": 0.72,
      "sources": [
        "Account knowledge: high-ticket investment products carry multi-day attribution windows",
        "Panama QIV Lead 7607343274 confirmed ENABLED PRIMARY this session",
        "User-confirmed CRM lead with GCLID = form submit is real"
      ],
      "disconfirmed_by": "Jul 19 passes with no conversion appearing in-platform against 7607343274 \u2014 at that point lag is exhausted and (a) or (c) is the live cause",
      "id": "c2-f0"
    },
    {
      "claim": "Campaign selective optimization may exclude 7607343274 from this campaign's bidding goals \u2014 verification of campaign_conversion_goal mapping is the single remaining open check",
      "severity": "high",
      "confidence": 0.65,
      "sources": [
        "Decision log: GTM Specialist's GAQL pull was blocked by role-permission mismatch and never executed",
        "A conversion action existing at account level does not guarantee it is mapped as biddable for campaign 24036236041"
      ],
      "disconfirmed_by": "GTM Specialist's campaign_conversion_goal GAQL query returns 7607343274 with biddable=true for campaign 24036236041",
      "id": "c2-f1"
    },
    {
      "claim": "Jul 16 spend restated to $379.29 (vs $222.10 in original report) \u2014 daily run rate is tracking materially above $220/day but no re-analysis warranted yet",
      "severity": "low",
      "confidence": 0.99,
      "sources": [
        "Live daily table: 2026-07-16 712 impr / 52 clicks / $379.29

### 2026-07-16 16:52 — Update your Measurement Caveat (cite your 14:11 update and the Jul 14–16 report 

**Task:** Update your Measurement Caveat (cite your 14:11 update and the Jul 14–16 report on file — do NOT redo either) with the decisive fact now in live context: 1 CONVERSION recorded on 2026-07-16 (daily tab
## Measurement Caveat — Updated (Jul 16, 20:51 · post-first-conversion)
**Citing my 14:11 update and the Jul 14–16 report on file — neither redone.**
**1. Re-rank.** My (b) attribution-lag hypothesis (c2-f0) is **provisionally CONFIRMED**: the live daily table now shows **1 conv on 2026-07-16** (696 impr / 50 clicks / $370.79). Something recorded. Pending the GTM Specialist's attribution read naming *which* action fired, (c) selective-optimization drops to unlikely and (a) tag misfire is effectively dead.
**2. What n=1 licenses — almost nothing.** 3-day totals: ~1,517 impr / 107 clicks / ~$620 / 1 conv → observed CPA **~$620**. Per pinned facts (campaign <7 days), that is **not a baseline** and must not be quoted as one. One conversion validates nor condemns no ad group — Property Investors' 68 clicks / $361.50 / 1 conv is a coin landing once.
**3. Strategic wrinkle.** The sole conversion arrived through **[PHRASE] "buy property in panama"** (61 clicks / 1 conv) — the exact keyword the team recommended pausing. **That pause/replace goes ON HOLD** pending the attribution verdict and the 7-day post-negative search-terms pull. The 20-negative batch **stays** (EXCLUDED statuses visible in the terms table); none of those terms produced the c
**4. Bidding.** Maximize Conversions just got its first real signal. **Zero bid/budget changes** — learning phase, one change type per day.
*— Analytics Analyst*

### 2026-07-16 16:54 — Orchestrated finding

{
  "summary": "First conversion landed Jul 16 (~$620 observed CPA on n=1, not a baseline) \u2014 attribution lag provisionally confirmed, negatives stay, and the pause of 'buy property in panama' goes on hold because it carried the conversion.",
  "findings": [
    {
      "claim": "Attribution lag confirmed as the cause of the earlier 0-conversion reading \u2014 no tracking remediation needed",
      "severity": "medium",
      "confidence": 0.85,
      "sources": [
        "Live daily table 2026-07-16: 696 impr / 50 clicks / $370.79 / 1 conv",
        "My 14:11 caveat ranking lag as most likely (c2-f0)"
      ],
      "disconfirmed_by": "GTM Specialist's attribution read showing the conversion recorded against a SECONDARY action (e.g. GA4 form_submit 6953214477) rather than Panama QIV Lead 7607343274",
      "id": "c2-f0"
    },
    {
      "claim": "HOLD the recommended pause/replace of [PHRASE] 'buy property in panama' \u2014 it carried the only conversion (61 clicks / 1 conv)",
      "severity": "high",
      "confidence": 0.8,
      "sources": [
        "Live keyword table: [PHRASE] buy property in panama 61 clicks / 1 conv",
        "Ad group table: Property Investors 68 clicks / $361.50 / 1 conv"
      ],
      "disconfirmed_by": "7-day post-negative search-terms pull showing the keyword still >80% listing-browse queries with no second conversion",
      "id": "c2-f1"
    },
    {
      "claim": "Do NOT treat observed CPA ~$620 as a baseline \u2014 campaign is <7 days old with n=1",
      "severity": "medium",
      "confidence": 0.95,
      "sources": [
        "3-day totals ~1,517 impr / 107 clicks / ~$620 / 1 conv",
        "Pinned fact: no CPA/CPC baselines until 7 days + 100 impressions"
      ],
      "disconfirmed_by": "Nothing \u2014 this is a definitional constraint, not an inference",
      "id": "c2-f2"
    },
    {
      "claim": "Keep the 20-negative batch in place; make zero bid/budget changes this cycle",
      "severity": "low",
      "confi

### 2026-07-24 11:48 — TRUTH LAYER for campaign 24036236041 (customer 7178239091) ONLY. Run ONE live se

**Task:** TRUTH LAYER for campaign 24036236041 (customer 7178239091) ONLY. Run ONE live segmented conversion pull via search_execute_query: conversions by segments.conversion_action (+ name), by date, Jul 14–24
Running the segmented conversion pull now.Live pull complete. Here is the honest truth layer.
**TRUTH LAYER — Segmented conversion pull, live this turn**
All 3 conversions are confirmed against **Panama QIV Lead (7607343274, PRIMARY)** — dates Jul 16, Jul 19, Jul 23, one per date, no restatement up or down. The mechanism claim is verified: no secondary action noise, no double-counting, no gap.
**What the numbers honestly say (citing prior desk reports, not redoing them):**
- Every conversion came through **Property Investors / listing-browse queries** (Search Term Hunter confirmed: "panama home for sale" served via the PHRASE keyword). The campaign's stated thesis — capturing QIP investor intent — has been tested with roughly **$800 combined spend** across Investor Program, Residency Core, and RBI Category, and has produced **zero conversions** in those three groups
- **CPA $661.91 is n=3 and not a baseline** (pinned fact). Three conversions from a listing-browse keyword is not evidence the campaign is working as designed; it's evidence that a subset of home-sale searchers convert on this offer. That may be fine, but it is not the thesis.
- **Rank-lost ~72%** (Jul 23 full-day close, per Creative Director). The RSA rewrites and pins landed Jul 23, but no QS movement is visible yet — the QS repair is **unproven** at this checkpoint.
- **Ad strength POOR on all 8 RSAs** is a real trade-off we chose (double-pinning to guarantee investor-qualifier on every impression), not noise. We own that decision.
**What you cannot honestly tell a CEO this week:** "Our campaign is reaching qualified QIP investors." You can honestly say: "We have 3 confirmed leads at $662 CPA, all from listing-adjacent traffic; our investor-intent ad groups are live but untested at meaningful volume; we shipped the QS fix (new RSAs + sitelinks) Jul 23 and the first honest read is Jul 26–28."
**UNVERIFIED:** whether the listing-browse converters are genuine $300K QIP prospects or mis-matched inquiries — that requires CRM quality data, which sits outside this pull.
*— Analytics Analyst*

### 2026-07-24 11:50 — Orchestrated finding

{
  "summary": "All 3 conversions confirmed PRIMARY (Panama QIV Lead), but every one came from listing-browse traffic in Property Investors \u2014 the investor-intent thesis is untested at ~$800 spend with zero conversions; CPA $661.91 and the rank-lost trend are both too early to claim.",
  "findings": [
    {
      "claim": "All 3 conversions are recorded against Panama QIV Lead (7607343274, PRIMARY) \u2014 no secondary action contamination, no double-counting",
      "severity": "high",
      "confidence": 0.99,
      "sources": [
        "Live GAQL segmented pull this turn: Jul 16 / Jul 19 / Jul 23, action_name = Panama QIV Lead, conversions = 1 each"
      ],
      "disconfirmed_by": "A future pull showing a fourth row with a different conversion_action_name \u2014 none exists in this window",
      "id": "c3-f0"
    },
    {
      "claim": "The campaign's investor-intent thesis (Investor Program + Residency Core + RBI = ~$800 spend) is unproven \u2014 zero conversions in those three groups, all 3 conversions from Property Investors listing-browse traffic",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "In-context ad group data: Property Investors 3 conv / $1,181.61; Investor Program 0 / $12.39; Residency Core 0 / $551.25; RBI 0 / $240.49",
        "Search Term Hunter: all converting queries were listing-browse / home-sale language"
      ],
      "disconfirmed_by": "Jul 26\u201328 pull showing a conversion in Investor Program or Residency Core after the RSA rewrites accumulate serving history",
      "id": "c3-f1"
    },
    {
      "claim": "CPA $661.91 is not a baseline \u2014 it rests on n=3 from a single ad group via off-thesis traffic",
      "severity": "medium",
      "confidence": 0.99,
      "sources": [
        "Pinned fact: no CPA baselines until 7 days + meaningful volume",
        "Live conversion segmentation: 3 conversions, all Property Investors, all listing-browse keyword"
      ],
      "disconfirmed_by": "Not
