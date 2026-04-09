# Greece Golden Visa Campaign Management Guidelines

> This document is the single source of truth for all Greece campaign management decisions.
> **READ THIS BEFORE making ANY changes to the Greece campaign.**
> Created: 2026-03-19
> Last updated: 2026-03-19

---

## Account Structure

| Level | ID | Name |
|-------|----|------|
| Manager (MCC) | 6895949945 | MQXDev (Login customer ID) |
| Sub-Manager | 7192648347 | Wassim |
| Client Account | 7178239091 | Mercan Group Main Account |

---

## Campaign: Greece Golden Visa Program

### Overview

| Field | Value |
|-------|-------|
| Campaign ID | 22551124974 |
| Account | 7178239091 (Mercan Group Main Account) |
| Channel | Search |
| Status | ENABLED (Limited by budget) |
| Launch Date | ~May 2025 (UTM: `greece-golden-visa-cp-05-2025`) |
| Budget | $200.00/day |
| Bidding Strategy | Maximize Conversions (Target CPA $60.00) |
| Landing Page | `https://www.mercan.com/greece-golden-visa/` |
| Location Target | United States |
| Devices | Desktop (17.2%), Mobile (82.8%), Tablet (-100% bid adj = excluded) |
| Optimization Score | 99.8% |

### Second Campaign (PAUSED/REMOVED)

| Field | Value |
|-------|-------|
| Campaign ID | 22807384760 |
| Name | Greece Golden Visa Program Maximize Conversion |
| Status | NOT in enabled campaigns list — paused or removed |
| Notes | Only one Greece campaign is active |

---

## Landing Page

| Field | Value |
|-------|-------|
| URL | `https://www.mercan.com/greece-golden-visa/` |
| Status | ✅ **WORKING** (confirmed 2026-03-19) |
| Page Title | GREECE GOLDEN VISA - MERCAN GROUP |
| Gravity Forms | ✅ Form ID 26 (`gform_26`) — AJAX submission |
| Contact Form 7 | Also present (wpcf7-f647-o1) — secondary form |
| GTM Container | ✅ GTM-KWFH5X9T (same as Portugal) |
| Google Tag | ✅ Present |
| Google Ads Tag | ✅ Present |

**⚠️ NOTE:** URL `/business-immigration/greece-golden-visa-program/` returns **404** — this is NOT the ad landing page. The correct URL is `/greece-golden-visa/` (without `/business-immigration/` prefix).

### Sitelink Extensions (Landing Pages Report)

| Landing Page | Clicks | Impr | Notes |
|-------------|--------|------|-------|
| `/greece-golden-visa/?utm_source=google&...` | 15 | 333 | ✅ Main landing page — ALL clicks go here |
| `/business-immigration/portugal-golden-visa-program/` | 0 | 97 | ⚠️ PORTUGAL page on Greece campaign! |
| `/business-immigration/portugal-golden-visa/` | 0 | 75 | ⚠️ PORTUGAL page on Greece campaign! |
| `/our-projects/` | 0 | 67 | Generic sitelink |
| `/branch-offices/` | 0 | 30 | Generic sitelink |

**ISSUE:** Portugal Golden Visa sitelinks are showing on the Greece campaign ads. These should be replaced with Greece-specific sitelinks.

---

## Conversion Tracking

### Conversion Actions

| Action | ID | Type | Status | Primary | GTM Tag |
|--------|----|------|--------|---------|---------|
| Greece Golden Visa USA CP | 7144337715 | WEBPAGE | ENABLED | PRIMARY | ✅ **WORKING** (GTM V6, label hMe8CLPl184aELCTg4oD) |
| form_submit (GA4) | 6953214477 | GA4_CUSTOM | ENABLED | SECONDARY | N/A (GA4 auto-tracking) |

### ✅ Conversion Tracking — WORKING (Fixed 2026-03-19)

**GTM Container (GTM-KWFH5X9T) — Current Tags:**

