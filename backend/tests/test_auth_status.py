"""Studio pre-flight (CHANGE-2 + CHANGE-3) — auth-status + cost-estimate class.

Drives the studio router endpoint functions directly (repo style: no TestClient),
patching `studio.HiggsfieldClient` with a fake whose methods raise/return what
each case needs. NO live Higgsfield calls (the CLI is logged out).

Covers:
  auth-status:
    - account status raises HiggsfieldError(code="auth")  → {logged_in:False, error_class:"auth"}
    - account status succeeds                              → {logged_in:True}
    - other HiggsfieldError (e.g. run)                     → {logged_in:True, error_class:"run"}
    - never throws (unexpected Exception)                  → {logged_in:True, error_class:"other"}
  cost-estimate:
    - estimate raises HiggsfieldError(code="auth") → credits=None + error_code + error_class="auth"
    - success path unchanged (credits populated, no error_class)

Run: cd backend && .venv/bin/python -m unittest tests.test_auth_status -v
"""

from __future__ import annotations

import asyncio
import unittest

from app.routers import studio
from app.services.higgsfield_client import HiggsfieldError


def _run(coro):
    return asyncio.run(coro)


def _fake_client(*, balance_exc=None, balance_ret=None,
                 cost_exc=None, cost_ret=None):
    """Return a HiggsfieldClient stand-in class whose get_balance /
    estimate_cost raise/return per the case. Constructor ignores kwargs so it
    matches HiggsfieldClient(timeout_s=...)."""
    class _Fake:
        def __init__(self, *a, **k):
            pass

        async def get_balance(self):
            if balance_exc is not None:
                raise balance_exc
            return balance_ret or {}

        async def estimate_cost(self, *, model, prompt, **params):
            if cost_exc is not None:
                raise cost_exc
            return cost_ret or {}

    return _Fake


class AuthStatus(unittest.TestCase):
    def setUp(self):
        self._orig = studio.HiggsfieldClient

    def tearDown(self):
        studio.HiggsfieldClient = self._orig

    def test_logged_out_reports_auth(self):
        studio.HiggsfieldClient = _fake_client(
            balance_exc=HiggsfieldError(message="not logged in", code="auth"),
        )
        res = _run(studio.auth_status())
        self.assertFalse(res.logged_in)
        self.assertEqual(res.error_class, "auth")
        self.assertIsNotNone(res.message)

    def test_logged_in_success(self):
        studio.HiggsfieldClient = _fake_client(
            balance_ret={"email": "op@x.com", "credits": 100},
        )
        res = _run(studio.auth_status())
        self.assertTrue(res.logged_in)
        self.assertIsNone(res.error_class)

    def test_other_error_is_degraded_but_logged_in(self):
        studio.HiggsfieldClient = _fake_client(
            balance_exc=HiggsfieldError(message="upstream flaky", code="run"),
        )
        res = _run(studio.auth_status())
        self.assertTrue(res.logged_in)          # reachable, not a login problem
        self.assertEqual(res.error_class, "run")

    def test_never_throws_on_unexpected(self):
        studio.HiggsfieldClient = _fake_client(
            balance_exc=RuntimeError("kaboom"),
        )
        res = _run(studio.auth_status())        # must NOT raise
        self.assertTrue(res.logged_in)
        self.assertEqual(res.error_class, "other")


class CostEstimateErrorClass(unittest.TestCase):
    def setUp(self):
        self._orig = studio.HiggsfieldClient

    def tearDown(self):
        studio.HiggsfieldClient = self._orig

    def _body(self, **over):
        params = {"prompt": "aerial over coastline", "model": "veo3_1"}
        params.update(over)
        return studio.CostEstimateRequest(**params)

    def test_auth_failure_sets_error_class_and_nulls_credits(self):
        studio.HiggsfieldClient = _fake_client(
            cost_exc=HiggsfieldError(message="not logged in", code="auth"),
        )
        res = _run(studio.cost_estimate(self._body()))
        self.assertIsNone(res.credits)                 # unchanged null-on-failure contract
        self.assertIsNone(res.credits_exact)
        self.assertEqual(res.error_code, "auth")       # existing field
        self.assertEqual(res.error_class, "auth")      # NEW additive field

    def test_success_path_unchanged(self):
        studio.HiggsfieldClient = _fake_client(
            cost_ret={"credits": 12, "credits_exact": 12.5},
        )
        res = _run(studio.cost_estimate(self._body()))
        self.assertEqual(res.credits, 12)
        self.assertEqual(res.credits_exact, 12.5)
        self.assertIsNone(res.error_code)
        self.assertIsNone(res.error_class)             # unset on success


if __name__ == "__main__":
    unittest.main()
