# Creative Director Notes

**Last updated:** 2026-04-15 17:42

**Task:** Run stage 4 for campaign build

**Critical Details:** https://goldenvisas.mercan.com/tr/greece-golden-visa`
# Stage 4: Creative Director — Ad Copy & Campaign Blueprint
## Greece Golden Visa — Turkey Campaign
I have the full picture from CRO, Competitor Intel, and Search Term Hunter. Here's the complete creative and campaign build proposal.
## CREATIVE STRATEGY
**Core Insight:** Zero paid competition in Turkey + Turkish investors live with lira devaluation daily = "Plan B" family safety messaging is not theoretical here, it's *urgent*. Every competitor talks about €250K and Schengen. Nobody talks about *why* a Turkish investor needs this *now*.
**Three copy pillars (in order of priority):**
1. **Emotional security** — "Plan B," protect your family, secure what you've built
2. **Investment returns** — 3% guaranteed yield, real estate as wealth preservation (contrast to TRY volatility)
3. **Trust & credibility** — 4,100+ investors, 98% success rate, 15+ years, licensed
**CTA everywhere:** "Ücretsiz Danışmanlık Alın" (Get Free Consultation) — matches landing page, no eligibility language.
**Final URL (all ad groups):** `https://goldenvisas.mercan.com/tr/greece-golden-visa`
## CAMPAIGN SETTINGS SUMMARY
| Setting | Value | Rationale |
|---------|-------|-----------|
| **Location** | Turkey | Geo target |
| **Status** | PAUSED | User enables when ready |
| **Campaign name** | `Greece Golden Visa - Turkey` | Clear naming |
## RSA 1: Ad Group `yunanistan-golden-visa` (Turkish Core)
**Display URL:** goldenvisas.mercan.com/**Altin-Vize**/**Yunanistan**
|---|---------------------|-------|-------|-----|
|---|------------------------|-------|
## RSA 2: Ad Group `yunanistan-oturum-gayrimenkul` (Residency + Property)
**Display URL:** goldenvisas.mercan.com/**Oturum-Izni**/**Gayrimenkul**
|---|---------------------|-------|-------|-----|
|---|------------------------|-------|
## RSA 3: Ad Group `greece-golden-visa-en` (English — Bilingual Turkish Investors)
**Display URL:** goldenvisas.mercan.com/**Golden-Visa**/**Greece**
|---|---------------------|-------|-------|-----|
|---|------------------------|-------|
## COPY RATIONALE
**Why "Plan B" in headlines 5 (all AGs):** Competitor Intel confirmed ZERO competitors use this angle in Turkey. Turkish investors deal with lira devaluation, inflation, and political uncertainty daily — "Plan B" isn't abstract for them. This is our first-mover differentiator.
**Why different Pin 2 per AG:**
- AG1: `%98 Başarı Oranımız` — specific stat cuts through generic claims
- AG2: `4.100+ Yatırımcı Güvendi` — social proof resonates with property-intent searchers who want validation
- AG3: `98% Approval Success Rate` — English equivalent, builds instant credibility
**Why AG2 has retirement headline (#7):** Search Term Hunter flagged 210/mo searches for "yunanistan emekli oturum izni." This headline + Description 3 (Mediterranean retirement) speak directly to that segment without needing a separate ad group.
**Language note for AG3:** English ads → Turkish landing page. This works because the confirmed audience is bilingual Turkish investors. The 2-field form (name, email) has near-zero language friction. If CTR or bounce rate is poor after 14 days, consider creating an English landing page variant.
## PRE-LAUNCH FLAGS
| Issue | Owner | Status |
|-------|-------|--------|
| Landing page `lang="en"` must be changed to `lang="tr"` | Dev/CRO | **BLOCKER** — hurts Quality Score |
| English meta description on Turkish page | Dev/CRO | **Should fix** — Quality Score impact |
| No WhatsApp on landing page | CRO | **Nice-to-have** — dominant channel in Turkey |
| Need Turkey-specific conversion action | Tracking | **Required** — avoid cross-contamination with USA campaign |
## EXECUTION PLAN (after approval)
1. `budget__create_campaign_budget` → $60/day
2. `campaign__create_campaign` → "Greece Golden Visa - Turkey", Maximize Clicks, max CPC $5, PAUSED
3. `campaign_criterion__add_location_criteria` → Turkey
4. `campaign_criterion__add_language_criteria` → Turkish + English
5. `ad_group__create_ad_group` × 3 (one per AG)
6. `keyword__add_keywords` × 3 (15 keywords total, all Phrase match)
7. `ad__create_responsive_search_ad` × 3 (one RSA per AG)
8. `campaign_criterion__add_negative_keyword_criteria` → 21 campaign-level negatives
**Approve this build and I'll execute it.**
The landing page `lang` fix and conversion action setup should happen in parallel but don't block campaign creation (campaign launches PAUSED anyway).
*— Creative Director*