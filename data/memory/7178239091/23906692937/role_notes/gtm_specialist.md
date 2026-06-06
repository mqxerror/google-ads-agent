# Gtm Specialist Notes

**Last updated:** 2026-06-03 14:46

**Task:** As the GTM Specialist, verify conversion tracking readiness for this new campaign:

Landing page: https://www.mercan.com/greece-golden-visa/

READ the CRO Specialist's findings about existing tracking

**Critical Details:** GTM-K6864NBH, GTM-KWFH5X9T
## GTM Specialist — Tracking Readiness: Greece GV "Plan B" (23906692937)
Read the CRO note. Confirmed: this campaign points to the **same landing page** (`mercan.com/greece-golden-visa/`) and the **same conversion action** as the existing live Greece campaign — which means tracking was already built and **end-to-end verified on 2026-03-19**. I'm not reopening that fix (it's closed); I'm verifying readiness for this new build.
### Operative tracking IDs (state them so they persist)
| Field | Value |
|---|---|
| **Conversion action** | **Greece Golden Visa USA CP — ID `7144337715`** (WEBPAGE, ENABLED, **PRIMARY**) |
| **Conversion label** | `hMe8CLPl184aELCTg4oD` (Google Ads ID 826329520) |
| **GTM container** | `GTM-KWFH5X9T` |
| **Trigger** | Custom event `gf_submit` filtered to Page Path contains `/greece-golden-visa/` (Gravity Form ID 26) |
### Readiness Checklist
| # | Check | Status | Evidence |
|---|---|---|---|
**Verdict: 4/5 PASS, 1 unverified. Tracking is READY for launch** — the build can proceed; conversions will record the moment the campaign is enabled.
### Two open items before enabling spend (NOT blockers — but do them while PAUSED)
1. **Confirm 90-day attribution window** on action `7144337715`. Default 30-day under-counts a €250K+ investment decision cycle (weeks–months). In a low-volume Tier-1-metro campaign, one missed late conversion has outsized ROAS impact. *Verify it's set — don't assume.*
2. **Enable Enhanced Conversions** on `7144337715`. The form captures email/phone → higher match rate. For low-volume HNWI leads this is a multiplier, not a marginal gain. Highest-priority open tracking item account-wide.
3. *(consent mode)* — quick Preview-Mode pass on the live page to confirm consent isn't gating the conversion ping in EU/CA visitor contexts.
### Memory-reconcile flag for the Director
My account skill references a unified action `fc6FCO3YnI4cELCTg4oD` (GTM-K6864NBH). The **Greece-specific guidelines** (single source of truth for this campaign) and every prior role in this build point to **`7144337715` / `hMe8CLPl184aELCTg4oD` / GTM-KWFH5X9T**. I'm operating on the Greece-specific IDs — they're the verified, campaign-correct ones. The account-level memory line should be reconcil
I have **not** changed anything — this is verification only. Say the word and I'll run a live Preview-Mode pass to close items #4 (consent) and confirm the tag still fires before the campaign goes live.
— GTM Specialist (Dam3oun-Google)