# Landing Page Upgrade Plan — MapleRoots Campaign
**Created:** 2026-05-24 | **Target implementation:** Week of May 26-30

## New LP URL
`https://www.mercan.com/lp/canadian-citizenship-by-descent`

## Current Status
- Page is IN DEVELOPMENT (not yet receiving ad traffic)
- Old page: `https://www.mercan.com/canadian-citizenship-by-descent` (CRO Score: 66/100)
- New page CRO Score: 76/100 (as-is), projected 84+ with P0 fixes

## P0 — Fix Before Switching Ads (5 minutes)
1. **Change "Submit" button → "Get My Free Consultation"** — 20-40% CTA uplift
2. **Remove "How did you hear about us?" field** — saves 5-10% form abandonment
3. **Reduce form to 5 fields** (First, Last, Email, Phone, Country) — drop Nationality + textarea

## P1 — Fix Same Week as Launch (hours)
4. **Add 2-3 client testimonials** above or below FAQ section
5. **Add at least 1 relevant image** (Canadian landscape, passport visual, team photo)
6. **Test mobile form position** — currently pushed below fold on mobile
7. **Add parent-path self-qualifier copy** — "Parent path is straightforward. Grandparent/great-grandparent paths are where our expertise makes the difference."

## P2 — Next Sprint (days)
8. **Build 3-question eligibility quiz** — projected +200-400% CVR
9. **Reduce post-quiz form to 3 fields** (Name, Email, Phone)

## Switch Ads Checklist (when P0 complete)
- [ ] P0 fixes confirmed live
- [ ] Test form submission fires conversion tag (GV Lead fc6FCO3YnI4cELCTg4oD equivalent / Canada Descent Lead 7612610100)
- [ ] Update all 4 RSA final_urls to `/lp/canadian-citizenship-by-descent`
- [ ] Monitor CVR for 3 days post-switch

## Projected Impact
| Scenario | CVR | CPA | vs Current ($93.78) |
|----------|-----|-----|---------------------|
| New page as-is | ~2.0-2.5% | $46-56 | -40-50% |
| + P0 fixes | ~2.5-3.0% | $37-45 | -52-60% |
| + 5-field form | ~3.0-3.5% | $32-37 | -60-66% |
| + quiz (P2) | ~5-6% | $19-22 | -77-80% |

## Key Findings from CRO Review (May 23)
- Form above fold on desktop = game-changer (was buried at 11,363px)
- All tracking confirmed firing (GTM, Google Ads, Clarity, FB Pixel, TruConversion)
- Page is 58% shorter (5,694px vs 13,500px)
- Zero images on page — feels like wireframe
- No testimonials/social proof anywhere
- "Bill C-3 IN FORCE" badge is strong urgency signal
