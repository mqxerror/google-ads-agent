"""Chat Orchestration v2 — the §5 turn state machine (Epic 2).

`run_turn` is ONE async generator that drives a single chat turn from triage
to synthesis. It yields BARE {"type":..., "payload":{...}} dicts; the
chat_runner wraps each in the v2 envelope (+seq) and persists it. run_turn OWNS
its terminal `turn_done` on EVERY path.

State machine (S0–S8):
  S0 TRIAGE      heuristic pre-gate → direct-or-orchestrate (1 optional haiku call)
  S1 RECALL      task_ledger.recall → memory_recall events
  S2 VERIFY      live landing-page fetch when a recall entry says reverify
  S3 PLAN        Director plans specialists (JSON) → plan event  (degrade → DIRECT)
  S4 DISPATCH    specialists run in parallel (capped), streamed as agent_* events
  S5 RESOLVE     deterministic conflict detection over structured findings
  S6 SYNTHESIZE  Director reconciles → final_* + decision events, persists message
  S7 GATE        deterministic claim gate over the Director's final (Epic 4)
  S8 WRITEBACK   append per-specialist findings to role notes

Every LLM call goes through stream_agent_response (LAZY-imported inside the
functions so tests can patch app.services.agent.stream_agent_response).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import AsyncIterator, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """UTC timestamp for provenance-manifest entries (Epic 4)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── v2 findings suffix — appended to each specialist task ─────────────
# Asks for tight prose THEN a machine-parseable findings JSON block so S5 can
# detect conflicts structurally.
_V2_FINDINGS_SUFFIX = (
    "\n\nKeep your report under ~200 words — a few tight bullets: findings + "
    "numbers, no padding. Ground every page/form/tracking claim in the VERIFIED "
    "PREMISE above (if present); if unverified, do NOT assert page facts.\n\n"
    "THEN, after the prose, emit ONE fenced JSON block in EXACTLY this shape "
    "(no extra prose after it):\n"
    "```json\n"
    "{\n"
    '  "findings": [\n'
    '    {"claim": "<one-sentence directional claim, e.g. \'increase budget on AG2\'>",'
    ' "severity": "high|medium|low", "confidence": 0.0,'
    ' "sources": ["<what you grounded it in>"],'
    ' "disconfirmed_by": "<the one fact that would flip it>"}\n'
    "  ],\n"
    '  "summary": "<one-line bottom line>"\n'
    "}\n```"
)

# Directional verb lexicon for deterministic conflict detection (S5). Each pair
# is (positive, negative) — two claims on the same topic with opposing verbs
# are a conflict.
_VERB_PAIRS = [
    ("increase", "decrease"),
    ("raise", "lower"),
    ("scale", "cut"),
    ("add", "remove"),
    ("keep", "pause"),
    ("expand", "shrink"),
    ("enable", "disable"),
]
_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is",
    "are", "be", "it", "this", "that", "we", "should", "would", "will", "by",
    "at", "from", "as", "our", "your", "more", "less",
}


# ── Write-intent detection (Fix 1 — P0 stop safety) ───────────────────
# A specialist whose task involves a MUTATION needs a stop-disposition warning
# so an approved-but-not-executed write never dies silently. We detect intent
# from (a) a `write_intent` boolean the plan may set, else (b) a verb/tool
# heuristic over the task text + requested tools.
_WRITE_VERBS = (
    "push", "create", "update", "add", "remove", "pause", "enable", "set",
    "mutate", "apply", "delete", "disable", "adjust", "raise", "lower",
    "increase", "decrease", "upload", "submit",
)


def _detect_write_intent(spec: dict) -> bool:
    """True when this specialist's task looks like it MUTATES the account.

    Honors an explicit `write_intent` flag from the plan JSON first; otherwise
    scans the tool names + task text for mutating verbs. Conservative on the
    side of warning (a false-positive warning is cheap; a silently-dropped write
    is the P0 bug we're fixing)."""
    explicit = spec.get("write_intent")
    if isinstance(explicit, bool):
        return explicit
    haystack = " ".join([
        str(spec.get("task", "") or ""),
        " ".join(str(t) for t in (spec.get("tools") or [])),
    ]).lower()
    return any(v in haystack for v in _WRITE_VERBS)


# ── Meta-question detection (Fix 2 — never orchestrate a conversational aside) ─
# Questions ABOUT the agent or this conversation itself ("why did you stop?",
# "what did you just do?", "repeat that") must route to DIRECT — no recall /
# landing-page verify / conversion fetch / plan pipeline — EVEN under the
# orchestrate toggle. Orchestrating a meta-question is the observed bug (it fired
# recall + landing-page verify + conversion fetch for "why you stopped?"). The
# regexes anchor on an agent/turn-referential subject so a CAMPAIGN question
# ("what happened to conversions last week?") does NOT match.
_META_QUESTION_RX = re.compile(
    r"("
    r"\bwhy\s+(did\s+|do\s+|would\s+|are\s+|is\s+|has\s+|have\s+|'d\s+)?"
    r"(you|it|that|this|the\s+plan|the\s+turn|the\s+run|the\s+answer|the\s+response|the\s+message)"
    r"\s+(just\s+)?(stop|stopp|cut|halt|end|freez|die|dying|quit|break|pause\s+writing)"
    r"|\bwhy\s+(did\s+)?(the\s+)?(plan|turn|answer|response|synthesis|message)\s+"
    r"(stop|stopp|cut|end|halt|die|break)"
    r"|\bwhat\s+just\s+happened\b"
    r"|\bwhat\s+(did|are|were)\s+you\s+(just\s+)?(do|doing|say|saying|writing|working)"
    r"|\b(can|could|would)\s+you\s+repeat\b|\bplease\s+repeat\b"
    r"|\brepeat\s+(that|it|your\s+last|the\s+last|your\s+answer)\b"
    r"|\bsay\s+that\s+again\b|\bcome\s+again\b"
    r"|\b(you|it|the\s+answer|the\s+response|the\s+message|the\s+text)\s+(got\s+)?"
    r"(cut\s+off|cutoff|stopped|stopping|truncat)"
    r"|\b(finish|continue|complete)\s+(your|that|the)\s+"
    r"(answer|thought|response|reply|sentence|message|verdict|point)"
    r"|\bdid\s+you\s+(finish|stop|complete|get\s+cut|hang)"
    r")",
    re.IGNORECASE,
)

# Terse bare meta phrases matched as a WHOLE message (after trimming ?/./!). Kept
# separate from the regex so ultra-short follow-ups ("repeat", "continue") route
# to DIRECT without risking a substring false-positive inside a real question.
_META_EXACT = {
    "what happened", "why did you stop", "why you stopped", "why'd you stop",
    "why stop", "why did it stop", "why did the plan stop", "why the plan stopped",
    "repeat", "repeat that", "repeat please", "say again", "say that again",
    "come again", "continue", "keep going", "go on", "what were you saying",
    "what did you do", "what did you just do",
}


def _is_meta_question(message: str) -> bool:
    """True when the user turn is a meta-question about the agent / conversation
    itself rather than the campaign. Such turns route to DIRECT — never
    orchestrated — even when force_mode='orchestrate' (the orchestrate toggle)."""
    norm = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not norm:
        return False
    if norm.rstrip("?.! ") in {m.rstrip("?.! ") for m in _META_EXACT}:
        return True
    # Only apply the regex to reasonably short follow-ups — meta asides are terse;
    # this keeps false-positives on long strategic prompts near zero.
    if len(norm) <= 140 and _META_QUESTION_RX.search(norm):
        return True
    return False


