# Search Term Hunter Notes

**Last updated:** 2026-07-16 13:02

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
