---
date: 2026-04-20
type: feature
title: Video ad pipeline — first end-to-end render
tags: [video, agent-quality]
---

First working video ad pipeline. Type a script, pick an avatar + voice, get back a downloadable MP4 in about a minute.

- ElevenLabs generates the voice (21 premade voices to choose from, default: Sarah).
- HeyGen takes that audio and renders a talking-head avatar (1281 stock avatars to choose from).
- The result plays inline in chat with download / copy.
- New `Video Script Generator` specialist role tuned for spoken pace at 6 / 15 / 30 / 60 seconds — ask the team to draft a script, then drop it into the renderer.

Mercan's HeyGen + ElevenLabs accounts are wired in. Per-client account credentials will come later if needed.
