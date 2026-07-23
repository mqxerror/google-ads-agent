# Search Term Hunter Notes

**Last updated:** 2026-07-23 12:22

**Task:** Analyze the NEW search terms report (last 7 days, in context) for campaign 24036236041. Key finding to develop: the [PHRASE] 'buy property in panama' keyword (51 clicks) is pulling generic residential
**Search Term Hunter — Campaign 24036236041 | Panama QIP**
**Root cause: [PHRASE] "buy property in panama" is a residential listing magnet.** 51 of 95 total clicks trace to Property Investors, and the search terms confirm pure listing-browser intent throughout — zero QIP investor signals anywhere in the report.
**Waste quantified from actual data:**
- Pure listing browse: "homes for sale in panama city" ($11.24), "realtor international panama" ($13.61), "panama real estate" ($10.57), "property for sale in panama" ($7.74), "houses for sale" ($5.00), "homes for sale in panama" ($3.94) — ~$52 confirmed from this cluster alone
- Wrong country: "chile residency by investment" ($5.31), "canada investment visa" ($0)
- Wrong program: "panama pensionado visa" ($0), "retiring in panama" ($1.92)
- Platform searches (MLS/listing sites): "realtor international panama" ($13.61), "encuentra24 panama real estate" ($2.14)
**Structural flag:** The Property Investors keyword set itself (buy apartment/condo/beachfront + buy property/real estate in panama) will keep attracting listing traffic even after negatives — the intent bucket those words live in is residential consumer, not investor-immigration. Negatives are necessary but insufficient; keyword strategy for that ad group needs a separate review pass.
**Proposed Negative Keyword List — grounded in actual search terms only**
| Negative Keyword | Match Type | Level | Source Terms (cost) | Can appear in valid QIP query? |
|---|---|---|---|---|
**Borderline — do NOT negate yet:** "friendly nations visa panama" ($4.58, 1 click) — different Panama program but genuine immigration intent; the Friendly Nations ad group is paused, so these queries land on the QIP page. Monitor one more week; if still zero conversions, negate at ad-group level only (not campaign — the program exists in this account's portfolio).
This is a 17-negative list. Per policy: all grounded in actual reported terms, no assumption-based additions. Recommend presenting for review (this report), then executing as a single LOW-IMPACT batch.

---

## Session Log

### 2026-07-16 12:58 — Orchestrated finding

{
  "summary": "The Property Investors keyword set is generating residential listing traffic at scale; 17 data-grounded negatives should be added immediately, and the ad group's keyword strategy reviewed separately.",
  "findings": [
    {
      "claim": "Property Investors ad group's keyword set structurally attracts residential listing traffic \u2014 negatives alone will not fix this without a keyword strategy revision for that ad group",
      "severity": "high",
      "confidence": 0.92,
      "sources": [
        "[PHRASE] buy property in panama = 51 clicks driving listing-browse queries",
        "search terms report: 'homes for sale', 'condos for sale', 'houses for sale', 'realtor international panama' all matching through this keyword"
      ],
      "disconfirmed_by": "If post-negative search terms show the same keyword generating QIP-intent queries (e.g., 'panama property investment visa'), the keyword is salvageable with negatives alone",
      "id": "c2-f0"
    },
    {
      "claim": "Add 17 negative keywords (PHRASE/EXACT) at campaign level to cut confirmed listing-browse and wrong-country waste \u2014 estimated ~$52+ in documented wasted spend over 3 days",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "Search terms report: 'homes for sale in panama city' $11.24, 'realtor international panama' $13.61, 'panama real estate' $10.57, 'chile residency by investment' $5.31, 'property for sale in panama' $7.74"
      ],
      "disconfirmed_by": "If any listed negative appears in a high-converting QIP query in a future search terms pull \u2014 no such evidence exists in current data",
      "id": "c2-f1"
    },
    {
      "claim": "QIP investor-specific queries are nearly absent from the search terms report \u2014 the campaign is not yet reaching its intended audience",
      "severity": "high",
      "confidence": 0.88,
      "sources": [
        "Search terms report top 40: only 'investor visa' (0 clicks), 'friendly nations

### 2026-07-16 13:01 — Analyze the NEW search terms report (last 7 days, in context) for campaign 24036

**Task:** Analyze the NEW search terms report (last 7 days, in context) for campaign 24036236041 ONLY — do NOT redo the performance report; the PPC Strategist's Jul 14–16 report (95 clicks / $471.66 / 0 conv, C

**Critical Details:** GTM-injected
**Citing PPC Strategist's Jul 14–16 report on file** (95 clicks / $471.66 / 0 conv / CPC +40% / Property Investors = 56% of spend — not re-reported here).
**Intent buckets + waste (40 visible terms / $103.07 visible spend):**
- **Real-estate listing browse + portals — $87.32:** `realtor international panama` $13.61 · `homes for sale in panama city panama` $11.24 · `panama real estate` $10.57 · `panama homes for sale` $9.25 · `property for sale in panama` $7.74 · `panama city RE` $5.04+$3.60 · `houses for sale in panama` $5.00 · `homes in panama for sale` $4.78 · `panama RE for sale` $3.81 · `condos for sale in panama c
- **Other-country — $5.31:** `chile residency by investment` $5.31
- **Retiree/pensionado — $1.92:** `retiring in panama` — **KEEP**, borderline (wealthy US retiree = plausible $300K QIP prospect)
- **QIP/immigration intent — $4.58:** `friendly nations visa panama` **KEEP** · `investor visa` / `golden visa` / `panama residency requirements` **KEEP** (all $0 or ADDED)
**Waste rate: $92.63 / $103.07 = 90% of visible spend.**
**Root-cause verdict — yes, the keyword itself is the structural problem.** `[PHRASE] buy property in panama` (51 clicks, Property Investors ad group, est. ~$233 of the group's $265.75) is not being betrayed by bad luck — 2026 phrase match semantically equates "buy property in panama" with "homes for sale in panama city," "realtor international panama," and every listing-browse variant in the visi
**Negative keyword list — report-sourced only, campaign level:**
| Negative | Match | Reason | Can appear in valid QIP query? |
|---|---|---|---|
| `homes for sale` | PHRASE | Listing-browse intent in any context | No |
| `houses for sale` | PHRASE | Listing-browse | No |
| `condos for sale` | PHRASE | Listing-browse | No |
| `realtor` | PHRASE | Portal navigation, not immigration | No |
| `pensionado` | PHRASE | Different Panama program (Pensionado Visa), DIY tone | No — QIP copy never uses this term |
| `boquete` | PHRASE | Retirement/expat mountain town, not QIP target zone | No |
| `coronado` | PHRASE | Expat beach retirement community | No |
| `pedasi` | PHRASE | Retirement beach town | No |
| `el valle` | PHRASE | Retirement hill town | No |
| `panama pacifico` | PHRASE | Expat community area, not investment-visa context | No |
| `chile` | PHRASE | Wrong country; no valid QIP query includes "chile" | No |
**→ 20 negatives, all LOW-impact, all grounded in actual reported terms. Ready to execute as a single batch and notify.**
**Terms to KEEP — do not negate:**
- `friendly nations visa panama` ($4.58) — genuine immigration intent; different Panama program but in the portfolio; monitor 1 week
- `panama residency requirements` ($0, ADDED) — residency intent, on-program
- `investor visa` ($0) — on-program
- `golden visa` ($0) — on-program
- `retiring in panama` ($1.92) — borderline; a wealthy American retiree with $300K is a plausible QIP buyer; watch one more week before negating
- `best place to buy real estate in panama` ($2.83, ADDED) — borderline; re-evaluate at next 7-day pull
**Pinned-fact respected:** campaign is 2 days old, 0 conversions — zero bid/budget/strategy changes proposed.
*— Search Term Hunter*

### 2026-07-16 13:02 — Orchestrated finding

{
  "summary": "90% of visible spend ($92.63/$103.07) is buying Panama home-shoppers, portals, and wrong-country visitors \u2014 root cause is [PHRASE] buy property in panama; 20 negatives ready as LOW batch (execute-and-notify), keyword pause/replace needs MEDIUM approval, and conversion tracking verification is the highest-priority unblocked action.",
  "findings": [
    {
      "claim": "Conversion tracking must be verified before interpreting 0 conversions as a traffic or bidding problem \u2014 no Panama-specific primary conversion action confirmed in registry, and LP static fetch returned no form signal and no tracking token",
      "severity": "high",
      "confidence": 0.75,
      "sources": [
        "Conversion registry lists PT GV, Greece GV, EB3 Brazil \u2014 no Panama QIP primary WEBPAGE action; live fetch of mercan.com/lp/panama-qualified-investor-program HTTP 200 but form signal: none detected, tracking token: none detected (static fetch cannot pierce JS-rendered or GTM-injected content)"
      ],
      "disconfirmed_by": "Live browser render confirms form visible and GV Lead tag firing on submit \u2014 at which point 0 conv at 95 clicks is statistically normal for a 3-day $300K-product campaign",
      "id": "c1-f0"
    },
    {
      "claim": "Pause [PHRASE] 'buy property in panama' (51 clicks / est. ~$233) and replace with [EXACT] or investment-intent phrase alternatives \u2014 negatives alone do not fix 2026 phrase-match semantic expansion to listing-browse queries",
      "severity": "medium",
      "confidence": 0.88,
      "sources": [
        "51 of 95 total clicks in Property Investors ad group; all visible search terms from this keyword show residential listing-browse intent with zero QIP investor signals; 2026 phrase match confirmed to expand 'buy property in panama' to home-shopping variants"
      ],
      "disconfirmed_by": "7-day post-negatives search terms pull shows <5% listing-browse queries remaining under this keyword \u2014 would

### 2026-07-22 16:34 — POST-NEGATIVE SEARCH-TERMS VERDICT from the in-context last-7-days table (top 40

**Task:** POST-NEGATIVE SEARCH-TERMS VERDICT from the in-context last-7-days table (top 40, as of Jul 22) — NO tool calls. Cite your Jul 16 pre-negative analysis (90% waste rate, $92.63 of $103.07 visible spend
**Post-Negative Verdict | Jul 22** *(Jul 16 analysis: 90% waste, $92.63/$103.07, root cause `[PHRASE] buy property in panama` — cited, not redone)*
**1. Waste rate: ~80% — phrase batch never landed**
Only 4 EXACT negatives blocked ($14.59 covered). Listing-browse regrew around them with brand-new variants: `real estate panama city panama` $34.95, `real estate in panama city panama` $15.72, `casa solution real estate panama` $10.86, `land for sale in panama` $8.94, `buying property in panama` $7.51, `houses in panama` $7.26, `houses for sale in panama` $5.00 — all NONE. `houses for sale` phrase
Buckets from ~$231 visible: listing-browse NONE ~$155 · wrong-program NONE (eb5an $22.64 + FNV $5K tier $8.60) ~$31 · on-program ADDED ~$33 · EXCLUDED $15. Active waste: ~$186/$217 active = **~86%** — structural, not cleaned.
**2. Verdict: EXACT gate triggered**
Listing-browse dominates the NONE column. `[PHRASE] buy property in panama` → `[EXACT]` now. Replacements: `[EXACT] buy property panama investment`, `[PHRASE] invest in panama real estate`.
**3. Negative batch (approval required — all from reported terms):**
- `[eb5an]` EXACT · campaign — EB-5 portal, zero QIP overlap
- `[$5000]` PHRASE · campaign — FNV tier only; never in $300K QIP context
- `[casa solutions]` + `[casa solution]` PHRASE · campaign — real estate agency; no QIP overlap
- `[viviun]` EXACT · campaign — listing portal
- `[panama home realty]` PHRASE · campaign — realty brand
- `[land for sale]` PHRASE · campaign — consumer real estate only
- `[real estate in panama city panama]` EXACT · campaign — surgical; blocks $15.72
- `[real estate panama city panama]` EXACT · campaign — biggest single waste term $34.95
**4. No-leads tie-in:** 0 conv since Jul 19 = 3 days, $629 spent. >80% of active visible spend is residential buyers. Maximize Conversions is bidding into irrelevant traffic with zero signal. The phrase batch not landing is the proximate cause — keyword move + this batch together are the fix.
*All items need your approval before any write. — Search Term Hunter*

### 2026-07-22 16:35 — Orchestrated finding

{
  "summary": "Phrase negatives never landed; listing-browse tail regrew to ~86% waste; move [PHRASE] buy property in panama to [EXACT] and push 8-negative batch \u2014 both need approval before write.",
  "findings": [
    {
      "claim": "Move [PHRASE] buy property in panama to [EXACT] immediately \u2014 listing-browse dominates the NONE column, Jul 21 gate condition met",
      "severity": "high",
      "confidence": 0.92,
      "sources": [
        "Post-negative search terms Jul 22: listing-browse NONE ~$155 of ~$217 active visible spend",
        "Jul 21 gate: if listing-browse >60% of terms, move to exact match"
      ],
      "disconfirmed_by": "Post-exact-match pull showing investment-intent queries were coming through the phrase match and are now blocked",
      "id": "c2-f0"
    },
    {
      "claim": "Phrase negative batch from Jul 16 never landed \u2014 houses for sale, buying property, houses in panama all NONE \u2014 waste rate fell only from 90% to ~86%, not materially lower",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "houses for sale in panama ($5.00), buying property in panama ($7.51), houses in panama ($7.26) all show NONE status despite Jul 16 phrase-negative recommendation"
      ],
      "disconfirmed_by": "Confirmation that phrase negatives were pushed but new query variants outpaced them \u2014 would change the diagnosis to structural keyword issue only, not a missing batch",
      "id": "c2-f1"
    },
    {
      "claim": "eb5an ($22.64 NONE) is the largest new single-term waste \u2014 EXACT campaign negative, zero QIP overlap",
      "severity": "high",
      "confidence": 0.98,
      "sources": [
        "EB5An is an EB-5 investment visa marketplace \u2014 different program, different country, different investment structure"
      ],
      "disconfirmed_by": "Nothing \u2014 EB-5 and Panama QIP share no searcher intent",
      "id": "c2-f2"
    },
    {
      "claim": "0 conversions since Jul 19 is a d

### 2026-07-22 17:10 — whats the plan than for the improvement ? also what are the phrase match keyword

**Task:** whats the plan than for the improvement ? also what are the phrase match keywords , also get me the traffic for the exact match keyword
Three asks — the improvement plan, the full phrase-match keyword list, and live traffic for the exact-match keyword. The plan and most of the keyword list are already on file from this session; the exact keyword's impressions aren't in context (context shows clicks only), so I'll run one live GAQL pull to get true traffic per keyword plus the full 33-keyword list. Loading the working query tool fi
## 1. The improvement plan — already sequenced, waiting on your "go"
Nothing new to invent; the plan is locked from this session's diagnosis (79.2% of impressions lost to Ad Rank, ~86% of spend on house-shoppers, CPA $844.53). One change type per day:
| Day | Move | What it fixes |
|---|---|---|
The only thing blocking step 1 is your approval on the negatives.
## 2. The phrase match keywords — all 32, live pull this turn
The campaign has **33 keywords total: 32 PHRASE + 1 EXACT**. Full phrase list by ad group (impressions/clicks/cost = Jul 14–22 live):
**Property Investors — 11 phrase keywords, $995.68, the problem group**
| Keyword | Impr | Clicks | Cost |
|---|---|---|---|
**Residency Core (Converters) — 8:** panama residency (358 impr / 25 clicks / $168.30) · panama residency program (180 / 22 / $187.54) · residency visa panama (106 / 9 / $37.55) · panama residency for americans (66 / 6 / $61.07) · panama residency requirements (47 / 8 / $22.58) · how to get residency in panama (19 / 2 / $8.01) · panama permanent residency (7 / 0 / $0) · panama residency visa (4 / 
**RBI Category — 5:** residence by investment (380 / 13 / **$177.47 — CPC $13.65, CTR 3.4%**) · residency by investment countries (153 / 3 / $21.64) · residency by investment programs (18 / 3 / $17.13) · cheapest residency by investment (5 / 0 / $0) · permanent residency by investment (0 impressions)
**Investor Program (High Intent) — 4 phrase:** panama residency by investment (33 / 2 / $8.20) · panama investment visa (14 / 0 / $0) · panama golden visa (13 / 1 / $4.19) · **panama permanent residency by investment (0 impressions — see below)**
**Friendly Nations Visa (paused group) — 4:** panama friendly nations visa · friendly nations visa · panama friendly nations visa requirements · friendly nations visa panama requirements (2 impr / $0 total)
Three things this pull surfaces that weren't visible before:
- **`[PHRASE] panama permanent residency by investment` already exists** in Investor Program — with **zero impressions lifetime**. The Jul 21 recommendation to add the `[EXACT]` stands, and the phrase's total absence from a 16-advertiser auction is the Ad Rank blockade in its purest form: we own the keyword and Google won't enter us at all.
- **`residence by investment` is the RBI group's quiet bleeder** — $177.47 at $13.65/click (the campaign's most expensive CPC) and 3.4% CTR. This generic term is almost certainly what matched `eb5an` ($22.64), `chile residency by investment`, and `citizenship by investment`. Today's negative batch covers the worst of it; if the Jul 26+ pull still shows off-program matches, this keyword goes on the
- **`cheapest residency by investment` should come out on Jul 24.** It only has 5 impressions, but it's a targeted invitation to budget-seekers — the exact audience this account structurally excludes, and the exact frame Henley's $100K undercut wins. Removing it costs nothing.
## 3. Traffic for the exact match keyword — effectively none
**`[EXACT] panama qualified investor program`** (Investor Program group, QS 3), live Jul 14–22:
- **20 impressions · 0 clicks · $0.00 · 0 conversions** — about 2 impressions per day, and not one click in nine days.
This is the program's own name, contested by 14 advertisers per the spy report, and we're near-invisible in it. The ad group's live numbers explain why: impression share **34.9%**, with **51.7% lost to rank**. When we do show, we're low on the page under Latitude's sitelink-loaded ads — 20 low-position impressions with zero clicks is what that looks like. This is not a bid or budget issue; it's th
**Bottom line from the terms desk:** the keyword architecture is 32 nets and 1 spear, the nets are catching house-shoppers, and the spear isn't being thrown. Today's negatives shrink the nets, Jul 23's copy sharpens the spear, Jul 24 re-rigs the worst net to exact. Say **"go"** on the negative batch and today's step executes.
*— Search Term Hunter*

### 2026-07-22 17:18 — before the go for today negatives, what about if we switch all keywords to exact

**Task:** before the go for today negatives, what about if we switch all keywords to exact match and double budget so we get more traffic and clean faster by next week i need to report back to the ceo regarding
**Verdict from the terms desk: don't do it — both halves of that move would backfire, and the combination would hand you a *worse* CEO report next week, not a better one.** All numbers below are from this session's live pulls; no new fetch needed.
## Why "all exact match" cuts traffic instead of cleaning it
Exact match doesn't clean your traffic — it shrinks your eligibility to almost nothing, because the campaign's volume lives in phrase expansion:
- Campaign total, Jul 14–22: **~3,309 impressions**. Of those, `[PHRASE] buy property in panama` alone is **1,617 (49%)**.
- We already own one exact keyword — `[EXACT] panama qualified investor program` — and its 9-day total is **20 impressions, 0 clicks, $0**. That's what exact match looks like at QS 3 in a 79%-rank-lost campaign.
- The high-intent keywords that would become your exact spears are the worst-scored in the account: `panama investment visa` QS 1 (14 impressions *as phrase*), `panama golden visa` QS 1 (13), `panama residency by investment` QS 1 (33). As exact, these serve **less**, not more — exact match enters you into precisely the auctions Google is currently refusing to rank you in. Match type doesn't touch 
Realistic outcome of flipping all 32: impressions drop roughly 70–85% overnight, the two-conversion keyword's history resets (new criterion IDs = fresh QS calculation), and Maximize Conversions — sitting on n=2 — loses most of its remaining signal a week before your report.
## Why doubling budget adds ~nothing right now
Jul 22 live split: **rank-lost 79.2%, budget-lost 0.6%**. Budget buys back only budget-lost auctions. Doubling to $400 purchases at most ~0.6 points of impression share — and if you go all-exact at the same time, the campaign can't even spend the $200 it has (far fewer eligible auctions). You'd be paying for a bigger pipe into a valve that's closed.
## The trap in doing both at once
Two change types on the same day means next week you *cannot tell the CEO what worked*. If results improve, was it match types or money? If they crater (likely), which do you roll back? The one-change-per-day rule exists exactly for the week you have to stand behind the numbers.
## What actually gets you a CEO-ready improvement story by next week
Your instinct — "exact match cleans the traffic" — is right about **one keyword**, and that's already in the plan. The dirt is not spread across 32 keywords: the on-program terms (`panama residency requirements`, `panama residency`, etc.) are matching cleanly (~$33 of ADDED/on-program spend, no junk). The waste is concentrated in Property Investors, overwhelmingly through `buy property in panama`.
| Day | Move | What you report to the CEO |
|---|---|---|
By the CEO meeting you can show: waste rate falling from 86%, rank-lost trending down from 79%, sitelinks + rewritten ads live, and budget doubled the moment it could buy real impressions. That's a genuine improvement narrative with a cause-and-effect chain you can defend. "We flipped everything to exact and doubled spend, impressions fell 80%, CPA is frozen at $844" is the opposite of that meetin
The negatives are still today's unlocked move and the clock is running — say **"go"** and the batch executes now.
*— Search Term Hunter*

### 2026-07-23 11:05 — POST-BATCH EARLY READ for campaign 24036236041 (customer 7178239091) ONLY. Use s

**Task:** POST-BATCH EARLY READ for campaign 24036236041 (customer 7178239091) ONLY. Use search_execute_query verbatim. Yesterday ~17:24 you executed 24 negatives (15 re-pushed Jul 16 phrase: homes/houses/house
Running a date-scoped search terms query (Jul 22–23 only, post-batch window) now.Good, tool is loaded. Running the date-scoped pull now.**POST-BATCH EARLY READ | Jul 22–23 | Live pull this turn** *(~22h post-write)*
**(a) Blocks confirmed — but tail is leaking.** EXCLUDED: `real estate panama city panama` ($1.64 residual, pre-propagation clicks) · `eb5an` ($0). The big pre-batch terms are gone from the NONE column. However `buy property in panama` (phrase) is generating variants the negatives don't cover — all NONE:
- `albrook panama real estate` $8.13 — no "real estate" phrase negative
- `land in panama for sale` $7.67 — phrase neg "land for sale" ≠ "land **in** panama for sale" (word order mismatch)
- `homes in panama city panama` $6.86 — no "for sale" in the query, phrase neg misses
- `volcan panama real estate for sale` $6.02 — geo-specific variant
- `realty panama` $3.20 — ≠ "realtor"
- `purchasing property in panama` $3.12 — ≠ "buying property"
- `boca del toro real estate` $2.18 — geo variant
**(b) Waste rate: ~$48/$56 visible ≈ ~86% — directionally unchanged** (citing Jul 22 verdict, not redone). Phrase negatives hit their specific targets; the keyword regenerates the tail with new geographic/modifier forms. Caveat: 22-hour window, very small sample — directional read only.
**(c) Third conversion appeared.** `panama home for sale` (NONE, $2.89, 1 conv) converted in this window — Property Investors now at 3 total conversions. Echoes the Jul 16 and Jul 19 pattern: QIP buyers occasionally surface via home-sale language. Doesn't reverse the move-to-EXACT verdict, but directional CPA has improved.
**RBI Category flag:** 14 wrong-country impressions visible (bahamas, bermuda, caribbean, comoros, el salvador, jordan, paraguay, trinidad, vanuatu) via `residence by investment` phrase — no clicks, but QS noise.
**Proposals only — no writes today (RSAs + sitelinks own the slot):**
- `[real estate]` EXACT campaign negative → kills the neighborhood real-estate tail systematically
- `"affordable"` PHRASE → budget-seeker signal (`affordable homes in panama` appeared)
- Country PHRASE negs for RBI noise: bahamas, bermuda, caribbean, comoros, el salvador, jordan, paraguay, trinidad, vanuatu
*— Search Term Hunter*

### 2026-07-23 11:05 — Orchestrated finding

{
  "summary": "24 negatives are partially working \u2014 the exact blocks confirmed, phrase blocks hit their targets \u2014 but [PHRASE] buy property in panama keeps generating geographic/modifier tails at ~86% waste; a third conversion appeared (listing-browse query, Property Investors); [real estate] EXACT is the next surgical fix, proposed for Jul 25.",
  "findings": [
    {
      "claim": "Listing-browse waste rate is ~86% post-batch \u2014 directionally unchanged \u2014 because [PHRASE] buy property in panama generates geographic/modifier variants (albrook, volcan, boca del toro) that phrase negatives structurally cannot block",
      "severity": "high",
      "confidence": 0.78,
      "sources": [
        "Live Jul 22\u201323 pull: ~$48/$56 visible spend in NONE listing-browse terms",
        "Jul 22 pre-batch baseline: ~86% waste rate (Search Term Hunter verdict, cited)"
      ],
      "disconfirmed_by": "Jul 25 pull showing listing-browse NONE spend below 40% of visible total \u2014 would indicate the phrase negatives + exact-match move together cleaned the tail",
      "id": "c2-f0"
    },
    {
      "claim": "The phrase negative 'land for sale' has a word-order gap \u2014 it does not block 'land in panama for sale' ($7.67 NONE), requiring either an additional phrase negative or the keyword moving to exact to prevent this variant",
      "severity": "medium",
      "confidence": 0.95,
      "sources": [
        "Live Jul 22\u201323 pull: 'land in panama for sale' $7.67 NONE despite 'land for sale' phrase negative being ENABLED"
      ],
      "disconfirmed_by": "Nothing structural \u2014 phrase match requires contiguous word order; 'land in panama for sale' cannot match 'land for sale' as a phrase negative",
      "id": "c2-f1"
    },
    {
      "claim": "A third conversion appeared on 'panama home for sale' ($2.89) \u2014 Property Investors now has 3 conversions total, improving directional CPA, but the converting query is still listing-browse intent",

### 2026-07-23 11:36 — since panama home for sale brought a conversion why we dont add it as exact matc

**Task:** since panama home for sale brought a conversion why we dont add it as exact match ? also why not cut the leak and make the buy property in panama to exact ? also i started a new spy report since yeste
Three asks on the desk: the converting query as a new exact keyword, pulling the exact-match flip forward, and the two new spy CSVs in Downloads. The first two I can answer from this session's data; the CSVs I need to go read. Doing that first.Both CSVs read — new spy window (started Jul 22, so it's a post-negative snapshot) across 5 tracked high-intent keywords in NY/NJ/WA/AL/FL. Here's the full 
**TLDR: Yes to `[EXACT] panama home for sale` — but tomorrow, in the keyword slot, alongside the exact-match flip you're asking about. Both belong to Jul 24 because today's change slot is the RSA + sitelink package, which is still waiting on your "go" — and the new spy report you just pulled is the strongest argument yet for firing it: Latitude is now running 66 keyword-mirrored ad variants at pos
## 1. `panama home for sale` as exact match — yes, and here's the interesting part
That query converted this morning at **$2.89** — and it only reached us through a gap in our own wall: yesterday's batch includes the phrase negative `"homes for sale"` (plural), and **Google negatives don't stem** — plural "homes" does not block singular "home". The converting query slipped through on a word form. That accident is now worth formalizing:
- **Add `[EXACT] panama home for sale`** to Property Investors. All 3 conversions have arrived via home-sale phrasing — this keeps the one proven lane open with zero sprawl risk, because exact match can't expand into "albrook panama real estate" the way the phrase net does.
- Exact, never phrase — a phrase version would rebuild the exact tail we're killing.
- At write time I'll read back the negative list to confirm no collision: none of the live EXACT negatives is the singular form, so it's servable. And the standing rule from here: **never add a singular `"home for sale"` negative**, or we block our own keyword.
- Honest caveat: n=1 on this query. It's a cheap lane-keeper, not a strategy change.
## 2. Why the `buy property in panama` → EXACT flip waits ~18 hours
Not bureaucracy — sequencing economics:
- **One change type per day** (your own account rule). Today = ad-side (RSAs + sitelinks). Tomorrow = keyword-side (the flip + the new exacts + dropping `cheapest residency by investment`). Stack them and next week's CEO report can't attribute which move bent the curve.
- **Rank-lost 65.8% is the bigger bleed.** The phrase tail leaked ~$48 in the last 22 hours — call it ~$50/day. Rank-lost is costing you roughly two-thirds of all eligible impressions on the auctions that matter. If either move gets priority today, it's the one attacking the 65%, not the $50.
- **The flip cuts ~49% of campaign impressions overnight** (1,617 of 3,309 lifetime came through that phrase). You want the rewritten RSAs live and accumulating expected-CTR history *before* you shrink the traffic pool, not after.
That said — the slots are swappable if you insist: keyword flip today, RSAs tomorrow is legal under the one-change rule. My recommendation stays RSAs first, for the three reasons above. Either way, **nothing fires until your "go" — the RSA + sitelink package has been staged since this morning and is still waiting.**
## 3. The new spy report — read, both files
**Advertisers table (new window, Jul 22→23) vs your Jul 15 export:**
|---|---|---|---|---|---|
Five findings that matter:
1. **The ad-depth gap is now the visible face of your rank-lost problem.** PPC Reveal counts rendered RSA combinations — Latitude's 66 "ads" are one rich RSA battery rotating keyword-mirrored headline pairs ("Panama Golden Visa $300K | Panama Qualified Investor", "Minimal Stay Requirement", "Family Included") plus assets (Case Studies, Chat Support, Expert Available) on every tracked keyword. Our 
2. **Where we DO get entered, we win.** Our "Qualified Investor Program | $300K Investment Program" ad is the **single highest-visibility ad row in the entire report (6.4)** on `panama qualified investor program` — ahead of Latitude's best (5.4). The ad is good; Google just isn't entering it into enough auctions. That's a clean CEO line: quality of entry is proven, frequency of entry is the fix in
3. **goldenvisas.com is the one to watch.** From nothing to #2 visibility (38.9%, statistically tied with us) in a week, leading with "Launched 2026 / Newly launched" novelty and a "Do You Qualify?" CTA. We never use qualify language (account rule — no screening tool exists); our counter is already in our copy: "Trusted for over 37 Years" vs. a firm that launched this year. Worth a dedicated Compe
4. **Competitors are making claims we're banned from mirroring.** Latitude: "Minimal Stay Requirement" / "flexible stay rules". glppanamaresidency: "No minimum stay" — which for Panama QIP is false per your standing correction (it's **1 visit every 2 years**). Our truthful version is already pinned in the Creative package. Don't copy theirs.
5. **panamags/NDM/Matapitti are flooding `residency visa panama` with retiree/pensionado attorney ads** — that keyword's auction is getting noisier with off-program intent, consistent with the pensionado-flavored queries we've been negating. No action needed; the negatives already wall that off on our side.
Net: the spy data changes nothing in the plan and validates all of it — the RSA mirroring, the sitelinks, and the `[EXACT] panama permanent residency by investment` add (Latitude runs ~10 variants on that keyword; we captured one ad on it).
**On the table now:** say **"go"** and the Jul 23 slot executes — RSAs + 6 sitelinks into the cleanest traffic this campaign has had. Tomorrow's keyword batch is then: flip `buy property in panama` to EXACT, add `[EXACT] panama home for sale` + `[EXACT] buy property panama investment` + `[EXACT] panama permanent residency by investment`, remove `cheapest residency by investment`.
*— Search Term Hunter*

### 2026-07-23 12:08 — for today execute the sitelinks and callouts and make the add better and bigger 

**Task:** for today execute the sitelinks and callouts and make the add better and bigger , today we change the keyword to exact match also to mention the ppcreveal is a screenshot in google every hopurs so lik
Wassim's given the go on both slots for today — ad-side (sitelinks, callouts, bigger keyword-mirrored RSAs) plus the keyword flip to exact. Executing now: loading the write tools first, then criterion IDs, then the writes with read-back verification.Write tools loaded. Now loading the keyword-add tool and pulling the criterion IDs + negative-list collision check in parallel.All 4 EXACTs are in. No
## 1. Keyword batch — all verified in the post-write pull
| Change | Where | Status |
|---|---|---|
| `[EXACT] buy property panama investment` added | Property Investors | ENABLED ✓ |
I paused rather than removed the phrase keywords — fully reversible if we ever want the net back.
## 2. The ads — bigger, and live in all 4 enabled ad groups
Each group got a new 15-headline / 4-description RSA (vs the ~thin originals), ENABLED alongside the existing proven ad — the old top-visibility "Qualified Investor Program" ad keeps serving while the new ones build history. Keyword-mirrored lead headlines per group: **"Buy Property in Panama"** (Property Investors), **"Panama Residency Program" / "Panama Residency for Americans"** (Residency Core
New ad IDs: 818022513810, 818022521508, 818134449086, 818134468214 — read-back shows all ENABLED with approval status "UNKNOWN," which just means they're minutes old and in Google's standard policy review (typically clears within hours). Two honest notes: the MCP create tool doesn't support headline pinning, so the H1/H2 pins from the Creative spec aren't set — relevance comes from the mirrored ph
## 3. Sitelinks + callouts — 12 new assets linked, all ENABLED
**Sitelinks (6):** $300K Investment Details · How Panama QIP Works · 30-Day Processing · Free Consultation · Compare Programs · Why Mercan — each with two description lines, pointing at LP anchor sections. **Callouts (6):** Trusted for 37+ Years · Licensed Advisors · 1 Visit Every 2 Years · $300K Official Program · Family Included · Fast 30-Day Processing.
The read-back surfaced something useful: the campaign **already had 4 sitelinks** ("Business Immigration", "How the QIP Works", "Book a Consultation", "About Mercan Group") that never showed in the spy data. No text collisions with the new six, so the campaign now carries 10 sitelinks + 6 callouts — Google rotates the best 4 sitelinks per impression. This is the direct answer to Latitude's asset b
## 4. On PPC Reveal — you're correct, and it changes how we read it
Yes: it screenshots the live SERP roughly hourly per tracked keyword/location — ~24 samples a day. That means (a) its "66 ads" for Latitude is really *rendered RSA combinations across snapshots* — a big rotation gets counted as many "ads," which inflates the gap versus our count; (b) visibility % is share-of-snapshots, not share-of-auctions, and it misses everything between snapshots; (c) it can't
## What to watch now
- **Impressions will drop and spend may underpace for a few days** — the paused phrase was ~49% of lifetime impressions. That's the design, not a problem: what remains is investor-intent traffic plus the proven home-sale lane via the new exacts.
- Both change types landed today (your call, logged) — so **Jul 24 is a clean observation day, nothing scheduled**. The CEO story is now "cleaned traffic + rebuilt ads on the same day, then measured."
- **The $400 budget trigger is unchanged**: rank-lost sustainably below ~50% on the Jul 26–28 read. With the junk auctions gone and richer ads in review, that's the number I'm watching.
*— Search Term Hunter*

### 2026-07-23 12:22 — enable the [PHRASE] buy property in panama (351567246136). isaid we do it tomorr

**Task:** enable the [PHRASE] buy property in panama (351567246136). isaid we do it tomorrow but keep both also the exact match
Wassim wants the phrase keyword back on today alongside the new exact — reversing the pause I made, with the flip decision moved to tomorrow. Executing now: loading the keyword-status write tool, then enabling criterion 351567246136, then verifying with a read-back.**Done — `[PHRASE] buy property in panama` (351567246136) is back to ENABLED, verified with a live read-back.** The pause is reversed 
Post-write state in Property Investors (all live this turn):
| Keyword | Criterion | Status |
|---|---|---|
`[PHRASE] cheapest residency by investment` stays paused — you didn't ask for that one back, and it has no defenders on this desk.
Two things worth knowing about running both:
1. **No self-competition on the core query.** When someone types exactly "buy property in panama", Google serves the EXACT keyword — identical-text exact match takes priority over phrase. The phrase only picks up the variants ("buying property in panama city", "where to buy property in panama", etc.). So the exact's fresh history builds cleanly either way.
2. **The variant tail is open again.** That's the trade-off you're accepting for today: the ~$50/day leak lane (albrook/volcan/realty-style variants) is live until the phrase is paused again or more negatives land. The 63 negatives stay in force, so the worst of it remains blocked — this is the residual tail, not the pre-batch firehose.
For tomorrow's keyword slot, the decision is now genuinely yours with a day of data behind it: if the phrase's Jul 23–24 search terms are still listing-browse junk, we pause it again (the original flip, one day later); if you want to keep both longer, we let the terms report arbitrate. Nothing fires without your word — I'll bring the phrase-only search-terms read tomorrow so the call is made on ev
Everything else from today's package is untouched: 4 new RSAs in review, 10 sitelinks + 6 callouts live, $400 budget trigger still waiting on rank-lost < ~50%.
*— Search Term Hunter*
