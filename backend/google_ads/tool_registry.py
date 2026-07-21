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


# ── Execution catalog (grounded in the live registry) ─────────────────────────
# Curated "common ops" the chat orchestrator surfaces to the Director so a PLAN
# authorizes execution BY EXACT TOOL NAME — never by an MCP SERVER name like
# 'google-ads', which authorizes NO tool BY NAME and once stranded a user-approved
# write (the 2026-07-20 interface-contract bug: plan carried tools=['google-ads']
# → 5× TOOL_NOT_ALLOWED, no seat could execute). Each candidate is INTERSECTED
# with the live registry below, so the catalog can never advertise a tool that
# isn't actually mounted (a mistyped/renamed candidate simply drops out).
_CATALOG_READ_CANDIDATES = [
    "search_execute_query",
    "search_search_campaigns",
    "search_search_ad_groups",
    "search_search_keywords",
    "search_generate_keyword_ideas",
    "search_list_accessible_customers",
]

_CATALOG_WRITE_CANDIDATES = [
    # negative keywords (the classic waste-cut execution)
    "campaign_criterion_add_negative_keyword_criteria",
    "customer_negative_criterion_add_negative_keywords",
    "shared_criterion_add_keywords_to_shared_set",
    # keywords
    "ad_group_criterion_add_keywords",
    "ad_group_criterion_remove_ad_group_criterion",
    "ad_group_criterion_update_ad_group_criterion_status",
    "ad_group_criterion_update_criterion_bid",
    # budgets
    "budget_update_campaign_budget",
    "budget_create_campaign_budget",
    # campaign / ad group / ad structure + status
    "campaign_update_campaign",
    "ad_group_update_ad_group",
    "ad_group_ad_create_ad_group_ad",
    "ad_group_ad_update_ad_group_ad_status",
    "ad_group_ad_remove_ad_group_ad",
    "ad_update_ad_status",
    # bid modifiers
    "campaign_bid_modifier_update_bid_modifier",
    "ad_group_bid_modifier_update_ad_group_bid_modifier",
]


def execution_catalog(*, refresh: bool = False) -> dict[str, list[str]]:
    """Grouped, registry-grounded catalog of the common read + write tool names
    the Director should reference when planning an execution. Each curated
    candidate is kept ONLY if it is a real registered tool (exact-name
    membership), so the catalog is always both *real* and *bounded*. Order-stable
    within each group. Heavy on first call (enumerates the live surface); memoized
    thereafter — call OFF the event loop (``asyncio.to_thread``) from async code."""
    names = registered_tool_names(refresh=refresh)
    return {
        "read": [t for t in _CATALOG_READ_CANDIDATES if t in names],
        "write": [t for t in _CATALOG_WRITE_CANDIDATES if t in names],
    }
