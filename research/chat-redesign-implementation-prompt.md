# Implementation Prompt — Re-skin google-ads chat to Shopify's calm design (paste into a fresh Dam3oun-Google session)

You are **Dam3oun-Google** working in `~/Documents/LangarAI/google-ads-agent`. Re-skin THIS repo's chat interface to adopt the **calm light visual language** of the Shopify CRO agent. Full spec: `research/chat-design-from-shopify.md` — read it first, in full.

This is a **UI / design-system task only**. Reuse the existing backend + SSE streaming, the message store/state, react-query, and every chat feature exactly as-is. **Do NOT** touch any `.py`, change the SSE event contract, or alter behavior. **Do NOT** invent a diff/review card or a plan checklist (the backend emits neither `diff_ready` nor `plan` events).

## Read first (in this order)
1. `research/chat-design-from-shopify.md` (this repo) — the spec + gap table + per-element changes.
2. Source design language (read, do not edit): `../shopify-cro-agent/frontend/DESIGN.md`, `../shopify-cro-agent/frontend/src/index.css` (the OKLCH `@theme`, `.studio-prose`, `.studio-caret`, `.studio-pulse`, `.label-section`), and components `../shopify-cro-agent/frontend/src/components/{ChatPanel,AgentAvatar,ToolCallBlock}.tsx`.
3. Targets you will edit (this repo): `frontend/src/index.css`, `frontend/src/components/layout/ChatPanel.tsx`, `frontend/src/components/chat/{ChatMessage,ChatInput,ContextBadge,MemoryPanel,AgentAvatar,ToolCallBlock}.tsx`, `frontend/src/lib/agentProfiles.ts`.

## Constraints
- **Tokens:** Port Shopify's OKLCH token families into `frontend/src/index.css`. google-ads uses Tailwind v4 `@theme` with shadcn-named HSL tokens and **defaults to DARK** (`.light` exists but is never applied). Adopt the **recommended translation layer**: add the OKLCH surface/text/accent/semantic families, then **alias the existing shadcn names to them** (`--color-background: var(--surface)`, `--color-primary: var(--accent)`, `--color-secondary: var(--surface-2)`, `--color-foreground: var(--text)`, `--color-muted: var(--text-muted)`, `--color-border: var(--border)`, `--color-destructive: var(--danger)`, `--color-card: var(--surface)`, `--color-sidebar: var(--surface-2)`, `--color-input: var(--surface-2)`). This makes light the rendered default and re-skins the whole app for free. Also add `.studio-prose`, `.studio-caret`, `.studio-pulse`, `.label-section`, the quiet scrollbar block, and `prefers-reduced-motion`. Do not introduce inline hex in components (persona hexes in `agentProfiles.ts` are the one allowed exception).
- **Type:** Inter + JetBrains Mono are already the `@theme` fonts — keep. Adopt Shopify's 14/13/12/11px rhythm in chat components.
- **Spacing/shape/motion:** radii 12/10/8/6, `--shadow-resting`/`--shadow-elevated`, `--ease-out-quint`, 140–220ms, transform/opacity only.
- **Preserve ALL features:** persona registry, model selector, Templates/Roles/Team/Video pickers, conversation history + search + id chip + export + new/delete, ContextBadge token meter, MemoryPanel, action-vs-internal tool split, full-screen, resize, message queue, "Send to Claude Code" handoff, inline video. Re-skin them; don't remove them.
- **UI-only:** no `.py` edits, no API/SSE changes. The streaming placeholder-message pattern stays; the caret is a render-time addition over existing state.

## Build order
1. **`index.css`** — port OKLCH tokens + alias shadcn names + add `.studio-prose` / `.studio-caret` / `.studio-pulse` / `.label-section` / scrollbar / reduced-motion. Verify the app now renders light by default.
2. **`AgentAvatar.tsx`** — keep persona colors; working dot → `studio-pulse bg-accent`, resting → `bg-success`, add `--shadow-resting`.
3. **`ToolCallBlock.tsx`** — flat quiet row + ported `StateDot`; expand panes on `bg-surface-2` with `.label-section`. Keep `source` icons + `compact` mode.
4. **`ChatMessage.tsx`** — replace `PROSE_CLASSES` with `studio-prose`; assistant turn → avatar lane + `border-l border-border pl-4` (drop `bg-secondary/40` card); user bubble → `bg-accent-soft text-text`; re-skin `ToolCallsSummary` to a quiet collapsible row (fold the `bg-primary/5` live-activity box into the pulsing dot); recolor hover actions to tokens. Keep the team-session role-splitting logic verbatim.
5. **`ChatInput.tsx`** — sunken `bg-surface-2` well with `focus-within:border-accent`; unify toolbar tabs to quiet ghosts (`hover:bg-surface-3`, selected `bg-accent-soft text-accent`); Send `bg-accent`, Stop `bg-danger`; overlays → `bg-surface` + `shadow-elevated`.
6. **`ChatPanel.tsx`** — normalize header icon buttons to token hovers; add the `.studio-caret` to the active streaming assistant message + the avatar+italic "thinking…" pre-token line; recolor resize handle + collapsed strip to tokens.
7. **`ContextBadge.tsx`** — pills `bg-surface-3`; status colors → `danger`/`warning`/`success` (+ `-soft`); dropdown `bg-surface` + `shadow-elevated`.
8. **`MemoryPanel.tsx`** — light pass; verify surfaces/inputs read against new tokens (may be near-zero changes via the aliases).
9. **`agentProfiles.ts`** — no structural change; optionally mute over-saturated persona text colors.

## Verification
- `cd frontend && pnpm tsc --noEmit` (or `npm run` equivalent) — zero type errors. (Use the repo's actual package manager — check `frontend/` for `pnpm-lock.yaml` / `package-lock.json`.)
- `pnpm build` succeeds.
- Run the dev server and visually confirm in the chat panel: light tinted surfaces (no dark navy), assistant turns as avatar-lane + hairline gutter (no filled card), tool calls as quiet dot rows (no boxes), user bubble in accent-soft, a gentle streaming caret while the agent responds, sunken composer well with one solid accent Send, calm toolbar (no blue/purple/pink tabs), ContextBadge + MemoryPanel + history search + persona names all still working.
- Confirm NO feature regressed: send a message, switch/search/export/delete a conversation, open Templates/Roles/Team/Video, stop a run, expand a tool call, expand ContextBadge, add a pinned fact, "Send to Claude Code".
- Grep the chat components for leftover sprawl: no `prose-invert`, no `bg-primary/5`, no `bg-blue-500`/`bg-purple-500`/`bg-pink-500`/`bg-amber-400` in chat files.

## BMAD drift discipline
Before ending: append ONE row to `_bmad-output/feature-log.md` (date · "Chat re-skin to Shopify calm design" · `NEW — unplanned` · files touched).

## Report back (under 250 words)
- Files changed + line counts.
- Whether you took the recommended alias approach or restyled chat-only, and why.
- Any token translation decisions (OKLCH families added, shadcn aliases wired).
- Anything you re-skinned beyond the spec, and any feature you had to special-case to preserve.
- tsc / build result + the visual-check outcome.
