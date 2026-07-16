"""Unit tests — primary_for_goal on ConversionService.update/create_conversion_action.

Closes the confirmed MCP gap where `conversion_update_conversion_action` could
not write `primary_for_goal`, so a deprecated conversion action could not be
demoted from primary to secondary from the agent. Mirrors the WS1 field-mask
precedent (`update_ad_final_urls`): the field is included in the update_mask
ONLY when explicitly provided, so back-compat (None => untouched) holds.

No live Google mutation happens — get_sdk_client is patched with a fake whose
get_service returns a request-capturing stub; the captured request/mask is the
smoke check. The third test drives the real MCP tool enumeration
(enumerate_tools in validate_all_tools) to prove the harness discovers the tool
and that its parameter schema now surfaces primary_for_goal, plus that the
fail-closed harness ARGS map exercises the demote path.

Run:  cd backend && .venv/bin/python -m unittest tests.test_conversion_primary_for_goal -v
"""

from __future__ import annotations

import unittest
from typing import Any, List
from unittest import mock

from google.ads.googleads.v23.services.types.conversion_action_service import (
    MutateConversionActionResult,
    MutateConversionActionsResponse,
)

from google_ads.services.conversions import conversion_service as cs_module
from google_ads.services.conversions.conversion_service import ConversionService

CUSTOMER = "1234567890"
CONVERSION_ACTION_ID = "987654321"
RESULT_RN = f"customers/{CUSTOMER}/conversionActions/{CONVERSION_ACTION_ID}"


class _ApiCtx:
    """Minimal FastMCP-Context stand-in — only ctx.log is exercised."""

    async def log(self, level: str, message: str) -> None:  # pragma: no cover
        return None


class _FakeConversionActionClient:
    """Captures every mutate request; returns a minimal real proto response."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_conversion_actions(self, request):
        self.requests.append(request)
        return MutateConversionActionsResponse(
            results=[MutateConversionActionResult(resource_name=RESULT_RN)]
        )


class _FakeSdkClient:
    """Stand-in for GoogleAdsSdkClient — get_service returns our fake."""

    def __init__(self, fake_service: _FakeConversionActionClient) -> None:
        self._fake_service = fake_service
        self.client = self  # sdk_client.client.get_service(...)

    def get_service(self, name: str):
        assert name == "ConversionActionService"
        return self._fake_service

    # ConversionService caches the resolved service on self._client, so a fresh
    # ConversionService() per test picks up whichever fake we patch in.


class ConversionPrimaryForGoalTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_demote_builds_primary_for_goal_mask(self):
        """primary_for_goal=False sets the field AND adds it to the update_mask."""
        fake = _FakeConversionActionClient()
        with mock.patch.object(
            cs_module, "get_sdk_client", return_value=_FakeSdkClient(fake)
        ):
            result = await ConversionService().update_conversion_action(
                _ApiCtx(),
                CUSTOMER,
                CONVERSION_ACTION_ID,
                primary_for_goal=False,
            )

        self.assertEqual(len(fake.requests), 1)
        op = fake.requests[-1].operations[0]
        # The demote value is carried on the update payload.
        self.assertIs(op.update.primary_for_goal, False)
        # And the field-mask covers it (else the API would ignore the change).
        self.assertIn("primary_for_goal", list(op.update_mask.paths))
        # Nothing else was touched — mask has exactly the one path.
        self.assertEqual(list(op.update_mask.paths), ["primary_for_goal"])
        self.assertEqual(result["results"][0]["resource_name"], RESULT_RN)

    async def test_update_omitted_leaves_mask_unchanged(self):
        """None (default) => primary_for_goal never enters the mask (back-compat)."""
        fake = _FakeConversionActionClient()
        with mock.patch.object(
            cs_module, "get_sdk_client", return_value=_FakeSdkClient(fake)
        ):
            await ConversionService().update_conversion_action(
                _ApiCtx(),
                CUSTOMER,
                CONVERSION_ACTION_ID,
                status="ENABLED",  # some other field so the request is valid
            )

        op = fake.requests[-1].operations[0]
        paths = list(op.update_mask.paths)
        self.assertIn("status", paths)
        self.assertNotIn("primary_for_goal", paths)

    async def test_update_true_promotes(self):
        """primary_for_goal=True is honored symmetrically (promote path)."""
        fake = _FakeConversionActionClient()
        with mock.patch.object(
            cs_module, "get_sdk_client", return_value=_FakeSdkClient(fake)
        ):
            await ConversionService().update_conversion_action(
                _ApiCtx(),
                CUSTOMER,
                CONVERSION_ACTION_ID,
                primary_for_goal=True,
            )

        op = fake.requests[-1].operations[0]
        self.assertIs(op.update.primary_for_goal, True)
        self.assertIn("primary_for_goal", list(op.update_mask.paths))

    async def test_create_sets_primary_for_goal_only_when_provided(self):
        """create includes primary_for_goal when passed; omits it otherwise."""
        fake = _FakeConversionActionClient()
        with mock.patch.object(
            cs_module, "get_sdk_client", return_value=_FakeSdkClient(fake)
        ):
            await ConversionService().create_conversion_action(
                _ApiCtx(),
                CUSTOMER,
                name="Demote-Aware Action",
                primary_for_goal=True,
            )
            with_flag = fake.requests[-1].operations[0].create
            self.assertIs(with_flag.primary_for_goal, True)

            await ConversionService().create_conversion_action(
                _ApiCtx(),
                CUSTOMER,
                name="Default Action",
            )
            # Not explicitly set => proto default False, API-default behavior.
            without_flag = fake.requests[-1].operations[0].create
            self.assertIs(without_flag.primary_for_goal, False)


class ConversionToolHarnessDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_harness_discovers_tool_and_exposes_primary_for_goal(self):
        """enumerate_tools surfaces conversion_update_conversion_action with the
        new param, and the fail-closed ARGS map exercises the demote path."""
        # enumerate_tools imports google_ads.mcp_main, which parses sys.argv at
        # import; pin it (as the harness's __main__ guard does) so argparse does
        # not choke on the unittest runner's argv.
        import sys

        with mock.patch.object(sys, "argv", ["validate_all_tools"]):
            from validate_all_tools import HARVEST_TOOL_ARGS, enumerate_tools

            tools = await enumerate_tools()
        by_name = {full: params for (full, _ns, _fn, params) in tools}

        self.assertIn("conversion_update_conversion_action", by_name)
        schema = by_name["conversion_update_conversion_action"]
        props = schema.get("properties", {})
        self.assertIn("primary_for_goal", props)

        # create also surfaces the flag.
        self.assertIn("conversion_create_conversion_action", by_name)
        self.assertIn(
            "primary_for_goal",
            by_name["conversion_create_conversion_action"].get("properties", {}),
        )

        # The dry-run harness entry drives the demote path fail-closed.
        args = HARVEST_TOOL_ARGS["conversion_update_conversion_action"](
            {"conversion_action_id": CONVERSION_ACTION_ID}
        )
        self.assertEqual(args["primary_for_goal"], False)


if __name__ == "__main__":
    unittest.main()
