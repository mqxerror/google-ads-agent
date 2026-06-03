# Chat Design — port Shopify's calm visual language into google-ads-agent

Status: design / handoff. Author: Dam3oun-Google (this session), grounded in both repos.
Direction (REVERSED from the earlier google→shopify port): **source of design = Shopify CRO agent, target to re-skin = google-ads-agent.**

This is a **re-skin only**. We keep every feature google-ads already has (persona registry, model selector, conversation history + search, context badge, memory panel, tool split, full-screen, resize, queueing, video, Claude-Code handoff, team sessions) and change only the *look*: surfaces, type, spacing, the tool-row aesthetic, markdown rhythm, the streaming/working states, and the one earned review card.

Why Shopify's chat reads as cleaner: it commits to **one calm light surface system**, renders tool calls as **quiet inline rows (not cards)**, typesets markdown like a document via a single `.studio-prose` block, uses a **gentle streaming caret**, and reserves elevated cards for the one place they're earned (the diff/review). google-ads is busy by comparison: dark default, multiple ad-hoc accent colors (blue/purple/pink/green/amber tints sprinkled per button), tool calls wrapped in bordered boxes, and per-element `prose-invert` arbitrary-variant CSS.

---

## Part A — The Shopify chat design language (the thing we're bringing over)

All paths below are in `shopify-cro-agent/`.

### A1. Token system — `frontend/src/index.css` + `frontend/DESIGN.md`
- **OKLCH tokens on `:root`**, mapped into Tailwind via an `@theme` block, so components read `bg-surface`, `text-muted`, `border-border`, `text-accent` — **no inline hex anywhere**.
- Surfaces are near-white, tinted toward the indigo brand hue (~281), never pure white: `--surface` `oklch(0.995 0.002 281)`, `--surface-2` (sunken: input well, code, tool-output), `--surface-3` (hover/pill), `--bg-app` (gutter behind panes).
- Borders: `--border` (1px hairlines), `--border-strong` (pane dividers, the avatar-lane gutter is `--border`).
- Text: `--text` / `--text-muted` / `--text-subtle` — near-black tinted, never pure black. **Hierarchy comes from scale + weight, not color.**
- ONE accent: calm indigo `--accent` (`oklch(0.585 0.205 281)`) + `--accent-hover` + `--accent-soft` (user bubble bg, active rows) + `--on-accent`. Accent carries ≤10% of the surface.
- Semantic pairs always come as `X` + `X-soft`: `--success`/`--success-soft`, `--danger`/`--danger-soft`, `--warning`/`--warning-soft`. The `-soft` tints are for backgrounds (diff lines, review header), the solid for dots/text.
- Elevation tokens: `--shadow-resting` (low), `--shadow-elevated` (review card, popovers, toast). Radii: card 12 / bubble 10 / control 8 / chip 6. Motion: `--ease-out-quint`, 140–220ms, no bounce, animate transform/opacity only.

### A2. Type — Inter (UI) + JetBrains Mono (code/tool names/tokens)
Base 14px body, 13px UI, 12px metadata, 11px uppercase tracked section labels (`.label-section`). Code 12.5px / line-height 1.55. Reading measure capped ~68ch on assistant prose.

### A3. Markdown rhythm — `.studio-prose` in `frontend/src/index.css`
A single hand-tuned block (no typography plugin) that sets: ≥1.25 heading scale, generous paragraph + section spacing, visible list markers with tinted `::marker`, an inline-code chip on `--surface-2` with a hairline border, a JetBrains-Mono code block on `--surface-2`, accent underlined links, weight-650 bold leads, a hairline-rule blockquote, bordered tables. `h4` is repurposed as a quiet uppercase sub-label. Both the live and the persisted bubble share the same `Markdown` component map (`ChatPanel.tsx` `mdComponents`) so there's no layout shift on stream-done.

