"""Video Director agent — the run_fn that owns the AI Video Studio flow.

This is the AGENT layer (a sibling of `chat_orchestrator.run_turn`): it rides
`chat_runner.start(run_fn, ...)` for free turn rows, monotonic-seq envelopes,
batched persistence, SSE replay, and per-turn stop. It orchestrates AROUND the
studio services — it MAY import `campaign_memory`, `roles`, `prompt_drafter`,
`model_catalog`, `agent.stream_agent_response`, `database.get_db` — but it does
NOT import any google_ads code (the standalone-product decoupling invariant,
plan §0.2 / §6.1).

State machine (plan §6.3), yielding BARE {type, payload} dicts:

  V0 CONTEXT    load the project row + (when linked) campaign memory.
  V1 CONSULT    (conditional §6.4) ONE scoped call to the campaign Director —
                degrades to pinned-facts-only, NEVER blocks drafting.
  V2 DECOMPOSE  prompt_drafter._stage1_decompose over the brief + consult block.
  V3 CONCEPT    3 angle loglines (problem-led / aspirational / social-proof) —
                the initial-draft turn ENDS here (operator picks an angle).
  V4 STORYBOARD model-aware expansion, SERVER-SIDE VALIDATED (the LLM only
                describes the contract; clamp_duration + the ≤8 cap + the ±1
                deviation rule ENFORCE it), persisted to the row (DB = truth).
  V5 WRITEBACK  append a one-para note to the campaign's role_notes when linked.

Cost + render live entirely OUTSIDE this turn (plan §6.3): a stop/crash in
drafting can never burn Higgsfield credits.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from app.database import get_db
from app.services import prompt_drafter
from app.services.higgsfield_scene import MAX_HIGGSFIELD_SCENES
from app.services.model_catalog import clamp_duration, get_model, plan_scenes
from app.services.roles import ROLES

logger = logging.getLogger(__name__)


# ── Seams / constants ─────────────────────────────────────────────────

# Seam: set when Higgsfield ships a lipsync model — the non-lipsync presenter
# pipeline stays as-is until then.
AVATAR_SPEAK_MODEL = None

# The campaign consult is a single scoped call; cap it hard so a slow/dead
# Director never stalls drafting (plan §6.3 V1).
_CONSULT_TIMEOUT_S = 90.0

# Video-director drafting (V2 decompose / V3 concepts / V4 storyboard) folds the
# whole campaign-context block into the Claude call, so it legitimately runs
# longer than prompt_drafter's tight image-drafting budget (45s). Cap it here so
# a genuinely slow draft still fails gracefully rather than dead-ending the turn.
_DRAFT_STAGE_TIMEOUT_S = 150.0

# Human-facing copy for a draft-stage timeout — the frontend renders this next
# to a Retry button (CHANGE 1 (c)/(d)). MUST match the string the UI expects.
_DRAFT_TIMEOUT_MESSAGE = (
    "The Director took too long drafting — this can happen with heavy campaign "
    "context. Retry."
)


def _draft_timeout_event() -> dict:
    """Structured, retryable turn_error for a draft-stage timeout. DirectorDock
    already handles `turn_error`; the extra `retryable`/`stage` fields let the
    UI surface a Retry button without a new event type (CHANGE 1 (c))."""
    return {"type": "turn_error", "payload": {
        "message": _DRAFT_TIMEOUT_MESSAGE,
        "retryable": True,
        "stage": "draft-timeout",
    }}

# Spoken pace (~2.5 words/sec) → per-scene VO word budget.
_WORDS_PER_SECOND = 2.5


# ── LLM helper (the single monkeypatch seam for tests) ────────────────


async def _draft_llm(system: str, user: str, model: str = "sonnet") -> str:
    """Every concept/storyboard model call routes through here so ONE
    monkeypatch (in tests) covers them all. Mirrors how prompt_drafter
    isolates its own `_claude_one_shot`. Uses the longer video-draft budget
    (_DRAFT_STAGE_TIMEOUT_S) because these calls carry the full campaign
    context — the 45s image budget dead-ends them (CHANGE 1)."""
    return await prompt_drafter._claude_one_shot(
        system=system, user=user, model=model, timeout_s=_DRAFT_STAGE_TIMEOUT_S,
    )


# ── Small helpers ─────────────────────────────────────────────────────


def _count_pinned(pinned_facts: str) -> int:
    """Count non-empty, non-comment bullet lines in a pinned_facts.md blob."""
    n = 0
    for line in (pinned_facts or "").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("<!--"):
            continue
        if s.startswith("-") or s.startswith("*"):
            n += 1
    return n


def _pinned_claims_covered(claim_hints: list[str], pinned_facts: str) -> bool:
    """True iff EVERY claim hint is covered by the pinned facts via a
    case-folded string-containment check (plan §6.4 auto-trigger)."""
    haystack = (pinned_facts or "").casefold()
    for hint in claim_hints or []:
        needle = str(hint or "").strip().casefold()
        if needle and needle not in haystack:
            return False
    return True


def _video_director_system() -> str:
    """The registered video_director system prompt (RULE 0, VO tables, the
    JSON output contract). Ground truth lives in roles.py."""
    return ROLES["video_director"].system_prompt


async def _load_project(project_id: str) -> dict[str, Any] | None:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM studio_video_projects WHERE id = ?", (project_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def _persist_storyboard(project_id: str, storyboard: dict[str, Any]) -> None:
    """Persist the validated storyboard + flip status to 'storyboard'.
    DB row is the source of truth — the `storyboard` event is a view of it."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE studio_video_projects "
            "SET storyboard_json = ?, status = 'storyboard', "
            "updated_at = datetime('now') WHERE id = ?",
            (json.dumps(storyboard), project_id),
        )
        await db.commit()
    finally:
        await db.close()


