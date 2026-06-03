---
stepsCompleted: [1, 2]
inputDocuments: []
session_topic: 'Studio v2 — local-first cinematic video ad generation pipeline'
session_goals: 'Generate Anthropic-Claude-Design-quality animated slideshow + avatar video ads quickly, from a one-line idea or a campaign-context handoff. Combine Opus 4.7 (1M context, local CLI) creative direction with Hyperframes for HTML→MP4 animation, HeyGen for avatars (incl. picture-based), and local pro-grade image editing.'
selected_approach: 'ai-recommended'
techniques_used: ['What If Scenarios', 'SCAMPER Method', 'Concept Blending']
ideas_generated: []
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Mqxerrormac16
**Date:** 2026-04-28

## Session Overview

**Topic:** Studio v2 — local-first cinematic video ad generation pipeline

**Goals:**
- Beautiful, well-animated slideshow ad videos at the **Anthropic Claude-Design quality bar**
- Use **Hyperframes** (HTML → MP4 via headless Chrome + ffmpeg) for motion graphics
- **HeyGen** for avatars — both stock catalogue and **picture-based** ("turn this photo into a talking avatar")
- **Smart avatar creation** — auto-style, brand-consistent, fast
- **Local pro-grade image editing** when needed (no cloud round-trips, privacy-friendly)
- One mechanism that takes **idea OR campaign context** → finished video quickly
- Leverage **Opus 4.7 1M context** local CLI for the creative direction (storyboarding, copy, motion timing, scene planning)
- Library / tooling — Python or any — that fits this stack

### Session Setup
Topic + goals consolidated from user's opening message. Outcome bar is "amazing like the Anthropic Claude Design slideshow video about Claude". Ready to pick a technique approach.

---

## Decision (2026-04-29)

User course-corrected mid-session away from platform sprawl: **"i need a fast creative eye catching video tools from an avatar or just brand video demo"**. Brainstorming converged on **two focused Studio modes**, both behind a single toggle in the existing Video Creator panel:

### Tool 1 — Avatar Snap
Photo + one-line idea/campaign → HeyGen photo-avatar talking head + ElevenLabs voice + brand-end-card overlay. ~15s output, ~80s render.

### Tool 2 — Brand Reel
One-line idea/campaign (no avatar) → 15-30s motion-graphics reel using Mercan brand palette (`#013160` navy, `#c9a84c` gold) and hotel B-roll. Pure Pillow + ffmpeg, fully local, $0 per draft. Optional ElevenLabs VO.

### Build size
- Avatar Snap: ~1 day (extends existing Video Creator)
- Brand Reel: ~2 days (net-new local renderer)
- Total: ~3 working days

### Tech choice
Brand Reel uses **Pillow + ffmpeg** (already in the dep tree) instead of Hyperframes — same cinematic output via ffmpeg `zoompan` (Ken Burns), `xfade` (crossfades), and Pillow-rendered text layers. Avoids installing Node 20+ / headless Chrome / Hyperframes CLI. Fully local.

### Ideas captured (21 in dialogue, 7 retained for Tool 1/2)
Workflow #1, #2, #3 (gallery, regenerate-knob, trash-can = signal) → punted to Studio v3.
Cost #10, #11 (local-only draft, cost preview chip) → Brand Reel embodies #10; #11 is a small UI add.
Format #7 (one render → four cuts) → punted to Studio v3.
Distribution #16-18 → punted to Studio v3.
Local image edit #19, #21 → punted (background removal lives in a future "Asset Prep" tool).
WI-22 to WI-26 → discarded as out-of-scope.

Final scope = the two tools above, nothing more.

