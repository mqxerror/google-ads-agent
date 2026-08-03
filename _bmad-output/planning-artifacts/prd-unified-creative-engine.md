---
type: prd
project: Google Ads Agent — Unified Creative Engine
date: 2026-08-03
author: Wassim (drafted by Dam3oun-Google)
version: 1.0
status: draft — for architecture review
track: bmad-method
parent: prd-v2.md (V2 product PRD; this PRD scopes one subsystem)
inputDocuments: [product-brief-unified-creative-engine.md, research/creative-best-practices-2026-08.md, ~/Documents/LangarAI/data/gads-creative-gap-analysis-2026-08-03.md]
---

# PRD — Unified Creative Engine

**Citation key:** `[research §X]` = `research/creative-best-practices-2026-08.md` · `[audit §X]` =
`~/Documents/LangarAI/data/gads-creative-gap-analysis-2026-08-03.md` (repo @ `a0602d9`).
Every character/count limit in this document carries one of the two. Limits marked **UNVERIFIED**
follow the audit's instruction: soft-validate locally, verify against the live Google API at build/write time.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope](#2-scope)
3. [Decisions Adopted](#3-decisions-adopted-owner-defaults-2026-08-03)
4. [★ Usable-First Milestone](#4--usable-first-milestone-mid-p2)
5. [User Journeys](#5-user-journeys)
6. [Functional Requirements](#6-functional-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Registry Seed Data (normative)](#8-registry-seed-data-normative)
9. [API Contract & Data Model Changes](#9-api-contract--data-model-changes)
10. [Phasing & Exit Gates](#10-phasing--exit-gates)
11. [Success Metrics](#11-success-metrics)
12. [Risks](#12-risks-honest)
13. [Binding Reuse Map](#13-binding-reuse-map)

---

## 1. Executive Summary

The repo ships two creative wizards (Demand Gen, PMax) that duplicate and diverge: the DG wizard got
the fully-assisted layer on 2026-07-28, PMax never did, and both hardcode text limits — wrongly for
DG (30 enforced where Google allows **40** [research §3-Q1 DEFINITIVE]) and incompletely for PMax
(no server max_count on any text field, no business-name cap, no total-image cap [audit §B]).

The Unified Creative Engine is **one creative core, many thin wizard shells**. The core owns five
things: a **Creative Spec Registry** (limits as data, one source of truth), a **Copy Workbench**
(angle-aware drafting, per-row rewrite, deterministic near-dup detection), an **Image Engine**
(three generation modes, server-side batch renderer, safe-zone check), a **Page Asset Scraper**
(brand-kit extraction unified with the existing extract-brief path), and **Draft Persistence**
(named server-side drafts). A **Coverage & Rationale panel** replaces Ad-Strength-chasing with an
honest completeness meter [research #5, §6-3]. PMax and DG are migrated onto the core strangler-style
(DG+PMax first); a NEW **Responsive Display Ad** builder ships last as the proof the core is real —
its shell must contain zero creative logic.

Five phases: P1 spec truth + drafts → P2 Copy Workbench + PMax parity (★ usable-first lands mid-P2)
→ P3 Image Engine → P4 scraper + rationale → P5 Display consumer.

## 2. Scope

**In scope:** the six FR groups of §6, across PMax + Demand Gen + new RDA, backend and frontend,
building ON the binding reuse map (§13).

**Explicitly OUT of scope** (per brief): live ad-preview rail (no Google preview API for DG/PMax
[audit §D]) · Canva integration [audit 4c] · headline×image pairing control (impossible on Google
asset campaigns [audit C6e]) · on-image headline baking as a default [research §6-1] ·
refresh-cadence automation (belongs to Scheduled Plans V17 [research #10]).

**Already IN FLIGHT elsewhere — excluded from this PRD's scope and phases:** the audit's Tier-0
fixes: 1.91:1 aspect validation vs the model catalog, hardcoded push-to-ad ids in
`DemandGenCreative.tsx`, PMax video hard-gate removal [audit Tier 0]. FRs below assume these land
independently; no FR re-plans them.

## 3. Decisions Adopted (owner defaults, 2026-08-03)

Resolutions of the brief's open questions. Treated as decided; each is binding on the FRs below.

| # | Decision | Resolution | Consequence |
|---|---|---|---|
| D1 | Safe-zone detector | **Heuristic v1**: subject bounding box via cheap CV (Pillow/OpenCV saliency / edge-energy); vision-model call per tile DEFERRED | FR2.5 must run free and local; quality ceiling accepted (Risk R5) |
| D2 | Scraper substrate | **httpx + BeautifulSoup v1**; Playwright full-render as a LATER fallback phase. Rationale: v1 targets operator-OWNED landing pages, which are SSR | Conscious deviation from the research's full-browser-render recommendation [research §5, Firecrawl lesson]; CSS-in-JS sites get an explicit partial-extraction warning, not silent empties (FR3.2) |
| D3 | Text-on-image | Registry **policy knob from P1** (`forbid \| allow_warned`), default `forbid` for every campaign type; **NO UI exposure until Display ships (P5)** | FR1.6; the PMax-display text-on-image school [research §6-1] stays reachable by config, invisible in UI until P5 |
| D4 | Draft scope | Named drafts are **per-account** (`account_id` in the key) | FR4.1; library picker default filter follows account |
| D5 | Phase order | **P4 scraper before P5 Display** stands (no swap) | §10 ordering final |
| D6 | PMax short description ≤60 | Adopted as proposed in the brief: registry carries it with `verified: false`, soft-validate locally, **verify at API write time** [research §2a note — UNVERIFIED] | FR1.3/FR1.4; same treatment for PMax video max-per-orientation (5 vs 15 [research §6-2]) |

## 4. ★ Usable-First Milestone (mid-P2)

The earliest slice the owner can feel, per the brief: the PMax backport is "the single biggest
perceived-quality jump for the least code" [audit Tier 1.3] — delivered as consumption of shared
components, not copy-paste.

**Demo script (what Wassim clicks, what he sees):**

1. Open **Campaign Builder → PMax wizard**. Step 1 now shows the DG-grade assist layer: campaign
   brief textarea, corporate-brand preset toggle, reference-photos picker, business-name field with
   live 25-char counter — none of which PMax had before [audit §B table].
2. Fill the brief for a Panama QIP campaign, toggle brand preset, pick 2 reference photos from the
   library. Click **Draft with Creative Director**.
3. Drafts return as rows where **every row wears an angle chip** (benefit / urgency / social-proof /
   feature / promotional). The PolicyHint card sits beside the fields; the drafter obeyed the policy
   block (no prices, no guaranteed-approval claims).
4. Click **Diversify the set**. Two near-duplicate headlines get flagged instantly (deterministic,
   no LLM wait) and replaced with rows carrying missing angles. The coverage meter shows
   "11/15 headlines · 5 distinct angles · 0 near-dupes".
5. Switch to the **DG wizard**, same components: the headline editor now accepts **40 characters**
   [research §3-Q1] and the drafter visibly uses the extra room. Paste 3 lines into a headline field
   → 3 rows appear.
6. Click **Create** on PMax → the confirm-before-create modal (previously DG-only) appears.

**Milestone gate:** all six steps demonstrable live on the real Mercan account (create paused);
demo recorded as the P2 mid-point check with Wassim before P2 continues.

## 5. User Journeys

### Journey 1 — PMax campaign with the assisted flow (post-★, primary)

Wassim opens the PMax wizard for a new Panama QIP push. Step 1 offers the brief textarea, brand
preset, reference photos, business-name counter (all previously DG-only [audit §B]). He drafts
copy; rows return angle-tagged. The coverage meter reads "8/15 headlines · 4 angles · 1 near-dup".
He clicks the flagged row's rewrite, picks the missing `urgency` angle, and the row regenerates in
place while the rest stay locked. The panel nudges — not gates — on the missing video
[research §3-Q2]. He saves the bundle as named draft "panama-q3-v1" (survives any restart), exports
the JSON as a template for the Greece variant, and creates the campaign PAUSED behind the confirm
modal.

**Journey success:** zero Google-side rejections at create (registry parity); the draft and its
JSON template are reusable next week.

### Journey 2 — Full image set from one art direction (P3)

Inside the wizard's image step, Wassim approves one Enhance-drafted art direction, then clicks
**Generate the full set**. The preflight shows "10 tiles · est. N credits" (5 slots × 2 variants,
under the 20-tile cap). The queue renders tiles in waves of ≤6; he closes the laptop mid-run; on
reopen the queue resumes from DB state. Two 9:16 tiles come back flagged "subject will be cut" —
he checks them against the SlotThumb crop preview, retries one, accepts the other. Every finished
tile is already sitting in its slot, cropped.

**Journey success:** one action → all aspect slots filled with zero manual crop fixes (brief
metric #3); no batch ever hard-fails on the old `aspects × variants > 6` rule.

### Journey 3 — Brand kit once, campaigns forever (P4) and the RDA proof (P5)

Wassim points the scraper at an owned Mercan LP. It returns the brand kit — logo, colors, fonts,
hero shots, claim seeds (banned claims already filtered by the accuracy gate). The kit persists in
the asset library. In P5 he opens the new Display builder: four thin steps, every capability —
drafting, angle chips, image modes, drafts, coverage — already there because the shells share one
core. He builds a complete RDA from the same brand kit in minutes.

**Journey success:** the RdaWizard shell shipped with zero creative logic (brief metric #6);
brand assets extracted once are consumed by three campaign types.

## 6. Functional Requirements

Every FR carries an acceptance criterion (AC) an automated test can assert. Phase = when it ships.

### FR Group 1: Creative Spec Registry & Copy Workbench

#### 1a — Spec Registry (the correctness groundwork)

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR1.1 | Single backend module `creative_specs.py` holds ALL per-campaign-type creative limits **as data** (text tiers, counts, char caps, image slots, logo slots, video, search themes, on-image-text policy) for PMax, DG, RDA — pattern-sibling of `creative_images.py`'s slot table | For each limit currently enforced in `TEXT_RULES`, `_validate_bundle`, `_DG_DRAFT_LIMITS`, client `RULES` [audit §A/§B], a test asserts the enforcing code path reads the registry object — no local numeric constant. CI guard test (NFR-D1) fails on mirrored literals | P1 |
| FR1.2 | Registry served to the frontend via `GET /api/creative/specs`; client validation derives from the response, never from baked constants | Endpoint returns JSON with DG `headline.max_chars == 40` [research §3-Q1], PMax `headline.min_count == 3, max_count == 15, max_chars == 30` [research §2a], RDA `long_headline.count == 1, max_chars == 90` [research §2c]. Frontend test: mocking a changed spec value changes UI validation with zero client-code change | P1 |
| FR1.3 | Every registry field carries `verified: true/false`; unverified fields soft-validate (warn, don't block) and defer to the Google API error at write time | PMax short-description ≤60 is `verified: false` [research §2a note — UNVERIFIED, verify at build time]; PMax video 15/orientation `verified: false` [research §6-2]. A bundle violating ONLY a soft limit submits with a surfaced warning; violating a hard limit is rejected client AND server | P1 |
| FR1.4 | PMax validation-gap closures, all reading the registry: `max_count` per text field · business name ≤25 · ≥1 description ≤60 (soft, per D6) · ≤20 images total per asset group · search themes ≤25 × ≤80 · final-URL format — mirrored client-side [audit Tier 1.1, audit §B validation table] | Server rejects: 16 headlines; 26-char business name; 21st image across ratios; 26th search theme; 81-char theme; malformed final URL. Server accepts-with-warning: zero ≤60 descriptions. Each mirrored in a client validation test | P1 |
| FR1.5 | DG headline limit lifted 30 → **40** in the registry; DG drafter prompt instructed to use the extra 10 chars deliberately, not pad [research §3-Q1 DEFINITIVE; audit §B "worth re-checking"] | 40-char DG headline passes client+server; 41 rejected. Drafter prompt snapshot contains the 40-char instruction. Existing DG tests updated in the same change (NFR-M1) | P1 |
| FR1.6 | On-image-text policy knob in the registry from P1: `forbid \| allow_warned` per campaign type, default `forbid` everywhere (defending `prompt_drafter.py:189-191` [audit surprise #3]); **no UI control renders it before P5** (D3) | Registry serves the knob; prompt builder reads it (test: flipping rda→`allow_warned` in a fixture registry changes the emitted prompt). Component-tree test asserts no knob control is rendered in P1–P4 builds | P1 |

#### 1b — Copy Workbench

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR1.7 | Drafting contract becomes `[{text, angle, tier}]` (from bare string lists) for DG and PMax drafters. Angle taxonomy: promotional · feature · benefit · urgency · social-proof [research §4B] + aspiration · specificity (existing DG prose angles [audit C1b]). Tier maps to Google's NATIVE slots: 30-headline / 90-long-headline / 90-description / ≤60-short-description [audit C1c] | Draft job response parses into typed rows; every row's `angle` ∈ taxonomy, `tier` ∈ native slots; malformed rows dropped with a logged warning, never crash the apply path | P2 |
| FR1.8 | Angle chips per row: visible tag, per-row lock, regenerate-by-angle | Locked rows are absent from the regenerate request payload (assert body); regenerated rows return with the requested angle | P2 |
| FR1.9 | Per-row AI rewrite carrying row index + current angle through the existing draft-job plumbing (poll + localStorage resume, `demand_gen.py:583-639` pattern [audit C2a]) | Rewrite job for row *i* replaces only row *i*; a page refresh mid-job resumes polling and applies the result (resume-key test) | P2 |
| FR1.10 | **Diversify the set**: regenerate for angle spread, powered by **deterministic near-duplicate detection** (normalized token similarity — no LLM in the detection path) [audit C2d; research #3 diversity-over-count] | Fixture set with 2 known near-dupes: detector flags exactly those 2, same output on repeat runs, zero CLI subprocess invocations during detection (spy assert). Diversify replaces flagged rows and the new set's pairwise similarity is below threshold | P2 |
| FR1.11 | Paste-multiline → split into rows in the shared TextList [audit C2b], each row clamped to registry limits | Pasting 3 newline-separated lines into one row yields 3 rows; a 45-char pasted DG headline row shows over-limit state at 40, not 30 | P1 |
| FR1.12 | DG assist layer extracted into shared components and consumed by BOTH wizards: PolicyHint card · corporate-brand preset · reference-photos picker (`referenceAssetIds`/`referenceNote` in PMax `baseContext`) · business-name 25-char counter · confirm-before-create modal [audit Tier 1.3, §B table] | Each component exists exactly once (shared path); PMax wizard renders all five (component tests); DG wizard behavior unchanged — its existing test files stay green unmodified (NFR-M1) | P2 |
| FR1.13 | PMax drafter prompt reaches DG parity: policy block (no prices, no guaranteed-approval, no `~ \| +`, no em dashes) + drafts `business_name` [audit §B; `demand_gen.py:283-287` vs `pmax.py:155-169`] | PMax draft prompt snapshot contains the policy block; draft response includes a ≤25-char `business_name` | P2 |

### FR Group 2: Image Engine

Built ON the existing spine: `creative_images.py` exact-aspect crop, `StudioPanel` + Enhance,
reference conditioning, DB-row job lifecycle + SSE [audit reuse list — binding; §13].

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR2.1 | Three explicit generation modes: **with-logo** (logo composited as a removable layer on the base render, never re-prompted in [research §5 AdCreative/Flair pattern]) · **without-logo** (current default) · **asset-anchored** (reference conditioning; backported to PMax [audit 6b]) | `mode=with_logo` stores base render AND composite as separate assets (base recoverable); `mode=asset_anchored` from the PMax wizard passes `--image` reference flags (request spy); `mode=without_logo` emits no logo instruction in the prompt | P3 |
| FR2.2 | Logo-placement policy per campaign type from the registry: DG/RDA logo ships in its dedicated logo slot, never overlaid on the photo [research #8]; overlay composite offered only where policy allows, with warning | Requesting with-logo overlay under a `forbid`-overlay type returns the policy warning and routes the logo to the logo slot; under an allowing type, composite proceeds and the warning text is attached to the asset record | P3 |
| FR2.3 | **Smart ASPECT Set**: one approved art direction (existing Enhance 3-angle flow) → batch-generate across ALL slots (1.91:1 · 1:1 · 4:5 · 9:16 · logo) × N variants → each finished tile auto-assigned to its slot through the existing `creative_images.py` crop [audit Tier 3, C6g; batch-resize model per research §5 Smartly.io] | One request for 5 slots × 2 variants enqueues 10 tiles; on completion every tile is assigned to its declared slot and has passed the exact-aspect crop (±1% tolerance preserved); a failed tile leaves its slot empty with a per-tile retry affordance | P3 |
| FR2.4 | Render queue is **server-side**, extending the existing DB-row job store: waves under the Semaphore(6) ceiling, combined progress, per-tile retry, queue survives page refresh AND backend restart [audit C6d; brief "rejected: client batching"] | Instrumented test: a 10-tile batch never exceeds 6 concurrent Higgsfield jobs; killing the app context mid-batch and restarting recovers queue state from DB rows (completed tiles kept, pending tiles resumable); the old `aspects × variants > 6` hard-fail path is gone | P3 |
| FR2.5 | **Safe-zone / subject-crop check** (heuristic v1 per D1): subject bbox via cheap CV; predicate = subject survives the center-crop to each destination ratio (center-80% rule [research #9]); flags "subject will be cut" before submit — highest signal on 9:16 [audit C6h] | Fixture with edge-positioned subject is flagged for 9:16 and not for 1:1; centered-subject fixture passes all ratios; the check makes zero network/vision-model calls (spy assert); flag is advisory — submit is never blocked by it | P3 |
| FR2.6 | Batch credit preflight: before a Smart ASPECT Set submits, show tile count and estimated Higgsfield credits; per-batch tile cap (config, default 20) | Preflight modal renders `tiles × model` estimate (fixture catalog); a batch above the cap is rejected client-side with the cap named; cap is config-driven, not a literal (NFR-D1 style) | P3 |

### FR Group 3: Page Asset Scraper

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR3.1 | Given a landing-page URL, extract a **brand-kit object**: `brand_name` · `logo_url` (+dark) · `favicon_url` · `colors[]` (hex + role + frequency) · `fonts[]` · `hero_images[]` / `product_images[]` · `claims[]` / `headlines[]` — contract per [research §5 extraction table] | Scraping the SSR fixture page returns every field per contract shape; colors are role-inferred and frequency-ranked; claims come from H1/H2/hero/meta only | P4 |
| FR3.2 | Substrate = **httpx + BeautifulSoup** (D2); no headless-browser dependency in v1; pages that defeat static parsing (CSS-in-JS) produce an explicit **partial-extraction warning** listing the empty fields — never silent empties. Playwright full-render is a designed-in later fallback phase | v1 dependency manifest contains no Playwright/Chromium; CSS-in-JS fixture returns `partial: true` + named missing fields; SSR fixture returns `partial: false` | P4 |
| FR3.3 | **UNIFY with extract-brief**: one extraction path (extending `studio.py:748` + `prompt_drafter.py:60-135`) whose output feeds (a) persisted brand-kit assets in the library (`ad_assets`) and (b) the shared research object handed to BOTH the image path and the copy drafter [audit C3a; brief "rejected: second scraper"] | One page fetch per URL per run (fetch-count spy); brand-kit assets appear as `ad_assets` rows pickable in `LibraryPicker`; the copy drafter receives the same research object the image path received (identity assert on the job record) | P4 |
| FR3.4 | Scraped `claims[]` are SEEDS only and pass through the existing pinned-claims accuracy gate before entering copy (cf. Panama stay-requirement incident [memory: feedback-panama-stay-requirement-fact]) | Fixture page containing a banned pinned claim: the claim appears in the raw brand kit but NOT in the copy-seed output (gate test); gate rejection is logged with the claim text | P4 |
| FR3.5 | Ownership + robots posture (v1): scraper runs only against operator-confirmed owned properties (explicit confirm or allowlist) and respects `robots.txt` disallow with a refusal message | Disallowed URL returns a 4xx with the robots reason; a URL outside the owned allowlist requires an explicit ownership confirmation flag or is refused | P4 |

### FR Group 4: Draft Persistence

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR4.1 | Server-side `creative_drafts` SQLite table (next migration in the V25+ chain): `{name, campaign_type, account_id, bundle JSON, updated_at}` — **scoped per account** (D4) | Migration test creates the table; a draft saved under account A is not listed for account B; list endpoint filters by `account_id` + `campaign_type` | P1 |
| FR4.2 | Named drafts CRUD: create / list / load / rename / delete; a second draft NEVER destroys the first [audit C8b] | Create two drafts of the same campaign type; both retrievable by name; deleting one leaves the other intact | P1 |
| FR4.3 | Durability: saved drafts AND draft jobs survive backend restart — the in-memory dicts (`_dg_draft_jobs` `demand_gen.py:226,257`, PMax `pmax.py:109,140` [audit C8d]) move to DB rows in the same stroke | Restart harness: save draft → recreate app context → draft retrievable byte-identical; a completed draft job's result is retrievable after restart; an in-flight job reports a recoverable status, not a 404 | P1 |
| FR4.4 | localStorage demoted to keystroke write-through **crash cache only**; server row is the source of truth; on load with a newer local cache the UI offers restore | Rehydrate keeps the existing Google-ref stripping (`DemandGenWizard.tsx:131-141` behavior pinned); with server draft older than local cache, the restore affordance appears; choosing server discards the cache | P1 |
| FR4.5 | JSON export/import on the review step; interchange format = the same bundle the create API accepts, so a draft doubles as a template [audit C8c] | Export → import round-trips to a deep-equal bundle; an imported bundle is validated against the registry before apply (over-limit import surfaces errors, not a crash) | P1 |

### FR Group 5: Coverage & Rationale Panel

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR5.1 | Coverage meter shows **slot coverage** (headlines n/15, images n/20, aspect slots filled) · **angle diversity** (distinct angles present) · **near-duplicate count** (target 0). Ad Strength is reframed as completeness — the panel NEVER tells the operator to "reach Excellent" [research #5 Optmyzr 1M+ ads, §6-3; audit 4b reshaped] | Meter values computed correctly from a bundle fixture (counts + distinct angles + dup count); panel copy snapshot contains no "Excellent"-chasing string; meter encourages filling slots, never maxing characters [research #4] | P2 (text) / P3 (image slots) |
| FR5.2 | Rationale surface: the page-research object (`value_prop, audience, tone, claim_hints`) is displayed to the operator alongside the drafts | After a draft with research attached, the panel renders all four fields; absent research renders an honest empty state, not placeholders | P4 |
| FR5.3 | Suggested audiences become **one-click PMax search themes / DG audience signals**, reusing research already computed [audit Tier 2.3, C3b] | Clicking a suggestion appends a ≤80-char search theme and respects the ≤25 cap from the registry [audit T1.1]; the click is idempotent (no duplicate theme) | P4 |
| FR5.4 | PMax video is NEVER a hard gate (removal in flight, Tier-0); the panel carries the persistent nudge "add your own video to beat the auto-generated slideshow" + the product-mismatch warning [research §3-Q2] | An image-only PMax bundle submits successfully; the nudge + mismatch warning render whenever the video list is empty; no blocking validation references video count | P2 |

### FR Group 6: Display Consumer (Responsive Display Ads)

| ID | Requirement | Acceptance criterion (testable) | Phase |
|----|-------------|--------------------------------|-------|
| FR6.1 | RDA registry entries: short headlines 1–5 × 30 · long headline **exactly 1** × 90 · descriptions 1–5 × 90 · business name 25 · images ≤15/ratio (1.91:1 + 1:1 required, 4:5 optional) · logo 1:1 + **4:1 LANDSCAPE_LOGO** (field type currently absent repo-wide [audit §B]) — all [research §2c]; RDA aggregator-sourced limits carry `verified: false` until checked against the live API | Registry serves the `rda` type with these values; the 4:1 logo field type exists and validates; 2 long headlines rejected; a soft-limit violation on a `verified:false` field warns, not blocks | P5 |
| FR6.2 | `rda_orchestrator` on the `demand_gen_orchestrator` pattern, reusing `creative_images.py` **unchanged** | Orchestrator emits the correct RDA asset field types (incl. LANDSCAPE_LOGO); the P5 diff contains zero changes to `creative_images.py` (exit-gate structural check) | P5 |
| FR6.3 | Thin `RdaWizard` shell (brief → text → images → review) consuming Copy Workbench, Image Engine, brand kit, drafts, coverage panel end-to-end. **The shell is the acceptance test of the core**: zero creative logic in the shell; target well under half of DemandGenWizard's 1,294 lines | Shell line count < 647; no creative validation/drafting/generation logic defined in the shell file (import-only audit); shipping RDA required zero modifications to core components (git-diff scope check at exit gate) | P5 |
| FR6.4 | RDA image rules ride in the registry, not the shell: >20%-text images discounted → generation default clean (`forbid` knob) [research §2c] · image not >80% blank · no logo overlaid on the photo [research #8] | RDA prompt builder emits the text-free instruction (registry-driven); with-logo overlay request under `rda` routes to the logo slot per FR2.2; rules verifiably read from registry entries (fixture flip test) | P5 |

## 7. Non-Functional Requirements

| ID | Requirement | Target / verification | Phase |
|----|-------------|----------------------|-------|
| NFR-D1 | **Spec-drift impossibility — structural.** Exactly ONE source of truth for creative limits (`creative_specs.py`); the client receives limits at runtime via `GET /api/creative/specs`; no mirrored constants anywhere. This is structural, not disciplinary: a CI guard test scans validators, drafter clamps, and frontend validation for numeric creative-limit literals outside the registry (test fixtures allowlisted) and FAILS the build on a hit. Rationale: the DG 30-vs-40 bug is exactly the mirrored-constant failure class; three copies already disagree [audit §B]; a lint can't catch "both sides agree on the wrong number" — removal of the second copy can [brief, rejected alternative] | CI guard test green in every phase; code review checklist item; FR1.1/FR1.2 ACs | P1→ |
| NFR-Q1 | **Render-queue behavior at the Semaphore(6) ceiling.** Never more than 6 concurrent Higgsfield jobs (mirrors the real per-account limit — raising it is rejected [brief]); requests beyond 6 QUEUE in waves instead of hard-failing (retires the `aspects × variants > 6` 400); combined progress is monotonic non-decreasing; per-tile retry ≤ 2 with backoff; queue state lives in DB rows, not process memory | Concurrency instrumentation test (FR2.4); progress monotonicity property test; restart-recovery test | P3 |
| NFR-R1 | **Draft durability across backend restarts.** Zero loss of saved drafts and completed draft-job results across process restart (LaunchAgent restarts are routine [memory: reference_backend_launchagent]); recovery requires no operator action beyond reloading the page | Restart harness tests (FR4.3); no in-memory dict remains on any draft/job path (grep-audit test) | P1 |
| NFR-C1 | **Per-campaign-type policy knobs are table-driven.** Policy values (on-image text, logo overlay, video nudge, per-type limits) resolve from the registry at request time; adding a campaign type or flipping a policy is a data change, never a code branch on campaign type in the enforcement path | Fixture-registry flip tests (FR1.6, FR2.2, FR6.4): changed data changes behavior with zero code diff | P1→ |
| NFR-M1 | **No regression to existing wizard flows during the strangler migration.** Strangler order: DG+PMax consume the core (P1–P4) before RDA exists (P5). At every phase exit, the pre-existing DG and PMax wizard test files pass; user-visible flows (step order, autosave, poll-resume, crop preview) unchanged unless an FR explicitly changes them; migration lands additively (shared components adopted per-wizard, old paths deleted only after the consuming wizard's tests are green on the new path) | Existing suites green at each phase exit; FR1.12 AC (DG tests unmodified); phase exit gates §10 | all |
| NFR-T1 | **Test-coverage floor per repo practice.** Suite stays ≥ the pre-P1 collected baseline (~469–495 at PRD date; 495 test functions counted in `backend/tests` on 2026-08-03) and GREEN at every phase exit; every FR's acceptance criterion lands as ≥1 automated test in the same phase as the FR; no phase merges red | CI at each phase exit; FR→test traceability check in phase review | all |
| NFR-P1 | **Near-dup detection is interactive-speed.** Deterministic detection over a full 15-row set completes < 50 ms client-side (it runs on keystrokes/paste); zero network calls | Perf test on the 15-row fixture; spy assert (FR1.10) | P2 |
| NFR-P2 | **Specs endpoint is startup-cheap.** `GET /api/creative/specs` responds < 100 ms (static data, cacheable); wizards render validation without blocking on it (stale-while-revalidate from last fetch) | Endpoint perf test; wizard renders with a mocked slow endpoint | P1 |

## 8. Registry Seed Data (normative)

The data P1 must encode in `creative_specs.py`. Consolidated from the brief's registry table and
the research spec tables; this section is the citation anchor for every number the engine enforces.
`V` = `verified: true` (Google help page or already API-proven in repo); `U` = `verified: false`
(aggregator-sourced or conflicted — soft-validate, verify against the live API at write time, per D6).

### 8a. Text assets

| Spec | PMax | DG | RDA | Verified | Source |
|---|---|---|---|---|---|
| Headline count | 3–15 | 3–5 | 1–5 | V/V/U | [research §2a] / [research §2b Google help] / [research §2c] |
| Headline chars | 30 | **40** | 30 | V/V/U | [research §2a] / [research §3-Q1 DEFINITIVE] / [research §2c] |
| Long headline count | 1–5 | — (format-dep.) | exactly 1 | V/—/U | [research §2a] / [research §2b] / [research §2c] |
| Long headline chars | 90 | 90 | 90 | V | [research §2] |
| Description count | 3–5 | 3–5 | 1–5 | V/V/U | [research §2a] / [research §2b] / [research §2c] |
| Description chars | 90; **≥1 ≤60** | 90 | 90 | **U** (≤60 — verify at build time [research §2a note]) / V / U | [research §2a] / [research §2b] / [research §2c] |
| Business name chars | 25 | 25 | 25 | V | [research §2] |
| Search themes | ≤25 × ≤80 chars | — | — | V (repo-proven post-create attach) | [audit T1.1, `pmax_orchestrator.py:573-612`] |
| Final URL | 2048 chars, format-checked | same | same | U | [research §2a] |

### 8b. Image + logo + video slots

| Spec | PMax | DG | RDA | Source |
|---|---|---|---|---|
| Landscape 1.91:1 | req, rec 1200×628, min 600×314 | req (≥1 of landscape+square), same dims | req, ≤15/ratio | [research §2a/§2b/§2c] |
| Square 1:1 | req, rec 1200×1200, min 300×300 | same | req, ≤15/ratio | [research §2a/§2b/§2c] |
| Portrait 4:5 | opt, rec 960×1200, min 480×600 | opt | opt (rec 1200×1500 U) | [research §2a/§2b/§2c] |
| Tall 9:16 | — | opt (Shorts), rec 1080×1920, min 600×1067 | — | [research §2b] |
| Logo 1:1 | req 1–5, min 128×128 | req, min 144×144, ≤150 KB | req 1–5, min 128×128 | [research §2a/§2b/§2c] |
| Logo 4:1 landscape | opt ≤5, rec 1200×300, min 512×128 | — | opt ≤5 | [research §2a/§2c; field type absent repo-wide today, audit §B] |
| Total image cap | **≤20 per asset group** | ≤20 per ad | ≤15/ratio | [research §2a hawky (U)] / [research §2b Google help] / [research §2c (U)] |
| File size | JPG/PNG ≤5 MB (existing transcode enforces) | same | same | [research §2]; `creative_images.py` [audit §A] |
| Video | optional; ≤15/orientation (**U** — 5-vs-15 conflict [research §6-2]); ≥10 s | optional; ≥5 s | optional ≤5, ≤30 s rec (U) | [research §2a/§2b/§2c, §3-Q2] |

### 8c. Policy knobs (per D3, per-type, `forbid` default)

| Knob | PMax | DG | RDA | Source |
|---|---|---|---|---|
| On-image text | `forbid` (flippable to `allow_warned` — display school [research §6-1]) | `forbid` | `forbid` (>20% text discounted [research §2c]) | [research §6-1; audit surprise #3] |
| Logo overlay on photo | `allow_warned` (composite mode only) | `forbid` — dedicated slot | `forbid` — dedicated slot [research #8] | [research #8, §5] |
| Video gate | never hard (nudge only) | never hard | never hard | [research §3-Q2] |

## 9. API Contract & Data Model Changes

New/changed endpoints (names indicative; architecture review owns final shapes):

| Endpoint | Verb | Purpose | Phase |
|---|---|---|---|
| `/api/creative/specs` | GET | Serve the full registry (all campaign types, verified flags, policy knobs) | P1 |
| `/api/accounts/{id}/creative-drafts` | GET/POST | List / create named drafts (per-account, per D4) | P1 |
| `/api/accounts/{id}/creative-drafts/{draft_id}` | GET/PUT/DELETE | Load / update / delete a named draft | P1 |
| existing draft-job endpoints (`demand_gen.py`, `pmax.py`) | — | Contract change only: response rows become `[{text, angle, tier}]`; job state moves to DB rows | P1 (storage) / P2 (contract) |
| `/api/studio/batch-render` | POST | Smart ASPECT Set: slots × variants, returns queue id; wave scheduling server-side | P3 |
| `/api/studio/batch-render/{id}` | GET + SSE | Combined progress, per-tile states, retry | P3 |
| `/api/creative/brand-kit` | POST | Scrape URL → brand-kit object; persists assets to library; extends extract-brief, single fetch (FR3.3) | P4 |

Data model (SQLite, next migrations in the V25+ chain):

- **`creative_drafts`** — `{id, name, campaign_type, account_id, bundle JSON, updated_at}`;
  unique `(account_id, campaign_type, name)` (FR4.1).
- **Draft jobs → DB rows** — `_dg_draft_jobs` / PMax in-memory dicts retired (FR4.3, NFR-R1).
- **Batch render queue** — extends the existing Studio job table with a parent-batch id, per-tile
  slot assignment, retry count (NFR-Q1).
- **Brand-kit assets** — persisted as `ad_assets` rows (existing table; new `source` value),
  no new table (FR3.3).

## 10. Phasing & Exit Gates

Order rationale (brief, upheld by D5): correctness before features; copy before image; scraper
after Image Engine (asset-anchored already works with library photos); RDA last because it is the
proof, not the driver. Rejected: RDA-first greenfield (would grow a third copy of everything).

| Phase | Contents (FRs) | Size | Exit gate — ALL must be true |
|---|---|---|---|
| **P1 — Spec truth + drafts** | FR1.1–FR1.6, FR1.11, FR4.1–FR4.5 | M (~3–5 d) | Registry is the only limit source (NFR-D1 CI guard green) · `GET /api/creative/specs` consumed by both wizards · all FR1.4 gap-closure rejections proven by tests · DG 40-char live in both client and server · a named draft survives restart and round-trips export/import (FR4.3/4.5 ACs) · suite ≥ baseline and green (NFR-T1) · existing wizard suites untouched-and-green (NFR-M1) |
| **P2 — Copy Workbench + PMax parity ★** | FR1.7–FR1.10, FR1.12–FR1.13, FR5.1 (text), FR5.4 | L (~1 wk) | ★ demo script (§4) performed live with Wassim and all 6 steps pass · `[{text, angle, tier}]` contract in both drafters · near-dup detector deterministic + <50 ms (NFR-P1) · shared assist components exist once, consumed twice · coverage meter v1 (text) live · image-only PMax bundle submits (FR5.4) · suite green |
| **P3 — Image Engine** | FR2.1–FR2.6, FR5.1 (image slots) | L (~1–2 wk) | One art direction → full slot set auto-assigned with zero manual crop fixes in one queued action · 10-tile batch respects Semaphore(6) and survives restart (NFR-Q1) · safe-zone flag fires on the edge-subject fixture, advisory-only · credit preflight caps batches · text-on-image knob wired, still no UI (D3) · suite green |
| **P4 — Scraper + rationale** | FR3.1–FR3.5, FR5.2–FR5.3 | M (~1 wk) | Brand kit extracted from an owned SSR page into the library and reused across two campaigns · single-fetch unification proven (FR3.3) · banned-claim fixture blocked by the accuracy gate · robots/ownership refusals proven · one-click search theme respects registry caps · suite green |
| **P5 — Display consumer** | FR6.1–FR6.4 | M (~4–6 d) | RdaWizard ships with zero creative logic and < 647 shell lines · P5 diff shows no core-component changes (FR6.3 structural check) · 4:1 LANDSCAPE_LOGO validates end-to-end · RDA `verified:false` limits confirmed or corrected against the live API before first real campaign · suite green |

## 11. Success Metrics

| # | Metric (from brief) | Proven by |
|---|---|---|
| 1 | Zero Google-side validation rejections for bundles that passed local validation | FR1.2–FR1.4; tracked across the first 5 real creates post-P1 |
| 2 | DG drafts actually use >30-char headlines when the message earns it | FR1.5; sampled from first real DG drafts post-P1 |
| 3 | One approved art direction → full slot set auto-assigned, zero manual crop fixes, one queued action | FR2.3/FR2.4; P3 exit gate |
| 4 | Near-duplicate count = 0 on every submitted set; ≥4 distinct angles per headline set | FR1.10, FR5.1; coverage meter at submit |
| 5 | A named draft survives backend restart and round-trips JSON export/import | FR4.3/FR4.5; P1 exit gate |
| 6 | RdaWizard ships with zero creative logic in the shell, no core changes required | FR6.3; P5 exit gate |

## 12. Risks (honest)

| # | Risk | Exposure | Mitigation |
|---|---|---|---|
| R1 | **Near-dup detection quality.** Normalized token similarity misses paraphrase duplicates ("Move to Panama fast" vs "Relocate to Panama quickly") and may false-positive legitimately similar compliance phrasing. A weak detector makes "Diversify" feel random and erodes trust in metric #4 | Medium — core P2 value prop | Threshold tuned on a labeled fixture set built from real Mercan campaign copy before P2 exit; false-positive escape hatch (operator dismisses a flag, dismissal persisted); detector is advisory + swappable behind an interface — LLM-assisted scoring can be added later WITHOUT changing the deterministic on-keystroke path [brief, rejected alternative] |
| R2 | **Higgsfield credit burn on batch sets.** Smart ASPECT Set multiplies spend: 5 slots × 2 variants = 10 renders/action, plus ≤2 retries each = worst-case 30. Habitual regeneration burns real subscription credits | Medium-high once P3 lands | FR2.6 credit preflight + per-batch cap (default 20 tiles); per-tile retry (never re-render finished tiles); balance surfaced in the queue UI (existing `studio.py` credits path); batch history in the job store makes spend auditable |
| R3 | **RDA spec drift vs the registry.** RDA limits are sourced from Tier-3 aggregators [research §2c — lineardesign, digitalapplied, udonis], not Google help pages; if wrong, the registry confidently enforces wrong numbers — the exact failure the registry exists to prevent, now at the data layer | Medium — deferred to P5 | RDA entries carry `verified: false` until checked against the live Google Ads API (FR6.1); P5 exit gate requires verification before the first real RDA campaign; registry treats limits as config Google can change mid-year [research §2 authority note] |
| R4 | **Scraper legal/robots posture.** Even with D2's own-properties-only scope, the capability generalizes; future multi-client onboarding (brief OQ6) would point it at pages we don't own | Low in v1, real later | FR3.5 hard posture: ownership confirm/allowlist + robots.txt respect + refusal messages, all tested; widening beyond owned properties is an explicit future decision requiring its own review, not a config flip |
| R5 | **Heuristic safe-zone detector (D1) under-detects.** Cheap CV bboxes are weak on busy scenes/soft subjects; false confidence is worse than no check | Low-medium | Flag is advisory-only (never blocks); SlotThumb crop preview [audit surprise #4] remains the human-verifiable truth beside every flag; detector interface designed so the deferred vision-model can drop in |
| R6 | **SSR assumption breaks silently (D2).** If a target LP moves to CSS-in-JS, static parsing degrades | Low in v1 | FR3.2 partial-extraction warning names the missing fields — degradation is loud; Playwright fallback phase is pre-designed |
| R7 | **Strangler regression risk.** Extracting the shared TextList/assist layer touches the two live wizards Wassim uses for real campaigns | Medium | NFR-M1 gates every phase on the pre-existing wizard suites; additive adoption; creates remain PAUSED by default [audit §A] so a slipped regression can't spend money |

## 13. Binding Reuse Map

Build ON these, not around them [audit reuse list — binding; brief reuse map].

| Existing asset | Role in the engine |
|---|---|
| `backend/google_ads/services/campaign/creative_images.py` | THE image spine: exact-aspect crop ±1%, min-size rejection, 5MB transcode, slot specs. Image Engine + safe-zone build on it; P5 must not touch it (FR6.2) [audit surprise #5] |
| `frontend/src/components/studio/StudioPanel.tsx` | Model picker, Enhance (Visual Director 3-angle), copy/image modes — generation modes layer on it |
| `SlotThumb` crop preview | Kept everywhere — "genuinely better than anything in the benchmark" [audit surprise #4]; the human check beside the safe-zone flag |
| Studio DB-row job store + SSE (`studio.py`) | Batch render queue extends it (NFR-Q1); draft jobs migrate into DB rows beside it (FR4.3) |
| `prompt_drafter.py` extract-brief 2-stage research | Scraper extends it into the brand kit (FR3.3); text-free image rule preserved as the default policy (FR1.6) |
| `TextList` + draft-poll/resume plumbing | Evolves into Copy Workbench; job plumbing reused for rewrite/diversify (FR1.9) |
| `LibraryPicker` / `AssetLibrary` + `ad_assets` table | Brand-kit assets persist here (FR3.3); reference picking unchanged |
| DG assist layer (PolicyHint, brand preset, ref photos, confirm modal) | Extracted into shared components; PMax gets them by consumption (FR1.12) [audit Tier 1.3] |

---

*Next step per the brief: architecture review focused on the registry contract, the batch renderer,
and the shared-component extraction seams — then epics & stories.*