# ── Storyboard validation — the ENFORCEMENT (LLM only describes) ──────


def _validate_storyboard(
    raw: dict[str, Any], *, model_id: str, target_seconds: int
) -> dict[str, Any]:
    """Coerce + clamp the LLM's storyboard into something the render path can
    trust. The Director's prompt DESCRIBES the contract; this ENFORCES it.

    - clamp each scene duration via clamp_duration (Veo enum-snap, Kling int-cap)
    - cap the scene list at MAX_HIGGSFIELD_SCENES (8)
    - deviation from plan_scenes may be ±1: if the LLM returned more than
      plan+1, truncate to plan+1; fewer than plan-1 is allowed (don't pad)
    - renumber `n` sequentially 1..k after any edit
    - coerce on_screen_text to str-or-None; vo_full/title/music_mood → str
    """
    plan = plan_scenes(target_seconds, model_id)
    plan_len = len(plan)

    raw_scenes = raw.get("scenes")
    if not isinstance(raw_scenes, list):
        raw_scenes = []

    # ≤8 hard cap first (never let the list balloon before the ±1 math).
    scenes_in = raw_scenes[:MAX_HIGGSFIELD_SCENES]

    # ±1 deviation: more than plan+1 → truncate to plan+1. plan_len==0 means
    # the model can't be scene-planned (unknown/native-length) — trust the ≤8
    # cap alone in that case.
    if plan_len > 0:
        upper = min(plan_len + 1, MAX_HIGGSFIELD_SCENES)
        scenes_in = scenes_in[:upper]

    scenes_out: list[dict[str, Any]] = []
    for i, s in enumerate(scenes_in, start=1):
        if not isinstance(s, dict):
            continue
        requested = s.get("duration")
        try:
            requested_int = int(requested) if requested is not None else None
        except (TypeError, ValueError):
            requested_int = None
        duration = clamp_duration(model_id, requested_int)

        ost = s.get("on_screen_text")
        ost = None if ost is None else str(ost)

        scenes_out.append({
            "n": len(scenes_out) + 1,  # renumber sequentially 1..k
            "duration": duration,
            "visual_prompt": str(s.get("visual_prompt") or ""),
            "vo_line": str(s.get("vo_line") or ""),
            "on_screen_text": ost,
            "continuity": str(s.get("continuity") or ""),
        })
        # keep n aligned to sequential position (i is the raw index)
        _ = i

    return {
        "scenes": scenes_out,
        "vo_full": str(raw.get("vo_full") or ""),
        "music_mood": str(raw.get("music_mood") or ""),
        "title": str(raw.get("title") or ""),
    }


# ── V1 CONSULT ─────────────────────────────────────────────────────────


