export interface ChatTemplate {
  id: string;
  label: string;
  icon: string;
  category: 'create' | 'analyze' | 'optimize' | 'audit' | 'report';
  description: string;
  prompt: string;
  /** If true, the prompt includes {campaign} placeholder to be filled with selected campaign name */
  needsCampaign?: boolean;
  /** Suggested model for this template */
  suggestedModel?: 'fable' | 'sonnet' | 'opus' | 'haiku';
}

const templates: ChatTemplate[] = [
  // ── Create ─────────────────────────────────────────────
  {
    id: 'clone-campaign',
    label: 'Clone & Adapt Campaign',
    icon: '🧬',
    category: 'create',
    description: 'Create a new campaign based on a successful existing one',
    needsCampaign: true,
    suggestedModel: 'opus',
    prompt: `Analyze the currently selected campaign "{campaign}" — its structure, keywords, match types, ad copy, bidding strategy, and performance data.

Then create a NEW campaign based on what's working, adapted for: [DESCRIBE NEW TARGET/PRODUCT HERE]

Requirements:
- Keep the same campaign structure and match type strategy that's proven
- Adapt keywords and ad copy for the new product/market
- Use the same bidding approach
- Suggest a starting budget based on the reference campaign's performance
- Create as PAUSED so I can review before enabling

Show me the full plan before executing.`,
  },
  {
    id: 'new-campaign-brief',
    label: 'Campaign from Brief',
    icon: '🚀',
    category: 'create',
    description: 'Build a complete campaign from a marketing brief',
    suggestedModel: 'opus',
    prompt: `Create a new Google Ads Search campaign with these details:

Product/Service: [WHAT ARE YOU ADVERTISING]
Target Audience: [WHO ARE YOU TARGETING]
Landing Page: [URL]
Daily Budget: $[AMOUNT]
Goal: [lead gen / e-commerce / brand awareness]
Geographic Targeting: [COUNTRIES/REGIONS]

Please propose:
1. Campaign settings (name, bid strategy, networks)
2. 3-5 ad groups organized by intent level
3. 15-20 keywords per ad group with appropriate match types
4. Negative keyword seed list (20+ terms)
5. 3 responsive search ads (15 headlines + 4 descriptions each)
6. Recommended bid strategy with rationale

Create as PAUSED. Show the full plan and wait for my approval before executing.`,
  },
  {
    id: 'new-adgroup',
    label: 'Add Ad Group to Campaign',
    icon: '📁',
    category: 'create',
    needsCampaign: true,
    description: 'Add a new ad group with keywords and ads to existing campaign',
    suggestedModel: 'sonnet',
    prompt: `For the campaign "{campaign}", create a new ad group:

Theme/Topic: [DESCRIBE THE AD GROUP THEME]

Please propose:
1. Ad group name
2. 10-15 keywords with match types (based on what's working in other ad groups)
3. Negative keywords specific to this ad group
4. 2 responsive search ads tailored to this theme
5. Suggested CPC bid (based on campaign's current performance)

Show the plan before executing.`,
  },
  {
    id: 'business-agent-leads-watch',
    label: 'Business Agent for Leads Watch',
    icon: '🤝',
    category: 'create',
    description: 'Track the Gemini lead-agent beta and check whether the site is ready to power it',
    suggestedModel: 'sonnet',
    prompt: `Watch + readiness check for Google's "Business Agent for Leads" — a Gemini chat unit that replaces the static lead form, answers prospect questions grounded in your website copy, then submits a pre-filled form once the conversation signals real intent. It launched at Google Marketing Live (2026-05-20) and is in beta.

1. **Check current availability / beta status**: do a quick web search to confirm the current state (still beta? GA? eligibility criteria?) — this moves fast. Report what you find WITH the source date; don't assume it's still where it was in May 2026.

2. **Assess fit for this account**: it's purpose-built for high-consideration, question-heavy purchases — exactly RBI / immigration (eligibility, budget, timeline questions before a form). Give a plain-language recommendation on whether to pursue the beta and what it could do for lead quality (pre-qualification before the form submits).

3. **Prerequisite audit — site copy accuracy (this is the gate):** the agent speaks AS the brand and answers ONLY from site content, so **site accuracy becomes ad accuracy**. Before enabling, the LP/site copy it would ground on must be current and compliant. Check for outdated program facts (stay requirements, investment minimums, timelines) — e.g. the Panama QIP "one visit every 2 years" fact must be correct — and confirm there is no citizenship or guaranteed-approval language the agent could repeat. List everything that must be fixed before this can be turned on.

Output: current beta status (with source), a fit verdict, and a punch-list of site-copy fixes required before enabling. Nothing gets enabled without my approval.`,
  },

  // ── Analyze ────────────────────────────────────────────
  {
    id: 'daily-review',
    label: 'Daily Performance Review',
    icon: '📊',
    category: 'analyze',
    needsCampaign: true,
    description: 'Quick daily health check with actionable insights',
    suggestedModel: 'sonnet',
    prompt: `Daily review for "{campaign}":

1. How did yesterday compare to the 7-day average? Flag any anomalies.
2. Are we on pace for monthly budget? Any pacing issues?
3. Any keywords with high spend and zero conversions?
4. Top 3 converting search terms — are they added as keywords?
5. Any immediate actions recommended?

Keep it concise and actionable.`,
  },
  {
    id: 'performance-deep-dive',
    label: 'Performance Deep Dive',
    icon: '🔬',
    category: 'analyze',
    needsCampaign: true,
    description: 'Comprehensive campaign analysis with strategic recommendations',
    suggestedModel: 'opus',
    prompt: `Deep performance analysis for "{campaign}":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown**: Which ad groups are carrying performance? Which are dragging?
3. **Keyword Efficiency**: Map keywords by CPA — identify winners, losers, and untested potential.
4. **Quality Score Audit**: Any keywords below QS 5? What's the impact?
5. **Search Term Quality**: What % of traffic comes from irrelevant terms? Estimate wasted spend.
6. **Budget Allocation**: Is budget distributed optimally across ad groups?
7. **Strategic Recommendations**: Top 3 changes that would have the biggest impact, prioritized by effort vs impact.`,
  },
  {
    id: 'budget-waste',
    label: 'Budget Waste Analysis',
    icon: '💸',
    category: 'analyze',
    needsCampaign: true,
    description: 'Find and fix wasted ad spend',
    suggestedModel: 'opus',
    prompt: `Analyze budget waste for "{campaign}":

1. **Non-converting keywords**: Which keywords have spent >$20 with 0 conversions?
2. **Irrelevant search terms**: Identify search terms that don't match buyer intent and estimate wasted spend.
3. **Low QS keywords**: Keywords with Quality Score <5 — what's the estimated CPC premium?
4. **Ad group imbalance**: Are any ad groups consuming budget disproportionately?
5. **Time-of-day waste**: If data available, any dayparting opportunities?

For each issue found, provide the specific fix (negative keyword, pause, bid adjustment) and estimated savings.`,
  },
  {
    id: 'ai-overviews-exposure',
    label: 'AI Overviews Exposure Check',
    icon: '🔮',
    category: 'analyze',
    needsCampaign: true,
    description: 'Find AIO-triggering queries dragging CTR and build an SEO citation-target list',
    suggestedModel: 'opus',
    prompt: `AI Overviews (AIO) exposure check for "{campaign}". Informational immigration queries ("Panama residency requirements", "Greece golden visa cost") trigger AI Overviews most, which compresses paid CTR and inflates CPC.

1. **Identify likely-AIO-triggering queries** in this campaign's search terms — the informational / research-stage terms (requirements, cost, how-to, eligibility, timeline) versus commercial / bottom-funnel terms (consultant, apply, "invest in", program name + intent). Split the terms into likely-AIO vs commercial.

2. **Check CTR drift**: compare CTR (and CPC if available) on the likely-AIO informational terms vs the commercial terms over a recent window. Quantify the gap. Per the research, AIO-present paid CTR is recovering (14.64%→16.21%, Jan'25→Feb'26) but still sits below non-AIO CTR — so look for RELATIVE drag, not collapse.

3. **Build a citation-target list for the SEO channel**: the terms where AIO hurts most are where an organic AIO *citation* would help most — brand cited in the AIO is associated with **~+91% paid CTR** (Seer, Q3 2025 — cite as reported, not as a guarantee). Output the ranked list of query themes to hand to seo-supreme-agent as citation targets.

Output: the AIO-vs-commercial term split with CTR/CPC comparison, a recommendation to shift budget toward higher-intent terms where AIO drags, and the SEO citation-target list. This is analysis + a cross-lane handoff, not an ads change.`,
  },

  // ── Optimize ───────────────────────────────────────────
  {
    id: 'search-term-audit',
    label: 'Search Term Audit',
    icon: '🔍',
    category: 'optimize',
    needsCampaign: true,
    description: 'Review search terms and suggest negatives',
    suggestedModel: 'sonnet',
    prompt: `Search term audit for "{campaign}":

1. Review all search terms from the last 7 days
2. Categorize each as: HIGH VALUE (converting, add as keyword), IRRELEVANT (negate), or MONITOR (need more data)
3. For irrelevant terms, suggest the negative keyword and match type (exact vs phrase)
4. For high-value terms not yet added as keywords, recommend adding them
5. Estimate total wasted spend on irrelevant terms

List the negative keywords to add, grouped by match type. I'll approve before you apply them.`,
  },
  {
    id: 'ad-copy-workshop',
    label: 'Ad Copy Workshop',
    icon: '✍️',
    category: 'optimize',
    needsCampaign: true,
    description: 'Improve RSA headlines and descriptions',
    suggestedModel: 'opus',
    prompt: `Ad copy workshop for "{campaign}":

1. Review all current responsive search ads — headlines and descriptions
2. Identify which ads/ad groups have the lowest CTR
3. For the weakest ads, propose NEW headlines using these frameworks:
   - Benefit-driven: What does the user get?
   - Urgency/Scarcity: Why act now?
   - Social proof: Who else has benefited?
   - Question-based: Engage curiosity
4. Propose 5 new headlines and 2 new descriptions for each underperforming ad
5. Explain the rationale for each

Show me the proposals before making changes.`,
  },
  {
    id: 'bid-strategy-review',
    label: 'Bid Strategy Review',
    icon: '⚡',
    category: 'optimize',
    needsCampaign: true,
    description: 'Evaluate and optimize bidding strategy',
    suggestedModel: 'opus',
    prompt: `Bid strategy review for "{campaign}":

1. Current bid strategy and how long it's been active
2. Is the campaign in learning phase? If so, when will it exit?
3. Conversion volume analysis — does the campaign have enough data for automated bidding?
4. If using Maximize Conversions, should we switch to Target CPA? What target?
5. If using Manual CPC, is there enough data to switch to automated?
6. Compare current CPA to what a different strategy might achieve

RESPECT THE PHASE RULES — if in learning phase, recommend patience not changes.`,
  },
  {
    id: 'value-based-bidding-gate',
    label: 'Value-Based Bidding Gate',
    icon: '💰',
    category: 'optimize',
    description: 'Which campaigns clear the volume floor for value bidding, and how to stage the switch',
    suggestedModel: 'opus',
    prompt: `Account-wide value-based-bidding (VBB) gate check. VBB teaches Smart Bidding to optimize for lead QUALITY, not raw volume — the single biggest quality lever for this account — but it has a hard volume floor and a value-signal prerequisite.

1. **Volume gate**: for each campaign, pull conversions over the last 30 days. The practical floor for value bidding is **~30 conv/30d** (tROAS technically needs ≥15, but practitioners want 30-50). List which campaigns clear it and which don't.

2. **For campaigns that clear the floor**: assess lead-stage value feasibility. CRM stages exist (MQL / SQL / consult-booked / deal) but there is **no value feed wired yet**. State what it would take to push lead-stage values via GCLID offline import (which, since 2026-06-15, must go through the Data Manager API — not the Ads API). Recommend the staging: start on **tCPA**, seed value data for the full 4-week / 3-conversion-cycle window, then move to **Max-Conv-Value / tROAS**. Recommend tCPA vs tROAS per campaign with rationale.

3. **For campaigns BELOW the floor**: give an explicit "not yet" verdict — state the current 30-day conversion count, the exact number of additional conversions needed to reach ~30, and keep them on tCPA / Max-Conv until they get there. VBB below the floor fails; do not recommend it.

Output a table: Campaign | 30d conv | Clears floor? | Value feed feasible? | Recommended strategy | Verdict. No changes without my approval.`,
  },
  {
    id: 'match-type-mix-review',
    label: 'Match-Type Mix Review',
    icon: '🎚️',
    category: 'optimize',
    needsCampaign: true,
    description: 'Audit the broad/phrase/exact keyword split against real conversion signals',
    suggestedModel: 'opus',
    prompt: `Match-type mix review for "{campaign}". The evidence conflicts — Optmyzr's 30k-account Feb-2026 study finds phrase match dominates lead-gen and broad "loses its footing" without conversion-value signals, while Search Engine Land argues to drop phrase entirely — so resolve it with THIS campaign's data, not doctrine.

1. **Audit the current split**: pull all keywords and break down spend / clicks / conversions / CPA by match type (broad vs phrase vs exact). Output a table.

2. **Apply the conditional rule:**
   - **Broad match is only defensible when Smart Bidding is receiving a value/quality signal** (offline lead-value data feeding the bid strategy). If this campaign has no value feed, broad match is likely leaking spend.
   - **Phrase match is the lead-gen workhorse** otherwise — the default for controlled intent capture here.
   - **Exact match** for tight control on core RBI terms.

3. **Decide on evidence**: does the account data support the doctrine or contradict it for this campaign? Where broad match runs without a value signal AND underperforms, recommend pulling it back to phrase. Where phrase carries conversions efficiently, leave it. Cite the actual CPA/conversion numbers behind every call — account evidence over doctrine.

Output: the match-type table, a per-match-type verdict, and specific keyword moves (with match types) for my approval before anything changes.`,
  },

  // ── Audit ──────────────────────────────────────────────
  {
    id: 'account-health',
    label: 'Account Health Check',
    icon: '🏥',
    category: 'audit',
    description: 'Full account audit across all campaigns',
    suggestedModel: 'opus',
    prompt: `Complete account health check:

1. **Campaign Overview**: Which campaigns are performing vs underperforming?
2. **Budget Pacing**: Are any campaigns overspending or underspending?
3. **Conversion Tracking**: Are all campaigns tracking conversions properly?
4. **Quality Scores**: Account-wide QS distribution — any systemic issues?
5. **Wasted Spend**: Total estimated waste across all campaigns
6. **Quick Wins**: Top 5 changes that would improve the account immediately
7. **Strategic Issues**: Any structural problems (duplicate keywords, cannibalization, etc.)

Prioritize recommendations by impact.`,
  },
  {
    id: 'competitor-analysis',
    label: 'Competitive Analysis',
    icon: '🎯',
    category: 'audit',
    needsCampaign: true,
    description: 'Analyze competitive position from available data',
    suggestedModel: 'opus',
    prompt: `Competitive analysis for "{campaign}":

Based on available data (impression share, search terms, auction insights if accessible):
1. What's our impression share? How much are we losing to rank vs budget?
2. Are competitors appearing on our brand terms?
3. Are there search terms suggesting competitor awareness we should address?
4. Recommend defensive strategies (brand campaigns, competitor conquesting)
5. Suggest keyword gaps based on search term patterns`,
  },

  // ── Research ───────────────────────────────────────────
  {
    id: 'keyword-research',
    label: 'Keyword Research',
    icon: '🔎',
    category: 'optimize',
    needsCampaign: true,
    description: 'Use Google Keyword Planner to discover new keyword opportunities',
    suggestedModel: 'opus',
    prompt: `Keyword research for "{campaign}" using the Google Ads Keyword Planner MCP tools:

1. First, analyze the existing keywords in this campaign — what themes and intent levels are covered?
2. Use the keyword_plan_idea tools to generate new keyword ideas:
   - Generate ideas FROM the top-performing existing keywords (keyword_plan_idea__generate_keyword_ideas_from_keywords)
   - Generate ideas FROM the campaign's landing page URL (keyword_plan_idea__generate_keyword_ideas_from_url)
3. For each suggested keyword, show: search volume, competition level, suggested bid
4. Categorize the results:
   - **High Intent** (ready to convert): bottom-of-funnel terms
   - **Mid Intent** (researching): comparison and informational terms
   - **Low Intent / Broad** (awareness): top-of-funnel terms
5. Cross-reference with existing keywords — flag duplicates and gaps
6. Recommend which keywords to add, with match types and which ad group they belong in

Present the results as a prioritized list. I'll approve before you add any.`,
  },
  {
    id: 'keyword-expansion',
    label: 'Keyword Expansion from URL',
    icon: '🌐',
    category: 'optimize',
    description: 'Generate keyword ideas from a landing page URL',
    suggestedModel: 'sonnet',
    prompt: `Use the Google Ads Keyword Planner to generate keyword ideas from a landing page:

**Landing Page URL**: [PASTE YOUR URL HERE]
**Target Location**: [COUNTRY/REGION]
**Language**: [LANGUAGE]

Steps:
1. Use keyword_plan_idea__generate_keyword_ideas_from_url to analyze the page and extract keyword ideas
2. Also try keyword_plan_idea__generate_keyword_ideas_from_site for broader site-level ideas
3. Show results with: keyword text, avg monthly searches, competition, top-of-page bid (low/high)
4. Group by theme/intent
5. Recommend match types for each keyword (exact for high-intent, phrase for mid, broad for discovery)

Show the top 30 most relevant keywords.`,
  },
  {
    id: 'find-duplicate-ads',
    label: 'Find Duplicate Ads',
    icon: '🔄',
    category: 'audit',
    description: 'Detect duplicate or near-duplicate ads across ad groups',
    suggestedModel: 'opus',
    prompt: `Audit this account for duplicate and near-duplicate ads:

1. Use the MCP tools to pull all ads across all ad groups (ad_group_ad__list_ad_group_ads or GAQL query)
2. Compare RSA headlines and descriptions across ad groups and campaigns
3. Identify:
   - **Exact duplicates**: Same headlines AND descriptions in different ad groups
   - **Near-duplicates**: >70% overlap in headlines or descriptions
   - **Cannibalization**: Different ads in same campaign competing for the same terms
4. For each duplicate found, show:
   - Which campaigns/ad groups contain the duplicate
   - Performance comparison (CTR, conversions) if available
   - Recommendation: which to keep, which to pause or differentiate
5. Estimate wasted budget from ad cannibalization

Flag any ad groups with only 1 RSA (Google recommends at least 2-3 for testing).`,
  },
  {
    id: 'google-recommendations',
    label: 'Review Google Recommendations',
    icon: '💡',
    category: 'audit',
    description: 'Fetch and evaluate Google Ads optimization recommendations',
    suggestedModel: 'sonnet',
    prompt: `Use the recommendation MCP tools to review Google's optimization suggestions:

1. Fetch all recommendations using recommendation__get_recommendations
2. Categorize them by type (keywords, bids, ads, targeting, etc.)
3. For each recommendation, evaluate:
   - **Accept**: clearly beneficial, explain why
   - **Review**: potentially good but needs context, explain trade-offs
   - **Reject**: not aligned with goals, explain why
4. Show estimated impact for each (if available)

Do NOT auto-apply any recommendations. Present them for my review first.
For the ones I approve, use recommendation__apply_recommendation to apply them.

STANDING ACCOUNT RULES (non-negotiable):
- This is a **read-only pass** by default — apply NOTHING without campaign-specific evidence that it helps THIS campaign's goals.
- **Verify the Recommendations → Auto-apply toggles are ALL OFF** every single time you run this. On 2026-07-25 auto-apply silently changed this account, so confirm every auto-apply category is disabled and report that state BEFORE evaluating anything else.`,
  },
  {
    id: 'ai-max-readiness',
    label: 'AI Max Readiness Audit',
    icon: '🤖',
    category: 'audit',
    description: 'Flag Sept 2026 AI Max auto-upgrade exposure and set compliance fences before opting in',
    suggestedModel: 'opus',
    prompt: `Account-wide AI Max readiness audit. AI Max for Search has been GA since April 2026, and from **Sept 2026 any campaign already using automatically-created assets OR campaign-level broad match auto-upgrades to AI Max**. Get ahead of it, don't get flipped blind.

1. **Inventory exposure**: using MCP/GAQL, list every Search campaign and flag which have:
   - Automatically-created assets ON (asset auto-creation setting)
   - Campaign-level broad match keywords
   These are the campaigns that auto-upgrade in Sept 2026. Output a table: Campaign | Auto-created assets | Broad match present | Sept-2026 auto-upgrade exposure (Y/N).

2. **Model the opt-in decision** for this lead-gen account at ~$60 CPA. Google's own aggregate claims AI Max delivers ~7% more conversions/value at similar CPA — treat that as UNVERIFIED for lead-gen (it is not a lead-gen-specific figure). Weigh the real risks: Final URL expansion sending traffic to the wrong page (a blog post instead of the consult LP) and text customization rewriting claims, against the reach upside. Judge on CRM-scored lead quality, not Google's conversion count.

3. **REQUIRED fences before ANY opt-in** — do NOT recommend opting a campaign in until all three are in place:
   - **AI Brief / brand guidelines set**: matching + messaging guidelines that lock compliance-critical claims in plain language.
   - **URL exclusions / Final URL Expansion disclaimers**: so traffic cannot land on off-brief pages and required legal text always renders.
   - **Immigration-policy constraint**: NO citizenship or guaranteed-approval claims. Any AI-rewritten headline/description MUST be reviewed for policy before it can serve — this account has real disapproval history, and under the July 2026 TOS auto-generated text is legally your liability.

Output: the exposure table, a per-campaign recommendation (opt in now / fence first / stay out), and the exact AI Brief guidelines to set. Recommend NOTHING be flipped without my approval.`,
  },
  {
    id: 'measurement-pipeline-health',
    label: 'Measurement Pipeline Health',
    icon: '🩺',
    category: 'audit',
    description: 'Verify conversions, consent-mode signals, and the June 2026 Data Manager API migration',
    suggestedModel: 'opus',
    prompt: `Account-wide measurement pipeline health check. Since 2026-06-15 the measurement plumbing changed materially — verify nothing has silently broken.

1. **Conversion actions recording vs expected**: list every conversion action (name, ID, category, counting, status) via a GAQL query on \`conversion_action\`. For each primary action, compare recent conversion volume to its baseline and flag any that have gone quiet — a silent stop = starved Smart Bidding.

2. **Consent Mode / ad_storage**: since 2026-06-15, \`ad_storage\` is the SINGLE Consent Mode control for Ads↔Analytics data flow (Google Signals no longer governs ad-data sharing). Confirm \`ad_storage\` + \`ad_user_data\` signals fire (Enhanced Conversions for Leads needs \`ad_user_data\`). Re-check remarketing audience sizes for post-June shrinkage.

3. **Enhanced Conversions status**: confirm Enhanced Conversions (web + leads are now a single on/off switch) is enabled and healthy.

4. **Offline import path**: NOTE — as of 2026-06-15, offline conversion import + Enhanced Conversions for Leads are live behind the **Data Manager API** and are BLOCKED in the Google Ads API. This account is GCLID-based offline import — the exact pipeline that moved. Any planned CRM offline upload MUST target the Data Manager API, not the Ads API. Confirm current uploads still land after 2026-06-15; if the path still points at the old Ads-API endpoint, that is a P0.

Output: a status line per check (OK / degraded / broken), the specific fix for anything broken, and which item is most urgent.`,
  },
  {
    id: 'deprecation-calendar-check',
    label: 'Deprecation Calendar Check',
    icon: '📅',
    category: 'audit',
    description: 'Scan the account against the Google Ads sunset calendar and assign actions with dates',
    suggestedModel: 'sonnet',
    prompt: `Scan this account against the current Google Ads deprecation / sunset calendar and produce an owned action list.

**Verify the current dates first** — these move; do a quick web search to confirm before you rely on them. As of the Aug 2026 digest the UPCOMING ones are:
- **Sept 2026** — auto-upgrade to AI Max for campaigns using auto-created assets + campaign-level broad match
- **Feb 2027** — Dynamic Search Ads sunset + DSA auto-upgrade to AI Max
(Already passed, for context: Google Ads API v20 retired 2026-06-10; measurement/consent changes 2026-06-15; automation-authority TOS 2026-07-01.)

For each UPCOMING item:
1. Check whether this account is actually affected (does it have auto-created assets / campaign-level broad match / DSA campaigns?).
2. State the required action.
3. Assign an owner (me / GTM Specialist / seo-supreme-agent) and a do-by date working back from the sunset.

Output a table: Date | Event | Affected here? | Required action | Owner | Do-by. Skip items the account is not exposed to and say so explicitly.`,
  },

  // ── Conversion & GTM ───────────────────────────────────
  {
    id: 'setup-conversion-tracking',
    label: 'Setup Conversion Tracking',
    icon: '🎯',
    category: 'create',
    needsCampaign: true,
    description: 'Create conversion action + GTM tag end-to-end',
    suggestedModel: 'opus',
    prompt: `Set up full conversion tracking for "{campaign}":

1. **Create the conversion action** in Google Ads using MCP tools:
   - Name: [DESCRIBE THE CONVERSION, e.g. "Lead Form Submission", "Purchase", "Phone Call"]
   - Category: Lead / Purchase / Sign-up / Other
   - Counting: One per click (leads) or Every (e-commerce)
   - Value: [AMOUNT or "no value"]

2. **Set up the GTM tag** (if GTM MCP is available):
   - Find the correct GTM container for this site
   - Create a trigger (e.g., Page View on thank-you page, or Form Submit event)
   - Create a Google Ads Conversion Tracking tag with the conversion ID + label
   - Publish the container version

3. **If GTM MCP is not available**, provide:
   - The conversion ID and label from step 1
   - Step-by-step instructions for manual GTM setup
   - The Global Site Tag and Event Snippet code

4. **Verify** the tag is firing correctly (if Chrome browser tools are available)

Landing page / thank-you page URL: [YOUR URL HERE]`,
  },
  {
    id: 'gtm-tag-audit',
    label: 'GTM Container Audit',
    icon: '🏷️',
    category: 'audit',
    description: 'Audit GTM tags, triggers, and variables for issues',
    suggestedModel: 'opus',
    prompt: `Audit the Google Tag Manager container for this account:

Using GTM MCP tools (or browser if not available):
1. List all containers and find the one for this website
2. List all tags, triggers, and variables in the active workspace
3. Check for:
   - **Missing conversion tags**: Are all Google Ads conversion actions tracked?
   - **Duplicate tags**: Same conversion ID used in multiple tags?
   - **Broken triggers**: Triggers referencing pages/events that may not exist
   - **Unused variables**: Variables defined but not referenced by any tag
   - **Missing remarketing tag**: Is there a Google Ads remarketing tag?
   - **GA4 setup**: Is Google Analytics 4 configured properly?
4. Check the most recent published version vs workspace — are there unpublished changes?
5. Provide recommendations with priority (critical / important / nice-to-have)`,
  },
  {
    id: 'conversion-tracking-audit',
    label: 'Conversion Tracking Audit',
    icon: '🔬',
    category: 'audit',
    description: 'End-to-end audit: Google Ads conversions + GTM container + live firing check',
    suggestedModel: 'opus',
    prompt: `Run a 4-perspective conversion tracking audit using the BMad party team approach. Pause between each perspective so I can review before you continue.

**Pre-requisites I need from you:**
- GTM Container ID: [e.g. GTM-NH2TST65]
- Container name: [e.g. "mercan backup"]
- Landing page URL: [e.g. https://goldenvisas.mercan.com]

---

**🎯 PERSPECTIVE 1 — PPC STRATEGIST (Google Ads MCP)**

Use Google Ads MCP tools to answer:
1. List ALL conversion actions in the account (name, ID, label, counting method, category, status) via a GAQL query on \`conversion_action\`
2. Which campaigns currently count toward each conversion action? (query \`campaign_conversion_goal\`)
3. For my selected campaign, which conversion actions does it track?
4. Flag any duplicate or legacy conversion actions that should be removed

Output as a table: Action Name | ID | Label | Counting | Campaigns Using It | Status

**PAUSE** — ask me if discovery looks right before continuing.

---

**🏗️ PERSPECTIVE 2 — TAG ARCHITECT (Chrome MCP → GTM)**

Using Chrome browser MCP tools:
1. Navigate to https://tagmanager.google.com/
2. Tell me to log in and wait for my "done" confirmation
3. Open the container I specified above
4. List ALL tags in the current workspace — name, type, firing triggers, conversion ID/label if Google Ads Conversion tag
5. List ALL triggers — name, event type, filter conditions
6. Check if there's a Conversion Linker tag
7. Note any unpublished changes in the workspace vs published version

Output current state as: Tag Name → Trigger → Fires When → Conversion ID/Label

**PAUSE** — show me the audit before moving to Perspective 3.

---

**🔍 PERSPECTIVE 3 — QA VALIDATOR (Chrome MCP → live site)**

Using Chrome browser MCP tools:
1. Navigate to my landing page URL
2. Use list_network_requests to capture network activity
3. Filter for requests to \`googleadservices.com/pagead/conversion\` — these are conversion hits
4. Parse the \`send_to\` label from each request URL
5. Report which labels fired on PAGE LOAD (before any interaction)
6. Tell me to trigger the form (or a safe interaction) and capture network activity again
7. Report which labels fire on FORM SUBMIT

**Red flags to explicitly report:**
- Label firing on page load that shouldn't (inflates conversions)
- Missing label on form submit (leads not tracked)
- Duplicate hits (double counting)

**PAUSE** — review with me before making recommendations.

---

**👨‍💻 PERSPECTIVE 4 — IMPLEMENTATION DEVELOPER (recommendation)**

Based on findings from Perspectives 1-3, recommend ONE of these strategies for tracking multiple campaigns separately (DO NOT execute yet):

**Strategy A — Dynamic labels via Lookup Table** (for 5+ campaigns)
- One Google Ads Conversion tag + GTM Lookup Table variable
- Maps campaign source → conversion label

**Strategy B — Multiple stacked tags** (simplest, for 2-4 campaigns)
- One conversion tag per campaign region
- All fire on the same Form Submit trigger

**Strategy C — UTM-triggered tags** (cleanest attribution)
- Trigger conditions filter by utm_campaign parameter
- One tag per campaign, fires only when URL matches

For your chosen strategy, provide:
- Exact tag names
- Trigger conditions
- Variables needed
- Order of operations to implement in GTM

I'll approve the strategy before you make any GTM changes.`,
  },
  {
    id: 'auto-install-tracking',
    label: 'Auto-Install All Tracking',
    icon: '⚡',
    category: 'create',
    description: 'Scan landing page and auto-install missing Clarity, GA4, and conversion tags via GTM',
    suggestedModel: 'opus',
    prompt: `As the GTM Specialist, scan the landing page for this campaign and auto-install any missing tracking:

1. **Open the landing page** using Chrome browser tools
2. **Check network requests** for existing tracking:
   - Microsoft Clarity script loaded?
   - Google Tag Manager container loaded?
   - Google Ads conversion tag (gtag) loaded?
   - GA4 measurement ID present?

3. **For each MISSING tracker, install it via GTM MCP:**

   If Clarity is missing:
   → Create Custom HTML tag with the Clarity tracking script
   → Trigger: All Pages
   → Publish

   If GA4 is missing:
   → Create GA4 Configuration tag
   → Trigger: All Pages
   → Publish

   If Google Ads conversion tag is missing:
   → Create Google Ads Conversion Tracking tag (use existing conversion action)
   → Create appropriate trigger (thank-you page or form submit)
   → Publish

4. **Verify** each installed tag is firing by checking network requests after publish

5. **Report** what was installed, what was already present, and what needs manual attention

Landing page URL: [THE CAMPAIGN'S LANDING PAGE]
GTM Container: GTM-K6864NBH`,
  },
  {
    id: 'landing-page-audit',
    label: 'Landing Page Audit',
    icon: '🔍',
    category: 'audit',
    needsCampaign: true,
    description: 'Audit landing page for ad relevance and conversion setup',
    suggestedModel: 'opus',
    prompt: `Audit the landing page for "{campaign}":

Using browser tools (if available) + campaign data:
1. Navigate to the campaign's landing page URL
2. Check:
   - **Tag verification**: Is the Google Ads tag / GTM container present?
   - **Conversion tracking**: Is the conversion event firing on form submit / CTA?
   - **Page speed**: Are there obvious heavy resources?
   - **Mobile responsiveness**: Does the page render well?
   - **Ad-to-page relevance**: Do the ad headlines match the page content?
   - **CTA clarity**: Is the call-to-action obvious and above the fold?
   - **Form fields**: Too many fields reducing conversion rate?
3. Compare to Quality Score factors: landing page experience, ad relevance
4. Provide specific recommendations to improve conversion rate

If browser tools are not available, analyze based on the campaign's landing page URL and keywords.`,
  },
  {
    id: 'cro-full-audit',
    label: 'Full CRO Audit (12-point)',
    icon: '🔬',
    category: 'audit',
    needsCampaign: true,
    description: 'Comprehensive 12-point CRO audit with competitor analysis and ad strength scoring',
    suggestedModel: 'opus',
    prompt: `As the CRO Specialist, run a comprehensive 12-point CRO audit for "{campaign}":

WORKFLOW:
1. Find the landing page URL from the campaign's ads (final_urls)
2. Run the FULL 12-step analysis using Chrome MCP browser tools:
   - Performance audit (Core Web Vitals, page speed)
   - DOM element analysis (CTAs, forms, headings, trust signals)
   - Visual analysis (desktop + mobile screenshots)
   - Copy quality scoring (value prop, benefit-driven)
   - Trust signal detection (reviews, badges, certifications)
   - Conversion element audit (form fields, CTA placement)
   - Ad-to-page alignment check
   - Conversion tracking verification (network requests for GTM/GA4/Ads)
   - Mobile UX (touch targets, responsive design)
   - Competitor research (find 2-3 competitors, analyze their pages)
3. Score against industry benchmarks
4. Generate 5-8 A/B test ideas with expected impact
5. Calculate CRO Score (0-100)
6. Analyze ad strength and suggest improvements to reach "Excellent" rating

CRITICAL: Output structured data wrapped in <!-- STRUCTURED_DATA_START --> and <!-- STRUCTURED_DATA_END --> markers so the Landing Page tab can display results.

Save the full analysis to campaign memory after completion.`,
  },
  {
    id: 'asset-diversity-review',
    label: 'Asset Diversity Review',
    icon: '🎨',
    category: 'optimize',
    needsCampaign: true,
    description: 'Fill genuine RSA coverage gaps — without chasing the Ad Strength label',
    suggestedModel: 'opus',
    prompt: `Asset diversity review for "{campaign}". The goal is genuine message coverage, NOT the Ad Strength meter.

**Read this first — do NOT chase "Excellent":** Optmyzr's 1M-ad study found ads rated *Average* often outperformed *Excellent* on CPA/ROAS, and shorter headlines frequently won. Ad Strength is a guide, not a KPI. So: never pad a headline to hit a character count, never add near-duplicate assets just to fill slots, and never sacrifice a proven short headline to lift the label.

WORKFLOW:
1. Pull every RSA in the campaign — list headlines and descriptions per ad group.
2. Find the GENUINE gaps (not label gaps):
   - **Empty slots**: ad groups with fewer than 2-3 RSAs, or RSAs leaving distinct-angle capacity unused
   - **Missing angles**: map current headlines to value props (eligibility, timeline, process simplicity, trust/track-record, cost clarity) and show which angles are uncovered
   - **Near-duplicates**: headlines that say the same thing — flag to merge/differentiate (they dilute testing), not to keep for volume
3. Cross-check against the landing page value prop so new assets match the page — and stay compliant (NO citizenship or guaranteed-approval claims).
4. Propose replacement/additional headlines and descriptions ONLY where they close a real coverage gap or land a genuinely stronger angle. For each, state which gap it fills.

Output: current coverage map, gaps found, and proposed assets with the gap each one closes. Show before/after for my approval. Do NOT report an Ad Strength target as the objective. Save findings to campaign memory.`,
  },
  {
    id: 'competitor-landing-pages',
    label: 'Competitor Landing Page Spy',
    icon: '🕵️',
    category: 'audit',
    needsCampaign: true,
    description: 'Analyze competitor landing pages and extract winning patterns',
    suggestedModel: 'opus',
    prompt: `As the CRO Specialist, analyze competitor landing pages for "{campaign}":

WORKFLOW:
1. Identify 3 main competitors in this niche (use Chrome to search Google for top results on main keywords)
2. For each competitor: open in new tab, screenshot, analyze CTAs/forms/copy/trust signals
3. Build comparison table: us vs each competitor across key dimensions
4. Identify patterns and winning elements
5. Generate 5-10 specific ideas to steal/adapt with priority levels
6. Save findings to campaign memory as cro_specialist notes

Output structured data so the Landing Page tab can display competitor insights.`,
  },

  // ── Report ─────────────────────────────────────────────
  {
    id: 'weekly-report',
    label: 'Weekly Performance Report',
    icon: '📋',
    category: 'report',
    description: 'Generate a weekly summary for client/team',
    suggestedModel: 'sonnet',
    prompt: `Generate a weekly performance report:

**Period**: Last 7 days vs prior 7 days

For each active campaign, include:
- Spend, Clicks, Conversions, CPA (with week-over-week change)
- Key highlights (what improved, what declined)
- Actions taken this week (from change log if available)

**Summary section**:
- Total account spend and conversions
- Best performing campaign
- Campaign needing attention
- Top 3 recommendations for next week

Format as a clean, client-ready report in markdown.`,
  },
  {
    id: 'monthly-summary',
    label: 'Monthly Summary',
    icon: '📈',
    category: 'report',
    description: 'End-of-month performance summary with trends',
    suggestedModel: 'opus',
    prompt: `Monthly performance summary (last 30 days):

1. **Account Overview**: Total spend, conversions, CPA, ROAS across all campaigns
2. **Campaign Rankings**: Best to worst by CPA and conversion volume
3. **Trend Analysis**: Is the account improving or declining? Key inflection points
4. **Budget Utilization**: Planned vs actual spend per campaign
5. **Key Wins**: What worked well this month
6. **Issues Identified**: What needs fixing
7. **Next Month Plan**: Strategic recommendations and priority actions

Format as a professional report.`,
  },
  {
    id: 'benchmark-reality-check',
    label: 'Benchmark Reality Check',
    icon: '📐',
    category: 'report',
    description: 'Compare account CPC/CPA against the honest vertical benchmark (Legal), not retail',
    suggestedModel: 'sonnet',
    prompt: `Benchmark reality check across the account. Compare each campaign's CPC and CPA against the honest vertical comp — NOT the cross-industry average.

**The comp for immigration / RBI lead-gen is Legal Services** (2026 reports): **~$6.75 CPC / ~$127 CPA**. Context: cross-industry CPC is up **+12% YoY**, so flat budgets buy ~12% fewer clicks than a year ago — bake that into the read.

1. Pull each campaign's current CPC and CPA (last 30 days).
2. For each, give a verdict vs the Legal benchmark: **competitive** (at/below ~$6.75 CPC / ~$127 CPA), **watch**, or **expensive for the vertical** (well above).
3. **Important reframe**: this is a ~$300K-product business — a defensible CPA target for a high-ticket RBI lead differs from the vertical median. A $200-400 CPA on a genuinely qualified consult can be fine; a $127 CPA on junk leads is not. So pair each verdict with a note on whether lead quality justifies the cost, and flag high-CPA + low-quality campaigns as the real problems (VBB candidates), not high-CPA-but-qualified ones.

Output a table: Campaign | CPC | CPA | vs Legal benchmark | Verdict | Quality note. Keep the +12% CPC inflation context in the summary. Client-ready markdown.`,
  },
];

export const TEMPLATE_CATEGORIES = [
  { id: 'create', label: 'Create', icon: '🚀' },
  { id: 'analyze', label: 'Analyze', icon: '📊' },
  { id: 'optimize', label: 'Optimize', icon: '⚡' },
  { id: 'audit', label: 'Audit', icon: '🏥' },
  { id: 'report', label: 'Report', icon: '📋' },
] as const;

export default templates;
