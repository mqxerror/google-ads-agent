# Studio Redesign — Design Brief (impeccable shape, confirmed by Wassim 2026-06-11)

## 1. Feature summary
Turn Studio from a complicated standalone page into a **creative engine with one
shared embedded panel**: Generate image / Create video / Draft copy open the same
Studio panel *in context* (PMax wizard first), output lands directly in that
flow's slot. The Studio page slims into a calm hub: **Asset Library + Soul
Creator + Presets**. Pass 1 = shared panel + library redesign + PMax wired.

## 2. Primary user action
From inside a campaign flow: click one button, get a usable on-brand asset into
the slot you're filling — without understanding models, params, or Studio's
internals. On the hub: find an asset fast; create/manage a Soul simply.

## 3. Design direction
- Register: **product**. Color strategy: **Restrained** (DESIGN.md tokens; kill
  the pink/amber/emerald sprawl in VideoCreator/Studio remnants).
- Scene: an agency operator mid-campaign-build in daylight needs one image in
  the right aspect *now* — the panel must feel like a calm assistant, not a lab.
- Anchors: Linear's command-palette economy · Figma's asset panel ·
  the app's own chat panel (quiet rows, studio-prose).

## 4. Scope (pass 1)
Production-ready. (a) `StudioPanel` shared component (modes: image / video /
copy) embeddable with `context` prop {campaignId, brief, businessName, slot,
aspect}; (b) Asset Library redesign; (c) **Soul Creator** flow; (d) PMax wizard
swaps its ad-hoc generate/library UIs for StudioPanel. Passes 2+: Search ads,
Shopping, chat, full video-engine P1 (model picker lands inside StudioPanel).

## 5. Layout strategy
- **Panel** (slide-over, right, 480px like chat): top = intent input (one
  prompt field + "Enhance (Visual Director)"), middle = results grid as they
  stream, bottom = quiet controls (model picker w/ live cost, aspect locked
  from context, Soul toggle). One primary action. Progressive disclosure —
  advanced params behind one "Tune" disclosure, never a wall of knobs.
- **Library (hub)**: filter rail (type · campaign · model · date) + dense
  quiet grid; metadata on hover/expand (prompt, model, cost, created); select-
  to-use / compare; relative times; search.
- **Soul Creator (hub)**: guided 3-step card — upload 5-10 face refs →
  name + train (progress states) → "ready" gallery w/ test-generate. Status
  chips reuse plan-state dots (training=pulse, ready=success, failed=danger).

## 6. Key states
Panel: idle (context-aware placeholder) · enhancing · generating (per-item
skeletons + cost ticking) · partial results · error-with-retry (per item) ·
empty-credits (link to top-up). Library: loading skeletons · empty ("generate
your first asset") · filtered-empty. Soul: untrained · uploading · training
(ETA) · ready · failed (reason + retry).

## 7. Interaction model
Click [Generate image] in any flow → panel slides over with context preloaded →
type idea → Enhance (optional) → Generate → click a result → "Use in slot" →
panel closes, slot filled, asset saved w/ campaign tag. Library: click asset →
expand detail → Use / Download / Delete. All jobs poll (no long requests);
panel survives close/reopen (job continues, badge on reopen).

## 8. Content requirements
Plain-language labels (no model jargon up front: "Best quality / Fast / Budget"
tiers mapping to models, real names in Tune). Empty/error copy per state.
Costs always visible before generate. No em dashes.

## 9. Open questions for build
- Slide-over vs inline expansion inside narrow wizard steps (panel must adapt).
- Library virtualization threshold (asset count is growing).
- Soul training cost/time surfacing (verify from higgsfield CLI before promising).

## BMAD
Becomes **Epic 12: Studio Engine** (pass 1 stories: 12.1 StudioPanel core,
12.2 Library redesign, 12.3 Soul Creator, 12.4 PMax integration) — pending
Wassim's brief confirmation; video-engine plan (Epic 11) P1 folds its model
picker INTO StudioPanel rather than shipping separately.

## Addendum (Wassim, 2026-06-11) — Creative QA gate before submit
Server-side auto-crop (added for ASPECT_RATIO_NOT_ALLOWED) can destroy text
baked into images. REQUIREMENT for Epic 12 / immediate next: the wizard's
Images/Review step must show each image AS GOOGLE WILL RECEIVE IT (post-crop
preview, mismatches flagged), and Studio's generators should produce at the
slot's exact aspect by default. Stretch: text-safe-margin warning when text
sits in the crop zone. No silent cropping at submit.

## APPROVED (Wassim, 2026-06-11) — build authorized, one shot
Epic 12 pass-1 + Epic 11 P1 (model catalog + higgsfield scenes) folded in.
**Strategic note:** if the result is good, Studio may become a STANDALONE
product for all social media — so StudioPanel + engine must stay cleanly
decoupled from Google-Ads-specific code (context prop is the only coupling;
no google_ads imports in the studio service layer).