### A4. Component intents (the calm patterns)
- **Assistant turn** (`ChatPanel.tsx` `MessageBubble` / `StreamingBubble`): NOT a card. An avatar in a left lane + a `border-l border-border pl-4` hairline gutter, prose in `.studio-prose`, `space-y-3` between prose and a tool cluster. Consecutive tool calls collapse into ONE tight `space-y-0.5` cluster.
- **User turn**: compact right-aligned `bg-accent-soft` bubble, `rounded-[10px]`, `max-w-[82%]`.
- **Tool call** (`ToolCallBlock.tsx`): a **quiet inline row** — a state dot (pending = `studio-pulse` subtle dot, done = `--success` dot, error = `--danger` dot + name/summary in `--danger`), mono name, right-aligned summary, expandable to input/output panes on `--surface-2`. Never a green check on a failed result.
- **Plan checklist** (`PlanChecklist.tsx`): one pinned low panel, rows not cards, hairline accent progress meter, spinner/check/dot marks. (google-ads has no plan stream — see Keep/Skip.)
- **Avatar** (`AgentAvatar.tsx`): calm `bg-accent-soft text-accent border-accent/30` mark + `studio-pulse` accent dot while working, `--shadow-resting`. Unicode/SVG only.
- **Review/diff card** (`ChatPanel.tsx` `ReviewChangeCard`): the ONE earned elevated card — `--warning-soft` header strip + `.label-section` "Review change", mono diff with `--success-soft`/`--danger-soft` line tints, primary Approve = `bg-accent`.
- **Header / composer**: header is a hairline-bottom strip, 12px muted, identity + session switcher + a tabular stats pill. Composer is a sunken `bg-surface-2` well framed as one control with `focus-within:border-accent`; affordance buttons are quiet bordered `bg-surface` ghosts; Send is the only solid `bg-accent` button.
- **Streaming**: pre-token "thinking…" = one avatar + italic muted line; mid-stream = `.studio-prose` + a `.studio-caret ▍` in `--text-subtle`. Retry note in `--warning`.

### A5. Bans (DESIGN.md)
No side-stripe accent borders on turns/cards. No gradient text. No glassmorphism. No identical icon-heading-text card grids. No em dashes in UI copy. Cards only where they're the best affordance.

---

## Part B — google-ads-agent's current chat styling system (the gap)

All paths in `google-ads-agent/frontend/`.

- **Stack:** Tailwind v4 (`@tailwindcss/vite` ^4.2.2), `react-markdown` + `remark-gfm`, `clsx` + `tailwind-merge` (`cn`), `lucide-react` icons, Radix UI primitives in `src/components/ui/`. Same core stack as Shopify, so the port is low-risk.
- **Token file:** `src/index.css`. It uses a Tailwind v4 `@theme` block exactly like Shopify — but tokens are **HSL, named for shadcn semantics** (`--color-background`, `--color-foreground`, `--color-card`, `--color-primary`, `--color-secondary`, `--color-muted`, `--color-accent`, `--color-border`, `--color-destructive`, `--color-sidebar`, `--color-input`, plus `--color-status-*` and `--color-tool-api`/`--color-tool-browser`).
- **Default theme is DARK.** The `@theme` block's default values are dark (`--color-background: hsl(224 71% 4%)`); `.light` is an override class — and it is **not applied** anywhere in `main.tsx` / `index.html` / `App.tsx`. So today the chat renders dark navy. Shopify is committed light. **This is the single biggest visual gap.**
- **No `@tailwindcss/typography` installed** — markdown is styled with a giant arbitrary-variant string `PROSE_CLASSES` (`prose prose-sm prose-invert [&_h1]:… [&_p]:… [&_code]:…`) inlined in `ChatMessage.tsx`. (`prose-invert` confirms the dark assumption.)
- **No `.studio-prose` / `.studio-caret` / `.studio-pulse` / `.label-section` helpers** — none of Shopify's reusable chat CSS exists here.
- **Color sprawl:** components hardcode many one-off Tailwind palette tints — `bg-primary/5`, `border-primary/20`, `bg-blue-500/10 text-blue-600`, `bg-purple-500/20 text-purple-400`, `bg-pink-500/20`, `text-emerald-600`, `bg-amber-400`, `text-yellow-500`, `text-green-500`, `text-pink-400` — across `ChatMessage.tsx`, `ChatInput.tsx`, `ContextBadge.tsx`, `AgentAvatar.tsx`. Shopify routes everything through ~3 token families.
- **Tool calls are boxed:** `ChatMessage.tsx` `ToolCallsSummary` wraps tool calls in a `border rounded-md` card with a "live activity" sub-card (`bg-primary/5 border border-primary/20 rounded-lg`); `ToolCallBlock.tsx` is a bordered expandable row. Shopify makes these flat quiet rows.
- **Assistant message is a card:** `ChatMessage.tsx` renders assistant content in `w-full bg-secondary/40 rounded-lg px-4 py-3` (a filled card) instead of Shopify's avatar-lane + hairline gutter.

