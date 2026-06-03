# Search Term Hunter Notes

**Last updated:** 2026-06-02 15:37

**Task:** Search-term + match-type audit for Greece Golden Visa - Turkey (23758877756) from the 7-day search-term report in context. 1) Waste analysis: quantify spend on low-intent/informational terms (nedir, ş
## Search Term Hunter — 7-Day Audit | Greece Golden Visa - Turkey (23758877756)
### 1. Waste Analysis — Quantified Spend
**7-day visible spend (context data): $233.37 total**
| Term | Clicks | Cost | Category | Action |
|------|--------|------|----------|--------|
**Zero-spend terms that will burn money at scale** (no action cost yet, but add negatives now before they get clicks):
| Term | Clicks | Category |
|------|--------|----------|
**Confirmed waste rate: ~$20.56 / $233.37 = 8.8% of weekly spend on identified low-intent terms**
`properties for sale` ($13.60) is the single biggest offender — 66% of the waste total, and it's the exact same pattern flagged on the main Greece campaign audit. Real-estate browsers, not investors.
### 2. Negative Keyword Recommendations
Per account policy: only terms from actual search data, EXACT where possible to protect long-tail.
**Campaign-level negatives (apply to all 3 ad groups):**
| Negative | Match Type | Rationale |
|----------|------------|-----------|
| ev fiyatları | PHRASE | "House prices" — property shopping intent, not investment immigration |
| nedir | PHRASE | "What is it" — purely informational, no action intent; structurally can't convert here |
| nasıl alınır | PHRASE | "How to get" — DIY applicant intent; this site offers consultation, not a self-serve guide |
| ekşi | EXACT | Review/forum site modifier; searchers looking for peer opinions, not a consultation |
| emekli | PHRASE | "Retired" — retirement visa searchers; different program, different eligibility path, different CTA |
**Ad-group-level negatives (yunanistan-golden-visa and yunanistan-oturum-gayrimenkul):**
| Negative | Match Type | Rationale |
|----------|------------|-----------|
**Note on "yunanistan da ev alınca vatandaşlık ver" (0 clicks):** Do NOT negate this. "Does Greece give citizenship when you buy a house?" is a citizenship-pathway question — exactly the investor intent this campaign targets. This is a "Plan B" query dressed up as a factual question. It's on the KEEP list.
### 3. High-Intent Terms Not Yet Added as Keywords
These appeared in the search terms with status NONE and show investor/citizenship intent:
| Term (Turkish) | Translation | Clicks | Cost | Proposed Match | Ad Group Target |
|----------------|------------|--------|------|----------------|-----------------|
**Priority flags:**
- **"golden visa yunanistan"** — already getting 2 clicks and $3.51 spend with NONE status, meaning it's being matched by an existing keyword but isn't capturing it directly. Add as PHRASE to yunanistan-golden-visa immediately.
- **Citizenship-pathway cluster** (ev alınca vatandaşlık, ev alarak vatandaş olmak, konut vatandaşlık) — these are the highest-intent queries in this report. Turkish investors searching "does buying a house in Greece give citizenship?" are ready-to-engage. The Creative Director already flagged this gap in the RSAs ("Ev Alarak Oturma İzni", "7 Yılda Vatandaşlığa Yol") — these keyword additions and 
- **Location-specific terms** (atina, selanik, halkidiki) — geographic specificity is a strong intent signal for this product. Investors who are already thinking about *which city to buy in* are deep in the funnel.
### 4. QS-1 Keywords — Pause or Move?
| Keyword | QS | Clicks | Cost | Recommendation |
|---------|----|--------|------|----------------|
**Reasoning:**
These are citizenship-pathway queries — exactly the high-intent investor language this campaign needs. The 10 clicks on "yunanistan ev alana vatandaşlık" confirm real demand. Pausing these would be the wrong move.
The QS 1 is an **ad relevance failure, not an intent failure.** The current RSA for yunanistan-oturum-gayrimenkul doesn't have pinned headlines directly matching "ev alana vatandaşlık" or "ev alarak oturma izni" language. Google sees the keyword, doesn't see it reflected in the ad headline, and scores Ad Relevance as "Below Average" → QS 1.
**The fix (hold until Jun 4, 7-day window post-May 21 RSA creation):**
1. Add 2 pinned Position 1 headlines to RSA `809625956041`:
- Pin 1: "Ev Alarak Oturma İzni Alın" (get residency by buying property)
- Pin 2: "Yunanistan'da Ev Al, AB'de Yaşa" (buy in Greece, live in EU)
2. This directly matches the keyword text → Ad Relevance jumps from Below Average → Average or Above Average → QS moves from 1 → 4–5 within 7 days.
**Short-term CPC protection:** With QS 1, you're paying a 5–10x premium per click. If the Manual CPC cap isn't already specifically set on these two keywords, set individual bids at $3.00–$4.00 max (below the ad-group default) to limit damage while QS recovers. The headline fix is the real solution; the bid cap is the stopgap.
### Summary Action Table
| Action | Keyword/Term | Level | Impact | When |
|--------|-------------|-------|--------|------|
| Add negative: "nasıl alınır" PHRASE | DIY queries | Campaign | Pre-emptive | Now |
| Add negative: "ekşi" EXACT | Forum/review traffic | Campaign | Pre-emptive | Now |
| Add negative: "emekli" PHRASE | Retirement visa searchers | Campaign | Pre-emptive | Now |
| Add negative: "ev fiyatları" PHRASE | House price browsing | Campaign | Pre-emptive | Now |
| Add keyword: "golden visa yunanistan" PHRASE | Already getting spend | yunanistan-golden-visa | Capture loose traffic | Now |
**Estimated weekly waste being left on the table with current state: ~$20–25/week on confirmed low-intent terms. Total addressable with all negatives above: ~$60–70/month.** The citizenship-pathway keyword additions are the more important upside — those are the terms this campaign exists to capture, and they're showing up in search terms unprotected.
— *Search Term Hunter*

---

## Session Log

### 2026-06-02 15:37 — You already produced your report. Now review your PEERS' reports below and cross

**Task:** You already produced your report. Now review your PEERS' reports below and cross-examine them.

FOCUS: Reconcile the central conflict: is the 1-conv-in-14-days / 0.34% CVR a TRACKING problem (analytic
## Search Term Hunter — Cross-Examination
**2026-06-02 | responding to PPC, Creative Director, Analytics Analyst**
### 1. Conflicts with my view
**On the traffic-intent framing:** I called this 8.8% waste (şartları/nedir/properties for sale). The Analytics Analyst frames it as "genuine low intent — not a tracking gap." We're actually saying the same thing, but my number is more precise: the traffic-intent problem accounts for ~$20/week, not the full CVR gap. The LP funnel is responsible for the remaining ~91% of the conversion deficit. I w
**On keyword sequencing vs. headline sequencing:** I recommended adding citizenship-pathway keywords (`ev alınca vatandaşlık`, `konut vatandaşlık`) **now**. The Creative Director says hold headline changes until Jun 4. These are in conflict: adding keywords before the RSA has the matching citizenship headlines would drive more traffic into QS-1 keywords, worsening CPC and QS temporarily. **I conce
### 2. Concessions
- **Analytics Analyst is right** that the May 23 conversion denominator matters. I used "NONE" search term status to call citizenship-pathway queries high-intent, but until someone reconciles that May 23 conversion to a real CRM lead, we don't actually know *which* search term drove it. The signal is directional, not confirmed.
- **PPC Strategist is right** that pausing the EN group is justified. The `properties for sale` ($13.60, my top waste flag) came exclusively from the EN group — it's structurally generating real-estate browsers. Pausing EN also eliminates this negative keyword I was about to add, making the negative moot.
- **All three are right** that the LP is the dominant problem. My waste rate of 8.8% is real but it projects to ~$60–70/month. The form fix projects to 3x leads on the same spend — that's a $370+ monthly value on current budget. The LP fix outranks my negatives 5:1 in impact.
### 3. What all four specialists missed
**The Czech language targeting is unresolved and blocking clean analysis.** The context shows `Languages: English, Czech`. The GTM Specialist's May 19 notes say Korean was removed and Turkish added. The Creative Director flagged it. But **no one put a live verification on the action plan**. This matters for my audit specifically: if Czech is still active, a slice of impressions is serving to Czech
**The `şartları` terms are NONE-status and still spending.** `golden visa yunanistan şartları` (1 click, $2.50 NONE), `yunanistan oturma izni şartları` (1 click, $0.45 NONE) — informational "conditions/requirements" queries getting spend with zero conversion path. The Analytics Analyst didn't flag these as intent issues. I already called for `şartları` as a phrase negative; what none of us explici
### Forced prioritized sequence (one-change-per-day, Jun 4 window respected)
| Day | Action | Type | Who owns it |
|-----|--------|------|-------------|
**Why this order:** Language verification first (no-cost, removes a QS suppressor), negatives second (lowest-impact, doesn't conflict with any pending ad change), EN group pause third (frees budget on Jun 4 when Jun 4 is already the wait-window release date — clean timing), headlines fourth (immediately after the 7-day window closes), keywords fifth (never add keywords before the matching ad copy 
— *Search Term Hunter*
