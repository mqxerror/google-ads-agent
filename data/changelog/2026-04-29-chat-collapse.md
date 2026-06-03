---
date: 2026-04-29
type: improvement
title: Hide / collapse the chat panel
tags: [chat, dx]
---

The chat panel now has a **hide** button (the panel-with-arrow icon at the top-left of the chat toolbar). Click it and the chat collapses to a thin 32-px strip on the right edge of the screen with a chevron-back button — click that to bring it back.

State persists across reloads (`localStorage.chatPanelCollapsed`), so if you usually work without the chat (e.g. in Studio), you stay collapsed.

Full-screen still wins — when chat is full-screen, the hide button isn't shown. Esc out of full-screen first if you want to collapse.
