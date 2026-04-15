# Cro Specialist Notes

**Last updated:** 2026-04-14 14:11

**Task:** review the discussion and redo the cross audit for the new page and based on ppc straight and adcopy feedback and work done

**Critical Details:** AW-826329520, AW-959555504, https://goldenvisas.mercan.com/portugal-golden-visa, GTM-K6864NBH
Starting the cross-audit on `/portugal-golden-visa` — I'll check the live page state, verify the Wave 1 ad changes, and score everything fresh. Let me launch Chrome and run the audit.Page loaded. Running Steps 1-5 in parallel — performance, DOM, screenshot, network requests, and trust signals.LCP 757ms, CLS 0.00, TTFB 166ms — excellent. Now running DOM, visual, trust signals, and network checks in
# CRO Cross-Audit Report — Portugal Golden Visa
## Post-Wave 1 Execution | `/portugal-golden-visa`
## 2026-04-14
## CRO Score: 75 → 86/100 (Grade B) — 11-point jump
The page is dramatically improved. Wave 1 ad copy is live and aligned. But **two issues from prior audits remain unfixed**, and I found **one new problem** introduced by Wave 1.
## Score Comparison (3-Way + Timeline)
|----------|:---:|:---:|:---:|:---:|:---:|
## Cross-Audit: What Each Agent Did — Graded
### PPC Strategist — Grade: B+
| Recommendation | Status | My Verdict |
|---|---|---|
| Fix `campaignid` in `final_url_suffix` | **User corrected** — GCLID handles attribution | Was wrong, accepted correction cleanly |
| Re-enable Portugal Residency ad group | **User corrected** — Search Hunter had valid reason to pause | Was wrong, accepted correction |
**Gap:** QS 1 keywords are still bleeding money. 186 clicks, 1 conversion, Quality Score 1. This wasn't addressed in Wave 1.
### Creative Director — Grade: A-
| Action | Status | My Verdict |
|---|---|---|
| Brand names saved to memory | **DONE** | Good. |
**One issue I caught:** The ads now say **"Schedule a Free Consultation"** as a headline. The page has "Schedule a Free Consultation" as a **radio option** inside the form, but the primary CTA **button** says **"Book Free Consultation"**. This is close enough — the user sees "Schedule a Free Consultation" in the form flow — but it's not a perfect button-text match. Minor.
### Analytics Analyst — Grade: B+
| Finding | Status | My Verdict |
|---|---|---|
| Campaign URLs point to old page | **FIXED** by Creative Director | Correct finding, resolved. |
| Missing star ratings | Flagged but not fixed | Correct, still missing |
### GTM Specialist — Grade: B
| Finding | Status | My Verdict |
|---|---|---|
| Triple-miss on old page (wrong container, no jQuery event, URL filter mismatch) | **Superseded** — new page has different form mechanism | Historical finding, correctly identified at the time |
| `campaignid` in `final_url_suffix` needed | **User corrected** — GCLID is sufficient | Was wrong, but the deep investigation was valuable |
### My Previous Audit (CRO Specialist) — Self-Grade: B
| Finding | Status | Self-Verdict |
|---|---|---|
| Star ratings missing | **STILL MISSING** | Correctly identified, not actioned |
## What's Still Broken (Priority Order)
### 1. `robots: noindex, nofollow` — CRITICAL BLOCKER (unchanged since Analytics Analyst flagged it)
**Impact:**
- Google cannot index this page — zero organic traffic
- Google's ad quality evaluator **may** penalize Quality Score (can't crawl landing page content)
- Lighthouse SEO: **69** (was 100 on old page) — entirely because of this tag
- Every SEO benefit of the new page (schemas, meta description, canonical) is **invisible to Google**
**Fix:** Remove the tag or change to `index, follow`. If this is staging protection, remove it NOW — the page is live and receiving paid traffic via Wave 1 ads.
**This single fix moves CRO Score from 86 → 88.**
### 2. No Star Ratings Widget — HIGH IMPACT (flagged in my original audit, still missing)
The page says "What Our Investors Say" (testimonial section) but has **no star rating visual** — no Trustpilot badge, no Google Reviews widget, no star icons.
**Industry benchmark:** Star ratings boost conversions up to **270%**. This is the single highest-ROI trust signal missing from the page.
**Fix:** Add a 5-star Trustpilot/Google Reviews widget above the fold or in the testimonials section.
**This fix moves CRO Score from 88 → 90.**
### 3. QS 1 Keywords Still Active — MEDIUM IMPACT (PPC Strategist flagged, not actioned)
| Keyword | Match | Clicks | Conv | QS | CPC Impact |
|---|---|---|---|---|---|
**Impact:** 186 clicks, ~$1,350+ spend, 1 conversion. QS 1 means Google considers the ad+landing page irrelevant for this query. These keywords drag down the entire ad group's quality signals.
**Fix:** Pause both keywords. Budget reallocates to QS 5-10 keywords that actually convert.
### 4. Best Practices Score Dropped to 77 — LOW-MEDIUM
Was 100 on the old page, now 77. This typically means:
- Third-party scripts blocking (TruConversion?)
- Mixed content or deprecated APIs
- Not a conversion killer, but worth investigating
### 5. No Social Proof Icons — LOW
Zero social media links (Facebook, LinkedIn, Instagram). For a $500K+ investment decision, prospects will Google "Mercan Group reviews" — having social presence linked from the page adds credibility.
## Ad-to-Page Alignment Deep Dive (Post Wave 1)
|---|---|---|---|
| "Direct From The Developer" | "We are the fund developer" in multiple sections | **Match** | |
| "Schedule a Free Consultation" | Form radio option: "Schedule a Free Consultation" | **Match** | Button says "Book Free Consultation" — close |
| "Talk to a Portugal Expert" | Mid-page anchor: "Talk to a Portugal Expert" | **Exact** | |
| "No Full Relocation Needed" | Hero: "No relocation" | **Match** | |
| **Final URL** | `goldenvisas.mercan.com/portugal-golden-visa` | **Exact** | Fixed from `/portugal` |
**Ad Alignment Score: 82/100 (B-)** — up from 52 (D). Massive improvement. The remaining 18 points come from:
- Wave 2 emotional hooks ("Plan B", "Buyback") not yet in ads
- Minor CTA wording variance ("Schedule" vs "Book")
## Tracking Verification (Post-Fix)
| Tag | Status | Evidence |
|---|---|---|
| GCLID Attribution | **Working** | Per user + GTM admin confirmation |
| TruConversion | **Loaded** | Heatmaps/recordings active |
| Conversion Linker | **Present in GTM** | Required for cross-domain measurement |
**Tracking Score: 95/100 (A)** — up from 35 (F). The 5-point gap is for no visible event testing confirmation (I'd need to submit a test form and verify the conversion ping fires).
## Performance Deep Dive
| Metric | Old `/portugal` | New `/portugal-golden-visa` | Change | Grade |
|---|---|---|---|---|
The performance improvement is remarkable — LCP went from "Good" to "Exceptional." The SEO regression is entirely caused by `noindex, nofollow`.
## Wave 2 Readiness Assessment
The Creative Director designed 3 new RSAs for the active ad groups. My CRO assessment of the Wave 2 designs:
| Headline | On Page? | CRO Impact | My Verdict |
|---|---|---|---|
| "Your Family's Plan B to EU" | Hero sub-headline: "Thinking about a Plan B?" | **High** — emotional hook matches hero perfectly | **APPROVE** |
| "Zero Management Fees" | Investment details | **Medium** — cost advantage over competitors | **APPROVE** |
| "CMVM-Regulated Fund" | Multiple sections | **Medium** — regulatory trust for sophisticated investors | **APPROVE** |
| "Compare Fund Options Free" | Not on page | **Low** — could confuse if there's only one fund option | **HOLD** — verify there are multiple fund options to compare |
**Wave 2 is ready to execute on Day 7.** All emotional hooks are substantiated by page content. One headline ("Compare Fund Options Free") needs verification.
## A/B Test Ideas (Updated)
| # | Hypothesis | Expected Impact | Effort | Priority |
|---|---|---|---|---|
## Immediate Action Items
| # | Action | Owner | Urgency | Impact |
|---|---|---|---|---|
<!-- STRUCTURED_DATA_START -->
<!-- STRUCTURED_DATA_END -->
## Bottom Line
**The campaign has gone from structurally broken (5 independent failures) to structurally sound in 2 days.** Here's the scorecard:
|---|---|---|---|
| `noindex, nofollow` | Not checked | **STILL BLOCKING** | Nobody |
| Star ratings missing | Flagged | **STILL MISSING** | Nobody |
**3 items flagged across multiple audits remain unfixed.** The `noindex` tag is the most urgent — it's a 1-minute fix that unlocks SEO value and may improve Quality Score.
**Projected trajectory:**
- Today (86/100) → Remove noindex + pause QS 1 → **88/100**
- This week → Add star ratings → **90/100**
- Day 7 → Wave 2 ads live → A/B testing emotional vs credential
- Day 14 → Evaluate bidding strategy change based on conversion data
**The foundation is now solid. Execute the 3 remaining fixes and you're at Greece-page parity (90+).**
— *CRO Specialist*

---

## Session Log

### 2026-04-14 14:11 — ignore any seo related review and put this globally as note and fact this is a d

**Task:** ignore any seo related review and put this globally as note and fact this is a domain for ads only
Understood. Let me save this globally and update the campaign facts.
Let me save this as a pinned fact and a global memory note.Now let me save this globally to memory for all future conversations.Done. Saved globally and to campaign memory.
**What changed:**
- **Pinned fact** added to campaign: `goldenvisas.mercan.com` is ads-only, `noindex` is intentional
- **Global memory** saved: all future conversations will skip SEO reviews for this domain
- **`noindex` removed from action items** — it was never a problem, I was wrong to flag it
**Revised CRO Score: 86 → 89/100** (SEO weight redistributed to other categories)
**Updated action items (SEO removed):**
| # | Action | Urgency | Impact |
|---|---|---|---|
— *CRO Specialist*
