---
date: 2026-04-22
type: improvement
title: Studio script handling, longer renders, campaign context
tags: [studio, video, agent-quality]
---

Studio quality-of-life pass after the first few real renders.

- **Pasted scripts no longer get spoken with their labels.** When you paste a structured block from the Script Generator (HOOK / SCRIPT / CTA / B-ROLL NOTES), the system now extracts only the spoken lines. A green "Will speak: ..." preview shows you exactly what goes to the voice before you commit to a render.
- **Longer videos won't time out.** Bumped the HeyGen wait from 5 to 10 minutes, and the UI now streams live status updates ("processing — 45s elapsed") instead of going silent.
- **Inline Script Generator in Studio.** No more chat → copy → paste. Click "Write script" inside Studio: pick brief + length (6/15/30/60s) + variant count, get back ready-to-render variants with a "Use for video" button on each.
- **Campaign context selector.** Pick a campaign at the top of Studio and (a) the asset library filters to that campaign's work, (b) the Script Generator pulls in that campaign's pinned facts and brand rules so generated scripts respect them.
