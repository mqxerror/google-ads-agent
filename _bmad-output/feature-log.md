# Feature Log — google-ads-agent (BMAD drift reconcile, Tier 1)

Lightweight delta capture so the BMAD planning artifacts don't silently drift from the code.

- **Tier 1 (this file):** every session that ships a feature appends ONE row to the Active table below — *before ending the session*. Cheap (~10s), captures the *why* while it's fresh. Same reflex as the chronicle line in this folder's product-dev memory.
- **Tier 2 (reconcile):** when this log exceeds ~10 unreconciled rows **OR** a month has passed **OR** before a version milestone, run `/bmad-document-project` to fold these deltas back into `_bmad-output/planning-artifacts/`. Then move the folded rows under **Reconciled** with the date.

Convention: **Story** = the epic/story id it maps to, or `NEW — unplanned` if it had no story. Keep each row to one line.

## Active (unreconciled)

| Date | Feature / change | Story | Files touched |
|---|---|---|---|
| 2026-06-02 | App-wide visual re-skin to Shopify "Studio" calm light design (OKLCH token layer + shadcn aliases → light default; `.studio-prose`/`.studio-caret`/`.studio-pulse`/`.label-section`; quiet tool rows; avatar-lane assistant turns; sunken composer well) | NEW — unplanned | frontend/src/index.css, frontend/index.html, frontend/DESIGN.md (new), frontend/PRODUCT.md (new), src/components/chat/{ChatMessage,ChatInput,ContextBadge,MemoryPanel,AgentAvatar,ToolCallBlock}.tsx, src/components/layout/ChatPanel.tsx |
| 2026-06-10 | Default model bumped Opus 4.8 → Fable 5 (`claude-fable-5[1m]`; plain `claude-fable-5` = fallback; opus/sonnet/haiku aliases kept) | NEW — unplanned | backend/app/services/{agent,token_counter,workflow_orchestrator}.py, backend/app/models/schemas.py, frontend/src/components/chat/ChatInput.tsx, components/campaign/CampaignBuilder.tsx, components/layout/ChatPanel.tsx, lib/{chatApi,chatTemplates}.ts, README.md, frontend/PRODUCT.md |
| 2026-06-10 | PRD+epics updated for commercialization: Phase 1.5 added to PRD §8 (PMax finalization P0, MCP plan tools P0, Shopping P1; supersedes "local-first forever" non-goal for the hosted-MCP track) + Epics 8/9/10 added to epic list & implementation order (stories TBD via /bmad-create-epics-and-stories). One-time direct edit authorized by Wassim (BMAD-governance rule otherwise) | Planning artifacts | _bmad-output/planning-artifacts/{prd-v2,epics-v2}.md, research/product-roadmap.md |
| 2026-06-10 | Epic 8 PMax finalization: local-UUID→Google image-asset bridge in orchestrator (pass-through for real resource names, webp/oversize→PNG/JPEG transcode via Pillow, pre-flight 422 for missing files), audience signals attached post-link (search themes + audiences, best-effort warnings), step-aware PMaxStepError + rollback report surfaced to wizard (502 detail incl. step/rolled_back), wizard now sends collected signal hints | Epic 8 | backend/google_ads/services/campaign/pmax_orchestrator.py, backend/app/routers/pmax.py, frontend/src/components/campaign/PMaxWizard.tsx |
| 2026-06-10 | Epic 9 MCP plan tools: create_plan/list_plans/approve_plan/skip_plan/run_plan_now on the HTTP MCP bridge (bearer auth; budget/bids/status/geo default approval-gated; reuses scheduler lifecycle; 10 tools total registered). Epics 8-10 stories written into epics-v2.md (9 stories). Autonomous execution authorized by Wassim 2026-06-10 (1-hour window; no live Google Ads mutations run) | Epic 9 + planning | backend/app/mcp_server.py, _bmad-output/planning-artifacts/epics-v2.md |

## Reconciled

_Rows folded into the planning artifacts. Format: `YYYY-MM-DD — reconciled via /bmad-document-project (covers <date range>)` followed by the moved rows._
