---
date: 2026-04-28
type: feature
title: Suggest edits to my guidelines (E7)
tags: [guidelines, agent-quality, dx]
---

A new **Guidelines** page (top nav) lets you view your account's guideline files (BUSINESS_CONTEXT, CAMPAIGN_GUIDELINES, GREECE_CAMPAIGN_GUIDELINES, MENA_CAMPAIGN_GUIDELINES, etc.) and ask the agent to **suggest edits**.

How it works:

- Click **"Suggest edits"** on any file. Optionally type a one-line focus ("add UK ad copy rules").
- The agent reads recent agent sessions, user corrections (your "no", "instead", "wrong" pushback messages), and your decision logs across all campaigns.
- It proposes a refined version of the file — **the file is never auto-modified**. You see a unified diff (red removed / green added) with a rationale and the evidence it used.
- Click **Apply** to overwrite the file with the proposal, or **Discard** to throw it away. **Re-generate** lets you ask again with a different focus.
- If the file changed since the suggestion was generated (e.g. you edited it manually), Apply refuses with a "stale" message — generate a fresh suggestion.

All proposals are stored in the database with their rationale and evidence so there's an audit trail of what the agent suggested vs what you accepted.

This is the closest thing to "the agent learning from how you use it" without giving it write access to your knowledge base — you stay in the loop on every change.
