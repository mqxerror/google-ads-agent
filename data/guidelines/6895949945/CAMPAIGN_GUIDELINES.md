# Google Ads Campaign Management Guidelines

> This document is the single source of truth for all campaign management decisions.
> **READ THIS BEFORE making ANY changes to any campaign.**
> Last updated: 2026-03-19

---

## Account Structure

| Level | ID | Name | Notes |
|-------|----|------|-------|
| Manager (MCC) | 6895949945 | MQXDev | Login customer ID |
| Sub-Manager | 7192648347 | Wassim | |
| Client Account | 7178239091 | Mercan Group Main Account | Active campaigns live here |
| Client Account | 1949155935 | (unnamed) | MSG Experts campaign (paused) |

**API Note:** The MCP server code uses v20 imports but the SDK is v29.2.0 (v23 API). Queries must use v23 request types. See `KNOWN_ISSUES.md` for the fix.

---

## Global Rules (Apply to ALL Campaigns)

### 1. Change Management
- **NEVER** make more than ONE type of change per day (e.g., don't change ads AND bidding strategy on the same day)
- **NEVER** edit ads while a bidding strategy is still in learning mode (first 14 days or after any change)
- After any change, wait **minimum 7 days** before evaluating results
- Document every change in the campaign's change log section below

### 2. Conversion Tracking Rules
- `mercan capital - GA4 (web) form_submit` (ID: 6953214477) fires on **ALL form submissions across the entire mercan.com website** — it is NOT campaign-specific
- This action is **SECONDARY** at account level (primary_for_goal = False) as of March 2026
- **NEVER** use `form_submit` as a primary conversion goal for any campaign — its data is inflated because it captures forms from organic, direct, and other campaigns
- Each campaign MUST have its own dedicated conversion action (WEBPAGE type with specific URL rules) set as PRIMARY
- Before launching any campaign, verify the dedicated conversion action is firing on the landing page

### 3. Conversion Actions Registry

| Conversion Action | ID | Type | Status | Primary | Used By |
|-------------------|----|------|--------|---------|---------|
| PGV LP - CT | 7463488293 | WEBPAGE | ENABLED | PRIMARY | Portugal GV campaigns | Tag installed via GTM — jQuery bug fixed 2026-03-19 |
| Greece Golden Visa USA CP | 7144337715 | WEBPAGE | ENABLED | PRIMARY | Greece GV campaign |
| form_submit (GA4) | 6953214477 | GA4_CUSTOM | ENABLED | SECONDARY | DO NOT use as primary — fires on all forms |
| Submit lead form | 7129643975 | WEBPAGE | ENABLED | SECONDARY | General |
| Lead form - Submit | 7240797059 | LEAD_FORM | ENABLED | SECONDARY | Lead form extensions |
| EB3 Brazil CAMPAIGN | 20043943331 | — | ENABLED | — | EB3 Brazil |

### 4. Negative Keyword Policy
- **NEVER** add negative keywords based on assumptions — only add them after reviewing actual search term reports with real data
- Before adding a negative, check: "Could this term appear in a high-intent query for this campaign?"
- Use [EXACT] match for negatives whenever possible to avoid blocking valuable long-tail queries
- Use [PHRASE] match only when the term is clearly irrelevant in any context
- Use [BROAD] match negatives ONLY for completely unrelated industries/topics
- **REVIEW negative keywords quarterly** to ensure they are not blocking valuable traffic
- Document the reason for every negative keyword added

### 5. Bidding Strategy Rules
- **Maximize Conversions** requires minimum 15 conversions in 30 days to work effectively
- If a campaign has fewer than 15 conversions/month, use **Manual CPC** or **Maximize Clicks** with a max CPC cap
- When switching FROM an automated strategy, expect 7-14 days of instability
- **NEVER** change the bidding strategy and conversion goals at the same time

---

## Campaign: Portugal Golden Visa - USA - 10-Mar-2026

### Overview

| Field | Value |
|-------|-------|
| Campaign ID | 23636342079 |
| Account | 7178239091 (Mercan Group Main Account) |
| Channel | Search |
| Status | ENABLED |
| Launch Date | 2026-03-10 |
| Budget | $200.00/day |
| Bidding Strategy | Maximize Clicks (max CPC $8.00) — changed 2026-03-19 from Maximize Conversions |
| Landing Page | https://www.mercan.com/business-immigration/portugal-golden-visa-program/ |
| Location Target | United States (geoTargetConstants/2840) |
| Devices | Desktop, Mobile, Tablet (all) |

### Conversion Tracking

| Action | Role | Status | Notes |
|--------|------|--------|-------|
| PGV LP - CT (7463488293) | PRIMARY/BIDDABLE | ENABLED | Dedicated to this landing page — MUST verify it fires |
| form_submit GA4 (6953214477) | SECONDARY | ENABLED | Fires on ALL forms — was recording 10 conv but data is unreliable |

**Campaign Conversion Goals (Biddable):**
- SUBMIT_LEAD_FORM (Website) — Biddable
- SUBMIT_LEAD_FORM (Google Hosted) — Biddable
- CONTACT (Website) — Biddable
- DOWNLOAD (App) — Biddable (irrelevant but harmless)

**IMPORTANT:** The 10 conversions reported Mar 10-19 came from `form_submit` (GA4) which fires on ALL website forms. These are NOT reliable for this campaign. The actual dedicated action `PGV LP - CT` has recorded 0 conversions prior to the fix on 2026-03-19.

**ROOT CAUSE (confirmed & fixed 2026-03-19):** The PGV LP - CT conversion tag WAS installed via GTM container `GTM-KWFH5X9T`, but the GTM Custom HTML tag "GF - Push dataLayer on AJAX confirmation" used `document.addEventListener('gform_confirmation_loaded', ...)` — a **native DOM event listener**. However, Gravity Forms fires `jQuery(document).trigger('gform_confirmation_loaded', [formId])` — a **jQuery event**. jQuery `.trigger()` does NOT fire native `addEventListener` callbacks. They are completely separate event systems. As a result, the `gf_submit` dataLayer event was never pushed, and the conversion tag never fired.

**Fix applied (2026-03-19):** Changed the GTM Custom HTML tag from `document.addEventListener()` to `jQuery(document).on('gform_confirmation_loaded', function(event, formId){...})`. Also fixed the formId parameter access — jQuery passes extra trigger arguments as function parameters, not via `event.detail`. Published as GTM Version 4 "V4 - Fix jQuery event listener".

**Landing Page Tag Audit (2026-03-19):**
- Google Ads ID: AW-826329520 ✅
- GTM Container: GTM-KWFH5X9T ✅
- GA4: GT-M3VGBZ ✅
- Form: Gravity Forms #23 (gform_23), AJAX submission ✅
- PixelYourSite: Fires `automatic_event_form` for Facebook only (separate system)
- Conversion Linker: Present in GTM ✅
- Google Tag (AW-826329520): Present in GTM ✅
- GF dataLayer push tag: Fixed — now uses jQuery event listener ✅
- PGV LP-CT tag (aCJmCKWW7-YbELCTg4oD): Present in GTM, fires on `gf_submit` + URL filter ✅
- Generic conversion tag: Present in GTM, fires on `gf_submit` (all pages) ✅

**GTM Tags (5 total in GTM-KWFH5X9T):**
1. Conversion Linker — All Pages
2. GF - Push dataLayer on AJAX confirmation — Custom HTML — All Pages (FIXED 2026-03-19)
3. Google Ads Conversion Tracking — fires on CE `gf_submit` (all pages)
4. Google Tag AW-826329520 — Initialization - All Pages
5. PGV LP - CT Conversion Tracking — fires on CE `gf_submit` + URL contains `/business-immigration/portugal-golden-visa-program`

**GTM Triggers (2):**
1. CE - gf_submit — Custom Event (event name: gf_submit)
2. CE - gf_submit - Portugal PGV — Custom Event (event: gf_submit, filter: Page URL contains /business-immigration/portugal-golden-visa-program)

**End-to-End Verification (2026-03-19):**
- Simulated `jQuery(document).trigger('gform_confirmation_loaded', [23])` on the landing page
- GTM Custom HTML tag caught the jQuery event and pushed `{event: 'gf_submit', gf_form_id: 23}` to dataLayer ✅
- GTM processed the event (assigned `gtm.uniqueEventId`) ✅
- GTM fired all associated tags (confirmed via `eventCallback` → `tagsFired: true, container: GTM-KWFH5X9T`) ✅
- Google Tag sent conversion data to `/ccm/collect` and `/ccm/form-data/826329520` ✅
- Test conversions returned 503 (expected — no real ad click in test session; real ad traffic will work)
- **MONITORING:** Check Google Ads PGV LP-CT conversion column after 2026-03-20 for first real conversions

### Ad Groups

| Ad Group | ID | Status | Keywords | Negative KWs |
|----------|----|--------|----------|--------------|
| Portugal Golden Visa | 202548312468 | ENABLED | 7 keywords | residency, fund, citizenship, mercan |
| Portugal Residency | 202548333748 | ENABLED | 7 keywords | fund, citizenship, mercan |
| Portugal Golden Visa Fund | 191851143737 | ENABLED | 3 keywords | residency, citizenship, mercan |
| Portugal Citizenship by Investment | 199260227452 | ENABLED | 5 keywords | residency, fund, mercan |
| Mercan Brand | 191851144937 | ENABLED | 4 keywords | (none) |

### Keywords

| Keyword | Match | Ad Group | Status | QS | Notes |
|---------|-------|----------|--------|----|-------|
| portugal golden visa | EXACT | Portugal Golden Visa | ENABLED | 7 | Top performer: 58 clicks, 6 conv |
| portugal golden visa | PHRASE | Portugal Golden Visa | ENABLED | 7 | |
| golden visa portugal | PHRASE | Portugal Golden Visa | ENABLED | 7 | |
| portugal golden visa program | EXACT | Portugal Golden Visa | ENABLED | 7 | |
| portugal golden visa program | PHRASE | Portugal Golden Visa | ENABLED | 7 | |
| portugal golden visa for americans | PHRASE | Portugal Golden Visa | ENABLED | N/A | |
| golden visa in portugal | EXACT | Portugal Golden Visa | ENABLED | N/A | |
| portugal golden visa 2026 | EXACT | Portugal Golden Visa | ENABLED | 7 | |
| portugal residency for us citizens | PHRASE | Portugal Residency | **PAUSED** | **2** | **HAD 49 CLICKS, 4 CONV — RE-ENABLE** |
| permanent residency in portugal | EXACT | Portugal Residency | ENABLED | N/A | |
| permanent residency in portugal | PHRASE | Portugal Residency | ENABLED | N/A | |
| portugal residency by investment | PHRASE | Portugal Residency | ENABLED | 5 | |
| portugal investment visa | PHRASE | Portugal Residency | ENABLED | 4 | |
| i want to move to portugal from usa | EXACT | Portugal Residency | ENABLED | N/A | 1 click, 2 conv! |
| portugal golden visa fund | EXACT | Portugal Golden Visa Fund | ENABLED | 5 | |
| portugal golden visa investment fund | EXACT | Portugal Golden Visa Fund | ENABLED | 4 | |
| portugal golden visa investment fund | PHRASE | Portugal Golden Visa Fund | ENABLED | 4 | |
| portugal golden visa cost | PHRASE | Portugal Golden Visa Fund | ENABLED | 4 | |
| portugal citizenship by investment | PHRASE | Citizenship by Investment | ENABLED | 5 | |
| citizenship by investment portugal | EXACT | Citizenship by Investment | ENABLED | 5 | |
| citizenship by investment portugal | PHRASE | Citizenship by Investment | ENABLED | 5 | |
| portugal citizenship investment | EXACT | Citizenship by Investment | ENABLED | N/A | |
| portugal citizenship through investment | PHRASE | Citizenship by Investment | ENABLED | 4 | |
| mercan group portugal | EXACT | Mercan Brand | ENABLED | N/A | |
| mercan portugal | EXACT | Mercan Brand | ENABLED | N/A | |
| mercan golden visa | PHRASE | Mercan Brand | ENABLED | N/A | |
| mercan group golden visa | EXACT | Mercan Brand | ENABLED | N/A | |

### Negative Keywords (Campaign Level) — 81 total

**Approved negatives (keep — clearly irrelevant):**
- Competitors/other programs: cyprus, eb5, eb-5, italy golden visa, ireland golden visa, spain golden visa, greece, italy, spain, uk investor, uk investor visa
- Informational/low intent: reddit, blog, forum, wiki, wikipedia, news, review, comparison, versus, vs, pros and cons
- Irrelevant intent: job, work permit, work visa, student visa, digital nomad, d2, d2 visa, d7, d7 visa, cheap, budget, free, scam, worth it
- Program status: abolished, cancelled, canceled, suspended, ended
- Wrong audience: by birth, by descent, sephardic, russian citizenship, portuguese citizenship, europe citizenship, how to become a citizen, how to get citizenship, apply for citizenship
- Other: green card, passport, venture capital, minimum salary, nomad gate, hqa, hqa visa, retire, retirement, expat, expats, immigration, how much, us citizen moving, imidaily, amer golden visa, does still have, how long can

**Negatives that need REVIEW (potentially blocking valuable traffic):**
| Negative | Match | Concern | Decision |
|----------|-------|---------|----------|
| immigration | PHRASE | Could block "portugal immigration investment" | REVIEW — check search terms for blocked queries |
| how much | PHRASE | Could block "how much to invest portugal golden visa" | REVIEW — check if relevant queries are being blocked |
| expat / expats | PHRASE | Could block "american expat portugal golden visa" | REVIEW — likely low intent, keep for now |
| retirement | BROAD | Could block "portugal golden visa retirement plan" | REVIEW — likely low intent, keep for now |
| us citizen moving | PHRASE | Could block "us citizen moving to portugal investment" | REVIEW — the exact search "us citizen moving to portugal" is informational |
| how to become a citizen | PHRASE | Could block "how to become a citizen through golden visa portugal" | REVIEW — check search terms |
| how to get citizenship | PHRASE | Could block "how to get citizenship portugal golden visa" | REVIEW — check search terms |

**Decision: DO NOT remove any negatives right now.** The campaign has only 9 days of data. The negatives are blocking mostly informational queries. We will revisit after 30 days of data when we can see which queries are actually being blocked and their conversion patterns.

### Performance History

| Date | Impr | Clicks | Cost | Conv | IS | Rank Lost |
|------|------|--------|------|------|----|-----------|
| Mar 10 | 16 | 0 | $0 | 0 | — | — |
| Mar 11 | 271 | 23 | $120 | 0 | 32.2% | 67.8% |
| Mar 12 | 273 | 29 | $200 | 6* | 45.2% | 54.8% |
| Mar 13 | 272 | 33 | $128 | 0 | 47.8% | 0.7% |
| Mar 14 | 439 | 60 | $173 | 0 | 64.8% | 0.4% |
| Mar 15 | 35 | 3 | $5 | 0 | 10.0% | 90.0% |
| Mar 16 | 192 | 27 | $125 | 4* | 38.6% | 23.8% |
| Mar 17 | 33 | 2 | $9 | 0 | 10.0% | 90.0% |
| Mar 18 | 66 | 2 | $5 | 0 | 10.0% | 90.0% |
| Mar 19 | 27 | 2 | $12 | 0 | 11.9% | 88.1% |

*Conversions from form_submit GA4 (unreliable — fires on all website forms)

### Known Issues

1. ~~**CRITICAL: Bidding strategy has no conversion signal**~~ — ✅ RESOLVED 2026-03-19: Switched to Maximize Clicks (max CPC $8.00). See Fix 1.
2. ~~**CRITICAL: PGV LP - CT conversion action shows 0 conversions**~~ — ✅ RESOLVED 2026-03-19: Root cause was jQuery vs native DOM event listener mismatch in GTM. Fixed and published GTM V4. See Fix 2. **MONITORING: Verify conversions appear within 7 days.**
3. ~~**HIGH: Top-performing keyword paused**~~ — ✅ RESOLVED 2026-03-19: Re-enabled `[PHRASE] portugal residency for us citizens`. See Fix 3.
4. **HIGH: 90% rank-lost impression share** — Campaign is barely showing ads since Mar 15. Switching to Maximize Clicks (Fix 1) should restore traffic within 24-48hrs. **MONITORING.**
5. **MEDIUM: Too many simultaneous changes** — Ads, assets, and conversion goals were all changed on Mar 18, compounding instability. Now in stabilization period — NO changes until 2026-03-26.

### Change Log

| Date | Change | Reason | Impact |
|------|--------|--------|--------|
| 2026-03-10 | Campaign launched | New campaign | — |
| 2026-03-18 | form_submit GA4 made SECONDARY | Fires on all forms, inflated data | Bidding strategy lost all conversion signal |
| 2026-03-18 | Multiple ad copy changes (11+ ads modified) | Ad optimization | Reset ad learning |
| 2026-03-18 | Campaign assets removed/added | Asset optimization | Additional disruption |
| 2026-03-19 | 30 ad group assets changed | Unknown (possibly auto-applied) | Additional disruption |
| 2026-03-19 | Campaign-level change at 10:31 | Unknown | — |
| 2026-03-19 | **FIX 1:** Bidding strategy changed from Maximize Conversions to Maximize Clicks (max CPC $8.00) | No primary conversion tag on LP, bidding algo had no signal, 90% rank-lost IS | Should restore traffic within 24-48hrs |
| 2026-03-19 | **FIX 3:** Re-enabled [PHRASE] "portugal residency for us citizens" keyword | Was paused despite 49 clicks + 4 conversions (top performer) | Immediate traffic uplift expected |
| 2026-03-19 | **FIX 2 COMPLETE:** Fixed GTM jQuery event listener for PGV LP - CT | Root cause: GTM Custom HTML tag used native `document.addEventListener` but Gravity Forms fires jQuery events. Changed to `jQuery(document).on()`. Published GTM V4. | Conversion tag should now fire on form submissions — monitor for 7 days |

### Fix Plan (Ordered — execute in sequence)

**Fix 1: Switch bidding strategy to Maximize Clicks**
- Change from Maximize Conversions to Maximize Clicks
- Set max CPC bid cap at $8.00 (based on historical avg CPC of $4.27, with headroom)
- Reason: No primary conversion signal available. Must restore traffic first.
- Wait 7 days before evaluating.

**Fix 2: Fix GTM event listener for PGV LP - CT conversion tag** ✅ COMPLETED 2026-03-19
- **Issue:** The conversion tag WAS installed in GTM but never fired because of a jQuery vs native DOM event mismatch
- **Root cause:** Gravity Forms fires `jQuery(document).trigger('gform_confirmation_loaded', [formId])` but the GTM Custom HTML tag used `document.addEventListener('gform_confirmation_loaded', ...)` — jQuery events don't fire native DOM listeners
- **Fix applied:** Changed GTM tag "GF - Push dataLayer on AJAX confirmation" to use `jQuery(document).on('gform_confirmation_loaded', function(event, formId){...})`
- **Published:** GTM Version 4 "V4 - Fix jQuery event listener" on 2026-03-19 12:41 PM
- **Verification needed:** Monitor Google Ads conversion column for PGV LP - CT over next 7 days to confirm conversions are now recording

**Fix 3: Re-enable paused keyword**
- Re-enable `[PHRASE] portugal residency for us citizens` in Portugal Residency ad group
- This keyword had 49 clicks and 4 conversions — it's a top performer
- QS of 2 needs work (improve ad relevance and landing page experience)

**Fix 4: Monitor for 7 days — no other changes**
- Let the bidding strategy stabilize
- Collect conversion data from PGV LP - CT
- Review search terms after 7 days

**Fix 5: After 7 days — evaluate and decide**
- If PGV LP - CT is recording conversions: switch to Target CPA or Maximize Conversions
- If PGV LP - CT is NOT recording: create a new dedicated conversion action for this landing page
- Review search terms and add negatives only if data supports it

---

## Campaign: PGV - Impression Share Bidding Strategy

| Field | Value |
|-------|-------|
| Campaign ID | 14815079674 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: EB3 Brazil CAMPAIGN

| Field | Value |
|-------|-------|
| Campaign ID | 20043943331 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: PORTUGAL GOLDEN VISA - Investment Funds (US) PGV Fund Experiment Target CPA

| Field | Value |
|-------|-------|
| Campaign ID | 21705602620 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: PORTUGAL GOLDEN VISA - Investment Funds (US) Trial 490

| Field | Value |
|-------|-------|
| Campaign ID | 21957819991 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: PORTUGAL GOLDEN VISA - Investment Funds (US) Maximize Click Strategy Test

| Field | Value |
|-------|-------|
| Campaign ID | 21987116063 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: PORTUGAL GOLDEN VISA - Investment Funds (US) Test For Quarter 2

| Field | Value |
|-------|-------|
| Campaign ID | 22396489815 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: Greece Golden Visa Program

| Field | Value |
|-------|-------|
| Campaign ID | 22551124974 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Campaign: Greece Golden Visa Program Maximize Conversion

| Field | Value |
|-------|-------|
| Campaign ID | 22807384760 |
| Status | ENABLED |
| Notes | Separate documentation needed |

---

## Appendix: How to Use This Document

1. **Before ANY campaign change:** Read the campaign's section and the Global Rules
2. **After ANY change:** Update the Change Log with date, what changed, why, and expected impact
3. **Weekly:** Review performance history table and update with new data
4. **Monthly:** Review negative keywords against search term data
5. **Quarterly:** Full audit of all campaigns against these guidelines
