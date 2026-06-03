---
date: 2026-04-13
type: improvement
title: Smart memory — relevance-based context selection
tags: [memory, agent-quality]
---

The agent now selects which prior messages to include in its context based on relevance to the current question, not just recency. Pinned facts always make it in. Older messages get auto-compacted into summaries when the conversation gets long, so the model doesn't run out of context window mid-task.

Practically: long-running conversations stay coherent without you needing to summarize manually.
