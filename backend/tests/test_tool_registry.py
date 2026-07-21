"""Registry-truth + canonicalization tests — the structural guard against the
2026-07-16 money bug (double-underscore chat allowlist matched the live
single-underscore MCP registry NOTHING, severing an approved negative-keyword
write while a campaign wasted ~$131/week).

The key test enumerates the ACTUAL registered tool surface (imports the real
server registrations, lists names) and asserts every read-only allowlist entry
matches a real tool. Name-convention drift now breaks CI instead of silently
failing at runtime.

Stdlib unittest. NO network, NO real LLM — the registry import mounts the same
FastMCP servers the live server mounts and lists tool names in-process.

Run:  cd backend && .venv/bin/python -m unittest tests.test_tool_registry -v
"""

from __future__ import annotations

import asyncio
import unittest

from google_ads import tool_registry
from google_ads.tool_registry import (
    allowlist_matches,
    canonical_tool_name,
    matches,
    registered_tool_names,
    unmatched_allowlist_entries,
)

from app.services import chat_orchestrator


class RegistryTruth(unittest.TestCase):
    """Every static read-only allowlist entry MUST match a real registered tool.
    This is the test the money bug would have failed: with `search__execute_query`
    (double underscore) it matches zero of the live single-underscore names."""

    @classmethod
    def setUpClass(cls):
        cls.names = registered_tool_names()

    def test_registry_is_nonempty_and_large(self):
        # The full mounted surface (~317 tools). Guards against an enumeration
        # that silently returns an empty/partial set (which would make the
        # match assertions vacuously pass).
        self.assertGreater(len(self.names), 200)

    def test_live_search_tool_names_are_single_underscore(self):
        # The exact names the allowlist depends on — single underscore joins
        # namespace `search` + tool. Documents reality in the suite.
        for real in (
            "search_execute_query",
            "search_search_campaigns",
            "search_search_ad_groups",
            "search_search_keywords",
            "search_list_accessible_customers",
            "search_generate_keyword_ideas",
        ):
            self.assertIn(real, self.names, f"{real} not in live registry")
        # The buggy double-underscore variants are NOT registered.
        self.assertNotIn("search__execute_query", self.names)

    def test_every_readonly_entry_matches_a_registered_tool(self):
        for entry in chat_orchestrator._READ_ONLY_GADS_TOOLS:
            hits = [n for n in self.names if matches(entry, n)]
            self.assertTrue(
                hits,
                f"read-only allowlist entry {entry!r} matches NO registered "
                f"tool — name-convention drift has severed tooling.",
            )

    def test_no_registered_tool_uses_double_underscore(self):
        # If the registry itself ever adopts `__`, the canonicalizer still
        # bridges it — but flag the surprise so we notice a convention change.
        dbl = sorted(n for n in self.names if "__" in n)
        self.assertEqual(dbl, [], f"unexpected double-underscore tools: {dbl}")


class Canonicalization(unittest.TestCase):
    def test_double_underscore_collapses_to_single(self):
        self.assertEqual(
            canonical_tool_name("search__execute_query"),
            canonical_tool_name("search_execute_query"),
        )

    def test_runs_and_casefold(self):
        self.assertEqual(canonical_tool_name("Search___Execute_Query"),
                         "search_execute_query")
        self.assertEqual(canonical_tool_name("  AD__Update_Ad_Status "),
                         "ad_update_ad_status")

    def test_empty(self):
        self.assertEqual(canonical_tool_name(""), "")
        self.assertEqual(canonical_tool_name(None), "")  # type: ignore[arg-type]

    def test_matches_bridges_underscore_drift(self):
        # A double-underscore ALLOWLIST entry still authorizes the live
        # single-underscore tool — the exact drift the bug tripped on.
        self.assertTrue(matches("search__execute_query", "search_execute_query"))
        self.assertTrue(matches("search_execute_query", "search__execute_query"))

    def test_matches_preserves_substring_semantics(self):
        # Plan-authorized names may be partial — substring match survives.
        self.assertTrue(matches("execute_query", "search_execute_query"))
        self.assertFalse(matches("delete_everything", "search_execute_query"))

    def test_allowlist_matches_any(self):
        allowed = ["search_execute_query", "search_search_campaigns"]
        self.assertTrue(allowlist_matches("search_execute_query", allowed))
        self.assertTrue(allowlist_matches("search__execute_query", allowed))  # drift
        self.assertFalse(allowlist_matches("campaign_update_campaign", allowed))
        self.assertFalse(allowlist_matches("search_execute_query", []))


