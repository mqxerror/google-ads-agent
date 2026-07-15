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
    """Mirror chat.py's _direct_run_fn: stream one Director/persona answer,
    translate events, persist the assistant message, end with turn_done."""
    from app.services.agent import stream_agent_response

    full_text_parts: list[str] = []
    tool_calls_json: list[dict] = []
    agent_role_id: Optional[str] = active_role
    agent_role_name: Optional[str] = None
    cost = cost_so_far
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
            payload = {k: v for k, v in event.items() if k != "type"}
            if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                full_text_parts.append(event.get("content", ""))
            elif etype == "tool_call":
                tool_calls_json.append(event)
            elif etype == "routing":
                agent_role_id = event.get("role_id") or agent_role_id
                agent_role_name = event.get("role_name")
            elif etype == "done":
                cost += float(event.get("cost") or 0.0)
            yield {"type": etype, "payload": payload}
    finally:
        full_text = "".join(full_text_parts)
        try:
            await _persist_assistant_message(
                conversation_id=conversation_id, content=full_text,
                tool_calls=tool_calls_json or None,
                agent_role_id=agent_role_id, agent_role_name=agent_role_name,
                campaign_id=campaign_id, turn_id=turn_id,
            )
        except Exception as e:  # persistence must never break the stream
            logger.warning("direct-path persist failed: %s", e)
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
    tools = spec.get("tools", []) or []

    await out.put({
        "type": "agent_start", "call_id": call_id, "role_id": role_id,
        "role_name": role_name, "task": task, "model": model, "tools": tools,
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
    go_direct = (
        force_mode == "direct"
        or intent.get("gear") == 1
        or (force_mode != "orchestrate" and is_greeting)
    )
    needs: list[str] = []

    if force_mode == "orchestrate":
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
        from app.services.agent import fetch_ad_landing_pages, stream_agent_response
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
        plan_prompt = (
            "You are the Marketing Director planning a focused multi-specialist "
            "response to ONE user question about this campaign.\n\n"
            f"USER QUESTION: {user_message}\n\n"
            "Available specialists (pick only the ones that fit; tailor each "
            "task):\n" + "\n".join(roster) + prior_block + premise_block +
            "\n\nDo NOT dispatch a specialist to redo work marked reuse — cite it "
            f"instead. Use at most {max_spec} specialists. Prefer tools=[] "
            "(analysis over data already in context).\n\n"
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

        specs: list[dict] = []
        for i, s in enumerate(raw_specs[:max_spec]):
            if not isinstance(s, dict) or not s.get("role_id"):
                continue
            role = get_role(s["role_id"])
            call_id = f"c{len(specs) + 1}"
            specs.append({
                "call_id": call_id,
                "role_id": s["role_id"],
                "role_name": role.name if role else s["role_id"],
                "task": (s.get("task") or user_message or "") + _V2_FINDINGS_SUFFIX,
                "model": s.get("model") or "sonnet",
                "tools": s.get("tools") or [],
                "reason": s.get("reason") or "",
            })

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

        yield {"type": "director_thought", "payload": {
            "text": f"Plan ready · {len(specs)} specialist(s).", "stage": "plan"}}
        yield {"type": "plan", "payload": {
            "specialists": [
                {"call_id": s["call_id"], "role_id": s["role_id"],
                 "role_name": s["role_name"], "task": s["task"],
                 "model": s["model"], "tools": s["tools"], "reason": s["reason"]}
                for s in specs
            ],
            "parallel_groups": [[s["call_id"] for s in specs]],
        }}

        # ══ S4 DISPATCH ════════════════════════════════════════════════
        from app.services.workflow_orchestrator import _MAX_PARALLEL

        budget_cost = float(settings.CHAT_ORCH_MAX_COST_USD)
        budget_secs = float(settings.CHAT_ORCH_MAX_RUNTIME_MIN) * 60.0
        sem = asyncio.Semaphore(_MAX_PARALLEL)
        out: asyncio.Queue = asyncio.Queue()
        findings_by_call: dict[str, list[dict]] = {}
        role_by_call: dict[str, str] = {}
        summary_by_call: dict[str, str] = {}
        degraded = False

        async def _guarded(spec, seq):
            async with sem:
                await _dispatch_specialist(
                    spec, turn_id=turn_id, out=out, account_id=account_id,
                    campaign_id=campaign_id, campaign_name=campaign_name,
                    conversation_id=conversation_id, seq=seq)

        tasks = [asyncio.create_task(_guarded(s, i)) for i, s in enumerate(specs)]
        gather_task = asyncio.gather(*tasks, return_exceptions=True)

        while not gather_task.done() or not out.empty():
            # Budget backstop — cancel outstanding work, keep findings in hand.
            if not degraded and (
                total_cost >= budget_cost
                or (time.monotonic() - turn_started) >= budget_secs
            ):
                degraded = True
                for t in tasks:
                    if not t.done():
                        t.cancel()
                yield {"type": "director_thought", "payload": {
                    "text": "Budget/time cap hit — synthesizing with findings so far.",
                    "stage": "resolve"}}
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
                    "model": item["model"], "tools": item["tools"]}}
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
        findings_json = json.dumps(
            {cid: fs for cid, fs in findings_by_call.items()}, indent=2)[:4000]
        conflicts_json = json.dumps(conflicts, indent=2) if conflicts else "[]"
        synth_prompt = (
            "You are the Marketing Director. Reconcile the specialists' findings "
            "into ONE answer, in a single voice, for the user's question.\n\n"
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
        yield {"type": "final_start", "payload": {}}
        final_parts: list[str] = []
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

        # Parse + emit conflict rulings.
        if conflicts:
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
        # emits).
        try:
            message_id = await _persist_assistant_message(
                conversation_id=conversation_id, content=final_text, tool_calls=None,
                agent_role_id="director", agent_role_name="Marketing Director",
                campaign_id=campaign_id, turn_id=turn_id)
        except Exception as e:
            logger.warning("synthesis persist failed: %s", e)
            message_id = str(uuid.uuid4())
        turn_ms = int((time.monotonic() - turn_started) * 1000)
        yield {"type": "final_done", "payload": {
            "message_id": message_id, "cost_total": round(total_cost, 4),
            "duration_ms": turn_ms, "agents_used": len(specs),
            "conflicts_resolved": len(conflicts)}}

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
