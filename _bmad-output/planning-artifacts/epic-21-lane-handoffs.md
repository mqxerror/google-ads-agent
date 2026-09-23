---
stepsCompleted: [01-prerequisites, 02-epic-design, 03-stories, 04-validation]
inputDocuments: [transcript evidence — MapleRoots Citizenship by Descent US (2026-07-29 → 2026-08-12), memory:project_scheduled_plans, memory:project_campaign_scope_guard, memory:project_pause_guard, memory:project_campaign_summary_dashboard]
workflowType: 'epics-and-stories'
lastStep: 4
parent: epics-v2.md
---

# Lane Handoffs & the Decision Queue — Epic Breakdown

**Author:** Wassim (drafted by Dam3oun-Google)
**Date:** 2026-08-12
**Version:** 1.0
**Status:** 📋 SPECIFIED — not started
**Contract:** self-contained (epic-scoped; no separate PRD). Requirements are numbered **H1–H12** below and mapped to stories.
**Numbering note:** epics-v2.md occupies Epics 1–13; the Unified Creative Engine took **14–20** (all BUILT 2026-08-03 → 08-04). **21 is the next free number.** Stories are `21.<n>`.

---

## The problem this epic closes

The campaign scope guard is correct and **stays exactly as it is** — a persona locked to campaign X must not touch campaign Y ([[project_campaign_scope_guard]]: prompt rules failed 6× in 24h; only the transport-layer block held). But the guard only decides what a persona may *do*. It says nothing about what happens to a recommendation that **exits the lane** — and today the answer is: it becomes prose, gets re-argued next session, and dies.

Measured on one real account (MapleRoots, 1,334-line export, 50 messages, **2026-07-29 → 2026-08-12**):

