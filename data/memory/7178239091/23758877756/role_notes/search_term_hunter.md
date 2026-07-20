# Search Term Hunter Notes

**Last updated:** 2026-07-20 16:22

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

### 2026-07-14 15:44 — Fresh 7-day search-term audit using ONLY the 2026-07-14 search-term table alread

**Task:** Fresh 7-day search-term audit using ONLY the 2026-07-14 search-term table already in context — do NOT re-pull the report. The user asks why this campaign gets zero leads; you own the traffic-quality h
**Search Term Hunter | Greece GV Turkey (23758877756) | 2026-07-14**
**1. Waste: 43.5% — 5× worse than Jun 2**
Visible search-term cost this week: **$292.10**
| Cluster | Terms | Cost |
|---------|-------|------|
Jun 2 baseline: 8.8% (~$20/week). **Waste is now 5× worse and ~$107/week higher.** Primary driver: the şartları cluster had near-zero spend on Jun 2; it has since surged to the campaign's single biggest waste line.
**2. Jun 2 negatives that were never applied**
Chronicle confirms "3 criteria created" Jun 2, but nedir ($28.35), nasıl alınır ($11.83), and ekşi ($1.14) are all still matching and spending this week — clear evidence none were applied (or the wrong 3 were). The şartları PHRASE negative (flagged again Jul 4 by Analytics Analyst as ~$62/week) is also unexecuted. No chronicle entry confirms any of these four were actioned after Jun 2.
**3. "golden visa yunanistan" — NONE status, 6 weeks overdue**
$31.63 / 4 clicks this week, status NONE. Flagged Jun 2 for immediate PHRASE addition to yunanistan-golden-visa. Still unactioned.
**Execute — negatives:**
| Term | Match | Level |
|------|-------|-------|
| şartları | PHRASE | Campaign |
| nedir | PHRASE | Campaign |
| nasıl alınır | PHRASE | Campaign |
| ekşi | EXACT | Campaign |
| şirket kurulumu | PHRASE | Ad-group: yunanistan-golden-visa |
**Execute — keyword adds:**
| Term | Match | Ad Group |
|------|-------|---------|
| golden visa yunanistan | PHRASE | yunanistan-golden-visa |
— *Search Term Hunter*

### 2026-07-14 15:47 — Orchestrated finding

