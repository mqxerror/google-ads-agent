# Plan — Hyperframes "Premium Reel" mode (Phase B)

**Status:** scoping only, not started.
**Predecessor:** the Pillow + ffmpeg "Brand Reel" already ships (2026-04-29). This plan is the next-level upgrade, kept separate so it can land without breaking the fast/free path.

---

## Why a third mode

The Pillow Brand Reel is fast (~5-10 s renders, $0 per draft), but its motion vocabulary is limited to ffmpeg `zoompan` (Ken Burns) + `fade` (alpha in/out). Real cinematic ad polish — what Nate Herkelrath demoes on YouTube using Hyperframes — needs:

- **Per-letter / per-word kinetic typography** (text typing in, masking, gradient sweeps, blur reveal)
- **Web fonts** (paid display fonts, custom weights) instead of system Arial fallbacks
- **CSS effects** real designers use: gradient text, drop shadows that don't bake into a PNG, glow, masking
- **GSAP timelines** for orchestrated multi-element animations (logo lock-up that builds, stat counter that ticks up, hotel image with parallax overlay)

These aren't possible in Pillow without rendering hundreds of frames per scene (which kills the "$0 per draft" promise).

---

## Architecture

A third Studio mode that lives next to Avatar Snap and Brand Reel:

```
Video Creator
├── Avatar Snap   (HeyGen + ElevenLabs, talking head)
├── Brand Reel    (Pillow + ffmpeg, fast/free, current)
└── Premium Reel  (Hyperframes + headless Chrome + ffmpeg, NEW)
```

Premium Reel produces the same MP4 output shape (16:9 / 9:16 / 1:1, registers in `ad_assets`) but uses Hyperframes for the actual rendering. The Brand Reel's auto-fill scene generator is **fully reused** — Hyperframes consumes the same `{headline, subhead, stat_value, stat_label, cta, voiceover_script}` JSON.

---

## Stack additions

| Component | Purpose | Install |
|---|---|---|
| Node 20+ | Hyperframes CLI runtime | `nvm install 20` |
| `hyperframes-student-kit` (clone from `nateherkai/hyperframes-student-kit`) | Project scaffold + 12 reference templates | `git clone` into `backend/hyperframes/` |
| `npx hyperframes` CLI | Preview + render | comes with kit |
| Headless Chromium | Renders HTML to frames | already pulled by Hyperframes |
| ffmpeg | Stitches frames + audio | already installed |
| Google Fonts (Inter, Playfair, Plus Jakarta Sans) | Display typography | downloaded once into `backend/hyperframes/assets/fonts/` |

Disk: ~5 GB for Chromium + node_modules. RAM: 16 GB recommended for smooth Chromium render at 1920×1080.

---

## Templates to ship

Three scene templates, each a Hyperframes `index.html` with a paused GSAP timeline at `window.__timelines`:

1. **Hero kinetic** — letters of the headline reveal one-by-one with a blur-to-sharp transition, gold underline draws in, tagline fades up
2. **Stat counter** — the stat number ticks from 0 → target value (e.g. 0 → 26) over 1.2 s with easing, label fades up after, gold accent line draws across
3. **CTA lock-up** — gold border draws around the CTA from top-left, text scales in with subtle bounce, MERCAN GROUP + tagline fade up beneath, final 0.8 s hold before fade-to-black

The B-roll scene reuses the existing Pillow renderer (it's just a photo with overlaid text — no kinetic typography needed there).

---

## Phased build

| Phase | Scope | Effort |
|---|---|---|
| **B0** Install + smoke test | Clone the student kit, render the bundled "claude-edit-intro" template to verify the full Chromium → MP4 chain works on this machine. | ~2 hr |
| **B1** Hero kinetic template | Author the HTML+GSAP for the hero scene. Wire it to accept `{headline, tagline}` via Hyperframes data injection. Render to standalone MP4. | ~half day |
| **B2** Stat counter + CTA templates | Same pattern, two more templates. | ~half day |
| **B3** Backend wiring | New service `premium_reel.py` that calls `npx hyperframes render` per scene with the auto-filled JSON, then uses the existing `_stitch` to combine. New endpoint `POST /api/video/premium-reel` (SSE stream, same shape as `/brand-reel`). | ~1 day |
| **B4** Studio mode toggle | Add "Premium Reel" as a third tab in the existing Avatar Snap / Brand Reel toggle. Reuse the auto-fill row. | ~half day |
| **B5** Polish | Per-template variations (3 styles per scene so output isn't repetitive), font preloading, error handling for Chromium crashes. | ~half day |

Total: ~3-4 working days.

---

## What NOT to do

- **Don't replace Brand Reel.** The Pillow path stays as the fast/free draft mode. Premium Reel is the polished output mode you switch to once you've nailed the angle. Same auto-fill, two render targets.
- **Don't run Chromium per frame.** Hyperframes already does the optimal thing — paused GSAP timeline, headless Chrome screenshots at fps intervals. Don't reinvent it.
- **Don't make it a separate app.** It lives in the existing Studio Video Creator, behind the same mode toggle.

---

## Open question

**Where do the templates live?** Two options:

- **A) Vendored in repo** under `backend/hyperframes/templates/*.html` — ships with the codebase, version-controlled, reproducible. Larger repo, but every developer/clone gets the same look.
- **B) Per-account in `data/hyperframes/<account_id>/`** — each client account can customize their templates, agency white-label friendly later. Smaller repo. But requires a "seed templates" step on first use.

**Recommend A** for v1. Move to B only when there's a real white-label demand.

---

## Reuse (zero rewrite of existing code)

- Brand Reel's `generate_scenes()` JSON output is the input format Premium Reel consumes — no new prompt, no new role.
- The Studio mode toggle UI just gets a third tab.
- The `ad_assets` library already supports the resulting MP4s — no schema change.
- Existing Avatar Snap + Brand Reel paths stay untouched and continue working.