# ── Read-only google-ads tool whitelist (Fix 3 — specialists can SELECT) ──────
# Chat-dispatched specialists ALWAYS get this read-only surface so a plain GAQL
# SELECT (conversion goals/actions, metrics, campaigns) works — the old
# tools=[] → "__NONE__" wall blocked EVERY google-ads tool and left specialists
# (and the GTM Specialist) in "analysis-only mode" on read queries. Every entry
# is read-only: GAQL (`search_execute_query`) has NO mutation syntax, and
# GenerateKeywordIdeas / ListAccessibleCustomers mutate nothing. A MUTATE tool's
# name is not in this set, so it stays blocked by the SAME middleware — reads
# open, writes stay gated exactly as today.
# NAMES MUST MATCH THE LIVE REGISTRY EXACTLY — single underscore joins namespace
# + tool (the `search` server's `execute_query` → `search_execute_query`). The
# prior DOUBLE-underscore names matched NOTHING and severed every read (the
# 2026-07-16 money bug). test_tool_registry.py now asserts each entry matches a
# real registered tool, so this list can never silently drift from reality again.
_READ_ONLY_GADS_TOOLS = [
    "search_execute_query",
    "search_search_campaigns",
    "search_search_ad_groups",
    "search_search_keywords",
    "search_list_accessible_customers",
    "search_generate_keyword_ideas",
]


def _specialist_tool_allowlist(planned_tools: list) -> list[str]:
    """Effective tool_allowlist for a chat-dispatched specialist: the read-only
    whitelist UNION any tools the plan explicitly requested (a plan-authorized
    mutate flows through exactly as before — the whitelist adds reads, never
    removes the existing gating). De-duplicates, order-stable."""
    merged = [*_READ_ONLY_GADS_TOOLS, *(str(t) for t in (planned_tools or []))]
    return list(dict.fromkeys(merged))


# MCP SERVER names the Director may mistakenly emit as a `tools` entry (the
# 2026-07-20 interface-contract bug: plan carried tools=['google-ads'] — a SERVER
# name grants NO tool BY NAME and stranded a user-approved write). Server names
# are ALWAYS invalid as an execution grant; mutate tools must be granted by exact
# tool name. Compared case/underscore-insensitively (`google_ads` → `google-ads`).
_MCP_SERVER_NAMES = {"google-ads", "chrome"}


async def _format_tool_catalog() -> str:
    """Compact, registry-grounded tool catalog for the Director's PLAN prompt:
    grouped read/write REAL tool names + the exact-name contract line. The
    Director must name execution tools VERBATIM from this catalog — a server name
    like 'google-ads' authorizes nothing. Enumerates the live surface OFF the
    event loop (cached); returns '' only if the registry can't be enumerated (so
    planning is never blocked — reads stay covered by the baked whitelist)."""
    try:
        from google_ads.tool_registry import execution_catalog
        cat = await asyncio.to_thread(execution_catalog)
    except Exception:  # pragma: no cover - defensive; never break planning
        logger.warning("tool-registry enumeration failed; plan prompt omits the "
                       "tool catalog", exc_info=True)
        return ""
    reads = cat.get("read") or []
    writes = cat.get("write") or []
    if not reads and not writes:
        return ""
    lines = ["\n\nTOOL CATALOG (exact registered tool names — use these VERBATIM "
             "in each specialist's `tools`):"]
    if reads:
        lines.append("  read:  " + ", ".join(reads))
    if writes:
        lines.append("  write: " + ", ".join(writes))
    lines.append(
        "CONTRACT: every `tools` entry MUST be an EXACT tool name from this "
        "catalog. MCP SERVER names (e.g. 'google-ads', 'chrome') are INVALID and "
        "grant NOTHING — an approved write named by a server name cannot execute. "
        "Use [] for analysis-only.")
    return "\n".join(lines)


def _plan_reask_prompt(original_prompt: str, invalid: list[str],
                       catalog_block: str) -> str:
    """One corrective re-ask when a plan named tools that can't grant execution.
    Restates the ORIGINAL plan ask + the real catalog + the exact invalid entries
    so the Director re-emits the same JSON with EXACT tool names."""
    return (
        original_prompt
        + "\n\n── CORRECTION REQUIRED ──\n"
        + ("Your previous plan named `tools` that are NOT valid execution tools: "
           f"{', '.join(invalid)}.\n")
        + "These are MCP SERVER names or unknown strings; a server name grants NO "
          "tool and would BLOCK an approved write.\n"
        + (catalog_block or "")
        + "\nRe-emit the SAME JSON shape, but every `tools` entry MUST be an EXACT "
          "tool name from the catalog above (or [] for analysis-only)."
    )


async def _validate_plan_tools(specs: list[dict]) -> list[str]:
    """Resolve every plan `tools` entry across `specs` against the LIVE MCP
    registry. Return the order-stable, de-duplicated entries that CANNOT grant
    execution — a known MCP server name, or an entry matching ZERO registered
    tools. Empty result = every named tool is real and grantable BY NAME.

    This is the interface-contract enforcement the plan-stage `verification` audit
    could not do (2026-07-20): that audit ran AFTER the plan event as a passive
    `verification/failed` note — no re-ask, no correction — so a server-name grant
    still stranded the approved batch. Registry-enumeration failure degrades to
    [] (no false alarm; the baked read-only whitelist still covers reads)."""
    entries: list[str] = []
    for s in specs:
        for t in (s.get("tools") or []):
            t = str(t)
            if t and t.strip() and t not in entries:
                entries.append(t)
    if not entries:
        return []
    try:
        from google_ads.tool_registry import (
            registered_tool_names, unmatched_allowlist_entries)
        names = await asyncio.to_thread(registered_tool_names)
    except Exception:  # pragma: no cover - defensive; never break dispatch
        logger.warning("tool-registry enumeration failed; skipping plan-tool "
                       "validation", exc_info=True)
        return []
    unresolved = set(unmatched_allowlist_entries(entries, names))
    server = {e for e in entries
              if e.strip().lower().replace("_", "-") in _MCP_SERVER_NAMES}
    return [e for e in entries if e in unresolved or e in server]


async def _audit_tool_allowlist(entries: list[str]) -> list[str]:
    """Fail-loud guard for the 2026-07-16 money bug: return the allowlist
    `entries` that match ZERO live-registered MCP tools (under the SAME canonical
    match the enforcement middleware uses). A non-empty result means a
    name-convention drift has silently severed tooling — the caller surfaces it
    on the turn ledger instead of letting it fail as a mystery block.

    Registry enumeration is a heavy, cached import run OFF the event loop; any
    failure degrades to `[]` (no false alarms). CI's `test_tool_registry.py` is
    the primary guard — this is the runtime backstop."""
    try:
        from google_ads.tool_registry import (
            registered_tool_names, unmatched_allowlist_entries)
        names = await asyncio.to_thread(registered_tool_names)
    except Exception:  # pragma: no cover - defensive; never break dispatch
        logger.warning("tool-registry enumeration failed; skipping allowlist "
                       "audit", exc_info=True)
        return []
    return unmatched_allowlist_entries(entries, names)


