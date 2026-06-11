# Unified Video Engine — PMax Wizard + Studio (plan, no code yet)

**Goal:** one video pipeline shared by PMax StepVideos and Studio, with three interchangeable backends: the existing Hyperframes slideshow renderer, Higgsfield generative clips (model user-selectable), and Soul talking-head presenter segments — composable into one MP4.

**Status:** plan only. Becomes **Epic 11** pending Wassim's approval (see BMAD note at bottom). No prd/epics edits now.

---

## 1. Engine abstraction — `VideoEngineRequest`

One request shape, a **segment timeline**: ordered segments, each tagged with an engine. The whole current PMax flow becomes the degenerate case (one `hyperframes` segment containing all scenes).

```python
# backend/app/services/video_engine.py  (NEW)
VideoEngineRequest:
    account_id: str
    segments: list[Segment]          # ordered; concat = final video
    voice_id: str | None             # ElevenLabs, applies to hyperframes + soul TTS
    music_filename: str | None       # bed across the whole timeline
    quality: str = "draft"
    aspect: str = "16:9"             # mezzanine target (1920x1080 default)
    campaign_id / brief: ...         # ad_assets card metadata (as today)

Segment (discriminated on `engine`):
  engine="hyperframes":  scenes: list[dict]            # today's storyboard scenes, verbatim
  engine="higgsfield":   model: str, prompt: str,      # text- or image-to-video
                         input_image: str | None,      # ad_assets id → local path → media upload
                         params: dict                  # duration/mode/quality — per-model contract
                         speak: str | None             # VO line muxed over the clip
  engine="soul":         soul_character_id: str,       # soul_characters row (V14, database.py:763)
                         script: str, model: str       # talking-head model (see open question §1a)
```

**Dispatcher:** `generate_engine_video(req)` async-generator (same SSE event shape as `generate_storyboard_reel`): render each segment to a local MP4 → **normalize to a mezzanine** (1080p/30fps/yuv420p/AAC — engines differ in fps, resolution, audio presence) → ffmpeg concat + music mux, reusing/generalizing `_stitch_mp4s` from `backend/app/services/premium_reel.py`.

| Backend | Implementation | Exists today |
|---|---|---|
| (a) hyperframes-slideshow | `generate_storyboard_reel` (premium_reel.py:181) called per-segment | YES — untouched |
| (b) higgsfield clip | `HiggsfieldClient(timeout_s=600).submit_video` → download `result_url` | Client + `/api/studio/generate-video` exist; reuse, add "download to temp + feed concat" path |
| (c) soul talking-head | Soul character (`soul_characters.soul_id`) + script → presenter clip | Soul training + picker exist (Studio S5); talking-head generation is NEW |

**§1a Open question (resolve before P2):** which CLI model id does lipsync/talking-head? Run `higgsfield --json model list --video` and `model get <id>` looking for speak/avatar/UGC models (the MCP skill advertises "presenter video" via Soul Cinema / Marketing Studio). Fallback if no CLI talking-head model: Soul still image (`text2image_soul_v2`) + image-to-video model with `speak` audio mux — presenter-ish, not lipsynced. Don't promise lipsync until verified.

---

## 2. Model picker UX (shared component)