| Tag | Type | Conv ID | Conv Label | Trigger | Status |
|-----|------|---------|------------|---------|--------|
| Google Tag - AW-826329520 | Google Tag | — | — | Initialization - All Pages | ✅ Active |
| Conversion Linker | Conversion Linker | — | — | All Pages | ✅ Active |
| GF - Push dataLayer on AJAX confirmation | Custom HTML | — | — | All Pages | ✅ Active (fixed 2026-03-19) |
| Google Ads Conversion Tracking | Google Ads Conv | 826329520 | -YHvCK6ejJsZELCTg4oD | CE - gf_submit | ⏸️ **PAUSED (V7, 2026-03-19)** — was active and causing cross-fire |
| **Greece GV - USA CP - Conversion Tracking** | **Google Ads Conv** | **826329520** | **hMe8CLPl184aELCTg4oD** | **CE - gf_submit - Greece GV** | ✅ **Active (FIXED 2026-03-19)** |
| PGV LP - CT Conversion Tracking | Google Ads Conv | 826329520 | aCJmCKWW7-YbELCTg4oD | CE - gf_submit - Portugal PGV | ✅ Active (Portugal only) |

**PixelYourSite Note:** The Google Ads pixel in PixelYourSite was disabled (2026-03-19) because it loaded a duplicate AW-826329520 tag that interfered with GTM's conversion tracking. Site Kit (GT-M3VGBZ) remains active for analytics. Do NOT re-enable PYS Google Ads pixel.

---

## Ad Groups

| Ad Group | ID | Status | Spend (today) | Conv | CTR |
|----------|-----|--------|---------------|------|-----|
| greece residency by investment | TBD | Enabled | $43.21 | 0 | 4.69% |
| greece golden visa | TBD | Enabled | $13.54 | 0 | 4.49% |

---

## Ads (2 RSAs — Same Creative in Both Ad Groups)

| Ad Group | Headlines | Descriptions | Status | Strength | Clicks | CTR | Cost |
|----------|-----------|-------------|--------|----------|--------|-----|------|
| greece residency by investment | Unlock Your EU Residency \| Secure Your Golden Visa \| Unlock Greece Golden Visa (+7 more) | Unlock EU Residency With Greece's Golden Visa! Invest Securely, Act Now! Join 3700+ Investors! (+2 more) | Eligible | Good | 10 | 4.69% | $43.21 |
| greece golden visa | Same as above | Same as above | Eligible | Good | 4 | 4.49% | $13.54 |

**Display URL:** www.mercan.com
**Final URL:** `https://www.mercan.com/greece-golden-visa/?utm_source=google&utm_medium=cpc&utm_campaign=greece-golden-visa-cp-05-2025`

---

## Keywords (8 total — All PHRASE match)

| Keyword | Match | Ad Group | Clicks | Impr | CTR | Cost | QS | Status |
|---------|-------|----------|--------|------|-----|------|----|--------|
| "greek citizenship by investment" | Phrase | greece residency by investment | 9 | 149 | 6.04% | $27.50 | — | Eligible |
| "greece citizenship by investment" | Phrase | greece residency by investment | 1 | 10 | 10.00% | $15.71 | — | Eligible |
| "greece investment visa" | Phrase | greece golden visa | 2 | 56 | 3.57% | $6.46 | — | Eligible |
| "greece golden visa program" | Phrase | greece golden visa | 1 | 24 | 4.17% | $4.56 | — | Eligible |
| "greece golden visa" | Phrase | greece golden visa | 1 | 6 | 16.67% | $2.52 | — | Eligible |
| "greece golden visa properties" | Phrase | greece golden visa | 0 | 0 | — | $0.00 | — | Eligible |
| "greece residency by investment" | Phrase | greece residency by investment | 0 | 4 | 0.00% | $0.00 | — | Eligible |
| "greece residency permit" | Phrase | greece residency by investment | 0 | 46 | 0.00% | $0.00 | Low | Eligible (Limited) — Rarely shown |

### 🚨 CRITICAL: AI Max Expanded Matches = 95.7% of Spend!

| Source | Clicks | Impr | Cost | % of Total |
|--------|--------|------|------|------------|
| AI Max expanded matches | 14 | 283 | $55.54 | **95.7%** |
| Actual keyword matches | 1 | 2 | $2.52 | **4.3%** |
| **Total** | **15** | **305** | **$58.06** | 100% |

