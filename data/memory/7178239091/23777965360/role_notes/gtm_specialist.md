# Gtm Specialist Notes

**Last updated:** 2026-04-20 14:47

**Task:** fix the consent on mercan.com not sure how we can do it though plugin or through gtm but the subdomain is not delivering conversion I need to test mercan with new campapifgns

**Critical Details:** GTM-WZKDXFH8, GTM-K6864NBH
Two issues to tackle: (1) consent blocking conversions, and (2) testing mercan.com with new campaigns. Let me diagnose the consent setup first.
I'll check both domains simultaneously to see what's happening with consent and tag firing.
Let me check both domains for consent setup and tag firing.No consent banner visible on goldenvisas.mercan.com. Let me check the consent state and tag firing status.Interesting — goldenvisas.mercan.com has **all consent granted by default** with no CMP (no Cookiebot, OneTrust, etc.). GTM-K6864NBH is loaded. That's not the problem there. Let me check mercan.com now.Let me read the screenshot proper
## The Problem: mercan.com Blocks ALL Tracking for UK Visitors
On **mercan.com**, Google Site Kit's consent mode script (`googlesitekit-consent-mode`) is setting this default:
...for **32 countries including GB (United Kingdom)**. And there is **NO consent banner/CMP installed** to ever flip these to `granted`. So for UK visitors:
- Google Ads conversion tags **never fire**
- GA4 **never collects data**
- Attribution is **completely dead**
This is why the subdomain isn't delivering — if you point the UK campaign at mercan.com pages, conversions will be invisible.
**goldenvisas.mercan.com** is fine — consent is `granted` by default (different GTM container: GTM-K6864NBH vs GTM-WZKDXFH8 on mercan.com).
## Two Fix Options
### Option A: Plugin (Recommended — proper compliance)
Install a WordPress CMP plugin like **Complianz** or **CookieYes** on mercan.com. It will:
1. Show a consent banner to UK/EU visitors
2. Automatically update Google Consent Mode to `granted` when users accept
3. Keep you UK GDPR compliant
This is the right fix if you plan to run UK campaigns pointing to mercan.com long-term.
### Option B: GTM Quick Fix (faster, less compliant)
In GTM container **GTM-WZKDXFH8** (mercan.com), add a **Consent Initialization** tag that overrides Site Kit's defaults and grants consent. Faster to deploy but skips the consent banner — not ideal for UK GDPR.
### Option C: Disable Site Kit Consent Mode (quickest)
In WordPress → Site Kit → Settings → disable the consent mode feature entirely. All tags fire immediately. Fastest fix but no compliance.
**My recommendation**: If you want to test mercan.com with new UK campaigns quickly, **Option C** (disable Site Kit consent mode) gets you live today. Then install Complianz (Option A) within a week for proper compliance.
Which approach do you want to go with? And do you want me to check if I can access the Site Kit settings via the WordPress admin, or should we go the GTM route?
— *GTM Specialist*