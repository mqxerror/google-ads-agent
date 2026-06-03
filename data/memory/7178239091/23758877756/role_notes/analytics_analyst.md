# Analytics Analyst Notes

**Last updated:** 2026-06-02 15:38

**Task:** Conversion-tracking + attribution audit for Greece Golden Visa - Turkey (23758877756). Context: GTM-WZKDXFH8 V12 fixed the trigger May 20 (regex greece-golden-visa|yunanistan-altin-vize), conversion l

**Critical Details:** GTM-KWFH5X9T, GTM-WZKDXFH8, GTM-K6864NBH
## Conversion-Tracking + Attribution Audit — Greece Golden Visa Turkey (23758877756)
**Analytics Analyst | 2026-06-02 | context-only, no tool calls**
First, a number-hygiene correction that changes the framing: the question cites **290 clicks / 0.34% CVR**. The 14-day daily table in context sums to **142 clicks**, and the **313** figure is *lifetime* ad-group spend, not this window. So the two CVRs floating around the team are both real, just measured over different denominators:
| Window | Clicks | Conv | CVR |
|---|---|---|---|
The post-fix number is the only one that's analytically valid — see below.
### 1. Is 1-conv-in-14-days a tracking gap or genuine low intent?
**Genuine low intent — not a tracking gap. Here's the evidence chain.**
- **Tracking was physically broken until May 20** (GTM-WZKDXFH8 V12 fixed the trigger regex). Any lead before May 20 *could not* have recorded a conversion. So the correct denominator is **post-fix clicks only (~134)**, not 313. Measuring CVR against lifetime clicks is comparing converting traffic to a period where conversion was impossible — that inflates the "tracking failure" narrative artifici
- **The 1 conversion landed May 23** — three days *after* the fix went live. That's exactly what you'd expect if the plumbing started working on May 20: first real conversion shows up within days. This is a coherence signal, not a red flag.
- **Conversion lag is mostly exhausted** for this window: the May 23 conversion is 10 days old, attribution window closed. Only **May 30–Jun 2 (4 days, ~32 clicks)** are still inside the open lag window and could still tick up. Don't treat those 4 days as final.
- **The low CVR is independently corroborated by behavioral data**, which is what rules out a tracking artifact: the CRO/Clarity audit found only **1 session in 14 days even started typing in the form**, plus a **9-field form** and **two dead-click CTA bugs**. If tracking were silently dropping conversions, you'd expect Clarity to show *many* completed form interactions with no matching pings. It 
**Verdict: 0.75% post-fix CVR is a real landing-page funnel problem, not a measurement problem.**
### 2. Reconcile the three layers
| Layer | State | Evidence | Is it the problem? |
|---|---|---|---|
The traffic is arriving (clicks, CTR, CPC all normal) and the tag works in test — so the gap between click and conversion is **the form**, not the auction and not the pixel. This is consistent across PPC, Search Term Hunter, and CRO. Don't touch bidding; fix the form.
### 3. What is NOT yet proven (and the evidence that would close it)
**Not proven: a VERIFIED organic conversion ping — a real visitor's submission firing the conversion, as distinct from the manual Jun 2 test push.**
- The Jun 2 test was a *deliberately submitted* test lead. It proves the chain *can* fire — it does **not** prove an unaided organic visitor triggers the same chain (the React `gf_submit` could behave differently on a real organic flow, consent state, or device).
- The **single May 23 conversion** is the candidate organic proof, but it has **not been reconciled against a backend/CRM lead record**. Right now it's a number in the Google Ads dashboard with no confirmed real human attached.
**Evidence that would close the gap (no new infrastructure — this is reconciliation, not a rebuild):**
1. Match the **May 23 conversion timestamp** against the `/api/form-submit` 200 log / Gravity Forms entry — confirm a real lead row exists at that time with a valid GCLID.
2. Use **enhanced conversions email hash** (already live per the CRO note) to tie the May 23 conversion to a named lead identity in the CRM.
3. Observe **one organic (non-test) gf_submit → conv ping** in real time over the next collection window.
Until #1 is done, the honest statement is: *tracking is verified working in test; one organic conversion is recorded but not yet independently confirmed as a real lead.*
### 4. Primary conversion action compliance
**Directionally compliant, with one flag I cannot fully close from context.**
- The firing conversion is the dedicated **WEBPAGE lead action** (Turkey uses the new per-program container GTM-WZKDXFH8, label **`fxvWCM-vu6scELCTg4oD`** — "Greece GV Lead"). This is a dedicated lead action, **not** the GA4 `form_submit` (ID 6953214477), which guidelines explicitly forbid as primary. ✅ on that rule.
- **Note a label discrepancy** worth keeping straight: the main Greece campaign uses `hMe8CLPl184aELCTg4oD` (action 7144337715, GTM-KWFH5X9T); the old account memory references `fc6FCO3YnI4cELCTg4oD` on GTM-K6864NBH. Turkey runs a **third** label on a **third** container. That's intentional per-program separation — but it means the Turkey campaign's `primary_for_goal` flag is a separate setting fr
- **What I cannot verify from context (no tool call):** whether `fxvWCM-vu6scELCTg4oD` is explicitly set **PRIMARY at this campaign's goal level**. The label in use is the right *type* (dedicated WEBPAGE lead), so the spirit of the rule is met — but the explicit PRIMARY flag should be confirmed with one GAQL pull on `conversion_action` before this is signed off as compliant.
### NOW WHAT — prioritized
1. **Reconcile the May 23 conversion to a CRM/Gravity Forms lead record** — closes the "verified organic ping" gap. Highest analytical priority; it converts an unproven dashboard number into confirmed signal.
2. **Ship the LP form fixes (9→3 fields + dead-click bug)** — this is the dominant CVR leak. CRO projects 0.7%→2%+, ~3x leads on the same spend. Far bigger lever than anything in the auction.
3. **Confirm `fxvWCM-vu6scELCTg4oD` is set PRIMARY** at campaign level (one-line GAQL check) — administrative, but required for guideline sign-off.
4. **Do not act on May 30–Jun 2 as final** — those 4 days are inside the open attribution window.
Bottom line: the pixel is not the suspect. The auction is solved. The 0.75% CVR is a *real* funnel leak the form fix should move — but until the May 23 conversion is matched to a real lead, "tracking verified" means *verified in test*, not *field-proven*.
— *Analytics Analyst*

