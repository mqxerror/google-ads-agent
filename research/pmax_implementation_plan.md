# PMax Campaign Creation — Implementation Plan

**Status:** Plan locked. Ready to execute.
**Companion to:** `.claude/worktrees/phase1-foundation/research/video_tools_plan.md` (original scoping; this doc supersedes it for Feature 1).
**Decided in BMad party-mode session, 2026-05-21.**

---

## What's already built (don't redo)

| Layer | Asset | Path |
|---|---|---|
| Backend MCP — primitive | `create_campaign` accepts `advertising_channel_type=PERFORMANCE_MAX` | `backend/google_ads/services/campaign/campaign_service.py:54` |
| Backend MCP — primitive | `create_asset_group` / `update` / `remove` | `backend/google_ads/services/assets/asset_group_service.py` |
| Backend MCP — primitive | `create_asset_group_asset` | `backend/google_ads/services/assets/asset_group_asset_service.py` |
| Backend MCP — primitive | `create_asset_group_signal` (audience signals) | `backend/google_ads/services/assets/asset_group_signal_service.py` |
| Backend MCP — primitive | `create_asset` (text/image/video) | `backend/google_ads/services/assets/asset_service.py` |
| DB | `ad_assets` table — uploaded creative library | `backend/app/database.py` |
| Roles | `growth_hacker` v4 (Performance Max in scaling framework), `creative_director` (Performance Max character limits at lines 156-158) | `data/roles/{account_id}/` |
| Reference impl | Higgsfield CLI subprocess pattern + frontend generator UI | `/Users/mqxerrormac16/Documents/LangarAI/meta-ads-agent/backend/app/services/higgsfield_client.py` + `frontend/src/components/HiggsfieldGenerator.tsx` |

**The gap is the orchestrator + the wizard.** Primitives without a recipe.

---

## Decisions (locked in party-mode discussion)

1. **Asset sourcing = FULL INLINE.** Wizard generates copy via `creative_director` role and images via higgsfield. User reviews + edits before submit.
2. **Agent entry = BOTH wizard + chat.** Visual wizard for click-driven users; chat recipe (`pmax_strategist`) for power users who say "build me a PMax for X at $Y/day".
3. **Scope = Feature 1 ONLY this round.** Feature 2 (Video campaigns) and Feature 3 (video editing) ship in separate sessions.

---

## Sprint — 6 stories, dependency-ordered

### PMax-1 — `create_pmax_campaign` orchestrator MCP tool

**Goal:** one entry point that batches the 5+ Google Ads ops into a single transactional `mutate` call.

**Operations in order:**
1. `CampaignBudgetOperation` (create new budget)
2. `CampaignOperation` (campaign with `advertising_channel_type=PERFORMANCE_MAX`, budget ref)
3. `AssetOperation[]` (any new text/image assets not already in account)
4. `AssetGroupOperation` (asset group attached to campaign)
5. `AssetGroupAssetOperation[]` (attach each asset to the group with `field_type`)
6. `AssetGroupSignalOperation[]` (optional audience signals)

**Files:**
- New: `backend/google_ads/services/campaign/pmax_orchestrator.py` (the recipe).
- Update: `backend/google_ads/mcp_main.py` — register the tool.

**Input shape:**
```python
{
  "account_id": str,
  "name": str,
  "budget_micros": int,
  "final_urls": list[str],
  "business_name": str,
  "headlines": list[str],           # ≥3, ≤30 chars each
  "long_headlines": list[str],      # ≥1, ≤90 chars
  "descriptions": list[str],        # ≥2, ≤90 chars
  "logos": list[str],               # asset ids or URLs, ≥1
  "marketing_images": {             # ≥1 each
      "landscape": list[str],
      "square": list[str],
      "portrait": list[str],
  },
  "video_youtube_ids": list[str],   # ≥1
  "audience_signals": list[dict] | None,
}
```

**Output:** `{campaign_id, budget_id, asset_group_id, asset_ids: [...]}`.

