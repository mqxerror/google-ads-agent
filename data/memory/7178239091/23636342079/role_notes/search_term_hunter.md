# Search Term Hunter Notes

**Last updated:** 2026-04-21 15:58

**Task:** we need the pro and the search term hunter to craft a plan for the developer telling the best pro or content page for who we are and our team , to add more trust to the subdomain , after that we can e

**Critical Details:** GTM-K6864NBH
## PPC Strategist — Trust Page Brief
**Why this matters to campaign performance:** A `/about` or `/team` page on goldenvisas.mercan.com serves two functions — it raises landing page Quality Score (Google's ad quality bot crawls the full domain, not just the landing page) and it gives HNW prospects somewhere to go when they're in the research phase before converting.
**The search term data confirms this need.** Queries like "does portugal still have the golden visa," "mercan portugal," and "what is portugal's golden visa" all show users who are not yet ready to fill the form — they're vetting the company first. Right now, those users hit a landing page with no company context and bounce. A credible `/about` page captures that intent.
### What the Trust Page Needs to Do for the Campaign
| Ad Claim | Page Must Prove |
|----------|-----------------|
| "Direct From The Developer" | Show the fund structure, Mercan as developer not broker |
| "37+ Years Experience" | Timeline or founding year with verifiable milestones |
| "3,700+ Families Helped" | Case studies or verified client count |
| "€2B+ Invested" | Asset under management figure with source/context |
| "CMVM-Regulated Fund" | License number, regulator name, verifiable link |
| "Reviewed by Jason Morgan" | Jason Morgan bio, credentials, photo |
Every headline in our ads makes a claim. The trust page is where those claims are documented.
## Search Term Hunter — Doubt Signal Mapping
**From the last 7 days of search terms, I identified 6 distinct doubt/research patterns.** The trust page must answer each one explicitly. Users searching these terms will navigate to the trust page before deciding to fill the form.
| Doubt Signal | Search Terms | What They're Really Asking |
|---|---|---|
| Company legitimacy | "mercan portugal", "what is portugal's golden visa" | Who is this company? Are they real? |
| Risk/safety | "golden visa portugal requirements", "portugal golden visa cost" | What are the risks? What exactly do I pay? |
| Competitive confusion | "iberis capital", "optimize portugal golden opportunities" | Are there other companies/funds doing this? How is Mercan different? |
| Outcomes | "portugal golden visa to citizenship", "benefits of portugal golden visa" | What do I actually get? |
The trust page must answer all 6 — not with marketing language but with verifiable, specific facts.
## Developer Brief — Trust & About Page for goldenvisas.mercan.com
**Page URL:** `goldenvisas.mercan.com/about`
**Priority:** High — supports active Google Ads campaigns
**Domain note:** This is an ads-only domain. `noindex, nofollow` on all pages is intentional. Do NOT add to sitemap.
### Page Architecture
### Section-by-Section Content Spec
#### Hero
**Headline:** `We Are the Developer. Not an Agent.`
**Sub-headline:** `Mercan Group has been building and managing investment immigration funds since 1989. 3,700+ families. €2B+ invested. One consultation.`
**No form here.** Just the stats and a scroll anchor. The form lives on `/portugal-golden-visa`. This page builds trust that sends the user back there.
#### Section 1 — The Company
**Block: Timeline (visual)**
| Year | Milestone |
|------|-----------|
| 1989 | Mercan Group founded — Quebec Immigrant Investor Program |
| [year] | Expanded to Portuguese Golden Visa program |
| [year] | First CMVM-regulated fund launched |
| 2024–2026 | 3,700+ families placed, €2B+ under management |
**Block: What "Developer Not Agent" Means**
> Most companies selling Golden Visa programs are intermediaries — they earn a commission by referring clients to third-party funds. Mercan is the fund developer. We created, registered, and manage the funds directly. When you invest with Mercan, there are no broker layers, no referral fees, and no conflicts of interest.
Copy note: this directly answers the "Direct From The Developer" ad claim and differentiates from Iberis Capital, Optimize Capital, and Oxy Capital — all of which are intermediary fund managers or brokers.
#### Section 2 — The Team
**Required for each team member:**
- Name + title
- Professional photo (headshot, not stock)
- 3–5 bullet credentials (immigration law license, years of experience, languages spoken, jurisdictions covered)
- Quote or brief bio (2–3 sentences, first person)
**Minimum team members to feature:**
1. **Jason Morgan** — already referenced in ad landing page as reviewer. Must appear here with full bio. This is the most important profile for ad Quality Score continuity.
2. **Senior immigration attorney or legal counsel** — specifically for Portugal program
3. **Fund manager or CMVM-regulated person** — the person whose name is on the CMVM license
4. **Client success/case manager** — humanizes the post-investment process
**Do not use stock photography.** HNW investors will reverse image search. It destroys credibility instantly.
#### Section 3 — The Fund
**Block: Fund Structure Explainer (visual diagram preferred)**
**Key facts to include (all verifiable):**
- CMVM registration number (required — this is the highest-trust signal for sophisticated investors)
- Fund type (open/closed, term)
- Minimum investment: €500,000
- Management fees: Zero (page already says this — repeat it here)
- Buyback guarantee: 100% from Year 6 — define the mechanism briefly
- Annual yield: 2% fixed — define payment schedule
**Do not over-promise on returns.** Include standard fund disclaimer: "Past performance does not guarantee future results." Required for CMVM-regulated funds and for Google ad policy compliance.
#### Section 4 — Track Record
**Block: By The Numbers (large visual stat display)**
| Stat | Number | Context |
|------|--------|---------|
| Success rate | [%] | Golden Visa approvals vs applications |
| Countries served | [#] | US, Canada, MENA, etc. |
**Block: Client Testimonials (3–5 minimum)**
- First name + last initial + country of origin + year
- Quote must be specific: "We applied in March 2024 and received our residency card in [month]" — not generic praise
- Photo if available (with permission)
- If Trustpilot or Google Reviews exist: embed the widget here. This solves the star-rating gap the CRO Specialist has flagged for 21 days.
#### Section 5 — Press / Recognition (if available)
If Mercan has been featured in Forbes, Bloomberg, Financial Times, local Portuguese press — logos here. Even one credible media mention dramatically increases trust for HNW investors.
If no press coverage exists: skip this section and replace with regulatory/accreditation logos (CMVM, Portuguese immigration authority, applicable bar associations).
#### Section 6 — Sticky CTA
Repeat the same CTA as the main landing page:
**"Schedule a Free Consultation"** — links back to `/portugal-golden-visa#form`
Do NOT create a second form on this page. One form, one conversion action, one thank-you page. The trust page converts by sending the user back to the main page ready to fill the form.
### Technical Spec for Developer
| Item | Requirement |
|------|-------------|
| URL | `/about` on `goldenvisas.mercan.com` |
| Framework | Next.js (same app — reuse existing components) |
| Meta robots | `noindex, nofollow` (same as all pages on this domain — intentional) |
| GTM | GTM-K6864NBH must load (same container) — conversion Linker active |
| Analytics | No conversion tag needed on this page — it's a trust/research page |
| CTA button | Links to `/portugal-golden-visa#form` — not a new form |
| Mobile | Must be fully responsive — same breakpoints as landing page |
| Images | Real photos only, optimized (WebP), lazy-loaded |
| Schema | `Organization` and `Person` schema on team members (same pattern as landing page) |
| Page speed | Target LCP < 1.2s (landing page is at 1.0s — match it) |
| Internal links | Nav/footer link from `/portugal-golden-visa` to `/about` — bidirectional |
### Priority Order for Content Gathering
Before the developer can build, the client needs to provide:
1. **Jason Morgan bio + headshot** — CRITICAL, already referenced in live ads
2. **CMVM registration/license number** — CRITICAL, without this the fund section is unverifiable
3. **3 other team member bios + photos** — HIGH
4. **3–5 client testimonials** — HIGH (with permission to publish)
5. **Fund structure details** (term, yield schedule, buyback mechanism) — HIGH
6. **Founding year and milestone dates** — MEDIUM
7. **Press coverage** — LOW (only if it exists)
*— PPC Strategist + Search Term Hunter*