# Dashboard v2.1 — Always-Fresh Data + Clarity + Effortless Home Access

> Drafted 2026-07-12 (planning agent, evidence-verified against the live DB
> `data/app.db` and the code as of commit `6291975`). Status: PLAN — BMAD-
> compatible (epics → stories with AC + effort). Feeds `/bmad-edit-prd`.
>
> Operator's words: *"The dashboard is clean but has ALWAYS STALE DATA, and
> not clear, and make the access of the home page easier."* The Epic-13
> layout ("command center") stays — this plan changes the DATA PIPELINE
> under it, sharpens what every number says, and removes friction getting
> home. Design system: Shopify-calm light OKLCH tokens (`frontend/DESIGN.md`)
> — untouched, never dark.

---

## PART 0 — ROOT-CAUSE FINDINGS (all verified, file:line)

### RC-1 · The background metrics sync has been silently broken for months (schema mismatch)

The table (`backend/app/database.py:163-179`) has columns **`date`**,
**`campaign_status`**, no `id`, PK `(account_id, campaign_id, date)`.

The background sync engine writes different columns:

- `backend/app/services/sync_engine.py:121-146` — `_sync_campaign_daily`
  INSERTs `(id, …, metric_date, …, status)` with
  `ON CONFLICT(account_id, campaign_id, metric_date)` → **`sqlite3.OperationalError:
  no such column` on EVERY row** → swallowed by the bare
  `except Exception: continue` at `sync_engine.py:161-163`. **Zero rows have
  ever been written by the scheduled sync.**
- `sync_engine.py:69-74` — the post-write count query
  `SELECT COUNT(DISTINCT metric_date)…` also raises → `sync_account()`
  crashes **before** `_update_sync_status` (`sync_engine.py:78`) → the
  `sync_status` row is never updated on the "success" path.

**Live-DB proof (queried 2026-07-12):**

| Evidence | Value |
|---|---|
| `sync_status.last_sync_at` | **2026-04-16** (frozen ~3 months; status=`error`, a 429) |
| `campaign_daily_metrics` MAX(`date`) | **2026-07-08** → 4 days stale *today* |
| MAX(`synced_at`) | 2026-07-12 02:54 (see RC-5 — the stamp lies) |
| Campaigns launched via SDK scripts 2026-07-06 (Panama Oman+Jordan `24002195025`, Greece `24002377362`) | **zero** metric rows — per-day row count stayed 3-4, never grew |

The dashboard is stale because **nothing scheduled has successfully written a
metrics row since the V2 schema landed.** Every fresh number Wassim ever saw
came from a manual `POST /api/accounts/{id}/sync` or a chart-open side-effect.

### RC-2 · The broken sync still burns catastrophic quota → 429s that poison everything else

`sync_engine.py:108-113`: per campaign, per day, it calls
`get_campaigns(account_id, day, day)` — a **full-account GAQL query**. With
~110 campaigns × 30-day lookback (`config.py:99 SYNC_LOOKBACK_DAYS=30`) that
is **~3,300 API calls per sync run**, 4×/day (`SYNC_INTERVAL_HOURS=6`) ≈
13,200/day — exactly the Basic-access operations ceiling. The frozen
`sync_status` error is literally *"Number of operations for basic access …
Too many requests. Retry in 10318 seconds."* All of it wasted (RC-1: every
write fails). The 429s then break *unrelated* reads (roster sync, charts,
agent context) through the shared client.

Same broken call is the Team Audit's "Phase 0 pre-fetch"
(`workflow_orchestrator.py:718-728`): it always throws, logs
`workflow pre-fetch failed (continuing on local data)` and the audit **runs
on stale local data while the UI says "one batched sync" happened.**

### RC-3 · No watchdog; failure is invisible by construction

- `sync_engine.py:331-341` `start_background_sync()` — fire-and-forget
  `asyncio.create_task`; the task's exception is never observed; restart
  check is `if _sync_task is not None` — **doesn't check `.done()`**
  (compare the correct pattern in `scheduler.py:445-448`).
- Failures go to `logger.error` only. **No UI surface reads metrics sync
  health.** The only freshness chip in the whole app is the sidebar's
  campaigns-roster chip (`Sidebar.tsx:392-404`) — it covers the roster, not
  metrics.