---

## Session Log

### 2026-06-02 15:38 — You already produced your report. Now review your PEERS' reports below and cross

**Task:** You already produced your report. Now review your PEERS' reports below and cross-examine them.

FOCUS: Reconcile the central conflict: is the 1-conv-in-14-days / 0.34% CVR a TRACKING problem (analytic
## Analytics Analyst — Cross-Examination
**2026-06-02 | responding to PPC Strategist, Search Term Hunter, Creative Director**
### 1. Conflicts with my view
**PPC Strategist on "redirect EN budget to Turkish groups"**
Both PPC and Creative Director use this phrase, but PPC's own cross-examination correctly identifies it as mechanically wrong under Manual CPC: pausing EN at current spend levels (~$0.50–1/day) doesn't move money to Turkish groups — it simply goes unspent unless keyword bids in those groups are actively raised. This framing is seductive but inaccurate. The honest argument for pausing EN is: stop a
**Search Term Hunter on "8.8% waste is a meaningful CVR lever"**
The Hunter correctly concedes in cross-examination that negatives address ~$60–70/month of waste, while the form fix addresses 3x lead volume on the same $1,800+/month spend. But the action table still lists eight "Now" items, which will compete for execution slots with the structural changes. The waste problem is real and worth fixing — it's just not a CVR lever. Negatives improve spend efficienc
### 2. Where I concede
**Creative Director is right on the EN group framing.** My report said "EN group has 0 conversions, $241 spent." That's correct but incomplete. Creative Director's LP-mismatch framing (English ad → Turkish LP → guaranteed bounce or friction) is the *mechanistic* explanation that closes the case. The $241/0 conv data point alone could be explained by low volume; the LP mismatch explains *why* it st
**PPC Strategist's execution calendar is right.** My report ended with a "NOW WHAT" priority list but didn't sequence it against the one-change-per-day rule. PPC's proposed calendar (Day 1: negatives only, Day 2: EN pause, Day 3: bid caps, Jun 4+: RSA pins + keywords) is the correct operational format. I should have produced that.
**Search Term Hunter's keyword sequencing concession is right.** Citizenship-pathway keywords should not be added before the RSA has matching headlines. Adding them now would send more traffic into QS-1 keywords, worsening CPC temporarily. Correct call to sequence headlines (Jun 4) before keyword additions (Jun 5+).
### 3. What the team collectively missed
**The May 23 conversion remains unreconciled — nobody actioned it.** I raised this as the single highest analytical priority: match the May 23 dashboard conversion to a Gravity Forms entry row and a GCLID. Without this, every CVR percentage in every report is built on a number that *might* be a test artifact. PPC used it as signal for "conversion tracking works." Creative Director used it to valid
**`fxvWCM-vu6scELCTg4oD` primary flag not verified.** I flagged this in my original report: the Turkey campaign's dedicated conversion label exists and is the right type, but whether it's explicitly set PRIMARY at campaign goal level is unconfirmed from context. No peer picked this up. If it's set SECONDARY, the bidding algorithm has no primary signal even when conversions record. One GAQL pull cl
**Czech vs Turkish language targeting remains unresolved with no named owner.** PPC, Search Term Hunter, and Creative Director all flagged it. The GTM Specialist's May 19 notes say Turkish was added; context shows `English, Czech`. These cannot both be true. But in the cross-examination phase, the action item is still floating — no one said "I will run the API check today." This is a read-only ver
**Forced consensus sequence:**
| Day | Action | Type | Owner | Rationale |
|-----|--------|------|-------|-----------|
| Today (pre-changes) | Verify language targeting live (API check: English + Turkish or Czech?) | Read-only | PPC Strategist | No cost; may change all subsequent QS diagnoses |
The LP form fix (9→3 fields + dead-click bugs) is outside this table — it's the single highest-leverage action in the campaign but belongs to the LP team. The brief should go out in parallel today. It is not a "change" under the one-change-per-day rule; it's a separate workstream that should not wait for the ads calendar to complete.
— *Analytics Analyst*