Google's AI Max feature is expanding keywords far beyond their phrase match intent and spending almost the entire budget on irrelevant queries (see Search Terms below).

---

## Search Terms Analysis (Today — 2026-03-19)

### Overview
- 97 total search terms (today only)
- 5 search terms with clicks, $30.88 visible cost
- **ALL search terms are "AI Max" expanded matches** — zero from actual phrase match keywords
- 0 conversions

### Search Terms with Clicks

| Search Term | Source | Clicks | Cost | Relevance |
|-------------|--------|--------|------|-----------|
| apply for europe visa | AI Max | 1 | $15.71 | ❌ IRRELEVANT — generic Europe |
| greek real estate | AI Max | 1 | $10.17 | ⚠️ Low intent — browsing |
| how can i move to europe as an american | AI Max | 1 | $2.84 | ❌ IRRELEVANT — generic Europe |
| greece visas for us citizens | AI Max | 1 | $1.10 | ✅ Relevant |
| american moving to greece | AI Max | 1 | $1.06 | ⚠️ Informational |

### Irrelevant Search Term Patterns (from 97 terms)

| Pattern | Issue | Examples |
|---------|-------|---------|
| Generic "Europe" queries | Not Greece-specific | "apply for europe visa", "how to get a visa for europe", "apply for citizenship in europe" |
| **Spanish language** | Wrong language! | "visa europea", "embajada de grecia en estados unidos", "visas de trabajo en europa" |
| Greek real estate browsing | Not investment visa | "kolonaki apartments for sale", "villas for sale in mykonos greece" |
| Jobs/moving | Not investment program | "jobs in greece for americans", "americans moving to greece" |
| Generic citizenship | Not investment-specific | "apply for greek citizenship online" |

---

## Negative Keywords

### Current Status
- No campaign-level or ad-group-level negatives have been audited yet
- Given the AI Max expanded match problem, negatives are CRITICAL

### Recommended Campaign-Level Negatives (Based on Search Terms)

**Must add after reviewing 30-day search term data:**
- Generic Europe (if not already negated): "europe visa" PHRASE, "european visa" PHRASE, "european citizenship" PHRASE
- Spanish language terms: "visa europea" EXACT, "embajada" PHRASE, "trabajo" PHRASE
- Real estate browsing: "apartments for sale" PHRASE, "villas for sale" PHRASE, "properties for sale" PHRASE (keep "golden visa properties")
- Jobs: "jobs in greece" PHRASE, "work in greece" PHRASE
- Wrong programs: Various country names not related to Greece
- Low intent: "how to move to" PHRASE, "cost to move" PHRASE

**⚠️ Do NOT add negatives until 30-day data is reviewed. Today's data is just one day snapshot.**

---

## Known Issues

