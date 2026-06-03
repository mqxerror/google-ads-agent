---
date: 2026-04-29
type: improvement
title: Brand Reel — staggered per-element animations (Slider Revolution-style)
tags: [studio, video, brand]
---

The Brand Reel no longer feels like PowerPoint. **Each element now animates in on its own timeline** instead of the whole scene appearing at once.

### What changed
Each scene was a single static PNG before. Now it's a **base PNG + N animated layers**, each with its own appearance time and motion (slide-in / fade-in / both). Concretely:

**Hero (Scene 1)**
- 0.20s · brand mark slides down + fades in (top-left)
- 0.50s · headline slides in from the left
- 1.20s · gold underline fades in beneath the headline
- 1.55s · tagline rises up + fades in

**B-roll (Scene 2)**
- 0.20s · dark bottom-half overlay fades in
- 0.50s · gold left accent strip slides down
- 0.85s · subhead slides in from the left over the (still Ken-Burning) photo

**Stat (Scene 3)**
- 0.25s · big stat number rises up + fades in
- 0.95s · white underline fades in
- 1.25s · stat label rises up + fades in

**CTA (Scene 4)**
- 0.30s · gold border box fades in (empty)
- 0.85s · CTA text slides up into the box
- 1.45s · brand mark rises beneath
- 1.75s · tagline fades in last

### Under the hood
Each scene now declares a list of `Layer`s (transparent PNGs with position, appearance time, animation type). The ffmpeg filter graph chains overlays with time-based `enable` and `x`/`y` expressions for the slide motion, plus per-layer alpha fades. The Ken-Burns motion on the B-roll background still runs continuously underneath the layered overlays.

### What's still PowerPoint-ish
Per-letter / per-word kinetic typography (text writing itself out, blur-to-sharp letter reveals) needs HTML+GSAP — see the **Hyperframes Premium Reel** plan in `research/hyperframes_premium_reel_plan.md` for that. The current per-element approach is the right step in between, and ships today without adding Node + Chromium to the stack.

Test render: 535 KB / 13.2s / 1920×1080 with the same content as before — no regression in size or speed.
