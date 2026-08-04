---
stepsCompleted: [01-prerequisites, 02-epic-design, 03-stories, 04-validation]
inputDocuments: [_bmad-output/planning-artifacts/prd-unified-creative-engine.md, _bmad-output/planning-artifacts/architecture-unified-creative-engine.md, _bmad-output/planning-artifacts/product-brief-unified-creative-engine.md]
workflowType: 'epics-and-stories'
lastStep: 4
parent: epics-v2.md
---

# Unified Creative Engine — Epic Breakdown

**Author:** Wassim (drafted by Dam3oun-Google)
**Date:** 2026-08-03
**Version:** 1.0
**Status:** ✅ BUILT — Epics 14–20 shipped 2026-08-03 → 2026-08-04 (see BUILD STATUS callout below)
**Contract:** prd-unified-creative-engine.md (37 FRs / 8 NFRs) · architecture-unified-creative-engine.md (AD-1…AD-6, §7 strangler map)
**Numbering note:** epics-v2.md occupies Epics 1–13 (11/12 reserved by the Studio track, both shipped). **14 is the next free number**; this subsystem takes Epics 14–20. Stories are `<epic>.<n>`.

---

> **✅ BUILD STATUS — 2026-08-04 (completion annotation; content below unchanged).** Epics 14–20 — the whole Unified Creative Engine — are BUILT and committed on `main` (`24d94ab` … Epic 20 close-out `4ed7759`+). Built 2026-08-03 → 2026-08-04 under the fleet's Fable-conducts / Opus-performs pattern. **Final suites: backend 671 pytest** (≥ the 496 baseline, NFR-T1) **· vitest 107** · `tsc -b` + `vite build` clean · CI spec-drift guard (`test_spec_registry_guard.py`) + RDA shell-gate (`RdaWizard.tsx` 643 < 647) + P5 diff-scope (`test_rda_policy.py::test_p5_diff_scope_zero_core_changes`) all green · **all 8 NFRs evidenced** in the Epic 20 close-out. Live `GET /api/creative/specs` serves `pmax` / `demand_gen` / `rda` with per-field sources. Per-story deltas live in `_bmad-output/feature-log.md` (reconciled under its Reconciled heading, 2026-08-04). Per the repo's Tier-2 drift discipline this is an annotation only — the artifact CONTENT is unchanged.

## Sizing key & conventions

- **S** ≈ ½ day · **M** ≈ 1 day · **L** ≈ 2 days (the three honesty-ledger Ls — 14.3, 16.4, 17.4 — may run to 3) of focused coding-subagent work. **★** = gate stories: 14.2 (CI spec-drift guard, lands EARLY, protects every later story) and 16.8 (mid-P2 usable-first — the PRD §4 demo script IS its acceptance test).
- **Every epic exit gate includes, always:** backend suite GREEN and ≥ the 496-test baseline (counted 2026-08-03; NFR-T1) · `tsc -b && vite build` clean · backend restart verification (launchctl relaunch, feature still works — [memory: reference_backend_launchagent]) · one `_bmad-output/feature-log.md` row per shipped story. Per-epic gates ADD to this, never replace it.
- **NFR-M1 applies to every story touching `DemandGenWizard.tsx` / `PMaxWizard.tsx` / either orchestrator:** pre-existing DG + PMax test files stay green; DG test files stay UNMODIFIED where the FR says so (FR1.12).

## Current-state inputs (landed since the PRD — stories account for these, never redo them)

| Commit | What landed | Story consequence |
|---|---|---|
| `cb76a04` | Tier-0: aspect-vs-catalog validation in `studio.py` (1.91:1 → "generate 16:9, crop at submit"), DG ad-picker endpoint, PMax video hard-gate removed | 16.7 builds the FR5.4 nudge ON the removed gate (precondition done). 17.3 adopts the same 1.91:1 answer for batch tiles. No story re-plans any Tier-0 item |
| `c7c95b4` | DG headline 30 → 40 in all three mirrored constants (`TEXT_RULES`, `_DG_DRAFT_LIMITS`, wizard `RULES`) | FR1.5's VALUE is live but as the exact mirrored-constant failure class NFR-D1 kills. 14.3/14.4/14.5 REPLACE those constants with registry reads and INHERIT `c7c95b4`'s tests (update imports, keep assertions). The 40-char drafter instruction + prompt snapshot (14.4) still stands |

