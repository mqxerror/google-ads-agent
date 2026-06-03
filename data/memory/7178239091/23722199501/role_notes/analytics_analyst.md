# Analytics Analyst Notes

**Last updated:** 2026-04-18 18:12

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
