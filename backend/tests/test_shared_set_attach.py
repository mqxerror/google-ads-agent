"""Unit test — attach_shared_set_to_campaigns on SharedSetService.

Pins the un-stubbing of attach_shared_set_to_campaigns (a stray
`raise NotImplementedError` sat directly above fully-working
CampaignSharedSet mutate code, so the tool always threw before the real
call ran). Removing the raise lets the real path execute; this test proves
it now builds one CampaignSharedSetOperation per campaign, points each at
the right campaign + shared-set resource names, sends a single
MutateCampaignSharedSetsRequest, and returns the serialized result.

The attach method resolves its client via
get_sdk_client().client.get_service("CampaignSharedSetService"), so we patch
get_sdk_client in the service module — the SDK client is stubbed and NO live
Google mutation happens; the captured request is the smoke check.

Run:  cd backend && .venv/bin/python -m unittest tests.test_shared_set_attach -v
"""

from __future__ import annotations

import unittest
from typing import Any, List
from unittest import mock

from google.ads.googleads.v23.services.types.campaign_shared_set_service import (
    MutateCampaignSharedSetResult,
    MutateCampaignSharedSetsResponse,
)

from google_ads.services.shared import shared_set_service as sss_module
from google_ads.services.shared.shared_set_service import SharedSetService

CUSTOMER = "1234567890"
SHARED_SET_ID = "555"
CAMPAIGN_IDS = ["111", "222"]
RESULT_RN = f"customers/{CUSTOMER}/campaignSharedSets/111~{SHARED_SET_ID}"


class _ApiCtx:
    """Minimal FastMCP-Context stand-in — only ctx.log is exercised."""

    async def log(self, level: str, message: str) -> None:  # pragma: no cover
        return None


class _FakeCampaignSharedSetClient:
    """Captures every mutate request; returns a minimal real proto response."""

    def __init__(self) -> None:
        self.requests: List[Any] = []

    def mutate_campaign_shared_sets(self, request):
        self.requests.append(request)
        return MutateCampaignSharedSetsResponse(
            results=[MutateCampaignSharedSetResult(resource_name=RESULT_RN)]
        )


class _FakeSdkClient:
    """Stand-in for GoogleAdsSdkClient — get_service returns our fake."""

    def __init__(self, fake_service: _FakeCampaignSharedSetClient) -> None:
        self._fake_service = fake_service
        self.client = self  # sdk_client.client.get_service(...)

    def get_service(self, name: str):
        assert name == "CampaignSharedSetService"
        return self._fake_service


class SharedSetAttachTests(unittest.IsolatedAsyncioTestCase):
    async def test_attach_builds_one_operation_per_campaign(self):
        fake = _FakeCampaignSharedSetClient()
        with mock.patch.object(
            sss_module, "get_sdk_client", return_value=_FakeSdkClient(fake)
        ):
            result = await SharedSetService().attach_shared_set_to_campaigns(
                _ApiCtx(),
                CUSTOMER,
                SHARED_SET_ID,
                CAMPAIGN_IDS,
            )

        # Exactly one mutate request, one operation per campaign id.
        self.assertEqual(len(fake.requests), 1)
        req = fake.requests[-1]
        self.assertEqual(req.customer_id, CUSTOMER)
        self.assertEqual(len(req.operations), len(CAMPAIGN_IDS))

        shared_set_rn = f"customers/{CUSTOMER}/sharedSets/{SHARED_SET_ID}"
        for op, campaign_id in zip(req.operations, CAMPAIGN_IDS):
            css = op.create
            self.assertEqual(
                css.campaign, f"customers/{CUSTOMER}/campaigns/{campaign_id}"
            )
            self.assertEqual(css.shared_set, shared_set_rn)

        # Serialized response is returned (proves the raise is gone).
        self.assertEqual(result["results"][0]["resource_name"], RESULT_RN)

    async def test_attach_formats_dashed_customer_id(self):
        fake = _FakeCampaignSharedSetClient()
        with mock.patch.object(
            sss_module, "get_sdk_client", return_value=_FakeSdkClient(fake)
        ):
            await SharedSetService().attach_shared_set_to_campaigns(
                _ApiCtx(), "123-456-7890", SHARED_SET_ID, ["111"]
            )
        self.assertEqual(fake.requests[-1].customer_id, "1234567890")


if __name__ == "__main__":
    unittest.main()
