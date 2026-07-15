# Studio Redesign Plan — Two Studios, One Director

**Status:** PLAN (build-ready) · drafted 2026-07-13 by the planning agent
**Supersedes the *layout* of:** `research/studio-redesign-brief.md` (Epic 12 pass-1, APPROVED 2026-06-11) — that brief's *invariants still bind* (see §0.2). This plan is the next pass: the entry fork, the AI Video Studio, and the Video Director agent.
**Executor:** Opus builder. Every section is written to be executed without re-deriving decisions. File:line refs verified against the tree on 2026-07-13.

---

## 0. What Wassim asked for, and what must not break

### 0.1 The spec (his words, structured)

1. **"Separate the Higgsfield and the Hyperframes — I choose from the beginning."** Kill the ambiguity where engine identity hides inside mode names (Avatar Snap / Brand Reel / Premium Reel / "Finished video"). Studio entry = a clean fork: pick your studio first, then live in a full flow built for that path. Each path elegantly designed — *especially* the Higgsfield one.
2. **"The video needs a Director."** A Video Director agent OWNS the video flow: drafts the script **for the selected Higgsfield model** (model-aware — each model has different clip lengths, param contracts, strengths), and **"can talk to the campaign director if needed or selected"** — when the video is for a campaign, the Video Director consults that campaign's Director/memory (guidelines, pinned facts, LP claims, audience) before drafting.
3. Benchmark: "the Meta ad creator is not bad — but not close to being a STUDIO for videos and images." Studio must feel like a real creative studio, not a form.

### 0.2 Standing invariants (do not violate)

- **Decoupling (approved brief, `research/studio-redesign-brief.md:81-86`):** Studio may become a standalone product. The studio service layer NEVER imports google_ads code (`model_catalog.py:15-17`, `video_engine.py:46`). Campaign context flows in through props/params only. The Video Director's campaign consult must respect this: the consult lives in the *router/orchestration* layer, not in studio services.
- **DB row = source of truth for jobs** (`studio.py:1-25` invariants block). Never in-memory-only job state for anything new.
- **Design law:** `frontend/DESIGN.md` — Shopify-calm light, OKLCH tokens only, one indigo accent ≤10% of any surface, no gradient text / glassmorphism / icon-card grids / em dashes (`DESIGN.md:99-104`). "Elegant" is achieved WITHIN this. The pink/amber/violet sprawl in `VideoCreator.tsx` dies with this redesign (it was already flagged in the approved brief §3).
- **Conversation↔campaign binding** (memory `project_conversation_campaign_binding.md`): a conversation binds to ONE campaign for life. The Video Director's conversation is created *after* the campaign link is chosen; changing the link later creates a NEW conversation (§6.6).
- **StudioPanel's host contract is frozen** — PMax wizard depends on it (§9.2 zero-regression list).

---

## 1. Current state map (what exists, where)

### 1.1 Frontend

| Piece | File | Notes |
|---|---|---|
| Studio hub page | `frontend/src/components/studio/StudioPage.tsx` (311 L) | Header buttons Upload / Write script / New video / Create (`:191-221`); Library·Souls·Presets tabs (`:29-35`, `:263-296`); mounts VideoCreator drawer (`:249-261`) and StudioPanel (`:300-308`) |
| Shared creator panel | `frontend/src/components/studio/StudioPanel.tsx` (1251 L) | 480px slide-over, modes image/video/copy (`:54`); the just-shipped model dropdown + 15/30/60 "finished video" sub-mode crammed in (`:143-149`, `:665-776`); Tune disclosure (`:987-1087`); Enhance→3-angle variants (`:346-380`, `:828-847`); talking-intro Soul toggle (`:126-137`, `:781-826`) |
| Legacy video strip | `frontend/src/components/chat/VideoCreator.tsx` (1810 L) | The pink-bordered "Video Ad Creator": modes `avatar-snap`/`brand-reel`/`premium-reel` (`:28`, `:628-668`), Premium sub-modes single/storyboard (`:29`, `:776-806`), Brand Story plan→preview→render (`:464-545`), stock/AI image swap modals, SSE consumer (`:548-595`). Hard-coded pink/amber/violet/emerald — banned palette |
| Model picker | `frontend/src/components/video/ModelPicker.tsx` (91 L) | `<select>` fed by `useModelCatalog(kind)` (`:28-39`) with module-level cache (`:14-26`) |
| Job watcher | `frontend/src/components/studio/useStudioJobs.ts` | poll-based watch/watchMore/failSubmit |
| Library / Souls / Presets | `AssetLibrary.tsx` (627 L), `SoulCreator.tsx` (401 L), `MarketingPresetsPanel.tsx` (167 L) | All redesigned in Epic 12 Phase B — keep |
| Routing / mount | `frontend/src/App.tsx:84-86` (URL→`showStudio` bridge), `:220-221` (`/studio`, `/studio/c/:assetId` routes); `frontend/src/stores/appStore.ts:136-146` (`setShowStudio` clears campaign + sibling toggles) | Studio is a content-area takeover driven by a store boolean, with a URL bridge |
| PMax consumer | `frontend/src/components/campaign/PMaxWizard.tsx:35-38, 486-498, 1472-1484, 1894-1904` | StudioPanel in copy mode (Text assets), YouTube-thumbnail slot, and per-image-slot generation with locked aspect |

### 1.2 Backend

| Piece | File | Notes |
|---|---|---|
| Studio router | `backend/app/routers/studio.py` (1297 L) | `/api/studio/*`: models (`:207-223`), generate-image (`:226-291`), generate-video (`:359-406`), cost-estimate (`:294-333`), balance (`:335-356`), jobs + SSE (`:409-451`), extract-brief → 2-stage drafter (`:618-695`), marketing hooks (`:716-742`), soul train/list (`:748-865`) |
| Model catalog | `backend/app/services/model_catalog.py` (325 L) | 12 video + 10 image curated entries w/ per-model constraints (`:42-191`), `clamp_duration` (`:208-229`), **`plan_scenes(target_seconds, model_id)`** (`:232-277`), live-availability refresh (`:280-304`) |
| Video engine (service) | `backend/app/services/video_engine.py` (559 L) | Segment timeline {storyboard, higgsfield, soul} → compiled to flat scenes → premium_reel render (`:492-559`); planner mode from target_seconds+model+prompt (`:503-513`); caps (`:65`, `higgsfield_scene.py:44`); `estimate_timeline_credits` (`:393-486`) |
| Video engine (router) | `backend/app/routers/video_engine.py` | `/api/video-engine/estimate` + `/render` + `/render/{job_id}`; render-job state is **in-memory** (`:20-22` docstring — DB-row deferred to P3) |
| Scene resolver | `backend/app/services/higgsfield_scene.py` (242 L) | prompt-hash clip cache (`:49-78`), generate+localize+record (`:81-168`), mezzanine normalize (`:187-229`) |
| Renderers | `premium_reel.py` (872 L; Hyperframes templates `:34-63`, storyboard reel), `brand_reel.py` (1348 L; Pillow+ffmpeg), `backend/hyperframes/` (student kit + `video-projects/mercan-*` templates) |
| Prompt quality | `backend/app/services/prompt_drafter.py` | `draft_variants` (`:60`), stage 1 decompose (`:126`), stage 2 w/ per-account role file `data/roles/{account_id}/visual_director.md` (`:86`, `:290`) + pinned-claims injection (`:315`) |
| Agent seam | `chat_runner.py` (542 L): generic `start(run_fn, ...)` (`:301-323`), `subscribe` (`:326-347`), event envelope+persistence (`:234-296`), stop (`:422-455`); `chat_orchestrator.py` (744 L): `run_turn` S0-S8 state machine (`:310-739`), `_dispatch_specialist` (`:220-306`), `_run_direct` (`:166-216`); SSE endpoints `routers/chat.py:522-595` (`/turns/active`, `/turns/{id}/events`, `/turns/{id}/stream`, `/stop`) |
| Personas | `roles.py` (992 L): `ROLES` registry + `_register` (`:40-44`), file overrides `data/roles/{role_id}.md` (`:770-800`), `classify_intent` (`:916`), existing `script_generator` role (`:184-225`) |
| Campaign memory | `campaign_memory.py` (660 L): per-campaign dirs (`:146-151`), `load_memory_index`/`load_decisions`/pinned facts loaders (`:231+`), `append_role_notes` (used at `chat_orchestrator.py:722-731`), staleness guard (`:32-55`) |