async def _run_consult(
    *, turn_id, account_id, campaign_id, campaign_name, conversation_id, brief: str,
) -> AsyncIterator[dict]:
    """ONE scoped call to the campaign Director, emitting the SAME
    agent_called/agent_progress/agent_result payloads chat_orchestrator uses so
    the dock renders it with existing chat components.

    Yields {type, payload} events AND a final sentinel dict with key
    "__consult_text__" carrying the accumulated brief text (or "" on failure).
    Never raises — degrades on timeout/exception (plan §6.3 V1).
    """
    from app.services.agent import stream_agent_response

    consult_brief = (
        "You are the campaign Director. A Video Director is about to draft a "
        "short video for this campaign and needs your guidance FIRST. In a tight "
        "brief (no preamble), give:\n"
        "1. AUDIENCE — who this video must speak to.\n"
        "2. ALLOWED CLAIMS — ONLY claims backed by the campaign's pinned facts; "
        "list them explicitly. Do not invent credibility.\n"
        "3. TONE — the register the campaign uses.\n"
        "4. LP PROMISE — the core promise the landing page makes.\n"
        "5. CURRENT CREATIVE ANGLE — how the campaign currently positions itself.\n"
        "6. ANYTHING TO AVOID — brands, claims, aesthetics that are off-limits.\n\n"
        f"Video brief context:\n{brief[:1500]}"
    )

    call_id = "consult"
    yield {"type": "agent_called", "payload": {
        "call_id": call_id, "role_id": "director", "role_name": "Marketing Director",
        "task": consult_brief, "model": "sonnet", "tools": [],
    }}

    parts: list[str] = []
    cost = 0.0
    started = asyncio.get_event_loop().time()

    async def _drain() -> None:
        nonlocal cost
        async for event in stream_agent_response(
            user_message=consult_brief,
            active_role="director",
            campaign_id=campaign_id,
            campaign_name=campaign_name or "",
            account_id=account_id,
            conversation_id=conversation_id,
            model="sonnet",
            tool_allowlist=[],
            proc_key=(turn_id, "consult"),
        ):
            etype = event.get("type")
            if etype in ("text", "text_delta"):  # text_delta = token-level (story 1.4)
                chunk = event.get("content", "")
                parts.append(chunk)
                _progress_q.put_nowait(chunk)
            elif etype == "done":
                cost = float(event.get("cost") or 0.0)

    # stream_agent_response text has to surface as agent_progress events on the
    # SAME async generator we're yielding from — bridge it through a queue.
    _progress_q: asyncio.Queue[str | None] = asyncio.Queue()

    async def _runner() -> None:
        try:
            await asyncio.wait_for(_drain(), timeout=_CONSULT_TIMEOUT_S)
        finally:
            _progress_q.put_nowait(None)  # sentinel

    task = asyncio.create_task(_runner())
    try:
        while True:
            chunk = await _progress_q.get()
            if chunk is None:
                break
            yield {"type": "agent_progress", "payload": {
                "call_id": call_id, "kind": "text", "content": chunk,
            }}
        await task  # surface timeout/exception here
    except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001 — degrade, never block
        logger.info("video_director consult degraded: %s", e)
        if not task.done():
            task.cancel()
        # DEGRADE (chat-hardening item 2): the consult degrading used to surface
        # only as a soft thought. Emit a prominent `degrade` ledger event too so
        # the dock renders (amber) that the draft is proceeding WITHOUT Director
        # guidance — a silent degrade is a future incident.
        _timed_out = isinstance(e, asyncio.TimeoutError)
        yield {"type": "degrade", "payload": {
            "stage": "consult", "what": "Campaign Director consult",
            "impact": "drafting from pinned facts only — no Director guidance this turn",
            "detail": ("timed out" if _timed_out else str(e)[:200])}}
        yield {"type": "director_thought", "payload": {
            "text": "Campaign Director unavailable — drafting from pinned facts only",
            "stage": "consult",
        }}
        yield {"__consult_text__": ""}
        return

    consult_text = "".join(parts).strip()
    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    yield {"type": "agent_result", "payload": {
        "call_id": call_id, "role_id": "director", "status": "ok",
        "cost": round(cost, 4), "duration_ms": duration_ms,
        "findings": [], "summary": consult_text[:4000],
    }}
    yield {"__consult_text__": consult_text}


# ── V3 CONCEPT ─────────────────────────────────────────────────────────


