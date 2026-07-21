# Competitor Intel Notes

**Last updated:** 2026-07-21 13:33

**Task:** POSITION-GAP ANALYSIS from data already in context — no tool calls. Inputs: PPC Reveal spy report in the user question (Latitude 37.5% visibility / avg pos 1.9 / 119 ads / 25.2% share; Henley 18.9% / 
**Position gap: pos 2.8 vs Latitude 1.9 — three compounding causes**
1. **QS collapse on the exact auctions that matter.** `residency visa panama` QS:1 (12 advertisers), `panama investment visa` QS:1 (17), `panama qualified investor program` QS:2 (14), `panama residency by investment` QS:3 (16). Ad Rank deficit is structural at these scores — bidding harder yields no position gain. `panama permanent residency by investment` (16 advertisers): no exact match from us 
2. **Budget misallocation starves the contested auctions.** 56%+ of clicks land in Property Investors on residential intent; Investor Program (High Intent) has 3 lifetime clicks. The algorithm has minimal signal on the auctions where Latitude dominates at pos 1.9.
3. **Asset depth: 51 ads vs Latitude's 119.** Sitelink battery anchors $300K investment details at pos 1.9 — lifts CTR and Ad Rank signal simultaneously. Our 51 RSA variants leave the auction-time customization floor empty by comparison.
**(i) Non-freeze levers — executable Jul 23:**
- Rewrite RSAs for `residency visa panama` + `panama investment visa` ad groups: pin "$300,000 Investment" + "Panama Residency in ~30 Days" in H1/H2 to mirror LP h1 word-for-word. Ad relevance is the fastest single QS lever.
- Add sitelink assets: $300K investment threshold, "Free Consultation" CTA, program timeline. Zero bid risk.
- Add `[EXACT] panama permanent residency by investment` to Investor Program — 16 advertisers, zero Mercan presence, no freeze violation.
**(ii) Post-Jul-23 bid/structure:**
- Rebalance budget toward Investor Program + Residency Core after the strategist's rank-lost % confirms scale.
- Bid increase on `residency visa panama` only after QS fix lands — raising bids on QS:1 burns budget for no position gain.
*— Competitor Intel*

---

## Session Log

### 2026-07-21 13:33 — Orchestrated finding

{
  "summary": "Mercan trails Latitude by 0.9 positions primarily due to QS 1-2 on the four most contested keywords; fastest close is RSA copy alignment to LP h1 + sitelink expansion (Jul 23), with budget rebalancing post-freeze once rank-lost % is confirmed live.",
  "findings": [
    {
      "claim": "QS 1-2 on residency-visa-panama, panama-investment-visa, and panama-qualified-investor-program creates a structural Ad Rank deficit against Latitude that bidding alone cannot close",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "In-context keyword table: residency visa panama QS:1, panama investment visa QS:1, panama qualified investor program QS:2",
        "PPC Reveal: Latitude avg pos 1.9 vs Mercan 2.8 across 5 contested keywords"
      ],
      "disconfirmed_by": "Live Auction Insights showing Latitude wins on bid delta, not Ad Rank \u2014 would indicate QS is not the binding constraint",
      "id": "c2-f0"
    },
    {
      "claim": "Zero presence in the panama-permanent-residency-by-investment auction (16 advertisers) \u2014 adding [EXACT] to Investor Program is the lowest-risk gap-close executable Jul 23",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "In-context keyword table: nearest is panama permanent residency QS:3, no 'by investment' variant exists",
        "PPC Reveal: 16 advertisers contesting this keyword"
      ],
      "disconfirmed_by": "Search-terms pull showing existing phrase keywords already capturing this intent with clicks",
      "id": "c2-f1"
    },
    {
      "claim": "RSA headline alignment to LP h1 ('$300,000 Investment\u2026 in About 30 Days') is the fastest QS ad-relevance fix executable Jul 23 without violating the change freeze",
      "severity": "high",
      "confidence": 0.85,
      "sources": [
        "LIVE LANDING PAGE STATE: h1 = 'Secure Panama Residency Through a $300,000 Investment, in About 30 Days'",
        "QS:1 on two contested keywords points to ad 