- **NEW `frontend/src/components/video/ModelPicker.tsx`** — extracted from `HiggsfieldGenerator.tsx` (VIDEO_MODELS list at line ~75 + cost-estimate effect at ~180). Mounted in: Studio `HiggsfieldGenerator`, PMax `StepVideos` (PMaxWizard.tsx:581), and the future hybrid panel.
- **Catalog moves to backend**: new `GET /api/studio/models?kind=video` serving a cached `higgsfield --json model list --video` + per-model constraint map (max duration, duration type enum-string vs int, allowed aspects, budget tier). Today the catalog is hardcoded FE-side in two shapes — one source of truth ends the drift.
- **Per model show:** name · live credit cost (existing `POST /api/studio/cost-estimate`, returns 200 + `error_code` on incompatible params — keep that pattern) · max duration · budget badge. Plus the row **"Hyperframes slideshow — free, local, ~60-90s render"** so the operator sees the zero-cost default.
- **Defaults:** PMax → hyperframes (free, today's behavior unchanged); Higgsfield scene/segment → `veo3_1_lite` (8 credits/5s, cheapest verified); Kling default `--mode std`. Soul segment → whatever §1a resolves to.

---

## 3. Hybrid compositions

Two composition mechanisms, in increasing ambition:

1. **Higgsfield clip as a scene INSIDE a hyperframes storyboard (P1).** New scene `type: "higgsfield"` accepted by the render path: clip is generated (or referenced by existing `ad_assets` id to avoid re-burn on re-render), then spliced into the concat list at its scene position. Per-scene TTS still works — `_speak_text` audio muxes over the clip. **Constraint:** clip duration is fixed by the model (Veo: 4/6/8s; Kling: int ≤15) and can't stretch to audio like HTML scenes do — pad with freeze-frame or trim speak to fit; warn in UI when speak > clip length.
2. **Segment timeline (P2/P3).** e.g. Soul presenter intro (5s) + hyperframes slideshow body (15-20s) + hyperframes CTA outro (5s). Pure §1 dispatcher + concat. Later (P3): an overlay variant — a `broll-video` Hyperframes template taking `data-video-path` so generative clips get captions/lower-thirds like image broll does.

---

## 4. The script agent — engine-aware storyboards

`script_generator` (invoked in `backend/app/routers/pmax_video.py:_run_draft_job`) gets a minimally-extended contract:

- **Request adds** `engine_prefs: { allow_higgsfield: bool, video_model: str, max_higgsfield_scenes: int (default 2), soul_character_id: str | null }` on `PMaxVideoDraftRequest`.
- **Prompt adds** (only when allowed): broll scenes MAY instead be `{"type": "higgsfield", "prompt": "<cinematic shot description>", "speak": "..."}` — max N, used when no library image fits the beat; and optionally one opening `{"type": "soul", "script": "..."}` when a Soul character is provided.
- **`_clean_scenes` validates** the new types: caps higgsfield scenes at `max_higgsfield_scenes` (credit-burn guard), strips `soul` scenes when no ready character, falls back to image broll otherwise. Everything else unchanged — existing drafts keep working (engine fields absent ⇒ pure hyperframes).

---

## 5. Shared between PMax + Studio

| Layer | Plan |
|---|---|
| Backend service | NEW `app/services/video_engine.py` (dispatcher + normalizer + stitch). `premium_reel.py` and `higgsfield_client.py` untouched underneath. |
| Router | NEW `app/routers/video_engine.py` — `/api/video-engine/draft` + `/render` (job+poll, **DB-row job state** like Studio, not the in-memory dicts pmax_video.py uses — survives restarts). `/api/pmax/video/*` stays as a thin delegate for wizard compat. |
| Frontend panel | NEW `components/video/VideoEnginePanel.tsx` — extract the draft→storyboard-edit→render→YouTube block out of `StepVideos` (PMaxWizard.tsx:581-1000) into a standalone component; mount in PMaxWizard step AND as a Studio tab (`StudioPage.tsx`), alongside existing `ScriptGenerator.tsx`. |
| YouTube upload | Reused as-is — `/api/youtube/upload` takes an `ad_assets` id; panel exposes it in both hosts (PMax auto-fills `videoIds`; Studio just shows the link). |
| Output | All engines land in `ad_assets` via `record_generated_video` with `account_id` set (Studio library shows everything, as today). |

---

## 6. Phasing

| Phase | Scope | Files touched | Effort | Risks |
|---|---|---|---|---|
| **P1 — model picker + higgsfield-clip-as-scene** | `GET /api/studio/models` catalog endpoint; shared `ModelPicker.tsx` (refactor HiggsfieldGenerator to use it); `type:"higgsfield"` scene in draft prompt + `_clean_scenes` + render path (generate clip → normalize → splice); engine_prefs on draft request | `routers/studio.py`, NEW `components/video/ModelPicker.tsx`, `HiggsfieldGenerator.tsx`, `routers/pmax_video.py`, `services/premium_reel.py` (or thin wrapper), `PMaxWizard.tsx` | 2-3 sessions | Credit burn on every re-render (mitigate: cache clip by prompt-hash in ad_assets, reuse on re-render); per-model param contracts (Veo string-enum duration vs Kling int — catalog must encode this or CLI errors at render time); render time jumps 60-90s → 6-12 min when clips queue |
| **P2 — Soul talking segment** | Resolve §1a model question; `engine:"soul"` segment + `type:"soul"` scene; Soul picker (reuse `SoulCharactersPanel` picker) in panel; segment-timeline dispatcher v1 (`video_engine.py`) for intro+body+outro | NEW `services/video_engine.py`, NEW `routers/video_engine.py`, `pmax_video.py` delegate, NEW `VideoEnginePanel.tsx` extraction, `StudioPage.tsx` | 2-3 sessions | Talking-head model may not exist in CLI (fallback = non-lipsync presenter — set expectation); Soul training latency (minutes-hours) means panel must handle "no ready character" gracefully; audio continuity across engine boundaries (VO bed vs per-clip audio — Kling `--sound on` clips bring their own audio, must duck/replace) |
| **P3 — hybrid timeline editor** | Drag-to-reorder segment UI, per-segment engine/model/duration controls, `broll-video` overlay template (clips get captions/lower-thirds), crossfade options between heterogeneous segments | `VideoEnginePanel.tsx` (major), NEW hyperframes `video-projects/broll-video/` template, `video_engine.py` | 3-4 sessions | UX complexity creep — keep the one-click "agent drafts it" path primary; ffmpeg concat of mixed fps/codec sources (mezzanine normalize is mandatory, adds re-encode time); total cost visibility (sum per-segment estimates in a sticky footer before render) |

**Cost guardrails (all phases):** show summed credit estimate before any render that touches Higgsfield; hard cap higgsfield scenes per draft (default 2); reuse generated clips by `ad_assets` reference on re-render; the balance pill (red <50) already exists — surface it in the panel too. Reference costs (verified May 2026): veo3_1_lite 8cr/5s · kling3_0 std 10cr/5s · wan2_6 13cr.

---

## 7. BMAD note

This plan = **Epic 11 candidate**, pending Wassim's approval. Do NOT edit `_bmad-output/planning-artifacts/` (prd/epics) now. When P1 ships: one Tier-1 row in `_bmad-output/feature-log.md` (`NEW — unplanned` until the epic is formalized), then fold into the epics at the next Tier-2 reconcile.
