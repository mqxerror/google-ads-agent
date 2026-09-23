# Google Ads Trends & Reports — Aug 2026 Digest (Lead-Gen Lens)

> **Compiled:** 2026-08-06 · **Window:** prioritizing last ~90 days (May–Aug 2026), with a few older studies noted where they are the primary data.
> **Purpose:** seed new chat prompt templates in google-ads-agent. Every claim is cited with URL + publish date. `UNVERIFIED` marks anything not confirmed to a primary/authoritative source.
> **Account reality this is written for:** immigration / residency-by-investment lead-gen (Panama QIP, Greece GV, etc.), Search + Demand Gen live, PMax planned. High-ticket, long sales cycle. US + Middle-East geos. Budgets **$25–400/day**, observed **CPAs $57–625**, **GCLID-based** offline lead tracking, **no ecommerce**. The relevant benchmark comps are **Legal Services** and **Finance/Business Services**, not retail.

---

## 1. Top-10 Executive Digest (one line each)

1. **AI Max for Search is now the default trajectory, not an opt-in.** GA since April 2026; campaigns using auto-created assets + campaign-level broad match **auto-upgrade to AI Max starting Sept 2026**. — [Search Engine Land / groas.ai, 2026](https://groas.ai/post/google-ads-updates-2026-every-major-change-campaign-impact)
2. **Dynamic Search Ads sunset was pushed from Sept 2026 → Feb 2027** (announced 2026-06-11); DSA creation was restored on 2026-06-15. — [blog.google, 2026-06-11](https://blog.google/products/ads-commerce/dsa-upgrade-to-ai-max-2026/)
3. **"Business Agent for Leads"** — a Gemini chat unit that replaces the static lead form, answers prospect questions from your site copy, then submits a pre-filled form on real intent. Launched at GML **2026-05-20**, in beta. This is the single most lead-gen-relevant launch of the year. — [Search Engine Land, 2026-05-20](https://searchengineland.com/google-tests-new-conversational-ad-formats-in-ai-mode-and-search-478115)
4. **Measurement plumbing changes on 2026-06-15:** `ad_storage` becomes the single Consent Mode control for Ads↔Analytics data; **offline conversion import + Enhanced Conversions for Leads migrate to the Data Manager API and are blocked in the Google Ads API.** — [clicksambo, 2026](https://clicksambo.com/blog-detail/google-ads-offline-conversion-guide-2026), [uniconsent, 2026](https://www.uniconsent.com/blog/google-ads-consent-mode-change-2026)
5. **Search CPC inflation is accelerating:** cross-industry avg **$2.96 in Q1 2026, +12% YoY**; **Legal Services $6.75 CPC / $127 CPA**. Steepest annual CPC rise since 2021. — [digitalapplied, 2026](https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry)
6. **AI Overviews' CTR damage is stabilizing, not worsening:** AIO-present paid CTR *rose* 14.64%→16.21% (Jan 2025→Feb 2026) while non-AIO paid CTR *fell* 25.98%→21.85% — the gap is closing. **Being cited in the AIO lifts paid CTR ~91%.** — [Seer via ideava/pixis, 2026](https://ideava.com/insights/ai-overviews-ctr-decline/)
7. **Google Ads TOS (effective 2026-07-01) makes automation the default authority** — Google may auto-generate/select targets, ads, destinations; **the advertiser is legally responsible for reviewing every AI-generated asset.** — [Search Engine Land, 2026](https://searchengineland.com/google-ads-updates-terms-of-service-ahead-of-july-2026-rollout-479255)
8. **PMax finally has real steering for lead-gen:** campaign + account-level negative keywords (10,000 cap), channel-level reporting, and **first-party audience exclusions** (exclude converters to chase new leads). — [business.google.com, 2026](https://business.google.com/us/accelerate/resources/articles/new-performance-max-steering-and-reporting-updates-coming-in-2026/)
9. **Match-type evidence conflicts — and it matters for lead-gen.** Optmyzr's 30k-account Feb-2026 study finds **phrase match best for lead-gen** (broad "loses its footing" without conversion-value signals); Search Engine Land argues to **drop phrase match**. Resolve empirically per account. — [Optmyzr, 2026](https://www.optmyzr.com/blog/google-ads-match-type-performance/) vs [Search Engine Land, 2026](https://searchengineland.com/google-ads-tactics-to-drop-464123)
10. **Value-based bidding is the lead-gen upgrade path — but it has a volume floor.** Needs a real differentiated value signal + ~30–50 conv/mo; feed lead-stage values via GCLID offline import. Below the floor it "fails." — [Optmyzr, 2026](https://www.optmyzr.com/blog/value-based-bidding-guide/), [Elevarus, 2026](https://elevarus.com/value-based-bidding-lead-generation-2026/)

---

## 2. Per-Trend Detail (what changed → why lead-gen cares → the check/action)

### TREND 1 — AI Max for Search: GA + auto-upgrade
**What changed.** AI Max for Search reached **general availability in April 2026**. It bundles search-term matching (campaign-level broad-match-like), automated text customization, and Final URL expansion. **From Sept 2026, campaigns already using automatically-created assets and campaign-level broad match auto-upgrade to AI Max**; DSA-based auto-upgrade was moved to **Feb 2027**. Google's own claim: AI Max delivers **~7% more conversions / conversion value at similar CPA/ROAS** when the full feature suite is on vs. search-term matching alone. New controls shipped: **AI Brief** (messaging / matching / audience guidelines in plain language — e.g. "never mention prices"), and **Final URL Expansion with text disclaimers** (forces compliance text to always render). — [groas.ai, 2026](https://groas.ai/post/google-ads-updates-2026-every-major-change-campaign-impact); [blog.google AI Max features, 2026](https://blog.google/products/ads-commerce/ai-max-new-features/)
**Why lead-gen cares.** Final URL expansion can send traffic to pages you didn't intend (a blog post instead of the RBI consult LP) and text customization can rewrite claims — dangerous for a regulated immigration niche where every claim must be accurate (recall the Panama "one visit every 2 years" fact). The +7% is Google's own aggregate, not lead-gen-specific → treat as **UNVERIFIED for lead-gen**.
**Action.** Don't wait to be auto-upgraded blind. (1) Inventory which campaigns use auto-created assets + campaign broad match — those flip in Sept 2026. (2) Before opting in, set **AI Brief matching guidelines** to fence the auto-migration and **messaging guidelines** to lock compliance-critical claims. (3) Use **Final URL Expansion text disclaimers** to force required legal text. (4) Run a **one-click AI Max experiment** and judge on *lead quality* (CRM-scored via GCLID), not on Google's conversion count.

### TREND 2 — Business Agent for Leads (the year's biggest lead-gen launch)
**What changed.** Announced at GML **2026-05-20**, currently **in beta**. Clicking the ad slides open a **Gemini chat window inside the Search results page**; the agent answers pricing / service / availability questions **grounded exclusively in the advertiser's website copy** (Google's stated anti-hallucination guardrail), then submits a **pre-filled lead form once the conversation signals real intent.** — [Search Engine Land, 2026-05-20](https://searchengineland.com/google-tests-new-conversational-ad-formats-in-ai-mode-and-search-478115); [blog.google Search ads, 2026](https://blog.google/products/ads-commerce/google-marketing-live-search-ads/)
**Why lead-gen cares.** This is purpose-built for high-consideration, question-heavy purchases — exactly RBI/immigration. It could pre-qualify (visa eligibility, budget, timeline) before a form ever submits, raising lead quality. Risk: the agent speaks *as your brand* from your site copy, so **site accuracy becomes ad accuracy** — outdated program facts become the agent's answers.
**Action.** (1) Check beta eligibility for the account. (2) **Audit the LP/site copy the agent would ground on** — every program fact (stay requirements, minimums, timelines) must be current before enabling. (3) Plan CRM capture of the conversation transcript as a lead-quality signal.

### TREND 3 — AI Overviews / AI Mode impact on paid search
**What changed.** Two data waves. Older Seer study (Jun 2024–Sep 2025, 3,119 terms, 42 orgs, 25.1M organic + 1.1M paid impressions): paid CTR on AIO queries fell **19.70%→6.34%**. But **2026 data reverses the panic**: AIO-present paid CTR *climbed* **14.64% (Jan 2025) → 16.21% (Feb 2026)**, while non-AIO paid CTR *fell* **25.98%→21.85%** — AIO CTR is still lower but no longer collapsing. **Brand cited in the AIO → paid CTR ~91% higher** (Seer, Q3 2025). Adthena (late Dec 2025–Jan 2026, 6 industries, 5M+ ads): AIO presence raises CPC and depresses CTR most in Telecom/Tech; **Financial Services shows "modest CPC increases that mask significant profitability impacts in already high-CPC sectors."** — [ideava, 2026](https://ideava.com/insights/ai-overviews-ctr-decline/); [Search Engine Land / Adthena, 2026](https://searchengineland.com/what-industry-data-reveals-about-the-impact-of-googles-ai-overviews-on-paid-search-470019)
**Why lead-gen cares.** Immigration queries are informational-heavy ("Panama residency requirements", "Greece golden visa cost") — exactly where AIO appears most, compressing paid CTR and inflating CPC. But the citation effect means **organic/GEO visibility now protects paid performance.**
**Action.** (1) Segment performance by whether the query triggers an AIO (device-split — mobile displacement is worse). (2) Cross-lane: ask **seo-supreme-agent** whether Mercan is *cited* in AIOs for target queries — a citation is worth ~91% paid CTR. (3) Expect informational-term CPC creep; weight budget toward higher-intent/bottom-funnel terms.

### TREND 4 — Measurement & consent plumbing (hard deadlines, June 2026)
**What changed.** On **2026-06-15**: (a) `ad_storage` becomes the **single Consent Mode control** for data flow between Analytics and Ads; **Google Signals loses its authority over ad data sharing** (Analytics-only now) — this can shrink remarketing lists; (b) **offline conversion import + Enhanced Conversions for Leads uploads migrate to the Data Manager API and are blocked in the Google Ads API**; (c) Enhanced Conversions for web + leads combine into a **single on/off switch**. Separately, **Google Ads API v20 retired 2026-06-10**; **API v25** shipped (July 2026) with retention goals + new objective management. For EEA advertisers, **Consent Mode v2 is mandatory** as of 2026-06-15. — [uniconsent, 2026](https://www.uniconsent.com/blog/google-ads-consent-mode-change-2026); [clicksambo, 2026](https://clicksambo.com/blog-detail/google-ads-offline-conversion-guide-2026); [Search Engine Land API news, 2026](https://searchengineland.com/library/platforms/google/google-ads)
**Why lead-gen cares.** This account is **GCLID-based offline import** — the exact pipeline being migrated. If the upload path still points at the old Google Ads API endpoint, **offline conversions silently stop**, starving Smart Bidding. Middle-East geos are non-EEA but any EU traffic makes CMv2 relevant.
**Action.** (1) Confirm the offline-import / EC-for-Leads pipeline uses the **Data Manager API** (not the deprecated Ads-API path) — verify uploads still land after 2026-06-15. (2) Confirm `ad_storage` + `ad_user_data` consent signals fire (EC for Leads needs `ad_user_data`). (3) Re-check remarketing audience sizes for post-June shrinkage.

### TREND 5 — CPC inflation & the benchmark reset
**What changed.** Q1 2026 cross-industry: **CPC $2.96 (+12% YoY)**, CTR 3.52%, CVR 4.40%, **CPA $53.89 (+6%)**. Legal Services **$6.75 CPC / $127.08 CPA (+8%)**; Finance & Banking $3.08 CPC / $65.25 CPA; Business Services $4.90 CPC / $106.29 CPA. Drivers cited: AI-era new advertiser demand, AIO shrinking organic CTR (pushing budget to paid), and PMax competing for high-value inventory. — [digitalapplied, 2026](https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry)
**Why lead-gen cares.** Legal is the closest public comp to immigration/RBI. **$127 CPA is well inside this account's observed $57–625 band**, so mid-band CPAs are competitive; the $400+ tail is the RBI premium, not waste. +12% CPC means flat budgets buy ~12% fewer clicks YoY — plan for it.
**Action.** Benchmark each campaign's CPC/CPA against the **Legal** row, not the cross-industry average. Where CPA runs above ~$150 with poor lead quality, that's where VBB (Trend 6) earns its keep.

### TREND 6 — Value-based bidding for lead gen
**What changed.** VBB assigns monetary weights to lead stages so Smart Bidding optimizes for *quality over volume*. Requirements: a **real differentiated value signal**, **enough volume** (tROAS needs ≥15 conv/30d; practitioners want **30–50/mo**), and a business that actually cares about lead quality. Google recommends feeding value data **4 weeks / 3 conversion cycles** before activating. Below the floor, VBB "fails." — [Optmyzr, 2026](https://www.optmyzr.com/blog/value-based-bidding-guide/); [Elevarus, 2026](https://elevarus.com/value-based-bidding-lead-generation-2026/)
**Why lead-gen cares.** RBI leads are wildly unequal (tire-kicker vs. $500k-QIP-ready). VBB via GCLID offline values is the mechanism to teach Google that difference — the single biggest quality lever available. But low-budget campaigns ($25/day) may never hit the volume floor.
**Action.** (1) Only run VBB on campaigns clearing ~30 conv/mo; keep thin campaigns on tCPA/Max-Conv. (2) Define a lead-value schema (MQL / SQL / consult-booked / deal) and push via offline import. (3) Wait the full 4-week seeding window before flipping to Max-Conv-Value / tROAS.

### TREND 7 — Automation-authority TOS (compliance duty shifted to you)
**What changed.** TOS effective **2026-07-01**, applied silently, no re-acceptance. Language shifts from "optional helpers" to **advertiser authorizes Google to format/select/generate targets, ads, destinations by default** — account posture is now **automated-unless-managed**. A **"continued obligation"** puts asset review (accuracy, policy, ownership) on the advertiser: **Google's AI writes it, you're liable for it.** — [Search Engine Land, 2026](https://searchengineland.com/google-ads-updates-terms-of-service-ahead-of-july-2026-rollout-479255); [digitalapplied, 2026](https://www.digitalapplied.com/blog/google-ads-terms-update-july-2026-ai-automation-authority)
**Why lead-gen cares.** In a regulated niche, an auto-generated headline making a false immigration claim is *your* legal exposure. Auto-created assets + Final URL expansion + Business Agent all now operate under this default authority.
**Action.** Institute a **standing auto-generated-asset review** — audit ACA headlines/descriptions and AI Max text customizations on a schedule; disable auto-created assets on any campaign where claim accuracy is legally sensitive until reviewed.

### TREND 8 — Performance Max steering for lead-gen
**What changed.** PMax now supports **campaign + account-level negative keywords (10,000 cap)**, **channel-level reporting** (Search/Shopping/Display/YouTube/Discover/Gmail/Maps), **search-terms reporting**, and **coming in 2026: first-party audience exclusions, budget/spend-projection reporting, full audience (age/gender) reporting, and network segmentation in placement reports.** — [business.google.com, 2026](https://business.google.com/us/accelerate/resources/articles/new-performance-max-steering-and-reporting-updates-coming-in-2026/); [groas.com negative-keyword strategy, 2026](https://www.groas.com/post/google-ads-negative-keyword-strategy-2026-campaign-level-ai-max-pmax-industry-lists)
**Why lead-gen cares.** PMax was historically a lead-quality black box. Negative keywords + channel reporting + **first-party exclusions (drop existing converters → chase net-new leads)** finally make PMax defensible for lead-gen. Channel reporting lets you correlate lead quality to the channel that sourced it.
**Action.** (1) Before launching planned PMax, pre-load a **negative-keyword list** (junk intent, jobs/DIY/free seekers) at campaign level. (2) Upload a **converter list as a first-party audience exclusion**. (3) Review channel-level reporting weekly against CRM lead quality; if Display/Gmail source junk, sculpt away.

### TREND 9 — Match-type & keyword strategy (evidence conflict — resolve per account)
**What changed.** Optmyzr (30,000 accounts, Feb 2026): exact match leads on efficiency; **phrase match "dominates" lead-gen on spend + conversion share; broad match "loses its footing" in lead-gen without conversion-value data**; 86% Smart Bidding adoption; exact-match spend share down 9.5% since 2022. Search Engine Land counters: **drop phrase match** (too limited to scale, too imprecise to control) in favor of exact-for-control + broad+Smart-Bidding-for-intent. — [Optmyzr, 2026](https://www.optmyzr.com/blog/google-ads-match-type-performance/); [Search Engine Land, 2026](https://searchengineland.com/google-ads-tactics-to-drop-464123)
**Why lead-gen cares.** The two authorities directly disagree. Optmyzr's split is empirical *and lead-gen-segmented*, so it's the stronger signal here — but note broad match's weakness is precisely **missing conversion-value signals**, which VBB (Trend 6) supplies. So the real answer is conditional: broad match works *once you feed value data*.
**Action.** Don't blanket-adopt broad match. Run exact/phrase for control on core RBI terms; only expand to broad match on campaigns where **offline value data is already feeding Smart Bidding**. A/B by match type per campaign, judge on CRM-scored lead quality.

### TREND 10 — Conversion-signal hygiene (drop-list)
**What changed.** Search Engine Land's 2026 drop-list includes: **stop using GA4 imported events as your primary conversion** (the GA4 pixel lacks freshness for real-time Smart Bidding — use the native Google Ads tag; link GA4 for audiences/secondary reporting only); **stop letting PMax capture branded terms** (carve out a dedicated brand Search campaign); **stop over-pinning RSAs** chasing Ad Strength. — [Search Engine Land, 2026](https://searchengineland.com/google-ads-tactics-to-drop-464123)
**Why lead-gen cares.** Smart Bidding + VBB are only as good as the freshness of the conversion signal. GCLID form-submit via native tag (already this account's setup per memory) is the right primary; GA4-imported would slow the bidding loop.
**Action.** Confirm primary conversion = **native Google Ads form-submit tag** (not GA4 import). Ensure PMax (when live) doesn't cannibalize branded; keep a dedicated brand campaign. Don't over-pin RSAs — treat Ad Strength as a guide, not a KPI.

---

## 3. Data-Backed Benchmark Table (Q1 2026 unless noted)

| Metric / Segment | Value | YoY | Source (date) | Notes |
|---|---|---|---|---|
| **Cross-industry Search CPC** | $2.96 | +12% | [digitalapplied 2026](https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry) | Steepest CPC rise since 2021 |
| Cross-industry Search CTR | 3.52% | +0.13pp | same | |
| Cross-industry Search CVR | 4.40% | +0.16pp | same | |
| Cross-industry Search CPA | $53.89 | +6% | same | |
| **Legal Services CPC** | **$6.75** | +14% | same | Closest comp to immigration/RBI |
| **Legal Services CPA** | **$127.08** | +8% | same | Inside this account's $57–625 band |
| Legal Services CTR / CVR | 2.31% / 5.31% | — | same | |
| Finance & Banking CPC / CPA | $3.08 / $65.25 | +10% / +7% | same | |
| Business Services CPC / CPA | $4.90 / $106.29 | +10% / +8% | same | |
| B2B / SaaS CPC / CPA | $3.33 / $87.17 | +12% / +9% | same | Long-sales-cycle comp |
| Insurance CPC / CPA | $6.22 / $101.14 | +11% / +7% | same | High-CPC lead-gen comp |
| **Smart Bidding share of spend** | 78–86% | — | [digitalapplied](https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry) / [Optmyzr](https://www.optmyzr.com/blog/google-ads-match-type-performance/) | ~22% lower CPA vs manual (`UNVERIFIED` magnitude) |
| Quality Score 8–10 CPC advantage | −37% vs median | — | [digitalapplied](https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry) | `UNVERIFIED` — single secondary source |
| **AIO-present paid CTR** | 14.64%→16.21% | Jan'25→Feb'26 | [Seer via ideava 2026](https://ideava.com/insights/ai-overviews-ctr-decline/) | Recovering; still < non-AIO |
| Non-AIO paid CTR | 25.98%→21.85% | Jan'25→Feb'26 | same | Falling |
| Paid CTR lift when brand cited in AIO | +91% | Q3 2025 | [Seer](https://ideava.com/insights/ai-overviews-ctr-decline/) | Argues for GEO/organic citation |
| AIO paid CTR (older Seer) | 19.70%→6.34% | Jun'24→Sep'25 | [Seer study](https://ideava.com/insights/ai-overviews-ctr-decline/) | 3,119 terms, 42 orgs, 25.1M org + 1.1M paid impr |
| AI Max full-suite conversion lift | +7% conv / value at similar CPA | — | [groas.ai 2026](https://groas.ai/post/google-ads-updates-2026-every-major-change-campaign-impact) | Google's own aggregate; `UNVERIFIED` for lead-gen |
| Exact-match spend share change | −9.5% | 2022→2026 | [Optmyzr 2026](https://www.optmyzr.com/blog/google-ads-match-type-performance/) | Budget shifting to phrase/broad |

> **Benchmark caveat:** WordStream/LocaliQ + secondary aggregators (digitalapplied) are directional industry medians, not a controlled study; use them for orientation, not targets. Immigration/RBI is not a named vertical — Legal + Insurance + B2B are the honest proxies.

---

## 4. Deprecation & Deadline Calendar

| Date | Event | Must-do for this account |
|---|---|---|
| **2026-04 (done)** | AI Max for Search GA | Decide opt-in posture with AI Brief fences before auto-upgrade |
| **2026-06-10 (done)** | Google Ads API **v20 retired** | Confirm any API integrations moved to v21+ (v25 current) |
| **2026-06-11 (done)** | DSA sunset extended to Feb 2027; DSA creation restored 06-15 | No emergency DSA migration needed; plan the AI Max transition deliberately |
| **2026-06-15 (done)** | `ad_storage` = single Consent Mode control; **Google Signals loses ad-data authority**; **offline import + EC-for-Leads move to Data Manager API (blocked in Google Ads API)**; EC web+leads merge to one switch; EEA CMv2 mandatory | **VERIFY offline GCLID upload pipeline still lands via Data Manager API; re-check remarketing list sizes; confirm `ad_user_data` consent fires** |
| **2026-07-01 (done)** | TOS: automation-authority default + advertiser asset-review obligation | Stand up a recurring auto-generated-asset compliance review |
| **2026-09 (upcoming)** | **Auto-upgrade to AI Max** for campaigns using auto-created assets + campaign-level broad match | Pre-set AI Brief matching/messaging guidelines + URL-expansion disclaimers **before** Sept |
| **2027-02 (future)** | **Dynamic Search Ads sunset + DSA auto-upgrade to AI Max** | Migrate any DSA campaigns on your terms before the forced date |

---

## 5. Chat Prompt Template Seeds (one recurring question per trend)

These are the operator-facing questions to bake into the product's prompt library. Each is phrased to trigger a concrete check against *this* account's data.

1. **AI Max readiness:** *"Which of my Search campaigns use automatically-created assets or campaign-level broad match and will auto-upgrade to AI Max in Sept 2026? For each, draft AI Brief messaging + matching guidelines that fence my compliance-critical claims, and model the risk/benefit of opting in for a lead-gen account at my current CPA."*
2. **Business Agent for Leads:** *"Am I eligible for the Business Agent for Leads beta? Audit the site/LP copy the agent would ground its answers on and flag any outdated immigration program facts before I enable it."*
3. **AI Overviews exposure:** *"Segment my Search performance by whether the query triggers an AI Overview (split by device). Where is AIO compressing my CTR or inflating CPC, and which informational terms should shift budget to higher-intent queries? Ask seo-supreme-agent whether we're cited in AIOs for my top terms."*
4. **Measurement pipeline health:** *"Verify my offline GCLID conversion import and Enhanced Conversions for Leads are running through the Data Manager API (not the retired Google Ads API path) and still landing after June 15. Confirm ad_storage + ad_user_data consent signals fire and flag any remarketing list shrinkage."*
5. **CPC/CPA benchmark check:** *"Compare each campaign's CPC and CPA against the 2026 Legal Services benchmark ($6.75 CPC / $127 CPA), not the cross-industry average. Flag campaigns above ~$150 CPA with poor CRM-scored lead quality as VBB candidates."*
6. **Value-based bidding gate:** *"Which campaigns clear ~30 conversions/month and have offline lead-value data feeding Smart Bidding? For those, model switching to value-based bidding; for thin ($25/day) campaigns, keep tCPA and explain why VBB would fail there."*
7. **Automation compliance review:** *"List every automatically-generated asset (ACA headlines/descriptions, AI Max text customizations) live in my account and flag any making immigration claims I haven't reviewed — I'm now legally responsible for them under the July 2026 TOS."*
8. **PMax lead-gen guardrails:** *"Before I launch PMax, build a negative-keyword list to block junk/DIY/jobs intent, set up a first-party audience exclusion for existing converters, and tell me which channels I should watch in channel-level reporting for lead quality."*
9. **Match-type experiment:** *"For my core RBI keywords, is exact/phrase or broad+Smart-Bidding better given my current offline-value signal coverage? Design a per-campaign A/B judged on CRM lead quality, not Google's conversion count."*
10. **Conversion-signal hygiene:** *"Confirm my primary conversion is the native Google Ads form-submit tag (not a GA4 import), that no PMax campaign is cannibalizing branded search, and that my RSAs aren't over-pinned."*

---

## Source Index (primary + authoritative)

- Google blog — AI Max new features: https://blog.google/products/ads-commerce/ai-max-new-features/
- Google blog — DSA upgrade to AI Max (2026-06-11): https://blog.google/products/ads-commerce/dsa-upgrade-to-ai-max-2026/
- Google blog — new Search ads for AI era (GML, 2026-05-20): https://blog.google/products/ads-commerce/google-marketing-live-search-ads/
- Google business — PMax steering & reporting updates 2026: https://business.google.com/us/accelerate/resources/articles/new-performance-max-steering-and-reporting-updates-coming-in-2026/
- Search Engine Land — GML 2026 everything (2026-05-20): https://searchengineland.com/google-marketing-live-2026-everything-you-need-to-know-478167
- Search Engine Land — conversational ad formats in AI Mode (2026-05-20): https://searchengineland.com/google-tests-new-conversational-ad-formats-in-ai-mode-and-search-478115
- Search Engine Land — AI Overviews impact on paid search (Adthena): https://searchengineland.com/what-industry-data-reveals-about-the-impact-of-googles-ai-overviews-on-paid-search-470019
- Search Engine Land — TOS update ahead of July 2026: https://searchengineland.com/google-ads-updates-terms-of-service-ahead-of-july-2026-rollout-479255
- Search Engine Land — 5 tactics to drop in 2026: https://searchengineland.com/google-ads-tactics-to-drop-464123
- Optmyzr — match-type performance study (30k accts, Feb 2026): https://www.optmyzr.com/blog/google-ads-match-type-performance/
- Optmyzr — value-based bidding guide: https://www.optmyzr.com/blog/value-based-bidding-guide/
- digitalapplied — 2026 benchmarks by industry: https://www.digitalapplied.com/blog/google-ads-benchmarks-2026-cpc-ctr-cvr-industry
- ideava — AI Overviews CTR decline (Seer data synthesis): https://ideava.com/insights/ai-overviews-ctr-decline/
- uniconsent — Consent Mode June 2026 change: https://www.uniconsent.com/blog/google-ads-consent-mode-change-2026
- clicksambo — 2026 offline conversion guide (Data Manager API migration): https://clicksambo.com/blog-detail/google-ads-offline-conversion-guide-2026
- groas.ai — 2026 Google Ads updates roundup: https://groas.ai/post/google-ads-updates-2026-every-major-change-campaign-impact
- groas.com — negative keyword strategy 2026: https://www.groas.com/post/google-ads-negative-keyword-strategy-2026-campaign-level-ai-max-pmax-industry-lists
- Elevarus — VBB for lead gen 2026: https://elevarus.com/value-based-bidding-lead-generation-2026/
- WordStream — GML 2026 11 announcements: https://www.wordstream.com/blog/google-marketing-live-2026

> **Confidence notes.** Google blog + Search Engine Land + Optmyzr are primary/high-trust. digitalapplied, groas, ideava, clicksambo, Elevarus are secondary aggregators — used where they carry the specific number and cross-check against each other; the `−37% QS`, `−22% CPA`, and `+7% AI Max` figures rest on single secondary sources and are marked `UNVERIFIED` for magnitude. No statistics were invented; where a source paraphrased a study (Seer, Adthena) rather than the original, the paraphrase is attributed.
