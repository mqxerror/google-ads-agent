# Analytics Analyst Notes

**Last updated:** 2026-06-03 13:17

**Task:** whats your opinion on the search hunter report
- The real issue is: **0 conversions on $588 spend over 2 days** with decent CTR (11-18%) and 42 clicks. That points to a **landing page or conversion tracking problem**, not a search term problem.
- ### My recommendation
- 2. **Stop focusing on search term cleanup** — the terms are healthy

---

## Session Log

### 2026-04-14 15:50 — we did massive landing page and audit change and adcopy why we still have the lo

**Task:** we did massive landing page and audit change and adcopy why we still have the low qs? also should we wait till we get more data so we can compare also the budget now is 150
## QS — Why It's Still Low (and What to Do)
**Short answer: 2 days is not enough. QS is a lagging indicator.**
### Why QS hasn't moved yet
| Reason | Detail |
|--------|--------|
| **Too soon** | Landing page + ad copy changes were Apr 12. That's 2 days ago. Google needs **1–4 weeks** of accumulated data post-change before QS recalculates. |
| **Low impression volume** | QS updates require sufficient impressions per keyword. At ~140 impressions/day across 23 keywords, most keywords are getting <10 impressions/day. Google doesn't have enough signal yet. |
| **QS:1/2 keywords are structural** | `greece citizenship by investment` (QS:1) and `greece residency by investment` (QS:2) are low because the ad relevance score for "citizenship" intent is weak — the ads lead with "Golden Visa" framing, not "citizenship by investment." This is a copy mismatch, not a LP issue. |
| **Many keywords show QS:--** | 8 keywords have no QS yet — not enough impressions. These will populate over the next 2–3 weeks. |
### Should you wait?
**Yes — but not passively.**
The changes that need data to evaluate:
- LP impact on QS → wait 2 more weeks (measure Apr 26 vs Apr 12 baseline)
- Ad copy V4 → already scheduled for Apr 19 minimum
- Bidding changes → wait for more conversions (only 1 so far)
What you can do **right now** without needing data:
**Pause the 2 QS:1 keywords** — these were already flagged in yesterday's daily review and I was waiting for your approval:
| Keyword | QS | Clicks | Cost | Why Pause |
|---------|-----|--------|------|-----------|
Pausing these removes the worst QS drag from the campaign average and stops the bid premium waste. Low blast radius — they're only 9 clicks of your 138 total.
### On the $150 budget change
Good move. You were spending ~$120/day in learning phase, so $150 gives the algorithm room without the $200+ overspend risk from the pre-learning period. No issues here.
**Bottom line:** QS will move — just not yet. The LP and copy changes were the right calls. Give it until Apr 26 for a meaningful comparison. In the meantime, let me pause those 2 QS:1 keywords now — want me to execute?
*— Analytics Analyst*

### 2026-04-18 18:00 — I received the test lead , also I have trueconversion like clarity , I didnt cre

**Task:** I received the test lead , also I have trueconversion like clarity , I didnt created a session recording for reece but I have for Portugal which is same result like Greece https://app.truconversion.co

**Critical Details:** GTM-K6864NBH
Good — test lead confirmed means the form and webhook pipeline work. Let me do both tasks in parallel: check the TrueConversion heatmap and install Clarity via GTM.## Status Update
### Clarity Installed — Live Now
**Microsoft Clarity is now active on goldenvisas.mercan.com** (all pages):
- GTM-K6864NBH → Version 7 published
- Tag: "Microsoft Clarity - All Pages" (Custom HTML)
- Project ID: `3149465520228862`
- Verified: `clarity.ms/tag/3149465520228862` loading on `/greece-golden-visa`
Session recordings, heatmaps, and scroll depth will start collecting immediately. You'll have actionable data within **24-48 hours**.
### TrueConversion Heatmap — Link Expired
The shared link returned **"Heatmap not Available — expired or does not exist."** You'll need to regenerate a fresh share link from TrueConversion if you want me to analyze it. Alternatively, we can wait for Clarity data since it's now installed.
### Where We Stand (The Real Problem)
| Metric | Value | Expected |
|--------|-------|----------|
The form works. Tracking works. **Users are clicking but not converting.** Until we have Clarity session recordings (give it 2-3 days), the next diagnostic step is a fresh CRO audit of the live `/greece-golden-visa` page to identify what's pushing users away.
**Options right now:**
1. **Regenerate the TrueConversion link** so I can see Portugal's heatmap (you said same pattern as Greece)
2. **Wait 48hrs for Clarity data** then analyze session recordings
3. **Run a CRO audit now** on the live page — I can check copy, form UX, mobile layout, page speed
4. **All of the above**
What do you want to prioritize?
*— Analytics Analyst*

### 2026-04-18 18:12 — check the Portugal ads if they use https://goldenvisas.mercan.com/portugal-golde

**Task:** check the Portugal ads if they use https://goldenvisas.mercan.com/portugal-golden-visa as landing page in ads the truecoversion report is for an old landing page
Let me pull the Portugal campaign ads. First I need the Portugal campaign's ad groups.## Portugal Ads — URL Check Complete
**Good news: All active Portugal ads ARE already using the new landing page.**
| Ad Group | Ad ID | Status | Final URL |
|----------|-------|--------|-----------|
All 5 enabled ads → `goldenvisas.mercan.com/portugal-golden-visa` ✅
The 13 **paused** ads all point to the old URL (`mercan.com/business-immigration/portugal-golden-visa-program/`).
### What This Means for the Heatmap Analysis
**The TrueConversion scroll heatmap you shared was from the OLD landing page** (`mercan.com/...`), not the current one. The page structure, form position, and scroll depth data may be completely different on the new `goldenvisas.mercan.com/portugal-golden-visa` page.
My earlier diagnosis — "form buried at 85-90% scroll depth" — **may not apply to the current page.** The new page could already have the form higher up.
**Want me to open the live `goldenvisas.mercan.com/portugal-golden-visa` page and check where the form sits?** That will tell us if the same scroll-depth problem exists on the page your ads are actually sending traffic to.
*— Analytics Analyst*