**Repo facts verified 2026-08-03:** migration head = V26 (`database.py`) → V27/V28 are next. `_GENERATION_SEMAPHORE(6)` at `studio.py:54`. `TEXT_RULES` at `demand_gen_orchestrator.py:117` / `pmax_orchestrator.py:110`; `_DRAFT_LIMITS` `pmax.py:98`; `_DG_DRAFT_LIMITS` `demand_gen.py:220`; in-memory job dicts `pmax.py:109` / `demand_gen.py:226`. `DemandGenWizard.tsx` = 1,294 lines (the <647 shell gate's denominator). **Frontend has NO test runner today** — vitest bootstrap is explicit work in 14.5, not an assumption.

---

## FR Coverage Map

| FR / NFR | Stories |
|----|------|
| FR1.1–FR1.3 (registry, endpoint, verified flags) | 14.1, 14.3, 14.5, 20.1 |
| FR1.4 / FR1.5 / FR1.6 | 14.3 + 14.6 (server/client) / 14.3 + 14.4 + 14.5 / 14.1 + 14.4 + 14.6 |
| FR1.7–FR1.9 (contract, chips, rewrite) | 16.1, 16.2, 16.3 |
| FR1.10 (near-dup) / FR1.11 (paste-split) | 15.6 (client) + 16.4 (server + parity + diversify) / 15.6 |
| FR1.12–FR1.13 (assist extraction, PMax prompt parity) | 16.5, 16.6 |
| FR2.1–FR2.2 (modes, logo policy) / FR2.3–FR2.4 (batch, queue) | 17.2 / 17.1, 17.3, 17.4, 17.6 |
| FR2.5 (safe zone) / FR2.6 (preflight) | 17.5 / 17.6 |
| FR3.1–FR3.5 (scraper) | 18.1, 18.2, 18.3, 18.4 |
| FR4.1–FR4.5 (drafts) | 15.1, 15.2, 15.3, 15.4, 15.5 |
| FR5.1 / FR5.2–FR5.3 / FR5.4 | 16.7 (text) + 17.7 (image) / 18.5 / 16.7 |
| FR6.1–FR6.4 (RDA) | 14.1 (data ships P1), 17.5 (4:1 slot pre-added P3), 19.1–19.4 |
| NFR-D1 / NFR-Q1 / NFR-R1 / NFR-C1 | ★14.2 + 20.2 / 17.3 + 17.4 / 15.1 + 15.3 / 14.1 + 14.3 + 19.4 |
| NFR-M1 / NFR-T1 (≥496) | every epic exit gate; 15.6 + 16.5 explicit / every exit gate; 20.2 |
| NFR-P1 (<50 ms) / NFR-P2 (specs cheap) | 15.6 + 16.4 / 14.1 + 14.5 |

---

## Epic List

| Epic | Phase / strangler steps | One-liner | FRs / NFRs |
|---|---|---|---|
| **14 — Creative Spec Registry & Spec Truth** | P1a / steps 1–2 | One frozen registry replaces every mirrored constant; ValidationReport warnings channel; ★ CI drift guard lands EARLY | FR1.1–1.6 (+FR6.1 data-only) · D1, C1, P2 |
| **15 — Draft Persistence & Workbench Extraction** | P1b / steps 3–4 | V27 kills in-memory job dicts + singleton drafts; `TextList` → shared `TextWorkbench` with paste-split + client dup badge | FR4.1–4.5, FR1.11, FR1.10 (client) · R1, P1, M1 |
| **16 — Copy Workbench + PMax Parity ★** | P2 / steps 5–7 | `[{text, angle, tier}]` contract, per-row rewrite, parity-locked diversify, assist extraction, coverage v1 → ★ live demo | FR1.7–1.10, FR1.12–1.13, FR5.1 (text), FR5.4 · P1, M1 |
| **17 — Image Engine** | P3 / step 8 | V28 batches, 3 modes, wave scheduler under Semaphore(6), restart recovery, safe-zone, preflight, SmartAspectSet | FR2.1–2.6, FR5.1 (image) · Q1 |
| **18 — Page Asset Scraper + Rationale** | P4 / step 9 | `brand_kit.py` over `page_fetcher`, unified with extract-brief (one fetch), claims gate, rationale + one-click themes | FR3.1–3.5, FR5.2–5.3 |
| **19 — Display Consumer (RDA)** | P5 / step 10 | `rda_orchestrator` on the DG pattern + thin `RdaWizard` shell = the acceptance test of the core (<647 lines) | FR6.1–6.4 |
| **20 — Hardening & Live Verification** | close-out | Live-API sweep of `verified:false` entries; strangler-debt audit; baseline hold | FR1.3/FR6.1 follow-through · D1, T1 · R3, D6 |

---

## Epic 14: Creative Spec Registry & Spec Truth (P1a)

**Goal:** exactly ONE source of truth for creative limits, served at runtime, guarded by CI — the DG 30-vs-40 failure class becomes unrepresentable (AD-1, fences F1–F4).
**Depends on:** nothing (foundation epic). **Blocks:** everything.
**Build order:** 14.1 → 14.2 → {14.3, 14.4} → 14.5 → 14.6 (14.3 and 14.4 parallelizable after the guard exists).
**Exit gate (adds to the standard gate):** NFR-D1 guard green with all backend tombstones registered · `GET /api/creative/specs` consumed by BOTH wizards · every FR1.4 rejection proven by a test · DG 40-char live client AND server via registry · existing orchestrator/wizard suites green with only import updates (NFR-M1).

---

### Story 14.1: Registry module `creative_specs.py` + `GET /api/creative/specs`

As a developer,
I want all per-campaign-type creative limits as frozen data in one module, served verbatim over HTTP,
So that every later consumer (validator, drafter, wizard) can read one object instead of owning a copy.

**Trace:** FR1.1, FR1.2 (server), FR1.3 (flag shape), FR1.6 (knob data), FR6.1 (RDA data ships now, activates P5), NFR-C1, NFR-P2
**Size:** M · **Depends on:** —

**Acceptance Criteria:**

**Given** the new module `backend/app/services/creative_specs.py`
**When** it is imported
**Then** it exposes frozen dataclasses exactly per AD-1 (`TextFieldSpec`, `ImageSlotSpec`, `PolicyKnobs`, `CampaignSpec`, `EngineConfig`) plus `REGISTRY: dict[str, CampaignSpec]` for `pmax | demand_gen | rda` and `ENGINE: EngineConfig` (`near_dup_threshold=0.65`, `batch_tile_cap=20`, `batch_retry_max=2`)
**And** every seed value matches PRD §8 verbatim, each field carrying `verified` + `source` (PMax short-desc ≤60 and video 15/orientation `verified: False`; all RDA text/image entries `verified: False`)
**And** slot geometry (aspect/min dims) is composed BY IMPORT from `creative_images.IMAGE_SLOT_SPECS`, never copied (fence F2) — a test asserts identity, not equality
**And** attempting to mutate any spec at runtime raises (`FrozenInstanceError` test — fence F4)

**Given** the new router `backend/app/routers/creative.py` registered in `main.py`
**When** `GET /api/creative/specs` is called
**Then** it returns the full registry + engine block + `version` per the architecture §6 shape, responds < 100 ms (perf test), and a deep-compare test proves the response deserializes back equal to `REGISTRY` (round-trip half of the guard)

**Files:** `backend/app/services/creative_specs.py` (new), `backend/app/routers/creative.py` (new), `backend/app/main.py` (router include), `backend/tests/test_creative_specs.py` (new)

---

### Story 14.2: ★ CI spec-drift guard (`test_spec_registry_guard.py`)

As the build,
I want a tripwire that fails on any resurrected limit constant or unexplained sentinel literal,
So that the mirrored-constant failure class stays dead for every story after this one.

**Trace:** NFR-D1, FR1.1 (AC's guard clause)
**Size:** M · **Depends on:** 14.1

**Acceptance Criteria:**

**Given** `backend/tests/test_spec_registry_guard.py` (new)
**When** the suite runs
**Then** three checks execute per AD-1: (1) **tombstone check** — a registered list of retired constant names fails the build if any name reappears in its enforcement file (AST walk for `.py`, regex for `.tsx`); (2) **sentinel-literal scan** — AST/regex walk over the curated enforcement-file list (both orchestrators' validate paths, `demand_gen.py`/`pmax.py` draft clamps, both wizards, `TextWorkbench.tsx` once it exists) failing on any literal in `{15, 20, 25, 30, 40, 60, 80, 90, 128, 2048}` without a `# spec-ok: <reason>` / `// spec-ok: <reason>` pragma, with pragma count snapshot-asserted; (3) **round-trip check** — `GET /api/creative/specs` deep-equals `REGISTRY`
**And** the tombstone list starts EMPTY with a documented `register_tombstone()` helper — stories 14.3/14.4/14.5 MUST register their deleted constants in the same commit that deletes them (each of those stories carries this as an AC)
**And** the guard runs in the default pytest collection (no marker, no opt-in) so no later story can merge past it

**Files:** `backend/tests/test_spec_registry_guard.py` (new)

**Sequencing note:** lands immediately after 14.1, BEFORE any migration story — the scan mechanism protects 14.3+ from day one; tombstones accrete per deletion.

---

### Story 14.3: Live validators read the registry + `ValidationReport` warnings channel

As an operator,
I want both create-path validators enforcing registry limits with soft limits warning instead of blocking,
So that local validation matches Google exactly and unverified limits never block a real create.

**Trace:** FR1.1, FR1.3, FR1.4 (server), FR1.5 (server), NFR-C1, NFR-M1 · Honesty ledger #6 and #8 — highest-blast-radius P1 edit, on the two code paths Wassim's real campaigns use
**Size:** **L** (may run 3 d) · **Depends on:** 14.1, 14.2

**Acceptance Criteria:**

**Given** `_validate_bundle` in `demand_gen_orchestrator.py` and `pmax_orchestrator.py`
**When** refactored
**Then** each takes a `spec: CampaignSpec` resolved via `creative_specs` and returns `ValidationReport {errors[], warnings[]}`; `verified=False` violations land in `warnings` and ride the EXISTING `warnings: List[str]` field of `PMaxCreateResponse`/`DemandGenCreateResponse`; errors still raise; the local `TEXT_RULES` (×2), `BUSINESS_NAME_MAX_CHARS`, `MAX_LOGOS` tables are DELETED and tombstoned in the guard (the `field_type` enum mapping stays — Google-API plumbing, not a limit)
**And** the FR1.4 gap closures are enforced from registry data — server rejects: 16 PMax headlines · 26-char business name · 21st image ACROSS ratios (cross-slot sum, new category per honesty #8) · 26th search theme · 81-char theme · malformed final URL; server accepts-with-warning: zero ≤60 descriptions
**And** a 40-char DG headline passes, 41 rejected (registry value; `c7c95b4`'s orchestrator tests inherited with updated imports, assertions intact)

**Given** the pre-existing `test_demand_gen_orchestrator` / `test_pmax_resubmit` suites
**When** this story merges
**Then** they are green with ONLY import/signature updates, plus new soft-limit tests (NFR-M1)

**Files:** `backend/google_ads/services/campaign/demand_gen_orchestrator.py`, `backend/google_ads/services/campaign/pmax_orchestrator.py`, `backend/app/services/creative_specs.py` (ValidationReport lives beside the registry), `backend/tests/test_spec_registry_guard.py` (tombstones), existing orchestrator tests

---

### Story 14.4: Drafter clamps from the registry + DG 40-char drafter instruction

As a drafting pipeline,
I want clamp tuples and the HARD-LIMITS prompt block derived from the same `CampaignSpec`,
So that the prompt can never promise a different number than the validator enforces.

**Trace:** FR1.1, FR1.5 (drafter half), FR1.6 (prompt builder reads the knob)
**Size:** M · **Depends on:** 14.1, 14.2

**Acceptance Criteria:**

**Given** `_DG_DRAFT_LIMITS` (`demand_gen.py:220`) and `_DRAFT_LIMITS` (`pmax.py:98`)
**When** this story merges
**Then** both are DELETED and tombstoned; the draft routes derive clamps from `creative_specs.get(<type>).text` and build the HARD-LIMITS prompt block from the same object
**And** the DG drafter prompt contains the deliberate-40-char instruction ("use the extra 10 chars deliberately, not pad") — prompt snapshot test asserts it (FR1.5 AC)
**And** the prompt builder reads `spec.policy.on_image_text`: flipping `rda → allow_warned` in a fixture registry changes the emitted prompt with zero code diff (FR1.6 flip test, NFR-C1)

**Files:** `backend/app/routers/demand_gen.py`, `backend/app/routers/pmax.py`, `backend/tests/test_demand_gen_draft.py` (inherit `c7c95b4` assertions), guard tombstones

---

### Story 14.5: `useCreativeSpecs()` provider + wizard `RULES` deletion + vitest bootstrap

As a wizard,
I want limits fetched at runtime with stale-while-revalidate,
So that no client constant can ever disagree with the server again.

**Trace:** FR1.2 (client — "mocking a changed spec value changes UI validation with zero client-code change"), FR1.5 (client), NFR-P2
**Size:** **L** · **Depends on:** 14.1

**Acceptance Criteria:**

**Given** `frontend/src/lib/creativeSpecs.ts` (new — TanStack Query provider + localStorage-cached last response)
**When** a wizard mounts
**Then** it renders validation immediately from cache; submit is disabled ONLY when no specs have EVER been fetched; a mocked slow endpoint does not block render (NFR-P2 test)
**And** both wizards' local `RULES` consts are DELETED (tombstoned in the guard's regex list); all client validation reads the provider
**And** the FR1.2 mock test passes: serving `max_chars: 35` for DG headlines changes the UI over-limit boundary with zero component-code change

**Given** the frontend has NO test runner today (verified 2026-08-03)
**When** this story lands
**Then** it bootstraps vitest (devDependency + `"test"` script + minimal config) — this harness is load-bearing for FR1.2, FR1.10 parity (16.4), and every later component test; budgeted here, not assumed

**Files:** `frontend/src/lib/creativeSpecs.ts` (new), `frontend/src/components/campaign/DemandGenWizard.tsx`, `frontend/src/components/campaign/PMaxWizard.tsx`, `frontend/package.json` (+vitest), `frontend/vitest.config.ts` (new), `frontend/src/lib/creativeSpecs.test.ts` (new)

---

### Story 14.6: PMax client gap-closure mirrors + FR1.6 no-UI assertion

As an operator in the PMax wizard,
I want every FR1.4 server rejection mirrored as inline client validation,
So that I never learn about a limit from a 422.

**Trace:** FR1.4 (client), FR1.6 (no knob UI before P5)
**Size:** M · **Depends on:** 14.5, 14.3

**Acceptance Criteria:**

**Given** the PMax wizard on the specs provider
**When** the operator exceeds any FR1.4 limit
**Then** the client shows the over-limit state for: per-field max_count · business name >25 · >20 images summed ACROSS ratio groups (cross-slot meter, honesty #8) · >25 search themes · >80-char theme · malformed final URL — each with a component test
**And** soft-limit (`verified:false`) violations render as warnings, not blockers, matching the server channel (FR1.3)
**And** a component-tree test asserts NO on-image-text knob control renders anywhere in the P1–P4 builds (FR1.6/D3)

**Files:** `frontend/src/components/campaign/PMaxWizard.tsx`, `frontend/src/components/campaign/PMaxWizard.test.tsx` (new)

---

## Epic 15: Draft Persistence & Workbench Extraction (P1b)

**Goal:** drafts and draft jobs become DB rows (nothing lives in process memory — fence F6); the shared `TextWorkbench` exists with paste-split and the client near-dup badge.
**Depends on:** 14.1 (spec props), 14.5 (provider) for 15.5/15.6; 15.1–15.3 can run parallel to Epic 14 backend stories.
**Build order:** 15.1 → {15.2, 15.3} → {15.4, 15.5} · 15.6 after 14.5.
**Exit gate (adds):** a named draft survives `launchctl` restart byte-identical and round-trips export/import (FR4.3/4.5 ACs) · grep-audit test green — zero module-level job dicts on any draft path (NFR-R1) · DG wizard test files untouched-and-green after the 15.6 extraction (NFR-M1).

---

### Story 15.1: Migration V27 — `creative_drafts` + `creative_jobs` + startup sweep

As the persistence layer,
I want the two tables and the boot-time `running → interrupted` sweep,
So that draft state has a durable home before any consumer lands.

**Trace:** FR4.1 (table), FR4.3 (sweep), NFR-R1
**Size:** S · **Depends on:** —

**Acceptance Criteria:**

**Given** `database.py` at V26
**When** V27 runs (idempotent `if version < 27` pattern)
**Then** `creative_drafts` `{id, account_id, campaign_type, name, bundle_json, created_at, updated_at}` with `UNIQUE(account_id, campaign_type, name)` and `creative_jobs` `{id, kind, account_id, campaign_type, status, request_json, result_json, error_message, research_hash, created_at, updated_at}` exist, plus `idx_creative_drafts_scope` and `idx_creative_jobs_status` (AD-5 verbatim)
**And** app lifespan startup (NOT the migration) sweeps `creative_jobs` `running → interrupted` on every boot — restart test asserts a seeded `running` row reads back `interrupted`

**Files:** `backend/app/database.py` (V27), `backend/app/main.py` (lifespan sweep), `backend/tests/test_creative_drafts.py` (new)

---

### Story 15.2: Named drafts CRUD + `DraftManager` UI

As an operator,
I want create/list/load/rename/delete of named drafts per account,
So that a second draft never destroys the first.

**Trace:** FR4.1, FR4.2 (D4 per-account scope)
**Size:** M · **Depends on:** 15.1, 14.1 (router file)

**Acceptance Criteria:**

**Given** `GET/POST /api/accounts/{id}/creative-drafts` and `GET/PUT/DELETE /api/accounts/{id}/creative-drafts/{draft_id}` in `routers/creative.py`
**When** exercised
**Then** list filters by `campaign_type` query; POST returns 409 on name collision; PUT re-validates the bundle against the registry (soft limits → `warnings[]`); a draft saved under account A is invisible to account B
**And** two drafts of the same campaign type are independently retrievable; deleting one leaves the other intact (FR4.2 AC)

**Given** `DraftManager.tsx` + `useNamedDrafts.ts` on both wizards' review steps
**When** the operator saves/loads by name
**Then** the flow round-trips through the API with the wizard bundle as the payload

**Files:** `backend/app/routers/creative.py`, `frontend/src/components/creative/DraftManager.tsx` (new), `frontend/src/components/creative/useNamedDrafts.ts` (new), both wizards (review-step wiring)

---

### Story 15.3: Draft jobs → DB rows; in-memory dicts deleted

As a draft job,
I want to live as a `creative_jobs` row from birth,
So that a backend restart yields `interrupted` + one-click re-run, never a 404.

**Trace:** FR4.3, NFR-R1 · Honesty ledger #4 — restart survival ≠ mid-LLM resume; promise exactly what ships
**Size:** **L** · **Depends on:** 15.1

**Acceptance Criteria:**

**Given** `_dg_draft_jobs` (`demand_gen.py:226`) and `_draft_jobs` (`pmax.py:109`)
**When** this story merges
**Then** both dicts are DELETED; job create/read on both draft routes goes through a `creative_jobs` repo (thin store layer in `backend/app/services/creative_copy.py` — storage NOW, the P2 contract arrives in 16.1 per the API table's "P1 storage / P2 contract" split)
**And** the grep-audit test (fence F6) asserts no module-level dict remains on any draft path — added to the default collection like the spec guard
**And** restart harness: completed job result retrievable after app-context recreation; in-flight job reads back `interrupted` with its full `request_json`, and the wizard UI offers one-click re-run from it (no transparent resume promised)

**Files:** `backend/app/routers/demand_gen.py`, `backend/app/routers/pmax.py`, `backend/app/services/creative_copy.py` (new — job store only), `backend/tests/test_creative_jobs_restart.py` (new), both wizards (interrupted-state affordance)

---

### Story 15.4: localStorage demoted to crash cache + restore banner

As an operator,
I want the server row as the source of truth with local edits recoverable after a crash,
So that autosave keeps its value without owning my drafts.

**Trace:** FR4.4
**Size:** S · **Depends on:** 15.2

**Acceptance Criteria:**

**Given** the existing per-keystroke write-through in both wizards
**When** a wizard opens with a local cache NEWER than the loaded server draft
**Then** a restore banner offers local-vs-server; choosing server clears the cache
**And** the existing Google-ref stripping on rehydrate (`DemandGenWizard.tsx:131-141`) is pinned by a test — behavior unchanged

**Files:** both wizards, `frontend/src/components/creative/useNamedDrafts.ts`, wizard tests

---

### Story 15.5: JSON export/import on the review step

As an operator,
I want a draft to double as a template file,
So that the Panama bundle becomes the Greece bundle in one import.

**Trace:** FR4.5
**Size:** S · **Depends on:** 15.2, 14.5

**Acceptance Criteria:**

**Given** the review step of either wizard
**When** the operator exports then re-imports the bundle JSON (client-side Blob / file input — same shape the create API accepts)
**Then** the round-trip is deep-equal; an over-limit import surfaces per-field errors from `useCreativeSpecs()` client-side, is re-validated server-side on save, and never crashes

**Files:** `frontend/src/components/creative/DraftManager.tsx`, both wizards' review steps, vitest round-trip test

---

### Story 15.6: `TextList` → `TextWorkbench` extraction + paste-split + client near-dup badge

As both wizards,
I want ONE text editor component with paste-split and an instant dup badge,
So that P2 grows one component, not two.

**Trace:** FR1.11, FR1.10 (client half), FR1.12 (groundwork), NFR-P1, NFR-M1 · Strangler step 4 — extraction BEFORE enhancement
**Size:** **L** · **Depends on:** 14.5

**Acceptance Criteria:**

**Given** `TextList` (duplicated logic, canonical copy `DemandGenWizard.tsx:939-993`)
**When** extracted VERBATIM to `frontend/src/components/creative/TextWorkbench.tsx` (props take a `FieldSpec` from the provider) and both wizards import it
**Then** the DG wizard's existing test files pass UNMODIFIED (FR1.12's NFR-M1 clause applies from here forward)
**And** pasting 3 newline-separated lines into one row yields 3 rows, each clamped to `fieldSpec.max_chars`; a 45-char pasted DG headline shows over-limit at 40, not 30 (FR1.11 AC)

**Given** `frontend/src/lib/nearDup.ts` (new) implementing the AD-2 pinned algorithm (normalize → stopword-drop → suffix-fold → token-set Jaccard + containment; threshold from the registry via provider)
**When** rows change on keystroke/paste
**Then** near-dup pairs get an inline badge; a 15-row set completes < 50 ms with zero network calls (vitest perf + spy test — NFR-P1)
**And** the golden fixture file `backend/tests/fixtures/near_dup_cases.json` is CREATED here (stopword list ships in the fixture, not inline) and the vitest side asserts against it — the Python twin (16.4) locks parity against the SAME file

**Files:** `frontend/src/components/creative/TextWorkbench.tsx` (new), `frontend/src/lib/nearDup.ts` (new), `backend/tests/fixtures/near_dup_cases.json` (new), both wizards, `frontend/src/lib/nearDup.test.ts` (new)

---

## Epic 16: Copy Workbench + PMax Parity ★ (P2)

**Goal:** angle-aware drafting on one contract, deterministic diversify, the DG assist layer consumed by PMax — proven live by the ★ demo.
**Depends on:** Epics 14 + 15 complete.
**Build order:** 16.1 → {16.2, 16.6} → {16.3, 16.4, 16.5} → 16.7 → ★16.8.
**Exit gate (adds):** ★ demo script performed live with Wassim, all 6 steps pass (recorded) · near-dup deterministic + <50 ms both runtimes on the parity fixture · shared assist components exist ONCE, consumed TWICE · legacy per-type draft endpoints DELETED after both wizards are green on copy-jobs (strangler step 5) · image-only PMax bundle submits (FR5.4).

---

### Story 16.1: `creative_copy.py` contract — `[{text, angle, tier}]` + copy-jobs endpoints

As the drafting pipeline,
I want one service and one endpoint pair for all campaign types,
So that angle/tier structure exists at the contract level, not as prose.

**Trace:** FR1.7, FR1.13 (service seam), NFR-M1 (shim-then-delete)
**Size:** **L** · **Depends on:** 15.3, 14.4

**Acceptance Criteria:**

**Given** `POST /api/accounts/{id}/creative/copy-jobs` and `GET /api/creative/copy-jobs/{job_id}` (router `creative.py`, service `creative_copy.py`, jobs as `creative_jobs` rows)
**When** a `mode: draft` job completes
**Then** the result parses into typed rows `{text, angle, tier}` with `angle ∈ {promotional, feature, benefit, urgency, social_proof, aspiration, specificity}` and `tier ∈ {headline, long_headline, description, short_description}`; malformed rows are DROPPED with a logged warning, never crash the apply path (FR1.7 AC)
**And** the HARD-LIMITS prompt block and clamps derive from `CampaignSpec` (moved from the 14.4 router-level derivation into the service — routers become thin)
**And** the existing `pmax.py`/`demand_gen.py` draft routes become SHIMS over `creative_copy.py` (deleted at P2 exit, 16.8); `request_json`/`research_hash` persist on the job row

**Files:** `backend/app/services/creative_copy.py`, `backend/app/routers/creative.py`, `backend/app/routers/demand_gen.py` + `pmax.py` (shims), `backend/tests/test_creative_copy.py` (new)

---

### Story 16.2: `useDraftJob` hook + angle chips + row locks in TextWorkbench

As an operator,
I want every drafted row to wear its angle and be lockable,
So that regeneration respects what I've already approved.

**Trace:** FR1.7 (apply path), FR1.8
**Size:** M · **Depends on:** 16.1, 15.6

**Acceptance Criteria:**

**Given** `frontend/src/components/creative/useDraftJob.ts` (new — poll + resume-key pattern lifted from the `demand_gen.py:583-639` client side)
**When** both wizards' applyDraft consume typed rows through it
**Then** every row renders an `AngleChip` + lock toggle in `TextWorkbench`
**And** locked rows are ABSENT from any regenerate request payload (assert request body — FR1.8 AC); regenerated rows return with the requested angle

**Files:** `frontend/src/components/creative/useDraftJob.ts` (new), `frontend/src/components/creative/TextWorkbench.tsx` (+`AngleChip`), both wizards

---

### Story 16.3: Per-row AI rewrite (`rewrite_row` mode)

As an operator,
I want to rewrite exactly one row toward a target angle,
So that fixing one weak headline never risks the other fourteen.

**Trace:** FR1.9
**Size:** M · **Depends on:** 16.1, 16.2

**Acceptance Criteria:**

**Given** a `rewrite_row` job carrying `row_index` + `target_angle`
**When** it completes
**Then** ONLY row *i* is replaced (assert all other rows byte-identical)
**And** a page refresh mid-job resumes polling via the persisted resume key and applies the result (FR1.9 resume test — job row survives per 15.3)

**Files:** `backend/app/services/creative_copy.py`, `frontend/src/components/creative/TextWorkbench.tsx` (per-row rewrite button), `frontend/src/components/creative/useDraftJob.ts`

---

### Story 16.4: Server near-dup twin + parity lock + Diversify

As the diversify pipeline,
I want the Python detector parity-locked to the TS one and verifying its own output,
So that "Diversify" provably returns a set below threshold.

**Trace:** FR1.10, NFR-P1 · Honesty ledger #7 — the ONE sanctioned dual implementation; R1 threshold-tuning gate
**Size:** **L** (may run 3 d) · **Depends on:** 15.6, 16.1

**Acceptance Criteria:**

**Given** `backend/app/services/near_dup.py` (new) implementing the SAME pinned algorithm, threshold read from `ENGINE.near_dup_threshold`
**When** pytest AND vitest both run against `backend/tests/fixtures/near_dup_cases.json` (same path, symlink-free)
**Then** both suites assert IDENTICAL flag sets on every fixture case — a disagreement fails CI on both sides (fence F5)
**And** the fixture set includes the 2-known-near-dupes case: detector flags exactly those 2, identically on repeat runs, with zero CLI subprocess invocations during detection (spy assert — FR1.10 AC)

**Given** a `diversify` job carrying the client's `flagged_rows` + `locked_rows`
**When** it completes
**Then** locked rows were excluded from the regenerate payload; the server VERIFIES the regenerated set's pairwise similarity is below threshold before returning; `dismissed_dup_pairs` persist in the draft bundle (R1 escape hatch)
**And** before P2 exit, the threshold is tuned on a labeled fixture set built from REAL Mercan campaign copy (new fixture file; tuning result recorded in the story's feature-log row)

**Files:** `backend/app/services/near_dup.py` (new), `backend/app/services/creative_copy.py` (diversify mode), `backend/tests/fixtures/near_dup_cases.json` (+ labeled Mercan set), `backend/tests/test_near_dup_parity.py` (new), `frontend/src/lib/nearDup.test.ts` (parity side)

---

### Story 16.5: DG assist layer → shared components, PMax consumes

As the PMax wizard,
I want the five DG assist components by import,
So that the biggest perceived-quality jump lands as consumption, not copy-paste.

**Trace:** FR1.12, NFR-M1 (DG test files stay green UNMODIFIED)
**Size:** **L** · **Depends on:** 15.6, 14.5

**Acceptance Criteria:**

**Given** the five components inside `DemandGenWizard.tsx`
**When** extracted 1:1 into `frontend/src/components/creative/` — landing ONE AT A TIME in the architecture's order (PolicyHintCard → BusinessNameField → BrandPresetToggle + ReferencePhotosPicker → ConfirmCreateModal), PMax consuming each as it lands
**Then** each component exists exactly once (shared path); the PMax wizard renders all five (component tests per component); `referenceAssetIds`/`referenceNote` ride PMax's `baseContext`
**And** DG wizard behavior is unchanged — its existing test files pass UNMODIFIED at every intermediate commit (FR1.12 AC)

**Files:** `frontend/src/components/creative/{PolicyHintCard,BusinessNameField,BrandPresetToggle,ReferencePhotosPicker,ConfirmCreateModal}.tsx` (new ×5), `DemandGenWizard.tsx` (imports only), `PMaxWizard.tsx` (consumption), PMax component tests (new)

---

### Story 16.6: PMax drafter prompt parity

As the PMax drafter,
I want the DG policy block and a drafted business name,
So that PMax copy obeys the same guardrails DG copy does.

**Trace:** FR1.13
**Size:** S · **Depends on:** 16.1

**Acceptance Criteria:**

**Given** the PMax draft prompt built by `creative_copy.py`
**When** snapshot-tested
**Then** it contains the policy block (no prices, no guaranteed-approval, no `~ | +`, no em dashes — lifted from `demand_gen.py:283-287`) and the draft response includes a ≤25-char `business_name`

**Files:** `backend/app/services/creative_copy.py`, prompt snapshot test

---

### Story 16.7: CoveragePanel v1 (text) + PMax video nudge

As an operator,
I want an honest completeness meter and a nudge instead of a gate,
So that I fill slots for eligibility without chasing "Excellent".

**Trace:** FR5.1 (text scope), FR5.4 (builds ON `cb76a04`'s removed hard-gate)
**Size:** M · **Depends on:** 16.2, 16.4

**Acceptance Criteria:**

**Given** `frontend/src/components/creative/CoveragePanel.tsx` (new — pure client computation over bundle + specs + nearDup)
**When** rendered from a bundle fixture
**Then** it shows slot coverage (headlines n/max from spec), distinct-angle count, near-dup count — values assert correct; panel copy snapshot contains NO "Excellent"-chasing string; meter encourages filling slots, never maxing characters
**And** an image-only PMax bundle submits successfully; the "add your own video to beat the auto-generated slideshow" nudge + product-mismatch warning render whenever the video list is empty; no blocking validation references video count (FR5.4 AC)

**Files:** `frontend/src/components/creative/CoveragePanel.tsx` (new), both wizards, component tests

---

### Story 16.8: ★ Usable-first milestone — the PRD §4 demo live with Wassim + legacy endpoint deletion

As the owner,
I want to click through the six demo steps on the real Mercan account,
So that P2's value is proven felt, not claimed, before P3 starts.

**Trace:** PRD §4 (milestone gate), NFR-M1 (strangler step 5 deletion)
**Size:** S (orchestration; all code shipped by prior stories) · **Depends on:** 16.1–16.7 ALL

**Acceptance Criteria (the demo script IS the test — all six live, create paused):**

**Given** the real Mercan account
**When** Wassim runs the script
**Then** (1) PMax wizard step 1 shows the full DG-grade assist layer (brief, brand preset, reference photos, business-name 25-char counter); (2) a Panama QIP brief + preset + 2 library reference photos → Draft with Creative Director; (3) every returned row wears an angle chip and the drafter obeyed the policy block; (4) Diversify flags 2 near-dupes INSTANTLY (no LLM wait) and replaces them with missing-angle rows — coverage meter reads slots/angles/dupes correctly; (5) DG wizard accepts 40-char headlines and paste-of-3-lines → 3 rows; (6) PMax Create shows the confirm-before-create modal
**And** the session is recorded as the P2 mid-point check before P2 closes

**Given** both wizards green on `copy-jobs`
**When** the milestone passes
**Then** the legacy `pmax.py`/`demand_gen.py` draft-route shims are DELETED (tombstoned in the guard) — P2 exit condition

**Files:** demo recording reference in feature-log; `backend/app/routers/{pmax,demand_gen}.py` (shim deletion), guard tombstones

---

## Epic 17: Image Engine (P3)

**Goal:** one approved art direction → the full slot set, rendered in waves under the EXISTING Semaphore(6), surviving restart, with advisory safe-zone flags and a credit preflight.
**Depends on:** Epic 16 (StudioPanel/Enhance untouched until SmartAspectSet is green — strangler step 8).
**Build order:** 17.1 → {17.2, 17.3} → 17.4 → 17.5 → 17.6 → 17.7.
**Exit gate (adds):** 10-tile batch never exceeds 6 concurrent Higgsfield jobs (instrumented) AND survives kill-and-restart with completed tiles kept (NFR-Q1) · safe-zone flag fires on the edge-subject fixture, advisory-only · preflight caps at `ENGINE.batch_tile_cap` · text-on-image knob wired, still NO UI (D3) · legacy `aspects × variants > 6` hard-fail retired only after SmartAspectSet is green.

---

### Story 17.1: Migration V28 — `creative_batches` + `ad_assets` columns

As the batch engine,
I want the parent-batch table and child columns before any scheduler exists,
So that children ARE the existing job store (no second job table).

**Trace:** FR2.3/FR2.4 (data layer), AD-3
**Size:** S · **Depends on:** 15.1 (V27 ordering)

**Acceptance Criteria:**

**Given** `database.py` at V27
**When** V28 runs
**Then** `creative_batches` is created exactly per architecture §5 (id, account_id, campaign_id, art_direction, model, mode, logo_asset_id, reference_asset_ids_json, slots_json, status running|done|done_with_failures|cancelled, est_credits, created_at) and `ad_assets` gains `batch_id, slot, variant_index, retry_count, parent_asset_id, safe_zone_json, meta_json` + `idx_ad_assets_batch` — `meta_json` lands HERE once (P4 uses it, no P4 migration)

**Files:** `backend/app/database.py` (V28), migration test

---

### Story 17.2: Generation modes — with_logo / without_logo / asset_anchored

As an operator,
I want the three modes as explicit request fields with policy from the registry,
So that logo handling is data-driven and the base render is never lost.

**Trace:** FR2.1, FR2.2, NFR-C1
**Size:** **L** · **Depends on:** 17.1, 14.1

**Acceptance Criteria:**

**Given** generation requests carrying `mode` + `logo_asset_id` / `reference_asset_ids`
**When** `mode=with_logo` runs
**Then** the base image renders normally and the logo composites as a server-side Pillow paste; base and composite are TWO `ad_assets` rows linked by `parent_asset_id` — base recoverable (FR2.1 AC); the logo is NEVER re-prompted into the model
**And** `mode=asset_anchored` from the PMax wizard passes `--image` reference flags (request spy — backport via `referenceAssetIds` in PMax `baseContext`); `mode=without_logo` emits no logo instruction
**And** with-logo under a `forbid` `spec.policy.logo_overlay` type returns the policy warning and routes the logo to the logo slot; under `allow_warned` (PMax) the composite proceeds with the warning attached to the asset record (FR2.2 AC — fixture flip test, zero code diff)

**Files:** `backend/app/routers/studio.py` (request models), `backend/app/services/batch_render.py` (compositor helper, shared with 17.3), `frontend/src/components/studio/StudioPanel.tsx` (mode controls), `PMaxWizard.tsx` (baseContext), tests

---

### Story 17.3: `batch_render.py` — Smart ASPECT Set scheduler + endpoints

As the render queue,
I want one parent row + N child `ad_assets` rows walked by a supervisor under the EXISTING semaphore,
So that batches and ad-hoc generations share one ceiling and the >6 hard-fail dies.

**Trace:** FR2.3, FR2.4, NFR-Q1
**Size:** **L** · **Depends on:** 17.1

**Acceptance Criteria:**

**Given** `POST /api/studio/batch-render` (slots × variants; rejected client+server above `ENGINE.batch_tile_cap`)
**When** a 5-slot × 2-variant request lands
**Then** ONE `creative_batches` row + 10 child `ad_assets` rows (`status='pending'`) are created; the per-batch supervisor task in `backend/app/services/batch_render.py` runs each child through the SAME single-image runner, acquiring `studio.py:54`'s `_GENERATION_SEMAPHORE` — instrumented test proves ≤6 concurrent jobs on a 10-tile batch
**And** 1.91:1 tiles are requested as 16:9 per `cb76a04`'s catalog rule and pass `fit_image_for_slot` on assignment; every completed tile auto-assigns to its declared slot through the existing exact-aspect crop (±1% preserved — FR2.3 AC)
**And** `GET /api/studio/batch-render/{batch_id}` + `/stream` SSE report `{status, progress{done,failed,total}, tiles[]}` with progress MONOTONIC (property test — terminal states never revert); `POST .../tiles/{asset_id}/retry` re-enqueues one tile up to `ENGINE.batch_retry_max` with backoff; a failed tile leaves its slot empty with the retry affordance

**Files:** `backend/app/services/batch_render.py` (new), `backend/app/routers/studio.py` (endpoints; legacy >6 400 STAYS until 17.6 retires its callers), `backend/tests/test_batch_render.py` (new)

---

### Story 17.4: Batch restart recovery — supervisor respawn

As a running batch,
I want to survive a backend restart from DB state alone,
So that closing the laptop mid-run costs nothing.

**Trace:** FR2.4 (restart clause), NFR-Q1, R2 · Honesty: the architecture flags respawn as hard — reattach vs re-enqueue vs never-re-render must each be proven, not assumed
**Size:** **L** (may run 3 d) · **Depends on:** 17.3

**Acceptance Criteria:**

**Given** app lifespan startup
**When** `creative_batches` rows with `status='running'` exist
**Then** supervisors respawn for each; children WITH a `higgsfield_job_id` re-poll via the CLI's job-status reattach; children WITHOUT one re-enqueue; COMPLETED tiles are never re-rendered (R2 — assert zero generation calls for terminal children)
**And** the kill-and-restart harness proves: app context killed mid-batch → restart → queue resumes from DB rows, completed tiles kept, pending tiles resumable, progress still monotonic across the boundary (NFR-Q1 AC)
**And** a batch whose every child is terminal at sweep time is finalized `done`/`done_with_failures`, never left `running`

**Files:** `backend/app/services/batch_render.py` (recovery scan), `backend/app/main.py` (lifespan), `backend/tests/test_batch_restart.py` (new)

---

### Story 17.5: Safe-zone heuristic v1 + `landscape_logo` slot (pre-add for P5)

As an operator,
I want "subject will be cut" flags computed free and locally, plus the 4:1 slot added NOW,
So that 9:16 crops stop surprising me and P5 genuinely cannot need a `creative_images.py` edit.

**Trace:** FR2.5 (D1), FR6.1 (4:1 geometry, pre-added per AD-6), R5
**Size:** M · **Depends on:** 17.3 (flags stored at tile completion)

**Acceptance Criteria:**

**Given** `subject_bbox(img)` and `crop_survival()` added to `creative_images.py` (grayscale → `FIND_EDGES` → 8×8 block energy → mean+1σ threshold → largest-region bbox +4% pad; center-crop window shrunk to central 80%; flag when <80% of bbox survives)
**When** run on the fixtures
**Then** the edge-positioned-subject fixture flags 9:16 and NOT 1:1; the centered-subject fixture passes all ratios; zero network/vision-model calls (spy assert — FR2.5 AC)
**And** flags are computed at tile completion, stored in `safe_zone_json` (per-slot booleans + bbox); the UI renders an advisory amber chip BESIDE the SlotThumb crop preview (human truth, R5); submit is NEVER blocked
**And** `landscape_logo` (4:1, rec 1200×300, min 512×128) is added to `IMAGE_SLOT_SPECS` HERE — after this story `creative_images.py` is FROZEN (FR6.2's P5 diff gate becomes satisfiable)

**Files:** `backend/google_ads/services/campaign/creative_images.py` (LAST allowed edit), `backend/app/services/batch_render.py` (flag hook), SlotThumb-adjacent chip in wizard image steps, `backend/tests/test_safe_zone.py` (new + fixtures)

---

### Story 17.6: `SmartAspectSet.tsx` + credit preflight + legacy hard-fail retirement

As an operator,
I want "Generate the full set" with an honest cost preview,
So that one action fills every slot without surprise spend.

**Trace:** FR2.3 (UI), FR2.6 · Honesty ledger #2 — `model_catalog.py` has only prose `cost_text`; numeric `est_credits` is NEW hand-maintained data, labeled "est."
**Size:** **L** · **Depends on:** 17.3, 17.5

**Acceptance Criteria:**

**Given** `frontend/src/components/creative/SmartAspectSet.tsx` (new — layered on the StudioPanel Enhance flow) wired into BOTH wizards' image steps
**When** the operator approves one art direction and opens the preflight
**Then** the modal shows `tiles × est_credits(model)` labeled "est." (numeric `est_credits` field added per `model_catalog.py` entry — fixture-catalog test), current balance from the existing Studio credits path, and rejects above `ENGINE.batch_tile_cap` client-side with the cap NAMED (config-driven, no literal — guard-scanned)
**And** the queue UI renders per-tile states/progress/retry from the SSE stream; finished tiles appear in their slots via SlotThumb unchanged
**And** with SmartAspectSet green in both wizards, the legacy `aspects × variants > 6` hard-fail path's callers are migrated and the 400 branch DELETED (strangler step 8 completion; batch row records actuals via per-tile `generation_cost_credits` for estimate recalibration)

**Files:** `frontend/src/components/creative/SmartAspectSet.tsx` (new), `backend/app/services/model_catalog.py` (+`est_credits`), `backend/app/routers/studio.py` (legacy branch removal), both wizards' image steps, component + catalog tests

---

### Story 17.7: CoveragePanel — image-slot extension

As an operator,
I want the meter to cover aspect slots too,
So that "coverage" means the whole bundle, not just text.

**Trace:** FR5.1 (image scope)
**Size:** S · **Depends on:** 17.6, 16.7

**Acceptance Criteria:**

**Given** a bundle with partial slot fill
**When** CoveragePanel renders
**Then** it shows images n/cap (cross-slot total from `spec.total_image_cap`) and per-aspect slot filled/empty from registry slot specs; values assert against a fixture; still no "Excellent" language

**Files:** `frontend/src/components/creative/CoveragePanel.tsx`, component test

---

## Epic 18: Page Asset Scraper + Rationale (P4)

**Goal:** one fetch → one research object → brand-kit assets in the library AND seeds for copy, gated by pinned claims; rationale surfaced with one-click themes.
**Depends on:** Epic 16 (creative_copy consumes the research object); independent of Epic 17 except 18.5's panel placement.
**Build order:** 18.1 → {18.2, 18.3, 18.4} → 18.5.
**Exit gate (adds):** brand kit extracted from an owned SSR page into the library and reused across two campaign types · single-fetch spy green (FR3.3) · banned-claim fixture blocked (FR3.4) · robots + ownership refusals proven (FR3.5) · one-click theme respects registry caps.

---

### Story 18.1: `brand_kit.py` extraction over `page_fetcher` + partial honesty

As the scraper,
I want the extraction contract implemented on the EXISTING fetcher with loud partials,
So that CSS-in-JS degradation is surfaced, never silent.

**Trace:** FR3.1, FR3.2 (D2), R6 · Honesty ledger #3 — declared-color ceiling accepted, ≤3 same-origin stylesheet sub-fetches
**Size:** **L** · **Depends on:** — (page_fetcher exists)

**Acceptance Criteria:**

**Given** `backend/app/services/brand_kit.py` (new) with `extract(page) → BrandKit` over `page_fetcher.fetch()` (`FetchedPage` gains `raw_html` — same bytes re-parsed, no second HTML fetch)
**When** run on the SSR fixture page
**Then** every contract field returns per FR3.1 (logo via header/nav img/svg + rel=icon + og:image fallback; colors hex/rgb from inline + `<style>` + ≤3 linked same-origin stylesheets, frequency-ranked + role-inferred; fonts; hero/product images; claims from H1/H2/hero/meta ONLY) with `partial: false`
**And** the CSS-in-JS fixture returns `partial: true` + NAMED missing fields (FR3.2 AC); the v1 dependency manifest contains no Playwright/Chromium (manifest test); the renderer seam is the single `extract()` boundary

**Files:** `backend/app/services/brand_kit.py` (new), `backend/app/services/page_fetcher.py` (`raw_html`), `backend/tests/test_brand_kit.py` (new + 2 HTML fixtures)

---

### Story 18.2: Unify with extract-brief + `/api/creative/brand-kit` + persistence

As both the image path and the copy drafter,
I want the SAME research object from ONE fetch, persisted as library assets,
So that the second-scraper failure class never exists.

**Trace:** FR3.3, FR5.2 (data), strangler step 9
**Size:** **L** · **Depends on:** 18.1, 16.1

**Acceptance Criteria:**

**Given** `POST /api/creative/brand-kit` `{url, account_id, confirm_ownership?}`
**When** a kit is extracted
**Then** downloaded logo/hero images persist as `ad_assets` rows `source='scraped'` (pickable in `LibraryPicker` UNCHANGED); non-file fields persist as ONE `ad_assets` row `type='brand_kit'` with the kit in `meta_json` (V28 column) + sibling image ids — account-scoped, no new table
**And** `extract-brief` (`studio.py:748` → `prompt_drafter.draft_variants`) is refactored to consume `brand_kit.research_object(page)` for Stage-1 input, and `creative_copy.py` draft jobs receive the SAME object — identity assert via shared `research_hash` on the job row (FR3.3 AC)
**And** the fetch-count spy proves ONE HTML document fetch per URL per run (stylesheet/image sub-fetches counted separately, per the architecture's testable definition); existing extract-brief regression tests stay green

**Files:** `backend/app/services/brand_kit.py`, `backend/app/routers/creative.py`, `backend/app/routers/studio.py` (extract-brief refactor), `backend/app/services/prompt_drafter.py`, `backend/app/services/creative_copy.py` (research intake), tests

---

### Story 18.3: Claims gate — `filter_claim_seeds()`

As the copy pipeline,
I want scraped claims filtered against pinned facts BEFORE they seed drafts,
So that a scraped page can never resurrect the Panama stay-requirement class of error.

**Trace:** FR3.4 · Honesty ledger #5 — reuse `claim_gate` PRIMITIVES, not `run_claim_gate` (built for chat audit, would silently no-op on fragments)
**Size:** M · **Depends on:** 18.1

**Acceptance Criteria:**

**Given** `filter_claim_seeds(claims, account_id, campaign_id)` (new entry point in `brand_kit.py` or `claim_gate.py` — implementer's call, normalization/matching primitives + `prompt_drafter._load_pinned_claims` store reused either way)
**When** run on the fixture page containing a banned pinned claim
**Then** the claim appears in the RAW brand kit but NOT in the copy-seed output; the rejection is logged WITH the claim text (FR3.4 AC)

**Files:** `backend/app/services/brand_kit.py`, `backend/app/services/claim_gate.py` (primitives exposed), `backend/tests/test_claim_seeds.py` (new)

---

### Story 18.4: Ownership allowlist + robots posture

As the operator's agent,
I want the scraper structurally unable to run wild,
So that widening beyond owned properties stays a review, not a config flip.

**Trace:** FR3.5, R4
**Size:** S · **Depends on:** 18.1

**Acceptance Criteria:**

**Given** `robots.txt` fetched once per host (cached) and evaluated with `urllib.robotparser`
**When** a disallowed URL is requested
**Then** 403 with the robots reason (FR3.5 AC)
**And** a URL outside the `config`-table `creative.owned_domains` JSON allowlist requires `confirm_ownership: true` or is refused with the ownership reason

**Files:** `backend/app/services/brand_kit.py`, config-table seeding, `backend/tests/test_brand_kit.py`

---

### Story 18.5: `BrandKitPanel` + rationale surface + one-click themes/signals

As an operator,
I want the research shown beside the drafts and audiences one click from being targeting,
So that computed intelligence stops dying in a prompt.

**Trace:** FR5.2, FR5.3
**Size:** M · **Depends on:** 18.2, 16.7

**Acceptance Criteria:**

**Given** `frontend/src/components/creative/BrandKitPanel.tsx` (new, beside CoveragePanel; kit assets via LibraryPicker/AssetLibrary)
**When** a draft has research attached
**Then** the panel renders `value_prop, audience, tone, claim_hints`; absent research renders an honest empty state, not placeholders (FR5.2 AC)
**And** clicking a suggested audience appends a ≤80-char PMax search theme (or DG audience signal) respecting the registry ≤25 cap, and the click is IDEMPOTENT — no duplicate theme (FR5.3 AC)

**Files:** `frontend/src/components/creative/BrandKitPanel.tsx` (new), both wizards, component tests

---

## Epic 19: Display Consumer — RDA (P5)

**Goal:** ship Responsive Display Ads as an almost-empty shell — the structural proof the core is real (fence F7).
**Depends on:** Epics 14–18 ALL (the shell consumes everything).
**Build order:** 19.1 → 19.2 → 19.3 → 19.4.
**Exit gate (adds):** `RdaWizard.tsx` < 647 lines + import-only audit green · P5 `git diff` shows ZERO changes to `creative_images.py` or any `components/creative/` core file (FR6.2/FR6.3 structural checks) · 4:1 LANDSCAPE_LOGO validates end-to-end · RDA `verified:false` limits confirmed via 20.1 BEFORE the first real RDA campaign (R3).

---

### Story 19.1: RDA registry activation + validation

As the registry,
I want the dormant `rda` entry activated and enforced,
So that RDA limits are data on day one, softly enforced until verified.

**Trace:** FR6.1 (activation — data shipped in 14.1), FR1.3 (soft path)
**Size:** M · **Depends on:** 14.1, 14.3, 17.5 (`landscape_logo` geometry exists)

**Acceptance Criteria:**

**Given** the `rda` `CampaignSpec` (short headlines 1–5×30 · long headline EXACTLY 1×90 · descriptions 1–5×90 · business name 25 · images ≤15/ratio · logos 1:1 + 4:1, all `verified: false`)
**When** validated through `ValidationReport`
**Then** 2 long headlines are REJECTED (exactly-1 is enforceable structure, not a soft limit); a soft-limit violation on any `verified:false` field WARNS, not blocks; `/api/creative/specs` serves the `rda` block with the 4:1 slot geometry imported from `creative_images.IMAGE_SLOT_SPECS.landscape_logo`

**Files:** `backend/app/services/creative_specs.py` (activation flag/wiring), `backend/tests/test_creative_specs.py`

---

### Story 19.2: `rda_orchestrator.py` + `POST /api/accounts/{id}/campaigns/rda`

As the create path,
I want RDA on the DG recipe with `creative_images` untouched,
So that the orchestrator is plumbing, not a third creative implementation.

**Trace:** FR6.2
**Size:** **L** · **Depends on:** 19.1

**Acceptance Criteria:**

**Given** `backend/google_ads/services/campaign/rda_orchestrator.py` (new) on the `demand_gen_orchestrator` recipe shape (budget → campaign → ad group → ONE `ResponsiveDisplayAdInfo` ad, PAUSED, rollback on step failure)
**When** a registry-validated bundle is submitted
**Then** the response mirrors the DG create shape `{campaign_id, budget_id, ad_group_id, ad_id, asset_ids, warnings[]}`; the orchestrator emits correct RDA asset field types INCLUDING `LANDSCAPE_LOGO` (field type absent repo-wide until now)
**And** the story's diff contains ZERO changes to `creative_images.py` (structural check runs from this story onward, not just at exit)

**Files:** `backend/google_ads/services/campaign/rda_orchestrator.py` (new), `backend/app/routers/creative.py` (or campaigns router per repo convention — implementer verifies where DG create mounts), `backend/tests/test_rda_orchestrator.py` (new)

---

### Story 19.3: `RdaWizard.tsx` — the thin shell

As the proof of the core,
I want a four-step wizard that defines nothing creative,
So that building it requires touching zero core components.

**Trace:** FR6.3
**Size:** M · **Depends on:** 19.2 + all core components (Epics 14–18)

**Acceptance Criteria:**

**Given** `frontend/src/components/campaign/RdaWizard.tsx` (new — brief → text → images → review)
**When** audited
**Then** line count < 647 (half of DemandGenWizard's 1,294) — CI-asserted; the import-only audit passes: the shell file defines NO function containing a limit comparison or a fetch to a generation endpoint; TextWorkbench, CoveragePanel, SmartAspectSet, DraftManager, BrandKitPanel, useCreativeSpecs, useDraftJob, useNamedDrafts all arrive by import
**And** an RDA bundle flows brief → drafted angle-tagged text → Smart ASPECT Set images → named draft → create PAUSED, end-to-end

**Files:** `frontend/src/components/campaign/RdaWizard.tsx` (new), route registration, shell-audit test (line count + AST/regex import-only check)

---

### Story 19.4: RDA policy rules from the registry + P5 structural exit checks

As the exit gate,
I want RDA's rules provably data and the diff provably clean,
So that FR6's "the shell is the acceptance test" claim is checked by machine.

**Trace:** FR6.4, FR6.2/FR6.3 (exit checks), NFR-C1
**Size:** M · **Depends on:** 19.2, 19.3

**Acceptance Criteria:**

**Given** the RDA prompt builder and image modes
**When** fixture-flip tested
**Then** the text-free instruction emits from the registry `forbid` knob (flip → prompt changes, zero code diff); a with-logo overlay request under `rda` routes to the logo slot per FR2.2; ">80% blank" and text-discount rules read from registry entries
**And** the P5 diff-scope check passes: zero changes to `creative_images.py` and zero changes to `frontend/src/components/creative/*` across the whole epic (FR6.2/FR6.3 gate — brief metric #6)

**Files:** prompt-builder flip tests, `backend/tests/test_rda_policy.py` (new), diff-scope check script/test

---

## Epic 20: Hardening & Live Verification

**Goal:** close the honest loops — verify every `verified:false` number against the live API, and prove the strangler left no debt.
**Depends on:** Epic 19 (20.1's RDA half is a P5-exit prerequisite; the PMax half can run any time after Epic 14).
**Exit gate:** all registry entries either `verified: true` with updated `source` citations or corrected · guard tombstone list complete (every retired constant + deleted shim registered) · suite ≥ baseline 496 + all new tests, green · feature-log Tier-2 reconcile row appended.

---

### Story 20.1: Live-API verification sweep of `verified:false` entries

As the registry,
I want every unverified number checked against the live Google Ads API,
So that the registry never confidently enforces a wrong limit (the R3 failure at the data layer).

**Trace:** FR1.3, FR6.1, D6, R3
**Size:** M · **Depends on:** 14.1 (PMax/DG entries — runnable early); 19.1 (RDA entries — REQUIRED before the first real RDA campaign)

**Acceptance Criteria:**

**Given** the `verified: false` set (PMax short-desc ≤60, PMax video 15/orientation, final-URL 2048, all RDA text/image entries)
**When** each is exercised against the live API (validate-only/paused creates on the real Mercan account)
**Then** each entry flips to `verified: true` with an updated `source` citation, or its VALUE is corrected in the same commit with the API evidence cited
**And** any correction automatically propagates everywhere (that is the registry's whole point — a spot-check test per corrected value confirms client + server + drafter all moved)

**Files:** `backend/app/services/creative_specs.py` (flag/value updates), verification notes in `source` fields, feature-log row with findings

---

### Story 20.2: Strangler-debt audit + baseline hold

As the release gate,
I want machine proof the migration finished,
So that no shim, dict, or constant outlives its replacement.

**Trace:** NFR-D1, NFR-R1, NFR-T1, NFR-M1
**Size:** S · **Depends on:** all epics

**Acceptance Criteria:**

**Given** the full suite
**When** run at close
**Then** the guard's tombstone list covers ALL of: `TEXT_RULES` ×2, `_DRAFT_LIMITS`, `_DG_DRAFT_LIMITS`, `BUSINESS_NAME_MAX_CHARS`, `MAX_LOGOS`, wizard `RULES` ×2, legacy draft shims, the `aspects × variants > 6` branch; the grep-audit finds zero module-level job dicts; the pragma-count snapshot is reviewed and re-pinned
**And** backend suite ≥ 496 baseline + all engine tests, green; `tsc -b && vite build` clean; vitest suite green; backend restart verification passes; a Tier-2 reconcile row lands in `feature-log.md`

**Files:** `backend/tests/test_spec_registry_guard.py` (final tombstones), feature-log

---

## Dependency Graph & Implementation Order

```
E14: 14.1 → 14.2★ → {14.3, 14.4} → 14.5 → 14.6          E15: 15.1 → {15.2, 15.3} → {15.4, 15.5} · 15.6 after 14.5
E16 (needs 14+15): 16.1 → {16.2, 16.6} → {16.3, 16.4, 16.5} → 16.7 → 16.8★
E17 (after 16):    17.1 → {17.2, 17.3} → 17.4 → 17.5 → 17.6 → 17.7
E18 (needs 16.1; parallel-safe with 17 except 18.5): 18.1 → {18.2, 18.3, 18.4} → 18.5
E19 (needs 14–18 ALL; 17.5 pre-adds its geometry):   19.1 → 19.2 → 19.3 → 19.4
E20: 20.1 (PMax half after E14; RDA half gates P5 close) → 20.2 last
```

Strict phase order per PRD §10 / architecture §7 — strangler steps 1–10 map to: 14.1–14.3 = step 1 · 14.4–14.6 = step 2 · 15.1–15.5 = step 3 · 15.6 = step 4 · 16.1–16.2 = step 5 · 16.5–16.6 = step 6 · 16.3/16.4/16.7/16.8 = step 7 · E17 = step 8 · E18 = step 9 · E19 = step 10. Within a phase, parallelize only where the graph allows; every wizard-touching story lands additively behind green pre-existing suites (NFR-M1).

## Validation Notes (04-validation)

- **All 37 FRs and 8 NFRs are placed** (coverage map above); no FR was left homeless. FR1.10 is deliberately split across phases (client badge P1/15.6 per architecture step 4; server twin + parity + diversify P2/16.4 per PRD phase) — the PRD/architecture phase disagreement is resolved in the architecture's favor for the client half because step 4's extraction is when `TextWorkbench` is open on the bench.
- **Size totals (S=½, M=1, L=2; the three flagged Ls may run 3):** E14 8 · E15 6.5 · E16 10 · E17 10 · E18 6.5 · E19 5 · E20 1.5 ≈ **47.5 nominal days** (upper ~51). This exceeds the brief's 22–31 d sum — the delta is honest, not padded: the brief's P1 "3–5 d" did not price the live-validator refactor (honesty #6), the vitest bootstrap (runner absent, verified), the dual-detector parity lock (honesty #7), or supervisor respawn (R2). Wall-clock compresses heavily under the fleet's parallel-subagent build pattern; the graph above marks every parallel-safe pair.
- **Baseline discipline:** 496 backend test functions at draft time; every epic exit re-asserts ≥ baseline + green, so the number only ratchets up.
