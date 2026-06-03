# Meta Funnel Implementation — Bill C-3 Descent Pages

**Pixel:** 584590286928383 (FLAGGED — standard events blocked)
**Container:** GTM-WZKDXFH8 (mercan.com V2, currently V11 live)
**Page:** https://www.mercan.com/canadian-citizenship-by-descent
**Date:** 2026-05-21

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  BROWSER (visitor's tab)                                 │
│                                                          │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────┐ │
│  │ 01-Utilities  │   │ 02-Engagement │   │ 03-Form    │ │
│  │ SHA-256, UUID │   │ Scroll, Time  │   │ Start/Email│ │
│  │ Bot check     │──▶│ Page_Engaged  │   │ Phone/Lead │ │
│  │ __mf_fireEvent│   └───────┬───────┘   └─────┬──────┘ │
│  └───────▲───────┘           │                  │        │
│          │         ┌─────────┴──────────────────┘        │
│          │         ▼                                     │
│  ┌───────┴───────────────────────────────────┐          │
│  │  __mf_fireEvent(eventName, customData)     │          │
│  │  1. Suppress bots + hidden tabs            │          │
│  │  2. Generate eventID (UUID v4)             │          │
│  │  3. Hash user_data (SHA-256)               │          │
│  │  4. fbq('trackCustom', ..., {eventID})     │◀── Browser Pixel
│  │  5. dataLayer.push({meta_custom_event})     │          │
│  └───────────────────┬───────────────────────┘          │
│                      │                                   │
│  ┌───────────────────▼───────────────────────┐          │
│  │  08-CAPI Relay                             │          │
│  │  sendBeacon → CAPI proxy endpoint          │◀── Server Signal
│  │  Same eventID for dedup                    │          │
│  └───────────────────┬───────────────────────┘          │
└──────────────────────┼───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  CAPI PROXY (capi-proxy.py)                              │
│  • Adds client_ip_address (server-side)                  │
│  • Forwards to graph.facebook.com/v20.0/{pixel}/events   │
│  • Blocks standard event names (safety net)              │
│  • Returns Meta's response for monitoring                │
└──────────────────────────────────────────────────────────┘
```

## GTM Tags to Create (8 total)

| # | Tag Name | Type | Trigger | Priority | File |
|---|----------|------|---------|----------|------|
| 1 | MF - Utilities & Dispatcher | Custom HTML | All Pages | 100 | `01-variables-and-utilities.html` |
| 2 | MF - Engagement (Scroll + Time) | Custom HTML | All Pages | 50 | `02-engagement-scroll-time.html` |
| 3 | MF - Form Tracking | Custom HTML | DOM Ready | 50 | `03-form-tracking.html` |
| 4 | MF - CTA Click Tracking | Custom HTML | All Pages | 50 | `04-cta-click-tracking.html` |
| 5 | MF - Video Tracking | Custom HTML | All Pages | 50 | `05-video-tracking.html` |
| 6 | MF - Quiz Tracking | Custom HTML | All Pages | 50 | `06-quiz-tracking.html` |
| 7 | MF - Booking Tracking | Custom HTML | All Pages | 50 | `07-booking-tracking.html` |
| 8 | MF - CAPI Relay | Custom HTML | All Pages | 10 | `08-capi-relay.html` |

**Trigger scoping:** All tags fire on All Pages but are internally scoped to
`/canadian-citizenship-by-descent` URLs by the event logic. If you want to
restrict to descent pages only, create a Page View trigger with URL contains
`/canadian-citizenship-by-descent`.

## GTM Variables Needed

**NONE.** All variables are handled inside the Custom HTML tags via `window.__mf_*`
globals. This avoids GTM variable lookup overhead and keeps everything self-contained.
The only GTM-native feature used is the "Tag Firing Priority" field on each tag.

## Trigger Configuration

| Trigger Name | Type | Condition | Used By |
|-------------|------|-----------|---------|
| All Pages | Page View | (built-in) | Tags 1, 2, 4, 5, 6, 7, 8 |
| DOM Ready | DOM Ready | (built-in) | Tag 3 (needs form fields in DOM) |

Only 2 triggers needed — both are GTM built-ins.

## Event Inventory

### Active Now (page elements exist)

| Event | Tier | Fire Rule | user_data |
|-------|------|-----------|-----------|
| Page_Engaged | Engagement | Once: 15s + 25% scroll | external_id only |
| Scroll_50 | Engagement | Once | external_id only |
| Scroll_75 | Engagement | Once | external_id only |
| Scroll_90 | Engagement | Once | external_id only |
| Time_60s | Engagement | Once | external_id only |
| Time_180s | Engagement | Once | external_id only |
| Form_Start | Intent | Once | external_id only |
| Form_Field_Email | Intent | Once | em + external_id |
| Form_Field_Phone | Intent | Once | ph + external_id |
| Phone_Click | Intent | Every click | external_id only |
| Canada_Citizenship_Lead | Conversion | Every submit | em, ph, fn, ln, country, external_id |

**11 active events** on deploy.

### Stub (auto-activate when page elements are added)

| Event | Prerequisite | Contract |
|-------|-------------|----------|
| WhatsApp_Click | wa.me link on page | Delegated listener — auto-detects |
| CTA_BookCall_Click | "Book a call" button | Text-match listener — auto-detects |
| CTA_FreeEval_Click | "Free assessment" button | Text-match listener — auto-detects |
| CTA_Guide_Download | PDF download link | href contains `.pdf` — auto-detects |
| Video_Play/50/Complete | `<video>` element | MutationObserver — auto-detects |
| Eligibility_Quiz_Start/Q3/Complete | Dev pushes `quiz_start`/`quiz_q3`/`quiz_complete` to dataLayer | See contract in `06-quiz-tracking.html` |
| Canada_Citizenship_Lead_Qualified | Quiz exists + form submit | See contract in `03-form-tracking.html` |
| Booking_PageView/Slot/Confirmed | Calendly or Cal.com iframe | postMessage listener — auto-detects |
| Intake_Complete | Dev pushes `intake_complete` to dataLayer | dataLayer listener |

**16 stub events** — zero GTM updates needed when features ship.

## CAPI Proxy Deployment

### Option A: Self-hosted (simplest for mercan stack)

```bash
# On 38.97.60.181
mkdir -p /opt/meta-capi && cd /opt/meta-capi
# Copy capi-proxy.py
pip install fastapi uvicorn httpx
# Set env vars
export META_PIXEL_ID=584590286928383
export META_ACCESS_TOKEN=<your_system_user_token>
# Run behind existing Nginx
uvicorn capi-proxy:app --host 127.0.0.1 --port 8787
# Add Nginx proxy_pass for /meta-events → localhost:8787
```

### Option B: Cloudflare Worker (recommended for latency)

Convert the Python logic to a CF Worker (JS). Same payload format.

### After deploying, update Tag 8:

In `08-capi-relay.html`, replace `{{CAPI Proxy URL}}` with the actual endpoint URL.

## GTM Installation Steps

1. Open GTM → GTM-WZKDXFH8 (mercan.com V2)
2. Create **Tag 1** first (Utilities — must exist before others):
   - New Tag → Custom HTML → paste contents of `01-variables-and-utilities.html`
   - Tag name: `MF - Utilities & Dispatcher`
   - Trigger: All Pages
   - Advanced Settings → Tag Firing Priority: `100`
   - Save
3. Create Tags 2-7 in any order (all depend on Tag 1):
   - Same process: Custom HTML → paste → set trigger → set priority `50`
   - Tag 3 uses **DOM Ready** trigger (not All Pages)
4. Create Tag 8 (CAPI Relay):
   - Only after CAPI proxy is deployed and URL is known
   - Priority: `10`
5. **Preview & test** using GTM Preview Mode before publishing
6. Run through the test plan (`test-plan.md`)
7. Publish new container version: `V12 - Meta Funnel Events (27 custom events)`

## Form Field → user_data Mapping

| Form Field | Field ID | user_data Key | Hash Method |
|-----------|----------|---------------|-------------|
| First Name | `input_46.3` | `fn` | SHA-256(lowercase(trim(value))) |
| Last Name | `input_46.6` | `ln` | SHA-256(lowercase(trim(value))) |
| Email | `input_3` | `em` | SHA-256(lowercase(trim(value))) |
| Phone | `input_42` | `ph` | SHA-256(digits only) |
| Country of Residence | `input_39` | `country` | SHA-256(lowercase(ISO-2)) |
| Session ID | sessionStorage | `external_id` | SHA-256(UUID) |

**Not mapped:** Nationality (`input_5`), How did you hear (`input_21`), Message (`input_9`) — no corresponding user_data keys in Meta spec.

## What This Does NOT Do (by design)

1. Does NOT fire any Meta standard event (Lead, Contact, etc.) — all blocked by pixel flag
2. Does NOT use Auto-Advanced Matching — explicit hashed user_data is more reliable on flagged pixels
3. Does NOT put unhashed PII in dataLayer or query strings
4. Does NOT track offsite redirects without postMessage backstop
5. Does NOT rename `Canada_Citizenship_Lead` — it's already trained with ~21 events
6. Does NOT use "immigration", "asylum", or other Meta-sensitive terms in event names

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Status |
|------|-----------|--------|-----------|--------|
| Meta rejects `Eligibility_Quiz_*` names | Low-Medium | Rename to `Quiz_*` | Monitor Events Manager Diagnostics for 48h post-deploy | Open |
| Multiple dataLayer.push monkey-patches conflict | Medium | Events don't fire | **FIXED** — consolidated into single subscriber in Tag 01 (`__mf_onDataLayer`). Tags 03, 06, 07, 08 now register handlers. | Resolved |
| CAPI proxy open to internet (no auth) | High | Event poisoning | **FIXED** — Origin check + `?token=` shared secret (CAPI_PROXY_SECRET env var). sendBeacon uses query param since it can't send custom headers. | Resolved |
| Country ISO-2 mapping incomplete | Medium | EMQ killed for non-CA/US | **FIXED** — 2-char values treated as ISO-2 directly; 55+ country name→code mappings added; unmapped countries produce empty (omitted) instead of garbage hash. | Resolved |
| Form field IDs change (dev redesign) | Low | Form tracking breaks | Field IDs are Gravity Forms convention — stable unless form is rebuilt | Open |
| CAPI proxy downtime | Low | Lose server-side signal | Browser pixel is primary — CAPI is redundant signal, not critical path | Open |
