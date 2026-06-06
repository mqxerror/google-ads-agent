# DESIGN.md — google-ads-agent frontend

Calm light-mode workspace for an AI Google Ads strategist. Color strategy:
**Restrained** — tinted neutrals + one indigo accent that carries ≤10% of any
surface. Adapted from the Shopify CRO agent's "Studio" language so the two
Mercan agents share one visual register.

Theme rationale: an agency operator reviews campaigns, keyword tables, and
agent chat at a desk in daylight. Bright ambient light + dense data tables
force **light**. The app previously shipped a dark navy default; it is now
committed light through the token layer (see `src/index.css`).

All colors OKLCH. Neutrals tinted toward the indigo brand hue (~281) at chroma
0.003–0.008. Never `#000` / `#fff`. The one allowed multi-hue exception is the
per-persona identity palette in `src/lib/agentProfiles.ts` (10 named agents).

## Token system

Single source of truth: OKLCH custom properties on `:root` in
`src/index.css`, surfaced to Tailwind v4 via the `@theme` block so components
read `bg-surface`, `text-muted`, `border-border`, `text-accent`,
`bg-accent-soft`, `text-success`, etc. No inline hex in components.

### Translation layer (why the whole app flipped light for free)
The app's components were written against shadcn-named tokens
(`bg-background`, `text-foreground`, `bg-primary`, `bg-secondary`, `bg-card`,
`text-muted-foreground`, `border-border`, `bg-destructive`, `bg-sidebar`,
`bg-input`, …). Rather than rewrite every component, each shadcn name is
**aliased onto an OKLCH family** in the `@theme` block:

| shadcn name | → OKLCH family |
|---|---|
| `--color-background` | `--bg-app` |
| `--color-foreground` | `--text` |
| `--color-card` / `--color-popover` | `--surface` |
| `--color-primary` / `--color-accent` | `--accent` |
| `--color-primary-foreground` | `--on-accent` |
| `--color-secondary` / `--color-input` / `--color-sidebar` | `--surface-2` |
| `--color-muted` / `--color-muted-foreground` | `--text-muted` |
| `--color-border` / `--color-ring` | `--border` / `--accent` |
| `--color-destructive` | `--danger` |
| `--color-status-enabled/paused/removed` | `--success`/`--warning`/`--danger` |

Result: the sidebar, dashboards, campaign tables, settings, Studio, and all
`ui/` primitives adopt the calm light palette in one place, while chat
components can additionally read the raw families (`bg-surface`, `text-muted`).

### OKLCH families
- **Surfaces** — `--bg-app` (app gutter), `--surface` (panes/cards),
  `--surface-2` (sunken: input well, code, tool output, tree),
  `--surface-3` (hover rows, pill bg). Near-white, never pure white.
- **Borders** — `--border` (1px hairlines), `--border-strong` (pane dividers,
  scrollbars).
- **Text** — `--text` / `--text-muted` / `--text-subtle`. Hierarchy from scale
  + weight, not color.
- **Accent** — `--accent` (indigo), `--accent-hover`, `--accent-soft` (user
  bubble, active tab, agent halo), `--on-accent`.
- **Semantic** — always a solid + `-soft` pair: `--success(-soft)`,
  `--danger(-soft)`, `--warning(-soft)`.
- **Elevation** — `--shadow-resting` (low, cards/avatars),
  `--shadow-elevated` (popovers, dropdowns).
- **Motion** — `--ease-out-quint`, 140–220ms, transform/opacity only.

## Typography

- **UI:** Inter (loaded in `index.html`). Body 14px, UI 13px, metadata 12px,
  section labels 11px uppercase tracked (`.label-section`). Label weight 600.
- **Code / tool names / tokens:** JetBrains Mono. 12.5px, line-height 1.55.
- **Scale:** ≥1.25 between heading steps. Reading measure capped ~68ch on
  assistant prose (`.studio-prose`).

## Reusable chat utilities (in `src/index.css`)
- `.studio-prose` — hand-tuned markdown rhythm (headings, lists with visible
  markers, inline-code chip, JetBrains code block, accent links, hairline
  blockquote/tables). Replaces the old `prose-invert` arbitrary-variant string.
- `.studio-caret` — gentle blinking `▍` for streaming.
- `.studio-pulse` — subtle pulse for pending tool dots and the working avatar
  dot.
- `.label-section` — 11px uppercase tracked muted label.

## Component intent (not boxes-in-boxes)
- **Chat assistant turn:** avatar in a left lane + a `border-l border-border`
  hairline gutter; prose in `.studio-prose`. NOT a filled card.
- **Chat user turn:** compact `bg-accent-soft` bubble, right-aligned,
  `rounded-[10px]`, `max-w-[82%]`.
- **Tool calls:** quiet inline rows — a state dot (pending pulse / `--success`
  done / `--danger` error) + mono name + expandable input/output on
  `--surface-2`. Never a green check on a failed result. No boxed cards.
- **Avatar:** per-persona tinted mark (`agentProfiles.ts`) + `--shadow-resting`;
  working dot = `.studio-pulse bg-accent`, resting = `bg-success`.
- **Composer:** one sunken `bg-surface-2` well with `focus-within:border-accent`;
  toolbar tabs are quiet ghosts (selected = `bg-accent-soft text-accent`); Send
  is the only solid `bg-accent` button; Stop = `bg-danger`.
- **ContextBadge / MemoryPanel:** quiet `bg-surface-3` pills; usage colors map
  to `danger`/`warning`/`success` (+ `-soft` for bar backgrounds).
- **Persona identity:** the 10 named agents in `agentProfiles.ts` are the one
  allowed multi-hue — light-mode tuned, used as quiet identity accents.

## Bans (enforced)
No side-stripe accent borders on turns. No gradient text. No glassmorphism. No
identical icon-heading-text card grids. No em dashes in UI copy. Cards only
where they're the best affordance (chat turns and tool rows are not).
Do NOT invent a diff/review card or a plan checklist — the backend emits
neither event.
