---
date: 2026-04-20
type: fix
title: Campaign memory isolation
tags: [memory, agent-quality]
---

Bug: selecting Portugal campaign and asking a question, the agent's reply still mentioned UK campaign details from a previous turn in the same conversation.

**What changed:**

- Switching campaigns mid-conversation now updates the conversation's stored campaign so subsequent turns load the right context.
- Each chat message is tagged with the campaign that was active when it was sent. When the agent loads recent context, it filters out messages that belong to other campaigns.
- The agent now receives the explicit campaign ID from the UI and stops trying to guess it from the campaign name.

**Net effect:** asking about Portugal in a conversation that was previously about UK no longer leaks UK context into the answer.
