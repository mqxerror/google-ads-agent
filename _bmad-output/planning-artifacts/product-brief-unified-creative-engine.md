---
type: product-brief
project: Google Ads Agent — Unified Creative Engine
date: 2026-08-03
author: Wassim (drafted by Dam3oun-Google)
status: draft
inputs: research/creative-best-practices-2026-08.md · ~/Documents/LangarAI/data/gads-creative-gap-analysis-2026-08-03.md
related: product-brief-v2.md (parent product), feature-log.md rows 2026-07-28 (DG wizard birth)
---

# Product Brief — Unified Creative Engine

## Executive Summary

Today the repo has TWO creative wizards (Demand Gen, PMax) that duplicate and diverge: DG got the
"fully-assisted" treatment on 2026-07-28 (brief, brand preset, reference photos, policy hints); PMax
never got the backport [audit §A/§B]. Both hardcode text limits — and hardcode them WRONG for DG
(30 chars enforced where Google allows 40 — 25% of headline space thrown away on every DG campaign
[research §3-Q1, audit §B]). Neither has angle-aware drafting, duplicate detection, durable drafts,
a page-asset scraper, or a batch image pipeline; and there is no Display builder at all.

The Unified Creative Engine is **ONE creative core, MANY thin wizard shells**. The core owns the
four capabilities every Google asset campaign needs — Copy Workbench, Image Engine, Page Asset
Scraper, Draft Persistence — plus a Coverage/Rationale panel. PMax, Demand Gen, and a NEW
Responsive Display Ad builder are its first three consumers. A shell contributes only what is
genuinely type-specific (PMax: video + audience signals; DG: channels; RDA: nothing new).

## Vision (owner's words, 2026-08-03)

> "A unified system between all google campaigns that can use the same components — like higgsfield
> and ad generator (with logo / without / with asset) — and also can scrape assets from the page;
> this applies to demand gen and display campaigns also."

Architectural spine: **one creative core, many thin wizard shells.** The proof the core is real:
the Display builder ships as an almost-empty shell.

## Problem Statement (evidence-grounded)

1. **The assist layer exists once, not everywhere.** PolicyHint, brand preset, reference-photo
   conditioning, business-name counter, confirm-modal — all DG-only [audit §B table]. PMax, the
   bigger spend surface, drafts copy with no policy block and no reference conditioning.
2. **Limits are constants, and constants drift.** DG headline is enforced at 30; Google's own help
   page says 40 ("Max. character: 40", support.google.com/google-ads/answer/17140672) [research
   §3-Q1 DEFINITIVE]. Client RULES and server validators are maintained separately and already
   disagree with Google: PMax server has no max_count on any text field, no business-name cap, no
   total-image cap, no search-themes cap [audit §B validation table].
3. **Copy quality has no system.** Angle diversity lives as one prose line in one prompt
   [audit C1b]; zero duplicate detection anywhere [audit C2d]; no per-row rewrite; drafting
   returns bare string lists.
4. **Image work is single-shot.** One slot, one generation; a 5-slot × 2-variant set is impossible
   in one action (aspects × variants > 6 hard-fails; Semaphore(6) ceiling) [audit C6d]; no
   safe-zone check despite every image being center-cropped to up to 5 ratios [audit C6h].
5. **Brand inputs are manual.** The landing page already gets 2-stage research for image prompts
   (`extract-brief`), but logo/colors/images/claims are never extracted as reusable assets, and the
   copy drafter re-fetches the page blind [audit C3a].
6. **Drafts are disposable.** One anonymous bundle per campaign type in localStorage; a second
   draft destroys the first; server-side draft-job stores are in-memory dicts lost on restart
   [audit C8b/C8d].

## Proposed Solution — the creative core

### Core component 0 — CREATIVE SPEC REGISTRY (the correctness groundwork)

A single backend module (`creative_specs.py`, pattern-sibling of `creative_images.py`'s slot
table) holding **limits as data, not constants**, per campaign type:

| Spec (examples) | PMax | Demand Gen | RDA | Source |
|---|---|---|---|---|
| Headline | 3–15 × 30 | 3–5 × **40** | 1–5 × 30 | [research §2a/§2b/§2c] |
| Long headline | 1–5 × 90 | — (format-dep. 90) | exactly 1 × 90 | [research §2] |
| Description | 3–5 × 90, ≥1 ≤60 (**UNVERIFIED** — verify at API write) | 3–5 × 90 | 1–5 × 90 | [research §2a note] |
| Business name | 25 | 25 | 25 | [research §2] |
| Image slots | 1.91:1/1:1 req, 4:5 opt, logo 1:1 + 4:1, ≤20 total | + 9:16 (Shorts) | ≤15/ratio, logo 1:1 + 4:1 | [research §2] |
| Video | **optional** (Google auto-generates) | optional | optional ≤5 | [research §3-Q2] |
| Search themes | ≤25 × ≤80 | — | — | [audit T1.1] |
| On-image-text policy | knob (see Image Engine) | forbid | forbid (>20% text discounted) | [research §6-1] |

- Served to the frontend (`GET /api/creative/specs`) so client RULES, server validators
  (`TEXT_RULES`, `_validate_bundle`), and drafter clamps (`_DG_DRAFT_LIMITS`) all read ONE object.
  **Why:** the DG 30-vs-40 bug is exactly the failure class of duplicated constants; three copies
  of the same table already disagree [audit §B]. **Rejected:** keeping mirrored client constants
  with a lint check — a lint can't catch "both sides agree on the wrong number".
- Fields carry `verified: true/false`; unverified limits (PMax short-description ≤60, video
  max/orientation 5-vs-15) validate softly locally and rely on the Google API error at write time
  [research §2a note, §6-2].
- **PMax validation-gap closures ship here, in the first epic:** max_count per text field,
  business-name ≤25, ≥1 short description (soft), ≤20 images per asset group, search themes
  ≤25 × ≤80, final-URL format — mirrored client-side [audit Tier 1.1]. The DG 40-char lift ships
  here too, with the drafter told to *use* the extra 10 chars deliberately [research §3-Q1].

### Core component 1 — COPY WORKBENCH

One shared text-asset editor replacing the per-wizard `TextList`s:

- **Drafting contract becomes `[{text, angle, tier}]`** (from bare string lists). Angle taxonomy
  seeded from evidence: promotional · feature · benefit · urgency · social-proof [research §4B],
  plus the existing DG prose angles (aspiration, specificity). Tier maps to Google's NATIVE slots
  (30-headline / 90-long-headline / 90-description / ≤60-short-description) — not Meta's
  short/long/long-form [audit C1c].
- **Angle chips per row** — visible tag, lock/regenerate by angle.
- **Per-row AI rewrite** — carries row index + current angle into the existing draft-job plumbing
  (poll + localStorage resume, `demand_gen.py:583-639` pattern) [audit C2a].
