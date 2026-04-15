# Search Term Hunter Notes

**Last updated:** 2026-04-12 13:34

**Task:** what facts the other campaign should no or what the other campaign like portugal mena campaign know before I start working on optimizing them?

**Critical Details:** AW-826329520, GTM-K6864NBH
## Cross-Campaign Intelligence Briefing — Portugal & MENA
Everything learned from Greece V2 that applies to both campaigns:
### 1. Conversion Tracking — Single Source of Truth
**GV Lead is the ONLY primary conversion action for ALL campaigns.**
| Detail | Value |
|--------|-------|
| Conversion Action | GV Lead |
| ID | 7546023021 |
| Label | `fc6FCO3YnI4cELCTg4oD` |
| GTM Container | GTM-K6864NBH |
| Attribution | GCLID — automatic. No per-campaign tags needed. |
- **PGV LP - CT** (ID: 7463488293) was changed to **SECONDARY** — it no longer drives bidding
- **form_submit GA4** (ID: 6953214477) is **SECONDARY** — never use as primary
- The direct `gtag('event', 'conversion', ...)` fires in `SimplifiedLeadForm.tsx` on form submit
- PixelYourSite Google Ads pixel is **DISABLED** — do NOT re-enable it (it was causing duplicate AW-826329520 tag and blocking GTM dataLayer)
### 2. Landing Page — The #1 Conversion Lever
Greece went from 0 conversions to tracking-ready with two changes:
1. **Form above the fold on desktop** — Page B (`/greece-golden-visa`) wins because the form is in the hero. Page A buried it at 1,517px. Check where Portugal/MENA forms are positioned.
2. **Correct URL in ads** — Verify the ad final URLs point to `goldenvisas.mercan.com/portugal` and `goldenvisas.mercan.com/mena` (not old mercan.com paths). Old URLs were 404ing for Greece.
Both pages are `noindex, nofollow` — pure PPC pages, no SEO concerns.
### 3. Consent Mode — Critical for Attribution
Without this, conversions fire but **can't be matched to clicks** (GCLID lost).
- All 4 consent signals must be `granted` for US/English-language traffic
- For MENA: UAE (PDPL) and Saudi (PDPA) have regional laws — consent grants should be region-specific
- Verify in browser: open the LP, run `gtag('get', 'AW-826329520', 'consent_state', console.log)` — should return all granted
### 4. Bidding Strategy Health Check
Before touching Portugal/MENA bidding:
| Check | Threshold | Action if Below |
|-------|-----------|-----------------|
Greece had 0 conversions on Maximize Conversions — the algorithm was guessing on targeting. Same risk exists for Portugal/MENA if conversion tracking isn't verified first.
### 5. Search Term Patterns to Watch
From the Greece audit, these patterns bled through before negatives were added:
| Pattern | Fix |
|---------|-----|
| Spanish language (`grecia`, `visa europea`, `embajada`) | Add `grecia` [PHRASE] as negative |
| Generic Europe queries | Add `europe visa` [PHRASE], `european citizenship` [PHRASE] |
| Real estate browsing (`apartments for sale`, `villas for sale`) | Phrase negatives — keep `golden visa properties` |
| Job/work queries | `jobs in` [PHRASE], `work permit` [PHRASE] |
For MENA: Arabic queries may bleed in from non-target countries. Check if campaign language targeting is set to Arabic + English or just one.
### 6. Known MENA-Specific Issue
**Phantom conversions firing 3-5 AM** — flagged in GTM notes. Likely bot traffic. Before optimizing MENA, pull a conversion time-of-day report. If conversions cluster at 3-5 AM, the conversion data is corrupted and bidding is optimizing toward bots.
### 7. One-Change-Per-Day Rule — Always
Never change ads AND bidding on the same day. Wait 7 days minimum after any change before evaluating. This is especially critical for Portugal which may have historical conversion data the bidding strategy is using.
### 8. Account Structure Reminder
| Level | ID |
|-------|----|
| MCC (Login with) | 6895949945 (MQXDev) |
| Sub-Manager | 7192648347 (Wassim) |
| Active campaigns | 7178239091 (Mercan Group) |
Always login with `6895949945` as the login customer ID, operate on `7178239091`.
**Bottom line for whoever runs Portugal/MENA next:** Verify tracking fires on the LP first (simulate a form submit, check for `fc6FCO3YnI4cELCTg4oD` in network requests). If it doesn't, nothing else matters — you're flying blind.
*— Search Term Hunter*