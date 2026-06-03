---
date: 2026-04-29
type: feature
title: Studio v2 — Avatar Snap + Brand Reel modes
tags: [studio, video, brand]
---

The Studio Video Creator now has **two modes**, picked from a toggle at the top.

### Avatar Snap *(talking head)*
The existing pipeline plus a new **"Use a photo as avatar"** button. Drop any face photo (JPG/PNG/WebP, ≤12 MB) and the system uploads it to HeyGen as a *talking_photo* — your render uses that face instead of a stock catalogue avatar. The stock-avatar dropdown auto-hides when a photo is loaded.

Use this when you want the founder, a team member, or a stock face to deliver a script.

### Brand Reel *(no avatar · fully local)*
A new mode for fast, eye-catching motion-graphics ads with **no HeyGen call** — fully local Pillow + ffmpeg pipeline. Form is one-line per scene:

- Headline (Scene 1 · hero on navy with gold accent)
- Subhead (Scene 2 · overlay on B-roll or brand gradient)
- Stat + label (Scene 3 · big gold number reveal — "EUR 250K" / "minimum investment")
- CTA (Scene 4 · gold-framed call-to-action with MERCAN GROUP brand mark)
- Optional voiceover script (uses ElevenLabs if filled in, silent otherwise)

Choose 15s or 30s, pick aspect (16:9 / 9:16 / 1:1), pick a B-roll source pack (Mercan generic / Greece / Portugal / Panama — gradient fallback if no image), hit **Render Reel**. Renders in 5-10 seconds. Costs $0 unless you turn on voiceover.

Outputs are 1920×1080 H.264 MP4 (or 1080×1920 vertical), saved to your Studio library with an "AI" badge — same shelf as HeyGen renders.

### Why two modes
Some ads need a face. Some don't. Brand Reel lets you experiment for free until you've nailed the angle, *then* spend the HeyGen budget on the avatar version.

### Under the hood
- New backend service `brand_reel.py` — Pillow renders 4 PNG scenes, ffmpeg stitches with Ken-Burns zoompan + xfade crossfades, optional ElevenLabs VO mixed in
- New endpoint `POST /api/video/brand-reel` (SSE stream)
- New endpoint `POST /api/video/talking-photo` (file upload → HeyGen talking_photo_id)
- `VideoRequest.character_type` distinguishes stock-avatar vs talking-photo flows
- Tested end-to-end: 16:9 → 458 KB / 13.2 s render, 9:16 → 285 KB. Pillow + ffmpeg already on the system.
