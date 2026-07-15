# Cro Specialist Notes

**Last updated:** 2026-07-08 14:50

**Task:** Run a CRO + SEO review of Mercan's Panama Qualified Investor Program pages. TWO pages:

PAGE A — PAID ADS LANDING PAGE: https://www.mercan.com/lp/panama-qualified-investor-program
- Where Google Ads s
## Panama QIP — Dual-Page CRO + SEO Review
**CRO Specialist | June 24, 2026**
### MEASUREMENT CAVEAT — Check This First
Before attributing the 0.33% CVR entirely to the page: the GTM Specialist's live test (June 1) confirmed the conversion tag **does** fire correctly on successful form submission, but the form itself **silently rejects international phone formats** (+1, +44, +971) with a generic "check the form" error. If paid visitors are predominantly international HNW investors who type their number with a count
## PAGE A — Paid LP (`/lp/`) CRO Analysis
### The Root Diagnosis: Why Paid Doesn't Convert When Meta/Organic Do
The search terms that **convert** on this campaign are `panama residency requirements` and `panama residency for us citizens` — **residency-research intent**, people validating that Panama is accessible and that they qualify. The terms that get **clicks but zero conversions** are `panama golden visa`, `citizenship by investment panama`, `investment visa` — **investor-intent** searches.
Page A is built for investor-intent (it leads with "through a $300,000 Investment" and immediately presents real estate assets at $307K–$347K). Residency-intent visitors land and don't see their question answered above the fold: *"Can I get residency in Panama? What are the requirements? Do I qualify?"* They see an investment pitch. They leave.
Meta converts because Meta targeting pre-selects HNW profiles who are ready for the investment frame. Organic converts because Page B answers residency questions comprehensively. Google paid sends a mixed-intent audience and Page A has only one frame: investment-first.
### Top 5 Conversion Blockers — Prioritized
**#1 — The $300K / $307K / $347K Price Confusion (HIGH IMPACT)**
The H1 says "through a $300,000 Investment." The first project shown above the fold is Santa Maria "from $347K." The Pullman is "From $307K." Neither property starts at $300K.
A visitor sees "$300K" in the ad headline, clicks through, reads "$300K" in the H1, then immediately sees "$347K" as the only project on-screen. That's a $47K surprise in the first scroll. For an audience doing careful due diligence on a $300K+ commitment, this framing inconsistency erodes trust.
**Fix:** Add one clarifying line immediately below the project cards — something that exists on the page already but isn't surfaced prominently: *"Either project clears the $300,000 Qualified Investor Program threshold. An advisor will match you to the right one."* That line is already in the copy mid-page — move it directly below the two project prices, above the fold. No fabricated content requi
Alternatively, anchor the hero H1 to the Pullman's entry price: *"Secure Panama Residency from $307,000 — in About 30 Days."* That's honest, removes the price gap surprise, and the $307K entry becomes a strength, not a liability.
**#2 — The Form is Still 8+ Fields with Silent Phone Rejection (CRITICAL)**
The creative director's 4-field reduction (Name, Email, Phone, Country) was logged but never shipped. The live form still has: First Name, Last Name, Email, Phone, Nationality (dropdown), Country of Residence (dropdown), How-did-you-hear, Message, Yes/No radio, reCAPTCHA. That's 10 fields minimum.
Each field above 3 reduces conversions ~10%. At 10 fields vs the recommended 3, the structural conversion ceiling is ~49% of what a 3-field form would produce — before accounting for the phone validation bug.
**Fix (dev team required):**
1. Reduce to 4 fields: Name · Email · Phone · Country of Residence
2. Fix phone validation to accept international formats: strip the `(###) ###-####` US-only mask, accept E.164 format or add an international tel input with country code selector
3. Surface a field-level error on the Phone field ("Please use international format, e.g. +1 514 282-9214") — the current generic "check the form" gives no signal
This is the single highest-ROI fix available. It requires a dev deploy to mercan.com but no copywriting changes.
**#3 — Message-Match Gap for Residency-Intent Traffic (MEDIUM-HIGH IMPACT)**
The converting search terms are residency-research queries. Page A's above-fold content answers zero residency-qualification questions. A visitor searching "panama residency for us citizens" wants to know: *Can I get it? What do I need? How long does it take?*
Page A's hero answers: "invest $300K, get a second home." That's the right frame for investor-intent traffic, but it doesn't validate residency-research intent.
**Fix:** Add a single qualifying signal to the hero subhead — pull from existing copy already on Page B:
Current subhead: *"A second residency for you and your family, backed by real estate, through Mercan, the only company with an official partnership with the Government of Panama."*
Proposed addition (use existing Page B eligibility language verbatim): Append *"No minimum stay requirement. No language test. Family included."* as a three-item trust bar immediately below the hero CTA. This answers the residency-qualifier's primary questions in three words each, without changing the investment frame.
**#4 — Trust Signals Appear After the Form (MEDIUM IMPACT)**
The sequence on Page A:
1. Hero H1 + CTA button
2. Form (8+ fields, blocked)
The trust signals that justify the consultation request appear **below** the first CTA. A HNW investor hitting an 8-field form for the first time has zero prior context — they haven't yet seen "Only official Panama QIP partner" or "37 years operating."
**Fix:** Move the trust signal bar (Government Partner · Est. 1989 · 37 years · 4,100+ families) to **above** the form, below the hero CTA button. This is a layout change only — all the copy already exists. No fabrication required.
**#5 — The Soft Conversion Offer Is Buried at 90% Page Depth (MEDIUM IMPACT)**
Clarity confirmed: 60% of paid visitors spend 1+ minute on the page, 25% spend 5+ minutes — they're engaged but not converting. The "Not Ready to Talk Yet? Get the Panama QIP Investor Guide" offer exists, but it's at the very bottom, after the second form.
Visitors who won't fill an 8-field form today are leaving with nothing captured. A one-field email offer placed mid-page (after the Plan B section, before the "At a Glance" table) would capture warm intent at the moment of peak engagement.
**Fix:** Add a second instance of the Investor Guide soft conversion mid-page (after "Your Family's Plan B, Secured"), not just at the bottom. The copy already exists — "Get the Panama QIP Investor Guide: the qualifying investment routes, the residency timeline, the tax structure, and how Santa Maria works. One email, no obligation." Reduce it to one field: email only.
## PAGE B — Organic Page CRO + SEO Review
### CRO: What Page B Does Right (and Why It Converts Organic)
Page B answers the questions paid searchers are actually asking. The Eligibility section (7 requirements listed explicitly, including "No language requirement," "No education requirement") directly validates residency-research intent. The 8-step process with timelines builds confidence. This is why organic visitors convert — the page matches their research journey.
**One CRO gap on Page B:** The form CTA at the bottom says "Request a consultation" with no friction context ("Confidential, no obligation. A senior advisor reviews every submission personally" is on Page A but not here). Add that friction-reducing line to Page B's form header — it's already written and proven.
### SEO: Prioritized Fixes for Page B
**#1 — H1 Keyword Gap (HIGH SEO IMPACT)**
Current H1: *"Residency in Panama, in about 30 days."*
This is a strong conversion headline but weak for SEO. The primary keyword "Panama Qualified Investor Program" appears in the page title and URL but NOT in the H1. Google weights H1 heavily for topical relevance.
**Fix (preserve voice):** *"Panama Qualified Investor Program — Residency in About 30 Days."*
This puts the target keyword first, preserves the speed differentiator, and doesn't change the voice. Compare to current title tag: "Panama Qualified Investor Program | 30-Day Residency | Mercan | Mercan Group" — the H1 should echo the title tag keyword, not diverge from it.
**#2 — Title Tag Cleanup (MEDIUM SEO IMPACT)**
Current: "Panama Qualified Investor Program | 30-Day Residency | Mercan | Mercan Group"
"Mercan Group" appears twice (once as "Mercan" and once as "Mercan Group" — deduplicated). Characters that could serve keywords are wasted on brand repetition.
**Fix:** "Panama Qualified Investor Program | USD 300K | 30-Day Residency | Mercan" (~65 chars)
Adds the investment threshold (a high-value qualifier people search for) while removing the duplicate brand mention.
**#3 — The US-Citizen Keyword Gap (HIGH SEO IMPACT)**
`panama residency for us citizens` and `panama residency requirements` are your **only converting search terms**. Page B has no section targeting US citizens specifically. The Eligibility section lists 7 requirements — none of them says "US citizens" or frames requirements from the US-investor perspective.
**Fix:** Add a short H3 callout under the Eligibility section — pull from real facts already on the page:
> **For US Citizens**
> No renouncing existing citizenship required. Panama permits dual nationality. The investment capital must originate from outside Panama (wire transfer from a US bank account qualifies). No language test, no education requirement.
This is 100% real content, grounded in the existing FAQ and eligibility sections, and directly targets the converting search cluster. It also creates a natural anchor for internal linking from blog content targeting "panama residency for us citizens."
**#4 — FAQ Schema Markup (MEDIUM SEO IMPACT, LOW EFFORT)**
... (truncated)

