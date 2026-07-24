"""Campaign Changelog + 1-click revert (V25).

Proves the change-capture brain, the merged feed, and the revert executor without
touching Google (the SDK client is a request-capturing fake):

  1. classify() — writes are classified, reads return None.
  2. build_change_row() — before-state → revertible row + revert_spec; missing
     before / destructive / no-op edits → revertible=0 with a plain reason.
  3. plan_before_read() — the cheap GAQL for status/bid/budget update tools.
  4. extract_resource_names() — dig created names out of a proto result.
  5. record / list_rows / build_feed — persistence, newest-first, batch grouping,
     external-change merge.
  6. revert executor — the correct INVERSE op per class (status/budget/bid/
     remove-criteria/remove-ad/final-urls/asset), read-back verified, with mocks.
  7. idempotence — reverting twice → RevertConflict (409).
  8. grouped batch revert — one op removes all members, one revert row.
  9. non-revertible → RevertNotSupported (400) carrying the reason.

Run:  cd backend && .venv/bin/python -m unittest tests.test_change_log -v
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="change-log-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402
from app.services import (  # noqa: E402
    change_capture,
    change_log,
    change_revert,
    external_change,
)

_ACCOUNT = "1234567890"


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


async def _clear():
    db = await get_db()
    try:
        await db.execute("DELETE FROM change_log")
        try:
            await db.execute("DELETE FROM external_change")
        except Exception:
            pass  # lazily-created table may not exist yet
        await db.commit()
    finally:
        await db.close()
    external_change._ensured = False


# ── A request-capturing fake Google Ads client ───────────────────────────────

class _FakeService:
    """Stands in for any Google Ads *Service. Records every mutate request and
    returns a response with one result-per-operation; search() returns the
    configured read-back rows so read-back verification can pass."""

    def __init__(self, parent):
        self.parent = parent

    def _results(self, request):
        results = []
        for i, op in enumerate(getattr(request, "operations", []) or []):
            rn = ""
            try:
                rn = op.remove or getattr(op.update, "resource_name", "") or ""
            except Exception:
                rn = ""
            results.append(SimpleNamespace(resource_name=rn or f"res-{i}"))
        if not results:
            results = [SimpleNamespace(resource_name="res-0")]
        return SimpleNamespace(results=results)

    def _record(self, name, request):
        self.parent.calls.append((name, request))
        return self._results(request)

    # Read
    def search(self, customer_id=None, query=None):
        self.parent.searches.append(query)
        return list(self.parent.readback)

    # Every mutate variant funnels through _record.
    def __getattr__(self, item):
        if item.startswith("mutate_"):
            return lambda request=None: self._record(item, request)
        raise AttributeError(item)


class _FakeClient:
    def __init__(self, readback=None):
        self.calls: list = []
        self.searches: list = []
        self.readback = readback or []

    def get_service(self, name):
        return _FakeService(self)


def _status_row(**paths):
    """Build a read-back row exposing whichever resource the get_* helper reads,
    each with .status.name / value set from kwargs."""
    ns = SimpleNamespace()
    for k, v in paths.items():
        setattr(ns, k, v)
    return ns


# ══════════════════════════════════════════════════════════════════════════════
# 1–4  Pure classifier / row-builder / planner / extractor
# ══════════════════════════════════════════════════════════════════════════════

class ClassifierTest(unittest.TestCase):
    def test_write_vs_read(self):
        self.assertIsNone(change_capture.classify("search_execute_query"))
        self.assertIsNone(change_capture.classify("search_search_campaigns"))
        spec = change_capture.classify("budget_update_campaign_budget")
        self.assertEqual(spec["revert"], "restore_budget")
        # Namespaced + double-underscore drift still matches (canonicalized).
        spec2 = change_capture.classify(
            "mcp__google-ads__campaign_criterion_add_negative_keyword_criteria")
        self.assertEqual(spec2["action"], "add")
        self.assertEqual(spec2["criterion_type"], "campaign")

    def test_add_row_is_revertible_via_remove(self):
        spec = change_capture.classify("ad_group_criterion_add_keywords")
        row = change_capture.build_change_row(
            tool_name="ad_group_criterion_add_keywords",
            args={"customer_id": _ACCOUNT, "ad_group_id": "77"},
            spec=spec, actor_type="chat-specialist", actor_detail="Team",
            resource_names=["customers/1/adGroupCriteria/77~1",
                            "customers/1/adGroupCriteria/77~2"],
            batch_count=2)
        self.assertEqual(row["revertible"], 1)
        rs = json.loads(row["revert_spec"])
        self.assertEqual(rs["kind"], "remove_criteria")
        self.assertEqual(len(rs["resource_names"]), 2)
        self.assertIn("Added 2 keyword", row["summary"])

    def test_add_without_resource_names_is_not_revertible(self):
        spec = change_capture.classify("ad_group_criterion_add_keywords")
        row = change_capture.build_change_row(
            tool_name="ad_group_criterion_add_keywords",
            args={"customer_id": _ACCOUNT}, spec=spec,
            actor_type="chat-specialist", actor_detail="Team",
            resource_names=[])
        self.assertEqual(row["revertible"], 0)
        self.assertIn("manually", row["revert_reason"])

    def test_status_needs_before_and_after(self):
        spec = change_capture.classify(
            "ad_group_criterion_update_ad_group_criterion_status")
        # both present → revertible
        good = change_capture.build_change_row(
            tool_name="ad_group_criterion_update_ad_group_criterion_status",
            args={"customer_id": _ACCOUNT, "ad_group_id": "5", "criterion_id": "9",
                  "status": "PAUSED"},
            spec=spec, actor_type="chat-specialist", actor_detail="Team",
            before="ENABLED", after="PAUSED")
        self.assertEqual(good["revertible"], 1)
        rs = json.loads(good["revert_spec"])
        self.assertEqual(rs["kind"], "restore_status")
        self.assertEqual(rs["restore"], "ENABLED")
        self.assertEqual(good["summary"], "Status ENABLED → PAUSED")
        # missing before → not revertible
        bad = change_capture.build_change_row(
            tool_name="ad_group_criterion_update_ad_group_criterion_status",
            args={"customer_id": _ACCOUNT, "ad_group_id": "5", "criterion_id": "9",
                  "status": "PAUSED"},
            spec=spec, actor_type="chat-specialist", actor_detail="Team",
            before=None, after="PAUSED")
        self.assertEqual(bad["revertible"], 0)

    def test_campaign_update_without_status_change_is_not_revertible(self):
        spec = change_capture.classify("campaign_update_campaign")
        row = change_capture.build_change_row(
            tool_name="campaign_update_campaign",
            args={"customer_id": _ACCOUNT, "campaign_id": "42", "name": "New name"},
            spec=spec, actor_type="chat-specialist", actor_detail="Team",
            before="ENABLED", after=None)  # no status arg → after None
        self.assertEqual(row["revertible"], 0)
        self.assertIn("didn't change status", row["revert_reason"])

    def test_remove_is_never_revertible(self):
        spec = change_capture.classify(
            "ad_group_criterion_remove_ad_group_criterion")
        row = change_capture.build_change_row(
            tool_name="ad_group_criterion_remove_ad_group_criterion",
            args={"customer_id": _ACCOUNT}, spec=spec,
            actor_type="chat-specialist", actor_detail="Team")
        self.assertEqual(row["revertible"], 0)
        self.assertIn("destructive", row["revert_reason"])

    def test_budget_summary_and_spec(self):
        spec = change_capture.classify("budget_update_campaign_budget")
        row = change_capture.build_change_row(
            tool_name="budget_update_campaign_budget",
            args={"customer_id": _ACCOUNT, "campaign_id": "42",
                  "amount_micros": 200_000_000},
            spec=spec, actor_type="chat-specialist", actor_detail="Team",
            before=150_000_000, after=200_000_000)
        self.assertEqual(row["revertible"], 1)
        self.assertEqual(row["summary"], "Budget $150.00 → $200.00")
        self.assertEqual(json.loads(row["revert_spec"])["restore_micros"], 150000000)

    def test_plan_before_read(self):
        p = change_capture.plan_before_read(
            "ad_group_criterion_update_criterion_bid",
            {"customer_id": _ACCOUNT,
             "criterion_resource_name": "customers/1/adGroupCriteria/5~9"})
        self.assertIn("cpc_bid_micros", p["gaql"])
        p2 = change_capture.plan_before_read(
            "budget_update_campaign_budget",
            {"customer_id": _ACCOUNT, "campaign_id": "42"})
        self.assertIn("amount_micros", p2["gaql"])
        # reads have no before-read plan
        self.assertIsNone(change_capture.plan_before_read("search_execute_query", {}))

    def test_extract_resource_names(self):
        sc = {"results": [
            {"resource_name": "customers/1/campaignCriteria/2~3"},
            {"resource_name": "customers/1/campaignCriteria/2~4"},
        ]}
        names = change_capture.extract_resource_names(sc)
        self.assertEqual(len(names), 2)
        self.assertEqual(change_capture.extract_resource_names(None), [])


# ══════════════════════════════════════════════════════════════════════════════
# 5  Persistence + feed
# ══════════════════════════════════════════════════════════════════════════════

class FeedTest(unittest.TestCase):
    def setUp(self):
        _run(_clear())

    def test_record_and_list_newest_first(self):
        async def go():
            await change_log.record({
                "actor_type": "app-user", "account_id": _ACCOUNT,
                "campaign_id": "42", "resource": "campaign", "action": "status",
                "field": "status", "summary": "Status ENABLED → PAUSED",
                "revertible": 1})
            await change_log.record({
                "actor_type": "chat-specialist", "account_id": _ACCOUNT,
                "campaign_id": "42", "resource": "budget", "action": "update",
                "summary": "Budget $150.00 → $200.00", "revertible": 1})
            rows = await change_log.list_rows(account_id=_ACCOUNT)
            self.assertEqual(len(rows), 2)
            # Newest first: the budget row (inserted last) leads.
            self.assertEqual(rows[0]["summary"], "Budget $150.00 → $200.00")
            self.assertGreater(rows[0]["id"], rows[1]["id"])
        _run(go())

    def test_feed_groups_batch(self):
        async def go():
            for i in range(3):
                await change_log.record({
                    "actor_type": "app-user", "account_id": _ACCOUNT,
                    "resource": "negative_keyword", "action": "add",
                    "summary": "Added negative", "revertible": 1,
                    "batch_id": "b-1", "batch_count": 3,
                    "revert_spec": json.dumps({"kind": "remove_criteria",
                                               "customer_id": _ACCOUNT,
                                               "criterion_type": "campaign",
                                               "resource_names": [f"rn-{i}"]})})
            feed = await change_log.build_feed(account_id=_ACCOUNT)
            # 3 rows collapse into ONE grouped entry.
            self.assertEqual(len(feed["entries"]), 1)
            entry = feed["entries"][0]
            self.assertEqual(entry["batch_count"], 3)
            self.assertEqual(len(entry["members"]), 3)
            self.assertIn("Added 3 negative keyword", entry["summary"])
            self.assertIsNotNone(feed["history_begins"])
        _run(go())

    def test_feed_merges_external(self):
        async def go():
            await change_log.record({
                "actor_type": "app-user", "account_id": _ACCOUNT,
                "resource": "campaign", "action": "status",
                "summary": "Status ENABLED → PAUSED", "revertible": 1})
            await external_change.record_external_changes(_ACCOUNT, [
                {"campaign_id": "42", "field": "status",
                 "before": "PAUSED", "after": "ENABLED"}])
            feed = await change_log.build_feed(account_id=_ACCOUNT)
            sources = {e["source"] for e in feed["entries"]}
            self.assertIn("external", sources)
            ext = [e for e in feed["entries"] if e["source"] == "external"][0]
            self.assertFalse(ext["revertible"])
            self.assertIn("outside the app", ext["revert_reason"])
        _run(go())

    def test_actor_filter(self):
        async def go():
            await change_log.record({"actor_type": "app-user",
                                     "account_id": _ACCOUNT, "summary": "a"})
            await change_log.record({"actor_type": "scheduler-plan",
                                     "account_id": _ACCOUNT, "summary": "b"})
            rows = await change_log.list_rows(account_id=_ACCOUNT,
                                              actor_type="scheduler-plan")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["summary"], "b")
        _run(go())


# ══════════════════════════════════════════════════════════════════════════════
# 6–9  Revert executor (mocked SDK)
# ══════════════════════════════════════════════════════════════════════════════

class RevertTest(unittest.TestCase):
    def setUp(self):
        _run(_clear())

    async def _insert(self, **over):
        row = {"actor_type": "app-user", "account_id": _ACCOUNT,
               "campaign_id": "42", "resource": "campaign", "action": "status",
               "field": "status", "summary": "x", "revertible": 1}
        row.update(over)
        return await change_log.record(row)

    def _do(self, change_id, fake):
        with mock.patch.object(change_revert, "_client", return_value=fake):
            return _run(change_revert.revert_change(change_id))

    def test_restore_status_campaign(self):
        async def setup():
            return await self._insert(
                before_value="ENABLED", after_value="PAUSED",
                revert_spec=json.dumps({"kind": "restore_status",
                                        "customer_id": _ACCOUNT, "target": "campaign",
                                        "campaign_id": "42", "restore": "ENABLED"}))
        cid = _run(setup())
        fake = _FakeClient(readback=[
            _status_row(campaign=SimpleNamespace(
                status=SimpleNamespace(name="ENABLED")))])
        res = self._do(cid, fake)
        self.assertEqual(res["status"], "ok")
        self.assertTrue(res["verified"])
        names = [c[0] for c in fake.calls]
        self.assertIn("mutate_campaigns", names)
        # original marked reverted; a revert row now exists
        row = _run(change_log.get(cid))
        self.assertEqual(row["reverted_by"], res["revert_id"])
        rev = _run(change_log.get(res["revert_id"]))
        self.assertEqual(rev["actor_type"], "revert")
        self.assertEqual(rev["reverts"], cid)

    def test_restore_budget(self):
        cid = _run(self._insert(
            resource="budget", action="update",
            revert_spec=json.dumps({"kind": "restore_budget", "customer_id": _ACCOUNT,
                                    "campaign_id": "42",
                                    "budget_resource_name": "customers/1/campaignBudgets/7",
                                    "restore_micros": 150000000})))
        fake = _FakeClient(readback=[SimpleNamespace(
            campaign=SimpleNamespace(campaign_budget="customers/1/campaignBudgets/7"),
            campaign_budget=SimpleNamespace(amount_micros=150000000))])
        res = self._do(cid, fake)
        self.assertTrue(res["verified"])
        self.assertIn("mutate_campaign_budgets", [c[0] for c in fake.calls])

    def test_restore_bid(self):
        cid = _run(self._insert(
            resource="keyword", action="update",
            revert_spec=json.dumps({"kind": "restore_bid", "customer_id": _ACCOUNT,
                                    "criterion_resource_name": "customers/1/adGroupCriteria/5~9",
                                    "restore_micros": 500000})))
        fake = _FakeClient(readback=[SimpleNamespace(
            ad_group_criterion=SimpleNamespace(cpc_bid_micros=500000))])
        res = self._do(cid, fake)
        self.assertTrue(res["verified"])
        self.assertIn("mutate_ad_group_criteria", [c[0] for c in fake.calls])

    def test_remove_criteria_reverts_an_add(self):
        cid = _run(self._insert(
            resource="negative_keyword", action="add",
            revert_spec=json.dumps({"kind": "remove_criteria", "customer_id": _ACCOUNT,
                                    "criterion_type": "campaign",
                                    "resource_names": ["customers/1/campaignCriteria/2~3"]})))
        fake = _FakeClient()
        res = self._do(cid, fake)
        self.assertTrue(res["verified"])
        name, req = fake.calls[0]
        self.assertEqual(name, "mutate_campaign_criteria")
        self.assertEqual(len(req.operations), 1)

    def test_remove_ad(self):
        cid = _run(self._insert(
            resource="ad", action="add",
            revert_spec=json.dumps({"kind": "remove_ad", "customer_id": _ACCOUNT,
                                    "ad_group_ad_resource_name": "customers/1/adGroupAds/5~9"})))
        fake = _FakeClient()
        res = self._do(cid, fake)
        self.assertTrue(res["verified"])
        self.assertIn("mutate_ad_group_ads", [c[0] for c in fake.calls])

    def test_restore_final_urls(self):
        cid = _run(self._insert(
            resource="ad", action="update", field="final_urls",
            revert_spec=json.dumps({"kind": "restore_final_urls", "customer_id": _ACCOUNT,
                                    "ad_resource_name": "customers/1/ads/9",
                                    "restore_urls": ["https://old.example/"]})))
        fake = _FakeClient(readback=[SimpleNamespace(
            ad=SimpleNamespace(final_urls=["https://old.example/"]))])
        res = self._do(cid, fake)
        self.assertTrue(res["verified"])
        self.assertIn("mutate_ads", [c[0] for c in fake.calls])

    def test_restore_asset_status(self):
        cid = _run(self._insert(
            resource="asset", action="status",
            revert_spec=json.dumps({"kind": "restore_asset_status", "customer_id": _ACCOUNT,
                                    "campaign_asset_resource_name": "customers/1/campaignAssets/8~SITELINK",
                                    "restore": "ENABLED"})))
        fake = _FakeClient(readback=[SimpleNamespace(
            campaign_asset=SimpleNamespace(status=SimpleNamespace(name="ENABLED")))])
        res = self._do(cid, fake)
        self.assertTrue(res["verified"])
        self.assertIn("mutate_campaign_assets", [c[0] for c in fake.calls])

    def test_idempotence_second_revert_conflicts(self):
        cid = _run(self._insert(
            before_value="ENABLED", after_value="PAUSED",
            revert_spec=json.dumps({"kind": "restore_status", "customer_id": _ACCOUNT,
                                    "target": "campaign", "campaign_id": "42",
                                    "restore": "ENABLED"})))
        fake = _FakeClient(readback=[_status_row(
            campaign=SimpleNamespace(status=SimpleNamespace(name="ENABLED")))])
        self._do(cid, fake)
        with self.assertRaises(change_revert.RevertConflict):
            self._do(cid, fake)

    def test_grouped_batch_revert_is_one_op(self):
        async def setup():
            ids = []
            for i in range(3):
                ids.append(await change_log.record({
                    "actor_type": "app-user", "account_id": _ACCOUNT,
                    "resource": "negative_keyword", "action": "add",
                    "summary": "Added 3 negative keywords", "revertible": 1,
                    "batch_id": "batch-x", "batch_count": 3,
                    "revert_spec": json.dumps({"kind": "remove_criteria",
                                               "customer_id": _ACCOUNT,
                                               "criterion_type": "campaign",
                                               "resource_names": [f"customers/1/campaignCriteria/2~{i}"]})}))
            return ids
        ids = _run(setup())
        fake = _FakeClient()
        res = self._do(ids[0], fake)
        # ALL three members removed in ONE mutate call.
        self.assertEqual(len(res["reverted_ids"]), 3)
        crit_calls = [req for name, req in fake.calls if name == "mutate_campaign_criteria"]
        self.assertEqual(len(crit_calls), 1)
        self.assertEqual(len(crit_calls[0].operations), 3)
        # every member is stamped reverted_by the single revert row
        for cid in ids:
            self.assertEqual(_run(change_log.get(cid))["reverted_by"], res["revert_id"])
        # reverting any member again → conflict
        with self.assertRaises(change_revert.RevertConflict):
            self._do(ids[1], fake)

    def test_non_revertible_raises_with_reason(self):
        cid = _run(self._insert(
            resource="keyword", action="remove", revertible=0,
            revert_reason="Removing a keyword is destructive."))
        with self.assertRaises(change_revert.RevertNotSupported) as ctx:
            self._do(cid, _FakeClient())
        self.assertIn("destructive", str(ctx.exception))

    def test_missing_change_raises_not_found(self):
        with self.assertRaises(change_revert.RevertNotFound):
            self._do(999999, _FakeClient())

    def test_cannot_revert_a_revert(self):
        cid = _run(self._insert(actor_type="revert", reverts=1, revertible=0))
        with self.assertRaises(change_revert.RevertNotSupported):
            self._do(cid, _FakeClient())


if __name__ == "__main__":
    unittest.main()