def _budget_snapshot(
    *, kind: str, reason: str, total_cost: float, elapsed_s: float, budget_cost: float,
    budget_secs: float, specialists_done: int, specialists_total: int,
) -> dict:
    """Structured payload for the visible `budget_notice` ledger event.
    kind  ∈ {'notice','stop'} — 'notice' = the $5 WATCH level was crossed
            (informational; the turn KEEPS running), 'stop' = the runaway BACKSTOP
            was hit (DISPATCH degraded + deterministic wrap-up).
    reason ∈ {'cost','time'} — which threshold triggered it. For a 'notice',
            `cap_usd` carries the WATCH level (not the backstop cap)."""
    return {
        "kind": kind,
        "reason": reason,
        "cost": round(total_cost, 4),
        "cap_usd": round(budget_cost, 2),
        "elapsed_s": round(elapsed_s, 1),
        "cap_s": round(budget_secs, 1),
        "specialists_done": specialists_done,
        "specialists_total": specialists_total,
    }


def _compose_budget_wrapup(
    specs: list[dict], findings_by_call: dict, summary_by_call: dict,
    conflicts: list[dict],
) -> str:
    """Deterministic final Director line, built from state, for when the turn
    budget is hit (Fix 1). A COMPLETE wrap-up — never a mid-sentence cut — that
    summarizes each specialist that returned and flags what did not finish."""
    lines = ["**Turn budget reached — here's where things stand:**", ""]
    done = [s for s in specs if s["call_id"] in findings_by_call]
    pending = [s for s in specs if s["call_id"] not in findings_by_call]
    if done:
        for s in done:
            cid = s["call_id"]
            summ = (summary_by_call.get(cid) or "").strip()
            if not summ:
                fs = findings_by_call.get(cid) or []
                first = fs[0] if fs and isinstance(fs[0], dict) else {}
                summ = (first.get("claim") or "reviewed; no clear finding surfaced").strip()
            lines.append(f"- **{s['role_name']}:** {summ}")
    else:
        lines.append("- No specialist finished before the cap was reached.")
    if pending:
        names = ", ".join(s["role_name"] for s in pending)
        lines.append("")
        lines.append(
            f"Still pending when the cap hit: {names}. Ask me to continue and "
            "I'll pick up from here.")
    if conflicts:
        lines.append("")
        lines.append(
            f"Note: {len(conflicts)} specialist conflict(s) were left unreconciled "
            "when the cap was reached.")
    return "\n".join(lines)


def _claim_tokens(text: str) -> set[str]:
    out: set[str] = set()
    word = []
    for ch in (text or "").lower():
        if ch.isalnum():
            word.append(ch)
        elif word:
            w = "".join(word)
            if w not in _STOPWORDS and len(w) > 1:
                out.add(w)
            word = []
    if word:
        w = "".join(word)
        if w not in _STOPWORDS and len(w) > 1:
            out.add(w)
    return out


def _stance(claim: str) -> Optional[str]:
    """Which directional verb (canonical positive) a claim carries, or None."""
    low = (claim or "").lower()
    for pos, neg in _VERB_PAIRS:
        if pos in low:
            return pos
        if neg in low:
            return neg
    return None


def _opposing(stance_a: Optional[str], stance_b: Optional[str]) -> bool:
    if not stance_a or not stance_b or stance_a == stance_b:
        return False
    for pos, neg in _VERB_PAIRS:
        if {stance_a, stance_b} == {pos, neg}:
            return True
    return False


async def _persist_chat_report(
    *, run_id: str, role_id: Optional[str], role_name: Optional[str],
    task: Optional[str], content: str, cost: float, seq: int,
) -> None:
    """Local variant of workflow_orchestrator._persist_report that ALSO stamps
    origin='chat' so task_ledger.recall can scope chat-dispatched reports."""
    from app.database import get_db

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO workflow_reports "
            "(id, run_id, phase, role_id, role_name, task, content, cost, seq, origin) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'chat')",
            (str(uuid.uuid4()), run_id, "specialist", role_id, role_name,
             task, content, cost, seq),
        )
        await db.commit()
    finally:
        await db.close()


async def _persist_assistant_message(
    *, conversation_id: str, content: str, tool_calls: Optional[list],
    agent_role_id: Optional[str], agent_role_name: Optional[str],
    campaign_id: Optional[str], turn_id: str,
) -> str:
    """Persist ONE assistant messages row (mirrors chat.py's direct-path INSERT).
    Returns the generated message id."""
    from app.database import get_db

    msg_id = str(uuid.uuid4())
    if not content:
        return msg_id
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, tool_input, "
            "agent_role, agent_role_name, campaign_id, turn_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, "assistant", content,
             json.dumps(tool_calls) if tool_calls else None,
             agent_role_id, agent_role_name, campaign_id, turn_id),
        )
        await db.commit()
    finally:
        await db.close()
    return msg_id


# ── DIRECT path helper (shared by S0 direct + S3 degrade) ─────────────
async def _run_direct(
    *, turn_id, user_message, account_id, campaign_id, campaign_name,
    conversation_id, base_guidelines, campaign_guidelines, model,
    active_role, cost_so_far: float = 0.0,
) -> AsyncIterator[dict]:
    """Stream one Director/persona answer INSIDE the orchestrated envelope.

    Fix 2(b): the orchestrated frontend renders the Director's bubble from
    `final_*` events ONLY — plain `text`/`text_delta` land in the ledger and
    NEVER reach the bubble. So the S0-direct answer AND the S3-degrade answer
    (both routed through here) MUST stream as final_start/final_chunk/final_done,
    exactly like the S6 synthesis. Emitting `text` here was why the degraded
    answer rendered as just the notice line with no visible reply. Persists the
    assistant message and OWNS the terminal turn_done."""
    from app.services.agent import stream_agent_response

    full_text_parts: list[str] = []
    tool_calls_json: list[dict] = []
    agent_role_id: Optional[str] = active_role
    agent_role_name: Optional[str] = None
    cost = cost_so_far
    started = time.monotonic()

    yield {"type": "final_start", "payload": {}}
    try:
        async for event in stream_agent_response(
            user_message=user_message,
            account_id=account_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            conversation_id=conversation_id,
            base_guidelines=base_guidelines,
            campaign_guidelines=campaign_guidelines,
            model=model,
            active_role=active_role,
            proc_key=(turn_id, "director"),
        ):
            etype = event.get("type", "event")
            if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                chunk = event.get("content", "")
                full_text_parts.append(chunk)
                yield {"type": "final_chunk", "payload": {"content": chunk}}
            elif etype == "tool_call":
                tool_calls_json.append(event)
                # Keep tool visibility in the ledger (harmless if unrendered).
                yield {"type": "tool_call",
                       "payload": {k: v for k, v in event.items() if k != "type"}}
            elif etype == "routing":
                agent_role_id = event.get("role_id") or agent_role_id
                agent_role_name = event.get("role_name")
                yield {"type": "routing",
                       "payload": {k: v for k, v in event.items() if k != "type"}}
            elif etype == "done":
                cost += float(event.get("cost") or 0.0)
            elif etype == "error":
                # Surface as a final_chunk so the bubble shows something, not silence.
                full_text_parts.append(f"\n\n_[error: {event.get('message', '')}]_")
                yield {"type": "final_chunk", "payload": {
                    "content": f"\n\n_[error: {event.get('message', '')}]_"}}
    except Exception as e:  # a stream failure must not leave an empty bubble
        logger.warning("direct-path stream failed: %s", e)
        full_text_parts.append(f"\n\n_[error: {e}]_")
        yield {"type": "final_chunk", "payload": {"content": f"\n\n_[error: {e}]_"}}

    full_text = "".join(full_text_parts).strip()
    # Fix 2(b): never end on just the notice line — if the model produced no
    # text, emit an honest minimal reply so the bubble is never empty.
    if not full_text:
        full_text = ("I don't have enough context to answer that directly right "
                     "now — could you rephrase or give me a bit more to go on?")
        yield {"type": "final_chunk", "payload": {"content": full_text}}

    message_id = str(uuid.uuid4())
    _role_id = agent_role_id or "director"
    _role_name = agent_role_name or "Marketing Director"
    try:
        message_id = await _persist_assistant_message(
            conversation_id=conversation_id, content=full_text,
            tool_calls=tool_calls_json or None,
            agent_role_id=_role_id, agent_role_name=_role_name,
            campaign_id=campaign_id, turn_id=turn_id,
        )
    except Exception as e:  # persistence must never break the stream
        logger.warning("direct-path persist failed: %s", e)
    yield {"type": "final_done", "payload": {
        "message_id": message_id, "cost_total": round(cost, 4),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "agents_used": 0, "conflicts_resolved": 0,
        # persona for the live bubble → export uses the display name, not "Assistant"
        "agent_role": _role_id, "agent_role_name": _role_name}}
    yield {"type": "turn_done", "payload": {"stop_reason": "natural", "cost": round(cost, 4)}}