---

## Session Log

### 2026-07-08 14:50 — switch the landing pages

**Task:** switch the landing pages

**Critical Details:** https://www.mercan.com/panama-qualified-investor-program`., https://www.mercan.com/lp/panama-qualified-investor-program`., https://www.mercan.com/lp/panama-qualified-investor-program`, https://www.mercan.com/panama-qualified-investor-program`
I'll execute the switch. Wassim confirmed — the Creative Director flagged this as high-impact and asked for a go, and "switch the landing pages" is that go. Before I touch anything, let me find the exact MCP tool that updates an ad's final URL (the google-ads server is still spinning up).Good — that confirms an important mechanical reality: **this MCP server has no tool to update an existing ad's 
Let me load the Chrome tools and see what's already open (the account was signed in in prior sessions).Full tool surface confirmed. Key finding for the mechanics: there is **no API/MCP tool to edit an existing RSA's final URL** — and recreating the ads via `ad_create_responsive_search_ad` would silently drop the pins (H1/H2 are pinned on the AG1 RSA) and reset ad history. So the correct, non-destr
Here's my plan before I touch the live account — quick and clear:
**What I'm switching**
`https://www.mercan.com/panama-qualified-investor-program` → `https://www.mercan.com/lp/panama-qualified-investor-program` (the `/lp/` page with the Plan B hook + email-capture soft offer).
**Which ads** — all 4 that actually serve:
| Ad ID | Ad group | Serving? |
|---|---|---|
(The AG4 ad and the paused AG1 ad don't serve — I'll switch them too for consistency if the UI makes it trivial, but they're not urgent.)
One honest note: doing all lanes at once means we forgo the clean AG2-only A/B the Creative Director floated — but with **B confirmed (zero real leads on the current page)**, there's no productive control to protect, so a full switch is the right call. Fully reversible anytime.
Let me check what's open in Chrome and get to the campaign.There's already a Google Ads tab open on this campaign (tab 8, signed in as account 7178239091). Let me switch to it and navigate to the campaign's Ads view. I need the `select_page` tool.Now let me switch to the Google Ads tab and navigate it to the campaign's Ads view.Signed into the correct account. Now navigating to the Ads view scoped
I'm going to stop here rather than thrash further or rebuild the ads a riskier way. Here's exactly where things stand.
## Status: switch is fully staged, but blocked by your browser
**What I confirmed via the live API (authoritative):** all 6 ads still point to the current page —
| Ad group | Ad ID | Serves? | Final URL now |
|---|---|---|---|
**Nothing was changed** — and no duplicate ads were created (I verified the ad IDs are all intact). I got the AG2 edit fully entered (`/lp/…` URL in the field, all 15 headlines / 4 descriptions / pins / sitelinks preserved, and I cleared the one pre-existing "Punctuation and symbols" finding by acknowledging it — that's from the `~` in "~30 days", nothing new) — but the final **Save** is what trip
## Two things I need to flag
**1. The blocker is an ad blocker in your Chrome.** Google Ads' editor won't save any edit while it detects one. I won't touch your extensions myself. Please **disable your ad blocker (uBlock/AdBlock/Brave shields/etc.) for `ads.google.com`** (or pause it for now), then say "go" — I'll switch all 4 serving ads (plus the 2 non-serving ones for consistency) in one clean pass and confirm each via the
**2. Why I'm not doing it via the API instead:** there's no API tool to edit an existing ad's final URL — the only API route is to *delete and recreate* each RSA, which would drop the pinned headlines on your AG1 ads and reset ad history. That's more destructive than a one-field URL edit and not what "switch the landing page" should cost. The in-place UI edit is the right tool; it just needs the a
... (truncated)