**Validation gate:** before hitting Google, check all Google minimums. Return structured errors keyed by field. Never partial-submit.

**Rollback:** if AssetGroup creation fails, REMOVE the campaign + budget we just created. The orchestrator is transactional from the user's perspective.

**Acceptance:** `curl POST /api/.../create_pmax_campaign` with a full asset bundle produces a campaign visible in Google Ads UI within 5 seconds. Partial-failure injection rolls back cleanly.

---

### PMax-2 — `asset_groups` table + repo (V12 migration)

**Mirrors campaigns_repo. Single source of truth for what we sent.**

**Schema:**
```sql
CREATE TABLE asset_groups (
  asset_group_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  name TEXT,
  status TEXT,
  final_urls TEXT,                  -- JSON list
  business_name TEXT,
  headlines TEXT,                   -- JSON
  long_headlines TEXT,
  descriptions TEXT,
  asset_refs TEXT,                  -- JSON {logos: [...], landscape: [...], ...}
  signals TEXT,                     -- JSON audience signals
  last_synced_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (account_id, asset_group_id)
);
CREATE INDEX idx_asset_groups_campaign ON asset_groups(account_id, campaign_id);
```

**Files:**
- Update: `backend/app/database.py` — V12 migration.
- New: `backend/app/services/asset_groups_repo.py` — `list_for_campaign`, `sync_asset_groups`, `get_asset_group`.

**Acceptance:** after PMax-1 succeeds, the table has the asset_group row; future endpoint reads come from here, not the live API.

---

### PMax-3 — Auto-sync after create

**The user shouldn't have to click "refresh" after building.**

After PMax-1 succeeds, the orchestrator calls:
- `campaigns_repo.sync_campaigns(account_id)` — refreshes the sidebar.
- `asset_groups_repo.sync_asset_groups(account_id, campaign_id)` — populates PMax-2's table.
- Creates the per-campaign memory folder at `data/memory/{account_id}/{campaign_id}/` (chronicle.md, decisions.md, role_notes/, pinned_facts.md seeded).

**Files:** update `pmax_orchestrator.py` (PMax-1 file).

**Acceptance:** within 5s of submit, the sidebar's `synced X ago` resets and the new campaign is in the tree. Memory folder exists.

---

### PMax-4 — Campaign-type picker in the wizard

**Files:** `frontend/src/components/campaign/CampaignBuilder.tsx`.

Add a step-0 type picker (3 cards: Search · PMax · Video) right after the URL input step. PMax routes to PMaxWizard (PMax-5). Search keeps the current flow. Video shows a "coming soon" card with a waitlist note.

**Acceptance:** user lands in PMax wizard with one extra click; Search flow unchanged.

---

### PMax-5 — PMax wizard (frontend)

**New file:** `frontend/src/components/campaign/PMaxWizard.tsx` + sub-components per step.

**Steps:**

1. **Brief & budget** — campaign name, daily budget (USD), final URL(s), business name, conversion goal selector.
2. **Text assets** — three accordions (headlines / long headlines / descriptions). Each has:
   - "Generate with Creative Director" button → calls existing chat agent with `creative_director` role, brief from step 1; returns suggestions in editable rows.
   - Manual add row.
   - Live character counter against Google's limits (30/90/90).
   - Validates Google minimums (≥3 headlines, ≥1 long, ≥2 descriptions).
3. **Image assets** — four grids (logos / landscape 1.91:1 / square 1:1 / portrait 4:5). Each:
   - Drag-drop upload.
   - "Generate with Higgsfield" button → opens an inline higgsfield generator (mirror of `meta-ads-agent/frontend/src/components/HiggsfieldGenerator.tsx`).
   - Pick from existing `ad_assets` library.
   - Aspect-ratio validation against Google specs.
4. **Video assets** — YouTube ID paste field with live preview thumbnail. Validates the ID resolves to a public video. Hands off to Feature 3 ("Generate video") with a placeholder button for next session.
5. **Audience signals** *(optional)* — custom segments, in-market segments, similar audiences. Skippable.
6. **Review & submit** — full bundle preview with all assets, character counts, validation status. Submit triggers PMax-1 orchestrator. Disabled until all Google minimums satisfied.

