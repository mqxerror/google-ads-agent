# Panama QIP Landing Page — CRO Edit Spec (for the code agent)

**Date:** 2026-06-24
**Target page (PAID LP):** `https://www.mercan.com/lp/panama-qualified-investor-program`
**Audience (NEW):** Gulf + Levant HNW investors (UAE, Saudi, Qatar, Kuwait, Bahrain, Oman, Egypt, Jordan, Lebanon). **English for now.** No US framing.
**Goal:** lift consultation-request conversion. Traffic engages (8.3% CTR) but converts at ~0.33% — the bottleneck is the page, not the click.

## Target files (mercan-main-site)
- `src/app/lp/panama-qualified-investor-program/page.tsx` — the paid LP (hero, qualifying assets, Plan B, benefits, at-a-glance, form). **Most edits here.**
- `src/app/lp/panama-qualified-investor-program/StickyCtaBar.tsx`
- `src/app/lp/panama-qualified-investor-program/InvestorGuideCapture.tsx` — soft email capture (add a mid-page instance).
- `src/components/trust/PanamaPartnership.tsx` — trust bar/logos.
- `src/app/[locale]/panama-qualified-investor-program/page.tsx` — the ORGANIC page (do NOT apply paid-LP copy here; SEO is separate).

## Hard constraints (non-negotiable)
1. **Keep the existing design system.** Reuse current components, OKLCH tokens, typography, spacing, card/modal/gallery patterns (`frontend/DESIGN.md`). No new colors, fonts, or visual language.
2. **No fabricated content.** No invented testimonials, stats, reviews, awards, or claims. Use only facts already on the page or verifiable Mercan/developer assets. Where social proof would help, source a real one — never invent.
3. **Copy rewrites are PROPOSALS** pending Wassim's approval (verbatim-copy rule). Implement structural/layout/visual changes freely; hold copy swaps for sign-off.
4. **Keep the `/lp/` page `noindex, follow`** (it's ads-only, canonical → organic page). Correct as-is — do not change.
5. **Performance:** below-the-fold images lazy-load; serve responsive/2x; don't regress LCP on the hero.

---

## Section-by-section edits

### 1. Hero — lead with the outcome, not the price
- **H1 (proposed):** `Secure Panama Residency Through a $300,000 Investment, in About 30 Days` → **`A Second Residency in Panama — for Your Whole Family, in About 30 Days`**
- **Subhead (proposed):** **`A USD 300,000 government-approved real-estate investment secures permanent residency and a path to a passport with visa-free access to 142 countries — through Mercan, Panama's only official QIP partner.`**
- Keep primary CTA + `Free · No obligation · Confidential`.
- Add a slim in-hero trust strip (reuse trust component): `Government Partner · Est. 1989 · 4,100+ families`.
- **Visual:** hero = Santa Maria tower render against the Panama City skyline. Optional muted looping skyline/tower clip behind hero using the *current* overlay treatment. No stock people.

### 2. Move the trust bar ABOVE the form
- The `Government Partner · Est. 1989 · 4,100+ families · 0% capital gains` bar currently renders BELOW the first form. Move it directly under the hero CTA, **above** the form. Layout-only (same `PanamaPartnership` component). Credibility before the ask.

### 3. Qualifying assets — visual centerpiece (the "360")
- **Copy:** surface the existing clarifier directly under the two price cards: `Either project clears the $300,000 Qualified Investor Program threshold — an advisor matches you to the right one.` (Kills the "$300K H1 vs $347K card" surprise.)
- **Visuals:**
  - **360° interactive tours** of Santa Maria units + the "360-degree city views," and Pullman suites — embedded in the existing card/modal component, behind an "Explore the residence" button (keeps mobile clean).
  - More detail per asset: floor plans, unit sizes (81–176 m²), amenity gallery (rooftop pool, cinema, concierge), delivery 2028, "from" price — existing gallery pattern.
  - Default card image = high-res "normal" render; 360 + gallery behind the button.

### 4. Benefits — reorder for the Gulf + add one map
- **Reorder** the existing six so Gulf-relevant lead: **Passport mobility → Family coverage → Territorial tax → 30-day speed → Citizenship in 5 years → Gateway location.**
- **Visual:** add a world map highlighting the **142 visa-free countries (Schengen + UK)** beside the mobility benefit, in the page's existing illustration style. (Produce from verifiable visa-free data.)

### 5. "Plan B" section — move it up
- Move `Your Family's Plan B, Secured` directly after the qualifying-assets section (before the long "At a glance" table). No copy change — it already resonates with Gulf families.

### 6. Social proof — real only
- Reinforce "4,100+ families" with **real completed/delivered Mercan project photos** and **real partner logos** (Government of Panama, Accor/Pullman) via the existing logo-row component. No invented testimonials/headshots. Real attributable quotes only, if any.

### 7. Form — shorten + reassure
- Reduce to **4 fields**: Name · Email · Phone · Country of Residence (same input components).
- Add reassurance microcopy above the button: `Confidential. A senior advisor reviews every submission personally.`
- ⚠️ **VERIFY FIRST:** test the live form with a `+971 / +966` number before touching phone validation. The "form silently rejects international phone numbers" claim is **unconfirmed** and may be a misread of an earlier `@example.com` *email* test quirk. Do not refactor phone validation on assumption.

### 8. Add a mid-page soft capture
- Add a second `InvestorGuideCapture` instance (email-only) after the Plan B section. Catches the engaged-but-not-ready visitor (Clarity shows long dwell times — confirm those numbers are from a real Clarity query before citing them).

---

## Visual production list (real assets only)
| Asset | Status |
|---|---|
| Santa Maria + Pullman renders (hero + cards) | likely on hand |
| 360° unit tours / interactive views | produce from real renders |
| Amenity gallery, floor plans, unit specs | from developer materials |
| Visa-free 142-country map graphic | produce from verifiable data |
| Completed-project photos + partner logos | real Mercan/Accor/Gov assets |
| Optional hero skyline video (muted loop) | optional, only if an asset exists |

## Verify before shipping
- [ ] Live-test the form with international phone formats (`+971`, `+966`) — confirm or refute the rejection bug.
- [ ] Confirm the Clarity dwell-time figures (60% 1min / 25% 5min) came from a real query.
- [ ] Get Wassim's sign-off on the H1 / subhead copy proposals.
- [ ] Confirm 360 tours / map graphic source from real assets (nothing fabricated).

## Out of scope / do NOT
- Do NOT change the `/lp/` index status (stays `noindex`).
- Do NOT apply this paid-LP copy to the organic `[locale]` page (SEO is a separate workstream).
- Do NOT introduce new design-system elements.
- Do NOT create or modify any ad campaign (this is page-only).
