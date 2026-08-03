"""Story 14.1 — Creative Spec Registry module + GET /api/creative/specs.

Asserts the registry shape (AD-1), the PRD §8 seed values (reconciled with the
Google-verified count minimums — see creative_specs module docstring), fence F2
(geometry composed by import, identity not copy), fence F4 (frozen), and the
endpoint (shape, <100 ms perf, round-trip deep-equality with REGISTRY).

Run: cd backend && .venv/bin/python -m pytest tests/test_creative_specs.py -q
"""

from __future__ import annotations

import time

import pytest
from dataclasses import FrozenInstanceError
from fastapi.testclient import TestClient

from app.services import creative_specs as cs
from app.services.creative_specs import (
    CampaignSpec,
    EngineConfig,
    ImageSlotSpec,
    PolicyKnobs,
    TextFieldSpec,
    VideoSpec,
)
from google_ads.services.campaign.creative_images import IMAGE_SLOT_SPECS


# ── shape (AD-1) ─────────────────────────────────────────────────────────────

def test_registry_covers_three_campaign_types():
    assert set(cs.REGISTRY.keys()) == {"pmax", "demand_gen", "rda"}
    for spec in cs.REGISTRY.values():
        assert isinstance(spec, CampaignSpec)


def test_engine_block_defaults():
    assert isinstance(cs.ENGINE, EngineConfig)
    assert cs.ENGINE.near_dup_threshold == 0.65
    assert cs.ENGINE.batch_tile_cap == 20
    assert cs.ENGINE.batch_retry_max == 2


def test_dataclasses_exist_per_ad1():
    # Instantiability of each frozen dataclass named in AD-1 / story 14.1.
    assert TextFieldSpec(1, 5, 30, True, "s").max_chars == 30
    assert ImageSlotSpec("landscape", 20, True, True, "s").slot == "landscape"
    assert PolicyKnobs("forbid", "forbid", "nudge").video_gate == "nudge"
    assert VideoSpec(15, 10, False, False, "s").max_per_orientation == 15


# ── PRD §8 seed values (verbatim where verified; reconciled minimums) ─────────

def test_pmax_text_seeds():
    t = cs.get("pmax").text
    assert (t["headlines"].min_count, t["headlines"].max_count, t["headlines"].max_chars) == (3, 15, 30)
    assert (t["long_headlines"].min_count, t["long_headlines"].max_count, t["long_headlines"].max_chars) == (1, 5, 90)
    # Google-verified hard minimum is 2 (not the PRD's recommended 3).
    assert (t["descriptions"].min_count, t["descriptions"].max_count, t["descriptions"].max_chars) == (2, 5, 90)
    for f in t.values():
        assert f.verified is True


def test_pmax_gap_closure_data():
    spec = cs.get("pmax")
    assert spec.business_name_max == 25
    assert spec.total_image_cap == 20
    assert spec.search_themes == (25, 80)
    assert spec.final_url_max == 2048


def test_pmax_short_description_is_soft():
    sd = cs.get("pmax").short_description
    assert sd is not None
    assert sd.max_chars == 60
    assert sd.min_count == 1
    assert sd.verified is False  # ≤60 not in current Google docs — soft only


def test_pmax_video_unverified():
    v = cs.get("pmax").video
    assert v.max_per_orientation == 15
    assert v.verified is False  # 5-vs-15 conflict


def test_demand_gen_text_seeds():
    t = cs.get("demand_gen").text
    assert (t["headlines"].min_count, t["headlines"].max_count, t["headlines"].max_chars) == (1, 5, 40)
    assert (t["descriptions"].min_count, t["descriptions"].max_count, t["descriptions"].max_chars) == (1, 5, 90)
    assert t["headlines"].verified is True
    assert cs.get("demand_gen").search_themes is None
    assert cs.get("demand_gen").short_description is None


def test_dg_headline_is_40_not_30():
    # The DG 30-vs-40 bug this whole epic exists to kill.
    assert cs.get("demand_gen").text["headlines"].max_chars == 40


