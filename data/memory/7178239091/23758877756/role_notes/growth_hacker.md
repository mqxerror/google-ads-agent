# Growth Hacker Notes

**Last updated:** 2026-07-17 11:35

**Task:** Arbitrate the NEW fork only: 'switch to Meta or fix this' — context data only, no tool calls, plain-language (user is a beginner on Meta). Ground truth to use: 3 lifetime conversions, ALL in the Turki

**Critical Details:** GTM-WZKDXFH8
**Fix first. Meta is a future test, not a rescue.**
**Why Google Search here is the right channel:**
Turkish investors are actively searching "yunanistan golden visa" — that's demand that already exists. The 3 lifetime conversions (all from the Turkish core, per Jul 14 inventory) prove real buyers are reachable on this channel. You don't abandon a proven demand-capture channel because the funnel has been left broken for 45 days.
**Meta would inherit the same broken funnel:**
Switching to Meta moves you from warm searchers (active intent) to cold interruption (no intent). The unfixed 9-field form with dead-click bugs (Jun 2 CRO — **stale, needs re-verify before acting on it**), the unverified tracking (live LP fetch this session still shows "none detected" — P=0.65 static-fetch artifact, browser-render check still outstanding from Jun 2), and the Czech targeting ghost 
**The real diagnosis:** ~$1,200/lead is the CPA of a campaign running with ~$127/week in informational waste, a never-paused EN group ($371 / 0 conv), and Czech language suppressing QS — none of which have shipped despite being agreed in Jun/Jul. The $40/day budget target is already achievable from cuts alone without touching the dial.
**Precondition for fix-first verdict:** The agreed list must actually ship this time — 4 negatives, EN pause, Czech fix, LP form verification.
**30-day kill criterion → trigger Meta test:**
After cuts ship and budget hits $40/day: if fewer than 2 conversions in 30 days, or CPA remains above $800 with fixes in place, trigger Meta test.
**Minimum viable Meta test spec (if triggered):**
- Turkish creative, investor/Plan B framing, no eligibility language
- Meta Lead Ads native form (3 fields max) — NOT the current 9-field LP
- Dedicated Meta conversion event, completely separate from Google's `fxvWCM-vu6scELCTg4oD`
- Budget: $30–40/day (match the Google plan; no invented Meta CPL benchmarks)
— *Growth Hacker*

---

## Session Log

### 2026-07-17 11:35 — Orchestrated finding

{
  "summary": "Fix Google first \u2014 the channel has proven demand, the CPA is inflated by 45 days of unexecuted agreed cuts; Meta is a 30-day conditional test, not the next step.",
  "findings": [
    {
      "claim": "Fix Google first \u2014 3 proven conversions from active Turkish searchers make this a funnel problem, not a channel problem; Meta would inherit the same unverified tracking and unfixed LP form",
      "severity": "high",
      "confidence": 0.87,
      "sources": [
        "Jul 14 keep/cut inventory: all 3 lifetime convs in yunanistan-golden-visa Turkish core",
        "Live LP fetch this session: 'form signal: none detected' on both URLs (P=0.65 static-fetch artifact)",
        "Jun 2 CRO audit (STALE): 9-field form + dead-click bugs \u2014 needs browser re-verify before acting",
        "Agreed fix list unexecuted: \u015fartlar\u0131/nedir/nas\u0131l al\u0131n\u0131r/ek\u015fi negatives ~$127/wk still matching, EN group 45d overdue"
      ],
      "disconfirmed_by": "Browser JS-render check confirming the LP form and GTM-WZKDXFH8 are broken (not a static-fetch artifact) \u2014 would mean even repaired Google traffic can't convert, making Meta's native Lead Ads form genuinely superior",
      "id": "c2-f0"
    },
    {
      "claim": "30-day kill criterion: fewer than 2 conversions or CPA above $800 at $40/day post-cuts triggers a minimum viable Meta test with Lead Ads native form and a dedicated conversion event",
      "severity": "medium",
      "confidence": 0.82,
      "sources": [
        "Business economics: $20K\u2013$100K+ deal value; $800 CPA is still profitable but signals structural non-fixability",
        "Meta test spec: Turkish creative, 3-field Lead Ads form, own conversion action, $30\u201340/day \u2014 no invented Meta CPL benchmarks"
      ],
      "disconfirmed_by": "Post-cuts data showing CPA improving toward $300\u2013400 range within 30 days \u2014 would push kill criterion out further",
      "id": "c2-f1"
    }
  ]
}