### 1.3 The problem, precisely

- Engine identity (Higgsfield generative vs Hyperframes/GSAP kinetic vs HeyGen avatar) is implicit inside mode names scattered across TWO components (StudioPanel video sub-modes + VideoCreator's three tabs) mounted on the same page.
- The creator is a cramped strip/panel ON TOP of the library, not a place to work. The new model dropdown + 15/30/60 presets were wedged into the 480px panel (`StudioPanel.tsx:665-776`) — functional, but the opposite of a studio.
- No agent presence in the video flow. The 2-stage drafter exists (`prompt_drafter.py`) but only as a one-shot "Enhance" button; nothing owns script → storyboard → render end-to-end, and nothing consults campaign knowledge.

### 1.4 Benchmark notes — meta-ads-agent (read 2026-07-13, brief)

`../meta-ads-agent/frontend/src/components/`: `StudioGenerator.tsx` (template picker + data-key form + proposal→approve→apply gate), `HiggsfieldGenerator.tsx`, `CreativeLibrary.tsx`, `launch/` workspace (DraftTree, MetaPreviewModal, AdCompositionRow), `wizard/` shells. Three patterns worth beating:

1. **Template-driven forms** (pick template → fill data keys → render). Functional, but it's a form. We beat it with a director-led storyboard the operator *converses with*.
2. **Placement preview** (MetaPreviewModal / AdPreview). Our equivalent already exists for PMax (post-crop slot preview). The AI Video Studio must match this energy with a real storyboard canvas: per-scene cards with duration math + thumbnails as clips land.
3. **Three-step approval gate before spend** (proposal → approve → apply). Correct instinct, heavy UX. Ours is one explicit **cost gate** — a priced Render button (estimate endpoint already live) that never fires silently.

Meta's prompt-architecture advantage (multi-stage decompose, role files, pinned claims) was already ported (memory `feedback_prompt_quality_principles.md`); the Video Director builds on that port, not from scratch.

---

## 2. The new IA — a fork at the door

### 2.1 Concept

`/studio` becomes **Studio Home**: a calm chooser with **three door cards** over the shared **Library**. Each door opens a full-page studio (content-area takeover, same as today's Studio — not another slide-over):

| Door | Engine identity (explicit, on the card) | Route |
|---|---|---|
| **AI Video Studio** | "Generative video · Higgsfield — Veo, Kling, Seedance…" | `/studio/ai-video` |
| **Kinetic Studio** | "Motion graphics · Hyperframes (GSAP) + Brand Reel — renders locally, no credits" | `/studio/kinetic` |
| **Image Studio** | "Generative images · Higgsfield — Nano Banana, GPT Image, Soul" | `/studio/image` (v1: opens StudioPanel in image mode — see §2.4) |

**Library / Souls / Presets = shared substrate, stay on Home** as the existing section tabs (`StudioPage.tsx:263-296`). Rationale: every studio *writes to* the same `ad_assets` library; Souls are used by BOTH image and video Higgsfield paths; moving them into one studio would orphan the other. The studios *link into* them contextually (AI Video Studio's Soul picker deep-links `/studio#souls` when no Soul is ready, mirroring the copy at `StudioPanel.tsx:806-808`).

### 2.2 Routing & migration

Current: `/studio` and `/studio/c/:assetId` routes (`App.tsx:220-221`) flip `showStudio` via the URL bridge (`App.tsx:84-86`); `ContentArea` renders `StudioPage` when `showStudio` is true.

Changes (small, surgical):

1. `App.tsx`: add routes `/studio/ai-video`, `/studio/ai-video/:projectId`, `/studio/kinetic`, `/studio/kinetic/:lane` — all `element={<AppRoot />}`, exactly like the existing pair. The `location.pathname.startsWith('/studio')` bridge at `App.tsx:84-86` already catches all of them — **no bridge change needed**.
2. `StudioPage.tsx` becomes a thin **StudioRouter**: reads `useLocation()`, renders `<StudioHome/>` for `/studio` + `/studio/c/:assetId`, `<AIVideoStudio/>` for `/studio/ai-video*`, `<KineticStudio/>` for `/studio/kinetic*`. Keep the store boolean untouched (`appStore.ts:136-146`) — the fork lives inside the studio surface, invisible to the rest of the app.
3. Studio-internal navigation uses `navigate('/studio/ai-video')` etc.; "Back to Studio" in each studio header navigates `/studio`; the existing "Back to campaigns" (`StudioPage.tsx:176-180`) stays on Home only.
4. Deep links: `/studio/c/:assetId` unchanged (Home + Library select). `/studio/ai-video/:projectId` re-opens a Video Director project (§6.5) — refresh-proof, like `/c/:conversationId` for chat.
5. Migration of entry points: the Home header loses "Write script" and "New video" buttons (`StudioPage.tsx:191-212`) — those flows re-home into Kinetic Studio (§7). "Upload" and "Create" (→ StudioPanel image) stay. Anything else in the app that opened VideoCreator must be re-pointed (builder: `grep -rn "VideoCreator" frontend/src` before moving — as of today its only mount is StudioPage.tsx:22,253).

### 2.3 Studio Home wireframe

```
┌────────────────────────────────────────────────────────────────────────────┐
│  ✦ Studio                                    [credits pill] [local only]   │
│  Create video and image assets, manage Souls and presets                   │
│                                              [Back to campaigns] [Upload]  │
│                                                                            │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌────────────────────┐  │
│  │ ▶ AI VIDEO STUDIO    │ │ ◆ KINETIC STUDIO     │ │ ▣ IMAGE STUDIO     │  │
│  │                      │ │                      │ │                    │  │
│  │ Generative video     │ │ Motion graphics &    │ │ Generative images  │  │
│  │ with a Video Director│ │ kinetic typography   │ │ & Soul portraits   │  │
│  │                      │ │                      │ │                    │  │
│  │ Higgsfield · Veo,    │ │ Hyperframes (GSAP) + │ │ Higgsfield · Nano  │  │
│  │ Kling, Seedance, Soul│ │ Brand Reel · local   │ │ Banana, GPT Image  │  │
│  │ 12 models · credits  │ │ render · no credits  │ │ 10 models · credits│  │
│  │                      │ │                      │ │                    │  │
│  │ [Open studio →]      │ │ [Open studio →]      │ │ [Create image →]   │  │
│  │ Resume: "Panama 30s" │ │                      │ │                    │  │
│  └──────────────────────┘ └──────────────────────┘ └────────────────────┘  │
│                                                                            │
│  Library   Souls   Presets                                    [search 🔍] │
│  ─────────────────────────────────────────────────────────────────────────│
│  [Type ▾] [Source ▾] [Campaign ▾] [Model ▾] [Created ▾]                    │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                  │
│  │    │ │    │ │    │ │    │ │    │ │    │ │    │ │    │   … asset grid   │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘                  │
└────────────────────────────────────────────────────────────────────────────┘
```

Door-card design (within DESIGN.md): `bg-card` + `border-border` + `--shadow-resting`, hover lifts to `--shadow-elevated` + `border-accent/40` (transform/opacity only, 140-220ms `--ease-out-quint`). Title 18px/600 Inter; the engine line 12px `text-muted-foreground`; one small mono chip per card for the cost fact (`12 models · credits` vs `local · free`) — this chip is what makes the engine identity *explicit at the door*, which is the whole point of the fork. These are true choice-cards, an affordance the DESIGN.md card ban explicitly permits ("Cards only where they're the best affordance"). They are NOT an identical icon-heading-text grid: each card carries distinct meta (resume chip on AI Video when a draft project exists, "no credits" badge on Kinetic, model-count on Image).

The "Resume: …" chip appears when `studio_video_projects` (§6.5) has a row with `status IN ('drafting','storyboard')` — the memory-file lesson from the PMax wizard localStorage fix applies: never lose in-progress work to a tab close.

### 2.4 Image Studio — v1 decision

v1: the Image Studio door does `openCreate('image')` — the existing StudioPanel slide-over over Home (`StudioPage.tsx:81-86`), unchanged. Zero build cost, keeps the fork honest (the door states the engine), and image generation genuinely fits the panel (single-shot, no timeline). A full-page Image Studio (gallery-first, variant comparisons) is a later pass — listed in §12 open calls. Do NOT build a page shell that just embeds the panel; that's fake depth.

---

## 3. AI Video Studio — the flagship

### 3.1 Shape

A **workspace, not a wizard**: three zones — setup rail (left), storyboard canvas (center), Director dock (right). The empty state walks brief → model → draft; after that it's a place you *work in*, iterating with the Director.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ← Studio   AI VIDEO STUDIO           project: "Panama QIV 30s"   [credits]   │
├───────────────┬───────────────────────────────────────────┬──────────────────┤
│ SETUP         │  STORYBOARD                               │ VIDEO DIRECTOR   │
│               │                                           │                  │
│ Campaign      │  ┌─────────────────────────────────────┐  │ ● Director       │
│ [Panama QIV ▾]│  │ SCENE 1 · 8s            [veo3_1] ⋮  │  │                  │
│ ☑ Consult     │  │ ┌─────────┐ Visual: Aerial dawn     │  │ Consulted the    │
│   campaign    │  │ │ thumb / │ shot over Panama City   │  │ campaign Director│
│   Director    │  │ │ pending │ skyline, glass towers…  │  │ — 3 pinned claims│
│               │  │ └─────────┘ VO: "Your capital can   │  │ apply. Drafting  │
│ Model         │  │             live where it grows."   │  │ 4 scenes for     │
│ ┌───────────┐ │  └─────────────────────────────────────┘  │ Veo 3.1 (8s max  │
│ │ Veo 3.1   │ │  ┌─────────────────────────────────────┐  │ per clip)…       │
│ │ Google ·  │ │  │ SCENE 2 · 8s                     ⋮  │  │                  │
│ │ Best · 4/ │ │  │ …                                   │  │ ┌──────────────┐ │
│ │ 6/8s clips│ │  └─────────────────────────────────────┘  │ │ 3 concept    │ │
│ │ [Change]  │ │  ┌─────────────────────────────────────┐  │ │ angles       │ │
│ └───────────┘ │  │ SCENE 3 · 8s                     ⋮  │  │ │ [problem-led]│ │
│               │  │ …                                   │  │ │ [aspiration] │ │
│ Length        │  └─────────────────────────────────────┘  │ │ [social-prf] │ │
│ [15][30][60]  │  ┌─────────────────────────────────────┐  │ └──────────────┘ │
│ ≈ 4 clips × 8s│  │ SCENE 4 · 6s                     ⋮  │  │                  │
│               │  │ …                                   │  │ "Make scene 2    │
│ Aspect [16:9▾]│  └─────────────────────────────────────┘  │  punchier"       │
│               │  ─────────────────────────────────────    │ ┌──────────────┐ │
│ Audio         │  ≈ 62 credits · 30s target · 4 scenes     │ │ …composer…   │ │
│ ☐ Music bed   │  [ Render video — burns ≈62 credits ]     │ └──────────────┘ │
│ ☐ Voiceover   │                                           │                  │
└───────────────┴───────────────────────────────────────────┴──────────────────┘
```

Column specs: rail 264px fixed; dock 360px, collapsible to a 40px spine (chevron) so the canvas breathes on small screens; canvas fluid, scene cards max-w `760px`, centered.

### 3.2 Model gallery (cards, not a dropdown)

Clicking **[Change]** on the rail's model chip opens a **model gallery sheet** (centered modal, max-w 880px, `--shadow-elevated`): the 12 video-catalog entries as selectable cards fed by the existing `useModelCatalog('video')` (`ModelPicker.tsx:28-39`) — the `<select>` stays untouched for StudioPanel hosts.

Card contents per entry (all data already in the catalog or added by one field, §10.2):

```
┌───────────────────────────────┐
│ Veo 3.1            Best · ✓   │   label + tier chip + available dot
│ Google (American)             │   origin — derived server-side (§10.2)
│ Clips: 4 / 6 / 8s (enum)      │   from constraints.durations/max_duration
│ Strength: motion & physics    │   NEW `strengths` field (§10.2)
│ realism, native quality tiers │
│ ≈ premium · tens of credits   │   cost_text
│ 30s target → 4 clips of 8s    │   live clip math: ceil(target/maxClip)
└───────────────────────────────┘
```

Grouped by tier rows (Best quality / Fast / Budget — order per `ModelPicker.tsx:12`). Selecting a card closes the sheet, snaps duration legality via the same clamp logic StudioPanel uses (`StudioPanel.tsx:207-219`), and — this is the key director hook — **stamps the model contract into the Director's next drafting context** (§6.3). The clip-math line reuses the FE mirror of `plan_scenes` (`StudioPanel.tsx:194-200`); keep that mirror in one shared hook `useClipMath(modelInfo, targetSeconds)` extracted from StudioPanel so the two surfaces can't drift.

### 3.3 Storyboard canvas

- One card per planned scene: index + duration chip (mono), editable visual-prompt textarea, editable VO line, model chip (defaults to the project model; per-scene override allowed via the ⋮ menu — `segments_to_scenes` already accepts per-scene `model`, `video_engine.py:146-149`), thumbnail slot (empty → skeleton while rendering → video poster when the clip lands).
- Scene count/durations come from the Director's draft, which itself is seeded by `plan_scenes(target_seconds, model_id)` (`model_catalog.py:232-277`) — the operator can add/remove/reorder scenes; the cap is `MAX_HIGGSFIELD_SCENES = 8` (`higgsfield_scene.py:44`), surfaced as a quiet counter "4 / 8 scenes".
- Footer = the **cost gate**: live total from `POST /api/video-engine/estimate` with the scene list (`routers/video_engine.py:55-90`; cached clips price 0 per `video_engine.py:449-453`), partial totals shown as `N+` exactly like `StudioPanel.tsx:955-958`. The Render button carries the number in its label ("Render video — burns ≈62 credits") — never a naked Render.
- Render → `POST /api/video-engine/render` with `segments=[{engine:"higgsfield", prompt, model, duration, speak}...]` + audio options; job-poll via `GET /api/video-engine/render/{job_id}` every 3s (same loop as `StudioPanel.tsx:495-525`). Stage messages from the render stream into a slim progress strip above the footer ("Scene 2/4 rendering · 4m elapsed"). Finished asset lands in `ad_assets` tagged with the campaign (existing behavior), and the canvas shows a player + "Open in Library" (deep-link `/studio/c/:assetId`).

### 3.4 Rail details

- **Campaign** dropdown = `fetchCampaigns(accountId)` (already on StudioPage, `:54-59`) + "No campaign". Under it, the **Consult campaign Director** checkbox — enabled only when a campaign is linked; default ON (§6.4).
- **Length**: the 15/30/60 preset pills (moved out of the cramped panel; same values, same planner semantics) + the "≈ N clips × Ms" hint.
- **Audio**: music-bed picker + voiceover, straight port of the finished-video audio block (`StudioPanel.tsx:716-775` + music picker `:1117-1164`); voices from `/api/video/voices`, music from the asset library audio query.
- **Aspect**: model-constrained select (clamped from `constraints.aspect_ratios`).

---

## 4. Design direction (both studios, within DESIGN.md)

- **No new colors.** Studio identity comes from structure and one glyph per studio (lucide `Clapperboard` for AI Video, `Type`/`Zap` for Kinetic, `Image` for Image Studio) tinted `text-accent` — not from per-studio hues. The per-persona palette exception (`DESIGN.md:14-15`) covers the Director's avatar in the dock (add a `video_director` entry to `agentProfiles.ts`, light-tuned like the other 10).
- Scene cards: `bg-card border-border rounded-lg`, NOT filled panels-in-panels; duration + cost figures in JetBrains Mono 12.5px; section labels `.label-section`.
- Director dock reuses chat components wholesale: `.studio-prose` for Director prose, quiet tool rows for consult/drafting steps (the `chat` tool-row pattern, `DESIGN.md:86-88`), `.studio-pulse` working dot. The dock IS a chat panel — do not invent a second chat visual language.
- Streaming: drafting text streams token-by-token into the dock (SSE, §6.7); the storyboard populates card-by-card as the Director emits scenes — **no blind spinners anywhere**. Cost estimates tick in per-scene ("pricing scene 3…").
- Motion: card entrance = 6px translate-y + fade, 180ms, stagger 40ms; respect transform/opacity-only rule.

---

## 5. The Video Director — persona decision

**Decision: a NEW `video_director` role in the ROLES registry, with the existing per-account `visual_director.md` retained as the stage-2 *prompt-crafting* subroutine it calls.** Not an extension of visual_director. Justification:

1. `visual_director` is not a chat persona — it's a per-account system-prompt *file* (`data/roles/{account_id}/visual_director.md`) consumed by `prompt_drafter._stage2_draft` (`prompt_drafter.py:86, :157-206`). It crafts single-image/video *prompts*. It has no registry entry, no avatar, no tools, and `roles.py` overrides live at a different path (`data/roles/{role_id}.md`, global — `roles.py:24, :740-767`). Overloading it would tangle two conventions.
2. The Video Director's job is bigger: timeline math, VO pacing (~2.5 words/sec — steal the word-count tables from the `script_generator` role, `roles.py:198-203`), scene continuity, model-contract awareness, campaign consultation, and conversational iteration. That's a persona, not a prompt file.
3. Registry membership gives us for free: appearance in `/api/chat/roles` (`chat.py:932`), file-based override editing (`roles.py:735-767`), and future eligibility as a plannable specialist in `run_turn` orchestrations (explicitly deferred, §11 flags).

Register in `roles.py` (after script_generator, ~`:226`):

```python
_register(Role(
    id="video_director",
    name="Video Director",
    avatar="clapperboard",
    specialty="Model-aware video scripting, storyboarding, and production direction for AI-generated video",
    system_prompt=<see §6.3 contract>,
    tools_focus=[],
    context_needs=["profile", "pinned_facts", "decisions"],
))
```

The per-scene *visual prompts* inside the storyboard are still drafted in the visual_director voice: the Video Director turn calls `prompt_drafter`'s stages rather than re-implementing them (§6.3, step V3). The four prompt-quality levers (multi-stage, role files, pinned claims, forced scaffolding — memory `feedback_prompt_quality_principles.md`) are all preserved by construction.

---

## 6. The Video Director flow — mechanism spec

### 6.1 Transport: ride chat_runner, invent nothing

`chat_runner.start(run_fn, ...)` is deliberately generic over `run_fn` (`chat_runner.py:56, :301-323`). The Video Director is a new run_fn — `video_director_turn` — living in a new module `backend/app/services/video_director.py`. It gets, for free: turn rows, monotonic-seq envelopes, batched event persistence (`chat_turn_events`), replay after restart, `subscribe` SSE, per-turn stop with process-group kill (`chat_runner.py:422-455`), zombie sweep. The FE consumes it through the EXISTING endpoints (`chat.py:522-595`) — `/turns/{turn_id}/stream` with cursor replay. **Do not build a parallel event bus in the studio router.**

Decoupling note (§0.2): `video_director.py` orchestrates *around* studio services — it may import `campaign_memory`, `roles`, `prompt_drafter`, `model_catalog`; it lives in the agent layer like `chat_orchestrator`, so the google_ads-free rule for studio services is not violated (studio services still import nothing from it).

### 6.2 Kickoff endpoint

New router slice (in `routers/studio.py` or a new `routers/video_director.py` — builder's call; keep `/api/studio` prefix):

```
POST /api/studio/video-projects                     → create project row (§6.5) + its conversation
POST /api/studio/video-projects/{id}/draft          → chat_runner.start(video_director_turn, ...)
        body: {message?: str}   # empty = initial draft; non-empty = iteration ("make scene 2 punchier")
        → {turn_id}             # FE then opens /api/chat/conversations/{cid}/turns/{turn_id}/stream
PATCH /api/studio/video-projects/{id}               → save storyboard edits (operator-side edits, debounced)
GET  /api/studio/video-projects/{id}                → row (resume/deep-link)
GET  /api/studio/video-projects?account_id=…        → list (home "Resume" chip)
```

### 6.3 `video_director_turn` state machine (yields bare `{type, payload}` like `run_turn`)

```
V0 CONTEXT   Load project row (model_id, target_seconds, aspect, brief, campaign_id,
             current storyboard_json). Load campaign memory when linked:
             pinned_facts + profile + guidelines via campaign_memory loaders
             (same loaders agent.py uses). Emit director_thought("Loaded campaign
             context · 3 pinned facts").
V1 CONSULT   (conditional — §6.4) ONE scoped call to the CAMPAIGN Director:
             stream_agent_response(user_message=<consult brief>, active_role="director",
             campaign_id=…, tool_allowlist=[], model="sonnet",
             proc_key=(turn_id,"consult")) — exactly the _dispatch_specialist shape
             (chat_orchestrator.py:244-255) minus the findings suffix. The consult
             brief asks for: audience, allowed claims (pinned only), tone, LP promise,
             current creative angle, anything to avoid. Emit agent_called /
             agent_progress / agent_result events (same payload shapes as
             chat_orchestrator.py:588-610) so the dock renders it with the existing
             chat components. Result text becomes the CAMPAIGN BRIEF block. Timeout
             90s → degrade: emit director_thought("Campaign Director unavailable —
             drafting from pinned facts only") and continue with raw memory. Consult
             failure NEVER blocks drafting.
V2 DECOMPOSE Reuse prompt_drafter._stage1_decompose (prompt_drafter.py:126) over a
             synthesized page dict {body_excerpt: brief + campaign brief block} —
             the same context-mode trick extract-brief uses (studio.py:644-654).
             → structured brief {subject, setting, value_prop, audience, tone,
             program, hard_constraints, claim_hints}.
V3 CONCEPT   Draft 3 concept angles (problem-led / aspirational / social-proof —
             the non-negotiable scaffold) as LOGLINES ONLY (hook + through-line +
             why-this-angle, ≤60 words each), via one sonnet call with the
             video_director system prompt + visual_director rules + pinned claims.
             Emit {type:"concepts", payload:{variants:[{angle, logline, rationale}]}}.
             PAUSE the turn here? NO — turns must terminate (chat_runner marks rows).
             Instead: initial draft turn ENDS after emitting concepts
             (turn_done). Operator picks an angle (or types their own direction);
             FE calls /draft again with message="angle:aspirational" → next turn
             runs V4 directly. (Iteration turns skip V1-V3 unless the message asks
             to re-consult or restart.)
V4 STORYBOARD Model-aware expansion. Inputs pinned into the prompt:
             - plan_scenes(target_seconds, model_id) → the EXACT scene skeleton
               (count + per-scene duration) the render will use (model_catalog.py:232-277)
             - the model's contract + strengths line (§10.2): "veo3_1: clips are
               exactly 4/6/8s, 16:9 or 9:16, no 1:1; strength: motion realism —
               write self-contained shots, do NOT rely on cross-clip character
               continuity" vs "kling3_0: up to 15s single takes — you may write one
               continuous evolving shot; std mode keeps cost down"
             - VO pacing: duration × 2.5 words = per-scene word budget
             - RULE 0 block (no third-party brands, archetypal subjects, no
               vacation aesthetic — from visual_director.md) + pinned claims
             OUTPUT CONTRACT (forced JSON, one fenced block):
             {"scenes":[{"n":1,"duration":8,"visual_prompt":"…","vo_line":"…",
               "on_screen_text":"…"|null,"continuity":"…"}],
              "vo_full":"…","music_mood":"…","title":"…"}
             Validate server-side: clamp each duration via clamp_duration
             (model_catalog.py:208-229); cap at 8 scenes; scene count may deviate
             ±1 from plan_scenes only by merging/splitting durations that stay legal.
             Persist storyboard_json to the project row (DB = truth), then emit
             {type:"storyboard", payload:{scenes:[…], vo_full, title}}.
V5 WRITEBACK If campaign-linked: append_role_notes(account_id, campaign_id,
             "video_director", <one-para summary + model + target + title>,
             section_title="Storyboard drafted") — same call shape as
             chat_orchestrator.py:722-731. Then turn_done.
```

Cost + render are NOT in the turn: the cost gate and Render button are canvas UI hitting the existing `/api/video-engine/*` endpoints (§3.3). Keeping paid rendering OUT of the LLM turn means a stop/crash in drafting can never burn credits, and the render path stays byte-identical to what's proven.

Iteration turns (`message` non-empty): V0 → (optional V1 if asked) → V4 with the current `storyboard_json` included and the instruction to return the FULL updated JSON (idempotent replace, no patch language). Every turn's storyboard lands in the project row; the canvas re-renders from the `storyboard` event.

### 6.4 Consult — "selected" vs "if needed"

- **Selected:** the rail checkbox (§3.4). Default ON when a campaign is linked, OFF (disabled) when not. Checked → V1 always runs on the initial draft turn.
- **If needed (auto):** when the checkbox is OFF but a campaign IS linked, V1 still auto-fires iff the decomposed brief (V2) produced `claim_hints` that are not covered by the campaign's pinned facts (string-containment check, case-folded) — i.e., the operator's brief is making claims the Director should verify against campaign knowledge. Emit `director_thought("Brief contains unverified claims — consulting the campaign Director")` so the auto-trigger is visible, and the dock shows it. (This ordering means V2 runs before the auto-decided V1 in that path; the state machine handles either order — V1 output is additive context.)
- Unlinked project: no consult, ever; pinned-claims block absent; social-proof angle degrades to composition-only authority exactly as the drafter already does (`studio.py:565-567` comment).

### 6.5 Persistence — `studio_video_projects` (migration V19)

```sql
CREATE TABLE studio_video_projects (
  id TEXT PRIMARY KEY,                -- uuid4
  account_id TEXT NOT NULL,
  campaign_id TEXT,                   -- nullable; set at creation (§6.6)
  conversation_id TEXT NOT NULL,      -- the Director's conversation
  title TEXT DEFAULT '',
  brief TEXT DEFAULT '',
  model_id TEXT NOT NULL,
  target_seconds INTEGER NOT NULL,
  aspect TEXT NOT NULL DEFAULT '16:9',
  consult_director INTEGER NOT NULL DEFAULT 1,
  storyboard_json TEXT,               -- latest full storyboard (source of truth)
  status TEXT NOT NULL DEFAULT 'drafting',  -- drafting|storyboard|rendering|done|abandoned
  asset_id TEXT,                      -- final ad_assets id once rendered
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Why a table and not localStorage: the house rule after the builder-state failure (memory `feedback_builder_frustration.md` — "derive pipeline state from files/rows, not browser state") and the studio invariant (`studio.py:1-25`). Refresh, tab close, or a second machine resumes identically from `GET /video-projects/{id}` + the conversation's persisted turn events.

### 6.6 Conversation binding rule

At `POST /video-projects`, create the conversation via the existing conversations INSERT path with `campaign_id` = the project's link (or NULL). **If the operator changes the campaign link on an existing project:** create a NEW conversation bound to the new campaign, update `conversation_id`, and leave the old conversation intact (history preserved, never rebindes) — enforcing memory `project_conversation_campaign_binding.md`. Surface it honestly in the dock: "Linked to Panama QIV — starting a fresh Director thread for this campaign."

### 6.7 Live-progress UX (dock)

The dock subscribes to `/api/chat/conversations/{cid}/turns/{tid}/stream?cursor=N` (the shipped v2 SSE, `chat.py:542-566`) and renders:

| Event | Dock rendering |
|---|---|
| `director_thought` | quiet muted line with the working dot |
| `agent_called` / `agent_progress` / `agent_result` (the consult) | the existing specialist row component: "Consulting campaign Director…" → collapsible result |
| `concepts` | 3 angle cards (amber/green/blue *identity dots only* per the existing angle convention — `project_visual_director_role.md` — not colored cards); click = pick |
| `storyboard` | canvas populates card-by-card (stagger); dock shows "Storyboard v2 ready — 4 scenes · 30s" |
| `text` (iteration prose) | `.studio-prose` |
| `turn_done` / `turn_stopped` / `turn_error` | composer re-enables; error states inline |

Reconnect: on mount, `GET /turns/active` (`chat.py:522`) → if a turn is running, resubscribe with the last seq; else hydrate the canvas from the project row alone. Stop button → `POST /turns/{id}/stop` (kills the CLI child too, `chat_runner.py:422-455`).

---

## 7. Kinetic Studio — recomposed, not rebuilt

### 7.1 Shape

Full page, three **lanes** as top tabs (recomposing `VideoCreator.tsx`'s cramped strip into a spacious two-column flow):

| Lane | Engine (stated in the tab's subtitle) | Source of truth today |
|---|---|---|
| **Brand Reel** | "fast local render · Pillow + ffmpeg" | `VideoCreator.tsx` brand-reel branch (`:359-428`, form `:809-1028`) |
| **Premium Reel** | "kinetic typography · Hyperframes GSAP" | premium-reel single + Brand Story storyboard branches (`:430-545`, `:776-806`, `:1030-1150+`) |
| **Presenter** | "talking avatar · HeyGen" | avatar-snap branch (`:326-357`, `:670-774`) + `ScriptGenerator.tsx` folded in as its script step |

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ← Studio   KINETIC STUDIO      Brand Reel · Premium Reel · Presenter       │
│            motion graphics & typography — renders locally, no credits      │
├──────────────────────────────────────┬─────────────────────────────────────┤
│  BRIEF                               │  PREVIEW                            │
│  ┌────────────────────────────────┐  │  ┌───────────────────────────────┐  │
│  │ Brief… (or URL below)          │  │  │                               │  │
│  └────────────────────────────────┘  │  │   GREECE GOLDEN VISA          │  │
│  ┌ URL ────────────────┐ [Auto-fill] │  │   EU residency through        │  │
│  └─────────────────────┘             │  │   real estate                 │  │
│                                      │  │                               │  │
│  FIELDS (auto-filled, editable)      │  │   live type preview from the  │  │
│  Headline   [Greece Golden Visa   ]  │  │   fields, real template fonts │  │
│  Subhead    [EU residency…        ]  │  └───────────────────────────────┘  │
│  Stat [EUR 250K] Label [min invest]  │   1920×1080 · 12s · 3 scenes        │
│  CTA        [Book a consultation  ]  │                                     │
│  Voiceover  [……………                ]  │   [Voice ▾] [♪ Music] [15s|30s]    │
│                                      │                                     │
│                                      │   [ Render — ~80s, local ]          │
├──────────────────────────────────────┴─────────────────────────────────────┤
│  (Brand Story sub-lane of Premium Reel keeps its plan → storyboard preview │
│   → render two-phase flow, storyboard cards restyled to match §3.3 cards)  │
└────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Rules for the recomposition

- **Zero backend changes.** All lanes keep their exact endpoints and SSE consumer (`/api/video/generate`, `/api/video/brand-reel`, `/api/video/premium-reel`, `/api/video/premium-reel/storyboard-plan|render`, `consumeStream` at `VideoCreator.tsx:548-595`).
- Extract the logic from `VideoCreator.tsx` into hooks (`useKineticRender`, `useBrandStoryPlan`) + lane components under `frontend/src/components/studio/kinetic/`; delete the old component once nothing imports it (today: only `StudioPage.tsx:22,253`).
- Kill every raw Tailwind color (`pink-500`, `amber-500`, `violet-500`, `emerald-500` throughout `VideoCreator.tsx:618-1028`) → tokens. Verbatim-mode toggle (`:1033-1057`) keeps its lock icon but uses `warning`-token styling.
- The **type preview** panel: render the Headline/Subhead/CTA into a static styled div approximating the mercan-hero template's type stack (font stack + scale from `backend/hyperframes/video-projects/mercan-hero`'s CSS — builder reads the template once and mirrors the core rules). It is a *preview of hierarchy*, not a pixel-perfect GSAP sim — label it "type preview". MVP-optional (§11 story D3).
- Presenter lane: `ScriptGenerator.tsx` (215 L) becomes its Step 1 ("Write the script" → sanitized-spoken preview already exists at `VideoCreator.tsx:242-246, :681-693`), avatar/photo + voice as Step 2, render as Step 3. This retires both hub header buttons (§2.2.5).

---

## 8. Where the old pieces land (explicit dispositions)

| Today | Disposition |
|---|---|
| `StudioPage.tsx` hub | → `StudioHome` (chooser + Library/Souls/Presets tabs). Header keeps credits pill, local-only badge, Back, Upload, Create(image) |
| "Write script" + "New video" hub buttons (`StudioPage.tsx:191-212`) | DELETED from Home; flows live in Kinetic Studio lanes |
| `VideoCreator.tsx` (whole strip) | DISSOLVED into Kinetic Studio lanes; file deleted after re-home |
| StudioPanel `videoSubMode='finished'` (`StudioPanel.tsx:143-149, :665-776`) | KEPT (in-flow hosts may use it) but the HUB stops being its primary home — the AI Video Studio supersedes it there. §12 open call: remove from panel later |
| StudioPanel everything else | UNCHANGED — frozen host contract (§9.2) |
| ModelPicker `<select>` | UNCHANGED for panel hosts; AI Video Studio uses the new gallery on the same `useModelCatalog` hook |
| `ScriptGenerator.tsx` | → Kinetic Presenter lane, Step 1 |
| Library/Souls/Presets components | UNCHANGED, still on Home |
| 15/30/60 presets + `plan_scenes` + cost estimate + music/VO pickers | REUSED as the AI Video Studio rail + cost gate |
| Soul talking-intro toggle (`StudioPanel.tsx:781-826`) | KEPT in panel; AI Video Studio expresses the same capability as a storyboard `soul` scene later (post-MVP; `segments_to_scenes` already supports it, `video_engine.py:152-164`) |

---

## 9. Reuse inventory & zero-regression contract

### 9.1 Survives untouched (backend)

`routers/studio.py` (all endpoints), `model_catalog.py` (one additive field, §10.2), `higgsfield_client.py`, `higgsfield_scene.py`, `video_engine.py` service + router, `premium_reel.py`, `brand_reel.py`, `prompt_drafter.py`, `page_fetcher.py`, soul training path, `routers/video.py` (HeyGen/TTS/stock), `routers/pmax_video.py`, hyperframes kit + templates, `ad_assets` schema (V19 adds a table, alters nothing).

### 9.2 PMax zero-regression list (verify before merge)

PMax composes studio pieces at four seams — all must behave byte-identically:

1. `PMaxWizard.tsx:486-498` — StudioPanel copy mode, host-injected drafter (`onDraftCopy`/`onUseCopy`), slot "Text assets".
2. `PMaxWizard.tsx:1472-1484` — YouTube-thumbnail slot, `onUse` fills the thumbnail.
3. `PMaxWizard.tsx:1894-1904` — per-image-slot panel with `aspect` locked (Lock chip path `StudioPanel.tsx:930-936`).
4. Post-crop preview / aspect-QA flow (approved-brief addendum) — untouched by this plan.

**Frozen contract:** `StudioPanelProps`, `StudioPanelContext`, `StudioPanelPreset` (`StudioPanel.tsx:56-103`) — no renames, no repositioned semantics. AC on every epic: run the PMax wizard through image slot → generate → Use in slot; thumbnail; copy draft. Also protect: `useStudioJobs` API, `/api/studio/models` response shape (additive field only), `/api/video-engine/*` request shapes (only ever *called* by new code).

### 9.3 Deleted

`VideoCreator.tsx` (post re-home), the hub's Write-script/New-video buttons, the hub-side crammed video creation path as the *primary* video entry.

---

## 10. Data & API deltas (complete list)

### 10.1 New

- Migration **V19**: `studio_video_projects` (§6.5).
- `backend/app/services/video_director.py`: `video_director_turn` run_fn + consult + storyboard validation (§6.3).
- Router: video-projects CRUD + `/draft` kickoff (§6.2).
- `roles.py`: `video_director` registration (§5). Optional per-account drafting rules file `data/roles/{account_id}/video_director.md` loaded via the `_load_role_md` pattern (`prompt_drafter.py:290`) — falls back to the registry prompt when absent.
- `agentProfiles.ts`: `video_director` identity entry.
- FE: `StudioHome`, `AIVideoStudio` (+ ModelGallerySheet, StoryboardCanvas, DirectorDock), `KineticStudio` (+3 lanes), `useClipMath` shared hook.

### 10.2 Additive changes

- `model_catalog.py` `_CATALOG` video entries get two fields: `"origin": "Google (US)" | "Kuaishou (CN)" | …` and `"strengths": "<one line>"` (content below); `CatalogModel` (`studio.py:182-197`) gets the two optional fields. This replaces the FE's regex origin-guess (`StudioPanel.tsx:201-205`) — leave the regex as fallback, prefer server value. Strengths copy (verified against the catalog + `reference_higgsfield_cli.md`):
  - veo3_1 / veo3_1_lite: "Motion & physics realism; enum clips 4/6/8s — write self-contained shots"
  - veo3: "Image-to-video only (needs a start image)"
  - kling3_0 / kling2_6: "Continuity king — single takes up to 15s/10s; std mode = cheap"
  - seedance_2_0 / seedance1_5: "Dynamic action & camera movement"
  - minimax_hailuo: "Expressive human performance"
  - wan2_6 / wan2_7: "Budget b-roll; enum 5/10/15s"
  - soul_cast: "Face-consistent presenter (needs a trained Soul)"
  - grok_video: "Fast turnaround, mid quality"
- `App.tsx`: 4 new routes (§2.2.1).

### 10.3 Explicitly NOT changed

`chat_runner.py`, `chat_orchestrator.py`, `agent.py` streaming, `campaign_memory.py`, all render pipelines, StudioPanel, ad_assets.

---

## 11. Phased delivery

**MVP cut = Epics A + B + C** (the fork + AI Video Studio with a working Director). Kinetic ships as a re-homed shell in A, gets its real recomposition in D.

### Epic A — The fork (routing + Home + Kinetic shim) — **2 d**
- **A1 (0.5d)** Routes + StudioRouter split (`App.tsx`, `StudioPage`→`StudioHome`). AC: `/studio` renders Home w/ existing tabs; `/studio/c/:id` still selects the asset; back/refresh stable; PMax untouched.
- **A2 (1d)** Door cards + Home header cleanup (buttons removed, Create(image)→panel kept). AC: three doors, engine identity readable on each, DESIGN.md-clean (no new hues), keyboard focusable.
- **A3 (0.5d)** Kinetic shim: `/studio/kinetic` full-page shell mounting the EXISTING `VideoCreator` (unstyled re-home, temporary). AC: all three legacy modes render end-to-end from the new page; hub buttons gone.

### Epic B — AI Video Studio workspace (no Director yet) — **3 d**
- **B1 (1d)** Page scaffold: rail (campaign link, length presets, aspect, audio ports from StudioPanel), canvas empty state, collapsed dock placeholder. AC: layout at 1280-1680px; rail state persists per project draft (local until B3).
- **B2 (1d)** Model gallery sheet + catalog `origin`/`strengths` fields + `useClipMath`. AC: 12 cards grouped by tier, live clip math per card, selection clamps durations; `<select>` hosts unaffected; `/api/studio/models` backward-compatible.
- **B3 (1d)** Storyboard canvas (manual mode): add/edit/reorder scene cards, cost gate wired to `/api/video-engine/estimate`, Render wired to `/render` + job poll + progress strip + asset landing. V19 table + project CRUD (create/save/resume; `/studio/ai-video/:projectId`). AC: a hand-written 30s/veo3_1_lite storyboard renders to one MP4 in the library, campaign-tagged; refresh mid-edit loses nothing; cached-clip re-render prices 0.

### Epic C — The Video Director — **4 d**
- **C1 (0.5d)** `video_director` role registration + `agentProfiles` entry + system-prompt contract (word budgets, RULE 0, JSON contract). AC: role listed in `/api/chat/roles`; override file editable.
- **C2 (1.5d)** `video_director_turn` V0/V2/V3/V4/V5 (no consult yet) + `/draft` endpoint + storyboard server-side validation (clamp_duration, ≤8 scenes) + project-row persistence. AC: brief → concepts event → pick angle → storyboard event, scenes legal for the selected model (Veo enum snap + Kling int cap verified in tests); turn events replay after backend restart.
- **C3 (1d)** Consult (V1): scoped campaign-Director call + toggle + auto-trigger rule + degrade path + conversation-binding rule (§6.6). AC: linked project consult produces a campaign-brief block visible in the dock; unlinked drafts skip it; consult timeout doesn't kill drafting; changing campaign link spawns a fresh conversation.
- **C4 (1d)** Director dock UI: SSE subscribe/reconnect/stop, concept cards, streaming prose, storyboard populate animation, iteration composer. AC: no blind spinner anywhere; kill backend mid-draft → reconnect replays cleanly; Stop works.

### Epic D — Kinetic Studio recomposition — **2.5 d**
- **D1 (1d)** Extract hooks + lane components; Brand Reel + Premium Reel(single) two-column layout; token-clean. AC: renders byte-identical params to the legacy calls (compare request payloads).
- **D2 (1d)** Brand Story lane: plan→storyboard-preview→render restyled to §3.3 card language (incl. image swap modals). Presenter lane w/ ScriptGenerator folded in. Delete `VideoCreator.tsx`. AC: full Brand Story e2e; script→avatar e2e; `grep VideoCreator` returns nothing.
- **D3 (0.5d)** Type-preview panel (hero-template type stack). AC: preview updates live from fields; honest "type preview" label.

### Epic E — Polish + regression sweep — **1 d**
- Home resume chips, `/studio#souls` deep links from the studios, empty/error states pass, PMax §9.2 checklist run, `/impeccable` visual pass, feature-log rows + memory writeback.

**Total ≈ 12.5 d · MVP (A+B+C) ≈ 9 d.**

---

## 12. Risks

1. **Chat v2 epics 4-8 are still in flight** (`research/chat-orchestration-v2-plan.md:455-476`). The Director rides ONLY shipped Epic-1/2 primitives (`chat_runner.start/subscribe/stop`, `stream_agent_response`, the event envelope). **Deferred until after Chat v2 E4-E8:** claim-gating VO scripts (E4's hard gate should eventually vet vo_full), registering video_director as a plannable specialist inside `run_turn` orchestrations, and any smart-memory writeback beyond the single `append_role_notes` call (E5 owns that surface). If E4-E8 land mid-build, do NOT chase their APIs — the pinned seam is the four functions above.
2. **Drafting cost/latency.** V1+V2+V3 ≈ 3 sonnet calls (~35-60s worst case with consult). Mitigate: concepts are loglines not full storyboards; consult capped at 90s; everything streams so waiting feels alive. Paid rendering is outside the turn by design (§6.3) — a runaway draft can never burn Higgsfield credits.
3. **Model-contract drift** (new Higgsfield models / changed enums). All legality flows through `clamp_duration`/`plan_scenes` server-side + storyboard validation in C2; the Director's prompt *describes* the contract but the validator *enforces* it — a hallucinated 12s Veo scene gets snapped to 8s with a visible warning chip on the card, mirroring the CLI-reject-proofing philosophy of the catalog (`model_catalog.py:1-18`).
4. **In-memory render jobs** (`routers/video_engine.py:20-22`): a backend restart mid-render orphans the job *view* (the asset may still land via the pipeline's own recording). Acceptable for now — it's the pre-existing tradeoff; the P3 DB-row job state is the fix and is out of scope here. The canvas handles a 404 poll with "job lost — check the Library" (same honest copy as `StudioPanel.tsx:504`).
5. **Two components own clip math** (canvas + gallery). Mitigated by the single `useClipMath` hook (B2) — do not let a second mirror of `plan_scenes` appear.
6. **Scope creep into StudioPanel.** The panel is frozen (§9.2). Any "while we're here" panel edits are rejected in review.

---

## 13. Open design calls for Wassim

1. **Presenter (Avatar Snap) placement** — planned as Kinetic's third lane (it's a form→deterministic-render tool sharing voice/music pickers). Alternative: its own fourth door. Plan assumes Kinetic lane.
2. **Image Studio depth** — v1 door opens the existing panel (§2.4). OK, or do you want a full image workspace (variant grid, compare, Soul gallery) in this pass?
3. **Consult default** — ON when campaign-linked (plan's assumption). Flip to OFF+auto-trigger-only if consults feel slow.
4. **Concept step** — 3 angle loglines before the full storyboard (one extra click, better creative control, cheaper iteration). Alternative: straight-to-storyboard with angle as a rail setting. Plan assumes the concept step for the initial draft only.
5. **StudioPanel "Finished video" sub-mode** — retire it from the panel once the AI Video Studio ships (it exists only because there was nowhere better), or keep for in-flow hosts? Plan keeps it untouched this pass.
6. **Souls/Presets residency** — staying as Home tabs (plan). Alternative: fold Presets into the AI Video/Image studios as a "concept starters" shelf.

---

## Appendix A — new turn-event types (additive to the v2 envelope)

| type | payload | emitted by |
|---|---|---|
| `concepts` | `{variants:[{angle, logline, rationale}]}` | V3 |
| `storyboard` | `{project_id, version, scenes:[{n,duration,visual_prompt,vo_line,on_screen_text,continuity,model?}], vo_full, music_mood, title}` | V4 |
| (reused) `director_thought`, `agent_called/progress/result`, `text`, `turn_done/stopped/error` | as in `chat_orchestrator.py` | V0-V5 |

Envelope, seq, persistence, replay: unchanged (`chat_runner.py:218-296`). FE treats unknown event types as no-ops (forward-compatible).

## Appendix B — storyboard → render mapping

`storyboard_json.scenes[]` → `POST /api/video-engine/render` body:
`segments = scenes.map(s => ({engine:"higgsfield", prompt:s.visual_prompt, model:s.model ?? project.model_id, duration:s.duration, speak: syncPerScene ? s.vo_line : ""}))`; whole-track VO alternative: `voiceover_script = vo_full` + `voice_id` (the dispatcher then disables per-scene sync itself, `video_engine.py:514-520`). `aspect`, `music_filename`, `quality:'draft'`, `account_id`, `campaign_id` as today. Estimate uses the same scene list via the router's `scenes` branch (`routers/video_engine.py:66-68`).