# ── S4 dispatch — one specialist ──────────────────────────────────────
async def _dispatch_specialist(
    spec: dict, *, turn_id, out: asyncio.Queue, account_id, campaign_id,
    campaign_name, conversation_id, seq: int,
) -> None:
    """Run ONE planned specialist via stream_agent_response, streaming tagged
    dicts onto `out` and persisting an origin='chat' report. Never crashes."""
    from app.services.agent import stream_agent_response
    from app.services.workflow_orchestrator import _extract_json

    call_id = spec["call_id"]
    role_id = spec["role_id"]
    role_name = spec.get("role_name", role_id)
    task = spec["task"]
    model = spec.get("model", "sonnet")
    planned_tools = spec.get("tools", []) or []
    write_intent = bool(spec.get("write_intent"))

    # Fix 3: grant the read-only google-ads whitelist so a plain GAQL SELECT
    # (conversion actions/goals, metrics) works — the old empty allowlist became
    # "__NONE__" and walled specialists into analysis-only mode on reads. Mutate
    # tools are absent from the whitelist, so they stay blocked by the SAME
    # middleware unless the plan explicitly authorized one (gated as today).
    tools = _specialist_tool_allowlist(planned_tools)

    await out.put({
        "type": "agent_start", "call_id": call_id, "role_id": role_id,
        "role_name": role_name, "task": task, "model": model,
        "tools": planned_tools, "write_intent": write_intent,
    })

    parts: list[str] = []
    # Live tool outputs harvested for the provenance manifest (Epic 4). Each is
    # {"output": <str>, "name": <tool>} — run_turn feeds them to add_live_api.
    tool_outputs: list[dict] = []
    cost = 0.0
    started = time.monotonic()
    last_tool_name = ""
    try:
        async for event in stream_agent_response(
            user_message=task,
            account_id=account_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            conversation_id=conversation_id,
            model=model,
            active_role=role_id,
            tool_allowlist=tools,
            proc_key=(turn_id, call_id),
        ):
            etype = event.get("type")
            if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                chunk = event.get("content", "")
                parts.append(chunk)
                await out.put({"type": "agent_text", "call_id": call_id,
                               "content": chunk})
            elif etype == "tool_call":
                last_tool_name = event.get("name", "") or last_tool_name
                await out.put({
                    "type": "agent_tool", "call_id": call_id,
                    "tool": {"source": event.get("source", ""),
                             "name": event.get("name", ""),
                             "input_summary": str(event.get("input", ""))[:200]},
                })
            elif etype == "tool_result":
                # Live MCP tool output (agent.py:1633-1634) — capture for the
                # provenance manifest so its IDs count as LIVE_API-verified.
                tool_outputs.append({
                    "output": str(event.get("output", "")),
                    "name": event.get("name", "") or last_tool_name,
                })
            elif etype == "done":
                cost = float(event.get("cost") or 0.0)
            elif etype == "error":
                await out.put({"type": "agent_text", "call_id": call_id,
                               "content": f"\n\n_[error: {event.get('message','')}]_"})
    except Exception as e:  # a specialist failure must not crash the turn
        logger.warning("chat specialist %s failed: %s", role_id, e)
        await out.put({"type": "agent_text", "call_id": call_id,
                       "content": f"\n\n_[agent failed: {e}]_"})

    content = "".join(parts).strip()
    duration_ms = int((time.monotonic() - started) * 1000)

    # Parse the v2 findings JSON (failure → empty findings, never crash).
    findings: list[dict] = []
    summary = ""
    parsed = _extract_json(content)
    if parsed and isinstance(parsed.get("findings"), list):
        for n, f in enumerate(parsed["findings"]):
            if not isinstance(f, dict):
                continue
            f.setdefault("id", f"{call_id}-f{n}")
            findings.append(f)
        summary = str(parsed.get("summary", "") or "")

    try:
        await _persist_chat_report(
            run_id=turn_id, role_id=role_id, role_name=role_name,
            task=task, content=content, cost=cost, seq=seq,
        )
    except Exception as e:
        logger.warning("chat report persist failed for %s: %s", role_id, e)

    await out.put({
        "type": "agent_done", "call_id": call_id, "role_id": role_id,
        "cost": cost, "duration_ms": duration_ms, "findings": findings,
        "summary": summary, "status": "ok", "tool_outputs": tool_outputs,
    })


