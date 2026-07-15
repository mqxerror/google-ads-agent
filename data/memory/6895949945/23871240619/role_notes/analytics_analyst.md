# Analytics Analyst Notes

**Last updated:** 2026-07-14 12:12

**Task:** Ground the whole analysis in the conversion truth so the team doesn't re-litigate it: cite (reuse, do not redo) the settled findings — tracking verified working, form works, Wassim confirmed zero CRM 
## Conversion Truth — Settled, Do Not Re-Litigate
**The verified premise (do not re-open):** tracking is confirmed working, the form is confirmed functional, and Wassim confirmed **B** (zero CRM leads). What Google Ads reports is real.
**Funnel math:**
- Lifetime: 4 conv / ~$5,788 spend / 1,756 clicks → **CVR 0.23%, CPA ~$1,447**
- Last 14 days: **0 conv / $1,563 / 420 clicks → CVR 0.0%**
- Account tolerance band: $150–200 CPA. Actual is **7–10× over ceiling.**
**Critical methodological warning:** with ≤4 lifetime conversions across 17 keywords and 4 ad groups, **any per-keyword or per-ad-group CPA figure is statistically meaningless.** AG2's "4 conversions" is a sample of 4 — margin of error swamps the signal. Do not optimize bids, pause keywords, or rank ad groups by CPA at this volume. It produces false precision and wrong cuts.
**Correct success metric for the next phase:** once the email-capture soft offer is live, register it as a **Secondary conversion action** and track **email opt-in rate (target: 5–8% of clicks)**. That's the high-frequency signal this funnel needs — the $300K CTA fires too rarely to optimize against.
*Landing-page content and tag state: pending re-verification this session — no page claims asserted.*

---

## Session Log

### 2026-07-14 12:12 — Orchestrated finding

{
  "summary": "4 lifetime conversions on $5.8K spend (CPA ~$1,447) is real, not a measurement gap \u2014 the funnel is one-step and the hard CTA is priced out of reach for research-intent traffic; the unlock is a high-frequency secondary metric (email opt-in), not keyword optimization on a 4-event sample.",
  "findings": [
    {
      "claim": "Lifetime CPA of ~$1,447 is 7\u201310\u00d7 over the $150\u2013200 tolerance band, confirmed by CRM verification \u2014 this is not a tracking gap",
      "severity": "high",
      "confidence": 0.95,
      "sources": [
        "Lifetime spend $5,788 / 4 conv from live data",
        "Wassim B-confirmation (zero CRM leads)",
        "account CPA tolerance in business context"
      ],
      "disconfirmed_by": "CRM records surface delayed leads that were attributed to this campaign",
      "id": "c3-f0"
    },
    {
      "claim": "Per-keyword and per-ad-group CPA analysis is statistically degenerate and should not drive optimization decisions at current conversion volume",
      "severity": "high",
      "confidence": 0.99,
      "sources": [
        "4 lifetime conversions across 17 keywords / 4 ad groups \u2014 insufficient for significance"
      ],
      "disconfirmed_by": "Conversion volume reaches 30+ events, enabling meaningful segmentation",
      "id": "c3-f1"
    },
    {
      "claim": "Email opt-in rate on a soft-offer (guide download) is the correct primary optimization metric until the $300K consult CTA accumulates \u226515 conversions/month",
      "severity": "medium",
      "confidence": 0.9,
      "sources": [
        "Account bidding rule: <15 conv/30d \u2192 Manual CPC only",
        "0.0% CVR on hard CTA over last 14 days",
        "Clarity behavioral data: 60% read 1+ min, 0 form interactions"
      ],
      "disconfirmed_by": "The direct consult CTA begins converting at \u22655 conv/month after the /lp/ URL switch",
      "id": "c3-f2"
    }
  ]
}
