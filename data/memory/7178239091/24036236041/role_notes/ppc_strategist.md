# Ppc Strategist Notes

**Last updated:** 2026-07-16 17:52

**Task:** Write the campaign performance report for Panama QIP — US — Search — v2 (ID 24036236041) strictly from the in-context data. Cover: (1) day-by-day 2026-07-14→16 (73→748→634 impr; 8→49→38 clicks; $33.37

**Critical Details:** https://www.mercan.com/lp/panama-qualified-investor-program`
## Panama QIP — US — Search — v2 | Performance Report | Jul 14–16, 2026
**Day-by-Day Trend**
| Date | Impr | Clicks | Cost | CTR | CPC |
|------|------|--------|------|-----|-----|
CPC rose **+40% in 3 days**; CTR fell **5pp**. Maximize Conversions is bidding up for volume with zero conversion signal to anchor it. **0 conversions on 95 clicks.**
**Spend Allocation — concentration risk**
- Property Investors: $265.75 / 58 clicks / 0 conv → **56% of budget**, driven by generic searchers ("buy property in panama," "homes for sale in panama") — low QIP intent
- Residency Core (Converters): $120.05 / 23 clicks / 0 conv
- RBI Category: $73.46 / 11 clicks / 0 conv
- Investor Program (High Intent): $12.39 / 3 clicks / 0 conv — highest-intent group, lowest share
**Bidding Phase**
Campaign is ~2 days old with 0 conversions. Per phase rules: **no bid-strategy or budget changes.** Flag only: the algorithm has no signal, so it defaults to click volume — Property Investors wins spend by default.
**Critical Landing Page Flag (verified this session)**
Live fetch of `https://www.mercan.com/lp/panama-qualified-investor-program` returned HTTP 200 but **no form signal and no tracking token detected**. If no form is visible or the conversion tag isn't firing, 0 conversions is guaranteed regardless of traffic quality. **Verify form presence and conversion firing before diagnosing this as a traffic or bidding problem.**

---

## Session Log

### 2026-07-16 12:58 — Orchestrated finding

{
  "summary": "$471.66 spent / 95 clicks / 0 conversions in 3 days; primary risk is a landing-page tracking gap (no form or tag detected on live fetch) \u2014 confirm conversion fires before any structural change.",
  "findings": [
    {
      "claim": "Landing page returned no form signal and no tracking token on live fetch \u2014 0 conversions likely reflects a page or tracking gap, not traffic quality",
      "severity": "high",
      "confidence": 0.85,
      "sources": [
        "LIVE LANDING PAGE STATE: form signal: none detected, tracking token: none detected"
      ],
      "disconfirmed_by": "A live form-submit test that confirms the GV Lead conversion fires in GTM confirms tracking is intact",
      "id": "c1-f0"
    },
    {
      "claim": "Property Investors ad group is consuming 56% of spend ($265.75) on generic real-estate intent, not QIP investor intent",
      "severity": "high",
      "confidence": 0.9,
      "sources": [
        "Ad group data: 58 clicks / $265.75 / 0 conv",
        "Search terms: 'panama real estate', 'homes for sale in panama', 'panama real estate for sale'"
      ],
      "disconfirmed_by": "If these terms produce conversions at learning-phase completion, spend share is justified",
      "id": "c1-f1"
    },
    {
      "claim": "CPC rising +40% ($4.17\u2192$5.84) with CTR falling 5pp signals Maximize Conversions bidding for volume without conversion data",
      "severity": "medium",
      "confidence": 0.85,
      "sources": [
        "Day-by-day metrics Jul 14\u201316"
      ],
      "disconfirmed_by": "CPC stabilizes once the algorithm accumulates enough impression/click signal in the learning phase",
      "id": "c1-f2"
    },
    {
      "claim": "No bid-strategy or budget changes should be made \u2014 campaign is in learning phase, <7 days old, 0 conversions",
      "severity": "low",
      "confidence": 0.95,
      "sources": [
        "Phase rules: Maximize Conversions requires 15+ conv/month; campaign age ~2 days"

### 2026-07-16 17:52 — do you need to tell a Panama QIP lead apart from a Panama Friendly Nations lead 

**Task:** do you need to tell a Panama QIP lead apart from a Panama Friendly Nations lead in your bidding? No
it is accunt defualt i tried to switch campaign goal and it showed only submit ;ead forms nothing sp
## Your instinct is 90% right — one correction, and one missing Google feature that explains what you saw in that Goals screen.
### Locked in: one Panama action for everything
You answered No — you don't need QIP vs Friendly Nations separated in bidding. So the design is final: **Panama QIV Lead serves every Panama campaign, forever.** And yes, when a future Panama campaign uses a different landing page, you extend the *same* action rather than creating a new one. One caveat on the "add an extra URL" part: that works exactly as you describe **if** the action is URL-rule
### The one thing you've got slightly wrong: attribution and goals are two different machines
> "google will always attribute the click id to the right ad anyway"
True — but that solves a different problem than the one account-default goals creates. Two separate mechanisms:
| Machine | Question it answers | Your status |
|---|---|---|
| **Attribution (GCLID)** | *Which campaign gets credit* for a conversion | ✅ Working — always routes to the right ad, you're correct |
| **Goal settings** | *Which conversion events count at all* for this campaign's bidding | ⚠️ Account-default = **every** primary lead action in the account counts |
Attribution never misroutes credit. But with account-default goals, if someone clicks your Panama ad, wanders to the Greece page, and submits *that* form — Greece GV Lead fires, attribution correctly credits your Panama campaign (it owned the click), and Maximize Conversions learns "this Panama search term converts." Attribution did its job perfectly and you still got polluted data. Attribution de
In practice this leak is small — cross-page wandering to another program's form is rare. The bigger pollutant is that **`[DEPRECATED] Greece GV Turkey CP - DO NOT USE` is still ENABLED and primary**, sitting inside the same "Submit lead form" folder every account-default campaign optimizes toward.
### Why the Goals screen "showed only Submit lead forms, nothing specific"
That's not a bug and you didn't miss a menu — it's how Google designed it. The campaign-goals picker operates at the **category folder** level, never the individual action level. Picking "Submit lead form" there would still mean *all six* primary lead actions feed this campaign, so it changes nothing.
The feature you were looking for exists, it's just hidden under a different name: a **custom goal**. In Tools → Conversions → **Goals** (left sidebar) → Create custom goal → you build a goal containing *only* Panama QIV Lead. That custom goal then appears in the campaign's Goals settings as a selectable option. That's the only mechanism in Google Ads that scopes a campaign to a specific action.
### My recommendation
**Do (needs your approval, account-level):** flip `[DEPRECATED] Greece GV Turkey CP` to **secondary**. This cleans the default goal folder for every campaign in the account, touches no campaign's learning phase, and per the Director's earlier note should happen regardless of anything else.
**Do tomorrow, not today (campaign-level):** create the custom goal "Panama QIV Lead" and assign it to this campaign. Reasons for yes: Maximize Conversions is sitting on n=1 — it is maximally sensitive to a single junk signal right now, and a goal change at day 4 is the cheapest it will ever be (at day 30 it costs real learning). Reason for *tomorrow*: the negatives were today's change, and the on
**Don't:** create any new conversion action, ever, for a Panama campaign pointing at a page the existing action can cover. Extend the URL rules (or the GTM trigger) instead.
Nothing here executes without your word — the deprecated-action flip and the custom goal are both changes I'd want you to explicitly approve. Say "do the custom goal tomorrow" and it goes on the log for Jul 17.
*— PPC Strategist*
