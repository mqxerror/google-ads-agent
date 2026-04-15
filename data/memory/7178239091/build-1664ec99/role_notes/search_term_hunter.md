# Search Term Hunter Notes

**Last updated:** 2026-04-15 17:35

**Task:** Run stage 3 for campaign build
## Stage 3: Search Term Hunter — Keyword Strategy & Negative Mining
I have the CRO and Competitor Intel findings. Now I need to build the keyword architecture. Let me pull keyword research data and mine the existing Greece GV USA campaign for negative keyword patterns we can pre-apply.
Now let me run keyword research and pull search terms from the existing campaign in parallel.Good, I have rich Turkish keyword data. Let me now extract the top English keywords from Turkey and pull search terms from the existing Greece GV USA campaign for negative keyword pattern mining.Excellent. I now have all the data I need. Let me compile the complete Stage 3 deliverable.
# Stage 3: Search Term Hunter — Keyword Strategy & Negative Mining
## Greece Golden Visa — Turkey Campaign
### DATA SOURCES USED
1. Google Keyword Planner: 37 Turkish keywords (Turkey, Turkish language)
2. Google Keyword Planner: 40 English keywords (Turkey, English language)
3. Existing Greece GV USA campaign: 68 search terms (last 30 days) for waste pattern mining
## 1. KEYWORD DEMAND MAP
### Turkish Keywords (Primary — highest volume)
| Keyword | Monthly Vol | Competition | Est. CPC Range | Intent |
|---------|------------|-------------|----------------|--------|
**Total addressable Turkish volume: ~6,400/month** (excluding Ekşi/waste queries)
### English Keywords (Secondary — bilingual Turkish investors)
| Keyword | Monthly Vol | Competition | Est. CPC Range | Intent |
|---------|------------|-------------|----------------|--------|
**Total addressable English volume: ~2,900/month** (from Turkey)
## 2. PROPOSED AD GROUP STRUCTURE
### Ad Group 1: `yunanistan-golden-visa` (Turkish — Core)
**Theme:** Direct golden visa program searches in Turkish
**Est. volume: ~5,000/month**
| Keyword | Match Type | Monthly Vol | Rationale |
|---------|-----------|------------|-----------|
**Why phrase match:** Zero paid competition means phrase match will get us coverage without overspending. No need for broad match + smart bidding in a zero-competition market. If volume is insufficient after 2 weeks, consider switching top 2 keywords to broad.
### Ad Group 2: `yunanistan-oturum-gayrimenkul` (Turkish — Residency + Property)
**Theme:** Residency/citizenship via real estate investment
**Est. volume: ~1,500/month**
| Keyword | Match Type | Monthly Vol | Rationale |
|---------|-----------|------------|-----------|
### Ad Group 3: `greece-golden-visa-en` (English — Bilingual Turkish investors)
**Theme:** Turkish investors searching in English
**Est. volume: ~1,800/month**
| Keyword | Match Type | Monthly Vol | Rationale |
|---------|-----------|------------|-----------|
**Why NOT include "golden visa europe":** At 1,000 vol with MEDIUM competition, this term is too broad — it'll match Portugal, Spain, Latvia queries. Not worth the waste risk for a Turkey-specific campaign with a Turkish landing page. English ads hitting a Turkish landing page already have a language mismatch risk; adding broad European terms compounds it.
## 3. NEGATIVE KEYWORD STRATEGY
### Campaign-Level Negatives (Absolute certainty — apply to all ad groups)
| Negative Keyword | Match Type | Reason | Volume Blocked |
|-----------------|-----------|--------|---------------|
| öğrenci | Phrase | Student — wrong visa category | — |
| turist vizesi | Phrase | Tourist visa — wrong category | — |
| mülteci | Phrase | Refugee — wrong category | — |
| iltica | Phrase | Asylum — wrong category | — |
| visa card | Phrase | Credit card brand confusion | — |
| kredi kartı | Phrase | Credit card in Turkish | — |
| student visa | Phrase | Wrong visa type | — |
| tourist visa | Phrase | Wrong visa type | — |
| asylum | Phrase | Wrong category | — |
| refugee | Phrase | Wrong category | — |
| get paid to move | Phrase | From USA campaign: pure waste | — |
| consulate | Phrase | From USA campaign: consulate visit queries, not investment | — |
| konsolosluk | Phrase | Turkish for consulate | — |
| how to apply for greek citizenship by descent | Phrase | Citizenship by ancestry, not investment | — |
### Ad-Group-Level Negatives (Applied to specific ad groups to prevent cross-matching)
**For Ad Group 3 (English) only:**
| Negative Keyword | Match Type | Reason |
|-----------------|-----------|--------|
| apartments for sale | Phrase | Pure real estate browsing |
| villas for sale | Phrase | Pure real estate browsing |
| houses for sale | Phrase | Pure real estate browsing |
| moving to | Phrase | Relocation queries |
| cost of living | Phrase | Informational, not investor |
| what is it like | Phrase | Informational browsing |
| expat | Phrase | Lifestyle queries, not investor |
**For all ad groups — outdated years:**
| Negative Keyword | Match Type | Reason |
|-----------------|-----------|--------|
### Keywords I Specifically DID NOT Negate (and why)
| Keyword | Why NOT negated |
|---------|----------------|
| şartları (requirements/conditions) | 260+170+90+40 = 550 monthly searches. Our landing page COVERS requirements. These are mid-funnel investors doing due diligence. High conversion potential. |
| gayrimenkul (real estate) | Greece GV IS a real estate product. "yunanistan oturum izni gayrimenkul" ($11.52 CPC) is the HIGHEST commercial intent keyword. |
| ucuz / cheapest | Not negated. Unlike the USA campaign where "cheapest" signals budget shoppers, in Turkey's context €250K IS the "cheap" golden visa option. Price-sensitive investors still invest. |
| emekli (retiree) | 210/month, distinct audience segment. Retirees relocating to Greece via GV is a real use case. Keep and monitor. |
## 4. WASTE PATTERN INTELLIGENCE FROM USA CAMPAIGN
I pulled 68 search terms (30 days) from the existing Greece GV USA campaign (ID: 22551124974). Key findings that inform the Turkey build:
**AI Max is STILL the #1 waste driver.** Of the 68 search terms with clicks, ~60 are AI_MAX matches. Total visible spend: ~$237 across those terms.
**Top waste clusters (USA data, applicable to Turkey):**
|--------------|-------------------------|-----------------|-------------------------------|
**Suspicious conversion data:** "greek work permit" shows 12 conversions from 1 click — this is a tracking artifact, not real. "living in the mediterranean" shows 3 conversions from 1 click — also suspicious. Don't use these as positive signals.
## 5. MATCH TYPE STRATEGY
**Recommendation: Start with ALL Phrase match. Do NOT use Broad match at launch.**
Rationale:
1. **Zero paid competition** in Turkey means we don't need broad match to get volume — phrase match will serve on the primary queries
2. **No conversion history** on a new campaign means smart bidding has no signal to optimize broad match queries
3. The USA campaign proves AI Max + broad match = 95%+ budget waste when there's no conversion data
4. Turkish keyword space is more contained than English — fewer ambiguous expansions
5. **After 15+ conversions in 30 days**, consider switching top 3 keywords to broad match with smart bidding
**If volume is insufficient after 14 days** (below 500 impressions/week per ad group):
- Promote "yunanistan golden visa" and "yunanistan oturum izni" to Broad match only
- Keep all others as Phrase
- Add the ad-group negatives from Section 3 before broadening
## 6. KEYWORD COUNT SUMMARY
| Ad Group | Keywords | Est. Monthly Vol | Primary Language |
|----------|----------|-----------------|-----------------|
**Campaign-level negatives:** 21 keywords
**Ad-group-level negatives:** 13 keywords (English AG only) + 4 year exclusions (all AGs)
## 7. FLAGS FOR OTHER ROLES
**For Copywriter/Ad Creator (Stage 4):**
- Turkish ad group needs fully Turkish ad copy — NOT translated, but culturally native
- English ad group can use similar copy to USA campaign but with Turkey-specific emotional hooks ("Plan B" / economic stability angle is MORE resonant for Turkish audience)
- "Emekli" (retiree) keyword in AG2 means at least one headline should speak to retirement relocation
- CTA must be "Ücretsiz Görüşme Ayırt" (Book Free Consultation) — no exceptions
**For Campaign Strategist:**
- Start with Maximize Clicks (with max CPC cap ~$5) until 15+ conversions accumulate, THEN switch to Maximize Conversions
- Alternatively, if user wants to mirror the USA campaign's Maximize Conversions strategy from day 1, set Target CPA at ~$40 (lower than USA's $60, justified by lower CPCs)
- Budget recommendation: $50-75/day to start — Turkey CPCs are 60-70% lower than US, so this gets equivalent volume to $150/day in the US
**For CRO / Tech:**
- The `lang="en"` issue on the Turkish landing page MUST be fixed before launch — Google uses this for language matching in Quality Score
- English meta description on a Turkish page will hurt Quality Score for Turkish keywords
*— Search Term Hunter*
**Ready for Stage 4 (ad copy & campaign creation).** All keyword data, match types, negative lists, and ad group structure are defined. The next role can build directly from this blueprint.