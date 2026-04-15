# Gtm Specialist Notes

**Last updated:** 2026-04-11 15:53

**Task:** provide what instruction for gtm setup for other campaigns MENA and portugal campaign after that redo the pro audit for the local page http://localhost:4000/greece

**Critical Details:** AW-826329520, https://goldenvisas.mercan.com/greece, https://goldenvisas.mercan.com/, http://localhost:4000/greece`., https://schema.org, GTM-NXRDJPT, GTM-K6864NBH
## GTM Setup for Portugal & MENA Campaigns
Based on what we established yesterday: **no additional GTM setup is needed.** Here's why:
| Component | Status | Why |
|-----------|--------|-----|
| Conversion Linker | ✅ Fires on all pages | Stores GCLID cookie for every ad click |
| GCLID attribution | ✅ Automatic | Google matches conversion → click → campaign → ad group → keyword |
**The "GV Lead" conversion action (ID: 7546023021, label: `fc6FCO3YnI4cELCTg4oD`) is the ONLY conversion action needed.** GCLID tells Google which campaign gets credit. No per-program labels required.
### What Each Campaign Team Needs to Do
**Portugal Campaign:**
1. Ensure ads link to `goldenvisas.mercan.com/portugal` (or whatever the Portugal LP path is)
2. Verify tracking template passes `{campaignid}` in the URL
3. Set "GV Lead" as the campaign's primary conversion goal in Google Ads settings
4. Deploy the consent mode fix (same developer prompt from yesterday)
5. Done. No GTM changes.
**MENA Campaign:**
1. Same as above — ads link to the MENA landing page on `goldenvisas.mercan.com`
2. Same tracking template with `{campaignid}`
3. Set "GV Lead" as primary conversion goal
4. **Extra consideration:** MENA targets Middle East where GDPR-like laws may apply (UAE PDPL, Saudi PDPA). The consent mode fix should use region-specific grants:
5. **Known issue from notes:** MENA has phantom conversions (3-5 AM firing) — likely bot traffic. Consider adding bot filtering or time-of-day exclusions.
### Cleanup To-Do (Not Urgent)
| Item | Action | Priority |
|------|--------|----------|
| Greece GV - Conversion tag (GTM) | Can be paused — direct gtag handles it | LOW |
| Portugal GV - Conversion tag (GTM) | Can be paused — same reason | LOW |
| GV Landing Page - Conversion tag (GTM) | Can be paused — same reason | LOW |
| Old container GTM-NXRDJPT | Remove from site if still present | MEDIUM |
**Bottom line:** The GTM infrastructure is already done. One conversion action, GCLID attribution, consent fix = all campaigns tracked. No complexity.
Now let me audit the local page at `http://localhost:4000/greece`.
Let me open the local page and start the audit.Good — the hero section looks updated since last audit. I can see they've already added "path to Greek citizenship after 7 years" in the sub-copy. Let me scroll through the full page and get the DOM structure.Full page screenshot failed (page too long). Let me read the snapshot and scroll through sections manually.The page has been **massively updated
# CRO PRO AUDIT — `localhost:4000/greece` (2026-04-11)
## EXECUTIVE SUMMARY
**Previous Score (2026-04-10): 80/100 (B)**
**Current Score: 92/100 (A)**
The dev team executed the majority of Phase 1 and Phase 2 CRO recommendations. The page went from a property-focused pitch with a buried form to a comprehensive, intent-matching Golden Visa landing page with strong conversion architecture.
## CRO CHECKLIST — WHAT WAS IMPLEMENTED
| # | Recommendation | Status | Notes |
|---|---------------|--------|-------|
## LIGHTHOUSE SCORES (Mobile)
| Category | Score | Previous | Change |
|----------|-------|----------|--------|
**3 Failed Audits:**
1. **Color contrast** — some text elements don't meet WCAG AA ratio (likely muted gray text on dark navy)
2. **Links rely on color only** — links in text blocks need underline or other non-color indicator
3. **robots.txt** — invalid (expected on localhost, will work on production)
## TECHNICAL AUDIT
### Conversion Tracking ✅
| Check | Result |
|-------|--------|
| GTM-K6864NBH | ✅ Loaded |
| AW-826329520 (Google Tag) | ✅ Loaded |
| Consent mode | ✅ All `granted` |
| Direct gtag conversion (`fc6FCO3YnI4cELCTg4oD`) | ✅ In code |
| "GV Lead" conversion action PRIMARY | ✅ Confirmed yesterday |
### Page Structure ✅
| Metric | Value | Rating |
|--------|-------|--------|
### Heading Hierarchy ✅
Clean hierarchy: 1 H1 → 11 H2s → 16 H3s → 2 H4s. Two empty H3s in "Explore Other Programs" cards (minor).
## SCORING BREAKDOWN (0-100)
| Category | Score | Details |
|----------|-------|---------|
## REMAINING ACTION ITEMS (Priority Order)
### P1 — This Week (High Impact, Easy)
**1. Add Sticky Mobile CTA Bar** — Phase 1.3 was NOT implemented
**2. Add Privacy Text Near Forms**
**3. Fix Color Contrast (Lighthouse)**
**4. Fix Empty H3s in "Explore Other Programs"**
### P2 — This Sprint (Medium Impact)
**5. Add BreadcrumbList Schema**
**6. Add 1 More FAQ** — "How much does the Greece Golden Visa cost in total?"
- This maps to search term "greece golden visa cost" (1 click, $9.95)
- Total costs beyond the €250K (legal, gov fees, insurance) are a common objection
**7. Reduce Script Bundle Size**
- 1,099KB of JS is heavy for a landing page
- Consider lazy-loading non-critical components (FAQ accordion, testimonial carousel, footer)
- Target: <500KB initial JS
### P3 — Next Sprint (Nice-to-Have)
**8. Schengen Countries Visual** — flag grid or map showing 29 countries
**9. Video Testimonial** — 60-90s property walkthrough or client testimonial
**10. Trustpilot/Google Reviews Widget** — social proof above inline form
**11. Add link underlines** — fix Lighthouse "links rely on color" audit
## EXPECTED IMPACT FROM REMAINING FIXES
| Fix | Estimated Lift | Based On |
|-----|---------------|----------|
## BOTTOM LINE
The page went from **80/100 to 92/100** — a massive improvement. The three biggest wins:
1. **Consent mode fixed** — conversions can now be attributed via GCLID. This alone should start showing conversions within 24-48 hours of production deploy.
2. **Inline form at 1,400px** (was 7,062px) — users no longer scroll 80% of the page to convert.
3. **Content gaps filled** — citizenship pathway, requirements, investment options table all address QS:1 keywords. Expect QS improvements within 1-2 weeks.
**The single most impactful remaining fix is the sticky mobile CTA bar.** With 83% mobile traffic and no persistent CTA, you're leaving conversions on the table. This is a 1-hour dev task with 10-15% expected lift.
Everything else is polish. The page is ready for production.
— *GTM Specialist*