**Acceptance:** entire flow from blank to live campaign in <10 minutes for a user with no prior assets; <2 minutes if they're reusing existing ones.

---

### PMax-6 — `pmax_strategist` agent recipe

**Two implementation options, picking option A for V1:**

**Option A (chosen):** new dedicated role file.

**Files:**
- New: `data/roles/{account_id}/pmax_strategist.md` — the role definition.
- Update: `backend/app/services/roles.py` — register it, add intent-classification keywords ("PMax", "Performance Max", "build me a PMax", "PMax campaign", etc.).

**The role's recipe (in its system prompt):**

When invoked with a brief like "build me a PMax for X at $Y/day":
1. Confirm the campaign-level inputs: budget, final URL, business name, conversion goal.
2. Hand off to `creative_director` (or generate inline) for text assets.
3. Hand off to image generation (higgsfield via the higgsfield-product-photoshoot skill) for missing image assets.
4. Ask user for YouTube video ID OR confirm an existing one from `ad_assets`.
5. Confirm audience signals or skip.
6. Show a single confirmation summary with every asset listed.
7. On user confirm, call the `create_pmax_campaign` orchestrator.
8. Verify the campaign appears in `campaigns_repo`. Sign off with the campaign URL.

**Acceptance:** chat prompt "build a Panama PMax at $50/day pointing at goldenvisas.mercan.com/panama" → working campaign in <8 prompts of back-and-forth.

---

## Cross-cutting requirements

- **Memory isolation:** every new PMax campaign auto-creates its memory folder with the correct `campaign_id`. The conversation↔campaign immutability rule we shipped earlier this session means the binding can't drift.
- **Chronicle entry:** PMax-3's auto-sync writes a CHRONICLE.md entry under the new campaign for the creation event (date, budget, asset summary, who built it).
- **Decision log:** the orchestrator records its asset choices to `decisions.md` so future analysis can attribute performance to specific creative bets.
- **Cost:** logged per generated asset (higgsfield cost per image, Claude tokens for copy) so the user knows what each campaign cost to build.

---

## Verification plan

1. **Happy path:** brief → wizard → orchestrator → campaign visible in Google Ads UI within 5s.
2. **Asset-spec edge cases:** wrong aspect ratio image, ≤2 descriptions, missing logo → wizard surfaces inline errors *before* submit; orchestrator never sees an invalid bundle.
3. **Partial-failure rollback:** simulate `create_asset_group` failure after campaign+budget created → budget + campaign rolled back, no orphans.
4. **Memory isolation:** new PMax campaign's folder has the right id; agent talking about it doesn't leak prior MapleRoots / Greece context.
5. **Sidebar sync:** new campaign appears in sidebar within 5s without a manual refresh.
6. **Chat path:** "build me a PMax for X at $Y/day" → working campaign in ≤8 prompts.

---

## Out of scope (explicit, for later)

- **Video Feature 2** (Video YouTube campaigns) — separate session.
- **Video Feature 3A** (motion-graphics editing) — Step 4 of the wizard has a placeholder button for now.
- **Video Feature 3B** (avatar + voice cloning) — premium tier, after 3A.
- **In-app YouTube upload** — user uploads to their own channel manually for V1.
- **A/B asset-group testing** within one PMax campaign — layer on after V1.
- **Brand exclusion lists** (PMax-specific) — useful but not blocking the create flow.

---

## Time estimate

| Block | Effort |
|---|---|
| PMax-1 + PMax-2 + PMax-3 (backend) | 1.5–2h |
| PMax-4 + PMax-5 (frontend wizard) | 2–2.5h |
| PMax-6 (role + intent wiring) | 30min |
| Tests + verification | 30–45min |
| **Total** | **~4.5–6h focused work** |

Realistic to ship in one focused session.
