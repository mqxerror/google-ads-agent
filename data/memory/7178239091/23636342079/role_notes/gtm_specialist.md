# Gtm Specialist Notes

**Last updated:** 2026-04-12 18:46

**Task:** audit the conversion tracking for this campaign and test it end to end
Starting the end-to-end conversion tracking audit. I'll check the Google Ads conversion action status and the landing page simultaneously.
Good, tools loaded. Let me run the audit in parallel — checking the conversion action in Google Ads and loading the landing page.Running the conversion action check and opening the landing page simultaneously.Page loaded. Let me fix the query and take a screenshot of the landing page.Landing page is live. Now let me check the tags on the page and query conversion actions.Good — all base tags are p

---

## Session Log

### 2026-04-12 18:24 — get the real landing page from the ad which is golden visas.mercan.com/portugal

**Task:** get the real landing page from the ad which is golden visas.mercan.com/portugal

**Critical Details:** AW-826329520, GTM-KWFH5X9T, AW-959555504, GTM-K6864NBH
Navigating to the actual ad landing page now.URL had a space — let me fix that. It should be `goldenvisas.mercan.com/portugal`.Page loaded. Let me screenshot it and check what tags are on this page.This is a **completely different site** from what's in the campaign configuration. This is a Next.js app at `goldenvisas.mercan.com`, NOT the WordPress/Gravity Forms page at `mercan.com/business-immigra
This is likely **the root cause of the conversion drought**. Let me check what tracking tags exist on this page.## CRITICAL FINDING — Root Cause Identified
**The ads are pointing to `goldenvisas.mercan.com/portugal` but ALL conversion tracking was built for `mercan.com/business-immigration/portugal-golden-visa-program/`.** These are completely different sites.
Here's what I found on the **actual landing page** (`goldenvisas.mercan.com/portugal`):
### Tags Present on This Page
| Tag | ID | Status |
|-----|----|--------|
| Consent | All granted | ✅ |
### What's MISSING (The Problem)
| Expected | Reality |
|----------|---------|
| GTM Container `GTM-KWFH5X9T` (has PGV LP-CT tag) | **NOT loaded — wrong container** |
| PGV LP-CT conversion tag (label `aCJmCKWW7-YbELCTg4oD`) | **Not present** |
| Gravity Forms `gf_submit` dataLayer event | **Not possible — this is a React/Next.js form, not Gravity Forms** |
| URL filter `/business-immigration/portugal-golden-visa-program` | **Page URL is `/portugal` — would never match** |
### The Triple Miss
The PGV LP-CT conversion tag fails in **three independent ways** on this page:
1. Wrong GTM container loaded (`K6864NBH` instead of `KWFH5X9T`)
2. No Gravity Forms = no `gf_submit` event = trigger never fires
3. URL filter looks for `/business-immigration/portugal-golden-visa-program` but page is `/portugal`
**The jQuery fix we applied on March 19 was on the OLD landing page. The ads are sending all traffic to this NEW page where there is zero form submission conversion tracking.**
### What Needs to Happen
I need to check two things next:
1. **What's inside GTM-K6864NBH** — does it have ANY form conversion tags?
2. **How does this React form submit?** — we need to understand the form mechanism to build a proper conversion tag
Want me to proceed with both checks? This is almost certainly why we have 1 conversion in 24 days — the only conversion recorded was likely from the old mercan.com page or an accidental `form_submit` GA4 event.
— *GTM Specialist*

### 2026-04-12 18:30 — the correct container for the campaign is GTM-K6864NBH

**Task:** the correct container for the campaign is GTM-K6864NBH

**Critical Details:** AW-826329520, campaignid=23636342079, GTM-K6864NBH
Understood — `GTM-K6864NBH` is the correct container. That eliminates one of the three issues. The remaining questions are:
1. **Does GTM-K6864NBH have any form submission conversion tags?**
2. **How does the React form on goldenvisas.mercan.com/portugal submit?**
Let me check both now.
Let me check both in parallel — the GTM container contents and the form submission mechanism on the landing page.I need to find the GTM-K6864NBH container. Let me scroll down to see more accounts.
Found it. **GTM-K6864NBH** is under "Mercan LP" account, container named "goldenvisas.mercan.com - V2". Let me click into it to see the tags.I'm inside the GTM-K6864NBH container (goldenvisas.mercan.com - V2). Let me check the Tags section to see what conversion tags exist.Good — Version 4, published 3 days ago. Let me click into Tags to see what's configured.There IS a "Portugal GV - Conversion" 
- **Conversion ID:** 826329520 (AW-826329520) ✅
- **Conversion Label:** `aCJmCKWW7-YbELCTg4oD` ✅ — matches PGV LP-CT
- **Trigger:** "Thank You - Portugal GV" — **Page View** type
The tag itself is correctly configured — same conversion label as PGV LP-CT. Now I need to check what URL the "Thank You" trigger fires on. Let me click into it.Tag panel is open. Now let me click on the "Thank You - Portugal GV" trigger to see its URL condition.Now I have the full picture of the trigger:
- **Type:** Page View
- **Condition 1:** Page Path **starts with** `/thank-you`
- **Condition 2:** Page URL **contains** `campaignid=23636342079`
This is a well-designed thank-you page trigger. The conversion fires when the user is redirected to `/thank-you?campaignid=23636342079` after form submission.
Now the critical question: **Does the form on `goldenvisas.mercan.com/portugal` actually redirect to this thank-you page with the campaign ID parameter?** Let me check the form behavior.The forms are React-managed. Let me check the Next.js bundle for the form submission and redirect logic.Let me look for the form submission handler and redirect logic in the JS bundles.It's a **multi-step form**. S
1. Captures all Google Ads tracking params from the current URL (including `campaignid`, `gclid`, etc.)
2. Redirects to `/thank-you?campaignid=23636342079&...`
This means the GTM trigger **will fire** — IF the ads are passing `campaignid={campaignid}` in the URL. Let me verify the campaign's tracking template or final URL suffix.**ROOT CAUSE CONFIRMED.**
The `final_url_suffix` is:
**`campaignid={campaignid}` is MISSING.** Without it:
1. User clicks ad → lands on `goldenvisas.mercan.com/portugal?utm_source=google&utm_medium=cpc&...` (no `campaignid` param)
2. User fills form → redirected to `/thank-you?program=...&goal=...&utm_source=google&...` (still no `campaignid`)
3. GTM trigger checks: Page URL contains `campaignid=23636342079` → **NEVER MATCHES** ❌
4. Portugal GV - Conversion tag → **NEVER FIRES** ❌
## The Fix
Add `campaignid={campaignid}` to the campaign's `final_url_suffix`. The corrected suffix:
This is a **low-risk change** — it only adds a URL parameter. No tags, triggers, or landing page code need to change. The form already captures `campaignid` and passes it to the thank-you page. The GTM trigger already checks for it.
**Want me to update the final URL suffix now?** I can also add other useful ValueTrack params like `adgroupid`, `keyword`, `matchtype`, `device`, `network` so they all flow through to the thank-you page for richer attribution (the form redirect code already supports all of them).
The full recommended suffix would be:
Confirm and I'll apply it.
— *GTM Specialist*

