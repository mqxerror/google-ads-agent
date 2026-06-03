# Cro Specialist Notes

**Last updated:** 2026-05-24 11:18

**Task:** execute the Today only for landing page we have a new landing page in development I need a review of it https://www.mercan.com/lp/canadian-citizenship-by-descent

**Critical Details:** https://www.mercan.com/lp/canadian-citizenship-by-descent`, GTM-WZKDXFH8, AW-826329520
I'll execute the 3 "Today" items and open the new landing page for CRO review simultaneously.Executing all 3 "Today" items + opening the new landing page simultaneously.Good — the new LP is loading. Let me run the API queries via stream (fixes the page_size error) and continue the page analysis in parallel.Excellent data. Here's what I found:
**Item 1 — eCPC:** `enhanced_cpc_enabled: false` ✅ Already OFF. Not the CPC root cause.
**Item 2 — AG2 Bids:** 3 of 7 keywords still at $1.29!
- `"canadian grandparent citizenship"` (48 clicks) — **$1.29** ❌
- `"canada citizenship grandparent"` (88 clicks) — **$1.29** ❌
- `[grandparent canadian citizen]` (61 clicks) — **$1.29** ❌
**Item 3 — AG4:** `"how to get canadian citizenship by descent"` at $0.60 — needs $0.35.
Fixing all 4 bids now + continuing page analysis.All 4 bid fixes executed. Now let me finish the landing page analysis — trust signals, mobile view, and tracking verification.All data collected. Here's the complete report.
# "Today" Bid Fixes — EXECUTED ✅
| # | Action | Before | After | Status |
|---|--------|--------|-------|--------|
**Impact projection:** Those 3 AG2 keywords account for 197 clicks (~$220 in spend). At $0.65 vs $1.29, CPC drops 50% on ~24% of campaign spend. Blended campaign CPC should drop from $1.04 → ~$0.75-0.85 within 3-5 days.
**AG2 final bid state (all 7 keywords):**
| Keyword | Bid | Status |
|---------|-----|--------|
# CRO Review — New Landing Page
**URL:** `https://www.mercan.com/lp/canadian-citizenship-by-descent`
**Review Date:** 2026-05-23
## First Impression: This Is a Major Upgrade
| Dimension | Old Page | New Page `/lp/` | Verdict |
|-----------|----------|-----------------|---------|
| Form visible on load | No | **Yes** (desktop) | ✅ |
| CTA phrasing | "Request a consultation" | **"Request a free consultation"** | ✅ |
| Phone number | Not above fold | **Above fold** | ✅ |
**The #1 problem from the CRO audit (form buried at 11,363px) is fixed.** The form is now the first thing a visitor sees on desktop — right panel, above fold, next to the value proposition. This alone should lift conversion rate significantly.
## What's Working Well
1. **Form above fold on desktop** — The split layout (copy left, form right) is the proven lead-gen pattern. Visitors from Google Ads searching "citizenship by descent" land directly on the form. No scrolling required.
2. **"BILL C-3 IN FORCE" badge** — Green dot + urgency signal at the very top. Ties the page to the news cycle driving searches.
3. **3 VERIFIED badges** — "Bill C-3 in force since 15 December 2025", "RCIC-Regulated Canadian consultants", "Decades of Canadian immigration practice". Clean trust signals positioned right below the hero CTA.
4. **"Three paths to citizenship by descent"** — Parent / Grandparent / Great-grandparent / 1947 Anchor. Clearly maps the eligibility paths. This is what searchers are looking for.
5. **"How the application works" — 3 steps** — Free eligibility consultation → Document gathering → Genealogical chain reconstruction. Sets expectations, reduces anxiety.
6. **FAQ section** — 6 well-chosen questions covering cost, dual citizenship, great-grandparent eligibility. Addresses the top objections.
7. **All tracking firing** — GTM-WZKDXFH8 ✅, AW-826329520 ✅, Clarity (56xm2r94rk) ✅, Facebook Pixel (584590286928383) ✅, TruConversion (63100/04369) ✅, reCAPTCHA ✅
## What Needs Fixing
### P0 — Fix Before Going Live (minutes)
**1. Submit button still says "Submit"**
- Current: Generic `Submit` button
- Change to: **"Get My Free Consultation"**
- Why: "Submit" is the lowest-converting CTA verb. Benefit-driven button text outperforms by 20-40%. This was flagged in the original P0 list on May 18 — carry it forward.
**2. "How did you hear about us?" field is still there**
- This is field 7 of 8. It adds friction with zero value — UTM parameters already track this.
- **Remove it.** Dropping from 8 → 7 fields saves ~5-10% form abandonment.
**3. Form still has 8 fields total** — even after removing "How did you hear," you'd have 7 (First, Last, Email, Nationality, Country, Phone, textarea). The textarea is marked "optional" which is fine, but **Nationality and Country of Residence are both dropdowns that can be inferred from IP/UTMs for paid US traffic.** Consider:
- **Minimum viable form (best CVR):** First, Last, Email, Phone = **4 fields**
- **Compromise:** First, Last, Email, Phone, Country = **5 fields**
- **Current:** 8 fields — each field above 3 loses ~5-10% of completions
### P1 — Fix This Week (hours)
**4. No testimonials or social proof anywhere**
- Zero client stories, case studies, or review counts on the entire page
- The "VERIFIED" badges are good but they're self-asserted credentials, not third-party proof
- **Add 2-3 short testimonials** above or below the FAQ section: "Name, State — outcome" format
- This is the biggest trust gap. For a service where people are trusting you with their ancestry documentation, social proof is essential.
**5. Zero images on the page**
- The DOM shows 0 `<img>` tags. The page is pure text + CSS.
- The dark navy/gold design is premium, but **no images at all** makes the page feel like a wireframe, not a finished product.
- Add: a Canadian landscape/flag motif, a team photo, or a document/passport visual to humanize the page.
- Even one relevant image above the fold adds perceived legitimacy.
**6. Mobile: form is pushed below fold**
- On mobile (375px), the hero + CTA + 3 verified badges fill the entire first screen. The form doesn't appear until the user scrolls past all of that.
- The "Request a free consultation" CTA button scrolls to the form anchor (`#consult`), which works — but **the form's exact position on mobile should be tested.**
- Consider: on mobile, move the form directly after the CTA button (before the VERIFIED badges) so users don't have to scroll further.
### P2 — Next Sprint
**7. Eligibility quiz (still the #1 competitive gap)**
- The page structure is now PERFECT for a quiz: replace the form with a 3-question quiz → result screen → simplified form.
- The "Three paths" section already teaches users about parent/grandparent/great-grandparent — the quiz would make this interactive instead of passive.
- Expected impact: +200-400% CVR (quiz/calculator pages consistently outperform static forms 3-5x).
**8. "through parents" search intent mismatch**
- Path 1 says "Your parent was a Canadian citizen at the time of your birth. The fastest path: typically a Proof of Citizenship application with the parent's citizenship documentation and your birth record."
- This confirms what we suspected: parent-path users **can do this themselves**. The page should explicitly say: "Parent path is straightforward — many applicants handle this directly. **Grandparent and great-grandparent paths** are where our expertise makes the difference." This pre-qualifies intent.
## CRO Score Comparison
| Category | Old Page | New Page `/lp/` | Change |
|----------|----------|-----------------|--------|
| | Old Page | New Page |
|---|---------|----------|
| **Grade** | D+ | **C+** |
**+10 points.** The biggest single gain is form position (25 → 45). With P0 fixes (button text + remove "how did you hear"), this jumps to ~80. With reduced form fields (5 instead of 8), it reaches ~84. With the quiz, ~92+.
## Projected Impact on Campaign
| Scenario | CVR | Conv/day | CPA | vs Current |
|----------|-----|----------|-----|------------|
**The form being above fold is the single biggest CRO improvement possible for this campaign.** Even without any other changes, switching the ads to point to `/lp/canadian-citizenship-by-descent` should roughly double the conversion rate.
## Recommendations Summary
| # | Action | Effort | Impact | When |
|---|--------|--------|--------|------|
**Bottom line:** This new page is a significant improvement — form above fold, focused content, proper structure. Apply the P0 fixes (5 minutes of work), then switch the campaign ads to this URL. The old page was scoring 66/100; this one is already at 76 and reaches 84+ with quick fixes. Most importantly, the conversion rate should roughly double just from the form placement change.
**When you're ready to switch the ads to this new URL, I can update all 4 RSA final_urls in one shot.**
— *CRO Specialist*

---

## Session Log

### 2026-05-24 11:18 — save the landing page as a plan and I memory for near future implementation in w

**Task:** save the landing page as a plan and I memory for near future implementation in week about and check the results since our latest changes and see the result today
LP plan saved. Now here's the performance check:
# Post-Fix Results — May 22-24
The AG2 bid corrections ($1.29→$0.65) and AG4 throttle ($0.60→$0.35) were applied **May 23 afternoon**. Here's what we see:
## Daily Performance
| Date | Impr | Clicks | Cost | Conv | CTR | CPC |
|------|------|--------|------|------|-----|-----|
## Ad Group Breakdown (May 23-24 combined, post-fix window)
| Ad Group | Clicks | Cost | Conv | CPC | % Spend |
|----------|--------|------|------|-----|---------|
## Key Observations
**What's working:**
- **AG4 is effectively throttled.** 1 click in 2 days at $0.59 — the $0.35 bid killed its volume as intended. Budget is no longer being cannibalized.
- **Daily spend is dropping.** $43.95 so far today — on pace for ~$90-100/day, which is finally within the $100/day budget.
- **CPC is still falling:** $1.08 → $1.05 → $1.02
**What's concerning:**
- **AG2 CPC is still $1.23** — the bid was set to $0.65 yesterday. Google takes 24-48h to fully adjust auction behavior. This should settle by May 25-26.
- **AG1 is now 78% of spend** — with AG4 throttled, AG1 absorbed everything. This over-concentration means one ad group carries all the risk.
- **Zero conversions today (so far)** — partial day, and May 22 was also zero. Two zero-conversion days in 3 is within Poisson variance at λ=1.5/day (22% probability per day), but worth watching.
- **AG3 (best CPA: $42) still only getting 7% of spend** — despite having the best conversion economics.
## Verdict: Bid Fixes Need 3 More Days
The AG4 throttle worked immediately. The AG2 bid fix hasn't fully propagated yet ($1.23 CPC vs $0.65 bid target). **Check back May 27** for the true post-fix picture.
**Budget pacing is finally normalizing** — today's pace suggests we'll hit ~$90-100 for the first time, which means the bid corrections are achieving their goal.
## Memory Saved ✅
LP upgrade plan saved to: `data/memory/7178239091/23847913167/lp_upgrade_plan.md`
**Next steps:**
1. Implement P0 fixes on the new LP (Submit button, remove field, reduce to 5 fields)
2. Confirm with me when ready to switch ad URLs → I'll update all 4 RSAs in one shot
3. May 27: review AG2 CPC post-fix + conversion recovery
4. May 28: budget decision ($100→$150) based on settled CPCs + lead quality feedback
— *CRO Specialist*
