# Gtm Specialist Notes

**Last updated:** 2026-07-16 13:17

**Task:** EXECUTE verification step 1 (user-approved) for campaign 24036236041 ONLY. (A) Load https://www.mercan.com/lp/panama-qualified-investor-program in the Chrome browser (new_page → take_screenshot → take
Executing both in parallel — opening the landing page in Chrome and querying conversion actions via GAQL simultaneously.Let me search for the new_page tool and then execute both the browser navigation and GAQL query in parallel.Executing both in parallel now — Chrome browser render and GAQL conversion action pull simultaneously.

---

## Session Log

### 2026-07-16 13:16 — User reports tracking IS working: a lead arrived with a click ID (GCLID). Critic

**Task:** User reports tracking IS working: a lead arrived with a click ID (GCLID). Critical distinction to verify for campaign 24036236041 (customer 7178239091) ONLY: a CRM lead carrying a GCLID proves the for

**Critical Details:** GTM-K6864NBH
Running all three GAQL queries in parallel now.Good, I can see the tools. Let me load the schema for the execute query tool and run all three queries in parallel.Running all three queries in parallel now.Now that schemas are loaded, running all three queries in parallel.The GAQL tool is blocked by a role-permission mismatch in the backend (`google_ads_search_google_ads` single-underscore vs the ro
## Tracking Verification — GTM Specialist · Campaign 24036236041
**New premise (user-confirmed):** A CRM lead arrived carrying a GCLID. This resolves the form-existence question — the page renders, the form submits, and the GCLID was captured. The static-fetch "no form signal" flag is closed.
**What GCLID capture proves vs. does NOT prove:**
- ✅ Form exists and renders in browser
- ✅ Click ID passed through URL → form hidden field → CRM (attribution chain intact)
- ❌ Does NOT prove a Google Ads conversion action fired on form submit
**Conversion action registry (from in-context data, all IDs sourced from account guidelines):**
| Action | ID | Type | Primary? | Notes |
|---|---|---|---|---|
| **Panama QIP** | **—** | **—** | **MISSING** | **No entry exists** |
**Verdict: (b) — lead captured, but almost certainly firing into a SECONDARY action Maximize Conversions cannot use.**
With no dedicated Panama QIP PRIMARY WEBPAGE action in the registry, this campaign is either optimizing against `form_submit` (GA4, secondary — fires on every form on the entire mercan.com domain) or against nothing at all. Both explain the 0-conversion reading in Google Ads despite a real lead arriving with a GCLID.
**Two GAQL queries I couldn't execute (run these to close the final gaps):**
**Required action — create the Panama QIP conversion action:**
The account rule is clear: every campaign needs its own dedicated PRIMARY WEBPAGE action. For Panama QIP this should be:
- **Type:** WEBPAGE (URL-based trigger on the thank-you / confirmation URL after form submit, OR on the `mercan.com/lp/panama-qualified-investor-program` post-submit state)
- **Category:** SUBMIT_LEAD_FORM
- **Primary for bidding:** YES
- **Attribution window:** 90 days (mandatory for this account — high-consideration product)
- **Install:** via GTM-K6864NBH as a Google Ads conversion tag scoped to the confirmation URL (do NOT add per-campaign inline gtag — the dual-tracking architecture stays; this goes through GTM as the safety net)
Once the action is live and firing, upload the arrived GCLID as a retroactive click conversion (`conversion_upload_upload_click_conversions`) so Maximize Conversions gets its first real signal immediately rather than waiting for the next organic lead.
*— GTM Specialist*

### 2026-07-16 13:17 — Orchestrated finding

{
  "summary": "Form and GCLID capture confirmed; the 0-conversion reading is almost certainly a missing PRIMARY Panama QIP conversion action, not a broken form \u2014 create the action, set 90-day window, upload the GCLID retroactively.",
  "findings": [
    {
      "claim": "A Panama QIP PRIMARY WEBPAGE conversion action does not exist \u2014 the lead fired into a secondary action Maximize Conversions cannot use as its optimization signal",
      "severity": "high",
      "confidence": 0.88,
      "sources": [
        "In-context conversion registry: Portugal GV 7463488293 PRIMARY, Greece GV 7144337715 PRIMARY, EB3 Brazil \u2014 all other actions SECONDARY; no Panama QIP entry",
        "Account rule: every campaign must have its own dedicated PRIMARY WEBPAGE conversion action",
        "0 recorded conversions in Google Ads dashboard despite user-confirmed lead with GCLID"
      ],
      "disconfirmed_by": "campaign_conversion_goal GAQL query shows this campaign is biddable against an existing PRIMARY action that fired on the lead's submit \u2014 at which point 0 conv is pure attribution lag",
      "id": "c1-f0"
    },
    {
      "claim": "The landing page form exists and captures GCLIDs \u2014 the static-fetch 'no form signal' finding is now closed",
      "severity": "low",
      "confidence": 0.99,
      "sources": [
        "User confirmed: CRM lead arrived with click ID from this campaign"
      ],
      "disconfirmed_by": "Nothing \u2014 user evidence is direct and conclusive",
      "id": "c1-f1"
    }
  ]
}
