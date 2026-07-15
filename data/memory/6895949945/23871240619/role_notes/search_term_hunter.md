# Search Term Hunter Notes

**Last updated:** 2026-07-14 12:12

**Task:** Cover items 3 (Keyword Efficiency), 4 (Quality Score Audit) and 5 (Search Term Quality / wasted spend %) from the KEYWORDS and SEARCH TERMS tables already in context. Map keywords into: converters (pa
**3 — Keyword Efficiency**
Two keywords produced all 4 lifetime conversions; everything else is at zero:
- **Converters:** `panama residency for americans` (QS 3, 419 clicks, 3 conv, 0.72% CVR) · `residency visa panama` (QS 5, 546 clicks, 1 conv)
- **Zero-conv spenders (clicks but nothing):** `panama residency by investment` 85 clicks · `panama tax residency` 53 · `panamanian residency` 50 · `invest in panama real estate` 43 · `panama investment property` 50 — ~280 clicks combined, $0 return
- **Dead weight (0 clicks by luck):** `best place to buy` (generic mismatch, flagged prior session, still live), `panama territorial tax`, `second residency for us citizens`
**4 — QS Audit (7 keywords below QS 5)**
| Keyword | QS | Impact |
|---|---|---|
The QS 3 on your top converter is the most expensive finding here: 419 clicks at a ~50% CPC surcharge means you've likely paid an extra ~$700+ on the keyword that produced 3 of your 4 conversions.
**5 — Search Term Quality / Wasted Spend**
Visible 7-day spend: **~$270**. Off-intent classification:
| Term(s) | Spend | Why off-intent |
|---|---|---|
**Off-intent total: ~$53 / $270 = ~20% of visible spend** going to wrong-program queries with zero chance of QIP conversion.
**Negatives to add (exact match, data-backed per account policy):**
- `[EXACT] panama golden visa`
- `[EXACT] golden visa panama`
- `[EXACT] panama visa for retirees`
- `[EXACT] friendly nation visa panama`
- **Remove keyword** `[PHRASE] best place to buy` (this is an existing keyword to delete, not a negative)
- **Pause keyword** `[PHRASE] panama passport by investment` (QS 1, 0 conv)
These 4 negatives + 2 keyword cleanups require no landing-page change, no budget touch, no learning phase risk — pure waste elimination executable today.
— *Search Term Hunter*

---

## Session Log

### 2026-07-14 12:12 — Orchestrated finding

{
  "summary": "20% of visible spend is off-intent waste eliminable with 4 exact-match negatives today; the #1 converter is paying a ~50% CPC surcharge at QS 3 that a single headline pin would fix.",
  "findings": [
    {
      "claim": "Add [EXACT] panama golden visa and [EXACT] golden visa panama as campaign negatives \u2014 $43.60 in 7 days on a product that doesn't exist; flagged twice, still un-actioned",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "search term table: 7 + 1 clicks = $43.60",
        "prior session flags May 25 + Jun 24"
      ],
      "disconfirmed_by": "If Mercan is rebranding QIP as a 'golden visa' product in its own marketing (it currently is not)",
      "id": "c2-f0"
    },
    {
      "claim": "panama residency for americans (QS 3, top converter) is overpaying ~40-50% on CPC due to ad-relevance gap \u2014 pinning it in H1 is the single highest-ROI keyword fix available",
      "severity": "high",
      "confidence": 0.82,
      "sources": [
        "keyword table: QS 3, 419 clicks, 3 conv",
        "Google QS CPC penalty curve"
      ],
      "disconfirmed_by": "If the QS 3 is driven by landing page experience rather than ad relevance (pinning the headline won't help in that case)",
      "id": "c2-f1"
    },
    {
      "claim": "~20% of visible 7-day spend ($53 of $270) hit off-intent queries for other Panama programs; 4 exact-match negatives would eliminate it",
      "severity": "medium",
      "confidence": 0.9,
      "sources": [
        "search term table: $43.60 + $4.97 + $4.95 classified against QIP program definition"
      ],
      "disconfirmed_by": "If retiree/friendly-nation searchers also have QIP intent (no conversion signal to confirm)",
      "id": "c2-f2"
    },
    {
      "claim": "Pause [PHRASE] panama passport by investment (QS 1) \u2014 wrong product frame and highest CPC penalty in the account on 0 conversions",
      "severity": "medium",
      "confidence": 0.93,
      "sources