# ── The state machine ─────────────────────────────────────────────────
async def run_turn(
    *, turn_id, user_message, account_id, campaign_id, campaign_name,
    conversation_id, base_guidelines=None, campaign_guidelines=None,
    model="fable", force_mode=None, **_,
) -> AsyncIterator[dict]:
    """Drive one chat turn. Yields BARE {type, payload}. OWNS its terminal
    turn_done on every path."""
    from app.services.roles import classify_intent, get_role
    from app.services.workflow_orchestrator import _extract_json

    turn_started = time.monotonic()
    total_cost = 0.0

    # ══ S0 TRIAGE ═════════════════════════════════════════════════════
    intent = classify_intent(user_message or "")
    is_greeting = len((user_message or "").strip()) < 90
    # Fix 2(a): a meta-question about the agent/conversation ("why did you stop?",
    # "what did you just do?", "repeat that") is NEVER orchestrated — it routes to
    # DIRECT even under force_mode='orchestrate'. Orchestrating it fired recall +
    # landing-page verify + conversion fetch for a conversational aside.
    is_meta = _is_meta_question(user_message or "")
    go_direct = (
        force_mode == "direct"
        or is_meta
        or intent.get("gear") == 1
        or (force_mode != "orchestrate" and is_greeting)
    )
    needs: list[str] = []

    if is_meta:
        go_direct = True  # hard override — beats the orchestrate toggle
    elif force_mode == "orchestrate":
        go_direct = False
    elif not go_direct:
        # ONE haiku triage call (safe default: any failure → DIRECT).
        from app.services.agent import stream_agent_response

        triage_prompt = (
            "You are a triage router for a Google Ads agent. Decide whether this "
            "user turn needs a multi-specialist orchestration or a single direct "
            "answer.\n\nUSER TURN: " + (user_message or "") + "\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"mode": "direct" | "orchestrate", "reason": "<short>", '
            '"needs": ["<data classes/roles the work needs, e.g. metrics, '
            'search_terms, page_check>"]}'
        )
        triage_text: list[str] = []
        try:
            async for ev in stream_agent_response(
                user_message=triage_prompt, model="haiku", tool_allowlist=[],
                account_id=account_id, campaign_id=campaign_id,
                campaign_name=campaign_name, conversation_id=conversation_id,
            ):
                if ev.get("type") in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                    triage_text.append(ev.get("content", ""))
                elif ev.get("type") == "done":
                    total_cost += float(ev.get("cost") or 0.0)
        except Exception as e:
            logger.warning("triage call failed → DIRECT: %s", e)
        parsed = _extract_json("".join(triage_text))
        if not parsed or parsed.get("mode") != "orchestrate":
            go_direct = True  # SAFE DEFAULT
        else:
            go_direct = False
            n = parsed.get("needs")
            needs = n if isinstance(n, list) else []

    # ── DIRECT path ───────────────────────────────────────────────────
    if go_direct:
        yield {"type": "turn_start", "payload": {
            "mode": "direct", "campaign_id": campaign_id,
            "campaign_name": campaign_name, "model": model}}
        yield {"type": "director_thought", "payload": {
            "text": "Handling directly — no orchestration needed.",
            "stage": "triage"}}
        active_role = intent.get("role_id") or None
        if active_role == "director":
            active_role = None
        async for ev in _run_direct(
            turn_id=turn_id, user_message=user_message, account_id=account_id,
            campaign_id=campaign_id, campaign_name=campaign_name,
            conversation_id=conversation_id, base_guidelines=base_guidelines,
            campaign_guidelines=campaign_guidelines, model=model,
            active_role=active_role, cost_so_far=total_cost,
        ):
            yield ev
        return  # _run_direct already emitted the terminal turn_done

    # ══ ORCHESTRATE path — guard the WHOLE body ═══════════════════════
    try:
        from app.services import task_ledger
        from app.services.agent import (
            fetch_ad_landing_pages, fetch_conversion_actions, stream_agent_response)
        from app.services.claim_gate import run_claim_gate
        from app.services.provenance import ProvenanceManifest
        from app.services.roles import list_roles

        # Epic 4 — the per-turn provenance manifest, populated during S1/S2/S4
        # and read ONCE by the deterministic claim gate at S7.
        manifest = ProvenanceManifest()
        now_iso = _now_iso()
        page_verified: Optional[bool] = None  # None = no page check ran this turn

        yield {"type": "turn_start", "payload": {
            "mode": "orchestrated", "campaign_id": campaign_id,
            "campaign_name": campaign_name, "model": model}}
        if force_mode != "orchestrate":
            yield {"type": "director_thought", "payload": {
                "text": "Routing to a multi-specialist orchestration.",
                "stage": "triage"}}

        # ══ S1 RECALL ══════════════════════════════════════════════════
        entries: list[dict] = []
        try:
            entries = await task_ledger.recall(
                account_id, campaign_id, needs, user_message or "", limit=8)
        except Exception as e:
            logger.warning("recall failed: %s", e)
        for e in entries:
            # Record into the provenance manifest (Epic 4). A recalled entry is
            # prior work, not this-session data: metrics that are still fresh
            # count as LOCAL_STORE; everything else (role notes, reports,
            # session summaries) is MEMORY — its IDs only pass the gate if the
            # final sentence self-labels them.
            try:
                src = (e.get("source") or "")
                is_metrics = "metric" in src.lower()
                stale = e.get("staleness") == "stale"
                if is_metrics and not stale:
                    from app.services.provenance import extract_ids
                    manifest.add_local_store(
                        extract_ids(e.get("summary") or ""), now_iso,
                        stale=False, detail=f"recalled {src}")
                else:
                    manifest.add_memory(
                        e.get("summary") or "", e.get("created_at") or now_iso,
                        role=e.get("role_id"), stale=stale)
            except Exception as _e:  # manifest must never break the turn
                logger.debug("manifest recall add skipped: %s", _e)
            yield {"type": "memory_recall", "payload": {
                "source": e.get("source"), "ref_id": e.get("ref_id"),
                "role_id": e.get("role_id"), "age_days": e.get("age_days"),
                "staleness": e.get("staleness"), "decision": e.get("decision"),
                "summary": e.get("summary")}}
        n_stale = sum(1 for e in entries if e.get("decision") == "reverify")
        yield {"type": "director_thought", "payload": {
            "text": f"Recalled {len(entries)} prior items ({n_stale} to reverify).",
            "stage": "recall"}}

        # ══ S2 VERIFY ══════════════════════════════════════════════════
        premise_block = ""
        want_verify = ("page_check" in (needs or [])) or any(
            e.get("decision") == "reverify" for e in entries)
        if want_verify:
            block = ""
            try:
                block = await fetch_ad_landing_pages(account_id, campaign_id)
            except Exception as e:  # fetch_ad_landing_pages should never raise
                logger.warning("landing-page fetch failed: %s", e)
                block = ""
            # Record the fetch into the manifest + set page_verified so the
            # claim gate can trace (or reject) page-state assertions (Epic 4).
            page_verified = bool(block)
            if block:
                try:
                    manifest.add_page_fetch(block, now_iso)
                except Exception as _e:
                    logger.debug("manifest page_fetch add skipped: %s", _e)
            yield {"type": "verification", "payload": {
                "kind": "landing_page",
                "status": "verified" if block else "failed",
                "detail": (block[:400] if block else "could not fetch")}}
            if block:
                premise_block = ("\n\nVERIFIED PREMISE (live landing-page state, "
                                 "fetched this turn):\n" + block[:1500] + "\n")
            else:
                premise_block = ("\n\nUNVERIFIED: landing-page state could NOT be "
                                 "fetched this turn — do NOT assert page facts.\n")
        else:
            yield {"type": "verification", "payload": {
                "kind": "landing_page", "status": "skipped", "detail": ""}}

        # ── S2b: live conversion-action registry (Fix 4) ──────────────
        # One cheap, account-scoped, read-only GAQL pull EVERY orchestrated turn.
        # The block is injected into the Director's context so it SUPERSEDES any
        # stale/remembered conversion registry; it is tagged LIVE_API so the
        # claim gate can verify conversion-action claims. A fetch failure degrades
        # silently (status=failed) and never aborts the turn.
        conv_block = ""
        try:
            conv_block, conv_rows = await fetch_conversion_actions(account_id)
        except Exception as e:  # fetch_conversion_actions should never raise
            logger.warning("conversion-action fetch failed: %s", e)
            conv_block, conv_rows = "", []
        if conv_block:
            try:
                manifest.add_live_api(
                    conv_block, now_iso, tool_name="conversion_action_gaql")
            except Exception as _e:
                logger.debug("manifest conversion add skipped: %s", _e)
            premise_block += "\n\n" + conv_block + "\n"
            yield {"type": "verification", "payload": {
                "kind": "conversion_actions", "status": "verified",
                "detail": conv_block[:400]}}
        else:
            yield {"type": "verification", "payload": {
                "kind": "conversion_actions", "status": "failed",
                "detail": "could not fetch"}}

        # ══ S3 PLAN ════════════════════════════════════════════════════
        roster = [
            f"- {r['id']} ({r['name']}): {r['specialty']}"
            for r in list_roles() if r["id"] != "director"
        ]
        prior_lines = []
        for e in entries:
            prior_lines.append(
                f"- [{e.get('decision')}] {e.get('role_id')} · {e.get('source')} · "
                f"{(e.get('summary') or '')[:140]}")
        prior_block = ("\n\nPRIOR WORK (reuse = cite it, do NOT redo; reverify = "
                       "may re-run):\n" + "\n".join(prior_lines)) if prior_lines else ""
        max_spec = int(settings.CHAT_ORCH_MAX_SPECIALISTS)
        # Registry-grounded catalog of REAL tool names — reused for the plan
        # prompt AND (if needed) the corrective re-ask. A plan must name execution
        # tools BY EXACT NAME from this catalog; a server name grants nothing.
        catalog_block = await _format_tool_catalog()
        plan_prompt = (
            "You are the Marketing Director planning a focused multi-specialist "
            "response to ONE user question about this campaign.\n\n"
            f"USER QUESTION: {user_message}\n\n"
            "Available specialists (pick only the ones that fit; tailor each "
            "task):\n" + "\n".join(roster) + prior_block + premise_block +
            catalog_block +
            "\n\nDo NOT dispatch a specialist to redo work marked reuse — cite it "
            f"instead. Use at most {max_spec} specialists. Prefer tools=[] "
            "(analysis over data already in context); when execution IS needed, "
            "grant the exact write tool name(s) from the catalog above.\n\n"
            "Respond with ONLY a JSON object, no prose:\n"
            "```json\n"
            "{\n"
            '  "specialists": [\n'
            '    {"role_id": "ppc_strategist", "model": "sonnet", "tools": [], "task": "...", "reason": "..."}\n'
            "  ]\n"
            "}\n```"
        )
        plan_parts: list[str] = []
        async for ev in stream_agent_response(
            user_message=plan_prompt, model="fable", active_role="director",
            tool_allowlist=[], account_id=account_id, campaign_id=campaign_id,
            campaign_name=campaign_name, conversation_id=conversation_id,
        ):
            if ev.get("type") in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                plan_parts.append(ev.get("content", ""))
            elif ev.get("type") == "done":
                total_cost += float(ev.get("cost") or 0.0)
        parsed_plan = _extract_json("".join(plan_parts))
        raw_specs = parsed_plan.get("specialists") if parsed_plan else None

        if not raw_specs or not isinstance(raw_specs, list):
            # DEGRADE to DIRECT — no default 3-specialist ritual.
            yield {"type": "director_thought", "payload": {
                "text": "Plan was empty/unparseable — degrading to a direct answer.",
                "stage": "plan"}}
            async for ev in _run_direct(
                turn_id=turn_id, user_message=user_message, account_id=account_id,
                campaign_id=campaign_id, campaign_name=campaign_name,
                conversation_id=conversation_id, base_guidelines=base_guidelines,
                campaign_guidelines=campaign_guidelines, model=model,
                active_role="director", cost_so_far=total_cost,
            ):
                yield ev
            return

        def _build_specs(raw: list | None) -> list[dict]:
            """Parse Director plan `specialists` into runnable specs. Reused for
            the corrective re-ask so the two paths can't drift."""
            out: list[dict] = []
            for s in (raw or [])[:max_spec]:
                if not isinstance(s, dict) or not s.get("role_id"):
                    continue
                role = get_role(s["role_id"])
                spec_entry = {
                    "call_id": f"c{len(out) + 1}",
                    "role_id": s["role_id"],
                    "role_name": role.name if role else s["role_id"],
                    "task": (s.get("task") or user_message or "") + _V2_FINDINGS_SUFFIX,
                    "model": s.get("model") or "sonnet",
                    "tools": s.get("tools") or [],
                    "reason": s.get("reason") or "",
                    # honor an explicit plan flag when present (see _detect_write_intent)
                    "write_intent": s.get("write_intent"),
                }
                # Fix 1: pin write-intent per spec so the stop path can report a
                # per-specialist disposition (an approved write must never die silently).
                spec_entry["write_intent"] = _detect_write_intent(spec_entry)
                out.append(spec_entry)
            return out

        specs = _build_specs(raw_specs)

        if not specs:
            yield {"type": "director_thought", "payload": {
                "text": "No valid specialists — degrading to a direct answer.",
                "stage": "plan"}}
            async for ev in _run_direct(
                turn_id=turn_id, user_message=user_message, account_id=account_id,
                campaign_id=campaign_id, campaign_name=campaign_name,
                conversation_id=conversation_id, base_guidelines=base_guidelines,
                campaign_guidelines=campaign_guidelines, model=model,
                active_role="director", cost_so_far=total_cost,
            ):
                yield ev
            return

        # ── Plan execution-grant contract (2026-07-20 interface-contract bug) ──
        # The Director's plan may name an MCP SERVER ('google-ads') instead of an
        # exact TOOL name; a server name grants NO tool BY NAME, so a user-APPROVED
        # write is silently stranded (5× TOOL_NOT_ALLOWED — no seat could execute).
        # Resolve every plan `tools` entry against the LIVE registry; on any
        # unresolved / server-name entry, re-ask the Director ONCE with the real
        # catalog, then (if still invalid) STRIP the bad entries and surface a
        # PROMINENT ledger event so an approved batch can never silently strand.
        invalid_tools = await _validate_plan_tools(specs)
        if invalid_tools:
            yield {"type": "director_thought", "payload": {
                "text": ("Plan named tools that aren't real execution tools: "
                         f"{', '.join(invalid_tools)}. Re-asking the Director to "
                         "use exact tool names from the catalog."),
                "stage": "plan"}}
            reask_prompt = _plan_reask_prompt(plan_prompt, invalid_tools, catalog_block)
            reask_parts: list[str] = []
            async for ev in stream_agent_response(
                user_message=reask_prompt, model="fable", active_role="director",
                tool_allowlist=[], account_id=account_id, campaign_id=campaign_id,
                campaign_name=campaign_name, conversation_id=conversation_id,
            ):
                if ev.get("type") in ("text", "text_delta"):
                    reask_parts.append(ev.get("content", ""))
                elif ev.get("type") == "done":
                    total_cost += float(ev.get("cost") or 0.0)
            reask_plan = _extract_json("".join(reask_parts))
            reask_specs = _build_specs(
                reask_plan.get("specialists") if reask_plan else None)
            if reask_specs:
                specs = reask_specs
            invalid_tools = await _validate_plan_tools(specs)
            if invalid_tools:
                # Still invalid after ONE re-ask: STRIP the bad entries (reads stay
                # whitelisted) and surface a PROMINENT, machine-detectable ledger
                # event so an approved write can never again die as a mystery
                # TOOL_NOT_ALLOWED. Valid entries survive → real mutates still land.
                _bad = set(invalid_tools)
                for s in specs:
                    s["tools"] = [t for t in (s.get("tools") or []) if str(t) not in _bad]
                _bad_list = ", ".join(sorted(_bad))
                yield {"type": "director_thought", "payload": {
                    "text": (f"⚠️ Plan authorized unknown tools {_bad_list} — "
                             "execution will be BLOCKED for those. Proceeding with "
                             "read-only tools; an approved write cannot land until "
                             "the plan names exact tool names."),
                    "stage": "plan"}}
                yield {"type": "verification", "payload": {
                    "kind": "plan_tools", "status": "failed",
                    "detail": (f"plan authorized unknown tools {_bad_list} — "
                               "execution will be blocked")}}

        yield {"type": "director_thought", "payload": {
            "text": f"Plan ready · {len(specs)} specialist(s).", "stage": "plan"}}
        yield {"type": "plan", "payload": {
            "specialists": [
                {"call_id": s["call_id"], "role_id": s["role_id"],
                 "role_name": s["role_name"], "task": s["task"],
                 "model": s["model"], "tools": s["tools"], "reason": s["reason"],
                 "write_intent": s["write_intent"]}
                for s in specs
            ],
            "parallel_groups": [[s["call_id"] for s in specs]],
        }}

        # ── Fail-loud allowlist audit (money-bug 2026-07-16) ───────────────
        # Every specialist's effective allowlist is checked against the LIVE MCP
        # registry BEFORE dispatch. If an entry matches no registered tool, a
        # name-convention drift (e.g. `search__execute_query` vs the live
        # `search_execute_query`) has silently severed tooling — surface it as a
        # visible verification event on the ledger instead of a mystery block
        # that once let a campaign waste ~$131/week. Deduped across specialists.
        _audit_entries = sorted({
            e for s in specs
            for e in _specialist_tool_allowlist(s.get("tools") or [])
        })
        for _entry in await _audit_tool_allowlist(_audit_entries):
            yield {"type": "verification", "payload": {
                "kind": "tool_allowlist", "status": "failed",
                "detail": (f"tool allowlist entry '{_entry}' matches no "
                           f"registered tool")}}

        # ══ S4 DISPATCH ════════════════════════════════════════════════
        from app.services.workflow_orchestrator import _MAX_PARALLEL

        # RUNAWAY BACKSTOP caps (not a pacing limit — see config). The turn only
        # degrades/wraps-up at these; the $5 watch level below is informational.
        budget_cost = float(settings.CHAT_ORCH_COST_CAP_USD)
        budget_secs = float(settings.CHAT_ORCH_MAX_RUNTIME_MIN) * 60.0
        # $5 WATCH level — crossing it (while still under the backstop) emits ONE
        # informational budget_notice(kind="notice") and the turn KEEPS running.
        cost_notice_usd = float(getattr(settings, "CHAT_ORCH_COST_NOTICE_USD", 0) or 0.0)
        # Fix 1(b): ring-fence headroom for S6 SYNTHESIZE + S7 GATE. DISPATCH is
        # cut short once cost/time reaches (cap - reserve), so the Director's
        # final reconciled answer always has room to finish — the turn never ends
        # mid-synthesis.
        reserve_usd = float(getattr(settings, "CHAT_ORCH_SYNTH_RESERVE_USD", 0) or 0.0)
        reserve_secs = float(getattr(settings, "CHAT_ORCH_SYNTH_RESERVE_SEC", 0) or 0.0)
        dispatch_cost_cap = max(0.0, budget_cost - reserve_usd)
        dispatch_secs_cap = max(0.0, budget_secs - reserve_secs)
        sem = asyncio.Semaphore(_MAX_PARALLEL)
        out: asyncio.Queue = asyncio.Queue()
        findings_by_call: dict[str, list[dict]] = {}
        role_by_call: dict[str, str] = {}
        summary_by_call: dict[str, str] = {}
        degraded = False
        budget_notice_emitted = False   # the BACKSTOP (kind="stop") notice
        notice_emitted = False          # the $5 WATCH (kind="notice") notice

        async def _guarded(spec, seq):
            async with sem:
                await _dispatch_specialist(
                    spec, turn_id=turn_id, out=out, account_id=account_id,
                    campaign_id=campaign_id, campaign_name=campaign_name,
                    conversation_id=conversation_id, seq=seq)

        tasks = [asyncio.create_task(_guarded(s, i)) for i, s in enumerate(specs)]
        gather_task = asyncio.gather(*tasks, return_exceptions=True)

        while not gather_task.done() or not out.empty():
            # Ring-fence backstop — cancel outstanding work at (cap - reserve),
            # keeping findings in hand + reserving budget for synthesis. Emits a
            # VISIBLE budget_notice ledger event (Fix 1a) so the user sees why the
            # dispatch stopped short.
            _elapsed = time.monotonic() - turn_started
            if not degraded and (
                total_cost >= dispatch_cost_cap or _elapsed >= dispatch_secs_cap
            ):
                degraded = True
                for t in tasks:
                    if not t.done():
                        t.cancel()
                budget_notice_emitted = True
                yield {"type": "budget_notice", "payload": _budget_snapshot(
                    kind="stop",
                    reason=("cost" if total_cost >= dispatch_cost_cap else "time"),
                    total_cost=total_cost, elapsed_s=_elapsed,
                    budget_cost=budget_cost, budget_secs=budget_secs,
                    specialists_done=len(findings_by_call),
                    specialists_total=len(specs))}
            try:
                item = await asyncio.wait_for(out.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            itype = item.get("type")
            if itype == "agent_start":
                role_by_call[item["call_id"]] = item["role_id"]
                yield {"type": "agent_called", "payload": {
                    "call_id": item["call_id"], "role_id": item["role_id"],
                    "role_name": item["role_name"], "task": item["task"],
                    "model": item["model"], "tools": item["tools"],
                    "write_intent": bool(item.get("write_intent"))}}
            elif itype == "agent_text":
                yield {"type": "agent_progress", "payload": {
                    "call_id": item["call_id"], "kind": "text",
                    "content": item["content"]}}
            elif itype == "agent_tool":
                yield {"type": "agent_progress", "payload": {
                    "call_id": item["call_id"], "kind": "tool",
                    "tool": item["tool"]}}
            elif itype == "agent_done":
                total_cost += float(item.get("cost") or 0.0)
                findings_by_call[item["call_id"]] = item.get("findings", [])
                summary_by_call[item["call_id"]] = item.get("summary", "")
                # Harvest this specialist's LIVE tool outputs into the manifest
                # so any IDs they surfaced count as LIVE_API-verified (Epic 4).
                for tout in item.get("tool_outputs", []) or []:
                    try:
                        manifest.add_live_api(
                            tout.get("output", ""), now_iso,
                            tool_name=tout.get("name", ""))
                    except Exception as _e:
                        logger.debug("manifest live_api add skipped: %s", _e)
                yield {"type": "agent_result", "payload": {
                    "call_id": item["call_id"], "role_id": item["role_id"],
                    "status": item.get("status", "ok"), "cost": item.get("cost", 0.0),
                    "duration_ms": item.get("duration_ms", 0),
                    "findings": item.get("findings", []),
                    "summary": item.get("summary", "")}}
                # $5 WATCH level (Wassim: on CLI/subscription, no hard limit — just
                # SHOW when a turn gets expensive). One-shot, cost-only, emitted the
                # moment total cost first crosses the watch level while still under
                # the backstop cap. Does NOT cancel/degrade — the turn keeps running.
                if not notice_emitted and cost_notice_usd <= total_cost < budget_cost:
                    notice_emitted = True
                    yield {"type": "budget_notice", "payload": _budget_snapshot(
                        kind="notice", reason="cost",
                        total_cost=total_cost,
                        elapsed_s=time.monotonic() - turn_started,
                        budget_cost=cost_notice_usd, budget_secs=budget_secs,
                        specialists_done=len(findings_by_call),
                        specialists_total=len(specs))}

        try:
            await gather_task
        except Exception:
            pass

        # ══ S5 RESOLVE — deterministic conflict detection ══════════════
        flat: list[dict] = []
        for call_id, fs in findings_by_call.items():
            for f in fs:
                flat.append({"call_id": call_id, "finding": f})
        # Harvest specialist-cited IDs into the manifest (Epic 4) — tagged by
        # the source each finding cites (live/api → LIVE_API, local/store →
        # LOCAL_STORE, else MEMORY).
        try:
            manifest.add_from_findings([f["finding"] for f in flat], now_iso)
        except Exception as _e:
            logger.debug("manifest findings add skipped: %s", _e)
        conflicts: list[dict] = []
        cf_n = 0
        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                a, b = flat[i], flat[j]
                if a["call_id"] == b["call_id"]:
                    continue
                ca = a["finding"].get("claim", "")
                cb = b["finding"].get("claim", "")
                shared = _claim_tokens(ca) & _claim_tokens(cb)
                sa, sb = _stance(ca), _stance(cb)
                if len(shared) >= 2 and _opposing(sa, sb):
                    cf_n += 1
                    cf_id = f"cf{cf_n}"
                    conflicts.append({
                        "id": cf_id,
                        "between": [a["call_id"], b["call_id"]],
                        "topic": " ".join(sorted(shared)),
                        "positions": [
                            {"call_id": a["call_id"], "stance": sa},
                            {"call_id": b["call_id"], "stance": sb}],
                    })
                    yield {"type": "conflict", "payload": conflicts[-1]}
        if conflicts:
            yield {"type": "director_thought", "payload": {
                "text": f"Detected {len(conflicts)} conflict(s) to reconcile.",
                "stage": "resolve"}}

        # ══ S6 SYNTHESIZE ══════════════════════════════════════════════
        # Fix 1(a): if the cap is truly blown by now (the reserve got eaten too),
        # do NOT spend more on an LLM synthesis that could run past the cap and be
        # cut mid-sentence — compose a COMPLETE wrap-up from state instead. The
        # ring-fence above makes this rare; this is the belt-and-suspenders that
        # guarantees the turn ends on a whole thought.
        _elapsed_s = time.monotonic() - turn_started
        budget_blown = total_cost >= budget_cost or _elapsed_s >= budget_secs
        yield {"type": "final_start", "payload": {}}
        final_parts: list[str] = []
        did_llm_synth = False
        if budget_blown:
            if not budget_notice_emitted:
                budget_notice_emitted = True
                yield {"type": "budget_notice", "payload": _budget_snapshot(
                    kind="stop",
                    reason=("cost" if total_cost >= budget_cost else "time"),
                    total_cost=total_cost, elapsed_s=_elapsed_s,
                    budget_cost=budget_cost, budget_secs=budget_secs,
                    specialists_done=len(findings_by_call),
                    specialists_total=len(specs))}
            wrap = _compose_budget_wrapup(
                specs, findings_by_call, summary_by_call, conflicts)
            final_parts.append(wrap)
            yield {"type": "final_chunk", "payload": {"content": wrap}}
        else:
            did_llm_synth = True
            findings_json = json.dumps(
                {cid: fs for cid, fs in findings_by_call.items()}, indent=2)[:4000]
            conflicts_json = json.dumps(conflicts, indent=2) if conflicts else "[]"
            synth_prompt = (
                "You are the Marketing Director. Reconcile the specialists' "
                "findings into ONE answer, in a single voice, for the user's "
                "question.\n\n"
                f"USER QUESTION: {user_message}\n" + prior_block + premise_block +
                "\n\nSPECIALIST FINDINGS (JSON):\n" + findings_json +
                "\n\nCONFLICTS the team flagged (JSON):\n" + conflicts_json +
                "\n\nWrite the reconciled answer in prose. Cite prior work marked "
                "reuse instead of re-deriving it."
            )
            if conflicts:
                synth_prompt += (
                    "\n\nAfter the prose, emit ONE fenced JSON block resolving each "
                    "conflict:\n```json\n"
                    '{"decisions":[{"conflict_id":"cf1","ruling":"...","rationale":"..."}]}\n```'
                )
            async for ev in stream_agent_response(
                user_message=synth_prompt, model=(model or "fable"),
                active_role="director", tool_allowlist=[], account_id=account_id,
                campaign_id=campaign_id, campaign_name=campaign_name,
                conversation_id=conversation_id,
            ):
                etype = ev.get("type")
                if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                    chunk = ev.get("content", "")
                    final_parts.append(chunk)
                    yield {"type": "final_chunk", "payload": {"content": chunk}}
                elif etype == "done":
                    total_cost += float(ev.get("cost") or 0.0)
        final_text = "".join(final_parts)

        # Parse + emit conflict rulings (only the LLM synthesis emits the JSON).
        if conflicts and did_llm_synth:
            dparsed = _extract_json(final_text)
            if dparsed and isinstance(dparsed.get("decisions"), list):
                for d in dparsed["decisions"]:
                    if not isinstance(d, dict):
                        continue
                    yield {"type": "decision", "payload": {
                        "conflict_id": d.get("conflict_id"),
                        "ruling": d.get("ruling", ""),
                        "rationale": d.get("rationale", ""),
                        "decided_by": "director"}}

        # ══ S7 GATE — deterministic claim gate (Epic 4) ════════════════
        # Runs on the Director's final BEFORE persistence: unverified IDs and
        # unbacked page-state assertions are rewritten in place; the PERSISTED
        # message is the GATED text. A gate failure must never abort the turn.
        gate_event = {"checked": 0, "passed": 0, "rewritten": [], "flagged": []}
        try:
            gate = run_claim_gate(final_text, manifest, page_verified)
            final_text = gate["text"]
            gate_event = gate["event"]
        except Exception as e:
            logger.warning("claim gate failed (persisting raw text): %s", e)

        # Persist ONLY the Director synthesis (GATED text) as the assistant
        # message. A persist failure must NOT abort the turn (final_done still
        # emits). The persona is captured in locals so the PERSISTED row and the
        # final_done event agree BY CONSTRUCTION — an orchestrated turn's message
        # must carry the Director persona, not fall back to a bare "Assistant" in
        # a live-session export (2026-07-20 export-labeling bug).
        synth_role_id = "director"
        synth_role_name = "Marketing Director"
        try:
            message_id = await _persist_assistant_message(
                conversation_id=conversation_id, content=final_text, tool_calls=None,
                agent_role_id=synth_role_id, agent_role_name=synth_role_name,
                campaign_id=campaign_id, turn_id=turn_id)
        except Exception as e:
            logger.warning("synthesis persist failed: %s", e)
            message_id = str(uuid.uuid4())
        turn_ms = int((time.monotonic() - turn_started) * 1000)
        yield {"type": "final_done", "payload": {
            "message_id": message_id, "cost_total": round(total_cost, 4),
            "duration_ms": turn_ms, "agents_used": len(specs),
            "conflicts_resolved": len(conflicts),
            # persona for the live bubble → export uses the display name, not "Assistant"
            "agent_role": synth_role_id, "agent_role_name": synth_role_name}}

        # Emit the real claim_gate event (shape {checked, passed, rewritten,
        # flagged}; the frontend type keys off checked/passed/rewritten).
        yield {"type": "claim_gate", "payload": gate_event}

        # ══ S8 WRITEBACK — append findings to role notes ═══════════════
        # (Session summary / chronicle writeback DEFERRED — Epic 3+.)
        try:
            from app.services.campaign_memory import append_role_notes

            for s in specs:
                cid = s["call_id"]
                fs = findings_by_call.get(cid, [])
                summ = summary_by_call.get(cid, "")
                note = json.dumps({"summary": summ, "findings": fs}, indent=2)[:2000]
                try:
                    append_role_notes(account_id, campaign_id, s["role_id"], note,
                                      section_title="Orchestrated finding")
                except Exception as e:
                    logger.debug("writeback skipped for %s: %s", s["role_id"], e)
        except Exception as e:
            logger.debug("writeback import failed: %s", e)

        # ══ TERMINAL ═══════════════════════════════════════════════════
        yield {"type": "turn_done", "payload": {
            "stop_reason": "natural", "cost": round(total_cost, 4)}}

    except Exception as e:
        logger.exception("orchestrate turn failed: %s", e)
        yield {"type": "turn_done", "payload": {
            "stop_reason": "error", "cost": round(total_cost, 4)}}