- **"Diversify the set"** — regenerate for angle spread; powered by **deterministic near-duplicate
  detection** (normalized token similarity), not an LLM judgment call. **Why deterministic:** the
  flag must be instant, free, and explainable on every keystroke; LLM is reserved for the rewrite
  actions it's good at. **Rejected:** LLM-scored similarity (slow, costs a turn, non-reproducible).
  Diversity-over-count is the evidence-backed goal: "variety of message, not raw count"
  [research #3], and shorter-beats-maxed [research #4, Optmyzr 1M+ ads].
- **Paste-multiline → split into rows** [audit C2b — cheap, both wizards inherit].
- Per-campaign-type limits come from the registry; the DG editor natively offers 40 chars.

### Core component 2 — IMAGE ENGINE

Built ON the existing spine — `creative_images.py` exact-aspect crop / min-size / 5MB transcode,
`StudioPanel` model picker + Enhance 3-angle prompts, reference conditioning via `upload_media`
`--image` flags, DB-row job lifecycle + SSE [audit "reuse" list — binding].

- **Three explicit generation modes** (the owner's "with logo / without / with asset"):
  1. **with-logo** — logo composited as a *removable layer* on the base render (AdCreative/Flair
     pattern [research §5]), never re-prompted in;
  2. **without-logo** — clean scene (current default);
  3. **asset-anchored** — reference-image conditioning (exists today for DG; backported to PMax).
  Per-type policy from the registry keeps Google's rule intact: for DG/RDA the logo ships in its
  *dedicated logo slot*, not overlaid on the photo [research #8]; the overlay composite is only
  offered where policy allows, with a warning.
- **On-image text = a policy knob, not a hardcode.** Current default (text-free, enforced in
  `prompt_drafter.py:189-191`) is KEPT for all Google slots — the audit calls it "a correct call,
  worth defending" [audit surprise #3] and Google discounts >20%-text images [research §2c]. The
  knob (`forbid | allow_warned`) exists so the PMax-display text-on-image school [research §6-1]
  can be enabled later without touching code.
- **Smart ASPECT Set** — the Google-shaped port of Meta's "smart image set" [audit Tier 3]: one
  approved art direction (existing Enhance flow) → batch-generate across ALL slots (1.91:1 · 1:1 ·
  4:5 · 9:16 · logo) × N variants → auto-assign each finished tile to its slot through the
  existing crop. Keyed on aspect-slot coverage because headline×image pairing does not exist on
  Google [audit C6e].
  - **Render queue is server-side**, extending the existing DB-row job store: waves under the
    Semaphore(6) ceiling, combined progress, per-tile retry, queue survives refresh/restart.
    **Why server-side:** client-side chunking dies with the tab and contradicts the repo's own
    DB-row-as-source-of-truth pattern. **Rejected:** raising the semaphore (it mirrors
    Higgsfield's real per-account 6-job limit) and client batching.
- **Safe-zone / subject-crop check** — subject bbox detected per tile; predicate: does the subject
  survive the center-crop to each destination ratio (center-80% rule [research #9])? Flag "subject
  will be cut" before submit; highest signal on 9:16 [audit C6h — "the single most Google-specific
  quality win available"]. Detector implementation is an open question (below).

### Core component 3 — PAGE ASSET SCRAPER

Given a landing-page URL, extract a **brand-kit object** into the asset library:

| Field | Heuristic | Feeds |
|---|---|---|
| `brand_name` | title / og:site_name / logo alt | business-name field |
| `logo_url` (+dark) / `favicon_url` | header img/svg, og:image, bg-image | logo slots + with-logo mode |
| `colors[]` (hex + role + frequency) | computed styles, role-inferred | art direction / prompts |
| `fonts[]` | font-family declarations | prompt styling |
| `hero_images[]` / `product_images[]` | large in-viewport img + og:image | asset-anchored references |
| `claims[]` / `headlines[]` | H1/H2, hero copy, meta description | Copy Workbench seeds |

(Contract per [research §5]; full-browser render required — CSS-in-JS sites defeat raw-HTML
parsing [research §5, Firecrawl lesson].)

- **UNIFY, don't duplicate:** this EXTENDS the existing `extract-brief` 2-stage page research
  (`studio.py:748`, `prompt_drafter.py:60-135`) — which today feeds image prompts only — into one
  extraction path whose output is (a) persisted brand-kit assets in the library (reusable across
  campaigns) and (b) the shared research object handed to BOTH the image path and the copy
  drafter [audit C3a]. **Rejected:** a second scraper service beside extract-brief — two fetchers
  of the same page with different opinions is the copy of the limits bug at the content layer.
- Scraped `claims[]` are *seeds*, and pass through the existing pinned-claims accuracy gate before
  entering copy — a scraped page can contain claims we must not repeat (cf. the Panama
  stay-requirement incident).

### Core component 4 — DRAFT PERSISTENCE

- **Named drafts in a server-side `creative_drafts` table** (SQLite, next migration in the V25+
  chain): `{name, campaign_type, account_id, bundle JSON, updated_at}`. localStorage remains as a
  keystroke write-through crash cache only. **Why straight to server:** doing a localStorage
  named-map first and migrating later is double work, and the restart-loss bug lives server-side
  too (in-memory draft-job dicts, `demand_gen.py:226,257`, `pmax.py:109,140` [audit C8d]) — draft
  jobs move to DB rows in the same stroke. **Rejected:** localStorage-keyed named drafts (no
  restart durability, no cross-browser, doesn't fix the job store).
- **JSON export/import** on the review step — cheap [audit C8c], and the interchange format is the
  same bundle the API accepts, so a draft is also a template.

### Coverage & Rationale panel (the honest meter)

- **Ad Strength is reframed as a completeness checklist, NOT a KPI** — the Optmyzr 1M+-ad study
  found "Average" RSAs beating "Excellent" on CPA/ROAS, and Google itself calls the meter
  "directional" [research #5, §6-3]. The panel therefore never says "reach Excellent"; it shows:
  **slot coverage** (headlines n/15, images n/20, aspect slots filled) · **angle diversity**
  (distinct angles present) · **near-duplicate count** (target: 0). Filling slots is encouraged
  for eligibility/coverage; maxing characters is not [research #4].
- **Rationale surface:** the page-research object (value_prop, audience, tone, claim_hints) is
  shown to the operator, and **suggested audiences become one-click PMax search themes / DG
  audience signals** — reusing research already computed [audit Tier 2.3, C3b].
- PMax video: never a hard gate (that removal is already in flight); the panel carries the
  persistent nudge "add your own video to beat the auto-generated slideshow" + the
  product-mismatch warning [research §3-Q2].

### NEW consumer — DISPLAY (Responsive Display Ads)

RDA slots are nearly identical to what the core already serves: short headlines 1–5 × 30, long
headline exactly 1 × 90, descriptions 1–5 × 90, business name 25, landscape + square images
(≤15/ratio), optional portrait, logos 1:1 + 4:1 [research §2c].

- New `RdaWizard` shell (brief → text → images → review) consuming Copy Workbench, Image Engine,
  scraper brand kit, drafts, coverage panel end-to-end. Backend: `rda_orchestrator` on the
  `demand_gen_orchestrator` pattern, reusing `creative_images.py` unchanged.
- RDA-specific rules ride in the registry, not in the shell: >20%-text images are discounted
  (generation default = clean) [research §2c], image not >80% blank, no logo overlaid on the
  photo [research #8], 4:1 landscape logo slot (currently absent repo-wide [audit §B]).
- **RDA is the acceptance test of the core:** the shell must contain zero creative logic — if
  building it requires touching core components, the core failed. Target: shell well under half
  of today's DemandGenWizard (1,294 lines).

## Reuse map (binding — build ON these, not around them)

| Existing asset | Role in the engine |
|---|---|
| `backend/google_ads/services/campaign/creative_images.py` | THE image spine: exact-aspect crop ±1%, min-size rejection, 5MB transcode, slot specs. Image Engine + safe-zone build on it [audit surprise #5] |
| `frontend/src/components/studio/StudioPanel.tsx` | Model picker, Enhance (Visual Director 3-angle), copy/image modes — Image Engine modes layer on it |
| `SlotThumb` crop preview (in wizards) | Kept everywhere — "genuinely better than anything in the benchmark" [audit surprise #4] |
| Studio DB-row job store + SSE (`studio.py`) | Batch render queue extends it; draft jobs migrate into it |
| `prompt_drafter.py` extract-brief 2-stage research | Scraper extends it into the brand kit; text-free image rule preserved as the default policy |
| `TextList` + draft-poll/resume plumbing | Evolves into Copy Workbench; job plumbing reused for rewrite/diversify |
| `LibraryPicker` / `AssetLibrary` + `ad_assets` table | Brand-kit assets persist here; reference picking unchanged |
| DG assist layer (PolicyHint, brand preset, ref photos, confirm modal) | Extracted into shared shell parts; PMax gets them by consumption [audit Tier 1.3] |

## Explicitly OUT of scope

- **Live ad-preview rail** — Google exposes no preview API for DG/PMax; a hand-built mock is fake
  fidelity ("a composition Google will never render" [audit §D]). Revisit only if Google ships one.
- **Canva integration** — Higgsfield is the generator; a second design tool adds surface, not
  capability [audit 4c].
- **Headline × image pairing control** — impossible on Google asset campaigns; the pairing axis
  here is aspect-slot coverage [audit C6e]. (RSA pinning for Search already exists.)
- **On-image headline baking as a default** — stays forbidden by default everywhere; only the
  policy knob exists [research §6-1].
- **Refresh-cadence automation** (rotate 2–3 assets, never all [research #10]) — belongs to the
  Scheduled Plans lane (V17), not this engine; noted for that backlog.

## Already IN FLIGHT separately (do not re-plan here)

Tier-0 bugs from the audit: 1.91:1 aspect-validation vs the model catalog, hardcoded push-to-ad
ids in `DemandGenCreative.tsx`, PMax video hard-gate removal [audit Tier 0].

## Phasing (sized; audit tiers as the starting shape)

| Phase | Contents | Size |
|---|---|---|
| **P1 — Spec truth + drafts** | Creative Spec Registry (limits as data, served to client) · ALL PMax validation-gap closures · DG 40-char lift · paste-multiline split + near-dup flag in TextList · named drafts + `creative_drafts` table + JSON export/import | **M** (~3–5 d) |
| **P2 — Copy Workbench + PMax parity ★** | `{text, angle, tier}` drafting contract · angle chips · per-row rewrite · Diversify-the-set · DG assist layer extracted to shared components, PMax consumes (PolicyHint, brand preset, reference conditioning, business-name counter, confirm modal) · coverage meter v1 (text coverage + diversity + dup count) | **L** (~1 wk) |
| **P3 — Image Engine** | Generation modes (with-logo layer / without / asset-anchored) · server-side batch renderer + queue UI · Smart ASPECT Set with auto-assign · safe-zone check · on-image-text policy knob · coverage meter extends to image slots | **L** (~1–2 wk) |
| **P4 — Scraper + rationale** | extract-brief → brand-kit extraction + library persistence · claims→copy seeds through the accuracy gate · rationale panel · one-click search themes / DG audience signals | **M** (~1 wk) |
| **P5 — Display consumer** | RDA registry entries (incl. 4:1 logo, text-discount rule) · `rda_orchestrator` · thin `RdaWizard` shell · shell-thinness acceptance check | **M** (~4–6 d) |

**★ USABLE FIRST (mid-P2, the earliest slice the owner can feel):** open the *PMax* wizard and get
the DG-grade assisted flow through shared components — brief + brand preset + reference photos →
draft → every row wears an angle chip → click **Diversify** → near-dupes flagged and replaced —
while the DG wizard, same components, now offers 40-char headlines. The audit already calls this
backport "the single biggest perceived-quality jump for the least code" [audit Tier 1.3]; the
engine makes it a consumption, not a copy-paste.

Order rationale: correctness before features (P1 makes every later phase validate against truth);
copy before image (the drafting-contract change ripples into rewrite/diversify/rationale); scraper
after Image Engine because asset-anchored mode already works with library photos today — the
scraper enriches it rather than blocking it; RDA last because it is the proof, not the driver.
**Rejected ordering:** building the RDA greenfield first "since it's clean" — it would grow its own
third copy of everything before the core exists.

## Key success metrics

1. Zero Google-side validation rejections for bundles that passed local validation (registry
   closes the client/server/Google gap).
2. DG drafts actually use >30-char headlines when the message earns it (the freed 25%).
3. One approved art direction → full slot set (all aspects + logo) auto-assigned with zero manual
   crop fixes, in one queued action.
4. Near-duplicate count = 0 on every submitted set; ≥4 distinct angles per headline set.
5. A named draft survives backend restart and round-trips through JSON export/import.
6. `RdaWizard` ships with zero creative logic in the shell and no core changes required.

## Constraints

- 100% local; drafting via Claude CLI subprocess (subscription, no API key); generation via
  Higgsfield CLI — all inherited from the parent product [product-brief-v2].
- Higgsfield per-account concurrency is 6 — the batcher schedules around it, never past it.
- Registry limits must be treated as config Google can change mid-year [research §2 authority
  note]; UNVERIFIED items stay soft until verified against the live API.

## Open questions (honesty over ambition)

1. **PMax short-description ≤60** — UNVERIFIED against a live 2026 Google page [research §2a
   note]. Proposed: soft-validate + verify at API write time. Confirm, or spend a session
   verifying against the API up front?
2. **Safe-zone detector implementation** — cheap heuristic (saliency/edge-energy via Pillow/OpenCV,
   free, weaker) vs a vision-model call per tile (better subject boxes, costs a call per image on
   every batch). Owner preference on spend?
3. **Scraper render substrate** — the full-browser-render requirement [research §5] needs headless
   Chrome. Add Playwright as a backend dependency, or route through the existing claude-in-chrome
   MCP (operator's browser), with plain-fetch fallback tiering? (Backend dep = works unattended;
   browser MCP = zero new deps but session-bound.)
4. **Text-on-image `allow_warned` for PMax display** — ship the knob wired but OFF in P3 (current
   plan), or expose it in the UI from day one? [research §6-1 conflict]
5. **Draft scope** — named drafts per account (proposed) or global? Affects the `creative_drafts`
   key and the library picker default filter.
6. **P4/P5 swap** — if Display campaigns are needed commercially before scraped brand kits,
   P5 can run before P4 (no dependency between them). Which is sooner: RDA launches or
   multi-client brand onboarding?

---

*Next step: PRD with functional requirements per phase, then architecture review focused on the
registry contract, the batch renderer, and the shared-component extraction seams.*
