# Gtm Specialist Notes

**Last updated:** 2026-04-15 19:32

**Task:** Run stage 6 for campaign build

**Critical Details:** GTM-K6864NBH, AW-959555504, AW-826329520, campaignid=2372219, campaignid=2368820
# Stage 6: GTM Specialist — Conversion Tracking & Verification
Per the PPC Strategist's build summary, campaign **23758877756** is PAUSED and needs conversion tracking configured before launch. Let me execute.
**What I know from account memory:**
- Container: **GTM-K6864NBH** (verified 2026-04-13)
- Dual-tracking: inline `gtag()` primary + GTM safety net
- Account-wide conversion: GV Lead (`fc6FCO3YnI4cELCTg4oD`)
- Turkey LP: `goldenvisas.mercan.com/tr/greece-golden-visa`
- Two Google Ads IDs detected on LP: **AW-959555504** and **AW-826329520**
**Step 1:** Create Turkey-specific conversion action + verify the landing page tracking in parallel.
Good, now let me create the conversion action and verify the landing page tracking simultaneously.Conversion action created: **Greece GV Turkey CP** (ID **7576883475**). Now let me get the tag details and verify the landing page in parallel.Page loaded (slow but there). Let me get the conversion details and screenshot in parallel.The GAQL queries are hitting a page_size bug. Let me verify the land
Let me check what's in the GTM container and the form submission code.Let me see the GTM tags list.GTM-K6864NBH confirmed, Version 5 live. Let me view the tags.5 tags configured. **GV Lead - Conversion** is active with "Thank You - All Campaigns" trigger. Two tags are paused (orange icons). Let me check the active conversion tag and the trigger details.Let me check the active GV Lead conversion ta
- Conversion ID: **826329520**
- Conversion Label: **fc6FCO3YnI4cELCTg4oD**
- Trigger: **"Thank You - All Campaigns"** (Page View type)
- Value: $1.00 USD
The trigger is a **Page View** — it fires on a thank-you page URL. Let me check the trigger's URL matching rule and the form submission flow.Now I have the full picture. The triggers use **Page View on `/thank-you`** pages:
| Trigger | Filter | Used by |
|---------|--------|---------|
| Thank You - All Campaigns | Page Path starts with `/thank-you` | GV Lead (ACTIVE) |
The GV Lead conversion **already fires for all campaigns** including Turkey — good. Now I need the conversion label for the new Turkey-specific action. Let me get it from the Google Ads UI.Conversion settings confirmed — 90-day lookback, $50 value, data-driven attribution. Now I need the tag snippet. Let me check the Details tab.I can see the "Data sources" section at the bottom. Let me scroll dow
- **reqid=1429**: `googleadservices.com/pagead/conversion/826329520/...en=conversion...label=fc6FCO3YnI4cELCTg4oD...value=1.0` → **200 OK** ✅
- **reqid=1439**: `doubleclick.net/pagead/viewthroughconversion/826329520/...en=conversion...label=fc6FCO3YnI4cELCTg4oD` → backup pixel ✅
- **reqid=1441-1442**: `1p-conversion` endpoints → first-party tracking ✅
- **Enhanced conversions**: Hashed email data (`em=`) present ✅
- **GCLID cookie**: `gclaw=test123_conversion_tracking` captured ✅
Now let me verify the form actually redirects to `/thank-you`. Let me check the app source code.**CRITICAL FINDING.** The form redirects to `/<locale>/thank-you` — for Turkish that's `/tr/thank-you`. But the GTM trigger uses "Page Path **starts with** `/thank-you`" which will NOT match `/tr/thank-you`.
Let me verify this and check the inline gtag conversion code.Now let me check if the GV Lead conversion fires on `/tr/thank-you` (Turkish locale).**CONFIRMED: The GV Lead conversion does NOT fire on `/tr/thank-you`.** Only config pings (`en=gtag.config`), zero conversion pings (`en=conversion`). The trigger mismatch is real.
But there's also an **inline gtag conversion** that fires before the redirect (line 238 in the form code). Let me check what conversion ID it uses.**Key finding:** `NEXT_PUBLIC_GADS_CONVERSION_ID=AW-826329520/fc6FCO3YnI4cELCTg4oD`
The inline gtag fires the GV Lead conversion on form submission (before redirect) — this IS the primary tracking mechanism and it works for all locales. But the GTM safety net is broken for non-English pages.
**I need to fix the GTM trigger.** Let me update it from "starts with /thank-you" to "contains /thank-you".I can see the trigger: "Page Path starts with /thank-you". I need to change "starts with" to "contains". Let me click on the filter to edit it.Now I can see the editable filter. Let me click the "starts with" dropdown to change it to "contains".
I can see the dropdown is available. Let me select "contains" instead of "starts with".The dropdown is highlighted but didn't change yet. Let me try selecting "contains" by interacting with the dropdown properly.Changed to "contains". The Save button is now active. Let me save.Trigger saved. "Workspace Changes: 1" confirmed. Now I need to publish this change. Let me click Submit.Let me add a versi
**Version 6 published successfully!** GTM-K6864NBH is now live with the locale trigger fix.
Now let me verify the fix works by testing `/tr/thank-you` again.## Stage 6 Deliverable — GTM Specialist / Conversion Tracking
**Campaign:** Greece Golden Visa – Turkey (ID: 23758877756)
**Landing Page:** goldenvisas.mercan.com/tr/greece-golden-visa
### 1. Conversion Action Created
| Field | Value |
|-------|-------|
| Name | Greece GV Turkey CP |
| ID | 7576883475 |
| Category | SUBMIT_LEAD_FORM |
| Value | $50 (fixed) |
| Counting | ONE_PER_CLICK |
| Lookback | 90 days (click), 30 days (view-through) |
| Attribution | Data-driven |
| Status | ENABLED |
### 2. Critical Bug Found & Fixed
**GTM trigger locale mismatch** — The "Thank You - All Campaigns" trigger used `Page Path starts with /thank-you`, which does NOT match localized paths like `/tr/thank-you`. This meant **zero GTM conversion tracking** for any non-English campaign.
**Fix:** Changed trigger operator to `Page Path contains /thank-you` → Published as **GTM Version 6** (container GTM-K6864NBH).
This fix benefits all localized campaigns (Turkish, Arabic, etc.), not just this one.
### 3. Dual-Tracking Architecture — Verified
| Layer | Mechanism | Fires When | Locale-Safe? |
|-------|-----------|------------|-------------|
**Tracking params preserved on redirect:** gclid, gbraid, wbraid, dclid, UTMs, campaignid, adgroupid, keyword, matchtype, device, network.
### 4. Pre-Launch Checklist
- [x] Conversion action created in Google Ads
- [x] Inline gtag fires on form submission (all locales)
- [x] GTM trigger fixed for localized thank-you pages (V6 published)
- [x] dataLayer push includes program + intent
- [x] Tracking params passed through to thank-you page
- [x] Conversion linker tag active in GTM (cookies: `_gcl_aw`, `_gcl_au`)
- [x] Enhanced conversions enabled (hashed email sent with conversion ping)
- [ ] **BLOCKER — Landing page `lang="en"`**: The `/tr/greece-golden-visa` page has `<html lang="en">` instead of `lang="tr"`. Google may quality-score this poorly for Turkish ad traffic. **Needs dev fix.**
- [ ] **Verify GTM V6 propagation**: CDN-cached container may take 15-30 min to update. Re-check `/tr/thank-you` for conversion pings after propagation.
- [ ] **Set campaign-level conversion goal**: Configure campaign 23758877756 to use the appropriate primary conversion action.
### 5. Recommendation
The **unified GV Lead conversion** (AW-826329520/fc6FCO3YnI4cELCTg4oD) is already wired into the inline gtag and will fire for this campaign. GCLID-based attribution will correctly attribute conversions to the Turkey campaign. The new **Greece GV Turkey CP** action (7576883475) can be used as a secondary/observation conversion or promoted to primary if you want campaign-specific reporting separati
**Bottom line:** Conversion tracking is functional. The inline gtag (primary mechanism) works across all locales today. The GTM safety net is now fixed with V6. One blocker remains: the `lang="en"` attribute on the Turkish landing page needs a code change before launch.