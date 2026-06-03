# Gtm Specialist Notes

**Last updated:** 2026-06-01 14:28

**Task:** Run stage 6 for campaign build

**Critical Details:** AW-959555504, GTM-WZKDXFH8, GTM-only, AW-826329520
Stage 6 — GTM Specialist sets up conversion tracking. Per the PPC Strategist's handoff, the campaign (ID 23871240619) is built and PAUSED, but needs a **Panama-specific conversion action** before enabling.
Let me verify what's currently on the landing page and check the conversion actions registry.Let me check existing conversion actions and verify tracking on the landing page simultaneously.**Panama QIV Lead** conversion action already exists (ID: 7607343274, PRIMARY, 90-day lookback). Now I need to verify the tag is actually firing in GTM-WZKDXFH8. Let me check the GTM container.I can see the GTM 
- **Type:** Google Ads Conversion Tracking
- **Conversion ID:** 826329520 (matches AW-826329520 on the page)
- **Conversion Label:** C98tCKqxu6scELCTg4oD
- **Trigger:** CE - Panama Form Submit (Custom Event)
Now let me verify the trigger to ensure it's scoped correctly to the Panama page form submission.Let me navigate to the trigger directly to see its configuration.Let me click on the Triggers tab to inspect the Panama trigger.The trigger **CE - Panama Form Submit** is configured:
- **Type:** Custom Event
- **Filter:** Page URL **contains** `panama-qualified-investor`
- **Used by:** 1 tag (Panama QIV Lead)
Now I need to verify what custom event name it's listening for. Let me click into it, and also check the "GF - Push dataLayer on AJAX" tag that creates the dataLayer event.The full trigger configuration:
- **Type:** Custom Event
- **Event name:** `gf_submit` (Gravity Forms AJAX submit event)
- **Fires on:** Page URL **contains** `panama-qualified-investor`
- **Referenced by:** Panama QIV Lead tag
This is the same pattern used for Greece and Portugal — the "GF - Push dataLayer on AJAX" custom HTML tag pushes a `gf_submit` event to the dataLayer when a Gravity Form submits, and each campaign's trigger listens for that event scoped to its landing page URL.
Now let me verify the GF dataLayer push tag to confirm the `gf_submit` event is being generated. Let me also check the inline gtag() on the Panama page for dual-tracking.Let me go to the GF dataLayer push tag directly.**Critical issue found.** The `programForms` array only includes forms `[15, 23, 26]` (Portugal and Greece). The Panama form is NOT in this list — the `gf_submit` event will **never 
Let me scroll down to see the full script, then check the Panama form ID.Now I have the full picture. The script pushes `gf_submit` **only** for forms 15, 23, 26. I need to find the Panama form ID. Let me check the Panama landing page.Important finding — this is **NOT a Gravity Form**. It's a custom React/Next.js form with `space-y-4` class. The `gform_confirmation_loaded` event from the GTM tag w
Let me check what happens on form submission — is there a thank-you page redirect or inline confirmation?Key findings:
1. **"Thank you! Your inquiry has been submitted."** — inline confirmation message (no redirect to a thank-you page)
2. **`gform_confirmation_loaded`** is referenced in the page JS — so Gravity Forms IS being used, but through a custom React wrapper
3. **No inline gtag conversion labels** — no dual-tracking on this page yet
4. **No thank-you page redirect** — confirmation is shown inline
Let me check if the `gform_confirmation_loaded` jQuery event actually fires on this page by examining the form submission handler more closely.jQuery is loaded but there are **no Gravity Forms elements in the DOM** — this is a custom React form. The `gform_confirmation_loaded` event will NOT fire on this page. Let me check how the form actually submits.I now have the full picture. This is a **Next
Let me save my findings and present the complete Stage 6 report.## Stage 6 — GTM Specialist: Conversion Tracking Audit
### What I Found
**Good news — the infrastructure exists:**
| Component | Status | Details |
|---|---|---|
| **Conversion Linker** | Active | Fires on All Pages |
| **Trigger** | CE - Panama Form Submit | Custom Event `gf_submit` where Page URL contains `panama-qualified-investor` |
| **Clarity** | Loaded | Project active on the page |
### CRITICAL ISSUE: The conversion tag will NEVER fire
The trigger listens for a `gf_submit` dataLayer event, which is pushed by the **"GF - Push dataLayer on AJAX"** Custom HTML tag. That tag listens for jQuery's `gform_confirmation_loaded` event — but **only for form IDs [15, 23, 26]** (Portugal and Greece forms).
**Two problems:**
1. **The Panama form ID is NOT in the `programForms` array** — even if the event fired, it would be filtered out
2. **The Panama page uses a custom React/Next.js form** — NOT a standard Gravity Form. There are no GF elements in the DOM, no GF AJAX submission. The `gform_confirmation_loaded` jQuery event will **never fire** on this page. The form shows an inline confirmation message ("Thank you! Your inquiry has been submitted.") via React state — no page redirect.
**Bottom line: zero conversions will be tracked for this campaign as-is.**
### Two Fix Options
**Option A: GTM MutationObserver (GTM-only, no code changes)**
Add a Custom HTML tag in GTM that watches for the "Thank you" confirmation text to appear on the Panama page. When detected, push `gf_submit` to dataLayer → existing trigger + tag fire normally.
- Pros: No site code changes, deploy entirely in GTM, works today
- Cons: Fragile if confirmation text changes, slight delay
**Option B: Inline gtag() in Next.js form handler (code change)**
Add `gtag('event', 'conversion', {send_to: 'AW-826329520/C98tCKqxu6scELCTg4oD'})` to the form's success callback in the Next.js source code. This matches the **dual-tracking pattern** (inline primary + GTM safety net) used on other campaigns.
- Pros: Most reliable, matches account architecture, fires instantly on success
- Cons: Requires a code deployment to mercan.com
### My Recommendation
**Do both** — this is the dual-tracking pattern that's proven on this account:
1. **Option B first** (inline gtag in Next.js) → primary, reliable
2. **Option A second** (GTM MutationObserver) → safety net
But if you can only do one right now, **Option A** gets us tracking today without waiting for a code deploy.
### Also Noted
- **No inline gtag conversion tracking** exists on this page currently — the other campaigns (goldenvisas.mercan.com) have inline `gtag()` as primary, but this mercan.com page does not
- The `AW-959555504` pixel the CRO Specialist saw is NOT present in the current page — only `AW-826329520` is active (which is the correct one matching the conversion tag)
### Which approach do you want me to execute?
— *GTM Specialist*