### 2026-06-03 13:17 — im planning a campaign in Silicon Valley in usability like Indiana and high paid

**Task:** im planning a campaign in Silicon Valley in usability like Indiana and high paid workers in there who might have h1b visa or similar that could be cancelled so im targeting those people and investor l
## Geo + Audience Targeting Report — H1B / High-Income Tech Workers → Greece Golden Visa
This is exactly the **"Plan B" / family-safety hedge** angle that's the highest-value messaging lever in this account. An H1B holder whose status can be revoked on a layoff (60-day grace period) is the textbook investor-migration buyer: high income, capital access, and a concrete personal-instability trigger. Strong fit.
One hard limitation up front: **Google Ads cannot target "H1B visa holders" directly** — there's no such audience or demographic. We reach them by stacking three proxies: **geography** (where they cluster) × **income** (top brackets) × **intent/affinity audiences** (relocation, EU residency, investment). Below is how.
### 1. WHERE the ads should serve (geo tiers)
H1B and high-comp tech talent is heavily metro-concentrated. Target by **metro area (DMA/city), not whole states** — statewide wastes spend on rural ZIPs. Recommended tiers with suggested bid posture:
**Tier 1 — core, highest density (bid +15–25%)**
| Metro | Why |
|---|---|
| San Jose–Sunnyvale–Santa Clara, CA | Silicon Valley core — highest H1B density in the US |
| San Francisco–Oakland, CA | Big Tech + startups |
| Seattle–Bellevue–Redmond, WA | Amazon, Microsoft |
| New York–Newark–Jersey City (incl. Edison, NJ) | Finance-tech + the largest Indian-IT consulting cluster |
**Tier 2 — large secondary hubs (bid baseline)**
| Metro | Why |
|---|---|
| Dallas–Fort Worth (Plano, Irving), TX | Major IT-consulting / H1B hub |
| Austin, TX | "Silicon Hills" |
| Boston–Cambridge, MA | Biotech + tech |
| Washington DC / Northern Virginia (Arlington) | Gov-tech, Amazon HQ2 |
| Chicago, IL | Consulting + enterprise tech |
| Atlanta, GA | Growing tech / fintech |
**Tier 3 — emerging / consulting-heavy (bid –10%, test)**
| Metro | Why |
|---|---|
| Raleigh–Durham, NC (Research Triangle) | Tech + pharma |
| **Indianapolis, IN** | Validates your Indiana instinct — Infosys built a major hub here; real H1B presence |
| Phoenix, AZ · Charlotte, NC · Houston, TX | Secondary IT/finance clusters |
> Practical note: 14 metros at one $50–200/day budget will spread too thin. **Start with Tier 1 + 2 Tier-2 metros**, prove CPL, then expand. Use location bid modifiers, not separate campaigns, so the algorithm keeps one conversion pool.
### 2. HOW to layer audiences on top of geo
Geography alone still catches retirees and tourists. Stack these (start as **"Observation,"** not "Targeting," so you gather data before you restrict):
- **Custom Intent / Search audiences** — people recently searching: *H1B layoff, visa sponsorship, green card backlog, EU residency, second passport, golden visa, relocate from US*.
- **In-market segments** — *Real Estate Investment*, *Immigration & Relocation Services*, *Business Services > International*.
- **Affinity** — *Technophiles*, *Avid Investors*, *Frequent International Travelers*.
- **Demographics — household income:** top **10%** and **11–20%** brackets (set lower-bracket bid modifiers negative). This is the single most useful overlay for an HNW/capital-holder product.
### 3. Messaging angle (this is where the lift is)
Lead with **visa precarity → Plan B**, not "buy Greek property." For the H1B segment specifically:
- *"Your status shouldn't depend on one employer."*
- *"Secure EU residency for your whole family — before you need it."*
- *"From €250K: a permanent backup plan in Europe."*
CTA stays account-standard: **"Request a Free Consultation."** No eligibility/quiz language (capital = qualified). Frame as a real-estate investment granting EU residency — never as visa paperwork.
### 4. Implementation notes
- This builds naturally on your **paused V2 campaign (`23722199501`)** — add the metro location targeting + income/audience layers there, or I can spin up a dedicated geo-segmented variant. Either way I'll keep writes on the correct campaign only.
- Set audiences to **Observation first**, run 7–14 days, then convert the winners to bid adjustments.
- Expect **low impression volume** — that's correct for this vertical; optimize on CPL and consultation rate, not impressions.
**Next step — pick one and I'll execute:**
1. Resolve the exact Google geo-target IDs for your chosen metros (I'll pull them via the geo tool), or
2. Apply Tier-1 metro targeting + income (top 10%) + observation audiences to the V2 campaign so it's ready to enable.
Which campaign should this live on — the paused **V2 (`23722199501`)**, or a new dedicated geo campaign?
*— Analytics Analyst (Dam3oun-Google)*
