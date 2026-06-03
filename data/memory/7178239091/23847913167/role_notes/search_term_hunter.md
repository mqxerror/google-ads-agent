# Search Term Hunter Notes

**Last updated:** 2026-06-02 12:28

**Task:** Deep performance analysis for "MapleRoots — Citizenship by Descent (US)":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown
# Deep Performance Analysis — MapleRoots (May 19 – June 2, 2026)
**Campaign age:** 18 days | **14-day window (May 19–Jun 1):** 13,567 impr · 1,626 clicks · $1,779.80 · **27 conv** · blended CPA **$65.92** · avg CPC **$1.09**
*(June 2 excluded from trends — partial day, 243 impr at midday.)*
## 1. Trend Analysis
| Date | Impr | Clicks | Cost | Conv | CTR | CPC | Event |
|------|------|--------|------|------|-----|-----|-------|
### Inflection points
1. **May 23 — AG2/AG4 bid corrections.** CPC broke below $1.05 and has held there (vs $1.20 on May 19). The bid plumbing is now largely fixed.
2. **May 26 — LP switch.** The measurable event. See pre/post below.
3. **May 30–31 — weekend collapse.** Impressions halved (1,128 → 416). Normal B2C-immigration weekend pattern, not a problem.
### Pre vs post LP-switch (the headline question)
| Window | Conv | Spend | **CPA** | Conv/day |
|--------|------|-------|---------|----------|
**Verdict: a real but modest -14% CPA improvement** — not the "double" the CRO models projected. The PPC Strategist is right: **the P0 dev fixes never shipped.** The new LP is above-fold but still carries the 8-field form and the "Submit" button. We captured the *form-position* win (~14%) but left the *form-friction* win (another 15–25%) on the table. Post-switch conv/day looks flat only because s
## 2. Ad Group Breakdown (lifetime)
| Ad Group | Clicks | Cost | Conv | **CPA** | % Spend | % Conv | Verdict |
|----------|--------|------|------|---------|---------|--------|---------|
**The story hasn't changed in 10 days: AG3 produces 24% of conversions on 10% of spend, and it's still underfunded.** AG2 is now the worst live ad group — $141 CPA, and bid fixes from May 23 haven't rescued it.
## 3. Keyword Efficiency Map
### Winners (protect + feed)
| Keyword | AG | Clicks | Conv | Est. CPA | QS |
|---------|-----|--------|------|----------|-----|
The two Bill C-3 / ancestry keywords are your CPA engine — both sit in AG1/AG3 and both convert 5–6×.
### The leak (my #1 finding as Search Term Hunter)
| Keyword | AG | Clicks | Conv | CVR | QS |
|---------|-----|--------|------|-----|-----|
**This single phrase-match keyword is the campaign's biggest structural leak.** It's the #1 click magnet (726 clicks ≈ $800 spend, ~45% of AG1) at the worst CVR in the campaign and the lowest Quality Score. "Through parents" is **DIY intent** — first-gen-born-abroad searchers who qualify automatically via a free IRCC Proof-of-Citizenship application and don't need a consultant. Every other special
### Losers (zero conv, money spent)
| Keyword | AG | Clicks | Conv | QS | Action |
|---------|-----|--------|------|-----|--------|
AG2's three grandparent keywords (`grandparent canadian citizen`, `canadian grandparent citizenship`, `canada citizenship grandparent`) account for **~198 clicks and 1 conversion** — that's why AG2's CPA is $141. The bid fixes lowered cost but the *intent* isn't converting.
### Untested potential (0 clicks)
`[am i a canadian citizen]`, `[my grandfather was born in canada...]` (phrase), `[canadian citizenship great grandparent]`, `"canada citizenship by descent new law"` — all QS 7–8, just no volume yet.
## 4. Quality Score Audit
**No keyword sits below QS 5.** But the one keyword *at* QS 5 is the problem child:
- **`"canadian citizenship through parents"` — QS 5 on 726 clicks.** This is the single highest-impact QS drag in the account: a below-average score on the campaign's biggest spender means you're paying a CPC premium *and* it's not converting. The low QS is the landing page + ad-relevance mismatch the CRO specialist flagged — "through parents" searchers hit a generic "descent" page that doesn't ad
The fix is structural, not cosmetic: this keyword shouldn't carry 45% of AG1's clicks. Tighten it (below).
## 5. Search Term Quality
**Search terms are exceptionally clean — this is the healthiest part of the campaign.** Of 40 visible terms (last 7 days, ~$166 visible spend ≈ 21% of total), essentially **100% are descent-relevant.** The May 19 negatives are doing their job: zero "jobs", "free", "renounce", "us citizen", or DNA-test noise this week.
The only borderline cluster is **research/DIY intent**, not waste:
| Pattern | Visible Clicks | Visible Cost | Verdict |
|---------|----------------|--------------|---------|
**Estimated true waste: <2% of visible spend (~$3–4/week).** Note for the record: my standard golden-visa instinct to negate "eligibility"/"requirements"/"quiz" **does NOT apply to this campaign** — Canadian citizenship by descent has a real ancestral-chain eligibility question, so those queries are on-intent. I'm explicitly not negating them.
**One converting term still not added:**
| Search Term | Clicks | Cost | Conv | Status |
|------------|--------|------|------|--------|
This is textbook grandparent-path intent and it converted — exactly what AG2 is built for. Add as exact match.
## 6. Budget Allocation
| Ad Group | % Spend | % Conv | Read |
|----------|---------|--------|------|
**The misallocation is the same one we've flagged since May 23 and still haven't fixed: AG3 earns 24% of conversions on 10% of spend.** Money is sitting in AG2 (grandparent, $141 CPA) that belongs in AG3 (great-grandparent/Bill C-3, $33 CPA).
**Pacing:** 14-day avg = **$127/day** (27% over the $100 budget), ~$3,900/mo vs $3,000 target. CPC is stuck at $1.05–1.14 — the $0.65 bids aren't translating because AG1's phrase-match keywords still win at a premium. Either formalize the budget to ~$130/day or fix the AG1 leak to bring true CPC down.
## 7. Strategic Recommendations — Top 3 (effort × impact)
### #1 — Tighten `"canadian citizenship through parents"` (the leak)
**Impact: HIGH · Effort: 10 min**
726 clicks / 7 conv / 0.96% CVR / QS 5 — the biggest spend concentration at the worst economics. Two-part fix:
- **Convert phrase → exact** `[canadian citizenship through parents]` so it stops catching broad DIY variants, AND
- **Add campaign-level phrase negative** `"born in canada"` to block "my parent was born in canada can I…" queries where the answer is free and obvious.
This reclaims ~$200–300/mo of AG1 spend and lifts blended CVR by concentrating budget on convertible intent. **Bigger lever than any bid tweak.**
### #2 — Reallocate to AG3 (the starved star)
**Impact: HIGH · Effort: 5 min**
AG3 = $33 CPA, 24% of conv, 10% of spend. Raise bids on `bill c-3 canadian citizenship` and `[bill c-3 citizenship]` by ~$0.15–0.20 to win more impression share, funded by the AG2 cuts below. Half the blended CPA lives in this ad group — feed it.
### #3 — Stop the AG2 grandparent bleed + add the converting term
**Impact: MEDIUM-HIGH · Effort: 5 min**
- Lower `[grandparent canadian citizen]` and `"canadian grandparent citizenship"` → **$0.45** (0 conv on 61/48 clicks even after the May 23 fix).
- **Add `[my grandfather was born in canada can i get citizenship]` exact, AG2, $0.65** — converted on 6 clicks, real grandparent intent.
## Summary Scorecard
| Dimension | Grade | Note |
|-----------|-------|------|
**Bottom line from the search-term seat:** the queries coming in are clean and high-intent — acquisition isn't the problem. The leak is *internal*: one phrase-match keyword (`through parents`) hoarding 45% of AG1's clicks at 0.96% CVR, and AG3's winning intent starved of budget. Fix the keyword structure (#1) and the allocation (#2/#3) and CPA should move from $66 toward the $45–50 range without t
Want me to execute #1–#3 now? #1 (exact-match conversion + `"born in canada"` negative) is the one I'd run first.
— *Search Term Hunter*