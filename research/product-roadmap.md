# Google Ads Agent — Product Roadmap (living doc)

> Last updated 2026-06-10. Two parallel tracks: **A) Commercialize the MCP/agent**
> and **B) Keep improving the app**. Neither pauses the other. Update this file
> as phases complete — it is meant to stay alive.
>
> **Governance (Wassim, 2026-06-10): every roadmap build goes through BMAD** —
> `/bmad-edit-prd` → `/bmad-create-epics-and-stories` → `/bmad-dev-story`,
> with Tier-1 feature-log capture per session. No ad-hoc roadmap coding.

---

## North star
A hosted, multi-tenant Google Ads *agent* (not just a data-pipe MCP): deep tools
+ a multi-persona strategist + Scheduled Plans + Team Audit + a campaign scope
guard, connectable from any Claude Code / ChatGPT / Cursor via MCP, billed by
credits. The moat is the **agent + safety layer**, not tool count.

## Competitive read (why we can win)
- Markifact (~$29–99/mo, credits, 300+ ops), Hyper MCP ($49/mo), Adspirer — all
  win on **hosting + breadth + human-in-the-loop + billing**, NOT few tools.
- Our edge they charge for and we already have: scope guard (blocks wrong-campaign
  writes), hybrid auto/approval (Scheduled Plans), multi-persona strategist, Team
  Audit. We are a *data pipe + an agent*; most rivals are just the pipe.

---

## Auth model (the facts that shape everything)
Two layers, kept separate:
1. **MCP connect** (Claude → our server): bearer **token** we issue. No OAuth.
2. **Google Ads data** (our server → a customer's account): Google **OAuth**
   (`adwords` sensitive scope) per customer; we store their refresh token.

Google gates:
- **Dev token**: Test (test accts) → **Basic** (real accts, 15k ops/day — enough
  to start) → **Standard** (unlimited, for scale).
- **OAuth verification**: Testing mode = up to **100 test users**, consent expires
  every 7 days + "unverified" warning. Past that → **sensitive-scope verification
  (2–6 wks)**. Start this EARLY; it is the long pole.

---

## TRACK A — Commercialization

### Phase A0 — "Use it from any Claude Code" (days) ← ✅ DONE 2026-06-10
- Plan tools live on the HTTP MCP bridge (`app/mcp_server.py`): `create_plan`,
  `list_plans`, `approve_plan`, `skip_plan`, `run_plan_now` — 10 tools total.
- Schedule + manage plans from ANY Claude Code on this machine works now
  (Epic 9 / Story 9.1, verified registered + service healthy).

### Phase A1 — Host it (days)
- Deploy backend (incl. /mcp bridge + scheduler) to the Mercan server via Dokploy,
  token-secured, HTTPS. Secrets stay in `~/.mercan-secrets`, never in repo.
- Caveat: hosting = the whole agent backend (Google creds + runs Claude CLI +
  scheduler). Cost of Claude runs must be covered by pricing later.
- Pilot: issue 1–3 testers a bearer token; they connect from their Claude Code.

### Phase A2 — Google access readiness (parallel, start NOW — long pole)
- Confirm current dev-token level. If Test → apply for **Basic** (covers small
  real-account testing). If already Standard, skip ahead.
- OAuth consent screen: add up to 100 **test users** (accept 7-day re-consent).
- Begin **sensitive-scope verification** for `adwords` (2–6 wks). Prepare the
  advertiser verification Google now requires on the applying MCC.
- Apply for **Standard** once real usage exists to show.

### Phase A3 — Multi-tenancy (weeks) — the big lift
- Per-customer Google OAuth flow → store each customer's refresh token (encrypted,
  server-only). Today the backend is single-account; needs per-tenant account_id
  isolation end to end (the campaign scope guard already helps).
- Tenant model: account → user(s) → their connected Google Ads + MCC.
- Data isolation: every query/tool/plan scoped by tenant. Audit for leaks.

### Phase A4 — Billing & metering (weeks)
- Credit model (copy Markifact): discovery/utility tools free; data ops/agent runs
  cost credits. Per-tenant API keys + usage limits + a daily cap (reuse the cost
  cap pattern).
- Pricing sketch: Free (test acct only) / Starter ~$29 / Pro ~$99, credits scale.

### Coverage workstream (parallel to A1–A4) — campaign-type completeness
Rivals sell "create Search, Display, Shopping, Demand Gen, PMax drafts." We have
Search deep; coverage gaps make the MCP a tool, not a product. **Required before A5.**
- **PMax finalization** — ✅ code-complete 2026-06-10 (image-asset bridge,
  signals attachment, step-aware errors; Epic 8). Pending: one human-run live
  wizard submit to verify e2e (campaign lands PAUSED), then mark done.
- **Shopping campaigns** — greenfield: Merchant Center link, product feeds,
  listing groups. (Second.)
- Later: Demand Gen / Display parity as demand shows.

### Phase A5 — Packaging / GTM (weeks)
- One-line connect DX + docs, landing page, "what makes us different" (the agent
  + safety, not tool count). Pricing page. Onboarding (connect Google in 1 OAuth).
- Gate: coverage workstream done (Search + PMax + Shopping minimum).

---

## TRACK B — Continuous app improvement (never stops)

**Now / near:**
- Battle-test Scheduled Plans (real auto + approval run on a live campaign).
- Tune Team Audit Director prompt on real output.
- Frontend auto-restart service (needs node Full Disk Access grant).

**Polish / bugs:**
- VideoCreator → fold pink/emerald into design tokens (`/impeccable colorize`).
- Chat restore-on-refresh (never blank the active thread on a blip).
- Resumable-session bug: keep the resume cookie when a turn errors before a clean
  result event (agent.py) — currently cold-starts.

**Bigger features (scoped, queued):**
- Video Tools: YouTube/Video campaign creation + video editing
  (`research/video_tools_plan.md`). PMax + Shopping moved to Track A's
  coverage workstream (commercialization-critical, 2026-06-10).

**Cross-cutting (always):**
- Stability (services), security (per-tenant secrets, isolation), observability
  (logs/metrics), cost control.

---

## Sequencing principle
- **A0 + A2 start immediately, in parallel** (A0 = days of build; A2 = weeks of
  Google review you can't speed up, so kick it off now).
- A3/A4 (multi-tenancy + billing) are the real "become a product" lift — begin
  after A0/A1 prove the value and A2 unblocks real accounts.
- Track B runs continuously; pull one item between Track-A phases so the app keeps
  improving (the "always in improvement phases" rule).