{
  "summary": "Waste tripled to 43.5% ($127/week) because Jun 2 negatives were never applied \u2014 add \u015fartlar\u0131 PHRASE + nedir PHRASE + nas\u0131l al\u0131n\u0131r PHRASE + ek\u015fi EXACT at campaign level, and finally add 'golden visa yunanistan' PHRASE as a keyword.",
  "findings": [
    {
      "claim": "Informational waste has grown from 8.8% to 43.5% of visible search-term spend (~$127/week) because Jun 2 negatives for \u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r/ek\u015fi were never applied",
      "severity": "high",
      "confidence": 0.93,
      "sources": [
        "2026-07-14 search-term table (context)",
        "Jun 2 chronicle: '3 criteria created' with no follow-up entries",
        "Jun 2 Search Term Hunter audit"
      ],
      "disconfirmed_by": "Evidence that nedir/nas\u0131l al\u0131n\u0131r/ek\u015fi were among the 3 negatives added Jun 2 but are re-matching due to match type gaps",
      "id": "c1-f0"
    },
    {
      "claim": "\u015fartlar\u0131 PHRASE at campaign level is the single highest-impact unexecuted negative \u2014 alone worth ~$80/week",
      "severity": "high",
      "confidence": 0.97,
      "sources": [
        "2026-07-14 search-term table: 5 \u015fartlar\u0131 variants sum to $79.88",
        "Jul 4 Analytics Analyst recommendation (unexecuted per chronicle)"
      ],
      "disconfirmed_by": "\u015eartlar\u0131 negative was applied between Jul 4 and Jul 14 but the benefit not yet visible in this data snapshot",
      "id": "c1-f1"
    },
    {
      "claim": "'golden visa yunanistan' should be added as PHRASE keyword to yunanistan-golden-visa \u2014 4 clicks/$31.63 this week at NONE status, flagged Jun 2 and still unexecuted",
      "severity": "medium",
      "confidence": 0.99,
      "sources": [
        "2026-07-14 search-term table (status: NONE, $31.63)",
        "Jun 2 Search Term Hunter recommendation"
      ],
      "disconfirmed_by": "A PHRASE or EXACT keyword already capturing this term exist

### 2026-07-14 16:56 — Produce the concrete 'keep what's working' inventory that either scenario (clone

**Task:** Produce the concrete 'keep what's working' inventory that either scenario (clone or prune-in-place) would be built from — context data only, cite your Jul 14 audit (reuse), do NOT redo the waste math.
**KEEP** (proven Turkish investor terms — all 3 lifetime convs live here):
- `yunanistan golden visa` PHRASE | **yunanistan-golden-visa** | QS 2 | 253 clicks, **2 conv** — primary signal, protect budget
- `golden vize yunanistan` PHRASE | **yunanistan-golden-visa** | QS 5 | 105 clicks, **1 conv** — best QS/conv combo
- `altın vize yunanistan` PHRASE | **yunanistan-golden-visa** | QS 6 | 24 clicks — anchor for QS score
- `yunanistan golden vize` PHRASE | **yunanistan-golden-visa** | QS 5 | 18 clicks — variant coverage
- `yunanistan ev alana vatandaşlık` PHRASE | **yunanistan-oturum-gayrimenkul** | QS 4 | 34 clicks — QS recovered, citizenship intent is on-thesis
- Remaining oturum-izni cluster (QS 3 band, yunanistan-oturum-gayrimenkul) — keep but let the EN pause + negatives free their budget share
**ADD**:
- `golden visa yunanistan` PHRASE → **yunanistan-golden-visa** | $31.63 / 4 clicks this week at NONE — 6 weeks overdue, add with $5 bid cap
**CUT/NEGATE**:
- Pause ad group `greece-golden-visa-en` (198513892027) entirely — kills `greece golden visa` (46 clicks/0 conv), `greece golden visa citizenship` (18 clicks/0 conv), `greece golden visa program` QS:8 — high QS but wrong-language group, Creative Director closed this Jul 14
- Campaign-level negatives: `şartları` PHRASE, `nedir` PHRASE, `nasıl alınır` PHRASE, `ekşi` EXACT — $127/week of identified waste per Jul 14 Hunter audit
- PROBATION (yunanistan-oturum-gayrimenkul, bid-cap $4 max, review in 7 days): `ev almak vatandaşlık`, `ev alınca vatandaşlık`, `oturum için ev almak` — all added Jul 6, coincide with the impression/CPC spike (439 impr, $172.82, band breach to $6.40+), on-thesis but suspects; cap before deciding
At $50/day: EN pause frees ~$8/day, negatives cut ~$18/day — together absorb the cap without touching the converting Turkish core.
— *Search Term Hunter*

### 2026-07-14 16:57 — Orchestrated finding

{
  "summary": "All 3 conversions are in yunanistan-golden-visa; keep its Turkish PHRASE core, add golden visa yunanistan PHRASE, pause EN group, deploy 4 campaign negatives, and bid-cap the Jul 6 citizenship additions \u2014 that gets you to $50/day without cutting converting traffic.",
  "findings": [
    {
      "claim": "All 3 lifetime conversions sit in yunanistan-golden-visa group; this group's top Turkish PHRASE keywords should receive the majority of the $50/day budget post-restructure",
      "severity": "high",
      "confidence": 0.92,
      "sources": [
        "Keyword table: yunanistan golden visa 253 clicks 2 conv, golden vize yunanistan 105 clicks 1 conv, golden vize yunanistan 105/1",
        "Ad group data: yunanistan-golden-visa $2,495 / 3 conv lifetime"
      ],
      "disconfirmed_by": "API pull showing conversions attributed to yunanistan-oturum-gayrimenkul or EN group keywords",
      "id": "c3-f0"
    },
    {
      "claim": "Jul 6 citizenship keyword additions (ev almak/al\u0131nca vatanda\u015fl\u0131k, oturum i\u00e7in ev almak) are the most likely trigger for the CPC band breach \u2014 bid-cap at $4, do not remove",
      "severity": "medium",
      "confidence": 0.72,
      "sources": [
        "15-day daily table: Jul 6 impression spike 439 / $172.82 / CPC $6.40",
        "Chronicle Jul 6: 3 PHRASE keywords added to oturum-gayrimenkul group"
      ],
      "disconfirmed_by": "Confirmed via API that no keywords were added or bids changed around Jul 5\u20136",
      "id": "c3-f1"
    },
    {
      "claim": "EN group pause is required before the $50/day cap is achievable \u2014 group currently contributes ~$8/day of structural waste with 0 lifetime conversions",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "Ad group data: 198513892027 $361.22 lifetime / 0 conv / 67 clicks",
        "Creative Director Jul 14: EN group removal confirmed \u2014 conversion action contamination + audience mismatch"
      ],

### 2026-07-17 11:31 — Answer 'why is this campaign so bad' from the traffic side using ONLY the fresh 

**Task:** Answer 'why is this campaign so bad' from the traffic side using ONLY the fresh 2026-07-17 7-day search-term table already in context — no tool calls, and cite your Jul 14 audit for history instead of
**Search Term Hunter | Greece GV Turkey (23758877756) | 2026-07-17**
**Verdict on the 4 negatives: NEVER applied.** Jul 14 confirmed all 4 still matching; this week they're still spending. 6.4 weeks of identified waste continues unblocked.
**This week's informational waste (Jul 17 search-term table):**
| Cluster | Active terms + cost | Total |
|---------|-------------------|-------|
All 4 first flagged **Jun 2**. Re-confirmed Jul 4 (Analyst), Jul 14 (Hunter). Today = Jul 17. **6.4 weeks overdue, still executing zero.**
**golden visa yunanistan:** CONFIRMED NONE — 5 clicks / $39.40 this week. Jun 2 PHRASE add = 6.4 weeks overdue.
**Executable list:**
| Action | Term | Match | Level | $ Impact |
|--------|------|-------|-------|----------|
Total recoverable from negatives alone: **$83.58/week.**

### 2026-07-17 11:33 — Orchestrated finding

{
  "summary": "4 negatives are 6.4 weeks overdue and burning $83.58/week (30% of visible spend); 'golden visa yunanistan' bleeding $39.40 at NONE is the top uncontrolled keyword leak \u2014 both are one-session fixes.",
  "findings": [
    {
      "claim": "The 4 agreed campaign negatives (\u015fartlar\u0131 PHRASE, nedir PHRASE, nas\u0131l al\u0131n\u0131r PHRASE, ek\u015fi EXACT) were never applied \u2014 all 4 clusters are still spending 6.4 weeks after first recommendation",
      "severity": "high",
      "confidence": 0.97,
      "sources": [
        "2026-07-17 search-term table: nedir $20.62, nas\u0131l al\u0131n\u0131r $11.90, ek\u015fi $1.14, \u015fartlar\u0131 variants $49.92 all at NONE status",
        "Jul 14 Search Term Hunter: identical 4 clusters confirmed unexecuted",
        "Jun 2 chronicle: '3 criteria created' but these 4 still matching on Jul 14 and Jul 17"
      ],
      "disconfirmed_by": "A live pull of campaign-level negative criteria showing \u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r/ek\u015fi applied between Jul 14\u201317, with data lag masking the effect in this snapshot",
      "id": "c2-f0"
    },
    {
      "claim": "Informational waste is $83.58/week (29.7% of visible spend), down from 43.5% on Jul 14 in dollar-share but still the campaign's single largest fixable cost leak with zero conversion path",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "2026-07-17 search-term table: \u015fartlar\u0131 $49.92 + nedir $20.62 + nas\u0131l al\u0131n\u0131r $11.90 + ek\u015fi $1.14 = $83.58",
        "Visible spend total: $281.52 summed from 22 non-zero terms in the top-40 table"
      ],
      "disconfirmed_by": "Any \u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r term recording a conversion in account history",
      "id": "c2-f1"
    },
    {
      "claim": "'golden visa yunanistan' remains NONE status at 5 clicks/$39.40 this week \u2014 budget is bleeding uncontrolled on this term for the

### 2026-07-18 23:55 — USER CONFIRMED — execute Day 1 of the agreed calendar NOW for campaign 237588777

**Task:** USER CONFIRMED — execute Day 1 of the agreed calendar NOW for campaign 23758877756 (Greece Golden Visa - Turkey) ONLY. Add exactly these 4 campaign-level negative keywords via campaign_criterion__add_
I'll execute Day 1 now. First, let me load the google-ads MCP tool schemas I need — the negative-keyword add tool and a GAQL query tool for verification.Tools loaded. Executing Day 1 now — adding the 4 campaign-level negatives to campaign 23758877756.The allowlist entry uses a **double-underscore** name (`campaign_criterion__add_negative_keyword_criteria`) but the actual registered tool is **singl
I could not add the 4 negatives, and I will not claim otherwise. Both required tools are blocked by a config bug, not applied.
- **What I attempted:** `campaign_criterion_add_negative_keyword_criteria` on campaign 23758877756 with şartları PHRASE, nedir PHRASE, nasıl alınır PHRASE, ekşi EXACT — my own overdue recommendation ($83.58/wk waste, 6.4 weeks overdue per the Jun 2 / Jul 14 / Jul 17 audit; waste math not redone).
- **Blocker:** the allowlist expects **double-underscore** names (`campaign_criterion__add_negative_keyword_criteria`, `search__execute_query`) but the live MCP tools are **single-underscore** (`..._add_negative_...`, `search_execute_query`). The double-underscore variants don't exist; the single-underscore ones return `TOOL_NOT_ALLOWED`. Same underscore mismatch the PPC Strategist logged Jul 17.
- **Verification:** also impossible from this seat — `search_execute_query` is blocked by the identical mismatch, so I have zero criterion IDs to report and cannot confirm live state.
- **Status unchanged:** the 4 clusters remain uncontrolled. This is a **second** silent-fail risk on top of Jun 2 — do NOT record Day 1 as done.
- **Fix needed:** correct the agent tool-allowlist to the real single-underscore names, then re-run this exact add + the campaign_criterion verification pull.

### 2026-07-19 00:00 — Orchestrated finding

{
  "summary": "Day 1 NOT executed \u2014 the 4 negatives are still unapplied; a tool-allowlist underscore mismatch blocks both the add and its verification. Fix the allowlist, then re-run. Do not mark Day 1 complete.",
  "findings": [
    {
      "claim": "Day 1 negatives (\u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r PHRASE + ek\u015fi EXACT) are still NOT applied \u2014 execution blocked by tool-allowlist underscore mismatch, not a Google API error",
      "severity": "high",
      "confidence": 0.98,
      "sources": [
        "Live TOOL_NOT_ALLOWED error naming allowed set with '__' vs registered '_' tools",
        "ToolSearch confirms no double-underscore variant exists",
        "Jul 17 PPC Strategist logged identical mismatch on search__execute_query"
      ],
      "disconfirmed_by": "A successful add call returning criterion IDs, or an allowlist entry matching the real single-underscore tool name",
      "id": "c1-f0"
    },
    {
      "claim": "Fix the agent tool-allowlist (map to single-underscore names) before any write/verify work on this account can proceed",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "Both write tool and search_execute_query blocked by same mismatch this session"
      ],
      "disconfirmed_by": "Either tool executing successfully under the current allowlist",
      "id": "c1-f1"
    }
  ]
}

### 2026-07-20 16:21 — Verify from the LIVE 3-day search-term table (2026-07-20, in context — do NOT re

**Task:** Verify from the LIVE 3-day search-term table (2026-07-20, in context — do NOT re-pull) whether the 4 Day-1 negatives you attempted Jul 18 are live. Cite your own Jul 18 execution report (REUSE — do no
**Search Term Hunter | Greece GV Turkey (23758877756) | 2026-07-20 — Day-1 negative verification**
- **Negatives NOT live — confirmed.** Per my Jul 18 execution report (reuse), both `campaign_criterion_add_negative_keyword_criteria` and `search_execute_query` were blocked by the tool-allowlist underscore mismatch, so Day 1 never applied. The live 3-day table corroborates it: every targeted informational term still matches at **NONE** status — `yunanistan golden visa şartları` 4c/$28.75, `yunani
- **Waste (3-day):** $28.75+$5.92+$7.71+$7.95+$5.93 = **$56.26** → ~**$131/week** projected — at or above my Jul 17 $83.58/week figure (cited, not rebuilt). Waste continuing undiminished.
- **`golden visa yunanistan` still uncontrolled:** 3c/$23.54, NONE — 7 weeks since my Jun 2 add recommendation.
**Verdict:** Negatives NOT applied; waste continuing at ≥ the prior rate; blocker remains the tool-allowlist fix.
— *Search Term Hunter*

### 2026-07-20 16:22 — Orchestrated finding

{
  "summary": "Day 1 negatives never applied \u2014 live table shows all 4 informational clusters still matching at NONE, ~$131/week waste continuing, blocker remains the tool-allowlist underscore fix.",
  "findings": [
    {
      "claim": "The 4 Day-1 campaign negatives (\u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r PHRASE + ek\u015fi EXACT) are still NOT applied \u2014 all target terms remain at NONE status in the live 3-day table",
      "severity": "high",
      "confidence": 0.98,
      "sources": [
        "Jul 18 execution report: both add tool + search_execute_query blocked by allowlist underscore mismatch",
        "2026-07-20 3-day search-term table: \u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r/ek\u015fi variants all status NONE"
      ],
      "disconfirmed_by": "Any of these terms showing 'Excluded' status or a live campaign-criterion pull listing them as negatives",
      "id": "c2-f0"
    },
    {
      "claim": "Informational waste is continuing undiminished \u2014 $56.26 over 3 days projects to ~$131/week, at or above the Jul 17 $83.58/week baseline",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "2026-07-20 3-day table: $28.75+$5.92+$7.71+$7.95+$5.93",
        "Jul 17 Search Term Hunter $83.58/week figure (cited)"
      ],
      "disconfirmed_by": "Any \u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r term recording a conversion, or a data-lag artifact inflating the 3-day snapshot",
      "id": "c2-f1"
    },
    {
      "claim": "'golden visa yunanistan' remains uncontrolled at 3 clicks/$23.54 NONE \u2014 7 weeks past the Jun 2 add-as-PHRASE recommendation",
      "severity": "medium",
      "confidence": 0.97,
      "sources": [
        "2026-07-20 3-day table: golden visa yunanistan 3c/$23.54 NONE",
        "Jun 2 Search Term Hunter add recommendation"
      ],
      "disconfirmed_by": "A PHRASE/EXACT keyword now capturing this term (status ADDED)",
      "id": "c2-f2"
    }
  ]
}
