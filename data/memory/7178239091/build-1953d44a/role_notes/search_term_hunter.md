# Search Term Hunter Notes

**Last updated:** 2026-04-25 21:16

**Task:** Run stage 3 for campaign build
# Search Term Hunter — Stage 3: Keyword Strategy & Negative Mining
## Panama Qualified Investor Visa (build-1953d44a)
Per CRO Specialist and Competitor Intel findings, I have the full keyword landscape. Here's the complete keyword architecture.
## 1. AD GROUP KEYWORD MAP (with match types)
### AG1: Panama Golden Visa (brand program term)
| Keyword | Match Type | Monthly Vol | Est. CPC | Rationale |
|---------|-----------|------------|----------|-----------|
### AG2: Panama Investor Visa / QIV (program-specific)
| Keyword | Match Type | Monthly Vol | Est. CPC | Rationale |
|---------|-----------|------------|----------|-----------|
### AG3: Panama Residency by Investment
| Keyword | Match Type | Monthly Vol | Est. CPC | Rationale |
|---------|-----------|------------|----------|-----------|
### AG4: Panama Citizenship by Investment
| Keyword | Match Type | Monthly Vol | Est. CPC | Rationale |
|---------|-----------|------------|----------|-----------|
### AG5: Panama Real Estate Investment (supporting)
| Keyword | Match Type | Monthly Vol | Est. CPC | Rationale |
|---------|-----------|------------|----------|-----------|
**Note on AG5:** Do NOT add broad "panama real estate investment" (210/mo) — per the Greece tiebreaker rule, property-only intent without residency/visa signal = waste. Only exact-match combos that include residency/visa language.
## 2. STRATEGIC DECISIONS
### Friendly Nations Visa (1,000/mo) → **EXCLUDE**
The page mentions it in a badge but the entire funnel is built for QIV ($300K investment). Friendly Nations is a different program with different requirements and investment levels. Adding it would:
- Dilute ad relevance (Quality Score hit)
- Send FNV searchers to a QIV page (bad experience, low conversion)
- Require separate landing page content to convert
**Recommendation:** Add as campaign-level phrase negative: `"friendly nations visa"`, `"friendly nations"`. If the business wants FNV traffic, build a separate campaign with a dedicated landing page.
### Pensionado Visa (720/mo) → **EXCLUDE**
Completely different program (retirement visa, no investment requirement). Campaign-level negative.
### "Move to panama" (1,000/mo) → **EXCLUDE for now**
This is lifestyle/relocation intent, not investment immigration intent. At $0.31–$2.29 CPC it's cheap, but these searchers want "how to move" guides, not a $300K investment consultation. Would burn budget with near-zero conversion rate for this offer.
**Recommendation:** Campaign-level phrase negative. Revisit only if a dedicated top-of-funnel landing page is built.
## 3. NEGATIVE KEYWORD LIST
### Campaign-Level Negatives (Phrase Match)
These are structurally irrelevant — no context makes them useful for QIV:
| Negative Keyword | Match | Category |
|-----------------|-------|----------|
| panama city florida | Phrase | Geographic confusion |
| panama city beach | Phrase | Geographic confusion |
| panama canal | Phrase | Tourist/geographic |
| panama hat | Phrase | Product confusion |
| panama papers | Phrase | News/scandal |
| panama jack | Phrase | Brand confusion |
| van halen panama | Phrase | Music |
| friendly nations visa | Phrase | Different program |
| friendly nations | Phrase | Different program |
| pensionado visa | Phrase | Different program |
| pensionado | Phrase | Different program |
| move to panama | Phrase | Relocation intent, not investment |
| relocating to panama | Phrase | Relocation intent |
| retire in panama | Phrase | Retirement, not investment immigration |
| retirement panama | Phrase | Retirement |
| student visa panama | Phrase | Wrong visa category |
| tourist visa panama | Phrase | Wrong visa category |
| work permit panama | Phrase | Employment visa |
| jobs in panama | Phrase | Employment |
| panama embassy | Phrase | Consular, not investment |
| do i qualify | Phrase | Eligibility screening (account rule — no quiz exists) |
| am i eligible | Phrase | Eligibility screening |
| eligibility check | Phrase | Eligibility screening |
| requirements checker | Phrase | Eligibility screening |
| free visa | Phrase | Budget/DIY |
| cheap visa | Phrase | Budget |
| visa application form | Phrase | DIY |
| how to apply myself | Phrase | DIY |
| sao tome | Phrase | Different country (appears on broad GV terms) |
### Campaign-Level Negatives (Exact Match)
| Negative Keyword | Match | Category |
|-----------------|-------|----------|
| [panama] | Exact | Pure country term, zero commercial intent |
| [panama visa] | Exact | Too generic — matches tourist/work/student visa |
| [visa panama] | Exact | Same |
### Ad-Group-Level Negatives (AG3: Residency — Phrase Match)
These are relevant in other ad groups but waste in the residency group:
| Negative Keyword | Match | Reason |
|-----------------|-------|--------|
**Hold list (DO NOT negate yet — monitor after launch):**
- `"buying property in panama"` — could be QIV research OR pure real estate. Apply Greece tiebreaker: wait for CTR/conversion data.
- `"panama tax benefits"` — informational but directly relevant to the offer's value prop. Let it run.
- `"panama residency cost"` — could be QIV budget research. Monitor.
## 4. MATCH TYPE STRATEGY
**Approach:** Phrase-dominant with exact-match protection for highest-intent terms.
- **Exact match** for: program-specific long-tails (`panama qualified investor visa`, `panama golden visa 2026`, `panama real estate investment visa`). These are conversion goldmines — protect them from broad match cannibalization.
- **Phrase match** for: core program terms (`panama golden visa`, `panama citizenship by investment`). Captures valuable long-tail variants while maintaining relevance control.
- **Broad match** for: ONE term only — `panama residency` in AG3. This is the discovery keyword. Smart bidding + the negative list above will filter junk. If CPA exceeds $15 after 2 weeks, switch to phrase.
- **No broad match** in AG1, AG2, AG4, AG5. CPCs are cheap enough that we don't need broad to maintain volume — the phrase keywords give us 800+ monthly searches combined.
## 5. IMPRESSION VOLUME ESTIMATE
|----------|------------------------|-----------------------------|--------------------|
These are pre-launch estimates from Keyword Planner volume. Actual impressions depend on bid strategy, budget, and Quality Score. The market is cheap — $500–$800/mo budget covers all core terms comfortably.
## 6. HANDOFF NOTES
**For PPC Strategist (campaign structure):**
- 5 ad groups mapped with keywords and match types above
- Start budget recommendation: $30–$40/day ($900–$1,200/mo) to cover all ad groups without throttling
- Bidding: Manual CPC or Maximize Clicks with $5 max CPC cap (new campaign, zero conversion history — don't start with smart bidding)
- Conversion action needed: create a Panama-specific conversion action (WEBPAGE type) or use the existing GV Lead (fc6FCO3YnI4cELCTg4oD) if the form fires the same tag
**For Creative Director (ad copy):**
- AG1-AG4 each need RSAs. Key differentiation angles from Competitor Intel:
- "Official Government Partner" (no competitor claims this)
- Specific property: "Invest in Pullman Hotel Panama from $307K"
- "0% Tax on Foreign Income" (competitors bury this)
- "No Currency Risk — USD Economy"
- Test "Plan B" emotional variants: "Your Family's Plan B in the Americas"
- Counter Henley's $100K ads with quality framing: "Premium Real Estate, Not Paper Investment"
**For Search Term Hunter (me, post-launch):**
- First search term audit at Day 7 (or 100+ clicks, whichever comes first)
- Priority: validate the broad match `panama residency` keyword — if junk ratio exceeds 30%, restrict to phrase
- Watch for: "panama friendly nations" leaking through (should be blocked), "panama real estate" without visa intent, any eligibility/quiz terms
*— Search Term Hunter, 2026-04-25*
*Campaign: build-1953d44a | Account: 7178239091*