### RC-4 · The only *working* metrics writers are user-triggered side effects

- `routers/campaigns.py:272-302` — manual `POST /api/accounts/{id}/sync`:
  the CORRECT writer (per-campaign `get_daily_metrics` GAQL →
  `metrics_store.sync_daily_metrics`, right columns). ~1 call/campaign.
  **Nothing schedules it.** This is what un-stuck the 9-day staleness.
- `routers/campaigns.py:223-244` — chart endpoint side-writes daily rows for
  the ONE campaign being viewed (and passes no `campaign_name` → blank).

### RC-5 · Staleness laundering — `synced_at` lies to everyone

- `services/cache.py:54-61` — on live-fetch failure the cache silently
  serves stale data of ANY age; `cache.py:47-51` — while the circuit breaker
  is open it serves arbitrarily old cache or `[]` (indistinguishable from
  "no campaigns"). **No marker reaches the caller.**
- `campaigns.py:238-242` then re-writes that possibly-stale chart payload
  into `campaign_daily_metrics`; `metrics_store.py:83-99` INSERT OR REPLACE
  restamps `synced_at = datetime('now')`. Live proof: **all 427 rows carry
  `synced_at = 2026-07-12 02:54:07` while MAX(date) = 2026-07-08.** Any
  future "is it fresh?" check keyed on `synced_at` will be lied to.
- Bonus corruption: that same INSERT OR REPLACE writes only 11 of 14 columns
  → it **NULLs out `campaign_status` / `bidding_strategy` / `budget_micros`**
  on rows that had them. The agent's Layer-5 context reads
  `bidding_strategy` from exactly those rows
  (`metrics_store.py:137-150 get_account_summary`) → the agent can state a
  wrong/empty bidding strategy. (The frontend mapping itself is correct —
  `formatters.ts:15-28` maps `TARGET_SPEND → "Maximize Clicks"` — the wrong
  *stored/stale value* is what gets displayed. See RC-8.)

### RC-6 · Homepage endpoints are local-only with no freshness trigger and no age metadata

- `routers/workflows.py:163-180` (`/account-report` + fast signals),
  `:230-247` (`/metrics/overview`) — "local SQLite only, zero Google Ads
  calls". Correct for speed, but **nothing anywhere refreshes the underlying
  table** (RC-1..4), and `metrics_store.get_overview` (`metrics_store.py:
  484-555`) returns **no data-age field** — the UI couldn't show staleness
  even if it wanted to.
- `fast_signals.py:5-7` claims "never stale" while reading the 4-day-stale
  table → pacing/waste $ figures are silently wrong-but-confident.
- `KpiCards.tsx` (`if (!anyValue) return null`) — when data is missing the
  KPI row **vanishes** instead of saying "no data since Jul 8". Zero-state
  discipline (brief §7) is being applied to a *broken pipeline* state it was
  never meant for → invisible staleness = the "not clear" feeling.

### RC-7 · Out-of-app campaigns: roster fast, metrics never

Roster: `campaigns_repo.list_campaigns` syncs on read when >5 min stale
(`campaigns_repo.py:33,52-57`) → new SDK-created campaigns appear in the
sidebar quickly. Metrics: no writer covers them (RC-4 writers are
per-viewed-campaign or manual) → they contribute **nothing** to KPI cards,
ranked table, or fast signals until someone opens their chart or runs the
manual sync. Verified: the two 2026-07-06 launches have zero rows.

### RC-8 · "Reverted settings" = display-cache shown as account-truth, with silent fallback

