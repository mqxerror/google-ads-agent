# Panama QIP — US Buyer-Intent Keyword Angles

**Date:** 2026-07-15 · **Research only — no campaign mutations.**
**Sources:** Google Keyword Planner v23 (`GenerateKeywordIdeas` ×3 seed calls → 2,116 idea rows; `GenerateKeywordHistoricalMetrics` → 97 canonical rows, US geo 2840 / EN 1000 / Google Search only) + DataForSEO (3 US SERPs + 7 competitor domains × 700 ranked keywords, $0.68 total spend).
**Raw/processed data:** `data/panama-us-angles-kwp.json` (processed) · `panama-us-angles-kwp-ideas-raw.json` · `panama-us-angles-kwp-hist-raw.json` · `panama-us-dfs-serp-raw.json` · `panama-us-dfs-ranked-raw.json`.
**Live campaign context:** "Panama QIP — US — Search — v2" (24036236041) — 6 keywords, losing 57.5% IS to rank.

**Methodology notes (honesty flags):**
- KWP folds close variants into shared stats. Rows with identical (volume, bids, competition) are ONE demand pool counted once — e.g. "homes for sale in panama" / "houses for sale in panama" / "buy house in panama" = one ~6,600/mo pool, not 19,800.
- `panama qualified investor program` / `... visa` report **0 in KWP** (below reporting threshold). The v2 campaign's real impressions prove the demand exists but it is micro-volume. Marked `<10` below.
- **Florida pollution:** for US searchers, generic "panama homes/houses/real estate" queries mix in Panama City Beach, FL demand (DFS shows 9,900–18,100/mo pure-FL terms nearby). Any property ad group needs FL negatives and should prefer country-scoped phrasing.
- All volumes = 12-month US averages, Google Search only. No fabricated numbers; blanks marked.

---

## 1. Angle clusters, ranked by buyer-intent × volume

Buyer-intent score: 5 = capital-holder actively evaluating a purchase route → 1 = curiosity research.

### #1 · Panama program / residency core — score 5 · ~2,390/mo (usable-for-bidding ≈1,670)
The only cluster where the searcher already chose Panama. Owns the LP promise 1:1.

| Keyword | US vol/mo | Comp | Top-of-page bid |
|---|---|---|---|
| panama visa for us citizens | 720 | LOW | $0.07–2.00 — **travel-polluted, exclude** |
| panama residency requirements | 320 | MED | $0.71–2.50 |
| panama residency | 260 | MED | $0.87–2.70 |
| panama golden visa | 210 | MED | $1.74–6.00 |
| panama immigration lawyers (+ lawyer 70) | 280 | MED | $2.93–8.80 — service-seeker, Wassim's call |
| panama permanent residency | 170 | MED | $0.93–2.83 |
| panama residency visa / residency visa panama (pool) | 90 | MED | $0.80–2.50 |
| how to get residency in panama | 90 | MED | $1.06–3.25 |
| panama residency by investment program | 70 | LOW | $5.81–10.96 |
| panama residency by investment | 50 | MED | $2.44–6.00 |
| immigrate to panama from us | 50 | MED | $0.53–2.50 |
| panama investment visa | 40 | HIGH | $1.77–6.00 |
| panama residency program / cost / permanent residency by investment | 20+10+10 | — | — |
| panama qualified investor program / visa / investor visa / for americans | **<10 each** | — | KWP below threshold; real (v2 serves them) |