async def _draft_concepts(
    *, brief: dict[str, Any], pinned_facts: str, campaign_brief: str,
) -> list[dict[str, Any]]:
    """3 angle loglines (problem-led / aspirational / social-proof), ≤60 words
    each, via ONE sonnet call. Validated server-side to the fixed trio."""
    pinned_block = ""
    if pinned_facts.strip():
        pinned_block = (
            "\nPINNED CLAIMS (the ONLY credibility you may evoke):\n"
            + pinned_facts.strip() + "\n"
        )
    campaign_block = f"\nCAMPAIGN BRIEF:\n{campaign_brief.strip()}\n" if campaign_brief.strip() else ""

    user = (
        "Emit the THREE concept angles as LOGLINES ONLY (no storyboard yet). "
        "Each logline ≤60 words: hook + through-line + why-this-angle. Return "
        "ONLY a JSON object, no preamble, no markdown fence:\n"
        '{"variants":[{"angle":"problem-led","logline":"…","rationale":"…"},'
        '{"angle":"aspirational","logline":"…","rationale":"…"},'
        '{"angle":"social-proof","logline":"…","rationale":"…"}]}\n\n'
        "STRUCTURED BRIEF:\n"
        f"  subject:          {brief['subject']}\n"
        f"  setting:          {brief['setting']}\n"
        f"  value_prop:       {brief['value_prop']}\n"
        f"  audience:         {brief['audience']}\n"
        f"  tone:             {brief['tone']}\n"
        f"  program:          {brief['program']}\n"
        f"  hard_constraints: {brief['hard_constraints']}\n"
        f"  claim_hints:      {brief['claim_hints']}\n"
        f"{pinned_block}{campaign_block}"
    )
    raw = await _draft_llm(_video_director_system(), user, model="sonnet")
    parsed = prompt_drafter._parse_json_envelope(raw)
    by_angle: dict[str, dict[str, Any]] = {}
    for v in parsed.get("variants") or []:
        if isinstance(v, dict):
            angle = str(v.get("angle") or "").strip().lower()
            if angle:
                by_angle[angle] = v
    out: list[dict[str, Any]] = []
    for expected in ("problem-led", "aspirational", "social-proof"):
        v = by_angle.get(expected) or {}
        out.append({
            "angle": expected,
            "logline": str(v.get("logline") or "").strip(),
            "rationale": str(v.get("rationale") or "").strip(),
        })
    return out


# ── V4 STORYBOARD ──────────────────────────────────────────────────────


def _build_storyboard_user_prompt(
    *, model_id: str, target_seconds: int, aspect: str, angle: str,
    brief: dict[str, Any], pinned_facts: str, campaign_brief: str,
    current_storyboard: dict[str, Any] | None,
) -> str:
    plan = plan_scenes(target_seconds, model_id)
    m = get_model(model_id) or {}
    constraints = m.get("constraints") or {}
    strengths = str(m.get("strengths") or "")

    # (a) exact scene skeleton the render will use
    skeleton_lines = []
    for i, s in enumerate(plan, start=1):
        dur = s.get("duration")
        budget = int(round((dur or 0) * _WORDS_PER_SECOND)) if dur else "native"
        skeleton_lines.append(
            f"  scene {i}: duration {dur}s → VO budget ≈{budget} words"
        )
    skeleton = "\n".join(skeleton_lines) or "  (model has no plannable skeleton — one native-length clip)"

    # (b) model contract + strengths
    dtype = constraints.get("duration_type")
    durations = constraints.get("durations")
    max_d = constraints.get("max_duration")
    if dtype == "enum" and durations:
        legal = f"clips are EXACTLY one of {durations}s (enum) — write self-contained shots, do NOT rely on cross-clip continuity"
    elif dtype == "int" and max_d:
        legal = f"clips are any length up to {max_d}s (int-capped) — you MAY write one continuous evolving shot per clip"
    else:
        legal = "native single-clip length (no duration control)"
    contract = (
        f"MODEL: {model_id} — {legal}. Strength: {strengths or '(unspecified)'}. "
        f"Aspect: {aspect}."
    )

    pinned_block = ""
    if pinned_facts.strip():
        pinned_block = (
            "\nPINNED CLAIMS (the ONLY credibility you may evoke — never assert "
            "a claim outside this list):\n" + pinned_facts.strip() + "\n"
        )
    campaign_block = f"\nCAMPAIGN BRIEF:\n{campaign_brief.strip()}\n" if campaign_brief.strip() else ""

    iteration_block = ""
    if current_storyboard is not None:
        iteration_block = (
            "\nCURRENT STORYBOARD (iterate on this — return the FULL updated JSON, "
            "an idempotent replace; no patch language, no diffs):\n"
            + json.dumps(current_storyboard) + "\n"
        )

    return (
        "Produce the storyboard now. Obey the OUTPUT CONTRACT from your system "
        "prompt EXACTLY: a single fenced JSON block, no preamble, no prose after.\n\n"
        f"SELECTED ANGLE: {angle}\n\n"
        f"SCENE SKELETON (the render will use exactly this — obey the count and "
        f"per-scene durations, ±1 scene only via a legal merge/split):\n{skeleton}\n\n"
        f"{contract}\n"
        f"VO PACING: per-scene word budget = duration × {_WORDS_PER_SECOND} words. Never exceed it.\n"
        f"{pinned_block}{campaign_block}{iteration_block}\n"
        "STRUCTURED BRIEF:\n"
        f"  subject:          {brief['subject']}\n"
        f"  setting:          {brief['setting']}\n"
        f"  value_prop:       {brief['value_prop']}\n"
        f"  audience:         {brief['audience']}\n"
        f"  tone:             {brief['tone']}\n"
        f"  program:          {brief['program']}\n"
        f"  hard_constraints: {brief['hard_constraints']}\n"
    )