### What google-ads does well — KEEP the features, only re-skin them
- **Persona registry** (`src/lib/agentProfiles.ts`) — 10 named personas with colors/initials/titles. Richer than Shopify's single CRO mark. Keep it; just make sure the per-persona colors read as quiet identity accents on a light surface, not loud chips (the profile bg/border hexes like `#EFF6FF`/`#3B82F6` are already light-mode friendly — they predate the dark default).
- **Model selector** (Sonnet/Opus/Haiku), **Templates**, **Roles**, **Team session**, **Video** pickers in `ChatInput.tsx`.
- **Conversation history + full-text search**, id chip, export-to-markdown, new/delete (`ChatPanel.tsx` toolbar + history panel).
- **ContextBadge** token-budget meter + per-layer breakdown (`ContextBadge.tsx`) — a genuinely good feature Shopify lacks.
- **MemoryPanel** pinned facts / decisions (`MemoryPanel.tsx`).
- **Tool split** action-vs-internal (`ChatMessage.tsx` `INTERNAL_TOOLS`) — a smart idea; keep the split, restyle the rows to Shopify's quiet dot style.
- Full-screen, resizable panel, message queueing, "Send to Claude Code" handoff, inline video. All stay.

---

## Part C — Gap table (Shopify trait → google-ads current → change)

| Shopify design trait | google-ads current state | Change needed |
|---|---|---|
| Committed light, OKLCH tokens (`index.css` `:root` + `@theme`) | Dark default HSL `@theme`; `.light` exists but unapplied | Port Shopify's OKLCH token set into `index.css` (translate to google-ads' semantic names OR add the surface/accent/text/semantic families); make light the rendered default |
| One accent (indigo) + `-soft` semantic pairs | `primary` + ad-hoc blue/purple/pink/green/amber/yellow tints | Collapse one-off tints to `accent` / `success` / `warning` / `danger` (+ `-soft`); persona colors stay as the only multi-hue, used quietly |
| `.studio-prose` single markdown block, 68ch cap, JetBrains code chip | `PROSE_CLASSES` arbitrary-variant string, `prose-invert` | Add `.studio-prose` to `index.css`; replace `PROSE_CLASSES` usages in `ChatMessage.tsx` with `studio-prose` |
| Assistant turn = avatar lane + `border-l` hairline gutter, no card | Assistant content in `bg-secondary/40 rounded-lg` card | Re-skin `ChatMessage.tsx` assistant branch to avatar + `border-l border-border pl-4`, prose in gutter; drop the filled card |
| User turn = compact `bg-accent-soft` right bubble | `bg-primary text-primary-foreground` bubble | Switch to `bg-accent-soft text-text`, `rounded-[10px]`, `max-w-[82%]` |
| Tool call = quiet inline row + state dot | Bordered summary card + bordered `ToolCallBlock` + `bg-primary/5` live-activity card | Re-skin `ChatMessage.tsx` `ToolCallsSummary` + `ToolCallBlock.tsx` to flat rows with `StateDot` (pulse/success/danger); fold "live activity" into the pulsing dot |
| Streaming caret `.studio-caret ▍` + "thinking…" line | "Agent is thinking..." `animate-pulse` text only; no caret | Add `.studio-caret`/`.studio-pulse` to `index.css`; render caret on the streaming assistant text in `ChatPanel.tsx` |
| Avatar = `accent-soft` mark + `studio-pulse` dot, `--shadow-resting` | Per-persona hex bg + `bg-amber-400 animate-pulse` working dot | Keep persona color, swap working dot to `studio-pulse bg-accent` (or persona color), use `--shadow-resting` |
| Composer = sunken `surface-2` well, `focus-within:border-accent`, one solid Send | `bg-secondary/50 border` textarea + Radix Buttons, many colored toolbar tabs | Re-skin `ChatInput.tsx` to one sunken well; quiet bordered `bg-surface` ghost tabs; Send = solid `bg-accent`; selected tabs `bg-accent-soft text-accent` |
| Header hairline strip + tabular stats pill | hairline strip exists (good); colored icon buttons | Mostly KEEP; normalize icon-button hover to `hover:bg-surface-3 hover:text-text` |
| ContextBadge quiet token pills | red/yellow/emerald hardcoded + `bg-secondary` pills | Map status colors to `danger`/`warning`/`success`; pills to `bg-surface-3` |
| Review/diff card = only earned elevated card | (no diff card — google-ads has no propose-edit flow) | N/A — nothing to port; do NOT invent one |
| Plan checklist pinned panel | (no plan SSE) | N/A — skip; backend emits no `plan` event |

---

## Part D — Per-element re-skin spec (real files both sides)

For each google-ads chat element: what to change, citing the Shopify token/intent/class and the google-ads file it lands in.