def test_rda_ships_as_data_all_unverified():
    spec = cs.get("rda")
    assert spec.text["long_headlines"].min_count == 1
    assert spec.text["long_headlines"].max_count == 1   # exactly 1
    assert spec.text["headlines"].max_chars == 30
    for f in spec.text.values():
        assert f.verified is False
    for slot in {**spec.images, **spec.logos}.values():
        assert slot.verified is False
    assert "landscape_logo" in spec.logos       # 4:1 field type ships as data


def test_policy_knobs_defaults_forbid():
    assert cs.get("pmax").policy.on_image_text == "forbid"
    assert cs.get("demand_gen").policy.on_image_text == "forbid"
    assert cs.get("rda").policy.on_image_text == "forbid"
    # PMax allows logo overlay (composite mode); DG/RDA forbid (dedicated slot).
    assert cs.get("pmax").policy.logo_overlay == "allow_warned"
    assert cs.get("demand_gen").policy.logo_overlay == "forbid"
    assert cs.get("rda").policy.logo_overlay == "forbid"
    for t in ("pmax", "demand_gen", "rda"):
        assert cs.get(t).policy.video_gate == "nudge"


# ── fence F2 — geometry composed BY IMPORT, identity not copy ─────────────────

def test_geometry_is_identity_not_copy():
    land = cs.get("pmax").images["landscape"]
    assert land.geometry is IMAGE_SLOT_SPECS["landscape"]   # SAME object
    assert land.aspect == IMAGE_SLOT_SPECS["landscape"]["aspect"]
    sq = cs.get("demand_gen").images["square"]
    assert sq.geometry is IMAGE_SLOT_SPECS["square"]


def test_geometry_none_for_slot_absent_until_p3():
    # landscape_logo (4:1) is not in the crop pipeline until P3 / story 17.5.
    ll = cs.get("pmax").logos["landscape_logo"]
    assert ll.geometry is None
    assert ll.aspect is None


# ── fence F4 — frozen (mutation raises) ───────────────────────────────────────

def test_campaign_spec_is_frozen():
    spec = cs.get("pmax")
    with pytest.raises(FrozenInstanceError):
        spec.business_name_max = 1  # type: ignore[misc]


def test_nested_specs_are_frozen():
    spec = cs.get("pmax")
    with pytest.raises(FrozenInstanceError):
        spec.text["headlines"].max_chars = 999  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        spec.policy.on_image_text = "allow_warned"  # type: ignore[misc]


# ── endpoint (shape, perf, round-trip) ────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def test_endpoint_shape(client):
    r = client.get("/api/creative/specs")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"campaign_types", "engine", "taxonomy", "version"}
    assert set(body["campaign_types"].keys()) == {"pmax", "demand_gen", "rda"}
    assert body["engine"]["near_dup_threshold"] == 0.65
    # Copy-Workbench taxonomy served for the frontend (Epic 16, AD-2).
    assert body["taxonomy"]["angles"] == list(cs.ANGLES)
    assert body["taxonomy"]["tiers"] == list(cs.TIERS)
    assert body["version"] == cs.VERSION


def test_endpoint_under_100ms(client):
    # Warm once, then measure (NFR-P2: static data, cacheable).
    client.get("/api/creative/specs")
    t0 = time.perf_counter()
    r = client.get("/api/creative/specs")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    assert elapsed_ms < 100, f"specs endpoint took {elapsed_ms:.1f} ms"


def test_endpoint_round_trips_to_registry(client):
    # The round-trip half of the CI guard: the wire form deserializes back to an
    # object deep-equal to REGISTRY, so the endpoint cannot drift from the module.
    body = client.get("/api/creative/specs").json()
    rebuilt = cs.deserialize_registry(body["campaign_types"])
    assert rebuilt == cs.REGISTRY


def test_serialize_deserialize_identity():
    assert cs.deserialize_registry(cs.serialize_registry()) == cs.REGISTRY
