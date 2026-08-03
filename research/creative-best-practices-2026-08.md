# Google Ads Creative Best Practices — Evidence Report for the Unified Creative Engine

**Compiled:** 2026-08-03 · **Author:** Dam3oun-Google research agent · **Feeds:** BMAD product brief for the unified creative engine (shared core → PMax + Demand Gen + Responsive Display builders)

**Method:** Google official docs (help + developer) treated as top authority, then large-sample practitioner studies, then opinion posts. Every claim carries a source URL and a "why trust" note. Anything unconfirmed is marked **UNVERIFIED**. Where sources conflict, the conflict is stated and ranked. Prefer 2025-2026 sources.

---

## 1. Executive Top-10 — "Bake this into the engine"

Ranked by evidence strength × leverage on our three builders.

| # | Requirement | One-line rationale | Source |
|---|---|---|---|
| 1 | **Store text limits per-campaign-type, NOT globally — Demand Gen headline is 40 chars, PMax/RDA/Search are 30.** | A shared copy workbench that hard-codes 30 silently truncates 10 chars of DG message on every ad. | [Google Ads Help – DG image asset specs](https://support.google.com/google-ads/answer/17140672?hl=en) |
| 2 | **Treat video as OPTIONAL but strongly-recommended for PMax; never block asset-group creation on a missing video.** | Google auto-generates slideshow video from images when none supplied — so the engine can ship without one, but should nudge the user to add one. | [Google Ads Help – PMax video assets](https://support.google.com/google-ads/answer/14528532?hl=en) |
| 3 | **Enforce asset DIVERSITY, not asset MAXIMISATION — each headline must carry a distinct angle; do not generate 5 rewordings of one idea.** | Practitioner + Google both: variety of *message*, not raw count, is the real signal; filler assets don't help. | [Groas PMax creative strategy](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs) · [Google Ad Strength](https://support.google.com/google-ads/answer/14143250?hl=en) |
| 4 | **Do NOT optimise the copy generator to "fill all characters" — favour concise headlines.** | 1M+-ad study: shorter headlines had better CTR & conversion rate; max-length is a dead heuristic. | [Optmyzr Ad Strength study (1M+ ads)](https://www.optmyzr.com/blog/google-ad-strength-study/) |
| 5 | **Treat Ad Strength as a completeness checklist, not a performance target — surface it, don't chase "Excellent".** | Same study: "Average" RSAs beat "Excellent" on CPA/ROAS; Ad Strength ≠ performance. Google itself calls it "directional, not a guarantee." | [Optmyzr study](https://www.optmyzr.com/blog/google-ad-strength-study/) · [Google Ad Strength](https://support.google.com/google-ads/answer/14143250?hl=en) |
| 6 | **Support all three image aspect ratios as a first-class batch output: landscape 1.91:1, square 1:1, portrait 4:5 — generate every asset in all three.** | Missing ratios shrink eligible placements; portrait unlocks Shorts/mobile-feed inventory. | [Google Ads Help – DG image specs](https://support.google.com/google-ads/answer/17140672?hl=en) · [Google PMax creative best practices](https://support.google.com/google-ads/answer/14528221?hl=en) |
| 7 | **Default image generation to LOW/NO text overlay for RDA & DG; keep a text-on-image mode for PMax display, gated with a warning.** | Google discounts images >20% text and can't swap baked-in headlines (RDA); but PMax practitioners argue burning the hook in grabs attention. Genuine conflict — see §6. | [Google RDA best practices](https://support.google.com/google-ads/answer/9823397?hl=en) · [Solutions 8](https://sol8.com/performance-max-image-assets/) |
| 8 | **Logo generation must be a toggle (with-logo / no-logo) AND keep logo OFF the photo for RDA/DG; supply logo as a separate asset slot.** | Google: "Don't overlay a logo on top of an image" for RDA — logo is its own asset (1:1 + 4:1). Tools (AdCreative/Flair) expose logo as separate on/off layer. | [Google RDA best practices](https://support.google.com/google-ads/answer/9823397?hl=en) · [AdCreative.ai](https://www.semrush.com/kb/1424-adcreative-ai) |
| 9 | **Keep the primary subject inside the centre ~80% (safe zone); crops differ per placement, so never place key content at edges.** | Google crops to fit each surface; edge content and logos get clipped (e.g. ~21% of a Gmail circular logo). | [PixExact PMax specs](https://www.pixexact.com/blog/performance-max-image-specs) · [Google DG image specs](https://support.google.com/google-ads/answer/17140672?hl=en) |
| 10 | **Build a refresh-cadence prompt into the engine: rotate 2-3 assets at a time on a rolling cycle, never swap all at once.** | Wholesale swaps reset algorithm learning; staggered refresh cut CPAs ~28% in cohort data. | [Groas PMax strategy](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs) · [Superads refresh cadence](https://www.superads.ai/blog/creative-refresh-cadence) |

---

## 2. Per-campaign-type spec tables (with citations)

> **Authority note:** Character limits and asset counts below are taken from Google's own help pages where possible (highest authority). Where only aggregator sources carry a field, that's flagged. Google occasionally raises limits mid-year, so the engine should treat these as config, not constants.

### 2a. Performance Max — asset group

| Field | Min | Max | Char / size limit | Source |
|---|---|---|---|---|
| Short headline | 3 | 15 | 30 chars | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Long headline | 1 | 5 | 90 chars | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Description | 3 | 5 | 90 chars each (one short description historically capped 60 — see note) | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Business name | 1 | 1 | 25 chars | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Call to action | 1 | 1 | Automated/enum | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Final URL | 1 | 1 | 2048 chars | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Image — Landscape 1.91:1 | 1 | 20 | rec 1200×628 (min 600×314), JPG/PNG ≤5 MB | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) · [PixExact](https://www.pixexact.com/blog/performance-max-image-specs) |
| Image — Square 1:1 | 1 | 20 | rec 1200×1200 (min 300×300), ≤5 MB | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Image — Portrait 4:5 | 0 | 20 | rec 960×1200 (min 480×600), ≤5 MB | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Logo — Square 1:1 | 1 | 5 | rec 1200×1200 (min 128×128), ≤5 MB | [PixExact](https://www.pixexact.com/blog/performance-max-image-specs) |
| Logo — Landscape 4:1 | 0 | 5 | rec 1200×300 (min 512×128) | [adnabu](https://blog.adnabu.com/google-ads/performance-max-ad-specs/) |
| Video | 0 (optional) | 15 per orientation (see §6 conflict) | 16:9 / 1:1 / 9:16; ≥10 s; MP4/MPG 1080p | [Google Ads Help](https://support.google.com/google-ads/answer/14528532?hl=en) · [hawky.ai](https://hawky.ai/blog/performance-max-creative-specs-guide) |

**Note on descriptions:** Multiple aggregators report all descriptions ≤90 chars; some spec sheets and the Google Ads UI historically require one *short* description ≤60 chars plus up to four ≤90. Treat the 60-char short-description as **UNVERIFIED against a live 2026 Google help page** — the engine should validate against the API at write time rather than trust a fixed number.

**Total image ceiling:** Up to 20 images shared across ratios per asset group ([hawky.ai](https://hawky.ai/blog/performance-max-creative-specs-guide)). Safe zone: primary subject within centre 80% of frame ([PixExact](https://www.pixexact.com/blog/performance-max-image-specs)).

### 2b. Demand Gen — single image ad (per ad)

| Field | Min | Max | Char / size limit | Source |
|---|---|---|---|---|
| Headline | 3 | 5 | **40 chars** | [Google Ads Help – DG image specs](https://support.google.com/google-ads/answer/17140672?hl=en) |
| Long headline | — | — | 90 chars (video/broader formats) | [ClickPatrol 2026 guide](https://clickpatrol.com/google-ads-character-limits-2026-guide-headlines/) |
| Description | 3 | 5 | 90 chars | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| Business name | 1 | 1 | 25 chars | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| Call to action | — | — | ~10 chars / enum (video format) | [ClickPatrol](https://clickpatrol.com/google-ads-character-limits-2026-guide-headlines/) |
| Images | 1 | 20 per ad | JPG/PNG ≤5 MB | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| — Square 1:1 | | | rec 1200×1200 (min 300×300) | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| — Horizontal 1.91:1 | | | rec 1200×628 (min 600×314) | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| — Vertical 4:5 | | | rec 960×1200 (min 480×600) | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| — Vertical 9:16 | | | rec 1080×1920 (min 600×1067) | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| Logo — Square 1:1 | required | | rec 1200×1200 (min 144×144), ≤150 KB | [Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en) |
| Video | optional | | 16:9 / 1:1 / 4:5 / 9:16; MPG (MPEG-2/4) 1080p; ≥5 s | [Google Ads Help – DG asset specs](https://support.google.com/google-ads/answer/13704860?hl=en) |

**Gmail crop warning:** Google states ~21.46% of a square logo is cropped when rendered as a circular Gmail logo — keep logo mark centred ([Google Ads Help](https://support.google.com/google-ads/answer/17140672?hl=en)).

### 2c. Responsive Display Ads (per ad)

| Field | Min | Max | Char / size limit | Source |
|---|---|---|---|---|
| Short headline | 1 | 5 | 30 chars | [lineardesign 2026](https://lineardesign.com/blog/google-ads-display-ad-sizes/) |
| Long headline | 1 | 1 | 90 chars | [lineardesign](https://lineardesign.com/blog/google-ads-display-ad-sizes/) |
| Description | 1 | 5 | 90 chars | [lineardesign](https://lineardesign.com/blog/google-ads-display-ad-sizes/) |
| Business name | 1 | 1 | 25 chars | [lineardesign](https://lineardesign.com/blog/google-ads-display-ad-sizes/) |
| Image — Landscape 1.91:1 | 1 | up to 15/ratio | rec 1200×628 (min 600×314), ≤5 MB | [digitalapplied 2026](https://www.digitalapplied.com/blog/google-ads-image-sizes-2026-formats-specs) |
| Image — Square 1:1 | 1 | up to 15/ratio | rec 1200×1200 (min 300×300) | [digitalapplied](https://www.digitalapplied.com/blog/google-ads-image-sizes-2026-formats-specs) |
| Image — Portrait 4:5 | 0 (optional) | | rec 1200×1500 (min 320×400) | [digitalapplied](https://www.digitalapplied.com/blog/google-ads-image-sizes-2026-formats-specs) |
| Logo — Square 1:1 | 1 | 5 | rec 1200×1200 (min 128×128), ≤5 MB | [lineardesign](https://lineardesign.com/blog/google-ads-display-ad-sizes/) |
| Logo — Landscape 4:1 | 0 | 5 | rec 1200×300 (min 512×128) | [lineardesign](https://lineardesign.com/blog/google-ads-display-ad-sizes/) |
| Video | optional | 5 | ≤30 s recommended | [udonis 2026](https://www.blog.udonis.co/digital-marketing/google-ads/google-display-ad-sizes) |

**Text-in-image rule (RDA-critical):** "no more than 20% of your display asset should be text" and Google discounts assets exceeding it; overlaid text can be unreadable at small sizes and blocks headline-swapping ([Google RDA best practices](https://support.google.com/google-ads/answer/9823397?hl=en)). Also: image should not be >80% blank space; subject must be the focus.

---

## 3. Two spec questions — verdicts

### Q1 — Demand Gen headline: 30 or 40? → **40 characters. DEFINITIVE.**

> "Headlines … Max. character: **40** … Upload at least 3 unique headlines. Up to 5 headlines per ad."
> — **Google Ads Help, "About image assets specifications … for Demand Gen campaigns"** ([support.google.com/google-ads/answer/17140672](https://support.google.com/google-ads/answer/17140672?hl=en))

Corroborated by the 2026 character-limit cheat sheets: "Demand Gen headlines allow 40 characters, where Search, Performance Max and Display all stop at 30." ([ClickPatrol 2026 guide](https://clickpatrol.com/google-ads-character-limits-2026-guide-headlines/)).

**Why trust:** primary source is Google's own current help page; independent 2026 practitioner references agree. **Engine action:** DG headline field = 40; all other headline fields (Search/PMax/RDA) = 30. The 40-char allowance is a feature to exploit, not a rounding error — the DG copy path should use the extra 10 chars deliberately.

### Q2 — Is PMax video truly optional? → **YES, optional; Google auto-generates from images. But omitting it has real consequences. RECOMMEND supplying one.**

> "If you don't add a video to your Performance Max asset group, then one or more videos may be auto-generated from the assets in your asset group."
> — **Google Ads Help, "About video assets for Performance Max campaigns"** ([support.google.com/google-ads/answer/14528532](https://support.google.com/google-ads/answer/14528532?hl=en))

Consequences Google itself names:
- Auto-generated slideshow video is lower quality than a purpose-built one.
- "Performance Max campaigns that use auto-generated videos may show customers who visit your landing page a different product than the one featured in your video" (product-mismatch risk) ([Google Ads Help](https://support.google.com/google-ads/answer/14528532?hl=en)).
- Google's Ad Strength page pushes uploading your own videos (horizontal + square + vertical) to reach "Excellent" ([Google Ad Strength](https://support.google.com/google-ads/answer/14143250?hl=en)).

Practitioner corroboration: "Manually created videos outperform auto-generated by 25 to 40%" and video "unlocks significant additional reach" on YouTube/Discover ([Groas](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs)) — treat the 25-40% figure as a single-vendor claim, directionally useful, not a Google-verified number.

**Engine action:** never hard-require video for asset-group creation (Q2 confirms it isn't required), but surface a persistent "add your own video to beat the auto-generated one" recommendation, and offer to generate one via the video path. Also warn about the landing-page/product-mismatch when relying on auto-gen.

---

## 4. Practitioner practices (ranked by authority)

**A. Asset counts that practitioners actually target (converges with Google Ad Strength):**
- Ideal PMax asset group ≈ **10-15 images** (product shots + lifestyle + close-ups + contextual use), **2-3 videos** in different lengths/formats, all 5 short headlines, 5 long headlines, 5 descriptions ([Groas](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs)).
- Google's own "Excellent" recipe: all 15 headlines, all 5 descriptions, own videos in all 3 orientations, 4+ images per ratio, ≥6 sitelinks; claims advertisers reaching Excellent see "on average, 6% more conversions" ([Google Ad Strength](https://support.google.com/google-ads/answer/14143250?hl=en)). **Why trust with caution:** Google-reported aggregate, self-serving; the Optmyzr study (below) contradicts the premise that Ad Strength predicts performance.

**B. Angle/hook taxonomy (bake into the copy workbench as generation modes):** promotional · feature-focused · benefit-driven · urgency-based · social-proof — "Each headline should communicate a different value proposition… Do not write 5 variations of the same headline." ([Groas](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs)).

**C. The big contrarian finding (highest sample size, 1M+ ads / 22k+ accounts):** Ad Strength does **not** correlate with performance — RSAs with "Average" Ad Strength delivered the best CPA, conversion rate and ROAS; "Excellent" underperformed; CTR barely moved across strength tiers. Shorter headlines beat maxed-out ones. ([Optmyzr Ad Strength study](https://www.optmyzr.com/blog/google-ad-strength-study/)). **Why trust:** largest independent dataset found; but note it could not pull asset-level PMax data, so its PMax read is indirect.

**D. Image style — split by campaign type (see §6 conflict):**
- Google (RDA/DG): images must have the product/brand as focus, <80% blank, <20% text, no logo overlaid on photo ([Google RDA best practices](https://support.google.com/google-ads/answer/9823397?hl=en)).
- Solutions 8 (PMax display): *add* copy to images — headline + 4-5-word benefit + discount + USP + urgency + CTA — because Display images compete with surrounding page content, unlike a text-native Search ad ([Solutions 8](https://sol8.com/performance-max-image-assets/)).
- Groas: "burn your best hooks directly into the visual" since Google can't guarantee pairing a specific description with a specific image ([Groas creative strategy](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs)).

**E. Refresh cadence (build a scheduler prompt):** weekly review of asset ratings → replace "Low" assets every 2-3 weeks → major static refresh every 4-6 weeks → video refresh every 8-12 weeks; **never swap all assets at once** (resets learning) ([Groas](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs)). Cross-platform fatigue signals: frequency >2.5-4.0, CTR down 20-30% over 3-7 days, CPA drift; structured rotation (new launches, not edits) linked to ~28% lower CPAs ([Superads](https://www.superads.ai/blog/creative-refresh-cadence)). **Why trust:** vendor cohort data, directional not causal.

**F. Asset-level feedback loop:** PMax reports asset ratings Low / Good / Best — mine "Best" assets as templates for the next generation batch ([Stackmatix](https://www.stackmatix.com/blog/performance-max-creative-practices)).

---

## 5. Scraper extraction contract (for our page-asset scraper)

How the best tools scrape brand assets from a landing-page URL, and the contract we should implement.

**What tools extract from a URL (AdCreative.ai "Import Brand"): name, logos, colors, fonts** — "The tool will scan the individual URLs you provide and identify your name, logos, colors, and fonts." One-click, then editable in Advanced Setup (swap logo, pick font) ([AdCreative.ai via Semrush KB](https://www.semrush.com/kb/1424-adcreative-ai)).

**Firecrawl branding extraction** returns structured fields — logo as URL, colors as hex, typography as named font families, plus spacing scale/UI styles — via a **full browser render** (not stylesheet-only parsing), so it survives design-in-JS / Wix / Framer sites where CSS parsing fails ([Firecrawl glossary](https://www.firecrawl.dev/glossary/web-extraction-apis/extract-website-branding)).

**webclaw brand extraction** returns a concrete field set we can copy: `logo_url`, `favicon_url`, `colors[]` (hex + inferred role primary/text/background + frequency count), `fonts[]` — colors ranked by frequency in HTML+inline CSS then role-inferred; fonts from stylesheet parsing ([webclaw](https://webclaw.io/use-cases/brand-extraction)).

**Recommended extraction contract for our engine:**

| Field | Source heuristic | Notes |
|---|---|---|
| `brand_name` | `<title>` / `og:site_name` / logo alt-text | AdCreative extracts name; webclaw does not — belt-and-braces both |
| `logo_url` (+ `logo_dark`) | header `<img>`/`<svg>`, `og:image`, background-image logos | full-render to catch CSS/background logos (Firecrawl lesson) |
| `favicon_url` | `<link rel=icon>` | fallback anchor for the mark |
| `colors[]` | hex from HTML + inline/computed CSS, ranked by frequency, role-inferred (primary/bg/text) | prefer computed-style over source CSS |
| `fonts[]` | `font-family` declarations, named families | map to nearest available generation font |
| `hero_images[]` / `product_images[]` | large in-viewport `<img>` + `og:image` | anchor images for asset-anchored generation mode |
| `claims[]` / `headlines[]` | H1/H2, hero copy, meta description | feed the copy workbench + our pinned-claims injection (accuracy gate applies) |

**Two design requirements this implies:**
1. Use a **headless/full browser render**, not raw HTML fetch — CSS-in-JS and modern site builders defeat stylesheet parsing.
2. The scraper output is a *brand kit object* that becomes the shared input to all three generation modes (logo / no-logo / asset-anchored) and to the copy workbench (claims → headline seeds, subject to the fact-accuracy gate already in our stack).

**Logo-on / logo-off & batch-resize (generation modes to build):**
- AdCreative pattern: upload/import logo + brand colors + brand description, then generate — logo is a *separate composited layer*, editable/removable, not baked into the base image ([AdCreative.ai](https://www.semrush.com/kb/1424-adcreative-ai)). This directly supports a with-logo/no-logo toggle.
- Flair.ai / AdGPT: product image + brand elements composited as overlays (logo, colors, product name) rather than regenerated — cleaner than re-prompting ([search set](https://flair.ai/), [AdGPT](https://adgpt.com/)).
- Smartly.io AI Studio: one approved creative concept → auto crop/resize into per-platform aspect ratios (Stories, feed, pins) — the model for our **batch-across-aspect-ratios** output ([Smartly.io AI Studio](https://www.smartly.io/resources/smartlys-ai-studio-expands-product-availability-to-help-advertisers-elevate-creative-with-gen-ai)).

**Engine takeaway:** generate the base image once, then composite logo as a removable layer (respecting the RDA "no logo on photo" rule by keeping it a separate asset slot), and auto-derive 1.91:1 / 1:1 / 4:5 (+9:16) crops with subject kept in the centre-80% safe zone.

---

## 6. Conflicts & how we ranked them

1. **Text-on-image: Google says minimise, PMax practitioners say maximise.**
   - Google (RDA/DG, top authority): images >20% text are discounted; overlaid text blocks headline-swapping and is unreadable small ([Google RDA](https://support.google.com/google-ads/answer/9823397?hl=en)).
   - Solutions 8 + Groas (PMax display, practitioner): put the hook *on* the image because Display competes for attention and Google can't guarantee text-image pairing ([Solutions 8](https://sol8.com/performance-max-image-assets/), [Groas](https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs)).
   - **Resolution:** platform-specific. Default RDA & DG image generation to clean/low-text (obey Google's discount rule); offer a text-on-image mode for PMax display assets, warned. Do NOT apply one global text policy.

2. **PMax video max count: 5 vs 15 per orientation.** adnabu says up to 5/orientation; Google's help page and 2026 spec guides say up to 15 ([Google Ads Help](https://support.google.com/google-ads/answer/14528532?hl=en), [hawky.ai](https://hawky.ai/blog/performance-max-creative-specs-guide)). **Resolution:** trust Google (15) but validate against the live API at write time — this is exactly the kind of limit Google raised mid-2025/2026.

3. **Does Ad Strength "Excellent" help?** Google claims +6% conversions at Excellent ([Google](https://support.google.com/google-ads/answer/14143250?hl=en)); Optmyzr's 1M+-ad study finds no correlation and "Average" often winning ([Optmyzr](https://www.optmyzr.com/blog/google-ad-strength-study/)). **Resolution:** larger independent sample outranks the vendor's own aggregate — treat Ad Strength as a *completeness* nudge, not a KPI. Fill the slots for coverage, but never sacrifice concise/varied copy to chase the meter.

4. **PMax description char nuance (60 vs 90).** Flagged **UNVERIFIED** — validate at API write time (see §2a note).

---

## 7. Sources (grouped by authority)

**Tier 1 — Google official (help + developer):**
- DG image asset specs (Q1 verdict): https://support.google.com/google-ads/answer/17140672?hl=en
- DG creative asset specs & guidelines: https://support.google.com/google-ads/answer/13704860?hl=en
- DG campaign specs & format requirements: https://support.google.com/google-ads/answer/17091672?hl=en
- PMax video assets (Q2 verdict): https://support.google.com/google-ads/answer/14528532?hl=en
- PMax build an asset group: https://support.google.com/google-ads/answer/10724492?hl=en
- PMax best practices for creative assets: https://support.google.com/google-ads/answer/14528221?hl=en
- PMax best practices for asset groups: https://support.google.com/google-ads/answer/14528220?hl=en
- Performance Max Ad Strength: https://support.google.com/google-ads/answer/14143250?hl=en
- Best practices guide for responsive display ads: https://support.google.com/google-ads/answer/9823397?hl=en
- Tips for creating effective display ads: https://support.google.com/google-ads/answer/1722134?hl=en
- Assets in a Performance Max campaign (developer): https://developers.google.com/google-ads/api/performance-max/assets
- Think with Google — Creative in PMax Playbook (PDF): https://www.thinkwithgoogle.com/_qs/documents/18344/Google_UKI___Creative_in_Performance_Max_Playbook.pdf

**Tier 2 — large-sample / practitioner studies:**
- Optmyzr Ad Strength study, 1M+ ads / 22k+ accounts: https://www.optmyzr.com/blog/google-ad-strength-study/
- Optmyzr PMax 24,702-campaign analysis: https://www.optmyzr.com/blog/performance-max-2025-updates-study-analysis/

**Tier 2 — specialist practitioners:**
- Solutions 8 — PMax image assets: https://sol8.com/performance-max-image-assets/
- Groas — PMax creative strategy: https://www.groas.com/post/performance-max-creative-strategy-how-to-feed-the-algorithm-what-it-actually-needs
- Groas — PMax video assets specs/strategy: https://www.groas.com/post/performance-max-video-assets-specs-creative-strategy-guide-2026
- Stackmatix — PMax creative best practices: https://www.stackmatix.com/blog/performance-max-creative-practices

**Tier 3 — spec aggregators (2026, cross-checked):**
- adnabu PMax specs: https://blog.adnabu.com/google-ads/performance-max-ad-specs/
- hawky.ai PMax creative specs: https://hawky.ai/blog/performance-max-creative-specs-guide
- PixExact PMax image specs: https://www.pixexact.com/blog/performance-max-image-specs
- digitalapplied Google Ads image sizes 2026: https://www.digitalapplied.com/blog/google-ads-image-sizes-2026-formats-specs
- lineardesign display ad sizes 2026: https://lineardesign.com/blog/google-ads-display-ad-sizes/
- udonis Google display ad sizes 2026: https://www.blog.udonis.co/digital-marketing/google-ads/google-display-ad-sizes
- ClickPatrol character limits 2026: https://clickpatrol.com/google-ads-character-limits-2026-guide-headlines/

**Tier 2/3 — creative-ops & refresh cadence:**
- Superads creative refresh cadence 2026: https://www.superads.ai/blog/creative-refresh-cadence
- Singular creative fatigue 2025: https://www.singular.net/blog/creative-fatigue/

**Tool teardowns (scraper + generation modes):**
- AdCreative.ai (Import Brand) via Semrush KB: https://www.semrush.com/kb/1424-adcreative-ai
- Firecrawl brand extraction: https://www.firecrawl.dev/glossary/web-extraction-apis/extract-website-branding
- webclaw brand extraction API: https://webclaw.io/use-cases/brand-extraction
- Smartly.io AI Studio (batch resize): https://www.smartly.io/resources/smartlys-ai-studio-expands-product-availability-to-help-advertisers-elevate-creative-with-gen-ai
- Flair.ai (product/logo compositing): https://flair.ai/
- AdGPT (brand-element overlays): https://adgpt.com/

---

*UNVERIFIED items to re-check at build time: (1) PMax short-description 60-char cap; (2) exact PMax video max per orientation (5 vs 15) — validate both against the live Google Ads API. Single-vendor performance figures (25-40% manual-video lift, +6% Excellent conversions, 28% CPA improvement from staggered refresh) are directional, not independently confirmed.*
