# Search Term Hunter Notes

**Last updated:** 2026-05-25 13:37

**Task:** Deep performance analysis for "Panama QIP — Qualified Investor Program":

1. **Trend Analysis**: How has performance changed over the last 14 days? Identify inflection points.
2. **Ad Group Breakdown*
## Panama QIP (23871240619) — Search Term Hunter Deep Analysis, May 25
**Data window:** May 21–25 (5 days live). 2,375 impressions, 241 clicks, $753.58 spent, **0 conversions**. Avg CPC $3.12, CTR 10.2%.
**Context:** Yesterday (May 24) I executed: 7 campaign-level negatives, removed 3 bad keywords, reduced AG2 bid to $2.50. Today's analysis measures the full picture and identifies what's still leaking.
### 1. Trend Analysis
| Date | Impr | Clicks | Cost | CTR | CPC |
|------|------|--------|------|-----|-----|
**Inflection point: May 23.** Impressions nearly doubled (519→797) — Google's auction exploration hit full stride. Spend blew past budget ($268 vs $150 target). May 24 pulled back slightly but still overspent at $223.
**May 25 is tracking lighter** (Sunday effect + negatives/keyword removals from yesterday may be reducing match volume). This is expected and healthy — we want fewer, better clicks.
**CPC is creeping up:** $2.89 → $3.24 over 5 days. This is normal auction pressure as Google tests higher positions. Not alarming yet, but watch for >$3.50.
### 2. Ad Group Breakdown
| Ad Group | Clicks | Cost | % Spend | Planned % | CPC | Verdict |
|----------|--------|------|---------|-----------|-----|---------|
**AG2 is still dominant at 53%** but this includes 4 days of pre-fix data. The 3 removed keywords + bid reduction should shift the next 7 days significantly. Recheck Tuesday.
**AG1 at 10.7% vs planned 50% remains the core structural problem.** The policy-blocked keyword ("panama qualified investor program" [exact]) was its anchor. The remaining AG1 keywords are lower-volume. AG1 needs new keywords or the policy exemption.
**AG4 at 21% with $4.81 CPC** is spending double its plan. Real estate keywords are expensive. Only 33 clicks — too early to judge, but the CPC warrants watching.
### 3. Keyword Efficiency (0 conversions = no CPA math possible)
**Top spenders:**
| Keyword | AG | Clicks | Cost | QS | Verdict |
|---------|-----|--------|------|-----|---------|
**Zero-serving keywords (0 clicks, 5 days):**
| Keyword | AG | QS | Issue |
|---------|-----|-----|-------|
**🚨 CRITICAL FLAG — 5 SUSPICIOUS KEYWORDS:**
| Keyword | Match | AG | Issue |
|---------|-------|----|-------|
These have 0 clicks so far — but **broad match "hotel" and "airbnb" are ticking time bombs.** If Google starts matching them, we'll burn budget on travel/rental queries instantly. These look like they were meant to be **negative keywords in AG4** but may have been added as positive keywords by mistake. **Must verify and remove/convert immediately.**
### 4. Quality Score Audit
| QS | Keywords | Impact |
|----|----------|--------|
**QS 1: "panama permanent residency"** — this is different from the QS 1 keyword I removed yesterday ("panama permanent residency **requirements**"). This one sits in AG2, has 6 clicks at ~$18. The LP doesn't match generic "permanent residency" queries well. **Recommend pause.**
**Total QS tax estimate: ~$70–100 of $753.58 (9–13%)** went to inflated CPCs from QS ≤3 keywords.
### 5. Search Term Quality — Post-Negative Assessment
#### NOW BLOCKED by yesterday's negatives:
| Cluster | Clicks | Cost | Status |
|---------|--------|------|--------|
#### STILL LEAKING — Not blocked by current negatives:
| Term | Clicks | Cost | Problem |
|------|--------|------|---------|
#### Waste Summary:
| Category | Cost | % of Total | Status |
|----------|------|------------|--------|
The negatives cut waste from ~20% to ~11.5%, but the **lifestyle/relocation cluster is the next target.**
#### Good queries (keep/promote):
| Term | Clicks | Cost | Signal |
|------|--------|------|--------|
### 6. Budget Allocation
| Ad Group | Planned % | Actual % | Weekly Projected | Verdict |
|----------|-----------|----------|------------------|---------|
**The budget problem is two-fold:**
1. AG2 has the most keyword volume → Google preferentially serves it (improving post-fix)
2. AG1 lost its anchor keyword to policy → starved for impressions (structural)
### 7. Top 3 Recommendations
#### 1. REMOVE/VERIFY 5 SUSPICIOUS KEYWORDS — hotel, airbnb, vacation rental, land for sale, rent apartment (CRITICAL, 5 min)
These look like negative keywords accidentally added as positives. Broad match "hotel" alone could drain the entire daily budget on irrelevant travel queries. They have 0 clicks only by luck. **This is a ticking time bomb — verify and remove today.**
**Impact: Prevents potential catastrophic waste**
**Effort: 5 minutes**
#### 2. ADD LIFESTYLE/RELOCATION NEGATIVES — cut the remaining 11.5% waste (HIGH impact, LOW effort)
The pensionado cluster is blocked, but relocation queries are still leaking ~$86 over 5 days (~$17/day = 11% of budget).
**Proposed campaign-level negatives:**
| Negative | Match Type | Rationale |
|----------|-----------|-----------|
| how to move to | Phrase | DIY research intent |
| living in panama | Phrase | Lifestyle, not investor |
| americans moving | Phrase | Same cluster |
**AG4-level negatives:**
| Negative | Match Type | Rationale |
|----------|-----------|-----------|
| best place to buy | Phrase | Property shopping without visa intent |
**Estimated weekly savings: ~$60–80**
#### 3. PAUSE "panama permanent residency" (QS 1) + "move to panama from us" (QS 3) (MEDIUM impact, LOW effort)
Two more keywords actively hurting the campaign:
| Keyword | QS | Clicks | Cost | Problem |
|---------|-----|--------|------|---------|
Pausing these removes $64 of waste and improves account-level QS signals. "move to panama from us" is also the source keyword for the biggest leaking search term cluster.
**Estimated weekly savings: ~$80–100 in QS-inflated CPCs + waste**
### Updated Scorecard (vs. May 24 analysis)
|--------|--------|--------|---|
### Priority Stack
1. 🚨 **Verify + remove 5 suspicious keywords** (hotel, airbnb, etc.) — TODAY
2. ⚡ **Add 5 lifestyle negatives** — TODAY
3. ⚡ **Pause QS 1 + QS 3 keywords** — TODAY
4. 🔧 **Form reduction to 4 fields** — developer needed, biggest ROI item
5. 📋 **Request policy exemption** for "panama qualified investor program" [exact] — restores AG1 volume
**Shall I execute items 1–3 now?** Item 1 is the most urgent — I want to verify those 5 keywords before Google starts matching "hotel" to our $150/day budget.
— *Search Term Hunter*