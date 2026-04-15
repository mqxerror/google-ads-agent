# Ppc Strategist Notes

**Last updated:** 2026-04-15 19:11

**Task:** Run stage 5 for campaign build
# Stage 5: Campaign Builder — Executing the Blueprint
Per the Creative Director's approved plan, I'm now building the Greece Golden Visa - Turkey campaign. Let me execute step by step.
**Step 1:** Create the campaign budget ($60/day).Creating the budget now.Budget created: **ID 15507840903** ($60/day).
**Step 2:** Create the campaign with Maximize Clicks bidding.Campaign created: **ID 23758877756** (PAUSED).
**Step 3:** Configure bidding, location (Turkey), and language targeting in parallel.Adding Turkey location and Turkish + English language targeting in parallel.Location: Turkey. Languages: Turkish + English. All set.
**Step 4:** Create the 3 ad groups. Let me fetch the tool and create them.
Creating all 3 ad groups in parallel with $5 max CPC bid.3 ad groups created:
- **yunanistan-golden-visa**: ID 193233675497
- **yunanistan-oturum-gayrimenkul**: ID 192400794941
- **greece-golden-visa-en**: ID 198513892027
**Step 5:** Add keywords to each ad group (15 total, all Phrase match).
Adding keywords to all 3 ad groups in parallel.All 15 keywords added (all Phrase match).
**Step 6:** Create RSAs — one per ad group.Creating all 3 RSAs in parallel. Note: headline pinning will need to be set in the Google Ads UI after build (API tool doesn't support pin positions).All 3 RSAs created successfully.
**Step 7:** Add campaign-level negative keywords (21 negatives from Search Term Hunter).24 campaign-level negatives added. Now adding ad-group-level negatives for the English ad group.9 ad-group negatives added to the English AG.
# Stage 5: Build Complete — Summary
## Greece Golden Visa - Turkey Campaign
| Component | Details | ID |
|-----------|---------|-----|
### Ad Groups & Keywords
| Ad Group | ID | Keywords | Match |
|----------|-----|----------|-------|
### RSAs Created
| Ad Group | Ad ID | Headlines | Descriptions |
|----------|-------|-----------|-------------|
### Negative Keywords
- **Campaign-level:** 24 negatives (20 phrase + 4 exact year exclusions)
- **Ad-group-level:** 9 negatives on English AG (real estate browsing, relocation, lifestyle)
## POST-BUILD TASKS (manual)
| Task | Priority | Notes |
|------|----------|-------|
| **Fix `lang="en"` → `lang="tr"`** on landing page | BLOCKER before enabling | Hurts Quality Score for Turkish keywords |
| **Fix English meta description** on Turkish page | HIGH | Quality Score impact |
| **Create Turkey-specific conversion action** | REQUIRED before enabling | Avoid cross-contamination with USA campaign data |
| **Add WhatsApp to landing page** | NICE-TO-HAVE | Dominant channel in Turkey |
**Campaign is PAUSED and ready.** Do not enable until the landing page `lang` fix and Turkey conversion action are in place.
*— PPC Strategist (Stage 5: Builder)*