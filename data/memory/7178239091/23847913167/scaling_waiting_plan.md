# Scaling & Waiting Plan — Campaign 23847913167 (MapleRoots)

**Set:** 2026-06-02 | **Owner:** PPC Strategist | **Status:** ACTIVE — in waiting window

## Why we're waiting (the waiting plan)

On **2026-06-02** we shipped the structural-cleanup block (the "TODAY task"):
- Fixed the leak: `"canadian citizenship through parents"` PHRASE removed → re-added as `[canadian citizenship through parents]` EXACT @ $0.65 (criterion `930552782390`).
- Campaign-level PHRASE negatives added: `"parent was born in canada"`, `"i was born in canada"`.
- Fed AG3: `bill c-3 canadian citizenship` + `[bill c-3 citizenship]` raised $1.29 → $1.45.
- Stopped AG2 bleed: `[grandparent canadian citizen]` + `"canadian grandparent citizenship"` → $0.45.
- Added converter: `[my grandfather was born in canada can i get citizenship]` EXACT → AG2 @ $0.65 (criterion `2487699848355`).

**Per campaign guidelines (ONE change-type per day, wait 7 clean days before reading), the earliest honest review/scale date is 2026-06-09.** The exact `through parents` keyword also starts fresh on Quality Score — expect a few days of QS rebuild. Do NOT stack new changes on top during the window; hold all other moves for separate days.

## Staged-scale plan (the boost — slow, gated on CPA)

Budget is already **$130/day** (budget ID `15581336301`), not $100. We are NOT over-pacing — ~$127/day actual is on-budget. The "boost" the stakeholders asked for is a staged climb, each step gated on **CPA ≤ $55**:

| Date | Move | Trigger to advance |
|------|------|--------------------|
| Now → Jun 9 | Hold **$130/day**, let the leak fix settle | 7 clean days post-fix |
| **Jun 9** | Step to **$170/day** (~30% boost) | CPA holding ≤ $55 |
| Jun 16 | Step to **$220/day** | CPA still ≤ $55 + losing impr share to budget |
| Jun 23+ | Toward **$260/day** | Same gates hold |

Stakeholder message: "We're already at $130; we scale 30% now → 100% by month-end, gated on CPA." Not a "wait" answer — a confident staged answer.

## Bidding-strategy switch (deferred, NOT today)

Manual CPC → Maximize Conversions is on the table (27 conv/14 days ≈ 58/mo, well above the 15-conv/30-day floor) but **deferred ~7–10 days** because:
1. Switching now would override the manual bid moves we just made (AG3 raise, AG2 lower).
2. The `through parents` signal needs to be clean first — automating on a polluted signal teaches Google the wrong intent.
3. Learning-phase volatility (7–14 days) would muddy attribution of today's changes.

**Sequence:** clean run through ~Jun 9–12 → then switch to Maximize Conversions on a clean signal. PPC Strategist to flag the switch date at the Jun 9 review.

## Jun 9 review checklist
1. Did blended CPA move $66 → ~$52 after the leak fix? (success gate for the first scale step)
2. Is `[through parents]` EXACT QS rebuilding? CVR on the tightened keyword?
3. AG3 impression-share gain from the $1.45 bids?
4. AG2 CPA after the $0.45 cut + the new grandparent converter keyword?
5. If CPA ≤ $55 → step budget to $170/day AND flag the Manual → Maximize Conversions switch.

## Still-pending (separate days, do NOT stack)
- AG1 AVERAGE → GOOD headline trim (Creative Director) — 64% of spend, higher leverage than AG2 copy.
- Dev: ship the free P0 LP fixes (Submit → "Get My Free Consultation", remove "How did you hear" field, drop to 5 fields) — the never-shipped experiment.
- Analytics: clean `/lp/`-only Clarity pull for isolated post-switch behavior.
