# Search Term Hunter Notes

**Last updated:** 2026-07-05 17:18

**Task:** Deep performance analysis for "Panama QIP — Qualified Investor Program":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown*
## Panama QIP (23871240619) — Search Term Hunter Deep Analysis
**Analysis window:** Jun 21 – Jul 4 (14 full days) + Jul 5 partial. All $ USD. Data read from context — no re-fetch.
**Prior work I'm building on:** The lifestyle/relocation leak and the QS 1 `panama golden visa` keyword have been flagged for negation/pausing since **May 25** and again **Jun 24** — both are **still live**. The downstream conversion wall (Gravity Form ID 11 silently rejecting international phone formats — GTM Specialist's Jun 1 live test) is confirmed and out of my lane; I flag it but focus this 
### 1. Trend Analysis (14 days)
| Window | Impr | Clicks | Cost | Conv | CTR | CPC |
|---|---|---|---|---|---|---|
**Everything is flat-to-declining and stable — except conversions, which are zero.** CPC held at ~$3.26, CTR steady ~9%. This is a campaign in equilibrium at the wrong altitude: healthy click mechanics, no downstream conversion.
**Inflection points:**
- **Jun 22** — volume collapse (15 clicks, 5.3% CTR) — single low-serving day.
- **Jun 23** — CPC spike to **$4.01** and $168.30 spend (14-day high). Already diagnosed as auction pressure, not a lasting shift — CPC reverted to ~$3.20 the next day.
- **Jun 25** — the **lone conversion** (4th lifetime, AG2). Nothing since — **10 consecutive zero-conversion days (Jun 26 → Jul 5).**
- **Jun 30 / Jul 5** — CTR spikes (13.0% / 14.3%) with no conversion follow-through — engagement is fine, the wall is post-click.
**14-day bottom line:** $1,488.50 spent, 456 clicks, **1 conversion** → CPA $1,488 for the period.
### 2. Ad Group Breakdown (lifetime)
| Ad Group | Status | Clicks | Cost | Conv | CPA | Verdict |
|---|---|---|---|---|---|---|
**AG2 is the whole account** — all 4 lifetime conversions, 70% of clicks. Its CVR (0.375%) is still weak, but it's the only lane with any signal. **AG1 is the misallocation**: $1,478 (31% of lifetime spend) for zero conversions. Note AG1's once-blocked anchor `[EXACT] panama qualified investor program` is now **live at QS 6** (18 clicks, 0 conv) — the policy block resolved, but the ad group still 
### 3. Keyword Efficiency
Per-keyword cost isn't in context (only clicks/conv/QS), so CPA is mapped by click-volume, not exact dollars.
**Winners — the only converters (both AG2):**
| Keyword | QS | Clicks | Conv | Note |
|---|---|---|---|---|
**Losers — meaningful clicks, zero conversions:**
| Keyword | QS | Clicks | Conv |
|---|---|---|---|
**Untested (0 clicks — new adds):**
- `[PHRASE] second residency for us citizens` — high-intent US lane Competitor Intel flagged. **Nurture, don't touch.**
- `[EXACT] panama residency no minimum stay`, `[PHRASE] panama territorial tax` — fine to let mature.
- ⚠️ `[PHRASE] best place to buy` — **this is a property-shopping phrase sitting as a POSITIVE keyword.** Last survivor of the "5 suspicious keywords" cluster (May 25). 0 clicks by luck. **It belongs as a negative — remove it before Google matches it.**
### 4. Quality Score Audit
**The counter-intuitive finding: QS is inverted vs. commercial value here.**
- The **highest-QS keyword** — `panama investment property` (QS 8) — has **0 conversions**.
- The **best converter** — `panama residency for americans` (QS 3, 3 conv) — has a **low** QS.
That's the CRO Specialist's diagnosis in numbers: the landing page is **investor-framed**, but the converting queries are **residency-research intent**. So residency keywords score low on LP-relevance (QS) yet convert, because the searcher's underlying intent matches the offer. **The low QS on converting keywords is a landing-page relevance problem, not a keyword problem** — do NOT pause them.
**The one keyword that's genuinely QS-toxic:** `[PHRASE] panama golden visa` at **QS 1** — low QS *and* 0 conv (52 clicks) *and* wrong framing (the program is the "Qualified Investor Program," not a "golden visa"). Google levies a QS tax on every auction this keyword enters and drags Ad Rank on neighbors. **This is clean, no-regret waste.**
Impact estimate: the QS 1–3 cluster carries ~10–15% of spend at inflated CPCs — but only `panama golden visa` should be cut on QS grounds. The rest need a **residency-answering LP section above the fold**, not negation.
### 5. Search Term Quality (last 7 days, visible sample: 43 clicks / ~$139)
The search-term report shows only top terms, so this is a sample of total spend. Categorized by **investor/residency intent vs. lifestyle**:
**Keep — residency-research = the converting intent (do NOT negate):**
`panama residency requirements` (6, $14.69), `panama residency for us citizens` (1, $2.44), `panama residency requirements for us ci…` (2, $4.99), `panamanian citizenship by investment` (1, $5.96), `panama investment visa` (1, $5.90). These are the exact query family that produced all 4 conversions.
**High-confidence waste — lifestyle / relocation-to-live (negate):**
| Term | Clicks | Cost | Problem |
|---|---|---|---|
**Single biggest waste line:** `panama golden visa` as a search term — **5 clicks, $28.89 = 21% of visible 7-day spend** — maps straight to the QS 1 keyword above.
**Wasteful % :** clear lifestyle/relocation ≈ **$15/week high-confidence**; add the QS-1 `golden visa` line and it's ~$44/week (~24% of visible spend). Wrong-program patterns to pre-empt (0 clicks now, but ticking): `nomad visa panama`, `panama reforestation visa program`, `panama temporary residency`.
### 6. Budget Allocation
| Ad Group | Planned % | Actual % (lifetime) | Reality |
|---|---|---|---|
**Allocation has self-corrected against the original plan — and the drift is healthy.** The plan bet 50% on AG1 (investor-intent); reality routed the money to AG2 (residency-intent), which is where every conversion came from. **Don't force budget back to plan.** Pacing: ~$100/day vs $150 cap (67% utilization) — **bids/volume are the binding constraint, not budget.** No budget action.
### 7. Top 3 Recommendations (effort × impact)
**#1 — Pause `[PHRASE] panama golden visa` (QS 1). ⏱️ 2 min · clean win.**
52 lifetime clicks, 0 conv, QS 1, wrong framing — and $28.89 of *this week's* spend alone. It's the single clearest mechanical waste and drags account-level QS. Flagged Jun 24, still live. *(Low-medium impact — I'll execute on your OK.)*
**#2 — Add surgical lifestyle/wrong-program negatives (campaign-level). ⏱️ 5 min · ~$15–20/wk saved.**
Kept deliberately narrow so I don't touch the converting residency-research cluster:
`[PHRASE] move to panama` · `[PHRASE] moving to panama` · `[PHRASE] live in panama` · `[PHRASE] living in panama` · `[PHRASE] retiring to panama` · `[PHRASE] nomad visa` · `[PHRASE] reforestation`
**Guard rail (do NOT negate):** anything with "requirements", "how to get residency", "for us citizens" — that's the money lane. *(Negatives are low-impact — execute & notify.)*
**#3 — Remove the misplaced positive `[PHRASE] best place to buy`. ⏱️ 1 min · prevents future waste.**
Property-shopping phrase living as a positive keyword. 0 clicks by luck — remove before Google spends on it.
**The lever above all three (flagged, out of my lane):** The 10-day zero-conversion streak isn't a keyword problem — it's the **phone-validation form wall** on `/panama-qualified-investor-program`. My negatives cut waste; they can't manufacture conversions the form silently rejects. Best keyword hygiene in the account still funnels into the same broken finish line.
Items #1–#3 are all low/low-medium impact and align with the account's over-negation guard rail. **Want me to execute all three now?** I'll pause the QS 1 keyword, add the 7 negatives, and remove `best place to buy` — then log the changes to the decision file with role=`search_term_hunter`.
— *Search Term Hunter*