### Issue 1: Conversion Tracking ✅ FULLY VERIFIED
- **Status:** RESOLVED & VERIFIED (2026-03-19)
- **Impact:** CRITICAL — Was spending $200/day with no conversion data
- **Root Cause:** No GTM tag for Greece conversion action (ID: 7144337715), compounded by PixelYourSite plugin interference
- **Fix Applied:**
  1. Created "Greece GV - USA CP - Conversion Tracking v2" tag in GTM-KWFH5X9T.
     - **Version 5** (initial fix): Tag created with correct config but compiled container had incorrect trigger-tag rule mappings.
     - **Version 6** (bug fix): Re-published to regenerate compiled container with correct mappings.
  2. **Disabled PixelYourSite Google Ads pixel** — PYS was loading AW-826329520 directly (duplicate of GTM's Google Tag), which interfered with GTM's dataLayer processing and likely set consent mode defaults that blocked conversion tags.
  - Conv ID: 826329520, Label: hMe8CLPl184aELCTg4oD. Trigger: gf_submit event filtered to /greece-golden-visa/ pages.
- **End-to-End Test PASSED (2026-03-19):** `dataLayer.push({event:'gf_submit',formId:26})` on `/greece-golden-visa/` → 4 network requests to googleadservices.com with `label=hMe8CLPl184aELCTg4oD` and `en=conversion` — all from GTM-KWFH5X9T (container 246465919). Primary request returned **200 OK**.

### Issue 2: AI Max Burning 95%+ Budget on Irrelevant Queries ❌
- **Status:** UNRESOLVED
- **Impact:** HIGH — Almost all spend wasted on non-converting, irrelevant queries
- **Root Cause:** Maximize Conversions bidding with zero conversion data = algorithm has no signal. AI Max expands matches aggressively with nothing to optimize towards.
- **Fix:**
  1. Fix conversion tracking first
  2. Switch to Maximize Clicks while conversion tracking stabilizes
  3. Consider disabling AI Max expanded matches in campaign settings if available
  4. Add negative keywords to block irrelevant patterns

### Issue 3: Portugal Sitelinks on Greece Ads ⚠️
- **Status:** UNRESOLVED
- **Impact:** MEDIUM — Confusing user experience, Portugal links showing on Greece ads
- **Root Cause:** Account-level sitelink extensions applying to all campaigns
- **Fix:** Create campaign-specific sitelinks for Greece, or exclude Portugal sitelinks from this campaign

### Issue 4: "greece residency permit" — Low Quality Score ⚠️
- **Status:** MONITORING
- **Impact:** LOW — Keyword rarely shown, $0 spend
- **Fix:** Consider pausing or improving ad relevance for this keyword

### Issue 5: Portugal Conversion Tag Firing on Greece Page ✅ FIXED (V7)
- **Status:** RESOLVED (2026-03-19, Version 7)
- **Impact:** MEDIUM — Portugal conversion label (`-YHvCK6ejJsZELCTg4oD`) was firing on `gf_submit` on the Greece page, recording false Portugal conversions from Greece form submissions
- **Root Cause:** The "Google Ads Conversion Tracking" tag (label `-YHvCK6ejJsZELCTg4oD`) was ACTIVE (not paused as documented). Its trigger (`CE - gf_submit`) had NO page path filter — it fired on ALL gf_submit events across all pages.
- **Fix Applied:** Paused the tag in GTM and published as Version 7. Portugal conversions are handled by the page-filtered "PGV LP - CT Conversion Tracking" tag (label `aCJmCKWW7-YbELCTg4oD`). Verified: after V7, only Greece label (`hMe8CLPl184aELCTg4oD`) fires on Greece page.

### Issue 6: Spanish Language Search Terms ⚠️
- **Status:** UNRESOLVED
- **Impact:** MEDIUM — Wasting impressions on Spanish queries in an English campaign
- **Root Cause:** AI Max expanded matches not respecting language targeting
- **Fix:** Add Spanish term negatives, verify campaign language settings

### Issue 7: Bidding Strategy — KEEP Maximize Conversions ✅
- **Status:** RESOLVED — User confirmed campaign was generating great leads, DO NOT switch bidding strategy
- **Impact:** N/A — Conversion tracking now fixed (Issue 1), Maximize Conversions will have data to optimize
- **Current:** Maximize Conversions (Target CPA $60.00) — KEEP AS-IS
- **Note:** User explicitly said switching strategy would kill performance. Now that conversion tracking is fixed, the bidding algorithm will start receiving conversion signals.

---

## Optimization Priority (Action Plan)

| Priority | Action | Impact | Dependencies |
|----------|--------|--------|-------------|
| ✅ DONE | Fix conversion tracking — Greece GTM tag + PYS disabled | CRITICAL | COMPLETED & VERIFIED 2026-03-19 — GTM V6, PYS Google Ads pixel disabled, end-to-end test passed |
| ❌ CANCELLED | Switch bidding to Maximize Clicks (max CPC $8) | N/A | User confirmed: DO NOT switch — campaign generating great leads |
| 🟡 P1 | Add campaign-level negative keywords | HIGH | Need 30-day search term data |
| 🟡 P1 | Replace Portugal sitelinks with Greece-specific ones | MEDIUM | Asset/sitelink management |
| 🟢 P2 | Review AI Max expanded matches setting | MEDIUM | After conversion tracking fixed |
| 🟢 P2 | Audit 30-day search terms for patterns | MEDIUM | Need date range access |
| 🟢 P3 | Pause "greece residency permit" (low QS) | LOW | None |

---

## Change Log

| Date | Change | Details | Expected Impact |
|------|--------|---------|-----------------|
| 2026-03-19 | **INITIAL AUDIT** | Full campaign analysis performed. Identified: broken conversion tracking (no GTM tag for Greece), AI Max spending 95%+ on irrelevant queries, Portugal sitelinks on Greece ads, Spanish search terms | Baseline established |
| 2026-03-19 | **CONVERSION TRACKING FIX** | Created GTM tag "Greece GV - USA CP - Conversion Tracking" in backup container (GTM-KWFH5X9T). Conv ID: 826329520, Conv Label: hMe8CLPl184aELCTg4oD. Trigger: CE - gf_submit - Greece GV (Custom Event gf_submit filtered to Page Path contains /greece-golden-visa/). Published as Version 5. | Conversion tracking now ACTIVE — Maximize Conversions bidding can now optimize with real data |
| 2026-03-19 | **V5 COMPILED CONTAINER BUG FIX** | Version 5's compiled CDN container had incorrect trigger-tag rule mappings: Greece GV conversion tag was mapped to Portugal path predicate, and Custom HTML tag was mapped to Greece path predicate. Workspace/preview version was correct, but the published compiled JS was broken. Re-published as Version 6 ("V6 - Re-publish to fix compiled container"). V6 CDN verified: Rule 4 correctly maps gf_submit + /greece-golden-visa/ → Greece GV conv tag (label hMe8CLPl184aELCTg4oD). Tag renamed to "v2" to force workspace change. | V6 compiled container now has CORRECT trigger-tag mappings. Production visitors will get correct conversion tracking. |
| 2026-03-19 | **PIXELYOURSITE GOOGLE ADS PIXEL DISABLED** | Disabled Google Ads pixel (AW-826329520) in PixelYourSite WordPress plugin. PYS was loading a duplicate Google Ads tag that interfered with GTM-KWFH5X9T's conversion tracking — `dataLayer.push` was failing and no conversion requests were being sent. After disabling PYS Google Ads pixel, end-to-end test passed: `gf_submit` push → 4 conversion requests with label `hMe8CLPl184aELCTg4oD` → 200 OK. Site Kit (GT-M3VGBZ) remains active for analytics. | Conversion tracking now fully operational. PixelYourSite Google Analytics pixel was already disabled. |
| 2026-03-19 | **PAUSED GENERIC CONVERSION TAG (V7)** | Paused "Google Ads Conversion Tracking" tag (label `-YHvCK6ejJsZELCTg4oD`) in GTM-KWFH5X9T. This tag had trigger `CE - gf_submit` with NO page path filter, causing it to fire on ALL pages including Greece. Published as Version 7. Portugal conversions handled by page-filtered "PGV LP - CT" tag. Verified: after V7 only Greece label (`hMe8`) fires on Greece page, zero Portugal label requests. | No more false Portugal conversions from Greece form submissions. Clean conversion attribution per campaign. |
| | | | |

---

## Verification Checklist

After implementing fixes, verify:
- [x] Greece GTM conversion tag created and published (Version 5, 2026-03-19)
- [x] V5 compiled container bug identified and fixed — re-published as Version 6 (2026-03-19)
- [x] V6 CDN compiled rules verified correct: gf_submit + /greece-golden-visa/ → Greece GV conv tag (hMe8CLPl184aELCTg4oD)
- [x] **END-TO-END TEST PASSED (2026-03-19):** `dataLayer.push({event:'gf_submit',formId:26})` on /greece-golden-visa/ → conversion requests with label hMe8CLPl184aELCTg4oD fired → 200 OK. PixelYourSite Google Ads pixel had to be disabled first (was interfering).
- [x] Conversion requests confirmed reaching googleadservices.com and 1p-conversion endpoints
- [x] Bidding strategy: KEEP Maximize Conversions (user confirmed — DO NOT switch)
- [ ] Greece-specific sitelinks created
- [ ] Portugal sitelinks excluded from Greece campaign
- [ ] Campaign-level negatives added (after 30-day data review)
- [ ] Monitor for 7 days post-fix for first real conversions
- [ ] After ≥15 conversions in 30 days, switch back to Maximize Conversions
