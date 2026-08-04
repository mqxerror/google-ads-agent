---
stepsCompleted: [01-init, 02-context-analysis, 03-starter-template, 04-architectural-decisions, 05-design-patterns, 06-data-integration, 07-validation, 08-complete]
inputDocuments: [_bmad-output/planning-artifacts/prd-unified-creative-engine.md, _bmad-output/planning-artifacts/product-brief-unified-creative-engine.md, research/creative-best-practices-2026-08.md, ~/Documents/LangarAI/data/gads-creative-gap-analysis-2026-08-03.md]
workflowType: 'architecture'
lastStep: 8
projectType: 'web_app'
parent: architecture-v2.md
---

# Architecture Document — Unified Creative Engine

**Author:** Wassim (drafted by Dam3oun-Google)
**Date:** 2026-08-03
**Version:** 1.0
**Status:** ✅ BUILT — realized across Epics 14–20, shipped 2026-08-03 → 2026-08-04 (see BUILD STATUS callout below)
**Parent:** architecture-v2.md (V2 system architecture; this document scopes one subsystem)

> **✅ BUILD STATUS — 2026-08-04 (completion annotation; content below unchanged).** AD-1…AD-6 and the §7 strangler map (steps 1–10) are all realized on `main`. Structural fences hold under test: F2 geometry single-source + F4 frozen specs (`test_creative_specs.py`), F5 near-dup parity (`test_near_dup_parity.py`), F6 no module-level job dicts (`test_creative_jobs_restart.py`), the NFR-D1 CI drift guard (`test_spec_registry_guard.py`), and the P5 diff-scope check proving `creative_images.py` + `components/creative/*` were untouched by the RDA consumer. Migrations landed through **V28** (`creative_drafts`/`creative_jobs` V27, `creative_batches`/`ad_assets` columns V28). Close-out battery: **backend 671 pytest · vitest 107** · `tsc -b` + `vite build` clean · launchctl restart → health 200. Per the Tier-2 drift discipline this is an annotation only — the architecture CONTENT is unchanged.
**Contract:** prd-unified-creative-engine.md (37 FRs / 8 NFRs) — every component below names the FRs it satisfies.

---

## Table of Contents

