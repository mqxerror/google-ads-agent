---
date: 2026-04-29
type: feature
title: Premium Reel — kinetic typography via Hyperframes (HTML+GSAP)
tags: [studio, video, brand]
---

A new third Studio mode — **Premium Reel** — sits alongside Avatar Snap (talking head) and Brand Reel (fast/local). Premium uses [Hyperframes](https://hyperframes.heygen.com) (HTML+GSAP+headless Chrome) to render true cinematic motion graphics, the kind Slider Revolution / Anthropic's Claude-Design videos look like.

### What's different from Brand Reel
| | Brand Reel | Premium Reel |
|---|---|---|
| Renderer | Pillow + ffmpeg overlays | Hyperframes (HTML+GSAP+Chromium) |
| Text reveal | Slide+fade per element | **Per-letter blur-in, counter ticks, gold-border draws sequentially** |
| Render time | ~10s | ~80s (3 scenes × ~25s each + stitch) |
| Cost | $0 (fully local) | $0 (fully local) |
| Aspects | 16:9 / 9:16 / 1:1 | 1920×1080 only (v1) |
| Duration | 15 / 30s | 12s (3 scenes × 4s) |
| B-roll | Yes (image picker) | No (pure motion graphics, v1) |

### Three scene templates (HTML + GSAP)
- **Hero** — words blur-in staggered (~0.085s between each), gold underline draws from center, tagline rises last
- **Stat** — number ticks from 0 to target with eased curve ("EUR 0K → EUR 250K" over 1.4s), white underline draws, label rises
- **CTA** — gold border draws around the box top→right→bottom→left in sequence (the Slider Revolution lock-up signature), CTA text scales in with bounce, brand mark + tagline rise after

All three templates live under `backend/hyperframes/video-projects/mercan-{hero,stat,cta}/`.

### How to use
Open Studio → 🎬 Video → click the new **Premium Reel** tab (third one, violet). Same form as Brand Reel — auto-fill from a brief or URL still works the same. Hit **Render Premium**. Wait ~80 seconds. Get back a **dramatically more polished MP4**.

### When to use which
- **Avatar Snap** — when you want a face talking. Costs HeyGen+ElevenLabs API calls.
- **Brand Reel** — fast iteration, want to see 5 angles in a minute, test b-roll choices.
- **Premium Reel** — the final ad you actually run.

### Setup notes (one-time)
- Cloned `nateherkai/hyperframes-student-kit` into `backend/hyperframes/`
- `npm install` (3 packages, < 30s)
- The Hyperframes CLI auto-installs via `npx -y hyperframes` on first run
- Requires Node 20+ (already on machine), system Chrome (already on machine), ffmpeg (already on machine)
- `node_modules` and `renders/` are gitignored

### What's still missing
- B-roll mode for Premium Reel (text-only in v1 — Brand Reel still wins for photo-driven scenes)
- Vertical 9:16 / square 1:1 aspect templates
- More than 3 scenes (the Pillow Brand Reel has 4 with B-roll)

These are good Phase B+ follow-ups. The 3-scene Premium Reel ships today and produces output the user described as **"crazy beautiful"** in early review.
