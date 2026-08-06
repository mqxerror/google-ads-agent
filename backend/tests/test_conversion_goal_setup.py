"""Task #49 — shared conversion-goal setup: pure-builder + skip-semantics tests.

Asserts the BUILT operations against fixtures — resource-name format (incl. the
``~CATEGORY~ORIGIN`` shape), the ``biddable`` update mask, and batch composition
— plus the reuse-not-duplicate goal matcher and the bundle skip semantics. NO
live mutations: every function under test is pure (proto builders / dict logic),
so nothing here touches the Google Ads API.
"""

from __future__ import annotations

import asyncio

import pytest

from google_ads.services.conversions import conversion_goal_setup as cgs


# ── resource-name helpers ────────────────────────────────────────────────────


def test_conversion_action_rn_strips_hyphens_and_formats():
    assert (
        cgs.conversion_action_rn("717-823-9091", "7612610100")
        == "customers/7178239091/conversionActions/7612610100"
    )


def test_config_resource_name_is_keyed_by_campaign():
    assert (
        cgs.config_resource_name("7178239091", "24102429981")
        == "customers/7178239091/conversionGoalCampaignConfigs/24102429981"
    )


def test_campaign_conversion_goal_rn_uses_category_origin_tilde_format():
    rn = cgs.campaign_conversion_goal_rn(
        "7178239091", "24102429981", "SUBMIT_LEAD_FORM", "WEBSITE"
    )
    assert rn == (
        "customers/7178239091/campaignConversionGoals/"
        "24102429981~SUBMIT_LEAD_FORM~WEBSITE"
    )


# ── reuse-not-duplicate matcher ──────────────────────────────────────────────

_ACTION = "customers/7178239091/conversionActions/7612610100"

# Mirrors the live account read: two custom goals, each wrapping exactly one
# action ("Canada Descent Lead" 6458573428 is the reuse precedent).
_EXISTING_GOALS = [
    {
        "resource_name": "customers/7178239091/customConversionGoals/6458374995",
        "name": "Panama QIV Lead",
        "conversion_actions": ["customers/7178239091/conversionActions/7607343274"],
        "status": "ENABLED",
    },
    {
        "resource_name": "customers/7178239091/customConversionGoals/6458573428",
        "name": "Canada Descent Lead",
        "conversion_actions": [_ACTION],
        "status": "ENABLED",
    },
]


def test_pick_reusable_goal_reuses_exact_single_action_match():
    assert (
        cgs.pick_reusable_goal(_EXISTING_GOALS, _ACTION)
        == "customers/7178239091/customConversionGoals/6458573428"
    )


def test_pick_reusable_goal_returns_none_when_no_goal_wraps_the_action():
    other = "customers/7178239091/conversionActions/9999999999"
    assert cgs.pick_reusable_goal(_EXISTING_GOALS, other) is None


def test_pick_reusable_goal_ignores_multi_action_goals():
    # A goal wrapping the action PLUS another is not an exact match — never reuse.
    goals = [
        {
            "resource_name": "customers/7178239091/customConversionGoals/1",
            "name": "Combo",
            "conversion_actions": [
                _ACTION,
                "customers/7178239091/conversionActions/7607343274",
            ],
            "status": "ENABLED",
        }
    ]
    assert cgs.pick_reusable_goal(goals, _ACTION) is None


def test_pick_reusable_goal_ignores_removed_goals():
    goals = [
        {
            "resource_name": "customers/7178239091/customConversionGoals/6458573428",
            "name": "Canada Descent Lead",
            "conversion_actions": [_ACTION],
            "status": "REMOVED",
        }
    ]
    assert cgs.pick_reusable_goal(goals, _ACTION) is None


# ── the zero-biddable batch builder (the step missed on 2026-08-05) ──────────

# The account's 8 category rows (live customer_conversion_goal read), 5 of them
# biddable — this batch flips EVERY row to biddable=false in one mutate.
_ROWS = [
    ("PURCHASE", "WEBSITE"),
    ("PAGE_VIEW", "WEBSITE"),
    ("DOWNLOAD", "APP"),
    ("SUBMIT_LEAD_FORM", "WEBSITE"),
    ("SUBMIT_LEAD_FORM", "GOOGLE_HOSTED"),
    ("CONTACT", "WEBSITE"),
    ("QUALIFIED_LEAD", "WEBSITE"),
    ("UNKNOWN", "GOOGLE_HOSTED"),
]


def test_build_zero_biddable_ops_one_op_per_row():
    ops = cgs.build_zero_biddable_ops("7178239091", "24102429981", _ROWS)
    assert len(ops) == len(_ROWS)


def test_build_zero_biddable_ops_all_false_masked_and_named():
    ops = cgs.build_zero_biddable_ops("7178239091", "24102429981", _ROWS)
    built = {op.update.resource_name: op for op in ops}

    # Every op is an update masked to exactly ['biddable'], value False.
    for op in ops:
        assert op.update.biddable is False
        assert list(op.update_mask.paths) == ["biddable"]

    # The category rows the account had biddable=true must be present + zeroed —
    # this is the fix for the "multiple conversion goals" warning.
    for category, origin in [
        ("PURCHASE", "WEBSITE"),
        ("DOWNLOAD", "APP"),
        ("SUBMIT_LEAD_FORM", "WEBSITE"),
        ("SUBMIT_LEAD_FORM", "GOOGLE_HOSTED"),
        ("CONTACT", "WEBSITE"),
    ]:
        rn = cgs.campaign_conversion_goal_rn(
            "7178239091", "24102429981", category, origin
        )
        assert rn in built, f"missing zero-op for {category}~{origin}"


def test_build_zero_biddable_ops_empty_rows_yields_empty_batch():
    assert cgs.build_zero_biddable_ops("7178239091", "24102429981", []) == []


# ── bundle skip semantics (one interpreter shared by all orchestrators) ──────


@pytest.mark.parametrize(
    "bundle, expected",
    [
        ({}, None),
        ({"conversion_goal_action_id": None}, None),
        ({"conversion_goal_action_id": ""}, None),
        ({"conversion_goal_action_id": "   "}, None),
        ({"conversion_goal_action_id": cgs.ACCOUNT_DEFAULT}, None),
        ({"conversion_goal_action_id": "7612610100"}, "7612610100"),
        ({"conversion_goal_action_id": 7612610100}, "7612610100"),
    ],
)
def test_bundle_conversion_goal_action_skip_semantics(bundle, expected):
    assert cgs.bundle_conversion_goal_action(bundle) == expected


def test_apply_bundle_conversion_goal_noop_for_account_default():
    # A skip value must NOT touch Google (no SDK client needed) and must leave
    # warnings untouched — proving the no-op path never reaches setup.
    warnings: list[str] = []
    asyncio.run(
        cgs.apply_bundle_conversion_goal(
            ctx=None,
            customer_id="7178239091",
            campaign_id="24102429981",
            bundle={"conversion_goal_action_id": cgs.ACCOUNT_DEFAULT},
            warnings=warnings,
        )
    )
    assert warnings == []