| Evaporated item | Lane it exits into | Repetitions | Standing | Cost of the gap |
|---|---|---|---|---|
| **Landing-page rebuild** (from the May CRO audit's P2 eligibility quiz) | external build | **9 assistant messages** across Aug 4/5/10/11 | ~3 months | QS<5 keywords carry **$2,854 of $4,295.79** 30-day spend (66%) → modeled **~$170/wk CPC premium**; "~$170 of the ~$240/wk identified waste has no in-campaign lever" |
| **GCLID offline-conversion upload** | external build | 2 messages, verbatim *"standing since Jul 21"* both times | **22 days** | Hard gate on PMax ("PMax becomes safe to try only after…") |
| **Demand Gen post-mortem** | another campaign's session | slipped across **5 messages**, Aug 6 → Aug 12 | due date arrived + passed in-transcript | DG took **652 clicks in one day, 23× MapleRoots' volume, 0 conversions**; agent is campaign-locked and *cannot even confirm it is still running* |
| **8-negative `[EXACT]` batch** | owner decision | pitched Aug 10, re-pitched Aug 11, re-pitched Aug 12 — **203 / 225 / 184 words ≈ 610 words re-arguing one batch** | 3 sessions, no ruling | 7 DIY terms **40 clicks / $192.95 / 0 conv** + 1 term **27 clicks / $137.04 / 0 conv**; ≈**$53/wk visible waste**, **$10.57 burned Aug 11→12 while waiting** |

Verbatim re-argument tax from the same export: *"the batch has now straddled three sessions without a ruling"* · *"We have never addressed this"* · *"Still standing from this morning's pulls"* · *"The honest caveat I gave you Monday still applies."*

**The load-bearing discovery (repo-verified 2026-08-12):** `scheduler._APPROVAL_CATEGORIES = {"budget","bids","status","geo"}` (`backend/app/services/scheduler.py:44`). **`search_terms` is already an auto-mode category** — the 8-negative batch never needed a go/no-go at all. The jam was not a missing gate; it was a persona asking for permission the system does not require, three sessions running, because no *documented bar* existed to let it act. Story 21.5 encodes the bar; it does not weaken a single existing gate.

**Thesis:** the guard decides *scope*; this epic decides *fate*. Anything that exits the lane becomes a row — surfaced, aged, and closed by one click, never re-argued.

---

## Sizing key & conventions

- **S** ≈ ½ day · **M** ≈ 1 day · **L** ≈ 2 days of focused coding-subagent work. **★** = gate stories: **21.1** (the entity + its no-mutation fence, lands first, every later story depends on it) and **21.4** (usable-first — the Decision Queue clearing the four real MapleRoots items IS this epic's acceptance test).
- **Every epic exit gate includes, always:** backend suite GREEN and ≥ the **671-test baseline** (counted 2026-08-04, Epic 20 close-out) · `tsc -b && vite build` clean · backend restart verification (launchctl relaunch, feature still works — [[reference_backend_launchagent]]) · one `_bmad-output/feature-log.md` row per shipped story. Per-epic gates ADD to this, never replace it.
- **Design system:** all new UI reads `frontend/DESIGN.md` tokens (Shopify-calm light). Never reintroduce dark ([[feedback_design_system_light]]).
- **Standing invariant for every story in this epic:** `CampaignScopeMiddleware`, `_APPROVAL_CATEGORIES`, and the pause guard are **unchanged**. Any story that appears to need one of them relaxed is mis-specified — re-scope it instead.

## Repo facts verified 2026-08-12 (stories build on these — do not re-derive)

| Fact | Location |
|---|---|
| Migration head = **V28**, one monolithic `init_db()`, pattern `if version < N:` → `executescript` → `INSERT OR IGNORE INTO schema_version` → `commit()` → `logger.info("VN migration complete (…)")` | `backend/app/database.py` |
| `scheduled_plans` + `scheduled_plan_runs` (V17 block, L845–897); status `scheduled\|due\|running\|awaiting_approval\|done\|failed\|paused`; `mode` `auto\|approval`; `action_category` `budget\|bids\|status\|geo\|search_terms\|audit\|report\|other` | `backend/app/database.py` |
| Scheduler: 60 s tick, `WHERE status='scheduled' AND next_run_at <= now` → `_fire()` dispatches on `action_category`; `_APPROVAL_CATEGORIES` L44; `infer_mode()` L88; concurrency cap 2 | `backend/app/services/scheduler.py` |
| **No approvals table exists** — approval is the `awaiting_approval` status + `proposed_change` TEXT, driven by `approve/skip/snooze/run-now` | `backend/app/routers/plans.py` (`prefix="/api/plans"`, 288 L) |
| `finding_actions` (V20, L969) — the precedent: operator decision-state keyed `(account_id, finding_key)`, nullable `plan_id` FK into `scheduled_plans`, `dollar_impact_wk` snapshot, and the in-code law *"No Google Ads mutation ever lives here; execution is always the plan path (scheduler.py), which is scope-guarded."* | `backend/app/database.py` |
| Router registration: bulk import L9, `app.include_router(plans.router)` **L118**; scheduler started in `lifespan` L44–45 | `backend/app/main.py` |
| Scope guard: `class CampaignScopeMiddleware` **L482**, `on_call_tool` L503 reads `LANGAR_BOUND_CAMPAIGN_ID`, inspects `*campaign_id*` keys **and** `resource_name` paths; skipped when unbound or `build-*` | `backend/google_ads/mcp_main.py`; env set by `backend/app/services/agent.py` L1745–1760 |
| Dashboard "Upcoming" = `['plans-upcoming']` → `GET /api/plans/upcoming?account_id=` (`api.ts` L1477, `Plan` iface L1404) | `frontend/src/components/dashboard/AgentActivity.tsx` L154 |
| Plans UI | `frontend/src/components/plans/{PlansPanel,PlanForm}.tsx`, `planHelpers.ts`; mounted as the "Plans" tab in `CampaignTabs` |
| `backend/app/services/task_ledger.py` is **pure-read memory recall — no table**. It is not the persistence layer this epic needs | `backend/app/services/task_ledger.py` |

---

## Architecture decision: NEW table, not an extension of `scheduled_plans`

**Recommendation: a new `lane_handoffs` table (V29), following the `finding_actions` precedent — with a nullable `plan_id` FK into `scheduled_plans`.**

Rationale, grounded in the code above, not in taste:

1. **`scheduled_plans` is structurally a time-triggered executor, not a ledger.** Its tick selects `WHERE status='scheduled' AND next_run_at <= now` and `_fire()` dispatches on `action_category` into `stream_agent_response`. A handoff has **no due-time trigger and no in-process executor** — "rebuild the landing page" is never something the scheduler runs.
2. **Over half the plan columns are meaningless for a handoff:** `run_at, recurrence, timezone, next_run_at, last_run_at, last_result, last_cost, run_count, proposed_change`. Extending would mean nine nullable columns plus a discriminator, and every scheduler query would need `AND kind='plan'` — a filter the tick loop currently does not need and could silently forget, which is a live-spend failure mode.
3. **The status vocabularies do not overlap.** Plans: `scheduled|due|running|awaiting_approval|done|failed|paused`. Handoffs: `open|acknowledged|in_progress|done|dismissed`. Only `done` is shared, and it means different things.
4. **The precedent already exists and works.** `finding_actions` is exactly this shape — a small decision-state table beside the executor, joined by a nullable `plan_id`. Reusing its pattern keeps the in-code law intact: *execution is always the plan path, which is scope-guarded.*
5. **Cross-campaign by nature.** A handoff's whole point is that it outlives and out-scopes its origin campaign; `scheduled_plans` rows are campaign-scoped operating instructions.

**Where they join:** when a handoff *does* become a runnable action (e.g. the operator turns "run the DG search-term hunt" into a scheduled task), the handoff stores the resulting `scheduled_plans.id` in `plan_id` and closes when that plan completes. One direction, one FK, no duplication of lifecycle.

## Requirement → story map

| # | Requirement | Stories |
|---|---|---|
| H1 | Handoff entity persisted: source (campaign + conversation + role), summary, frozen evidence snapshot, target lane, status, created/due, age | ★21.1 |
| H2 | Emit-once — a re-emit is a *reference* (bumps `restate_count`), never a second row | ★21.1, 21.2 |
| H3 | A handoff never mutates Google Ads; execution stays the plan path | ★21.1, 21.5 |
| H4 | Scope guard unchanged; `emit_handoff` provably cannot reach a mutation or a cross-campaign Ads call | 21.2 |
| H5 | Open handoffs injected into persona context; referenced by **id + age**, never re-argued | 21.3 |
| H6 | Reviews carry a fixed, hard-capped "Open handoffs" section | 21.3 |
| H7 | Decision Queue on the dashboard: open handoffs + `awaiting_approval` plans, one click each | ★21.4 |
| H8 | Per-campaign queue view | ★21.4 |
| H9 | Standing orders — items meeting a documented bar auto-execute via the existing auto lane, reported post-hoc | 21.5 |
| H10 | Gated categories (budget/bids/status/geo) + pause guard unchanged; standing orders are not a backdoor | 21.5 |
| H11 | Aging ladder + escalation surfaces (badge, review header) | 21.6 |
| H12 | No silent drop — closure only by explicit operator action or linked plan completion | 21.6, 21.7 |

---

## Epic 21: Lane Handoffs & the Decision Queue

**Goal:** every recommendation that exits the campaign lane becomes a durable, surfaced, aging row — emitted once, referenced by id thereafter, and cleared with one click. The re-argument tax goes to zero; nothing is silently dropped.
**Depends on:** V17 Scheduled Plans (join target), V20 `finding_actions` (pattern), the scope guard (unchanged).
**Blocks:** nothing — additive.
**Build order:** ★21.1 → {21.2, 21.6} → 21.3 → ★21.4 → 21.5 → 21.7. (21.2 and 21.6 parallelize once the table exists; 21.5 needs 21.4's queue to report into.)
**Exit gate (adds to the standard gate):** the four real MapleRoots items exist as rows and are clearable from one screen · a fence test proves the handoff path cannot mutate Google Ads · a fence test proves `_APPROVAL_CATEGORIES` and the pause guard are byte-unchanged · no code path closes a handoff without an explicit operator action or a completed linked plan.

---

### Story 21.1: ★ `lane_handoffs` (V29) + service + `GET/POST /api/handoffs`

As an operator,
I want every out-of-lane recommendation to exist as a row with its evidence frozen at emit time,
So that a recommendation survives the session that produced it.

**Trace:** H1, H2, H3
**Size:** M · **Depends on:** —

**Acceptance Criteria:**

**Given** `backend/app/database.py` at head V28
**When** the V29 block is added following the house pattern (`if version < 29:` → `executescript` → `INSERT OR IGNORE INTO schema_version (version) VALUES (29)` → `commit()` → `logger.info("V29 migration complete (lane_handoffs).")`)
**Then** `lane_handoffs` exists with exactly these columns: `id` TEXT PK (`hof-<8hex>`) · `account_id` · `source_campaign_id` · `source_campaign_name` · `source_conversation_id` · `source_role` · `title` (≤80 chars) · `recommendation` · `evidence_snapshot` TEXT (JSON, frozen at emit) · `target_lane` · `target_ref` (nullable) · `status` (default `open`) · `dollar_impact_wk` REAL (nullable) · `due_at` (nullable) · `plan_id` (nullable, joins `scheduled_plans.id`) · `dedupe_key` · `restate_count` INTEGER default 0 · `last_referenced_at` · `closed_note` · `created_at` · `acknowledged_at` · `closed_at` · `updated_at`
**And** `target_lane` is constrained to `campaign | product_dev | external_build | other_platform | owner_decision` and `status` to `open | acknowledged | in_progress | done | dismissed`
**And** a UNIQUE index on `(account_id, dedupe_key)` makes a duplicate emit **impossible at the DB layer** (H2 is a constraint, not a convention), plus an index on `(account_id, status)` mirroring `idx_finding_actions_account`

**Given** the new service `backend/app/services/handoffs.py`
**When** it is imported
**Then** it exposes create / get / list / transition / reference helpers and **imports nothing from `google_ads/`** — asserted by an import-graph test (fence: the handoff path has no route to a mutation, H3)
**And** `age_days` is computed **server-side** from `created_at` on every read (never a client clock)
**And** the module carries the `finding_actions` law in its docstring verbatim in spirit: *no Google Ads mutation ever lives here; execution is always the plan path (scheduler.py), which is scope-guarded*

**Given** the new router `backend/app/routers/handoffs.py` (`prefix="/api/handoffs"`), registered in `main.py` beside `plans.router`
**When** exercised
**Then** it serves `GET /` (filters: `account_id`, `status`, `target_lane`, `campaign_id`, `overdue`), `GET /{id}`, `POST /` (create), `PATCH /{id}` (status + `closed_note` + `due_at`), and `POST /{id}/link-plan` (sets `plan_id`)
**And** a `POST` whose `dedupe_key` already exists returns **200 with the existing row and `restate_count` incremented**, not 201 and not a 409 — re-emission is defined as reference (H2)

**Files:** `backend/app/database.py` (V29), `backend/app/services/handoffs.py` (new), `backend/app/routers/handoffs.py` (new), `backend/app/main.py` (include), `backend/tests/test_handoffs.py` (new)

---

### Story 21.2: `emit_handoff` MCP tool + the emission contract

As a persona that has just concluded something outside its lane,
I want one tool that files it once,
So that I stop paying the recommendation forward in prose.

**Trace:** H2, H4
**Size:** M · **Depends on:** 21.1

**Acceptance Criteria:**

**Given** a new MCP tool `emit_handoff` registered in `backend/google_ads/mcp_main.py`
**When** a persona calls it
**Then** its arguments are `title`, `recommendation`, `target_lane`, `target_ref` (optional), `evidence` (object), `dollar_impact_wk` (optional), `due_at` (optional) — and it writes via the app DB path from 21.1, issuing **zero Google Ads API calls**
**And** `dedupe_key` is a **server-computed** stable hash (normalized `title` + `target_lane` + `target_ref`) — the calling model never supplies it, so it cannot mint a near-duplicate by rewording (a test emits the same intent with three different phrasings and asserts one row, `restate_count == 3`)

**Given** `CampaignScopeMiddleware` (unchanged — L482/L503)
**When** `emit_handoff` names another campaign as its target
**Then** the target argument is called **`target_ref`, never `*campaign_id*`**, so it does not collide with the guard's inspected key set — and the tool is added to an explicit, documented pass-through allowlist with a test proving (a) `emit_handoff` still passes while bound to a different campaign, (b) the guard's blocking behaviour on all mutation tools is **byte-identical to today** (the existing 5 guard cases stay green, unmodified)
**And** a fence test asserts `emit_handoff` appears in **no** mutation dispatch path — the allowlist buys a note-write, never an action

**Given** the persona prompt contract (`backend/app/services/agent.py` role prompts)
**When** a recommendation's owner is another campaign's session, this agent's own backlog, an external build, another platform, or a pure Wassim ruling
**Then** the prompt instructs: emit **once**, then reference — with the five lanes defined by the real cases (`campaign` = DG post-mortem · `product_dev` = "the builder has no Demand Gen import path" · `external_build` = LP rebuild, GCLID upload · `other_platform` = shift budget to Meta · `owner_decision` = a go/no-go with no build)
**And** a prompt-snapshot test asserts the emit-once instruction and all five lane definitions are present

**Files:** `backend/google_ads/mcp_main.py`, `backend/app/services/agent.py` (prompt contract), `backend/tests/test_handoff_emission.py` (new), existing `test_campaign_scope_guard` suite (green, unmodified)

---

### Story 21.3: Reference-by-id — open handoffs in context + the fixed review section

As Wassim reading a review,
I want standing items listed as one line each with their age,
So that I never read 610 words re-arguing a batch I already know about.

**Trace:** H5, H6
**Size:** M · **Depends on:** 21.1, 21.2

**Acceptance Criteria:**

**Given** a chat turn on an account with open handoffs
**When** context is assembled
**Then** a compact block is injected — `id · title · target_lane · age_days · status`, ordered by age descending, **capped at 10 rows and a hard token ceiling** — under the instruction: *these are already captured; reference by id and age; do not re-derive their evidence; do not re-argue them*
**And** the injection is cheap and bounded: a test with 100 open handoffs asserts the block never exceeds the cap
**And** any turn that references a handoff bumps `restate_count` and `last_referenced_at` (giving the re-argument tax a **measurable meter** — 21.7 reads it as evidence the epic worked)

**Given** any review/audit-shaped response
**When** it is rendered
**Then** it carries a fixed section — `## Open handoffs` — appended **deterministically from the DB by the renderer, not by the model**, one line per open item in the form `LP rebuild — external build, open 14 days (hof-a1b2c3d4)`
**And** the section is capped (top 5 by age + an "and N more" line) and is **omitted entirely when there are none** (no empty ceremony)
**And** a prompt-snapshot test asserts the model-side instruction *"reference by id; the Open handoffs section is rendered for you — do not restate its contents in prose"*

**Files:** `backend/app/services/agent.py` (context assembly + prompt), `backend/app/services/handoffs.py` (renderer helper), `backend/tests/test_handoff_context.py` (new)

---

### Story 21.4: ★ The Decision Queue — dashboard + per-campaign

As Wassim with 30 seconds,
I want one screen listing everything waiting on me with a button per row,
So that clearing my desk is clicks, not reading.

**Trace:** H7, H8
**Size:** **L** · **Depends on:** 21.1

**Acceptance Criteria:**

**Given** a new endpoint `GET /api/handoffs/queue?account_id=` (optionally `&campaign_id=`)
**When** called
**Then** it returns ONE merged, age-sorted list from **two** sources — open/acknowledged/in-progress `lane_handoffs` **and** existing `scheduled_plans` rows with `status='awaiting_approval'` — each item tagged with its kind so the client renders the right actions, with **no change to `plans.py`'s existing endpoints or semantics**

**Given** the new `frontend/src/components/handoffs/DecisionQueue.tsx` (DESIGN.md tokens, light)
**When** it renders a row
**Then** the row body is a **hard-capped summary (≤200 characters, server-truncated)** with full evidence behind a disclosure — the anti-prose fence, so a queue of 12 items is still one screen
**And** each row exposes one-click actions inline: handoffs → **Acknowledge · Start · Done · Dismiss · Snooze** (sets `due_at`) · **Convert to plan** (opens the existing prefilled `PlanForm`, then `POST /{id}/link-plan`); plan approvals → the **existing** Approve / Skip / Snooze / Run-now handlers, called unchanged
**And** every action is optimistic with rollback on failure, and a component test asserts a row can be cleared in exactly one click for each of the five handoff actions

**Given** placement
**When** the app renders
**Then** the queue appears (a) on the dashboard in `ContentArea` **above** the existing `AgentActivity`/UpcomingPlans timeline — pending decisions outrank scheduled future — and (b) per-campaign as a section in `CampaignTabs` beside the Plans tab, filtered to that campaign's `source_campaign_id` **plus** any handoff whose `target_ref` names it (so the DG post-mortem shows up in the DG campaign's queue, where it can actually be acted on)
**And** the existing Plans tab and UpcomingPlans keep working unchanged (regression assertion)

**Files:** `backend/app/routers/handoffs.py` (queue endpoint), `frontend/src/components/handoffs/DecisionQueue.tsx` (new), `frontend/src/components/handoffs/queueHelpers.ts` (new), `frontend/src/components/layout/ContentArea.tsx` (or `dashboard/HomeV2.tsx` — whichever owns the home composition at build time), `frontend/src/components/campaign/CampaignTabs.tsx`, `frontend/src/lib/api.ts`, `frontend/src/components/handoffs/DecisionQueue.test.tsx` (new)

---

### Story 21.5: Standing orders — the jammed-approval fix

As Wassim,
I want to rule **once** on a class of routine action and have the agent just do it and tell me after,
So that a $53/week negative-keyword batch never straddles three sessions again.

**Trace:** H9, H10
**Size:** **L** · **Depends on:** 21.1, 21.4

**Acceptance Criteria:**

**Given** the V29 migration also creates `standing_orders` — `id · account_id · order_type · bar_json · enabled · granted_by · granted_at · revoked_at · created_at`
**When** a standing order is granted for `search_term_negatives` with the account's **already-documented bar** (`>$10/day zero-conversion` for a new negative; the transcript's own threshold language is the seed value, stored as data)
**Then** the bar lives as data — changing the threshold requires **zero code change** (test flips `bar_json` in a fixture and asserts the qualifying set changes)
**And** grants are per-`(account_id, order_type)`, revocable, and every grant/revoke is audit-stamped

**Given** a persona identifies an item that provably clears a live standing order's bar
**When** it acts
**Then** it **executes via the existing auto lane** — `action_category='search_terms'`, which `_APPROVAL_CATEGORIES` already excludes (`scheduler.py:44`) — and **reports post-hoc** into the Decision Queue as an informational, already-done row (`status='done'`, evidence attached), instead of asking
**And** an item that does **not** clear the bar is **emitted as a handoff with `target_lane='owner_decision'`** — filed once, listed with its age — never re-pitched in prose

**Given** the gates
**When** this story merges
**Then** a fence test asserts `_APPROVAL_CATEGORIES == {"budget","bids","status","geo"}` **unchanged**, and that no `order_type` may be created for any of those four categories — budget/bid/status/structure changes stay approval-gated **exactly as today**
**And** a second fence test asserts standing orders **cannot** reach the pause path: the pause guard's UI-grant requirement is untouched and a standing order can never substitute for it ([[project_pause_guard]] — "working campaigns cannot be paused by chat text")
**And** every standing-order execution writes to `change_log` (V25) like any other write, so the existing changelog + 1-click revert covers it — auto-execution is never unattributed or irreversible

**Files:** `backend/app/database.py` (V29 second table), `backend/app/services/standing_orders.py` (new), `backend/app/routers/handoffs.py` (grant/revoke endpoints), `backend/app/services/agent.py` (prompt contract: *act under a live standing order, report after; otherwise emit a handoff — never re-pitch*), `backend/tests/test_standing_orders.py` (new), `backend/tests/test_scheduler.py` (fence assertions)

---

### Story 21.6: Aging, escalation, and the no-silent-drop guarantee

As an operator,
I want old handoffs to get louder rather than quieter,
So that "standing since Jul 21" is a visible state, not a phrase buried in a chat log.

**Trace:** H11, H12
**Size:** M · **Depends on:** 21.1

**Acceptance Criteria:**

**Given** server-computed `age_days` and optional `due_at`
**When** a handoff is read
**Then** it carries a derived `escalation` of `fresh` (<7 d) · `aging` (7–13 d) · `overdue` (`due_at` passed **or** ≥14 d without a due date) · `escalated` (≥30 d), with boundary tests at 6/7/13/14/29/30 days and a frozen clock

**Given** the escalation level
**When** surfaces render
**Then** (a) the dashboard shows a count badge whose token intensity steps with the **highest** live level (DESIGN.md warning-soft → warning, matching the Plans tab's existing needs-attention badge convention), (b) the `## Open handoffs` section from 21.3 gains a **header line** when anything is overdue — e.g. `2 overdue: LP rebuild 14d · GCLID upload 22d` — and (c) overdue rows sort to the top of the Decision Queue regardless of kind

**Given** the no-silent-drop guarantee
**When** any code path attempts to close a handoff
**Then** `status` may reach `done` **only** from an explicit operator action or a completed linked `plan_id`, and `dismissed` **only** with a non-empty `closed_note` — enforced in the service layer and asserted by a test that greps the codebase for writes to `lane_handoffs.status` and proves each call site is one of the sanctioned transitions
**And** there is **no TTL, no auto-archive, and no auto-close job** anywhere in the epic — an explicit non-feature, asserted by test and stated in the service docstring

**Files:** `backend/app/services/handoffs.py`, `backend/app/routers/handoffs.py`, `frontend/src/components/handoffs/DecisionQueue.tsx`, `frontend/src/components/handoffs/queueHelpers.ts`, `backend/tests/test_handoff_aging.py` (new)

---

### Story 21.7: Live verification against the real backlog + close-out

As the build,
I want the four items this epic exists for to be provably clearable,
So that "tracked handoff" is demonstrated on real data, not asserted.

**Trace:** H12 + whole-epic acceptance
**Size:** S · **Depends on:** 21.1–21.6

**Acceptance Criteria:**

**Given** a seed/backfill script (idempotent, re-runnable)
**When** run against the MapleRoots account
**Then** the four standing items are filed with their **real** created dates so ages are honest on day one: LP rebuild (`external_build`, traced to the May CRO audit P2, `dollar_impact_wk` ≈ 170) · GCLID offline upload (`external_build`, created 2026-07-21 → **shows 22+ days**) · DG post-mortem (`campaign`, `target_ref` = the DG campaign, `due_at` 2026-08-12 → **shows overdue**) · the 8-negative batch (`owner_decision`, or auto-cleared if a `search_term_negatives` standing order is granted first)
**And** each renders in the Decision Queue with the correct escalation level, and each is clearable in one click

**Given** the epic exit gate
**When** close-out runs
**Then** backend suite GREEN and ≥ 671 · `tsc -b && vite build` clean · launchctl restart → `/api/health` 200 and `/api/handoffs/queue` serves the seeded rows · the three fence tests (no-mutation import graph · `_APPROVAL_CATEGORIES` unchanged · sanctioned-transitions-only) all green · existing scope-guard and plans suites green and **unmodified**
**And** one `_bmad-output/feature-log.md` row per shipped story, per Tier-1 drift discipline
**And** the close-out records the baseline `restate_count` reading as the epic's success metric — the re-argument tax is now a number, and a follow-up session can prove it fell

**Files:** `backend/scripts/seed_lane_handoffs.py` (new), `_bmad-output/feature-log.md`, `backend/tests/test_handoff_fences.py` (new)

---

## Explicit non-goals

- **No change to the campaign scope guard.** A handoff is a note, not an action; it needs no scope exemption to work.
- **No new approval gate.** Budget / bids / status / geo stay exactly as gated as they are today; this epic only removes ceremony from the categories the system **already** treats as auto.
- **No auto-close, TTL, or archive job.** Aging makes items louder, never quieter (H12).
- **No cross-agent dispatch.** Routing a handoff to a sibling agent over the bridge (`:8765`) is a natural sequel, deliberately out of scope — v1 files and surfaces; Wassim routes.
- **No handoff executor.** If it can be executed, it becomes a `scheduled_plans` row via `plan_id`. There is exactly one execution path in this system and it stays scope-guarded.

## Open questions for Wassim

1. **Standing-order scope at launch.** Grant `search_term_negatives` for MapleRoots only, or account-wide across all live campaigns from day one?
2. **The 14-day default.** Is "overdue at 14 days with no explicit due date" the right default, or should handoffs require a `due_at` at emit time (forcing a commitment, at the cost of friction)?
3. **Keyword pauses as a second standing order.** The transcript documents a `>$20 spent, 0 conversions` bar for pausing keywords — but `status` is an approval-gated category and this epic does not touch that. Should keyword-level (not campaign-level) pauses become a narrowly-scoped standing order in a follow-up, or stay per-item approvals?