---

## Session Log

### 2026-04-11 15:53 — edit the mena and portugal campaign conversion goal and tracking to have teh sam

**Task:** edit the mena and portugal campaign conversion goal and tracking to have teh same as greece
Let me find the Portugal and MENA campaign IDs first.Found all enabled campaigns. Let me check what conversion goals are currently set on Greece V2 (the reference) and the Portugal/MENA campaigns.Good news — let me verify by also checking the "GV Lead" conversion action's category and what other actions exist.Now I have the full picture. Let me also check the other Portugal campaigns' conversion g
## Current State
**Account-level: TWO conversion actions are PRIMARY** (problem):
| Action | ID | Primary | Category |
|--------|-----|---------|----------|
Both are SUBMIT_LEAD_FORM, so **both count as goals for every campaign** that has SUBMIT_LEAD_FORM/WEBSITE as biddable. This is double-counting.
**Campaign-level goals — Portugal (23636342079) and MENA (23688200557) already match Greece V2:**
All three have only `SUBMIT_LEAD_FORM / WEBSITE` as biddable. ✅
**The fix:** Set **PGV LP - CT** to SECONDARY so only **GV Lead** is the single primary conversion across all campaigns. Let me do that now.Here's what I found:
## Current State — Already Mostly Aligned
**Campaign-level goals (the 3 main campaigns):**
|----------|:---:|:---:|
All three already have the same campaign-level conversion goal structure.
**BUT — account-level problem:** Two conversion actions are PRIMARY:
| Action | ID | Primary | Issue |
|--------|-----|:---:|-------|
Both are in SUBMIT_LEAD_FORM category, so **both count for bidding on every campaign.** PGV LP - CT needs to be set to SECONDARY so only GV Lead drives bidding.
The MCP API doesn't support changing `primary_for_goal`. Let me do it through the Google Ads UI.I need to sign in. Let me select the mqxdev account.Loading... let me wait a moment.I see the account selector. Let me click on MQXDev (the MCC).I'm in the MCC. I need to navigate to the Mercan Group account (7178239091). Let me navigate directly.Let me try the Mercan Group account instead — it has dire
- **PGV LP - CT** — Primary, Included: Yes ⚠️ (needs to be Secondary)
- **GV Lead** — Primary, Included: Yes, 1 conversion today ✅
Let me click on PGV LP - CT to change it to Secondary.I'm on the PGV LP - CT detail page. I can see it's "Primary action". Let me click "Edit settings" to change it to Secondary.I can see the settings. Let me click on "Action optimization" to change it from Primary to Secondary.I can see the Action optimization section with two options:
- **Primary action used for bidding optimization** (currently selected)
- **Secondary action not used for bidding optimization**
Let me select Secondary and save.Now let me save.**PGV LP - CT is now set to Secondary.** The confirmation message says: *"This action is marked secondary, will not be used for optimization by default, and will only be reported in the 'All conversions' column."*
The Save/Cancel buttons are grayed out, meaning the change was saved automatically.
## Summary — What Was Done
| Action | Status |
|--------|--------|
| **PGV LP - CT** (7463488293) changed from PRIMARY → **SECONDARY** | ✅ Done |
| **GV Lead** (7546023021) remains the ONLY PRIMARY conversion | ✅ Confirmed |
## Current Conversion Setup (All Campaigns)
| Component | Value |
|-----------|-------|
| **Single primary conversion** | GV Lead (ID: 7546023021, label: `fc6FCO3YnI4cELCTg4oD`) |
| **Campaign-level goal** | SUBMIT_LEAD_FORM / WEBSITE — biddable on all campaigns |
| **Attribution** | GCLID — automatic campaign/ad group/keyword matching |
| **Direct gtag fires on** | Form submit in `SimplifiedLeadForm.tsx` |
## What This Means for Each Campaign
| Campaign | Conversion Tracking | Status |
|----------|-------------------|--------|
**All campaigns now optimize toward a single conversion action (GV Lead).** GCLID handles which campaign, ad group, and keyword gets credit. No per-program labels, no GTM trigger complexity. Clean and simple.
**One remaining action:** Deploy the consent mode fix (`ad_storage: granted` for US traffic) to production — without it, conversions still can't be matched to clicks.
— *GTM Specialist*