---

## Session Log

### 2026-05-31 00:02 — how our server side tagging agent and system is diferenrent from what https://po

**Task:** how our server side tagging agent and system is diferenrent from what https://popsixle.com/product offer

**Critical Details:** GTM-K6864NBH, GTM-WZKDXFH8
I'll look at what Popsixle offers, then compare to your setup.## Popsixle vs. Our Tracking System — GTM Specialist Breakdown
Two fundamentally different things. Popsixle is a **product** (a Shopify CAPI SaaS); ours is a **bespoke lead-gen measurement stack + an AI agent that manages it**. Here's the honest comparison.
### What Popsixle actually is
A plug-and-play **server-side Conversions API connector for Shopify ecommerce**. It captures purchase/checkout events server-to-server and forwards them to Meta, Google, TikTok. Its whole value prop is *"recover the ~60% of signal lost to iOS14/ad-blockers, send 100% of site data, SHA-256 hashed, 10-min no-code install, weekly refresh."* It's optimized for **transactional ecommerce events** (purch
### What we run
| Dimension | Popsixle | Our system (Panama QIP / Mercan) |
|---|---|---|
| **Conversion type** | Purchase/checkout transactions | Form submission (consultation request), GCLID-attributed |
| **"Agent"** | None — it's static infra | A multi-persona AI (this) that audits, debugs, and writes changes to live tracking + campaigns |
### The honest gap — where Popsixle is genuinely ahead
**We are NOT doing true server-side tagging today.** Our "server-side tagging agent" is really:
1. **Client-side dual-tracking** (inline gtag + GTM client container) — fires in the browser, so it's exposed to the same ad-blocker / ITP / iOS signal loss that Popsixle exists to solve.
2. An **AI agent** that manages campaigns + tags, not a server container (sGTM) forwarding hashed events server-to-server.
Popsixle's core advantage — a real **server-to-server CAPI pipe** that recovers blocked browser signal — is something our current Panama stack **does not have**. For an account this low-volume and high-value, every lost conversion is disproportionately costly, so this matters.
### Where we're ahead / why Popsixle doesn't fit us as-is
- **It's Shopify/ecommerce-shaped.** Mercan sells a $300K real-estate-backed advisory service via lead forms on a Next.js page — there's no "purchase" event, no cart, no AOV for Popsixle to optimize against.
- **It's Meta-centric in spirit; we're Google Ads-first** with a 90-day investor decision cycle Popsixle's ecommerce defaults don't model.
- **Custom conversion logic** — we scope to a specific React form confirmation state with GCLID passthrough; a generic Shopify connector wouldn't handle that.
### My recommendation
If the goal is "match Popsixle's signal recovery," the right move isn't to buy Popsixle — it's to **close our two open items + add a server container**:
1. **Enable Google Ads Enhanced Conversions** (already our #1 open action) — this is the lead-gen equivalent of Popsixle's hashed CAPI matching, hashing form email/phone client-side and recovering match rate. Highest ROI, lowest lift.
2. **Add server-side GTM (sGTM)** for the Panama LP — a real server container forwarding hashed lead events to Google's CAPI. *This* is the genuine "server-side tagging" Popsixle is selling, adapted to lead-gen.
3. Keep the dual-tracking as the browser layer; sGTM becomes the third, ITP/ad-blocker-resistant layer.
Want me to spec the sGTM + Enhanced Conversions buildout for the Panama page? That gets us Popsixle's actual benefit without bolting an ecommerce tool onto a lead-gen funnel.
— *GTM Specialist*

### 2026-06-01 14:28 — submit a real test in the landing page using chrome mcp and check the tag and tr

**Task:** submit a real test in the landing page using chrome mcp and check the tag and tracking if fired

**Critical Details:** GTM-Verify, GTM-WZKDXFH8
I'll run the live test. First, let me load the Chrome browser tools, then drive the form submission while watching for the conversion ping.Tools loaded. Let me check what pages are currently open in Chrome.The Panama page is open (tab 10) and Tag Assistant is connected to GTM-WZKDXFH8 (tab 15). Let me select the Panama page and reload it fresh so I capture network requests from a clean state.Panam
- `{"is_valid":false}` — submission rejected
- The **Phone field** (`"id":3 ... "failed_validation":true`) — my `+15142829214` failed Gravity Forms' "standard" US phone format `(###) ###-####`. reCAPTCHA token (`input_999`) was accepted; phone format is what blocked it.
Also confirmed: this is **Gravity Form ID 11** (`/api/forms/11`), Name + E-mail + Nationality + Country are required. Let me fix the phone format and re-submit cleanly, resetting the dataLayer monitor first.Phone fixed to valid US format. Re-submitting now.**Breakthrough — the submission succeeded this time.** `hasThankYou: true`, form replaced by confirmation, and critically **`gf_submit` FIRED**
## GTM Specialist — Live Test-Lead Verification Result
I submitted a real test lead on the Panama LP via Chrome (marked `TEST / GTM-Verify-Ignore / test.gtm.verify@mercan.com` so sales discards it). The "Thank You!" confirmation rendered (screenshot above). Here's what fired.
### ✅ Tracking is FULLY working — end to end, with Enhanced Conversions
On the successful submit, I captured the **dedicated conversion ping** in the network log:
The full chain is confirmed: **form success → `gf_submit` dataLayer event → "CE - Panama Form Submit" trigger → Panama QIV Lead tag (ID 826329520 / label C98tCKqxu6scELCTg4oD) → hashed email attached.** This **closes my long-standing open concern** — whatever the old `programForms [15,23,26]` worry was, the new `/api/form-submit` path now pushes `gf_submit` for form 11 correctly, and Enhanced Conv
*(Caveat: my test used a placeholder gclid `test123_conversion_tracking` since I navigated directly, so this test conversion won't attribute to a real ad click — but the tag firing + EC data is what we needed to verify, and both check out.)*
### 🚨 The real discovery — a hidden conversion killer
My **first** submit attempt was **rejected** (`{"is_valid":false}`) — and the only on-screen feedback was a vague *"Please check the form and try again."* The server response pinpointed the cause: the **Phone field failed validation** (`"id":3,"failed_validation":true`). My `+15142829214` was rejected because the form enforces Gravity Forms' **"standard" US format `(###) ###-####`**. It only passe
**Why this matters enormously for THIS audience:** our targets are US-based and **international HNW investors**. Anyone entering a phone with a country code (`+1...`, `+44...`, `+971...`) — which is exactly how investors type their number — gets **silently rejected with a generic error and no field-level hint**. This is fully consistent with Clarity's "engaged readers, zero completions" signal. We
### Confirmed facts (persist these)
- **Form:** Gravity Form **ID 11**, 8 fields (Name, E-mail*, Phone, Nationality*, Country of residence*, How-heard, Message, Yes/No radio) + reCAPTCHA v3 — **the 13→4 reduction never shipped**, as flagged earlier.
- **Conversion:** Panama QIV Lead — ID **826329520**, label **C98tCKqxu6scELCTg4oD**, trigger **CE - Panama Form Submit** (`gf_submit`), container **GTM-WZKDXFH8**. Firing ✅. Enhanced Conversions ✅.
- **Required fields:** Name, E-mail, Nationality, Country of residence. Phone is *optional* but format-validated when filled.
### Recommended fixes (not tracking — this is the conversion wall)
1. **Relax the phone validation** to accept international formats (or switch to an intl tel input with country selector). Highest-priority — it's silently killing investor leads.
2. **Surface field-level errors** — replace the generic "check the form" with a red message on the offending field.
3. Ship the **form-field reduction** that was logged but never deployed.
Want me to (a) document this in the role notes + chronicle, and (b) write up the phone-validation fix spec for the mercan.com dev team?
— *GTM Specialist*