### D1. Tokens & global CSS — `google-ads-agent/frontend/src/index.css`
Port from `shopify-cro-agent/frontend/src/index.css`:
- The OKLCH `:root` token families: surfaces (`--surface`, `--surface-2`, `--surface-3`, `--bg-app`, `--border`, `--border-strong`), text (`--text`, `--text-muted`, `--text-subtle`), accent (`--accent`, `--accent-hover`, `--accent-soft`, `--on-accent`), semantics (`--success(-soft)`, `--danger(-soft)`, `--warning(-soft)`), `--focus-ring`, `--shadow-resting`, `--shadow-elevated`, `--ease-out-quint`.
- The `@theme` mapping so Tailwind exposes `bg-surface`, `text-muted`, `border-border`, `text-accent`, `bg-accent-soft`, `text-success`, etc. **Translation note:** google-ads' existing tokens are shadcn-named (`background`/`foreground`/`card`/`primary`/`secondary`/`muted`/`border`). Two valid approaches — pick ONE in implementation:
  - **(Recommended) Add the Shopify families alongside, then alias** the shadcn names to them — `--color-background: var(--surface)`, `--color-foreground: var(--text)`, `--color-primary: var(--accent)`, `--color-secondary: var(--surface-2)`, `--color-muted: var(--text-muted)`, `--color-border: var(--border)`, `--color-card: var(--surface)`, `--color-destructive: var(--danger)`. This re-skins the WHOLE app (sidebar, dashboards, ui/ primitives) to the calm light system for free, and chat components can additionally use `bg-surface`/`text-muted` directly. Default (no `.light` needed) becomes light.
  - (Minimal) Only add the new families + helper classes, restyle chat components explicitly, leave the rest dark. Cheaper but leaves the chat looking grafted onto a dark app — not recommended.
- The reusable classes: `.label-section`, `.studio-caret` (+ `@keyframes studio-caret`), `.studio-pulse` (+ keyframes), the quiet scrollbar block, the `prefers-reduced-motion` block, and the entire `.studio-prose { … }` ruleset.

### D2. Markdown — `src/components/chat/ChatMessage.tsx`
- Replace the `PROSE_CLASSES` constant + its 4 usages (regular content, team preamble/role/epilogue) with `className="studio-prose break-words"`. Keep the `<ReactMarkdown remarkPlugins={[remarkGfm]}>` calls and the team-session role-splitting logic verbatim — only the wrapper class changes.
- (Optional, matches Shopify) add the `mdComponents` map (anchors `target=_blank rel=noreferrer`, pass-through `code`) so links open safely; reuse for both regular + team renders.

### D3. Assistant & user turn shells — `src/components/chat/ChatMessage.tsx`
- Assistant branch: drop `bg-secondary/40 rounded-lg px-4 py-3`; render as Shopify's `<div className="flex gap-3"><AgentAvatar …/><div className="min-w-0 flex-1 space-y-3 border-l border-border pl-4">…</div></div>`. The persona header (avatar + name + title + relative time) stays — it's google-ads' richer identity; just place it above the prose inside the gutter, or keep the avatar in the lane and the name as a small `text-text` label.
- User branch: `bg-primary text-primary-foreground` → `bg-accent-soft text-text rounded-[10px] max-w-[82%]`. Keep the "Queued" badge (recolor to `text-muted`).
- Hover action buttons (delete, "Claude Code") — keep behavior; recolor to quiet `bg-surface-3 text-muted hover:text-text`, sent/error states to `success`/`danger`.