### 2026-04-12 18:46 — check the Greece conversion action and make it the same we have one form to subm

**Task:** check the Greece conversion action and make it the same we have one form to submit the gelid from google will give the right conversion follow same strategy

**Critical Details:** Conversion ID: 826329520, campaignid=23722199501, AW-826329520, GTM-K6864NBH
Let me check the Greece campaign setup in parallel — the campaign details, conversion action, and GTM container for a Greece tag.Let me pull the Greece campaign details, the Greece conversion action, and check what's in GTM for Greece — all in parallel.Let me use the stream API instead.Good findings. Now let me get the full picture — Greece campaign ads/URLs and check GTM for Greece tags.Clear pic
Let me check GTM-K6864NBH for a Greece conversion tag and verify the Greece landing page form behavior.I see page 13 is already in the GTM container. Let me select it and check the tags.I can see a "GV Landing Page - Conversion" tag with:
- **Conversion ID:** 826329520 (AW-826329520)
- **Conversion Label:** `fc6FCO3YnI4cELCTg4oD` — different from PGV LP-CT
- **Trigger:** "Thank You - GV Landing Page"
I also see a "Greec..." tag in the sidebar. Let me check the trigger conditions first, then the Greece tag.I can see all 5 tags. There's a **"Greece GV - Conversion"** tag with trigger **"Thank You - Greece GV"**. Let me click into it to check the conversion label and trigger conditions.Still showing the GV Landing Page tag. Let me close this and click the Greece tag directly.**Greece GV - Convers
- Conversion ID: 826329520 (AW-826329520) ✅
- Conversion Label: `hMe8CLPi184aELCTg4oD`
- Trigger: "Thank You - Greece GV" — Page View
Now let me check the trigger conditions to see what `campaignid` it expects.Now let me click on the trigger to see its URL conditions.**Confirmed — exact same root cause as Portugal.** The Greece trigger expects `campaignid=23722199501` in the thank-you page URL, but the Greece V2 campaign has **no `final_url_suffix`** at all.
Now let me verify the conversion label matches the Google Ads conversion action, and check the other Greece campaign too.The old Greece campaign (22807384760) has no `final_url_suffix` either, but it has 0 impressions so it's essentially dead. Let me find the Greece conversion label from the large result.**Label confirmed:** `AW-826329520/hMe8CLPi184aELCTg4oD` — the GTM tag matches the Google Ads 
## Greece Campaign Audit — Complete Picture
### What's set up correctly
| Component | Status |
|-----------|--------|
| GTM Tag "Greece GV - Conversion" | ✅ Label `hMe8CLPi184aELCTg4oD` matches conversion action |
| GTM Trigger "Thank You - Greece GV" | ✅ Fires on `/thank-you` + `campaignid=23722199501` |
| Form redirect (Next.js) | ✅ Same app — captures `campaignid` and passes it to `/thank-you` |
| Conversion Linker | ✅ All Pages |
| Google Tag AW-826329520 | ✅ Initialization - All Pages |
### What's broken — same root cause as Portugal
| Issue | Detail |
|-------|--------|
| `final_url_suffix` on Greece V2 (23722199501) | **EMPTY** — no `campaignid` param passed |
| Result | Form redirects to `/thank-you` WITHOUT `campaignid=23722199501` → trigger never matches → **0 conversions on 84 clicks / $1,026 spent** |
| Conversion action priority | `primary_for_goal = false` (SECONDARY) — should verify this doesn't block attribution |
### The Fix
Add `campaignid={campaignid}` to the Greece V2 campaign's `final_url_suffix`:
This is **low-risk** — only adds URL parameters. No GTM or landing page changes needed. The form already captures `campaignid` and passes it through.
I also recommend applying the same fix to the **Portugal campaign (23636342079)** at the same time since you approved it earlier.
**Shall I update both campaigns' `final_url_suffix` now?**
1. **Greece V2 (23722199501):** `utm_source=google&utm_medium=cpc&utm_campaign=greece-gv-v2&utm_content={adgroupid}&utm_term={keyword}&campaignid={campaignid}`
2. **Portugal (23636342079):** `utm_source=google&utm_medium=cpc&utm_campaign=pgv-usa&utm_content={adgroupid}&utm_term={keyword}&campaignid={campaignid}`
— *GTM Specialist*
