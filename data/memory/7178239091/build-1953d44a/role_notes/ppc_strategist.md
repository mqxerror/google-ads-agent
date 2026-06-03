# Ppc Strategist Notes

**Last updated:** 2026-04-25 23:13

**Task:** Run stage 5 for campaign build

**Critical Details:** https://goldenvisas.mercan.com/panama`
# PPC Strategist — Stage 5: Campaign Build Execution
## Panama Qualified Investor Visa (build-1953d44a)
All 4 prior stages are complete. Here's the full build plan before I execute via MCP tools.
## BUILD PLAN
### Campaign Settings
| Setting | Value | Rationale |
|---------|-------|-----------|
| **Name** | Panama QIV — Golden Visa USA | Clear program + geo identifier |
| **Status** | PAUSED | Always launch paused per account rules |
| **Network** | Search only | No Display — HNW intent-based targeting |
| **Geo target** | United States | Per competitor intel — competitors concentrated in NY, CA, TX, AZ, MI |
| **Language** | English | |
### 5 Ad Groups (each with keywords + 1 RSA)
| Ad Group | Keywords | Match Types | RSA |
|----------|----------|-------------|-----|
### Campaign-Level Negatives
31 phrase-match + 3 exact-match negatives (from Search Term Hunter's list — geographic confusion, wrong programs, DIY intent, eligibility language)
### Landing Page
`https://goldenvisas.mercan.com/panama` — all RSAs point here
## EXECUTION ORDER
1. `budget__create_campaign_budget` → $35/day
2. `campaign__create_campaign` → Search, PAUSED, Maximize Clicks ($5 cap)
3. `campaign_criterion__add_location_criteria` → United States
4. `campaign_criterion__add_language_criteria` → English
5. `ad_group__create_ad_group` × 5
6. `keyword__add_keywords` × 5 (per ad group)
7. `ad__create_responsive_search_ad` × 5
8. `campaign_criterion__add_negative_keyword_criteria` → 34 negatives
**This is a HIGH-IMPACT action (creating a full campaign). Shall I proceed with the build?**
Any changes to budget ($35/day), bidding (Maximize Clicks / $5 cap), or structure before I execute?
*— PPC Strategist, 2026-04-25*

---

## Session Log

### 2026-04-25 21:26 — but 250 budget and get the optimal bidding size and we use manual cpc no cheap t

**Task:** but 250 budget and get the optimal bidding size and we use manual cpc no cheap traffic
Got it — $250/day budget, Manual CPC, premium positioning. Let me check what tools I have for the bidding strategy change.Two changes needed:
1. **Budget → $250/day** — I can do this now via MCP
2. **Manual CPC** — the campaign update tool doesn't support changing bidding strategy, but I can set optimal ad group-level CPC bids now and you'll flip the strategy to Manual CPC in Google Ads UI (one toggle)
Here's the optimal bid plan based on keyword planner CPC data — bidding above high-end estimates to lock top-of-page positions:
| Ad Group | High-End CPC | My Bid | Rationale |
|----------|-------------|--------|-----------|
At these bids with $250/day: ~45–55 premium clicks/day. No junk traffic.
Updating budget and setting all 5 ad group bids now:All done. Here's what was updated:
## Changes Applied
| Setting | Before | After |
|---------|--------|-------|
## One Manual Step Needed
The MCP API can't change the bidding strategy type on an existing campaign. You need to switch from **Maximize Clicks → Manual CPC** in the Google Ads UI:
1. Go to campaign **23798023420** (Panama QIV — Golden Visa USA)
2. **Settings → Bidding → Change bid strategy → Manual CPC**
3. Uncheck "Enhanced CPC" (we want pure manual control for now)
Once you flip that toggle, the ad group bids above take effect immediately — premium positioning, no cheap traffic.
*— PPC Strategist, 2026-04-25*

### 2026-04-25 23:13 — keep them for now , stop al experiments related to the stale campaign in ui keep

**Task:** keep them for now , stop al experiments related to the stale campaign in ui keep the running and spending only
Let me navigate to the Experiments page in Google Ads and end those stale experiments.It redirected to account chooser. Let me select the right account.I'm on the Experiments page but it's showing empty — the experiments might be in a different view. Let me check if there's a table/list view.I can see 5 experiments on page 1 (9 total). All show "Complete Not applied" status. These are the ones cre
1. **[Broad Match] PORTUGAL GOLDEN VISA - Investment Funds** — creates the PGV Investment Funds trial campaigns
2. **Greece Maximize Conversion** — creates the Greece GV Maximize Conversion trial
3. **Maximize Click Strategy Test** — another PGV trial
4. **PGV - Impression Share Bidding Strategy** — creates the Impression Share trial
Let me click into the first one and end it. I'll start with the Broad Match experiment.I'm in the experiment detail page for "[Broad Match] PORTUGAL GOLDEN VISA - Investment Funds". Status is "Complete (Not applied)". I need to find an option to end/remove this experiment. Let me take a snapshot to find the action buttons.I found the **"Remove Experiment"** button (uid=4_47). This experiment has 0
1. **Golden Visa Final Seconf landing page test** — Complete Not applied
2. **Greece Maximize Conversion** — Complete Not applied
3. **Maximize Click Strategy Test** — Complete Not applied
4. **PGV - Impression Share Bidding Strategy** — Complete Not applied
5. **pgv 2025** — Saved as draft (also stale)
6. **PGV Fund Experiment Target CPA** — Complete Not applied
7. **PGV Funds Maximize Conversion Experiment** — Complete **Applied** (this one was actually applied, skip)
8. **Test For Quarter 2 for PGV Investment Fund Search CP** — Complete Not applied
I can select multiple rows and bulk remove. Let me select all the "Complete Not applied" and "Saved as draft" ones. I'll check the select-all checkbox first, then deselect the one that's "Complete Applied".
Actually, let me just select the ones to remove individually. Let me click into each one. Starting with "Golden Visa Final Seconf landing page test".The "Golden Visa Final Seconf landing page test" row isn't visible — it must have scrolled past or the first removed experiment shifted the list. I can see 8 experiments now. The one I already removed (Broad Match) is gone, and the "Golden Visa Final 
Actually looking more carefully, I see 7 experiments here (8 total minus 1 removed = 7, but it says "1 - 8 of 8"). The landing page test might not be visible. Let me scroll up.Good — all 8 experiments visible. I need to remove 7 of them (all except "PGV Funds Maximize Conversion Experiment" which is "Complete Applied"). Let me click into "Golden Visa Final Seconf landing page test" to remove it.I 
Actually, looking at the snapshot, there's no "Remove Experiment" button visible. Ad variation experiments may not have a remove option since they don't create trial campaigns. This one (Jul 2023 - Aug 2024) is already complete and has 0 campaigns associated. Let me go back and focus on the ones that actually have trial campaigns (the stale ones).Now let me update the todo list and go to the next 
| Experiment | Status | Action |
|---|---|---|
| Golden Visa Final Seconf landing page test | Complete Not applied | **Kept** — Ad variations type, no trial campaign |
| PGV Funds Maximize Conversion Experiment | Complete Applied | **Kept** — intentionally applied |
**Summary of experiments removed this session (7 total):**
1. [Broad Match] PGV Investment Funds
2. Greece Maximize Conversion
3. Maximize Click Strategy Test
4. PGV - Impression Share Bidding Strategy
5. pgv 2025 (draft)
6. PGV Fund Experiment Target CPA
7. Test For Quarter 2 for PGV Investment Fund Search CP
The stale experiment trial campaigns and their phantom budgets ($750/day allocated, 0 impressions) are now cleaned up. Portugal ($80/day) and Greece ($80/day) campaigns remain running as requested.
