# Ppc Strategist Notes

**Last updated:** 2026-07-14 12:12

**Task:** Answer the 'recreate the campaign with a better strategy?' question head-on, plus items 1 (Trend Analysis), 2 (Ad Group Breakdown), 6 (Budget Allocation) and lead item 7 (Top 3 recommendations). Use O
**On "recreate with a better strategy":** No. The campaign shell is not the problem — Manual CPC means no Smart Bidding learning to reset, and no conversion history is sacrificed by tearing it down. The funnel (no soft-offer, wrong LP URL — per the prior team verdict, still pending the ad-blocker-blocked switch) is the diagnosed problem and survives any rebuild intact. A new campaign ID fixes noth
**Trend Analysis (14 days):**
- Pre-Jul 8: CPC $3.03–3.60, CTR 8–14%, healthy
- **Jul 8 inflection:** CPC jumped to $4.61, held $4.00–4.64 through Jul 13 — ~30% auction-cost increase with no offsetting conversion signal
- Jul 13–14: impressions collapsed (207→62) — budget exhaustion or QS drag pulling the campaign out of auctions
**Ad Group Breakdown:**
| AG | Spend | Conv | Verdict |
|---|---|---|---|
**Budget Allocation:** AG1 absorbs ~38% of lifetime spend with zero conversions. Pausing AG1+AG3 concentrates all spend on AG2 at ~$60–70/day — no budget-line change required, spend self-corrects.
**Top 3 by effort vs. impact:**
1. **Pause AG1 + AG3** (5 min, immediate) — stops 36% of bleed, no downside
2. **Switch final URLs to `/lp/`** (blocked by ad-blocker modal — needs browser fix) — the two-step soft offer is the conversion unlock the whole team converged on
3. **Add `[PHRASE] eu` / `[PHRASE] european` campaign negatives** (low effort) — pre-empts EU-citizenship query contamination from Google's keyword recommendations

---

## Session Log

### 2026-07-14 12:12 — Orchestrated finding

{
  "summary": "Don't rebuild \u2014 pause AG1+AG3, unblock the /lp/ URL switch, and judge the campaign only after a working two-step funnel is live.",
  "findings": [
    {
      "claim": "Pause AG1 immediately \u2014 $2,152 spent with 0 conversions, 32% of lifetime budget, no return",
      "severity": "high",
      "confidence": 0.93,
      "sources": [
        "AG lifetime splits, LIVE CAMPAIGN DATA"
      ],
      "disconfirmed_by": "AG1 converts within 7 days after the /lp/ switch is live",
      "id": "c1-f0"
    },
    {
      "claim": "Do not recreate the campaign \u2014 the funnel is the problem, not the campaign shell; Manual CPC means no learning phase to sacrifice",
      "severity": "high",
      "confidence": 0.91,
      "sources": [
        "Prior team verdict (throttle-don't-kill, two-step funnel gate)",
        "Manual CPC status, LIVE CAMPAIGN DATA"
      ],
      "disconfirmed_by": "A rebuilt campaign with /lp/ + lead-form asset converts while the current campaign does not under identical conditions",
      "id": "c1-f1"
    },
    {
      "claim": "Jul 8 CPC inflection ($3.30\u2192$4.50, +36%) is a structural auction signal, not a budget artifact \u2014 likely QS degradation on low-converting keywords",
      "severity": "medium",
      "confidence": 0.78,
      "sources": [
        "14-day daily table, LIVE CAMPAIGN DATA"
      ],
      "disconfirmed_by": "CPC normalizes below $3.60 within 7 days without any change",
      "id": "c1-f2"
    },
    {
      "claim": "Concentrate all spend on AG2 by pausing AG1+AG3 \u2014 no budget-line change needed, spend self-corrects to ~$60-70/day on the only producing lane",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "AG lifetime splits, LIVE CAMPAIGN DATA",
        "prior team consensus"
      ],
      "disconfirmed_by": "AG2's 4 conversions are confirmed as tracking artifacts not reflected in the CRM",
      "id": "c1-f3"
    }
  ]
}
