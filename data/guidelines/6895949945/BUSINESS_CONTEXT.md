# Mercan Group — Business Context for AI Agent

## About the Company
Mercan Group is an immigration consulting firm that helps high-net-worth individuals and families obtain residency and citizenship through investment programs (Golden Visa programs). They operate globally with a focus on Portuguese, Greek, and MENA market immigration pathways.

## Programs We Advertise

### Portugal Golden Visa
- **What it is:** An investment-based residency program. Investors put money into approved Portuguese investment funds (minimum €500K) and receive residency permits, with a pathway to citizenship after 5 years.
- **Target audience:** US-based high-net-worth individuals looking for EU residency/citizenship.
- **Landing page:** mercan.com/business-immigration/portugal-golden-visa-program/
- **Conversion = lead form submission** on the landing page (Gravity Forms, tracked via GTM)
- **This is NOT just a keyword** — "Portugal Golden Visa" is the actual name of the government program.

### Greece Golden Visa
- **What it is:** Real estate investment-based residency in Greece. Lower entry point than Portugal.
- **Target audience:** US-based investors.
- **Landing page:** mercan.com/greece-golden-visa/

### MENA Golden Visa / Programs
- **What it is:** Various residency/investment programs marketed to Arabic-speaking audiences in UAE, Saudi Arabia, Kuwait, Qatar, Bahrain, Egypt.
- **Languages:** Arabic + English
- **This is a newer, smaller campaign with lower budget.**

### EB3 Brazil
- **What it is:** Employment-based immigration (EB-3) program targeting Brazilian market.
- **Smaller budget, high conversion volume at low CPA.**

## Business Model
1. Google Ads drives traffic to landing pages
2. Users fill out a lead form (consultation request)
3. Mercan's sales team contacts the lead
4. If qualified, the client signs up for the visa program (high-value deal: $20K-$100K+ per client)

## Campaign Management Philosophy
- **Lead quality matters more than lead volume** — one qualified lead is worth thousands of dollars
- **Cost per lead targets vary by program** — Portugal GV can tolerate $150-200 CPA because the deal value is very high. EB3 Brazil has lower CPA targets.
- **Only make ONE type of change per day** — don't change ads AND bidding at the same time
- **Wait 7 days minimum** after any change before evaluating results
- **Never use form_submit GA4 as primary conversion** — it fires on ALL website forms, inflating data
- **Each campaign MUST have its own dedicated conversion action**
- **Negative keywords should only be added based on actual search term data**, never on assumptions

## Account Structure
- Manager (MCC): 6895949945 (MQXDev)
- Sub-Manager: 7192648347 (Wassim)
- Client: 7178239091 (Mercan Group Main Account) — all active campaigns live here

## Key Context the Agent Must Always Remember
1. "Portugal Golden Visa" is a real government program, not just a marketing term
2. The campaigns target US audiences (except MENA which targets Middle East)
3. Conversion tracking uses GTM with campaign-specific tags — the GTM jQuery fix from March 19 is critical history
4. The account has many paused legacy campaigns — focus analysis on ENABLED campaigns only
5. Budget overspend is a known issue with TARGET_SPEND (Maximize Clicks) strategy — Google can spend up to 2x daily budget