Competitors ranking here organically: henleyglobal (#5 panama residency), kraemerlaw (everything), goldenvisas.com, panamasovereign. **mercan.com already ranks #4–6 on all three head terms** (panama residency by investment / qualified investor visa / golden visa).
Policy: SAFE.

### #2 · Property + residency bridge — score 4 · ~16,360/mo total, buyer-subset ≈1,720
Greece's money-cluster analog. The capital-holder signal ("buy", "invest") lives in the subset; the big for-sale pools are browse-heavy and FL-ambiguous.

**Buyer subset (bid first):**

| Keyword | US vol/mo | Comp | Bid |
|---|---|---|---|
| buy condo in panama | 590 | MED | $0.06–2.16 |
| panama real estate for expats | 320 | MED | $0.05–1.49 |
| buy property in panama / buy real estate in panama (pool) | 210 | MED | $0.21–1.56 |
| invest in panama real estate / panama real estate investment / real estate investment in panama (pool) | 210 | LOW | $1.46–3.55 |
| buy apartment in panama | 210 | LOW | $0.03–1.67 |
| best place to buy real estate in panama | 70 | MED | $0.22–1.86 — **blocked by v2 negative `best place to buy`** |
| santa maria panama real estate | 50 | LOW | $0.31–1.62 — our own project's name searched! |
| panama beachfront property for sale | 40 | MED | $0.07–1.84 |
| panama investment property | 20 | MED | $2.08–4.85 |

**Volume pools (Tier-3 scale, browse-heavy, FL-risk):** homes/houses/buy house in panama ~6,600 (one pool) · panama real estate 3,600 · panama real estate for sale / property for sale ~2,400 (pool) · panama city panama real estate 1,000 · panama city panama condos 720 · apartments for sale in panama city panama 320. CPCs $0.03–1.67 — dirt cheap.
Competitors: **panamasovereign.com owns this cluster** (#2–#11 across all of it). No investment-migration player bridges property→residency with an actual owned project — that bridge (Santa Maria Residences) is uniquely ours.
Policy: SAFE; needs `panama city beach` / `florida` / rental negatives.

### #3 · Friendly Nations Visa — score 4 · 1,330/mo
Named-program, Panama-specific, LOW competition, CPC $0.25–1.51 (cheapest intent in the study).

| Keyword | US vol/mo | Comp | Bid |
|---|---|---|---|
| panama friendly nations visa | 880 | LOW | $0.50–1.51 |
| friendly nations visa | 390 | LOW | $0.25–0.94 |
| + requirements variants | 60 | MED | ~$0.45–1.48 |

⚠️ FNV is a *different* Panama route (employment/economic-solvency, lower threshold) — the ad/LP must bridge honestly: "compare Panama residency routes / QIP = fastest, ~30 days." Only panamasovereign, kraemerlaw, nomadcapitalist rank. Policy: SAFE with honest bridging.

### #4 · Residency-by-investment category — score 4 · 820/mo
Small in the US (the category vocabulary skews "golden visa"/"citizenship"): residency by investment programs 320 ($3.15–9.13) · residency/residence by investment ~260 pool ($2.04–6.92) · countries 140 · permanent residency by investment 70 · cheapest 30. henley/immigrantinvest/getgoldenvisa own it organically. Policy: SAFE.

### #5 · Golden visa generic — score 3 · 11,230/mo — the scale lever
golden visa 8,100 ($1.41–6.02) · countries 1,600 · program(s) 720 · cheapest 210 · cost 210 · best programs 140 · real estate golden visa 140+20 · best 90.
Demand is EU-leaning (portugal golden visa alone = 9,900; already negatived). Research-heavy → guide soft-offer is the conversion path. Requires country-negative wall extension. All 5 mined generalists rank here; ads = pay-to-play.

### #6 · Citizenship / passport — score 2 · 14,730/mo — **POLICY-FLAG, not recommended**
golden passport 5,400 · second citizenship 2,900 · citizenship by investment 2,400 · CBI programs 1,300 · panama passport 720 · second passport 590 · panama citizenship 590 · cheapest CBI 390 · panama citizenship by investment 210 (transactional, $5.04!) · panama dual citizenship 210.
LP sells residency, not citizenship → offer mismatch + risky ad framing (no passport/citizenship promises allowed per house rules). v2's broad `passport` negative already walls part of this off. Document only; if Wassim ever wants panama citizenship by investment (210, genuinely transactional), copy must reframe to "residency first — the path that can lead to naturalization" and that's his call.

### Dead angles (tested, real numbers, drop)
- **Second residency / plan-B:** 240/mo total (second residence 170, second residency 40, plan b residency 10). The HNW *motive* exists but there's no US search language for it — use "Plan B" in ad copy (already in v2 RSAs), not as keywords.
- **Tax / territorial tax:** 150/mo. Same: copy angle, not keyword angle.
- **Investor/investment visa generics:** 790/mo but "investment visa" (720) is mostly EB-5-INTO-the-US direction. Needs `eb5`/`green card` negatives even for the terms we do run.
- **Retirement (excluded by design):** 4,780/mo (panama retirement visa 1,300, pensionado pools ~1,900, retiring to panama 1,600) — pensionado ≠ $300K QIP buyer. Add negatives.

---

## 2. The ≥5K/month plan

**Recommended bid set: ~44 keywords ≈ 5,260 aggregate US searches/mo** (5,540 with lawyers) — meets the 5K floor **without** the citizenship cluster and **without** the browse-heavy property pools:

| Tier | Ad group | ~Vol/mo | Intent character |
|---|---|---|---|
| 1 | QIP Program (exact) — existing + `panama golden visa` | 380 | Pure buyer |
| 1 | Panama Residency Core (phrase) | 1,010 | Chose-Panama researcher → guide |
| 1 | Friendly Nations (phrase) | 1,330 | Chose-Panama, route-comparison |
| 1 | RBI Category (phrase) | 820 | Category shopper |
| 2 | Panama Property Investors (phrase) | 1,720 | Capital-holder |
| — | **Core total** | **≈5,260** | ✓ ≥5K |
| opt | Immigration lawyers (2 kws) | +280 | Service-seeker (Wassim's call) |
| 3 | Golden Visa Generic (phrase) | +11,230 | Research-leaning — scale lever |
| 3b | Property for-sale pools (phrase, FL-negatived) | +~14,600 | Browse-heavy, $0.03–1.5 CPCs |
| | **Full ceiling** | **≈31,000** | |

**Explicit tradeoff:** the strictly-buyer Panama terms max out around 3,400/mo (program + FNV + property-buyer subset). Hitting 5K forces in the residency-core and RBI researcher terms — handled by the LP's email Investor-Guide soft offer (capture → nurture), which is exactly what it's built for. Tier 3 doubles-to-6×'s volume but shifts further toward research; gate it on Tier 1/2 CPA data.

---

## 3. Campaign structure recommendation

Angle-pure ad groups for QS; keep the v2 campaign, add groups rather than rebuild.

| Ad group | Match | Start CPC (from KWP tops) | RSA headline direction (policy-safe, no citizenship/passport promises, no third-party brands, no symbols) |
|---|---|---|---|
| **AG1 QIP Program** (existing, + add `panama golden visa` E) | Exact | keep $6.50 | Qualified Investor Program · $300K Govt-Approved Investment · Residency in About 30 Days |
| **AG2 Panama Residency Core** (residency / requirements / permanent residency / residency visa / how to get / program) | Phrase | $3.00 | Panama Residency Explained · Requirements and Timeline · Free Panama Investor Guide (email capture) |
| **AG3 Friendly Nations** (FNV + generic + requirements) | Phrase | $1.50 | Compare Panama Residency Routes · The Fastest Route Takes About 30 Days · Free Route-Comparison Guide |
| **AG4 Property Investors** (buy property/real estate/condo/apartment, invest in panama real estate, investment property, for expats, santa maria panama real estate, beachfront) | Phrase | $2.50 | Own Real Estate in Panama · Investment That Includes Residency · Santa Maria Residences (our own project — allowed) · Family Included |
| **AG5 RBI Category** (residency by investment ×5) | Phrase | $5.50 | Residency by Investment in Panama · $300K Government-Approved Route · No Minimum Stay Required |
| **AG6 Golden Visa Generic** (Tier 3, later) | Phrase | $4.50 | Golden Visa Program in the Americas · US Dollar Economy · About 30 Days |
| **AG7 Property For-Sale pools** (Tier 3b, only if AG4 converts) | Phrase | $1.00 | same as AG4 |

**Negatives — relax:**
- `best place to buy` → REMOVE when AG4 launches (blocks a 70/mo buyer term). Everything else it blocks is noise anyway.
- `passport` → **KEEP** (walls off 720/mo travel/info + policy risk; nothing in the plan needs it).

**Negatives — add:**
- Retirement wall: `pensionado`, `retirement`, `retire`, `retiree` (v2 only has "retiring to panama") — blocks 4,780/mo of non-buyers.
- EB-5 wall (for AG5/investment-visa terms): `eb5`, `eb-5`, `green card`, `us visa`, `usa visa`, `visa for usa`.
- Florida wall (with AG4/AG7): `panama city beach`, `florida`, `fl`, `pcb`, `rent`, `rental`, `rentals`, `foreclosure`, `cheap`.
- Golden-visa country wall (with AG6): `spain`, `spanish`, `dubai`, `uae`, `emirates`, `malta`, `italy`, `cyprus`, `turkey`, `st kitts`, `dominica`, `grenada`, `antigua`, `caribbean` (greece/portugal/europe/schengen already in).
- Stays excluded: citizenship/passport cluster, second-residency and tax keyword plays (copy angles only), nomad, work/tourist visa long tail.

---

## 4. Competitor intel summary

**Who's strong where** (US organic, from 3 SERPs + 4,900 ranked-keyword rows):

| Competitor | Territory | Threat notes |
|---|---|---|
| **kraemerlaw.com** (Panama law firm) | The entire Panama visa/immigration long tail — residency, citizenship, pensionado, travel, lawyers, taxes (#2–#11 on ~everything Panama) | The domain to beat on Panama-specific terms; also owns "panama immigration lawyers" ($9.51 CPC signal = someone's bidding) |
| **panamasovereign.com** | Panama property + expat + FNV (#2–#4 on property cluster) | Only player bridging property↔residency; doesn't have an owned project |
| **henleyglobal.com** | Category head terms (#1–#3 on all three of ours) + "multiple citizenship" content machine (40,500/mo) | Brand gravity; won't outrank soon — outbid instead |
| **goldenvisas.com / getgoldenvisa.com** | Golden-visa category generics + per-country guides | Lead-gen brokers; our direct ad competitors on AG6 |
| **immigrantinvest.com / nomadcapitalist.com** | Dual-citizenship/plan-B content (22,200/mo "dual citizenship for americans") + expat lifestyle | Content plays, not offer pages — low ad overlap |
| **ntltrust / globalresidenceindex / imidaily** | Mid-tail category + industry news | Minor |

**Gaps we can own:** (1) QIP program terms — micro-volume but ours, and mercan.com already ranks #4–6 organically on head terms (ads + organic double-slot opportunity); (2) FNV at $0.25–1.51 CPC — nobody's defending it commercially; (3) the property→residency bridge with a real owned project (Santa Maria) — no competitor can copy that ad story; (4) "panama residency $5000" (110/mo) shows price-anchored FNV-era demand — comparison-guide content play.

**What multiple competitors rank for that v2 doesn't cover:** panama residency requirements (4 competitors), panama permanent residency (3), panama golden visa (3), panama friendly nations visa (3), panama citizenship by investment (3, flagged), residency by investment generics (3) — all addressed by AG2/AG3/AG5 above.
