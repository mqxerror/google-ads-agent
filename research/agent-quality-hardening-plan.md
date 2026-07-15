# Agent Quality Hardening Plan — from the Panama QIP chat post-mortem (2026-07-08)

Source: critical evaluation of the app agent's Panama QIP thread (`Downloads/Panama QIP  Qualified Investor Program_2026-07-08.md`). The decisions were mostly sound; the **process** failed — stale-data diagnosis, root cause (the ad's final URL / the `/lp/` page that already had the email capture) missed for 10+ messages and a full 7-persona Team Audit, and an execution dead-end on "switch the landing page."

## Workstreams (priority order)

### WS1 — Ship the ad final-URL MCP tool  [P0 · concrete · BUILD NOW]
**Problem:** No MCP/service tool updates an existing ad's `final_urls` (only *create* + *status*). Confirmed 2026-07-08: `final_url` appears only in create/read paths. "Switch the landing page" is impossible without a destructive delete+recreate (drops RSA pins + resets ad history — including on the only converting ad).
**Build:**
- Service method + MCP tool `ad_update_final_urls(ad_resource_name, final_urls)` using `AdService.mutate_ads` with `update_mask=["final_urls"]` (this in-place mutate is PROVEN — used it 2026-07-06 to edit live RSA copy). Works for RSAs/ETAs; does NOT drop pins/headlines/history.
- Optional router endpoint `POST /api/operations/ad/final-urls` mirroring `operations.py`.
- URL validation (http/https, non-empty). Register in the MCP surface + `--groups`.
- Dry-run harness coverage (validate_only) so it's in `validate_all_tools.py`.
**Acceptance:** tool visible in MCP surface; dry-run passes; can change a test ad's final URL in place (validate_only) with no new ad ID created.

### WS2 — Verify-before-diagnose (step-0 audit checks)  [P1]
**Problem:** Agent diagnosed from a month-old form finding and never checked the page the ads actually point to — for 10+ messages. The `/lp/` page (with the "missing" email capture) was discovered only because the user volunteered it.
**Build (surgical, additive to the campaign-audit / PPC-persona / workflow_orchestrator flow):** a mandatory Step 0 that, before any diagnosis, (a) pulls each serving ad's live `final_urls`, (b) fetches that exact page, (c) re-tests the form + confirms tracking present — and injects those live facts into the analysis context. No recommendation may anchor on an unverified page/form claim.
**Acceptance:** an audit surfaces the ad's real final URL + page state up front; no page/form claim is asserted without a same-session check.

### WS3 — Freshness guard on findings  [P1]
**Problem:** June-1 form finding reused as current fact on July 8.
**Build:** findings / `role_notes` carry a timestamp; any finding older than 7 days is auto-labeled `STALE — re-verify` and cannot anchor a live-money recommendation without a fresh check.
**Acceptance:** stale findings are labeled; the agent re-verifies or flags before use.

### WS4 — ID integrity  [P2]
**Problem:** cites specific GTM/conversion IDs (GTM-WZKDXFH8, AW-826329520, AW-959555504, labels, GA4/Lead-form IDs) that may be inferred and differ from tracking memory.
**Build:** conversion/container IDs in any output must originate from a live pull (conversion-action query / tag data) and be labeled with source; never inferred. Analytics-persona guard/checklist.
**Acceptance:** every ID in a report is traceable to a live query.

### WS5 — Team Audit retune  [P2]
**Problem:** 7 personas, verbose, mostly agreeing despite being told to disagree; amplified a wrong premise.
**Build:** gate the team session behind a WS2-verified premise; cap per-persona length; require each persona to state one disconfirming fact / one thing that would change the conclusion.
**Acceptance:** shorter, premise-gated output with genuine disconfirmation.

## Execution assignment
- **Subagent A → WS1** (final-URL MCP tool): build + test outright.
- **Subagent B → WS2–WS5** (behavior hardening): implement the SAFE additive guardrails; conservative, no wholesale persona rewrites; where a change is a genuine design choice, implement a conservative first-cut AND flag it for Wassim's review. Test nothing breaks (unit tests + import). Do NOT restart prod backend.
- Both report back: files changed, what shipped vs. what needs Wassim's design call.

## Constraints
- Additive/surgical only. MCP is wired into Claude Code globally; `.py` changes need a manual backend restart to take effect (do not restart).
- No account mutations. No secrets in code. Keep existing flows intact.
