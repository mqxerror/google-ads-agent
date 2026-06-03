# Account-Wide Insights

<!-- Cross-campaign patterns and learnings -->

## Always-on anchors (every agent must respect these)

- **Account currency: USD.** Every metric returned by Google Ads (cost_micros, budget_micros, CPC, CPA) is in USD because the Google Ads account is billed in USD. **Never recommend in £/€/CHF without converting.** When discussing UK keyword markets, EU-cost benchmarks, or any non-USD figure, convert to USD inline (e.g. "UK GV CPC ~£10 ≈ $12-13 USD"). Do not mix units in the same recommendation.
- **No invented baselines.** If a campaign has no historical CPA/CPC/QS data (brand new, < 7 days, < 100 impressions), say so explicitly — do not pull benchmarks from "industry knowledge" or other campaigns and present them as expectations for this one.
- **Stay in your campaign's lane.** When writing to `role_notes/<role>.md`, the analysis MUST be about the campaign whose folder you are in. If the user asks about a different campaign, write to that campaign's folder, not the one selected in the conversation.

## Patterns

- **[2026-04-13]** All campaigns use inline gtag() + GTM safety net for conversion. Do NOT add per-campaign tags. Primary conversion: GV Lead (fc6FCO3YnI4cELCTg4oD).
- **[2026-04-13]** CRO pattern: landing pages have excellent visual design but weak copy (no emotional hooks). "Plan B" family safety messaging is open competitive space — apply to ALL campaigns.