1. [Architectural Overview](#1-architectural-overview)
2. [Current-State Delta (what already moved since the audit)](#2-current-state-delta)
3. [Architectural Decisions](#3-architectural-decisions)
4. [Component & File Map](#4-component--file-map)
5. [Data Model & Migrations](#5-data-model--migrations)
6. [API Contracts](#6-api-contracts)
7. [Strangler Migration Map](#7-strangler-migration-map)
8. [Structural Fences](#8-structural-fences)
9. [Risk Mitigations (PRD §12 → design)](#9-risk-mitigations-prd-12--design)
10. [Honesty Ledger — harder than the PRD makes it look](#10-honesty-ledger--harder-than-the-prd-makes-it-look)

---

## 1. Architectural Overview

**One creative core, many thin wizard shells.** The core is five backend capabilities plus one
shared frontend component family; PMax and Demand Gen are migrated onto it strangler-style, and the
new Responsive Display builder consumes it as an almost-empty shell (the acceptance test, FR6.3).

```
┌──────────────────────────── WIZARD SHELLS (thin) ─────────────────────────────┐
│  PMaxWizard        DemandGenWizard        RdaWizard (NEW, P5)                 │
│  step scaffold ·   step scaffold ·        step scaffold ·                     │
│  type-specific     type-specific          nothing type-specific               │
│  (video, signals)  (channels, geo)                                            │
└───────┬──────────────────┬──────────────────────┬─────────────────────────────┘
        │  all creative behavior imported from ↓
┌───────▼──────────────────▼──────────────────────▼─────────────────────────────┐
│              SHARED CREATIVE COMPONENTS  frontend/src/components/creative/    │
│  TextWorkbench (angle chips, per-row rewrite, paste-split, near-dup flags)    │
│  CoveragePanel · PolicyHintCard · BrandPresetToggle · ReferencePhotosPicker   │
│  BusinessNameField · ConfirmCreateModal · SmartAspectSet · DraftManager       │
│  hooks: useCreativeSpecs · useDraftJob · useNamedDrafts · lib: nearDup.ts     │
└───────┬───────────────────────────────────────────────────────────────────────┘
        │ REST + SSE (all limits fetched at runtime — zero baked constants)
┌───────▼───────────────────────────────────────────────────────────────────────┐
│                          BACKEND CREATIVE CORE                                 │
│  creative_specs.py   THE registry — limits/policies as data (AD-1)            │
│  creative_copy.py    draft / rewrite / diversify jobs → DB rows (AD-2)        │
│  batch_render.py     Smart ASPECT Set wave scheduler over Semaphore(6) (AD-3) │
│  brand_kit.py        httpx+BS4 brand-kit extraction, one fetch (AD-4)         │
│  creative_drafts     named drafts table + export/import (AD-5)                │
│  near_dup.py         deterministic detector, parity-locked with TS (AD-2)     │
├────────────────────────────────────────────────────────────────────────────────┤
│  EXISTING SPINE (build ON, per binding reuse map — PRD §13)                   │
│  creative_images.py (exact-aspect crop · slot geometry — frozen in P5)        │
│  studio.py DB-row job store + SSE · prompt_drafter.py 2-stage research        │
│  page_fetcher.py · claim_gate.py + pinned claims · ad_assets + LibraryPicker  │
│  demand_gen_orchestrator.py · pmax_orchestrator.py (+ rda_orchestrator.py P5) │
└────────────────────────────────────────────────────────────────────────────────┘
```

Design style follows the repo culture: **make the wrong thing unrepresentable** where cheap
(§8 Structural Fences), DB rows as the single source of truth for every long-running job, the
orchestrators as the only Google-write path, creates PAUSED.

---

## 2. Current-State Delta

The PRD was cut against repo `a0602d9`. Two commits have landed since; the architecture accounts
for them:

| Commit | What landed | Effect on this design |
|---|---|---|
| `cb76a04` | Tier-0 fixes: aspect-vs-catalog validation in `studio.py` (1.91:1 → "generate 16:9, crop at submit"), ad-picker endpoint replacing hardcoded ad ids, PMax video hard-gate removed (client `videos: {min: 0}` + server comment) | FR5.4's precondition is DONE. Smart ASPECT Set (AD-3) adopts the same 1.91:1 answer: request 16:9 from the model, let `fit_image_for_slot` produce 1.91:1 |
| `c7c95b4` | DG headline 30 → 40 in all three copies (`TEXT_RULES`, `_DG_DRAFT_LIMITS`, wizard `RULES`) | FR1.5's *value* is live, but as three mirrored constants — exactly the failure class NFR-D1 exists to kill. P1 replaces the copies with registry reads; the FR1.5 test work (drafter 40-char instruction, prompt snapshot) still stands |

Also verified in code (matters below): both create responses already carry `warnings: List[str]`
(`PMaxCreateResponse`, `DemandGenCreateResponse`) — the soft-validation channel FR1.3 needs exists;
`_validate_bundle` in both orchestrators is errors-only today and needs the warnings side added.

---

## 3. Architectural Decisions

### AD-1: Creative Spec Registry — one frozen Python module, served at runtime

**Context.** Limits live in ≥4 places today (orchestrator `TEXT_RULES` ×2, router draft clamps ×2,
wizard `RULES` ×2, plus `IMAGE_SLOT_SPECS` in `creative_images.py`) and have already disagreed with
each other and with Google (FR1.1–FR1.6, NFR-D1).

**Decision.** A single backend module **`backend/app/services/creative_specs.py`** holding the
registry as **frozen dataclasses** keyed by campaign type, served verbatim by
`GET /api/creative/specs`:

```python
@dataclass(frozen=True)
class TextFieldSpec:
    min_count: int; max_count: int; max_chars: int
    verified: bool                      # False ⇒ soft-validate (warn, never block) — FR1.3
    source: str                         # citation key, e.g. "research §3-Q1"

@dataclass(frozen=True)
class ImageSlotSpec:
    slot: str                           # key into creative_images.IMAGE_SLOT_SPECS
    max_count: int; required: bool; verified: bool; source: str
    # aspect / min_w / min_h are NOT stored here — resolved from
    # creative_images.IMAGE_SLOT_SPECS at import time (geometry single-source, §8-F2)

@dataclass(frozen=True)
class PolicyKnobs:                      # NFR-C1 — table-driven, never a code branch
    on_image_text: str                  # 'forbid' | 'allow_warned'   (FR1.6, D3)
    logo_overlay: str                   # 'forbid' | 'allow_warned'   (FR2.2)
    video_gate: str                     # always 'nudge'              (FR5.4)

@dataclass(frozen=True)
class CampaignSpec:
    text: dict[str, TextFieldSpec]      # headlines / long_headlines / descriptions / …
    images: dict[str, ImageSlotSpec]; logos: dict[str, ImageSlotSpec]
    business_name_max: int; total_image_cap: int | None
    search_themes: tuple[int, int] | None      # (max_count, max_chars) — PMax only
    video: VideoSpec; final_url_max: int; policy: PolicyKnobs

@dataclass(frozen=True)
class EngineConfig:                     # engine-wide knobs, same single-source discipline
    near_dup_threshold: float           # default 0.65 — read by BOTH detectors (AD-2)
    batch_tile_cap: int                 # default 20 — FR2.6 "config-driven, not a literal"
    batch_retry_max: int                # default 2  — NFR-Q1

REGISTRY: dict[str, CampaignSpec]       # 'pmax' | 'demand_gen' | 'rda'
ENGINE: EngineConfig
```

Seed values come verbatim from PRD §8 (normative), each with `verified` + `source`. The RDA entry
ships in P1 as data (costs nothing; FR6.1 only *activates* it in P5).

**How the three consumer families read the SAME object (FR1.1/FR1.2):**

- **Server validators** — `_validate_bundle` in both orchestrators gains a
  `spec: CampaignSpec` parameter resolved via `creative_specs.get('pmax')`; the local
  `TEXT_RULES` / `BUSINESS_NAME_MAX_CHARS` / `MAX_LOGOS` tables are **deleted** (the `field_type`
  enum mapping stays in the orchestrator — it is Google-API plumbing, not a limit). Validation
  returns a `ValidationReport {errors[], warnings[]}`: `verified=False` violations land in
  `warnings` and ride the existing `warnings` field of the create response; errors still raise.
- **Drafter clamps** — `_DG_DRAFT_LIMITS` / `_DRAFT_LIMITS` are deleted; `creative_copy.py`
  derives clamp tuples from `spec.text` and builds the HARD-LIMITS prompt block from the same
  object (so the prompt can never promise a different number than the validator enforces).
- **Frontend** — wizard `RULES` consts are deleted. `useCreativeSpecs()` (context provider,
  `frontend/src/lib/creativeSpecs.ts`) fetches `/api/creative/specs` with
  stale-while-revalidate (localStorage-cached last response; NFR-P2: wizards render immediately
  from cache, submit disabled only when no specs have EVER been fetched). `TextWorkbench` and the
  validators take a `FieldSpec` prop whose only source is the provider.

**CI guard (NFR-D1) — the concrete mechanism**, `backend/tests/test_spec_registry_guard.py`:

1. **Tombstone check:** asserts the retired constant names (`TEXT_RULES`, `_DRAFT_LIMITS`,
   `_DG_DRAFT_LIMITS`, `BUSINESS_NAME_MAX_CHARS`, `MAX_LOGOS`, frontend `RULES`) no longer exist
   in the enforcement files (AST walk for Python, regex for TSX). A resurrected copy fails CI by
   name before anyone argues about values.
2. **Sentinel-literal scan:** AST-walks a curated list of enforcement files (both orchestrators'
   validate paths, `creative_copy.py`, both wizards, `TextWorkbench.tsx`) and fails on any numeric
   literal in the sentinel set `{15, 20, 25, 30, 40, 60, 80, 90, 128, 2048}` unless the line
   carries a `# spec-ok: <reason>` / `// spec-ok: <reason>` pragma. Pragma uses are counted and
   snapshot-asserted so additions are visible in review.
3. **Round-trip check:** deserializes `GET /api/creative/specs` and deep-compares against
   `REGISTRY` — the endpoint cannot drift from the module.

The scan is a tripwire, not a proof — the *structural* fence is that step 1 has deleted the second
copy, so there is nothing left to disagree (brief's rejected-lint rationale).

**Rejected alternatives.**
- *DB table for specs* — limits change when Google changes them, i.e. via a reviewed commit with a
  citation and updated tests, not at runtime; a DB row has no `source` citation in code review, no
  type checking, and invites a mutation UI nobody asked for. The registry is config-as-code.
- *YAML/JSON file* — loses import-time typing and the ability of `creative_images` geometry to be
  composed by reference; a parse step is one more place to drift.
- *Build-time codegen of TS constants* — reintroduces baked client constants one artifact removed;
  runtime fetch keeps exactly one serialization (FR1.2's "zero client-code change" test depends
  on it).

### AD-2: Copy Workbench — shared TextWorkbench + `[{text, angle, tier}]` contract + parity-locked near-dup detector

**Decision.**

- **Contract (FR1.7):** the drafting/rewrite/diversify pipeline moves to
  `backend/app/services/creative_copy.py`, one service for all campaign types. Response rows are
  `{text: str, angle: str, tier: str}` with `angle ∈ {promotional, feature, benefit, urgency,
  social_proof, aspiration, specificity}` and `tier ∈ {headline, long_headline, description,
  short_description}` (Google-native slots). Malformed rows are dropped with a logged warning
  (FR1.7 AC). Job modes: `draft` (full set) · `rewrite_row` (row index + target angle, only that
  row replaced — FR1.9) · `diversify` (server receives the client's flagged row indices + locked
  rows; locked rows are excluded from the regenerate payload — FR1.8/FR1.10). Jobs persist as
  `creative_jobs` rows (AD-5), reusing the poll + resume-key pattern from
  `demand_gen.py:583-639`'s client side via a shared `useDraftJob` hook.
- **TextWorkbench (FR1.8/FR1.11/FR1.12):** today's `TextList` (duplicated in both wizards) is
  extracted to `frontend/src/components/creative/TextWorkbench.tsx` and grows: angle chip + lock
  per row, per-row rewrite button, paste-multiline split (`onPaste` splits on newlines into rows,
  each clamped to `fieldSpec.max_chars`), inline near-dup badge. The five DG assist components
  (PolicyHintCard, BrandPresetToggle, ReferencePhotosPicker, BusinessNameField,
  ConfirmCreateModal) are extracted 1:1 into `components/creative/` and consumed by both wizards.
- **Near-dup detector (FR1.10, NFR-P1) — the algorithm, pinned:**
  1. *Normalize:* lowercase → strip punctuation/symbols → collapse whitespace → drop a fixed
     30-word English stopword list (the list ships in the fixtures, not inline) → light suffix
     fold (trailing `s`, `ing`, `ed`).
  2. *Compare:* token-SET Jaccard, `sim(a,b) = |A∩B| / |A∪B|`; additionally flag when the smaller
     set is fully contained in the larger (`|A∩B| = min(|A|,|B|)`) — catches "Move to Panama" vs
     "Move to Panama today".
  3. *Flag:* pair is a near-dup when `sim ≥ ENGINE.near_dup_threshold` (default 0.65, tuned on the
     labeled Mercan fixture set before P2 exit — Risk R1) or normalized-equal.
  - **Where it runs:** client-side (`frontend/src/lib/nearDup.ts`) on keystroke/paste — <50 ms on
    15 rows, zero network (NFR-P1 spy AC) — AND server-side (`backend/app/services/near_dup.py`)
    where `diversify` verifies the regenerated set is below threshold before returning. Two
    implementations of ~20 lines each, **parity-locked** by a shared golden fixture file
    (`backend/tests/fixtures/near_dup_cases.json`, symlink-free — the vitest suite reads the same
    path) asserting identical flag sets in pytest and vitest, with the threshold read from the
    registry on both sides. Operator dismissals persist in the draft bundle
    (`dismissed_dup_pairs`) — R1's escape hatch.

**Rejected alternatives.**
- *LLM-scored similarity* — slow, costs a turn, non-reproducible on keystroke (brief; the detector
  interface stays swappable so an LLM scorer can be ADDED behind the same flag shape later).
- *Server-only detection endpoint* — violates NFR-P1 (network on keystroke); client-only detection
  — leaves `diversify` unable to honor its own acceptance criterion server-side. Dual
  implementation with parity fixtures is the honest cheapest option; it is the ONE sanctioned
  mirrored-logic site in the engine, and it is fixture-locked where the limits case is
  deletion-locked.
- *Per-type draft endpoints kept forever* — the existing `pmax.py`/`demand_gen.py` draft routes
  become thin shims over `creative_copy.py` in P2 and are deleted at P2 exit once both wizards are
  on `POST /api/accounts/{id}/creative/copy-jobs` (NFR-M1 additive rule).

### AD-3: Image Engine — mode fields on the request, batch = parent row + `ad_assets` children, waves under the EXISTING semaphore

**Decision.**

- **Generation modes (FR2.1/FR2.2)** are explicit request fields, not prompt conventions:
  `mode: 'with_logo' | 'without_logo' | 'asset_anchored'`, plus `logo_asset_id` (with_logo) and
  `reference_asset_ids` (asset_anchored — the existing `--image` flag path, backported to PMax by
  including `referenceAssetIds` in PMax's `baseContext`). `with_logo` renders the base image
  normally, then composites the logo as a Pillow paste step server-side; **base and composite are
  two `ad_assets` rows** linked by `parent_asset_id` — the base stays recoverable (AdCreative/Flair
  layer pattern, never re-prompted). Logo-overlay policy resolves from `spec.policy.logo_overlay`:
  under `forbid`, the request is answered with the policy warning and the logo routed to the logo
  slot (FR2.2).
- **Smart ASPECT Set (FR2.3/FR2.4, NFR-Q1):** `POST /api/studio/batch-render` creates ONE
  `creative_batches` parent row + N child `ad_assets` rows (`batch_id`, `slot`, `variant_index`,
  `status='pending'`) — the children ARE the existing DB-row job store, so SlotThumb, the library,
  and SSE all work unchanged. A per-batch **supervisor task** (`batch_render.py`) walks pending
  children and runs each through the SAME single-image runner used today, acquiring the SAME
  module-level `_GENERATION_SEMAPHORE(6)` — so batches and ad-hoc generations share one ceiling
  and the `aspects × variants > 6` hard-fail is retired (the 400 in `generate_image` stays for the
  legacy single-shot path until P3 replaces its callers). 1.91:1 tiles are requested from the
  model as 16:9 (per `cb76a04`'s catalog rule) and pass through `fit_image_for_slot` on
  assignment. **Restart recovery:** app lifespan startup scans `creative_batches` with
  `status='running'` and respawns supervisors; children with a `higgsfield_job_id` are re-polled
  (the CLI supports job-status reattach), children without one re-enqueue; completed tiles are
  never re-rendered (R2). Progress = terminal children / total — monotonic because terminal states
  never revert. Per-tile retry increments `retry_count` up to `ENGINE.batch_retry_max` with
  backoff; a failed tile leaves its slot empty with the retry affordance (FR2.3 AC).
- **Safe-zone heuristic v1 (FR2.5, D1)** lives in `creative_images.py` (P3 — allowed; the P5
  freeze is FR6.2's): `subject_bbox(img)` = grayscale → `ImageFilter.FIND_EDGES` → 8×8 block
  energy grid → threshold at mean+1σ → bbox of the largest connected block region, padded 4%.
  **Predicate:** for each destination slot, compute the center-crop window at the slot's aspect,
  shrink it to its central 80% (research #9); flag the slot when <80% of the bbox area falls
  inside that safe window. Pure Pillow + stdlib — zero network, zero new deps (spy AC). Flags are
  computed at tile completion and stored on the row (`safe_zone_json`, per-slot booleans + bbox);
  the UI renders an advisory amber chip beside the SlotThumb crop preview (the human-verifiable
  truth, R5) — submit is never blocked.
- **Credit preflight (FR2.6):** preflight modal computes `tiles × est_credits(model)` and checks
  `tiles ≤ ENGINE.batch_tile_cap`; balance surfaced from the existing Studio credits path.
  Requires adding a numeric `est_credits` field to `model_catalog.py` entries (today only prose
  `cost_text` exists — see Honesty Ledger #2); estimates are labeled estimates in the UI.

**Rejected alternatives.**
- *Client-side batching* — dies with the tab, contradicts the DB-row-as-truth pattern
  (brief-rejected, restated for the record).
- *Raising the semaphore* — it mirrors Higgsfield's real per-account 6-job cap (brief-rejected).
- *A separate batch-jobs table for tiles* — a second job store beside `ad_assets` is the limits
  bug at the job layer; only the parent aggregate is new, children stay `ad_assets` rows.
- *Vision-model safe-zone* — deferred per D1; the detector is one function behind a stable
  signature so the vision model can drop in without touching callers.

### AD-4: Page Asset Scraper — extend `page_fetcher` + one extraction module, two consumers

**Decision.** `backend/app/services/brand_kit.py` implements the extraction contract (FR3.1) over
the EXISTING `page_fetcher.fetch()` (httpx, 5s timeout, 10MB cap, SSRF guards — already exactly
D2's substrate). `FetchedPage` gains a `raw_html` field so brand-kit parsing re-parses the same
bytes — **one HTML document fetch per URL per run** (FR3.3's fetch-count spy counts HTML document
fetches; linked same-origin stylesheets [≤3] and selected image downloads are subordinate asset
fetches, not page re-fetches — stated here so the AC is testable without being false).

Extraction heuristics (per research §5 contract): logo from header/nav `<img>`/inline `<svg>` with
logo-ish class/alt/src + `rel=icon` favicon + `og:image` fallback; `colors[]` as hex/rgb literals
harvested from inline styles + `<style>` blocks + fetched linked CSS, frequency-ranked,
role-inferred from selector context (body/header → background, button/a → primary, body color →
text); `fonts[]` from `font-family` declarations; hero/product images from large-dimension or
hero-classed `<img>` + `og:image`; `claims[]`/`headlines[]` from H1/H2/hero copy/meta description
ONLY. **Partial-extraction honesty (FR3.2):** every field group reports found/empty; a page whose
color+font harvest comes back empty (CSS-in-JS) returns `partial: true` + the named missing fields.
No Playwright anywhere in the v1 dependency manifest; the module boundary (`extract(page) →
BrandKit`) is where a rendered-DOM provider plugs in later (R6).

**Persistence + unification (FR3.3):** downloaded logo/hero images land as `ad_assets` rows with
`source='scraped'` (pickable in `LibraryPicker` unchanged); the non-file fields (brand_name,
colors, fonts, claims) persist as ONE `ad_assets` row of `type='brand_kit'` whose `meta_json`
column (new, V28) carries the kit object + the ids of its sibling image rows — account-scoped,
listable, no new table (PRD data-model note honored via one additive column). `extract-brief`
(`studio.py:748` → `prompt_drafter.draft_variants`) is refactored to consume
`brand_kit.research_object(page)` for its Stage-1 input, and `creative_copy.py` receives the SAME
research object on draft jobs (identity assert = shared `research_hash` recorded on the job row).

**Claims gate (FR3.4):** scraped `claims[]` pass through a new `filter_claim_seeds()` entry point
built on the EXISTING pinned-claims store (`prompt_drafter._load_pinned_claims` / campaign memory)
and `claim_gate.py`'s normalization/matching primitives — a seed that contradicts a pinned fact
(the Panama stay-requirement class) is dropped and logged with the claim text. Honest note:
`claim_gate.run_claim_gate` was built to audit chat output, so FR3.4 reuses its primitives, not
its top-level function (Honesty Ledger #5).

**Ownership + robots (FR3.5):** `robots.txt` fetched once per host (cached) and evaluated with
`urllib.robotparser`; disallow → 403 with the robots reason. Ownership allowlist = JSON list under
the existing `config` table key `creative.owned_domains`; a URL off-list requires
`confirm_ownership: true` in the request or is refused. Widening beyond owned properties is a
future decision, not a flag flip (R4).

**Rejected alternatives.** *Playwright now* (D2 — v1 targets operator-owned SSR pages; loud
partial warnings instead of silent empties) · *claude-in-chrome MCP as renderer* (session-bound,
can't run unattended, drags a browser dependency into a server path) · *second scraper beside
extract-brief* (brief-rejected: two fetchers with different opinions = the limits bug at the
content layer).

### AD-5: Draft Persistence — `creative_drafts` + `creative_jobs` tables, localStorage demoted

**Decision.** Migration **V27** (next in the chain after V26) creates:

- **`creative_drafts`** — `{id, account_id, campaign_type, name, bundle_json, created_at,
  updated_at}` with `UNIQUE(account_id, campaign_type, name)` (FR4.1, D4). CRUD per §6; a second
  draft can never destroy the first because names are rows, not a singleton key (FR4.2).
- **`creative_jobs`** — `{id, kind ('draft'|'rewrite_row'|'diversify'), account_id, campaign_type,
  status ('running'|'done'|'error'|'interrupted'), request_json, result_json, error_message,
  research_hash, created_at, updated_at}`. The in-memory dicts `_dg_draft_jobs` / `_draft_jobs`
  are deleted in the same stroke (FR4.3, NFR-R1); the grep-audit test asserts no module-level
  job dict remains on any draft path. App startup sweeps `running → interrupted`: the CLI
  subprocess died with the process, so an in-flight job cannot silently resume — `interrupted` is
  the FR4.3 "recoverable status, not a 404", and the UI offers one-click re-run with the persisted
  `request_json` (Honesty Ledger #4).
- **localStorage (FR4.4):** keeps the per-keystroke write-through as a crash cache, INCLUDING the
  existing Google-ref stripping on rehydrate (`DemandGenWizard.tsx` guard, behavior pinned). On
  wizard open: if the local cache's `updated_at` is newer than the loaded server draft, a restore
  banner offers local-vs-server; choosing server clears the cache.
- **Export/import (FR4.5):** client-side Blob download / file-input of the bundle JSON — the same
  shape the create API accepts (a draft is a template). Import validates against
  `useCreativeSpecs()` client-side and is re-validated server-side on save/create; an over-limit
  import surfaces field errors, never a crash.

**Rejected alternative.** *localStorage-keyed named drafts first, server later* — double work, no
restart durability, and it leaves the server-side job-store restart bug (`C8d`) unfixed
(brief-rejected).

### AD-6: RDA consumer — `rda_orchestrator` on the DG pattern, shell as acceptance test

**Decision (FR6.1–FR6.4, P5).** `backend/google_ads/services/campaign/rda_orchestrator.py`
follows `demand_gen_orchestrator`'s recipe shape (budget → campaign → ad group → one
`ResponsiveDisplayAdInfo` ad, PAUSED, rollback on step failure), calling `creative_images` helpers
**unchanged** — the P5 exit gate diffs `creative_images.py` for zero changes (FR6.2). The one new
geometry, **4:1 LANDSCAPE_LOGO**, is added to `IMAGE_SLOT_SPECS` as `landscape_logo` in **P3**
(when the Image Engine touches slot plumbing anyway) so P5 genuinely cannot need a
`creative_images` edit. RDA registry entries ship `verified: false` and are confirmed against the
live API before the first real campaign (R3, P5 exit gate). `RdaWizard.tsx` = brief → text →
images → review; the **<647-line gate** (half of DemandGenWizard's 1,294) is explained by what a
shell must NOT contain: no `TextList`/`ImageGroup`/`SlotThumb` implementations (imported), no
validation logic (specs come from the provider), no draft-poll plumbing (`useDraftJob`), no
persistence logic (`useNamedDrafts` + DraftManager), no near-dup/coverage logic (TextWorkbench /
CoveragePanel internals) — leaving step scaffolding, field wiring, and the submit mapping, which
the DG wizard spends ~350 lines on today. Enforced by line count + an import-only audit (the shell
file defines no function containing a limit comparison or a fetch to a generation endpoint).

**Rejected alternative.** *RDA-first greenfield* — grows a third copy of everything before the
core exists (brief-rejected; P5 stays last, D5).

---

## 4. Component & File Map

New modules (exact proposed paths), the FRs they satisfy, and what each builds ON:

| # | Path | FRs | Builds on (binding reuse) |
|---|---|---|---|
| B1 | `backend/app/services/creative_specs.py` | FR1.1–FR1.6, FR6.1, NFR-D1/C1 | `creative_images.IMAGE_SLOT_SPECS` (geometry imported, never copied) |
| B2 | `backend/app/routers/creative.py` | FR1.2, FR4.1–FR4.5, FR3.1 | router conventions of `pmax.py`/`demand_gen.py` (422/502 shape) |
| B3 | `backend/app/services/creative_copy.py` | FR1.7–FR1.10, FR1.13 | `stream_agent_response` creative_director path; prompt policy block from `demand_gen.py:283-287`; clamps from B1 |
| B4 | `backend/app/services/near_dup.py` + `backend/tests/fixtures/near_dup_cases.json` | FR1.10, NFR-P1 | — (parity fixtures shared with F3) |
| B5 | `backend/app/services/batch_render.py` | FR2.3/FR2.4, NFR-Q1 | `studio.py` `_GENERATION_SEMAPHORE`, `_run_image_job` runner, `ad_assets` job rows + SSE |
| B6 | `creative_images.py` additions: `subject_bbox()`, `crop_survival()`, `landscape_logo` slot | FR2.5, FR6.1 | its own crop math; frozen after P3 (FR6.2) |
| B7 | `backend/app/services/brand_kit.py` | FR3.1–FR3.5 | `page_fetcher.fetch` (+`raw_html`), `prompt_drafter` Stage-1, `claim_gate` primitives, `ad_assets` |
| B8 | `backend/google_ads/services/campaign/rda_orchestrator.py` | FR6.1–FR6.2 | `demand_gen_orchestrator` recipe pattern, `creative_images` unchanged |
| B9 | `backend/tests/test_spec_registry_guard.py` | NFR-D1 | — |
| F1 | `frontend/src/lib/creativeSpecs.ts` (`useCreativeSpecs` provider) | FR1.2, NFR-P2 | TanStack Query + localStorage cache |
| F2 | `frontend/src/components/creative/TextWorkbench.tsx` (+`AngleChip`) | FR1.7/1.8/1.11 | `TextList` (extracted from `DemandGenWizard.tsx:939-993`) |
| F3 | `frontend/src/lib/nearDup.ts` | FR1.10, NFR-P1 | parity fixtures (B4) |
| F4 | `frontend/src/components/creative/{PolicyHintCard,BrandPresetToggle,ReferencePhotosPicker,BusinessNameField,ConfirmCreateModal}.tsx` | FR1.12 | extracted 1:1 from `DemandGenWizard.tsx` |
| F5 | `frontend/src/components/creative/useDraftJob.ts` | FR1.9, FR4.3 | poll+resume pattern from `demand_gen.py:583-639` client side |
| F6 | `frontend/src/components/creative/CoveragePanel.tsx` | FR5.1–FR5.4 | bundle + specs + nearDup, pure client computation |
| F7 | `frontend/src/components/creative/SmartAspectSet.tsx` | FR2.3/2.4/2.6 | `StudioPanel` Enhance flow, `SlotThumb`, batch endpoints |
| F8 | `frontend/src/components/creative/{DraftManager,useNamedDrafts}.tsx/ts` | FR4.1–FR4.5 | drafts CRUD (B2) |
| F9 | `frontend/src/components/creative/BrandKitPanel.tsx` | FR3.1, FR5.2/5.3 | `LibraryPicker`/`AssetLibrary` |
| F10 | `frontend/src/components/campaign/RdaWizard.tsx` | FR6.3/6.4 | everything above; <647 lines, import-only |

---

## 5. Data Model & Migrations

All migrations follow the `database.py` idempotent pattern (`if version < N`, additive
`ALTER TABLE` in try/except, `INSERT OR IGNORE INTO schema_version`).

**V27 — draft persistence (P1):** `creative_drafts` + `creative_jobs` as specified in AD-5, plus
indexes `idx_creative_drafts_scope (account_id, campaign_type, updated_at DESC)` and
`idx_creative_jobs_status (status, created_at)`. Startup sweep `running → interrupted` added to
app lifespan (not the migration — it must run every boot).

**V28 — image engine (P3):**

```sql
CREATE TABLE creative_batches (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, campaign_id TEXT,
    art_direction TEXT NOT NULL,          -- the approved Enhance prompt
    model TEXT NOT NULL, mode TEXT NOT NULL,  -- with_logo | without_logo | asset_anchored
    logo_asset_id TEXT, reference_asset_ids_json TEXT,
    slots_json TEXT NOT NULL,             -- [{slot, variants}]
    status TEXT NOT NULL DEFAULT 'running',   -- running | done | done_with_failures | cancelled
    est_credits INTEGER, created_at TEXT DEFAULT (datetime('now'))
);
-- ad_assets additions (children ARE the job rows):
ALTER TABLE ad_assets ADD COLUMN batch_id TEXT;          -- FK-ish to creative_batches
ALTER TABLE ad_assets ADD COLUMN slot TEXT;              -- logos|landscape|square|portrait|tall_portrait|landscape_logo
ALTER TABLE ad_assets ADD COLUMN variant_index INTEGER;
ALTER TABLE ad_assets ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE ad_assets ADD COLUMN parent_asset_id TEXT;   -- composite → base link (FR2.1)
ALTER TABLE ad_assets ADD COLUMN safe_zone_json TEXT;    -- per-slot flags + bbox (FR2.5)
ALTER TABLE ad_assets ADD COLUMN meta_json TEXT;         -- brand-kit object on type='brand_kit' rows (P4 uses it; added here once)
CREATE INDEX idx_ad_assets_batch ON ad_assets(batch_id, variant_index);
```

**No migration for P4:** `source='scraped'` and `type='brand_kit'` are new values in existing
columns; `meta_json` arrived in V28; the ownership allowlist lives in the existing `config` table
(`creative.owned_domains`). **No migration for P5.**

---

## 6. API Contracts

| Endpoint | Verb | Request (sketch) | Response (sketch) | Phase |
|---|---|---|---|---|
| `/api/creative/specs` | GET | — | full registry: `{campaign_types: {pmax:{...}, demand_gen:{...}, rda:{...}}, engine: {near_dup_threshold, batch_tile_cap, ...}, version}` — <100 ms, cacheable (NFR-P2) | P1 |
| `/api/accounts/{id}/creative-drafts` | GET/POST | POST `{name, campaign_type, bundle}` | list (filtered by `campaign_type` query) / created draft; 409 on name collision | P1 |
| `/api/accounts/{id}/creative-drafts/{draft_id}` | GET/PUT/DELETE | PUT `{name?, bundle?}` | draft row; PUT re-validates bundle vs registry (soft limits → `warnings[]`) | P1 |
| `/api/accounts/{id}/creative/copy-jobs` | POST | `{campaign_type, mode: draft\|rewrite_row\|diversify, brief, final_url, business_name, rows?, row_index?, target_angle?, locked_rows?, flagged_rows?, research_hash?}` | `{job_id, status}` | P1 storage / P2 contract |
| `/api/creative/copy-jobs/{job_id}` | GET | — | `{status, result?: {rows: [{text, angle, tier}], business_name?}, error?}`; `interrupted` after restart, never 404 | P1/P2 |
| `/api/studio/batch-render` | POST | `{account_id, campaign_id?, art_direction, model, mode, logo_asset_id?, reference_asset_ids?, slots: [{slot, variants}]}` — rejected client+server above `batch_tile_cap` | `{batch_id, tiles: [{asset_id, slot, variant_index}], est_credits}` | P3 |
| `/api/studio/batch-render/{batch_id}` | GET + `/stream` SSE | — | `{status, progress: {done, failed, total}, tiles: [{asset_id, slot, status, retry_count, safe_zone}]}` — progress monotonic (NFR-Q1) | P3 |
| `/api/studio/batch-render/{batch_id}/tiles/{asset_id}/retry` | POST | — | re-enqueues one tile (≤ `batch_retry_max`) | P3 |
| `/api/creative/brand-kit` | POST | `{url, account_id, confirm_ownership?}` | `{brand_name, logo_url, favicon_url, colors[], fonts[], hero_images[] (asset ids), claims[] (gated), partial, missing_fields[], kit_asset_id}`; 403 with robots/ownership reason | P4 |
| `/api/accounts/{id}/campaigns/rda` | POST | RDA bundle (registry-validated) | `{campaign_id, budget_id, ad_group_id, ad_id, asset_ids, warnings[]}` — mirrors DG create shape | P5 |
| existing `pmax`/`demand-gen` draft endpoints | — | become shims over copy-jobs in P2, **deleted at P2 exit** | — | P2 |

---

## 7. Strangler Migration Map

Exact swap order; every step lands additively and gates on the pre-existing DG + PMax suites
staying green (NFR-M1). Old code is deleted only after its consumer is green on the new path.

| Step | Phase | Swap | Regression gate |
|---|---|---|---|
| 1 | P1 | `creative_specs.py` + `GET /specs` land; orchestrator `_validate_bundle`s take `spec` param, local tables deleted; `ValidationReport` warnings channel added; PMax gap closures (FR1.4) ship as registry data | existing `test_demand_gen_orchestrator` / `test_pmax_resubmit` green with updated imports; guard test (B9) green |
| 2 | P1 | wizards fetch specs via `useCreativeSpecs`; `RULES` consts deleted; draft clamps in routers read registry | both wizard flows manual-checked; FR1.2 mock-spec test |
| 3 | P1 | `creative_drafts`/`creative_jobs` (V27); in-memory job dicts deleted; DraftManager + export/import on review steps; localStorage demoted | restart harness (FR4.3); DG/PMax draft tests green on DB-backed jobs |
| 4 | P1 | `TextList` → `TextWorkbench` (extraction only + paste-split + dup badge); both wizards import it | DG wizard tests unmodified-and-green (FR1.12 AC applies from here) |
| 5 | P2 | drafting contract → `[{text, angle, tier}]` via `creative_copy.py`; wizards' applyDraft consume rows; legacy draft endpoints shimmed then deleted | contract tests; ★ demo step 3/5 |
| 6 | P2 | assist components extracted one at a time (PolicyHintCard → BusinessNameField → BrandPreset+ReferencePhotos → ConfirmCreateModal), PMax consumes each as it lands; PMax drafter prompt reaches DG parity (FR1.13) | DG tests untouched; PMax component tests added; ★ demo steps 1–2, 6 |
| 7 | P2 | rewrite/diversify modes + CoveragePanel (text) + video nudge (FR5.4) | ★ full demo script live with Wassim — P2 mid-gate |
| 8 | P3 | batch renderer + SmartAspectSet entry in both wizards' StepImages; modes on generation requests; safe-zone flags; preflight | NFR-Q1 instrumentation + restart tests; single-shot Studio path untouched until SmartAspectSet is green, then legacy >6 hard-fail path retired |
| 9 | P4 | `brand_kit.py` + extract-brief refactor to the shared research object; BrandKitPanel; rationale + one-click themes | fetch-count spy; extract-brief regression tests; claims-gate fixture |
| 10 | P5 | RDA registry activation + `rda_orchestrator` + `RdaWizard` thin shell | shell <647 lines; import-only audit; `git diff` shows zero core/`creative_images.py` changes (FR6.2/6.3) |

---

## 8. Structural Fences

The repo culture: prefer unrepresentable over discouraged. Cheap fences this design commits to:

- **F1 — Limits import-only.** Enforcement code receives `CampaignSpec` objects; the constant
  tables are deleted, and the guard test tombstones their names. A validator with a local limit
  literal fails CI by name and by sentinel scan (AD-1).
- **F2 — Geometry single-source.** `creative_specs.py` composes slot geometry BY IMPORT from
  `creative_images.IMAGE_SLOT_SPECS`; the registry physically cannot disagree with the crop
  pipeline about aspects/minimums.
- **F3 — Policy without branches.** Prompt builders and validators read `spec.policy`; campaign
  type appears exactly once — as the registry lookup key (NFR-C1 flip-test enforces: changed
  fixture data changes behavior with zero code diff).
- **F4 — Frozen dataclasses.** The registry is immutable at runtime; there is no code path that
  writes a limit (mirrors the fleet's ApprovalToken-style "no mint site" discipline, scaled to
  this problem).
- **F5 — Detector parity lock.** The ONE sanctioned dual implementation (near-dup TS+Py) shares a
  fixture file asserted by both test suites and a threshold that only exists in the registry.
- **F6 — Job state has no memory home.** A grep-audit test (NFR-R1) fails on any module-level
  dict on a draft/batch path; job state exists only as DB rows.
- **F7 — Shell thinness is tested, not promised.** Line-count gate + import-only audit on
  `RdaWizard.tsx`; P5 exit runs a diff-scope check proving zero core changes (FR6.3).

---

## 9. Risk Mitigations (PRD §12 → design)

| Risk | Design element that carries it |
|---|---|
| R1 near-dup quality | threshold in registry (tunable data), labeled Mercan fixture set gate before P2 exit, `dismissed_dup_pairs` persisted in the bundle, detector behind a stable flag-shape interface (AD-2) |
| R2 credit burn | preflight + `batch_tile_cap` in registry, per-tile retry never re-renders finished tiles (terminal states immutable), `est_credits` recorded on the batch row for spend audit (AD-3) |
| R3 RDA spec drift | `verified:false` on every aggregator-sourced RDA entry, warnings-not-errors path, P5 exit gate = live-API confirmation before first real campaign (AD-1/AD-6) |
| R4 scraper posture | robots parser + `creative.owned_domains` allowlist + explicit confirm flag; widening = review, not config (AD-4) |
| R5 weak safe-zone | advisory-only flag, SlotThumb crop preview remains adjacent human truth, `subject_bbox` signature stable for vision-model drop-in (AD-3) |
| R6 SSR assumption breaks | per-field `partial`/`missing_fields` in the response — degradation is loud; renderer seam isolated in `brand_kit.extract` (AD-4) |
| R7 strangler regression | §7 step ordering with per-step gates; extraction before enhancement (step 4 extracts TextList verbatim before P2 grows it); creates stay PAUSED (AD-2, §7) |

---

## 10. Honesty Ledger — harder than the PRD makes it look

1. **FR1.2's "zero client-code change" holds for VALUES only.** Mocking `max_chars: 40 → 35`
   changes UI validation with no code change — true. Adding a NEW field *shape* (RDA's 4:1
   LANDSCAPE_LOGO slot) still needs a UI slot component instance and orchestrator field-type
   mapping; the registry makes it data-described, not code-free. The AC should be read (and
   tested) as value-drift-free, which is what NFR-D1 is for.
2. **FR2.6 credit estimates have no numeric substrate today.** `model_catalog.py` carries prose
   `cost_text` ("about 2 credits per image") only. The design adds a numeric `est_credits` per
   catalog entry — a hand-maintained estimate, not a Higgsfield quote; the preflight must label it
   "est." and the batch row records actuals (`generation_cost_credits` exists per tile) so
   estimates can be recalibrated from history.
3. **True computed-style color extraction is impossible without a renderer.** Static parsing gets
   declared colors from inline styles + `<style>` + linked CSS (extra sub-fetches, bounded at 3
   same-origin stylesheets) — good enough for operator-owned SSR pages, and role inference is
   heuristic. This is D2's accepted ceiling, surfaced per-field via `partial`, not discovered
   later.
4. **"Draft jobs survive restart" ≠ mid-LLM resume.** The Claude CLI subprocess dies with the
   backend. What survives: saved drafts (byte-identical), completed job results, and an in-flight
   job's full request as an `interrupted` row with one-click re-run. FR4.3's AC ("recoverable
   status, not a 404") is written compatibly — epics should not promise transparent resume.
5. **`claim_gate.py` was built for chat-output auditing, not seed filtering.** FR3.4 reuses its
   sentence/number-normalization primitives and the pinned-claims store behind a NEW
   `filter_claim_seeds()` entry point; treating it as a drop-in gate would silently no-op on
   scraped fragments.
6. **The soft-limit warnings channel requires touching both live validators.** `_validate_bundle`
   (PMax + DG) is errors-only; FR1.3 needs the `ValidationReport {errors, warnings}` refactor in
   P1 — on the two code paths Wassim's real campaigns use. The existing `warnings[]` response
   fields make the wire change free, but this is the highest-blast-radius P1 edit; it lands in §7
   step 1 behind the existing orchestrator suites plus new soft-limit tests.
7. **The near-dup detector is intentionally two implementations.** NFR-P1 (keystroke, zero
   network) + FR1.10's server-side diversify verification cannot be met by one runtime without
   shipping WASM or calling the server per keystroke. The parity-fixture lock (F5) is the honest
   containment; if the implementations ever disagree on a fixture, CI fails on both sides.
8. **Cross-slot total-image caps are a new validation concept.** FR1.4's "≤20 images per asset
   group" spans four slot groups; neither wizard nor orchestrator validates ACROSS slots today.
   The registry carries `total_image_cap`, and both the client meter (CoveragePanel) and
   `ValidationReport` sum across slots — small code, but a new category, called out so it isn't
   "just another max_count".

---

*Next step per the PRD: epics & stories, with §7's step table as the epic skeleton and the ★
usable-first demo (PRD §4) pinned mid-P2.*
