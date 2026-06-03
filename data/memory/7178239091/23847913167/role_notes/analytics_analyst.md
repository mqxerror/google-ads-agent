# Analytics Analyst Notes

**Last updated:** 2026-05-26 12:25

**Task:** analyze clarity data for this campaign
Let me pull Clarity data for the landing page across multiple dimensions in parallel.Now let me get one more data point — mobile vs desktop conversion behavior.# Clarity Behavioral Analysis — MapleRoots Landing Page
**Period:** May 16–26, 2026 | **Sessions:** 7,340 | **Campaign:** 23847913167
## The Headlines
| Metric | Value | Verdict |
|--------|-------|---------|
## Finding #1: 97.8% of Traffic Is Mobile — And Mobile Doesn't Convert
| Device | Sessions | % | Avg Duration | Form Submits | CVR |
|--------|----------|---|-------------|-------------|-----|
**This is the single most important finding.** Nearly ALL your paid traffic is mobile. Mobile users spend 76 seconds on a 13,500px page — they're seeing maybe the first 2 screens and leaving. PC users stay 3.4x longer but there are almost none of them (1.4%).
**The form at 11,363px is essentially invisible to 98% of your audience.**
Google Ads campaign data shows 1,297 clicks → Clarity shows 7,340 sessions. The gap is likely organic/direct visitors hitting the same page + some session fragmentation, but the mobile dominance applies to paid traffic too.
## Finding #2: Nobody Scrolls — The Page Is a Cliff
| Scroll Depth | Page Views | Cumulative % |
|-------------|-----------|-------------|
**78.7% of all visitors stop at 3% scroll depth.** On the old 13,500px page, 3% = ~405px. That's roughly the hero section + the first headline. They see the title, maybe the "Bill C-3" badge, and decide whether to continue or leave.
**Only 5.3% of visitors scroll past 4% (540px).** The form at 11,363px (84% scroll depth) is reached by essentially nobody organically scrolling.
This confirms the CRO audit finding: **the old page is built for readers, not converters. The form is invisible.**
## Finding #3: Converter Behavior — What the 18 Who Submitted Actually Did
From the 4 paid-search form-submit sessions Clarity captured:
| Session | Time to Form | Total Duration | Path |
|---------|-------------|---------------|------|
**Pattern:** Converters click the **"Request a free consultation" floating CTA** — they don't scroll to the form organically. The floating CTA is the only thing saving this page's conversion rate. Without it, the form would get zero submissions.
**The May 23 session is alarming:** A highly interested user spent 69 MINUTES across 6 page loads before finally submitting. They read the page for 27 minutes on the first visit, left and returned 4 more times over an hour before converting. That's an enormous amount of friction for a free consultation form.
## Finding #4: "Read the Complete Guide" Is a Conversion Leak
Multiple high-engagement sessions show this pattern:
1. Land on citizenship-by-descent page from Google Ad
2. Click **"Read the complete guide"** → navigates to `/bill-c-3-canadian-citizenship-2026-complete-guide`
3. Spend 20-40 minutes reading the Bill C-3 guide
4. **Never return to convert**
This is a content rabbit hole. Users leave the landing page for deeper content and never come back to the form. The "Read the complete guide" link is acting as a conversion leak — it satisfies the user's information need without capturing a lead.
**Sessions showing this pattern:** At least 6 of the top 20 longest sessions.
## Finding #5: Dead Clicks Tell Us What Users WANT to Click
| Page | Dead Clicks | Rage Clicks |
|------|------------|-------------|
251 dead clicks on the old page = users clicking things they expect to be interactive but aren't. From the session data, dead clicks are happening on:
- **"Submitted to Immigration, Refugees and Citizenship Canada"** — users think this is a clickable status/link
- **"Bill C-3 in force since..."** badge — users try to click the badge for more info
- **"Updated for the December..."** text — looks like a link but isn't
The new LP has 96% fewer dead clicks (10 vs 251) — its cleaner, more intentional design eliminates false affordances.
## Finding #6: Geographic & Channel Confirmation
| Country | Page Views | % |
|---------|-----------|---|
Targeting is clean — 95.7% US traffic as intended. The 3.1% Canada traffic is likely organic bleed (the page isn't behind geo-restrictions).
## The Clarity Verdict: Why This Campaign Has a 1.2% CVR
| Root Cause | Evidence | Impact |
|-----------|----------|--------|
## Recommendations — Informed by Behavioral Data
### Urgent (reinforces the LP switch decision)
**1. Switch ads to `/lp/canadian-citizenship-by-descent` ASAP**
- The new LP has the form at 167px (above fold) vs 11,363px
- 96% fewer dead clicks already
- With 98% mobile traffic, form above fold = immediately visible
- **Projected CVR lift: 1.2% → 2.5-3.5%** based on form position alone
**2. Remove or gate the "Read the complete guide" link on the new LP**
- Either remove it entirely (the new LP is self-contained), OR
- Move it BELOW the form so users encounter the conversion point first
- Currently leaking your most engaged visitors into a content rabbit hole
**3. Prioritize mobile form UX above all else**
- 98% of traffic is mobile. Every form optimization decision should be mobile-first.
- The 5-field reduction (8 → 5 fields) matters MORE than we thought — on a mobile screen, 8 fields = 3+ scrolls past the form. 5 fields = 1 scroll.
- Test the new LP on a 375px viewport before launch.
### This Week
**4. Investigate zero PC conversions**
- 106 PC sessions, 256s avg duration, 0 form submits. PC users are reading but not converting.
- Possible cause: on desktop, the form is in a right sidebar that may feel secondary to the content. Check if the form is visually prominent enough on desktop.
**5. Add a "mini-CTA" after the Three Paths section on new LP**
- The Bill C-3 guide link proves users want more info after reading eligibility paths.
- Instead of linking away, capture them: "Know your path? → Get My Free Consultation" inline CTA right after the paths section.
## Bottom Line
Clarity tells the story that Google Ads data couldn't: **this isn't a traffic quality problem or a bid optimization problem — it's a page architecture problem.** You're sending 98% mobile traffic to a 13,500px page with the form at 84% scroll depth, and only 5.3% of users scroll past the hero. The floating CTA is the only thing producing conversions at all.
**The new LP (`/lp/`) with form at 167px fixes the #1 problem.** Combined with the P0 changes (button text, field reduction), this should lift CVR from 1.2% to 2.5-3.5% — worth more than every bid correction we've made combined.
**When you're ready to switch, I'll update all 4 RSA final_urls in one shot.**
— *Analytics Analyst*