# ── The turn ──────────────────────────────────────────────────────────


async def video_director_turn(
    *, turn_id, project_id, message: str = "", brief_source: Any = None, **_
) -> AsyncIterator[dict]:
    """Drive one Video Director turn. Yields BARE {type, payload} dicts; the
    chat_runner stamps envelopes + persists. Called by chat_runner as
    run_fn(turn_id=..., **params).

    `brief_source` (dict | BriefSource | None, JSON-round-tripped by chat_runner)
    selects how the brief is seeded: None/text = existing behavior; `campaign`
    synthesizes a brief from campaign memory; `landing_page` grounds the brief
    in a fetched page (degrades to UNVERIFIED, never blocks, on fetch failure).
    Combinable — a campaign-linked project with a url feeds BOTH context blocks.
    """
    # Normalize defensively — chat_runner JSON-round-trips params, so this is
    # most likely a plain dict; tolerate a BriefSource-like object or None too.
    bs_type = "text"
    bs_url = None
    if brief_source is not None:
        if isinstance(brief_source, dict):
            bs_type = str(brief_source.get("type") or "text")
            bs_url = brief_source.get("url")
        else:  # BriefSource-like object
            bs_type = str(getattr(brief_source, "type", None) or "text")
            bs_url = getattr(brief_source, "url", None)

    message = (message or "").strip()
    is_iteration = bool(message) and not message.startswith("angle:")
    is_angle_jump = message.startswith("angle:")
    is_initial = not message

    # ══ V0 CONTEXT ═════════════════════════════════════════════════════
    project = await _load_project(project_id)
    if project is None:
        yield {"type": "turn_error", "payload": {"message": f"project {project_id} not found"}}
        return

    account_id = project["account_id"]
    campaign_id = project["campaign_id"]
    campaign_name = project.get("campaign_name") if isinstance(project, dict) else None
    model_id = project["model_id"]
    target_seconds = int(project["target_seconds"] or 30)
    aspect = project.get("aspect") or "16:9"
    brief_text = project.get("brief") or ""
    conversation_id = project["conversation_id"]
    consult_director = int(project.get("consult_director") or 0)
    current_storyboard = None
    if project.get("storyboard_json"):
        try:
            current_storyboard = json.loads(project["storyboard_json"])
        except (json.JSONDecodeError, TypeError):
            current_storyboard = None

    pinned_facts = ""
    profile_block = ""
    decisions_block = ""
    if campaign_id:
        from app.services import campaign_memory
        try:
            pinned_facts = campaign_memory.load_pinned_facts(account_id, campaign_id)
            profile_block = campaign_memory.load_profile(account_id, campaign_id)
            decisions_block = campaign_memory.load_decisions(account_id, campaign_id)
        except Exception as e:  # memory read must never crash the turn
            logger.info("video_director memory load failed: %s", e)

    n_pinned = _count_pinned(pinned_facts)
    plural = "fact" if n_pinned == 1 else "facts"
    ctx_msg = (
        f"Loaded campaign context · {n_pinned} pinned {plural}"
        if campaign_id else "No campaign linked · drafting from the brief only"
    )
    yield {"type": "director_thought", "payload": {"text": ctx_msg, "stage": "context"}}

    # ══ BRIEF SOURCE — synthesize / ground the brief (additive) ═══════
    # `source_block` is folded into the body the decomposer sees so the brief
    # can be seeded from a campaign or a landing page even when the operator
    # gave no brief text. It NEVER blocks: a failed page fetch degrades to an
    # UNVERIFIED verification event and drafting continues from whatever exists.
    source_block = ""

    # type == campaign: synthesize the brief from the campaign's guidelines
    # (profile), pinned facts + recent decisions. campaign_id presence was
    # enforced at the router (400 if absent); guard again defensively.
    if bs_type == "campaign" and campaign_id:
        synth_parts: list[str] = []
        if (profile_block or "").strip():
            synth_parts.append("CAMPAIGN GUIDELINES (profile):\n" + profile_block.strip()[:1500])
        if (pinned_facts or "").strip():
            synth_parts.append("PINNED FACTS:\n" + pinned_facts.strip()[:1500])
        if (decisions_block or "").strip():
            synth_parts.append("RECENT CAMPAIGN DECISIONS:\n" + decisions_block.strip()[:1500])
        if synth_parts:
            source_block += (
                "SYNTHESIZED CAMPAIGN BRIEF — anchor the video in these "
                "operator-verified campaign signals; do NOT invent claims "
                "outside them:\n\n" + "\n\n".join(synth_parts) + "\n"
            )

    # type == landing_page: fetch the page + inject its actual claims. url
    # presence was enforced at the router; degrade (never block) on failure.
    if bs_type == "landing_page" and (bs_url or "").strip():
        try:
            from app.services.page_fetcher import fetch
            page = await fetch(bs_url)
            status = getattr(page, "status", 0) or 0
            if not (200 <= int(status) < 300):
                raise RuntimeError(f"non-2xx status {status}")
            page_lines = [
                f"LANDING PAGE ({bs_url}) — anchor the copy in the page's ACTUAL claims:",
            ]
            if page.title:
                page_lines.append(f"Title: {page.title}")
            if page.h1:
                page_lines.append(f"H1: {page.h1}")
            if (page.body_excerpt or "").strip():
                page_lines.append("Page copy excerpt:\n" + page.body_excerpt.strip()[:1800])
            if source_block:
                source_block += "\n"
            source_block += "\n".join(page_lines) + "\n"
        except Exception as e:  # DEGRADE, never block
            logger.info("video_director landing-page fetch failed: %s", e)
            yield {"type": "verification", "payload": {
                "stage": "page-unverified",
                "message": f"Could not fetch {bs_url} — drafting without page grounding.",
            }}

    # ══ V2 DECOMPOSE (may run before V1 on the auto-consult path) ══════
    # We produce the decomposed brief up front so the auto-trigger (§6.4) can
    # inspect claim_hints. V1's output is additive, so running V2 first is fine.
    campaign_brief = ""
    decomposed = None

    async def _decompose(consult_block: str) -> dict[str, Any]:
        # Fold the brief-source context in FRONT of the brief text + consult
        # block so the decomposer grounds on campaign/page signals even when
        # brief_text is empty (campaign/landing_page seeding, plan CHANGE-1).
        body_parts = [p for p in (source_block, brief_text, consult_block) if p]
        page = {
            "body_excerpt": "\n\n".join(body_parts),
            "url": bs_url if bs_type == "landing_page" else None,
            "title": None,
        }
        # V2 decompose goes through prompt_drafter directly (NOT _draft_llm), so
        # pass the longer video-draft budget here too — else the 45s default
        # dead-ends the campaign-context decompose (CHANGE 1).
        return await prompt_drafter._stage1_decompose(
            page=page, target="video", timeout_s=_DRAFT_STAGE_TIMEOUT_S,
        )

    if is_initial:
        try:
            decomposed = await _decompose("")
        except prompt_drafter.PromptDrafterError as e:
            logger.info("video_director V2 decompose timed out/failed: %s", e)
            yield _draft_timeout_event()
            return

    # ══ V1 CONSULT (conditional §6.4) ═════════════════════════════════
    # Runs on the INITIAL draft turn when either the operator selected it
    # (consult_director on + campaign linked) OR the auto-trigger fires (linked
    # campaign + decomposed claim_hints not covered by pinned facts). On an
    # ITERATION turn, only re-consult if the message explicitly asks.
    want_consult = False
    if campaign_id:
        if is_initial:
            selected = consult_director == 1
            auto = decomposed is not None and not _pinned_claims_covered(
                decomposed.get("claim_hints") or [], pinned_facts
            )
            if auto and not selected:
                yield {"type": "director_thought", "payload": {
                    "text": "Brief contains unverified claims — consulting the campaign Director",
                    "stage": "consult",
                }}
            want_consult = selected or auto
        elif is_iteration and ("consult" in message.lower() or "director" in message.lower()):
            want_consult = True

    if want_consult:
        try:
            async for ev in _run_consult(
                turn_id=turn_id, account_id=account_id, campaign_id=campaign_id,
                campaign_name=campaign_name, conversation_id=conversation_id,
                brief=brief_text,
            ):
                if "__consult_text__" in ev:
                    campaign_brief = ev["__consult_text__"]
                else:
                    yield ev
        except Exception as e:  # the whole consult degrades, never blocks
            logger.info("video_director consult wrapper degraded: %s", e)
            yield {"type": "director_thought", "payload": {
                "text": "Campaign Director unavailable — drafting from pinned facts only",
                "stage": "consult",
            }}
            campaign_brief = ""

    # V2 (re-run with the consult block folded in, or run for the first time on
    # an iteration turn — decompose is cheap and keeps the brief structured).
    if decomposed is None or campaign_brief:
        try:
            decomposed = await _decompose(campaign_brief)
        except prompt_drafter.PromptDrafterError as e:
            logger.info("video_director V2 decompose timed out/failed: %s", e)
            yield _draft_timeout_event()
            return

    # ══ V3 CONCEPT (initial draft only, not an angle jump) ════════════
    if is_initial:
        try:
            concepts = await _draft_concepts(
                brief=decomposed, pinned_facts=pinned_facts, campaign_brief=campaign_brief,
            )
        except prompt_drafter.PromptDrafterError as e:
            logger.info("video_director V3 concepts timed out/failed: %s", e)
            yield _draft_timeout_event()
            return
        yield {"type": "concepts", "payload": {"variants": concepts}}
        yield {"type": "turn_done", "payload": {"stop_reason": "natural"}}
        return

    # ══ V4 STORYBOARD ═════════════════════════════════════════════════
    if is_angle_jump:
        # §13 default: straight-to-draft — skip V3, jump to V4 with the chosen angle.
        angle = message[len("angle:"):].strip() or "aspirational"
    else:
        # Iteration turn — the operator is refining an existing storyboard.
        angle = (current_storyboard or {}).get("title") or "the current direction"

    user = _build_storyboard_user_prompt(
        model_id=model_id, target_seconds=target_seconds, aspect=aspect, angle=angle,
        brief=decomposed, pinned_facts=pinned_facts, campaign_brief=campaign_brief,
        current_storyboard=current_storyboard if is_iteration else None,
    )
    try:
        raw = await _draft_llm(_video_director_system(), user, model="sonnet")
    except prompt_drafter.PromptDrafterError as e:
        logger.info("video_director V4 storyboard timed out/failed: %s", e)
        yield _draft_timeout_event()
        return
    parsed = prompt_drafter._parse_json_envelope(raw)
    storyboard = _validate_storyboard(
        parsed, model_id=model_id, target_seconds=target_seconds
    )

    await _persist_storyboard(project_id, storyboard)

    version = 1
    if current_storyboard is not None:
        version = int((current_storyboard.get("_version") or 1)) + 1
    storyboard_out = dict(storyboard)
    yield {"type": "storyboard", "payload": {
        "project_id": project_id,
        "version": version,
        "scenes": storyboard_out["scenes"],
        "vo_full": storyboard_out["vo_full"],
        "music_mood": storyboard_out["music_mood"],
        "title": storyboard_out["title"],
    }}

    # ══ V5 WRITEBACK ═══════════════════════════════════════════════════
    if campaign_id:
        try:
            from app.services import campaign_memory
            n_scenes = len(storyboard_out["scenes"])
            note = (
                f"Storyboard drafted for {model_id} · target {target_seconds}s · "
                f"{n_scenes} scenes · title \"{storyboard_out['title']}\"."
            )
            campaign_memory.append_role_notes(
                account_id, campaign_id, "video_director", note,
                section_title="Storyboard drafted",
            )
        except Exception as e:  # writeback failure must not crash the turn
            logger.info("video_director writeback failed: %s", e)

    yield {"type": "turn_done", "payload": {"stop_reason": "natural"}}
