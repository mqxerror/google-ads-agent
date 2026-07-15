# Search Term Hunter Notes

**Last updated:** 2026-07-05 16:26

**Task:** Deep performance analysis for "MapleRoots — Citizenship by Descent (US)":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown
## MapleRoots — Deep Performance Analysis (14-Day) · July 5, 2026
**Search Term Hunter | Campaign 23847913167**
Data pulled entirely from context — no API re-fetch. Let me answer the budget question first since you flagged it, then walk the seven dimensions.
### 🔴 The "150% cost increase" — what actually happened
The 150% is **one day**, not a structural break. July 4 spent **$279.33** vs July 3's **$111.80** — that's **+150% day-over-day**, exactly the number you saw.
| Date | Cost | Clicks | Conv | CPC | CPA |
|------|------|--------|------|-----|-----|
This is the **Independence Day holiday overbid** the PPC Strategist called yesterday. The mechanism: holiday search volume drops, but competitors don't adjust dayparting, so Google fills the thinner inventory at a premium. $279 at $4.05/click for 2 conversions = 3.2× the baseline CPA.
**But here's what's new and worth your attention:** the PPC Strategist set a gate — "check Jul 5 morning; if CPC returns to $2.90–$3.20, no action." **It did not.** Jul 5 CPC is **$4.46 — the highest ever recorded in this campaign**, above even Jul 4. The holiday premium is *not* fading on schedule, and Jul 5 is already at $102 with **0 conversions**. This has crossed from "watch" toward "if it ho
**The deeper cost story (the real +140%):** Zoom out and CPC went from **~$1.40 in June** (MaxClicks, $1.40 cap) to **~$3.37 now** (Maximize Conversions, no cap) = **+141%**. *But CPA held flat at ~$48.* You're paying 2.4× per click and converting proportionally more — Maximize Conversions is bidding up for likely-converters. **Efficiency is intact; the per-click price is not.** That's the honest 
### 1. Trend Analysis (Jun 21 – Jul 4, 14 full days)
**Totals:** 605 clicks · $2,038.20 spend · 42 conv · **$48.53 blended CPA** · $3.37 avg CPC · $145.59/day
Week-over-week — remarkably stable until the holiday:
| Window | Clicks | Spend | Conv | CPA | CPC |
|--------|--------|-------|------|-----|-----|
**Inflection points:**
- **Jun 24** — best day: 6 conv at $24.31 CPA
- **Jun 25** — low-CVR anomaly: 926 impr (highest volume), only 1 conv, $138 CPA. Single-day variance.
- **Jul 2–3** — the clean pocket: 9 conv on $194 = ~$21.60 CPA. This is the campaign at its best.
- **Jul 4–5** — CPC spike ($4.05 → $4.46), CPA blows out. The one true inflection in the window.
**Verdict:** No structural degradation. CPA sat at ~$48.5 in both weeks. The trend is *flat-and-healthy* with a holiday spike bolted on the end.
### 2. Ad Group Breakdown (lifetime)
| Ad Group | Clicks | Spend | Conv | CVR | Est. CPA | Verdict |
|----------|--------|-------|------|-----|----------|---------|
**Carrying performance:** AG3 (efficiency) + AG1 (volume). **Dragging:** AG2+AG4 — combined **806 clicks / $1,261 / 14 conv = $90 CPA**, ~19% of spend at nearly **2× AG3's cost-per-lead**. The gap: both share the campaign's worst QS keywords, which floors their effective CPC no matter what the algorithm wants to do.
### 3. Keyword Efficiency Map
I have clicks + conversions per keyword but **not per-keyword cost** (that column isn't in context), so I'm mapping by CVR + volume. Exact per-keyword CPA needs a cost pull.
**🏆 Winners — protect these:**
| Keyword | Clicks | Conv | CVR | QS |
|---------|--------|------|-----|-----|
**💀 Losers — clicks, zero return:**
| Keyword | Clicks | Conv | QS | Action |
|---------|--------|------|-----|--------|
**⚠️ Highest-volume, worst-efficiency — the hidden drain:**
- **[PHRASE] canadian citizenship through parents — 737 clicks, 8 conv (1.09% CVR), QS 3.** This is the most-clicked keyword in the entire campaign and the worst converter among the big ones. It's the historical "$66-CPA leak" keyword. At ~$3+ CPC that's roughly **$150+ CPA** — 3× the campaign average, on the single biggest click bucket. This is where the money quietly goes.
**Untested potential:** `canadian citizenship by descent lawyer` converted this week ($27.26, 1 conv) as a **search term with no matching keyword** — "lawyer" = high commercial intent. Capture it as [EXACT].
### 4. Quality Score Audit — the controllable half of your cost problem
**12 of 35 keywords sit below QS 5.** The impact isn't academic: under Maximize Conversions, QS still drives Ad Rank and effective CPC — low QS is a direct tax on the $3.37 CPC you're asking about.
| Keyword | QS | Clicks | Why it matters |
|---------|----|--------|----|
**The leverage:** `through parents` (737) + `through ancestry` (469) = **1,206 clicks — a third of the campaign — sitting at QS 3.** Lifting these two from QS3→5+ is the single biggest *controllable* lever on the elevated CPC. The QS1 exact keyword is worse per-click but far lower volume. Fix order: the two big phrase keywords first.
### 5. Search Term Quality & Wasted Spend
Last 7 days, top 40 visible terms = **~$166 visible spend** (most spend is hidden below Google's privacy threshold, so this is a sample, not the total).
**Waste breakdown (visible):**
|----------|--------------|-----------|
**~35% of visible search-term spend is going to junk** (legislation + DIY intent). Extrapolating across hidden terms, call it **$60–80/week** — roughly 6–8% of total spend. Not catastrophic in %, but at $3–4/click each junk click now costs **2.5× what it did in June**. Every day these stay open costs more than it used to.
This confirms my Jul 4 audit exactly — same 6 negatives, ~$61.50/week. Still unexecuted.
### 6. Budget Allocation
**Not optimal, but the lever isn't manual.** AG1 absorbs **64% of spend** at $71 CPA; AG3 — your **$50-CPA best group** — gets only **17%**. Under Maximize Conversions you don't split budget by ad group directly; the algorithm allocates, and it *can't* route more into AG3 because AG3's keyword set is small and QS-limited. To feed AG3's superior economics, you expand its converting keyword coverage
**One flag on the daily budget itself:** the pinned schedule said "**→ $250/day on Jun 19**," but the daily data clusters tightly at **$145–155/day** (only Jul 4's holiday spike broke $250). Either the $250 step never went live or the campaign can't spend to it. **The operative ceiling looks like $150, not $250 — worth confirming**, because if you intended $250 you're leaving reach on the table on
### 7. Top 3 Strategic Recommendations (effort × impact)
| # | Action | Effort | Impact | Owner |
|---|--------|--------|--------|-------|
AG2/AG4's $90-CPA drag folds into #2 — it's the same QS-floor problem, and Maximize Conversions will self-correct once the QS tax lifts.
### ✅ Ready to Execute (my lane — say the word)
All **from real spend, all campaign-level, all [EXACT] or narrow [PHRASE]** — zero risk of clipping legitimate descent queries:
1. `[EXACT] bill c 3`
2. `[EXACT] canadian bill c 3`
3. `[EXACT] bill c 3 canada`
4. `[PHRASE] how to apply for`
5. `[EXACT] am i a canadian citizen`
6. `[PHRASE] what documents do i need`
7. **Pause** `[EXACT] grandparent canadian citizen` (medium-impact — I'll confirm before pausing)
The 6 negatives I can add in one shot via MCP and notify you (low-impact). The keyword pause I'll hold for your explicit "go." **Give me the green light and they go in immediately.**
One honest caveat: the negatives recover ~$60–90/week, but the bigger number is locked in **Recommendation #2** — the two QS3 phrase keywords carry a third of your clicks and are the real driver of the CPC you flagged. Negatives are the fast win; QS is the structural one.
— *Search Term Hunter*