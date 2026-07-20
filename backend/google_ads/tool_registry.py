"""Shared MCP tool-name canonicalization + live-registry enumeration.

Single source of truth for **how MCP tool names are compared** and **what the
live registered surface actually is**, so a name-convention drift between the
chat-specialist allowlist (`chat_orchestrator._READ_ONLY_GADS_TOOLS`) and the
enforcement middleware (`mcp_main.CampaignScopeMiddleware`) can never again
*silently* sever tooling.

Why this module exists (the 2026-07-16 money bug): the allowlist shipped with
DOUBLE-underscore names (`search__execute_query`) while the live registry mounts
tools with a SINGLE underscore (`search_execute_query`). The middleware's plain
substring check (`a in tool_name`) therefore matched NOTHING, blocking an
approved negative-keyword write (and its verification) on Jul 18 while a campaign
kept wasting ~$131/week. Both the allowlist-audit side and the enforcement side
now route through the SAME canonicalizer here, so single-vs-double underscore or
case drift collapses to a match instead of a mystery block.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys

logger = logging.getLogger(__name__)

_UNDERSCORE_RUN = re.compile(r"_+")


def canonical_tool_name(name: str) -> str:
    """Normalize an MCP tool name for drift-proof comparison.

    Collapses any run of underscores to a single ``_`` and casefolds, so
    ``search__execute_query`` and ``Search_Execute_Query`` both canonicalize to
    ``search_execute_query``. This is the ONE normalization both the allowlist
    audit and the enforcement middleware use — they cannot disagree.
    """
    return _UNDERSCORE_RUN.sub("_", (name or "").strip()).casefold()


def matches(entry: str, tool_name: str) -> bool:
    """True when allowlist ``entry`` authorizes ``tool_name`` under
    canonicalization. Substring semantics are preserved (plan-authorized names
    come from the model and may be partial), but compared on the canonical form
    so ``search__execute_query`` still matches the live ``search_execute_query``.
    """
    ce = canonical_tool_name(entry)
    return bool(ce) and ce in canonical_tool_name(tool_name)


def allowlist_matches(tool_name: str, allowed: list[str]) -> bool:
    """True when ANY entry in ``allowed`` authorizes ``tool_name`` (the exact
    check the middleware runs). Empty/blank entries are ignored."""
    return any(matches(a, tool_name) for a in allowed if a and a.strip())


# ── Live registry enumeration (authoritative surface, cached) ─────────────────
_REGISTRY: frozenset[str] | None = None


def _build_registry() -> frozenset[str]:
    """Enumerate the REAL registered tool names by mounting every server the
    production MCP mounts (``--groups all``) onto a throwaway FastMCP and listing
    its tools. Uses ``mcp_main.get_servers_to_mount`` — the same mapping the live
    server uses — so this reflects reality, not a hand-maintained list.

    ``mcp_main`` runs ``argparse.parse_args()`` at import; we feed it clean argv
    so importing it here never trips on the caller's argv (e.g. pytest/uvicorn).
    The enumeration is deterministic regardless of how/whether ``mcp_main`` was
    already imported, because it re-mounts from ``get_servers_to_mount('all')``
    rather than trusting the module-level ``mcp`` (whose surface depends on the
    argv at first import).
    """
    from fastmcp import FastMCP

    saved = list(sys.argv)
    try:
        sys.argv = ["mcp_main.py"]
        from google_ads import mcp_main
    finally:
        sys.argv[:] = saved

    probe: FastMCP = FastMCP(name="tool-registry-probe")
    for namespace, server in mcp_main.get_servers_to_mount("all"):
        probe.mount(server, namespace=namespace)
    tools = asyncio.run(probe.list_tools())
    return frozenset(getattr(t, "name", str(t)) for t in tools)


def registered_tool_names(*, refresh: bool = False) -> frozenset[str]:
    """Cached set of every live-registered MCP tool name. Heavy on first call
    (imports the full server surface); memoized thereafter. Call off the event
    loop (``asyncio.to_thread``) from async code — it uses ``asyncio.run``."""
    global _REGISTRY
    if _REGISTRY is None or refresh:
        _REGISTRY = _build_registry()
    return _REGISTRY


def unmatched_allowlist_entries(entries: list[str], names: frozenset[str]) -> list[str]:
    """Order-stable list of allowlist ``entries`` that match ZERO tools in
    ``names`` (under canonicalization). A non-empty result means convention drift
    has severed tooling — the caller should surface it, not swallow it."""
    return [e for e in entries if e and not any(matches(e, n) for n in names)]
