# Analytics Analyst Notes

**Last updated:** 2026-04-14 11:34

**Task:** I ve did the changes on /portugal-golden-visa redo the audit and compare
Let me open the updated page and run a fresh audit. I'll check Chrome first, then do performance, DOM, visual, and tracking analysis in parallel.
Let me open the updated Portugal page and start the audit.Chrome isn't running. Let me launch it.Page loaded. Let me run the performance trace, take a screenshot, and analyze the DOM all in parallel.Massive changes visible already. The H1 is fixed, form is in the hero above fold, dual CTA, Plan B messaging, schemas added. Let me now do the full-page screenshot, Lighthouse audit, and mobile check i
# Re-Audit Report — Portugal Golden Visa Landing Page (v2)
## `/portugal-golden-visa` vs old `/portugal` vs Greece `/greece-golden-visa`
## HEADLINE: CRO Score **75 → 89/100 (B+)** — a 14-point jump
You implemented nearly every item from the Greece playbook. The page is dramatically improved. But there are **2 critical blockers** that need immediate attention before this page can go live on the campaign.
## 🚨 CRITICAL BLOCKERS (Fix Before Going Live)
### 1. `robots: noindex, nofollow` — THE PAGE IS HIDDEN FROM GOOGLE
The meta robots tag is set to **`noindex, nofollow`**. This means:
- Google **will not index** this page — no organic traffic
- Google's ad quality evaluator **may not be able to crawl** it — hurts Quality Score
- Lighthouse SEO dropped from **100 → 69** because of this single tag
**If this is intentional (staging)** — fine, remove it when ready to go live.
**If this is accidental** — fix it NOW. Change to `index, follow` or remove the tag entirely.
### 2. Campaign Ads Point to OLD URL `/portugal`
The campaign's `final_urls` still point to `goldenvisas.mercan.com/portugal` (or `mercan.com/...`). The new page is at `/portugal-golden-visa`. You need to either:
- **Option A:** Update all ad `final_urls` to `goldenvisas.mercan.com/portugal-golden-visa`
- **Option B:** Set up a 301 redirect from `/portugal` → `/portugal-golden-visa`
Without this, ad traffic goes to the OLD page and all your improvements are invisible to paid users.
## Head-to-Head Score Comparison (3-Way)
| Category | Old `/portugal` | **New `/portugal-golden-visa`** | Greece `/greece-golden-visa` | Change |
|----------|:---:|:---:|:---:|:---:|
## What You Nailed (Greece Playbook Items Implemented)
| Feature | Status | Evidence |
|---------|:------:|---------|
| **Dual CTA (Consult + Brochure)** | ✅ | "Schedule a Free Consultation" + "Download Investment Brochure" |
| **Program cross-sell tabs** | ✅ | Portugal 🇵🇹 / Greece 🇬🇷 / Panama 🇵🇦 flag-icon tabs on form |
| **FAQPage schema** | ✅ | JSON-LD present |
| **Organization schema** | ✅ | JSON-LD present |
| **BreadcrumbList schema** | ✅ | JSON-LD present |
| **"Plan B" emotional messaging** | ✅ | Hero sub-headline: "Thinking about a Plan B? EU residency for your family..." |
| **Processing timeline** | ✅ | Documentation → Fund Investment → Application → Approval & Residency |
| **OG tags** | ✅ | Title, description, image, Twitter card all set |
| **Canonical URL** | ✅ | Correctly set to `/portugal-golden-visa` |
## Performance Deep-Dive
| Metric | Old `/portugal` | New `/portugal-golden-visa` | Greece | Verdict |
|--------|:---:|:---:|:---:|:---:|
The LCP improvement from 2.17s → 1.0s is excellent. TTFB is slightly higher (702ms vs 427ms) but still within "Good" range. The SEO score drop is entirely caused by the `noindex` meta tag.
## What's Still Missing (5-Point Gap to Greece)
| # | Item | Greece Has | Portugal Missing | Impact | Effort |
|---|------|:---:|:---:|:---:|:---:|
## Revised CRO Score Projection
| Scenario | Score | Grade |
|----------|:-----:|:-----:|
**Remove the `noindex` tag and update the campaign URLs → you're at Greece parity.**
## Before / After Summary
|---------|-----------------|----------------|
| URL | `/portugal` | `/portugal-golden-visa` |
| Emotional messaging | None | **"Plan B", "Your Family", urgency** |
| E-E-A-T attribution | None | **"Reviewed by Jason Morgan" + date** |
## Action Items (Priority Order)
| # | Action | Urgency | Owner |
|---|--------|---------|-------|
**Bottom line: The page transformation is excellent — you've closed 14 of the 19-point gap with Greece in one sprint. The two remaining blockers (`noindex` + URL mismatch) are 5-minute fixes that will unlock the full value of everything you built. Once those are done, Portugal matches Greece at 92-94.**
— *Analytics Analyst*