class UnmatchedEntries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names = registered_tool_names()

    def test_real_readonly_list_has_no_unmatched(self):
        bad = unmatched_allowlist_entries(
            list(chat_orchestrator._READ_ONLY_GADS_TOOLS), self.names)
        self.assertEqual(bad, [])

    def test_double_underscore_entry_is_not_flagged(self):
        # The old buggy names would (wrongly) be reported as severed by a naive
        # exact check; the canonical audit correctly sees them as matched.
        bad = unmatched_allowlist_entries(["search__execute_query"], self.names)
        self.assertEqual(bad, [])

    def test_bogus_entry_is_flagged(self):
        bad = unmatched_allowlist_entries(
            ["search_execute_query", "totally_made_up_tool"], self.names)
        self.assertEqual(bad, ["totally_made_up_tool"])


class DispatchAudit(unittest.IsolatedAsyncioTestCase):
    """The dispatch-time fail-loud helper: clean list → [], drift → the offender."""

    async def test_current_allowlist_clean(self):
        allow = chat_orchestrator._specialist_tool_allowlist([])
        self.assertEqual(await chat_orchestrator._audit_tool_allowlist(allow), [])

    async def test_flags_severed_entry(self):
        allow = chat_orchestrator._specialist_tool_allowlist(["ghost__nope_tool"])
        bad = await chat_orchestrator._audit_tool_allowlist(allow)
        self.assertIn("ghost__nope_tool", bad)

    async def test_degrades_to_empty_on_registry_failure(self):
        # Enumeration failure must NEVER break dispatch — it degrades to [].
        orig = tool_registry.registered_tool_names

        def boom(*a, **k):
            raise RuntimeError("registry down")

        tool_registry.registered_tool_names = boom
        try:
            bad = await chat_orchestrator._audit_tool_allowlist(["anything"])
        finally:
            tool_registry.registered_tool_names = orig
        self.assertEqual(bad, [])


class ExecutionCatalog(unittest.TestCase):
    """The Director's plan-stage tool catalog: grouped, non-empty, and every
    listed name is a REAL registered tool (2026-07-20 interface-contract bug —
    the plan must name execution tools BY EXACT NAME, never a server name)."""

    @classmethod
    def setUpClass(cls):
        from google_ads.tool_registry import execution_catalog
        cls.cat = execution_catalog()
        cls.names = registered_tool_names()

    def test_catalog_nonempty_reads_and_writes(self):
        self.assertTrue(self.cat["read"], "catalog must surface read tools")
        self.assertTrue(self.cat["write"], "catalog must surface write tools")

    def test_every_catalog_entry_is_a_real_tool(self):
        for group in ("read", "write"):
            for name in self.cat[group]:
                self.assertIn(name, self.names,
                              f"catalog {group} entry '{name}' is not registered")

    def test_catalog_carries_the_common_execution_ops(self):
        writes = set(self.cat["write"])
        # the negative-keyword + budget mutates the chat agent actually executes
        self.assertIn("campaign_criterion_add_negative_keyword_criteria", writes)
        self.assertIn("budget_update_campaign_budget", writes)

    def test_catalog_never_contains_a_server_name(self):
        flat = self.cat["read"] + self.cat["write"]
        self.assertNotIn("google-ads", flat)
        self.assertNotIn("chrome", flat)


if __name__ == "__main__":
    unittest.main()
