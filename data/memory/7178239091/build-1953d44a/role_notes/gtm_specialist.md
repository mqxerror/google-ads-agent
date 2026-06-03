# Gtm Specialist Notes

**Last updated:** 2026-04-25 21:22

**Task:** Run stage 6 for campaign build

**Critical Details:** https://goldenvisas.mercan.com/panama`, GTM-K6864NBH
Stage 6: Executing the full campaign build via MCP tools. Let me start with budget and campaign creation.Budget created: `customers/7178239091/campaignBudgets/15541449304`. Now creating the campaign.Campaign created: ID **23798023420** (PAUSED). Now adding location + language criteria and creating the 5 ad groups.All targeting and ad groups created. Here's my tracking:
| Component | ID |
|---|---|
| **Campaign** | 23798023420 |
| **AG1: Panama Golden Visa** | 194279247525 |
| **AG2: Panama Investor Visa** | 195600842043 |
| **AG3: Panama Residency** | 194645937774 |
| **AG4: Panama Citizenship** | 201090563932 |
| **AG5: Panama Real Estate** | 197478198642 |
| **Location** | United States (2840) |
| **Language** | English (1000) |
Now adding keywords to all 5 ad groups.All 19 keywords added across 5 ad groups. Now creating the 5 RSAs.All 5 RSAs hit character limits — the em-dash `—` counts as 3 bytes in the API. Let me fix all descriptions and the one headline, then retry.4 of 5 RSAs created. RSA 2 (AG2: Investor Visa) had one description still over 90 chars. Fixing and retrying.All 5 RSAs created. Now adding the 34 campaig
# Stage 6 Complete — Panama QIV Campaign Built
## Campaign: Panama QIV — Golden Visa USA
| Component | ID | Status |
|---|---|---|
## Ad Groups & Assets
| Ad Group | ID | Keywords | RSA |
|---|---|---|---|
## Totals
- **19 keywords** across 5 ad groups
- **5 RSAs** (75 headlines, 20 descriptions)
- **34 negative keywords** (31 phrase + 3 exact)
- **Landing page:** `https://goldenvisas.mercan.com/panama`
- **Bidding:** Maximize Clicks with $5 max CPC cap
- **Conversion:** GV Lead (fc6FCO3YnI4cELCTg4oD) — existing account-wide tag
## GTM Note
Per account records, the dual-tracking layer (inline `gtag()` + GTM safety net in container GTM-K6864NBH) already fires on all `goldenvisas.mercan.com` pages. The GV Lead conversion action (`fc6FCO3YnI4cELCTg4oD`) will capture form submissions on the Panama page automatically. **No new tags needed.**
## Before Enabling
1. Verify the form on `/panama` fires GV Lead conversion (quick test in GTM Preview Mode)
2. Confirm the 90-day attribution window is set on GV Lead (open action item from account notes)
3. When ready, change campaign status from PAUSED → ENABLED
**Campaign is ready to launch on your signal.**
*— GTM Specialist, 2026-04-25*