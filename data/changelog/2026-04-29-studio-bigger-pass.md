---
date: 2026-04-29
type: feature
title: Studio — uploaded vs AI library, b-roll picker, URL-to-scenes, no-campaign mode
tags: [studio, video, brand]
---

Four asks, all addressed in one pass.

### 1 · Library: uploaded vs AI-generated split
The asset library now has a **second filter row** alongside the type tabs. Three options: **All sources / Uploaded / AI-generated**. Uploaded gets a green pill, AI-generated gets pink so you can spot the difference at a glance. The schema already tracked `source` per asset — just exposed it.

### 2 · Brand Reel: pick your own b-roll image
Replaced the hardcoded "Mercan generic / Greece / Portugal / Panama" dropdown with a real **Pick b-roll** button that opens a grid of your uploaded images. Click one → it gets baked into Scene 2 as the background, with the existing dark-bottom overlay for text legibility. The system reads the image **directly from disk** (`/api/assets/file/...`) — no internal HTTP roundtrip, no cloud, fully local.

When no image is picked the brand-color gradient still renders. So nothing breaks if you skip it.

### 3 · URL → scenes auto-fill
The auto-fill row has a new **second line for a URL**. Drop a landing-page link (e.g. `https://www.mercan.com/greece-golden-visa/`) and the system:
- Fetches the page
- Strips HTML to plain text (~8 KB cap to stay snappy)
- Feeds it as **SOURCE PAGE** context to the scene generator
- Anchors copy in **real claims from your page** — verifiable stats only, no inventions

Tested live with the Mercan Greece GV page → produced "3% Annual Return Guaranteed" + "26 Schengen Nations" pulled straight from the page. Works in 5-10s.

### 4 · Branded video without ever creating a campaign
The auto-fill button is no longer disabled when no campaign is selected. The **Mercan brand rules** (palette, no third-party brand names, no eligibility language, HNW framing, program-specific positioning for Greece/Portugal/Panama/EB-3/Canada) live in the system prompt and apply **regardless of campaign**.

So you can now: type a URL **or** a brief, hit **Auto-fill scenes**, then **Render Reel** — and ship a fully branded video without touching any campaign settings.

### How the new flow looks
```
✨  [ Brief — optional if a URL is set                    ]  [Auto-fill scenes]
🔗  [ Optional URL — landing page or article              ]                 [×]
```
URL takes precedence — when both are set the agent reads the page first and uses the brief as steering.
