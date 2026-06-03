# Meta Funnel — Test Plan

**Pixel:** 584590286928383
**Container:** GTM-WZKDXFH8
**Page:** https://www.mercan.com/canadian-citizenship-by-descent

## Pre-Test Setup

1. Open Meta Events Manager → Test Events tab
2. Enter your browser's Test Event Code (from Events Manager)
3. Open GTM Preview Mode for GTM-WZKDXFH8
4. Navigate to the landing page in the GTM Preview browser

## Event Verification Matrix

### Tier 1: Engagement (test immediately — page elements exist)

| # | Event | Test Action | Expected Fire | Verify In |
|---|-------|-------------|---------------|-----------|
| 1 | **Page_Engaged** | Stay on page 15s AND scroll past 25% | Once | Events Manager: `Page_Engaged` appears with `content_category: bill_c3_descent` |
| 2 | **Scroll_50** | Scroll to ~50% of page (~6,900px) | Once | Events Manager: `Scroll_50` with `scroll_depth: 50` |
| 3 | **Scroll_75** | Scroll to ~75% (~10,400px) | Once | Events Manager: `Scroll_75` |
| 4 | **Scroll_90** | Scroll to ~90% (~12,500px) | Once | Events Manager: `Scroll_90` |
| 5 | **Time_60s** | Stay on page 60s with tab visible | Once | Events Manager: `Time_60s` with `time_on_page: 60` |
| 6 | **Time_180s** | Stay on page 180s with tab visible | Once | Events Manager: `Time_180s` |

**Visibility test:** Switch to another tab during timer → timer should PAUSE. Switch back → timer resumes. Time_60s should NOT fire if you spent 30s visible + 30s hidden.

### Tier 2: Form Interactions (test immediately — form exists)

| # | Event | Test Action | Expected Fire | Verify In |
|---|-------|-------------|---------------|-----------|
| 7 | **Form_Start** | Click into First Name field | Once (first field only) | Events Manager: `Form_Start` |
| 8 | **Form_Field_Email** | Type `test@example.com` in email field, click away | Once | Events Manager: `Form_Field_Email` with `field_value_length` |
| 9 | **Form_Field_Phone** | Type `5141234567` in phone field, click away | Once | Events Manager: `Form_Field_Phone` |
| 10 | **Canada_Citizenship_Lead** | Submit the form with valid data | Every submit | Events Manager: `Canada_Citizenship_Lead` with hashed `em`, `ph`, `fn`, `ln` in user_data |

**EMQ verification for #10:**
- After submit, check Events Manager → Canada_Citizenship_Lead → Event Match Quality
- Should show match parameters: `em` (email), `ph` (phone), `fn` (first name), `ln` (last name), `external_id`
- EMQ should move from "blank" to at least "Good" within 24-48h of receiving 5+ events with hashed PII

### Tier 3: CTA Clicks (test immediately — phone links exist)

| # | Event | Test Action | Expected Fire | Verify In |
|---|-------|-------------|---------------|-----------|
| 11 | **Phone_Click** | Click the `514-282-9214` phone link (header) | Every click | Events Manager: `Phone_Click` with `phone_number` and `click_location: header` |
| 12 | **Phone_Click** | Click the phone link in footer | Every click | `click_location: footer` |

### Tier 4: STUB Events (test AFTER dev builds the feature)

| # | Event | Prerequisite | Test Action |
|---|-------|-------------|-------------|
| 13 | **Eligibility_Quiz_Start** | Quiz built (P2 dev) | Click into Q1 of quiz |
| 14 | **Eligibility_Quiz_Q3** | Quiz built | Reach Q3 |
| 15 | **Eligibility_Quiz_Complete** | Quiz built | Complete quiz |
| 16 | **Canada_Citizenship_Lead_Qualified** | Quiz built + form | Submit form after passing quiz |
| 17 | **WhatsApp_Click** | WhatsApp button added | Click WhatsApp link |
| 18 | **CTA_BookCall_Click** | "Book a call" button added | Click booking CTA |
| 19 | **CTA_FreeEval_Click** | "Free assessment" button added | Click assessment CTA |
| 20 | **CTA_Guide_Download** | Bill C-3 PDF added | Click download link |
| 21 | **Video_Play** | Video element added | Play video |
| 22 | **Video_50** | Video element added | Watch to 50% |
| 23 | **Video_Complete** | Video element added | Watch to 95% |
| 24 | **Booking_PageView** | Calendly/Cal.com added | Page loads with calendar |
| 25 | **Booking_Slot_Selected** | Calendly added | Select a time slot |
| 26 | **Booking_Confirmed** | Calendly added | Confirm booking |
| 27 | **Intake_Complete** | Long intake form built | Submit intake form |

## Bot Suppression Verification

1. Open Chrome DevTools → Network conditions → User agent
2. Set UA to `Googlebot/2.1 (+http://www.google.com/bot.html)`
3. Reload page, scroll, interact with form
4. **ZERO events should fire** in Events Manager
5. Reset UA to default, reload → events should fire again

## CAPI Dedup Verification

1. Submit the form (triggers Canada_Citizenship_Lead)
2. In Events Manager, the event should appear **once** (not twice)
3. Check "Processing Status" → should show "Browser + Server" source
4. The `event_id` should match between browser and server entries
5. If you see duplicates, check the CAPI proxy logs for mismatched eventIDs

## Tab Visibility Test

1. Open page, immediately switch to another tab
2. Wait 60 seconds
3. Switch back to the landing page tab
4. **Time_60s should NOT have fired** (timer was paused while hidden)
5. Wait on the page for the remaining time → Time_60s should fire

## EMQ Timeline

| Day | Expected EMQ Status | Action If Not Met |
|-----|--------------------|--------------------|
| Day 0 (deploy) | Blank | Normal — no events yet |
| Day 1 | Blank → Poor | Check if events are arriving in Events Manager |
| Day 2 | Poor → OK | Verify user_data hashes are present in event payloads |
| Day 3-5 | OK → Good | If still "Poor", check SHA-256 hashing output format |
| Day 7 | Good → Great | If stuck at "OK", ensure phone numbers use E.164 format |

## Post-Deploy Monitoring Checklist

- [ ] All 12 active events appear in Events Manager within 1 hour
- [ ] Zero standard events (Lead, Contact, etc.) in the event log
- [ ] user_data shows hashed fields (64-char hex strings) not plaintext
- [ ] Bot traffic does NOT generate events
- [ ] CAPI proxy returns 200 for all events
- [ ] CAPI proxy returns 422 if someone accidentally sends a standard event name
- [ ] EMQ exits "blank" within 48h
- [ ] No events rejected by Meta (check Events Manager → Diagnostics)

## Events Meta Might Reject (watch list)

These custom event names are safe but monitor for 48h:

| Event | Risk | Mitigation |
|-------|------|-----------|
| Canada_Citizenship_Lead | LOW — already accepted (~21 events) | None needed |
| Canada_Citizenship_Lead_Qualified | LOW — "Citizenship" accepted in existing event | None |
| Eligibility_Quiz_* | MEDIUM — "Eligibility" could trigger sensitivity filter | Rename to `Quiz_Start`, `Quiz_Q3`, `Quiz_Complete` if rejected |
| Booking_Confirmed | LOW — generic name | None |
| All others | LOW — generic engagement names | None |
