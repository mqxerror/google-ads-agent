# Cro Specialist Notes

**Last updated:** 2026-06-02 15:28

**Task:** this campaign and please update the landing page
I need to find the landing page URL for this Turkey campaign first. Let me pull the ad details.The listing didn't include the Turkey campaign's ads. Let me search specifically for this campaign's ad groups to get the final URLs.Now let me get the ads with final URLs for these ad groups.The list endpoint didn't return final_urls. Let me query directly via GAQL.The API tools are having a page_size i

---

## Session Log

### 2026-05-19 15:55 — we need first change the landing page and after that we do reaudit https://www.m

**Task:** we need first change the landing page and after that we do reaudit https://www.mercan.com/tr/yunanistan-altin-vize

**Critical Details:** https://www.mercan.com/tr/yunanistan-altin-vize`., https://www.mercan.com/tr/yunanistan-altin-vize`, https://goldenvisas.mercan.com/tr/greece-golden-visa`
I'll change the landing page URL for all ads in this Turkey campaign from `goldenvisas.mercan.com/tr/greece-golden-visa` to `https://www.mercan.com/tr/yunanistan-altin-vize`.
First, let me get all the ad details (IDs, headlines, descriptions) so I can recreate them with the new URL.Let me try the stream endpoint instead.Got all 3 ads. Here's the plan:
**Current URL:** `https://goldenvisas.mercan.com/tr/greece-golden-visa`
**New URL:** `https://www.mercan.com/tr/yunanistan-altin-vize`
Since Google Ads doesn't allow editing final URLs on existing ads, I need to:
1. Create 3 new RSAs (same headlines/descriptions) with the new URL
2. Pause the 3 old ads
| Ad Group | Ad ID | Headlines | Action |
|----------|-------|-----------|--------|
**Shall I proceed?** This is a medium-impact change — the ad copy stays identical, only the landing page URL changes.

### 2026-06-02 15:28 — As the CRO Specialist, run a comprehensive 12-point CRO audit for "Greece Golden

**Task:** As the CRO Specialist, run a comprehensive 12-point CRO audit for "Greece Golden Visa - Turkey".

WORKFLOW:
1. Find the landing page URL from the campaign's ads (final_urls)
2. Run the FULL 12-step an

**Critical Details:** https://www.mercan.com/tr/yunanistan-altin-vize`., GTM-WZKDXFH8, https://www.mercan.com/tr/yunanistan-altin-vize
I'll run the full 12-point CRO audit on the Turkey LP. The landing page URL is already known from the ads' final URLs: `https://www.mercan.com/tr/yunanistan-altin-vize`. Let me load the Chrome tools and set up the workflow.Tab 3 already has the Turkish LP open. Let me select it and run the performance + DOM analysis.Now let me reload it fresh and run the combined DOM + performance + trust + copy e
<!-- STRUCTURED_DATA_START -->
<!-- STRUCTURED_DATA_END -->
## CRO Score: 79 / 100 (B-)
**The headline:** This is a genuinely strong page held back by three fixable funnel leaks. The auction problems are solved (CPC stabilized $2.56–$6.08, QS recovering, tracking verified). The 0.7% CVR is now **the** problem — and it's a landing-page problem, not a traffic problem.
### What's excellent (don't touch)
- **Performance:** FCP 780ms, full load 2.1s, ~45KB transfer — top-tier.
- **Copy/positioning:** H1 *"Aileniz için AB ikameti. Atina'da %3 kira garantili mülk."* nails outcome-first + family + Plan B, with the €250K anchor and friction-removal ("no test, no interview, no residency requirement"). Zero eligibility/quiz language. On-brand.
- **Tracking:** Verified firing end-to-end Jun 2 — leave it.
- **Mobile + visual:** premium, sticky CTA bar, large touch targets.
### The 3 conversion killers (ranked by impact × effort)
1. **9-field form** (Name, Surname, Email, Phone, Citizenship, Residence, Source, Message, Consent) — 3x the optimal. Clarity confirms only **1 session in 14 days** even started typing. Cut to 3 fields → biggest single lift available.
2. **Two dead-click bugs** (Clarity): the primary "Ücretsiz görüşme talep et" CTA and the "Detaylı incelemek için" project button both dead-click. Motivated users click and get nothing. Low-effort dev fix.
3. **Trust gaps for a Turkish audience:** no testimonials/case studies, and a **Canadian +1 514 phone** with no local TR number/WhatsApp. Add a WhatsApp click-to-chat + 2–3 outcome testimonials.
### Ad strength note
The Turkish RSAs (`809590104375`, `809625956041`) already carry 15 headlines + 4 descriptions — structurally near "Excellent." The remaining gap is the Creative Director's flag: add **pinned citizenship-pathway headlines** ("Ev Alarak Oturma İzni", "7 Yılda Vatandaşlığa Yol") to lift the two stuck QS-1 keywords. Hold until Jun 4 to respect the 7-day-wait window after the May 21 change.
### Recommended sequence
Form-to-3-fields + dead-click fix together could plausibly move CVR from 0.7% → 2%+ — roughly **3x the leads on the same spend**, far bigger than any bid tweak. These are LP-team dev tasks; want me to draft the exact fix spec (field list, click-handler targets, WhatsApp widget) for the LP team?
— *CRO Specialist*
