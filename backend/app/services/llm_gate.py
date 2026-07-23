"""Global Claude-CLI concurrency gate — chat-hardening batch, item 1.

ONE process-wide `asyncio.Semaphore` that bounds how many `claude` CLI
subprocesses may run at the same time, ACROSS every component:

  * chat direct turns            (chat.py → agent.stream_agent_response)
  * orchestrated specialists     (chat_orchestrator → stream_agent_response)
  * the Director's own triage / plan / synthesis calls (same path)
  * Team Audit agents            (workflow_orchestrator → stream_agent_response)
  * scheduled plan runs          (scheduler → stream_agent_response)
  * the video-director consult   (video_director → stream_agent_response)
  * the video-director decompose (prompt_drafter._claude_one_shot)

Before this gate each of those held (or lacked) its OWN local
`asyncio.Semaphore(_MAX_PARALLEL)`, blind to the others — so a chat turn, a
background audit and a scheduled run could stampede 8+ CLI subprocesses at once
(each ~256 MB + its own Google API pressure). The fix is deliberately placed at
the SINGLE point where a Claude subprocess is actually spawned, not at each
dispatch loop, so the ceiling is airtight: EVERY Claude run is counted exactly
once, and the per-turn dispatch semaphores stay as-is for per-turn pacing.

Why no deadlock: the gate is acquired only around a leaf CLI run, which never
spawns a nested Claude run while holding it. A dispatch loop may hold its OWN
(different) per-turn semaphore and then acquire this gate — acquisition order is
always per-turn-outer / global-inner, so there is no circular wait; excess
demand simply queues on the gate (a bounded wait) rather than deadlocking.

Sizing: `settings.LLM_GLOBAL_MAX_CONCURRENCY` (default 4) — enough for one
orchestrated turn (≤2 parallel specialists) plus one background audit.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.config import settings

_DEFAULT_SIZE = 4


def gate_size() -> int:
    """Configured global CLI ceiling (>=1). Read fresh so a settings override
    applies to the NEXT event loop that builds a gate."""
    try:
        return max(1, int(getattr(settings, "LLM_GLOBAL_MAX_CONCURRENCY", 0) or _DEFAULT_SIZE))
    except (TypeError, ValueError):
        return _DEFAULT_SIZE


# The gate is bound to whatever event loop first asks for it. Tests (and the app)
# create/tear down loops; a semaphore bound to a dead loop would raise, so we
# re-create when the running loop changes. Within ONE loop every component gets
# the SAME instance — that shared identity is exactly item 1's guarantee.
_gate: Optional[asyncio.Semaphore] = None
_gate_loop: Optional[asyncio.AbstractEventLoop] = None


def get_gate() -> asyncio.Semaphore:
    """The one shared global CLI semaphore for the CURRENT running loop.

    Returns the identical object for every caller within a loop (so
    chat_orchestrator, workflow_orchestrator, the scheduler, the video director
    and agent.py all contend on ONE gate). Re-created only when the running loop
    changes (fresh loop → fresh gate, sized from settings at that moment)."""
    global _gate, _gate_loop
    loop = asyncio.get_running_loop()
    if _gate is None or _gate_loop is not loop:
        _gate = asyncio.Semaphore(gate_size())
        _gate_loop = loop
    return _gate


def llm_slot() -> asyncio.Semaphore:
    """`async with llm_slot():` — hold one global CLI slot for a Claude run.

    Sugar over get_gate(); an `asyncio.Semaphore` is itself an async context
    manager, so `async with llm_slot():` acquires on enter and releases on exit
    (including on cancellation / generator close)."""
    return get_gate()


def _reset_for_tests() -> None:
    """Drop the cached gate so the next get_gate() rebuilds from current settings
    on the current loop. Test-only helper."""
    global _gate, _gate_loop
    _gate = None
    _gate_loop = None
