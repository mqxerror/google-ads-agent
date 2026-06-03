# Plan — Hybrid LLM runners (Claude + Gemini) with per-account privacy policy

**Status:** scoping only, not started. Approved direction.
**Drives:** `backend/app/services/agent.py` refactor + new runner modules + `accounts_v2` schema bump + frontend picker + Settings UI.

---

## Why

User prefers Claude for the agentic chains the team runs daily (PPC Strategist, Search Term Hunter, browser automation). Some team members and prospective clients want **Google** for client-data privacy reasons — they don't want client account data flowing through Anthropic's endpoints.

The real ask isn't "model choice" — it's a **provider policy per account** so client data with privacy constraints can't accidentally route to a provider they didn't approve.

## Architecture

Strategy pattern around the agent runner. Memory, Studio, role files, frontend chat — all unaffected.

```
┌─────────────────────────────────────────────┐
│ stream_agent_response()  (caller surface unchanged)  │
└────────────┬────────────────────────────────┘
             │ picks runner from { account.policy, request.model }
             ▼
   ┌─────────────────────┐
   │ AgentRunner (ABC)   │ ← normalized event types
   ├─────────────────────┤
   │  ClaudeRunner       │ ← current code, refactored out
   │  GeminiRunner       │ ← new (Google AI Studio API)
   │  GeminiVertexRunner │ ← new (Vertex AI — data stays in your GCP)
   └─────────────────────┘
             │ all three connect to the SAME MCP servers
             ▼
   [Google Ads MCP] [Chrome MCP] [GTM MCP] [Clarity MCP]
```

The MCP servers are reused unchanged across runners — only the config files differ.

## What's shared, what's per-runner

| Layer | Per-runner change |
|---|---|
| MCP server processes | None — same processes, same commands |
| MCP config file format | Generate both Claude `mcp_config.json` and Gemini `~/.gemini/settings.json` from one shared registry |
| Built-in tools (Bash/Read/Edit/Grep) | Each CLI brings its own; semantics close enough that role prompts work for both with light templating |
| Stream event format | Per-runner adapter normalizes to a single internal event dict the rest of the system consumes |
| Cost tracking | Per-provider rates; existing `AGENT_MAX_TOTAL_COST_USD` cap still applies |
| Role files (`data/roles/*.md`) | None — they're just text |
| Memory, Studio, Changelog, frontend chat | None |

## Per-account privacy policy

New fields on `accounts_v2`:
```
default_provider: 'anthropic' | 'google' | 'google-vertex'
allowed_providers: ['anthropic', 'google', 'google-vertex']  -- whitelist; null = all allowed
```

- **Soft default**: when user doesn't pick a model, the account's `default_provider` runs.
- **Hard lock**: if `allowed_providers` excludes a provider, the model picker hides it for that account and the backend refuses the request server-side (defense in depth).
- A **provider badge** ("via Claude" / "via Gemini" / "via Vertex") shows on every assistant message so it's never ambiguous which provider saw the data.
- Switching the policy is one toggle in account Settings — no code change per client.
- An **audit log entry** records the (account_id, conversation_id, message_id, provider) tuple per send so you can prove to a client which provider handled their data.

## Phased build (~5-6 working days total)

| Phase | Scope | Effort |
|---|---|---|
| **0** Smoke-test | Install Gemini CLI. Talk to one existing MCP server. Document the stream-event shape vs Claude's. De-risks the refactor. | ~2 hr |
| **1** Runner-agnostic refactor | Define `AgentRunner` ABC + normalized event types. Move existing Claude logic into `ClaudeRunner`. No behavior change. | ~1 day |
| **2** GeminiRunner (consumer API) | Subprocess wrapper. MCP config generator emits both formats from a shared registry. Stream-event adapter to normalized dict. Wire into runner factory. | ~2 days |
| **3** Frontend picker + provider badges | Group model dropdown by provider. Show provider badge per assistant message. Surface per-account default in chat header. | ~half day |
| **4** Privacy policy & enforcement | `accounts_v2.allowed_providers` + DB migration + server-side guard + UI lock indicator + audit log table. | ~1 day |
| **5** GeminiVertexRunner | Same shape as GeminiRunner but service-account auth + Vertex endpoint + project ID config. The "data stays in your GCP" claim for client contracts. | ~1 day |

Each phase ships independently and reverts cleanly.

## Open questions to resolve before Phase 0

1. **Vertex or consumer Google AI Studio API?**
   - Vertex AI = data stays in your GCP tenant, no training use, contractual residency. Right answer if "client privacy" means contracts and DPAs.
   - Consumer API = easier to set up, but data flows through Google's standard endpoints with the standard ToS.
   - **Recommendation**: if the team is asking for Gemini for privacy reasons, do Phase 5 first and skip the consumer API. The team's stated reason is the privacy upgrade, not "we like the consumer API".

2. **Granularity of policy**
   - **Account-level** (recommended) — enough for "Client X uses Gemini, Mercan uses Claude". Matches how billing/data ownership already works.
   - Per-campaign — finer but more places to misconfigure.
   - Global with per-message override — looser; risks accidental cross-provider leak.

## Reuse opportunities to confirm during Phase 1

- The role system prompt format is already provider-agnostic (markdown). Should work as-is for Gemini with the system role mapped properly.
- The `active_role` mechanism just sets the system prompt — runner-agnostic.
- The `role_notes` write-side guard (cross-campaign pollution check) sits below the runner abstraction — works for any provider.
- The Studio's `script_generator` ephemeral-conversation pattern can stay; it just calls `stream_agent_response` which routes via the factory.

## What NOT to do (rejected alternatives)

- **LiteLLM-style proxy** — would lose Claude CLI's built-in agent loop, MCP orchestration, permission modes, skill system. Net negative.
- **Anthropic SDK + Google SDK direct (no CLIs)** — would have to reimplement streaming, tool calls, MCP, permissions. Months of work to recreate what the CLIs already do.
- **Switch fully to Gemini CLI** — kills the working Claude flow during the migration. Tool-use reliability for long agent chains (10+ tool calls) is still better on Claude per current real-world testing.
