# Pinned Facts: Campaign 24002195025

<!-- Facts listed here are ALWAYS included in agent context. -->
<!-- They never expire from the conversation window. -->

- **Campaign ID:** 24002195025 — every recommendation must be scoped to THIS campaign only.
- **Currency:** USD (account billing currency). Convert any £/€ benchmark to USD before recommending.
- **Status:** Brand-new campaign created 2026-07-06. Until at least 7 days and 100+ impressions exist, **do not invent CPA/CPC/QS baselines** — say explicitly that there isn't enough data yet.
- **Landing page form (confirmed by Wassim 2026-07-16):** the form on mercan.com/lp/panama-qualified-investor-program is a **React frontend with a Gravity Forms backend**. It renders client-side, so raw-HTML fetches will report "no form detected" — that is EXPECTED, not a bug. Never diagnose "missing form" from a raw HTML fetch on this LP; verify form/tag behavior in-browser only. Lead entries live in Gravity Forms (check entries there for gclid/email when attributing leads).
- **Conversion goal (assigned 2026-07-16):** campaign optimizes only toward custom goal "Panama QIV Lead" (`customConversionGoals/6458374995`, conversion action ID `7607343274`, WEBPAGE type). WEBPAGE actions **cannot receive offline click-conversion uploads** — uploads require a separate UPLOAD_CLICKS ("import") action.