### D4. Tool rows — `src/components/chat/ChatMessage.tsx` (`ToolCallsSummary`) + `src/components/chat/ToolCallBlock.tsx`
- `ToolCallsSummary` summary bar: drop the outer `border … rounded-md` card; make it a quiet collapsible row using a `StateDot` (port Shopify's `StateDot`: pending `studio-pulse bg-subtle`, done `bg-success`, error `bg-danger`) instead of `Loader2/Check/X` lucide glyphs. Keep the action-vs-internal split + counts (good feature).
- Fold the `bg-primary/5 border border-primary/20` "live activity" sub-card into the pulsing-dot affordance + the summary text — no separate boxed panel.
- `ToolCallBlock.tsx`: re-skin to Shopify's row — `-mx-2 px-2 rounded-md hover:bg-surface-2`, mono `text-[12.5px]`, `StateDot`, right-aligned `text-muted` summary, expand panes on `bg-surface-2` with `.label-section` "Input"/"Output". Keep the `source` icon map and `compact` mode. Replace `text-tool-api`/`text-tool-browser`/`text-green-400`/`text-orange-400` with `text-text` (name) + the dot for state; sources can keep their emoji only.

### D5. Avatar — `src/components/chat/AgentAvatar.tsx`
- Keep the per-persona `bgColor`/`borderColor`/`color` inline style (identity). Swap the working dot `bg-amber-400 animate-pulse` → `studio-pulse bg-accent` with `border-2 border-surface`; resting dot `bg-emerald-400` → `bg-success`. Add `style={{ boxShadow: 'var(--shadow-resting)' }}`. Keep sizes.

### D6. Composer — `src/components/chat/ChatInput.tsx`
- Wrap textarea + affordance rows in one sunken well: `rounded-[12px] border border-border bg-surface-2 focus-within:border-accent` (Shopify `ChatPanel.tsx` composer). Textarea becomes `bg-transparent … placeholder:text-subtle outline-none`.
- Toolbar tabs (model buttons, Roles, Templates, Team, Video): unify to quiet ghosts — `text-muted hover:bg-surface-3 hover:text-text`; selected = `bg-accent-soft text-accent`. Remove the per-feature color theming (blue/purple/pink) so the strip reads calm; persona/feature identity can stay as the icon only.
- Send/Stop: replace Radix `Button` with Shopify's pattern OR restyle — Send = `bg-accent text-on-accent hover:bg-accent-hover`, Stop = `bg-danger text-on-accent`. Keep keyboard + queue behavior.
- Overlay panels (Templates/Roles/Team/Mentions): `bg-card border` → `bg-surface border-border` with `boxShadow: var(--shadow-elevated)`; rows `hover:bg-surface-2`, selected `bg-accent-soft`.

### D7. Header — `src/components/layout/ChatPanel.tsx`
- Mostly KEEP (it already has a hairline-bottom toolbar). Normalize all icon buttons to `text-muted hover:text-text hover:bg-surface-3`. The id chip's `text-green-500` check → `text-success`. The "Agent is thinking..." line: keep, but pair with the avatar + caret (D8). The resize handle `hover:bg-primary/30` → `hover:bg-accent/20`. Collapsed strip `bg-sidebar` → `bg-surface-2`.

### D8. Streaming state — `src/components/layout/ChatPanel.tsx`
- google-ads streams into a placeholder assistant message (no separate StreamingBubble). To get Shopify's feel: while the last message is the streaming assistant turn, append a `.studio-caret ▍` after its markdown (render the caret when `isResponding` and this is the active assistant msg). The pre-token state ("Agent is thinking...") → an avatar + italic `text-muted` "thinking…" line (Shopify `ChatPanel.tsx` pre-token block). No backend change — both read existing SSE state.

### D9. ContextBadge — `src/components/chat/ContextBadge.tsx`
- Pills `bg-secondary` → `bg-surface-3 text-text`; status dot `bg-status-enabled` stays (it's already a token). Usage colors: red/yellow/emerald → `danger`/`warning`/`success` (+ `-soft` for bar backgrounds). Details dropdown `bg-popover border` → `bg-surface border-border` + `shadow-elevated`. Per-layer bars: map `priorityColor` to token equivalents. This is a KEEP-the-feature, retune-the-palette pass.

### D10. MemoryPanel — `src/components/chat/MemoryPanel.tsx`
- Light pass only: ensure its surfaces/borders read against the new light tokens (it inherits `bg-card`/`secondary` via the alias if approach D1-recommended is taken, so it may need zero changes). Verify expandos and the add-fact input use `bg-surface-2` + `border-border`.

### D11. agentProfiles — `src/lib/agentProfiles.ts`
- No structural change. The persona hexes (`#EFF6FF` bg, `#3B82F6` border, `#2563EB` text, etc.) are already light-mode tuned, so they render correctly once the app surface is light. Optionally nudge any too-saturated `color` toward the muted register so persona names read as quiet identity, not loud labels. This file is the one place multi-hue is allowed — that's google-ads' richer-than-Shopify identity feature and we keep it.

---

## Part E — Explicit scope statement
Re-skin to Shopify's calmer light visual language. **Preserve all google-ads chat functionality.** No backend, no SSE-contract, no workflow changes. Do NOT invent a diff/review card or a plan checklist (google-ads' backend emits neither). The win is: one light token system, quiet tool rows, `.studio-prose` markdown, a gentle caret, and collapsed color sprawl — google-ads' feature-rich chat wearing Shopify's calm skin.
