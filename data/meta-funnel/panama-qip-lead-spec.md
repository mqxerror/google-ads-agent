# Panama_QIP_Lead — event spec + GTM Specialist brief (2026-06-17)

Mirror of `Canada_Citizenship_Lead`. Decisions: event name **`Panama_QIP_Lead`**;
console work via the **GTM Specialist** persona; capi-proxy retirement is GATED
(do NOT retire until every event is verified arriving at Meta).

## Current state (from code recon — spot-checked)
- ONE shared pipeline: every program's form → `mercan-main-site/src/app/api/form-submit/route.ts`; program resolved by URL via `resolveProgramTracking()` → `src/lib/tracking/program-map.ts`.
- Panama IS already mapped (`program-map.ts:93-98`: `contentCategory: "panama"`, `contentName: "Panama Qualified Investor Program"`, GravityForm **GF11**) but is **un-instrumented for a custom event** — it currently fires the standard `Lead`.
- Event name is decided at `route.ts:~328-337` by a hardcoded `isCitizenship` boolean → `"Canada_Citizenship_Lead"` else `"Lead"`. The browser `mercan_lead` dataLayer push (`src/lib/tracking/events.ts:140-151`) is gated to citizenship only.
- CAPI: `src/lib/tracking/meta-capi.ts` `sendLeadToCapi()` → Graph **v21**, hashes em/ph/fn/ln/country.

## ⚠️ Bug in the naive fix (do NOT do this)
The recon suggested "add `panama` to the `isCitizenship` boolean." That would send
**Canada_Citizenship_Lead for Panama submissions** — wrong event. Replace the
boolean with a per-program event-name map instead.

## CODE change (mercan-main-site — live site, needs go-ahead + Dokploy deploy)
1. `route.ts` — replace the `isCitizenship` event-name branch with:
   ```ts
   const META_EVENT_BY_CATEGORY: Record<string, string> = {
     citizenship_by_descent: "Canada_Citizenship_Lead",
     panama: "Panama_QIP_Lead",
   };
   const metaEventName =
     META_EVENT_BY_CATEGORY[programTracking.contentCategory] ?? "Lead";
   // use metaEventName in the sendLeadToCapi({ eventName: metaEventName, ... }) call
   ```
2. `events.ts:140-151` — generalize the `mercan_lead` dataLayer gate so it fires for
   any program that has a custom Meta event (citizenship + panama), passing the
   resolved event name / category through so GTM can route it.
3. Keep the same `event_id` on both the dataLayer push and the CAPI call (dedup).

## GTM Specialist brief (console — web GTM-WZKDXFH8 + server sGTM GTM-WVP46T9Q)
Mirror the Canada_Citizenship_Lead tags exactly, swapping the event name + trigger:
1. **Web container:** Meta Pixel custom-event tag → `trackSingleCustom '584590286928383' 'Panama_QIP_Lead' {content_name:'Panama Qualified Investor Program', value, currency} {eventID}`; trigger = `mercan_lead` dataLayer event where `content_category == "panama"`.
2. **sGTM (server):** duplicate the Stape "Facebook Conversions API" tag → `event_name = Panama_QIP_Lead`; trigger on the inbound Panama event. Auto-hash PII on; event_id passthrough for dedup.
3. **Publish discipline:** create + publish in ONE pass; then confirm **Workspace = 0 unpublished changes** (the duplicate-tag trap — see [[feedback_gtm_workspace_vs_live_duplicates]]).
4. **NO test_event_code** left on the tag in prod (the TEST10750 footgun).

## Wassim's manual step (only he can)
Meta Events Manager → after the event sends once → Event statuses → **Confirm `Panama_QIP_Lead`** (Nationality-dataset confirmation step) → build Custom Conversion on it (rule: `event == Panama_QIP_Lead AND url contains mercan.com`) → point the Panama campaign optimization at it.

## Verify end-to-end (then it's live)
Test submit on the Panama LP → Meta Test Events shows `Panama_QIP_Lead` Received-From-Server/Processed with full user_data → Overview count increments → EMQ populates.

## capi-proxy retirement — GATED (task #26, blockedBy #24)
Per Wassim 2026-06-17: NOT until ALL events verified tracked at Meta. The
verification checklist (task #24) must show every funnel event (lead + engagement)
arriving at Meta from sGTM before we disable the Next.js inline leg + GTM relay
Tag 08 and decommission the swarm service.
