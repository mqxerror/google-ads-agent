---
date: 2026-04-29
type: feature
title: Brand Story — N-scene Premium Reels with image storyboarding
tags: [studio, video, brand]
---

The 12-second Premium Reel was just round one. Now there's a **Brand Story** sub-mode inside Premium Reel that builds long-form (~30/60/90s) cinematic videos from your library images.

### How it works

1. Toggle into **Premium Reel** → **Brand Story** sub-tab.
2. Type a brief (or paste a URL — the Director reads the page for real claims).
3. Click **"Pick library images for b-roll"** — multi-select grid of your uploaded photos.
4. Set target duration (30 / 60 / 90s).
5. Hit **Generate Brand Story**.

The Director (Claude) writes a complete N-scene storyboard:
- 1 hero scene (kinetic blur-in headline)
- M b-roll scenes (one per image you picked — Director assigns each image to a scene by analyzing the filename)
- 1-3 stat scenes (real numbers from your campaign context, not invented)
- 1 CTA lock-up

Then each scene renders in parallel via Hyperframes (2 Chrome workers at once to balance speed vs RAM), and ffmpeg stitches them with crossfades + final fade-to-black.

### What you get

A 60-second Brand Story for Mercan with 8 hotel photos produces about **13 scenes**:
- Cinematic hero with per-word blur reveal
- 8 b-roll scenes — each with one of your hotel images doing slow Ken-Burns + caption blur-in word-by-word + scene-label tag (e.g. "Évora, Portugal")
- 3 stat scenes — "37 years", "4,100+ families", "26 hotel projects" (verified from campaign memory)
- Final CTA scene with gold border drawing top→right→bottom→left, text scaling in

Total render time: 2-4 minutes (storyboard call ~30s + N parallel scene renders ~60-150s + stitch ~10s).

### B-roll template (new)

Author'd `mercan-broll` Hyperframes template with:
- Local image background, slow Ken-Burns zoom (1.04 → 1.12 over 5s)
- Bottom darkening gradient that fades in over 0.7s for legibility
- Optional gold left accent strip that drops down
- Caption with **per-word blur reveal stagger** (same kinetic style as the hero)
- Optional small uppercase scene-label in the upper-left ("Athens, Greece" / "Évora, Portugal")

### Image handling — local only, never uploaded

Selected library images are **copied into each scene's `assets/` folder** during render and Hyperframes resolves them as `assets/<filename>`. No HTTP roundtrip, no cloud upload, no third-party API touches them. Matches the "🔒 local only" promise.

### What's still missing
- Image vision (Claude actually *seeing* the photo, not just the filename) — would let it write more precise captions per image. Phase B+ via Anthropic vision API.
- Custom music bed (currently just optional ElevenLabs voice). Phase B+.
- Vertical 9:16 templates for Shorts. Phase B+.