The campaign header (`CampaignOverview.tsx:215`, `CampaignTabs.tsx:47`)
reads the `campaigns` table via `fetchCampaigns`. Normally ≤5 min stale —
BUT when the roster sync fails (e.g. RC-2's 429 storms),
`campaigns_repo.py:54-58` logs a warning and **serves the old rows anyway**;
the campaign page has **no staleness indicator at all** (only the sidebar
chip). So: Greece Plan B showing ENABLED after being PAUSED, or a stale
bidding-strategy value, is exactly what this code does under quota pressure
— the app never *wrote* anything; it *displayed* an old snapshot as truth.
`api.ts:49` (`biddingStrategy: c.bidding_strategy || c.campaign_type`) adds
a second lie-vector: an empty strategy silently displays as the campaign
type. There is no live-verify read anywhere on the view path, and no
change-attribution surface to answer "who changed this?"

---

## PART 1 — FRESHNESS ARCHITECTURE

### 1.1 Principles (the contract)

1. **Prevented** — a resilient scheduler that cannot die silently.
2. **Self-healing** — reads trigger repair; opening the app/campaign is
   itself a freshness event.
3. **Honest** — every number carries its age; the pipeline may be stale but
   is never allowed to be *silently* stale. `synced_at` must mean "verified
   against Google at this time" — never restamped from cache.
4. **Push where cheap** — reuse the in-process pub/sub pattern already
   proven in `workflow_runner.py` (subscribe/replay hub) for a tiny per-
   account SSE channel; no new infra.

### 1.2 Rewrite the writer (kill sync_engine's broken path)

**One GAQL call per account** replaces ~3,300:

```sql
SELECT campaign.id, campaign.name, campaign.status,
       campaign.bidding_strategy_type, campaign_budget.amount_micros,
       segments.date, metrics.impressions, metrics.clicks,
       metrics.cost_micros, metrics.conversions
FROM campaign
WHERE segments.date BETWEEN :from AND :to
  AND campaign.status != 'REMOVED'
ORDER BY segments.date
```

Returns campaign×day rows for ALL campaigns in one `search_stream`. Upsert
into `campaign_daily_metrics` with the **actual** column names
(`date`, `campaign_status`) — delete `_sync_campaign_daily` and the
`metric_date` ghosts entirely. Insert **zero-rows for ENABLED campaigns on
days Google returns nothing** (so "no data" is distinguishable from "never
checked" — keep the existing intent, correctly implemented). New campaigns
are covered automatically (the query is account-wide) → RC-7 solved: an
SDK-launched campaign appears in metrics on the next cycle (≤60 min) or the
next app-open self-heal, whichever first.

Also in the same sync transaction: refresh the `campaigns` roster
(`campaigns_repo.sync_campaigns`) so roster and metrics can't skew, and keep
transactions short — the current `sync_account` holds one aiosqlite
connection across the entire run (`sync_engine.py:31,91`), a WAL-contention
hazard once syncs really run.

### 1.3 `sync_state` — one honest ledger (new table, V21)

```sql
CREATE TABLE sync_state (
  account_id TEXT NOT NULL,
  domain TEXT NOT NULL,            -- 'metrics' | 'roster' | 'asset_groups'
  last_attempt_at TEXT, last_success_at TEXT,
  last_error TEXT, consecutive_failures INTEGER DEFAULT 0,
  in_progress INTEGER DEFAULT 0,   -- single-flight lock
  data_through_date TEXT,          -- MAX(date) actually written (metrics)
  PRIMARY KEY (account_id, domain)
);
```

Replaces the dead `sync_status` table as the source of truth for the UI
health chip and the self-heal decision. `data_through_date` is the anti-
laundering field: freshness is judged by **what dates exist**, never by
`synced_at` stamps (RC-5 lesson).

### 1.4 Scheduler with watchdog + heartbeat

- **Fix the restart bug**: `start_background_sync` checks
  `_task is None or _task.done()` (copy `scheduler.py:445-448`).
- **Watchdog**: a 60s supervisor task (or fold into the existing
  scheduler tick at `scheduler.py:435-442`) checks (a) the sync task is
  alive, restarting it if `.done()`; (b) heartbeat age — the loop updates a
  `config`-table heartbeat each cycle; heartbeat older than 2× interval →
  restart + log + surface in `/api/health`.
- **Timeout fence**: each account sync wrapped in
  `asyncio.wait_for(…, 120s)` so one hung API call can never freeze the loop
  forever (the current `while True: … await sleep()` has no timeout
  anywhere — a hung `search_stream` = permanent stall).
- **Backoff**: on failure, exponential per-account backoff via
  `consecutive_failures` (1 min → 2 → 4 → cap 60), independent per account.
- **`/api/health` upgrade** (`main.py:109-111`): returns per-account
  `sync_state` summary + heartbeat age. The launchd service finally has a
  probe that means something.

### 1.5 Self-healing (sync-on-read)

- `GET /accounts/{id}/metrics/overview` (and `/account-report`,
  `/campaigns`): after answering from SQLite (always fast), check
  `data_through_date < yesterday` OR `last_success_at > N min` → **kick a
  background refresh task** (single-flight via `in_progress` + a min-
  interval guard of 10 min so tab-stampedes can't loop it). Response is
  never blocked on Google.
- Campaign page open → same, scoped hot-window (last 3 days) for that
  campaign's account.
- Backend boot → immediate sync for all `accounts_v2` accounts (today the
  loop also picks accounts from `conversations` — switch the roster source
  to `accounts_v2`, `sync_engine.py:286-299`).
- Manual `Sync now` button stays (wired to the corrected engine) — the
  escape hatch that saved Wassim before becomes a first-class, visible
  control next to every freshness chip.

### 1.6 Honest age everywhere (API contract)

Every dashboard read endpoint adds one envelope field:

```json
"freshness": {
  "data_through_date": "2026-07-11",
  "last_success_at": "2026-07-12 09:14:03",
  "age_minutes": 42,
  "state": "fresh" | "syncing" | "stale" | "error",
  "detail": "Sync failed 3× — quota"   // only when error
}
```

Thresholds: `fresh` = data through yesterday (Google's own reporting lags
~3h; *today* is always partial) AND last success <90 min; `syncing` =
`in_progress`; `stale`/`error` otherwise. The UI chip renders:
`live · synced 42m ago` / `syncing…` / amber `data through Jul 8 — Sync now`.

### 1.7 Push updates (cheap SSE)

`GET /api/accounts/{id}/events` — an SSE endpoint on the exact
`workflow_runner.py` hub pattern (in-process replay buffer + subscribe).
Events: `sync_completed {domain, data_through_date}`, `mutation_applied
{campaign_id, kind}` (emitted by the plan executor / operations router),
`audit_completed`. Frontend: one `EventSource` per account in a tiny hook →
`queryClient.invalidateQueries` for `['metrics-overview']`,
`['campaigns']`, `['fix-actions']`, `['account-report-meta']`. Result: the
operator watches the "syncing…" chip flip to "live · just now" without a
reload, and post-approval mutations refresh the ranked table instantly.
(Existing `refetchInterval` polls in `FixListStrip.tsx:93` /
`AgentActivity.tsx:121` can then be relaxed or kept as belt-and-braces.)

### 1.8 Cadence + quota budget (Basic access, 15k ops/day)

| Job | Cadence | Cost/day |
|---|---|---|
| Hot metrics sync (last 3 days, all campaigns, 1 GAQL) | hourly | 24 |
| Full 30-day re-pull (conversion-lag restatement — Google restates conversions for days/weeks) | nightly | 1 |
| Roster sync (stale-on-read ≤5 min, unchanged) + hourly floor | ~30-50 |
| Self-heal kicks (min-interval 10 min guard) | ~10-20 |
| Live-truth header reads (60s micro-cache, §2) | ~50-200 |
| **Total** | | **≈ 120-300 ops/day ≈ 2% of quota** (vs ~13,200 today) |

Config: `METRICS_HOT_SYNC_MINUTES=60`, `METRICS_HOT_WINDOW_DAYS=3`,
`METRICS_FULL_SYNC_LOOKBACK=30` (nightly). Central `GoogleAdsService`
semaphore (max 4 concurrent) + retry-with-backoff on `RESOURCE_EXHAUSTED`.
For productization, apply for Standard access — but Basic is now ample.

### 1.9 Kill the laundering (cache honesty)

- `CacheService.get_or_fetch` returns `(data, meta)` (or a `CacheResult`
  with `.stale: bool`, `.fetched_at`) — stale-serve and circuit-open-serve
  are **marked**; `[]`-on-open-circuit becomes an explicit error the caller
  can render ("couldn't reach Google — showing nothing rather than a lie").
- Chart endpoint (`campaigns.py:238-242`) only writes to the metrics store
  when the payload came from a **live** fetch — never re-stamps cached data.
- `metrics_store.sync_daily_metrics` stops NULLing metadata: drop
  `campaign_status`/`bidding_strategy`/`budget_micros` from that INSERT's
  REPLACE semantics (upsert only the metric columns) — those fields belong
  to the roster table anyway (V11's single-source-of-truth rule, honored).

---

## PART 2 — LIVE-TRUTH RULE (control plane vs analytics plane)

**Control plane — must reflect the account NOW (live read, 60s micro-cache):**

| Surface | Fields | Mechanism |
|---|---|---|
| Campaign header (`CampaignTabs`/`CampaignOverview`) | status · bidding strategy · daily budget · targeting | New `GET /accounts/{id}/campaigns/{cid}/live-head` — one tiny GAQL, 60s TTL, response carries `verified_at`. Header shows `✓ live` chip. On failure: keep DB values but flip the chip amber: `couldn't verify · showing data from {last_synced_at}` — **never silent** (fixes RC-8's failure mode). |
| Approval execution (plans `approve`) | same | Pre-flight live read before any write (the "diff" quoted to the user is against live values, not cache). Already analysis-first (`scheduler.py:275-287`) — add the live pre-read. |
| Agent Layer-5 context header | same | `metrics_store.format_for_agent` prepends an as-of line and takes status/bidding from the roster (fresh ≤5 min) + notes the data-through date — the agent stops confidently citing stale state. |

**Analytics plane — local store + age chip (never live on render):**
KPI cards, sparklines, ranked table sums, fast signals, charts, audits. The
freshness envelope (§1.6) is their honesty layer.

**Reconciling the "reverted settings" confusion permanently:**

1. Every roster sync diffs old→new `status`/`bidding_strategy`/
   `budget_micros`; changes not attributable to an app-side plan/operation
   get an `external_change` row (V21 table: campaign_id, field, before,
   after, detected_at, source='external').
2. Story-level (P2): query the Google Ads **`change_event`** resource
   (last 30 days, who/what/when) to attribute — "Paused 2026-07-07 14:02 by
   user X via Google Ads UI". Surfaced in AgentActivity ("Changed outside
   the app") and on the campaign header timeline.
   → The Greece Plan B ENABLED→PAUSED mystery becomes a visible, attributed
   event instead of a haunting.
3. The app's own sync paths remain **read-only toward Google** (verified:
   no sync path writes to the API; all mutations go through gated
   plans/operations). State that in the trust line's tooltip.

---

## PART 3 — CLARITY PASS (sharpen, don't redesign)

Shared primitive first: **`<FreshnessChip>`** (one component, DESIGN.md
tokens: `text-subtle` fresh / `text-warning` stale / pulse dot syncing) +
**`<InfoHover>`** (11px label + hover card explaining the number). Account
context bar: the HomeV2 header (`HomeV2.tsx:58-63`) gains `CID · currency ·
timezone` as quiet metadata under the account name (currency read once from
the account; every $ on the page is implicitly labeled by it).

### 3.1 KpiCards (`KpiCards.tsx`)

- Row header gains the FreshnessChip (from `/metrics/overview.freshness`).
- **Kill the vanishing act**: distinguish three states —
  (a) *empty account* → render nothing (brief §7 stands);
  (b) *pipeline stale/broken* → render the cards with values + amber chip
  `data through Jul 8 · [Sync now]`;
  (c) *no data in this window but pipeline healthy* → quiet inline line
  "No activity in this window." **This is a brief §7 amendment — needs
  Wassim sign-off** (zero-state ban was written for fake zeros, not for
  hiding pipeline failure).
- Per-card `InfoHover`: definition + exact window dates + prior-window dates
  ("Spend, Jul 5–Jul 11 vs Jun 28–Jul 4 · ENABLED campaigns only") + the
  conversion-lag note ("Google restates conversions for several days").
- `vs prior 7d` label stays; add the same window phrase to the delta
  tooltip. Currency symbol already explicit.

### 3.2 CampaignsRanked (`CampaignsRanked.tsx`)

- Section header gains window label ("last 7d") + FreshnessChip (shares the
  overview's envelope).
- Per-row honesty: a campaign with **no metric rows in the window** shows a
  quiet `no data yet` chip instead of $0 (today an SDK-launched campaign
  looks like a zero-spend dud — RC-7's UI face). Campaign first seen <72h →
  `new` chip (from `campaigns.created_at`).
- `— ` CPA already honest; add InfoHover on the flag chips exposing the
  formula ("High CPA = >2× account blended $X").
- Bidding-strategy fallback lie: remove `|| c.campaign_type` at `api.ts:49`
  — display `—` when unknown, never the channel type dressed as a strategy.

### 3.3 FixListStrip (`FixListStrip.tsx`)

- The `audited 2h ago` chip stays, but staleness gets **two dimensions**:
  audit age AND the data it ran on — when the audit's underlying
  `data_through_date` lags, render `audited 2h ago · on data through Jul 8`
  (amber). An audit fresh-in-time but computed on stale data is the most
  dangerous lie on the page today (RC-2's broken Phase-0 makes it routine;
  after §1.2 the pre-fetch actually works and the label proves it).
- Fast-signal rows get their window chip (`last 7d`) + InfoHover formula
  ("wasted spend = $ with 0 conversions over 7d") — and stop claiming
  "always fresh" anywhere; they inherit the same freshness envelope.
- `[Run again]` disabled-with-reason while a sync/audit is in flight
  (`syncing…` from SSE) instead of double-firing.

### 3.4 AgentActivity (`AgentActivity.tsx`)

- New row type: **external changes** (§2.3) — "Greece Plan B paused outside
  the app · Jul 7, 14:02" with the `change_event` attribution when
  available. This is the missing "why does the account look different"
  answer.
- Timestamps: relative + absolute-local on hover (today raw strings).
- Upcoming plans show `in 2d · Mon 09:00` (relative + absolute).

### 3.5 Campaign page header (`CampaignTabs.tsx` / `CampaignOverview.tsx`)

- Live-truth chip (§2). Status/bidding/budget always labeled `✓ live 12s`
  or amber `unverified · from {time}`.
- This is where the "clean but not clear" complaint dies: the operator can
  finally tell *which* numbers are account-truth and which are cached
  aggregates, at a glance, on every surface.

---

## PART 4 — HOME ACCESS (effortless)

**Today's friction (verified):**
- `selectedCampaignId` persists in localStorage (`appStore.ts:49,56-62`) →
  the app **reopens into the last campaign**, not home.
- Home is derived state, not a route (`App.tsx:96-104` `isHome = !campaign
  && !studio && !settings…`) — no URL, no browser-back, no deep-link.
- The only affordance is a small `Home` button in the Header
  (`Header.tsx:88-91`). No keyboard shortcut.

**Changes:**

1. **Home is the default and a real route.** `/` = home, always: on app
   open, do NOT auto-restore `selectedCampaignId` into the view (keep it as
   "last campaign" memory for a `Continue where you left off →` affordance
   on home instead). Campaign becomes a route too — `/campaign/:id` — same
   URL-sync pattern the app already proved with `/c/:id` and `/studio`
   (`App.tsx:160-177`). Browser back from a campaign now lands home.
   Refresh keeps you where you are. Deep-links to campaigns become
   shareable; the fix-list "Review in chat" and ranked-row clicks push real
   URLs.
2. **Keyboard**: `g h` → home, `g c` → last campaign, `g p` → Plans
   (Gmail-style two-key chords; single-key is unsafe while typing in chat).
   `Esc` on a campaign page (when no modal/drawer is open) → home. ⌘K stays
   chat-on-home (`HomeChatDock.tsx:33-40`) / palette elsewhere; add "Go
   home" as a palette command.
3. **Sidebar rail**: the icon rail's top item is Home (active-state aware);
   the flyout tree keeps campaign switching one hover away
   (`Sidebar.tsx:427-478` already built — just add the Home affordance and
   active states).
4. **Load-time budget**: skeleton (not spinner) per section, in-layout so
   nothing jumps: strip 88px, KPI row 96px, table 6×40px rows. All four
   home endpoints are local-SQLite (<50ms each) — the budget is
   **skeleton→content <300ms**; prefetch all four queries in parallel on
   app mount (before the route renders) via `queryClient.prefetchQuery`,
   so warm navigations render instantly. The self-heal sync (§1.5) never
   blocks render — data appears, then the chip flips when fresher data
   pushes via SSE.
5. **Small windows**: single column already; below `md` the KPI grid is 2×2
   (already), table gains horizontal scroll with sticky name column, chat
   drawer goes full-width, icon rail stays (it's 48px).

---

## PART 5 — PHASED DELIVERY

### Epic A — "The data is real again" (P0 — kills the staleness pain)

| Story | What | AC | Effort |
|---|---|---|---|
| A1 | Rewrite metrics sync: single-GAQL account×day upsert with CORRECT columns; delete `_sync_campaign_daily` + `metric_date` ghosts; roster refresh in same pass; short transactions | Fresh install + existing DB both sync 30d in one call; `campaign_daily_metrics` MAX(date) = yesterday after one run; SDK-created campaign appears in metrics next cycle; per-run API ops ≤3 | 1 d |
| A2 | `sync_state` table (V21) + watchdog/heartbeat + `.done()` restart fix + timeout fence + backoff + boot-sync from `accounts_v2` + `/api/health` upgrade | Kill the task mid-run → auto-restarted <2 min; hung API call → loop alive next cycle; health endpoint shows per-account state | 1 d |
| A3 | Freshness envelope on `/metrics/overview`, `/account-report`, `/campaigns` + `<FreshnessChip>` on KpiCards, CampaignsRanked, FixListStrip + visible `Sync now` | Every home section shows age; stale >24h renders amber; chip text matches `data_through_date`, not `synced_at` | 1 d |
| A4 | Self-heal: sync-on-app-open + on-campaign-open when stale (single-flight, 10-min guard); fix Team Audit Phase-0 to use the new engine | Open app after 3 idle days → chip shows syncing → fresh within ~30s; no duplicate concurrent syncs under tab spam; audit pre-fetch actually writes rows | 0.5 d |
| A5 | Cache honesty: marked stale-serve, no laundering writes from chart endpoint, stop NULLing roster fields in `sync_daily_metrics` | `synced_at` only ever set by live-verified writes; circuit-open serves flagged data, never silent `[]` | 0.5 d |

**P0 total: ~4 days.** After A1+A2 alone, the "always stale" experience is
dead; A3 makes it provable on screen.

### Epic B — "Every number explains itself" (P1)

| Story | What | Effort |
|---|---|---|
| B1 | KpiCards states (stale ≠ empty ≠ quiet window) + InfoHovers + brief §7 amendment sign-off | 0.5 d |
| B2 | CampaignsRanked: window label, `no data yet` + `new` chips, flag formula hovers, kill `\|\| campaign_type` fallback | 0.5 d |
| B3 | FixListStrip: dual staleness (audit age + data-through), signal window chips, Run-again in-flight state | 0.5 d |
| B4 | Live-truth campaign header (`/live-head`, 60s TTL, ✓ live / amber unverified) + approval pre-flight live read + agent Layer-5 as-of header | 1 d |
| B5 | Account context bar (CID · currency · tz) + AgentActivity timestamp polish | 0.5 d |

**P1 total: ~3 days.**

### Epic C — "Push + effortless home" (P2)

| Story | What | Effort |
|---|---|---|
| C1 | SSE `/accounts/{id}/events` (workflow_runner hub pattern) + frontend invalidation hook; emit from sync engine + plan executor | 1 d |
| C2 | Routes: `/` = home always (no auto-restore), `/campaign/:id`, "Continue where you left off" card, browser-back semantics | 1 d |
| C3 | Keyboard chords (`g h` / `g c` / `Esc`), palette "Go home", rail Home item + active states | 0.5 d |
| C4 | Skeletons + parallel prefetch + <300ms budget check; small-window table scroll | 0.5 d |
| C5 | External-change detection (roster diff → `external_change` rows) + `change_event` attribution in AgentActivity + campaign header | 1 d |

**P2 total: ~4 days. Grand total: ~11 dev-days across 3 epics / 15 stories.**

Sequencing: A is strictly first (everything else decorates its truth).
B4 and C5 are the two stories that close the "reverted settings" mystery.
C2 needs a 5-minute Wassim decision on the localStorage-restore change
(behavior change: app opens home, not last campaign).

---

## PART 6 — RISKS

1. **Conversion-lag restatement reads as "the dashboard changed my
   numbers".** Google restates conversions for days (esp. Search). The
   nightly 30-day re-pull will legitimately rewrite history. Mitigation:
   the KPI InfoHover states it plainly; never label restated windows as
   errors. (Without the nightly re-pull the numbers would just be wrong —
   this risk is the cost of being right.)
2. **Sync-on-read stampede / quota regression.** Multiple tabs + SSE
   invalidations could loop syncs. Mitigation: `in_progress` single-flight
   + 10-min min-interval per account + the API-call semaphore; the whole
   budget is ~2% of quota, and a runaway is visible in `sync_state`
   (`consecutive_failures`) + `/api/health` instead of a silent 3-month
   coma like RC-1.
3. **SQLite write contention.** Real hourly syncs + chat writes share one
   WAL file; long transactions would surface as `database is locked` in
   chat. Mitigation: batch upserts in one short transaction, keep the A1
   engine connection-per-phase, and A2's timeout fence bounds any lock
   hold. Watch item in A1's AC (sync full 30d in <5s wall time).
4. **Zero-state amendment dilutes the design law.** The brief's §7 ban is
   load-bearing for the "clean" feel Wassim likes. Mitigation: the
   amendment is narrowly scoped — only the *pipeline-stale* and
   *healthy-but-quiet* states may render text; fake zeros stay banned;
   one-line sign-off before B1.
5. **Live-head reads on hot campaign pages.** 60s TTL caps it (~1 call/min
   per viewed campaign); failure falls back to amber-labeled cache, so a
   quota storm degrades honestly instead of breaking pages.
6. **`change_event` scope creep (C5).** Attribution is a bonus, not the
   fix; the roster-diff `external_change` rows work without it. Timebox the
   GAQL exploration to the story's day.

---

## Appendix — evidence index

| Claim | Where |
|---|---|
| Table schema (`date`, `campaign_status`) | `backend/app/database.py:163-179` |
| Broken INSERT (`metric_date`, `id`, `status`) | `backend/app/services/sync_engine.py:121-146` |
| Silent per-day swallow | `sync_engine.py:161-163` |
| Crash before status update | `sync_engine.py:69-78` |
| Quota bomb (per-campaign×per-day full-account query) | `sync_engine.py:108-113` |
| No `.done()` restart check | `sync_engine.py:331-341` (vs correct `scheduler.py:445-448`) |
| Frozen sync_status (2026-04-16, 429) + MAX(date)=2026-07-08 | live `data/app.db` query 2026-07-12 |
| Stale-serve without marker + `[]` on open circuit | `app/services/cache.py:47-61` |
| Laundered `synced_at` restamp | `routers/campaigns.py:238-242` + `metrics_store.py:83-99`; all 427 rows stamped `2026-07-12 02:54:07` |
| Roster-field NULLing | `metrics_store.py:83-99` (11 of 14 columns) |
| Local-only homepage endpoints, no age field | `routers/workflows.py:163-180, 230-247`; `metrics_store.py:484-555` |
| Fast signals "never stale" claim | `app/services/fast_signals.py:5-7` |
| KPI row vanishes on missing data | `frontend/src/components/dashboard/KpiCards.tsx` (`!anyValue → null`) |
| Roster fail-open without UI signal | `app/services/campaigns_repo.py:52-58` |
| Bidding fallback lie | `frontend/src/lib/api.ts:49`; correct map at `formatters.ts:15-28` |
| Team Audit fake pre-fetch | `app/services/workflow_orchestrator.py:718-728` |
| Last-campaign restore (home friction) | `frontend/src/stores/appStore.ts:49,56-62` |
| Home as derived state, not route | `frontend/src/App.tsx:96-104,160-177` |
| Only-Home-button affordance | `frontend/src/components/layout/Header.tsx:88-91` |
| Sidebar roster chip (the one freshness UI that exists) | `frontend/src/components/layout/Sidebar.tsx:392-404` |
| SSE hub pattern to reuse | `app/services/workflow_runner.py` (subscribe/replay), `routers/workflows.py:55-93` |
| SDK-created campaigns missing from metrics | live DB: `24002195025`, `24002377362` have 0 rows; per-day count stayed 3-4 |
