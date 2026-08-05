"""Targeting reference service + endpoints — named languages and the live geo
picker that replace the wizards' raw numeric-id inputs.

Asserts:
  - the bundled language set is English-first (id 1000), complete, well-formed;
  - the /api/targeting/languages route returns that set;
  - suggest_geo_targets maps the SDK suggestion shape → picker rows, sorts by
    reach desc, and caps to `limit` (SDK client mocked — no live call);
  - resolve_geo_targets maps ids → names, filters non-numeric, preserves order,
    and echoes unknown ids so the picker never drops a chip.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.data.google_ads_languages import (
    DEFAULT_LANGUAGE_ID,
    get_languages,
    language_name,
)
from app.routers import targeting as targeting_router
from app.services import targeting as targeting_service


def _run(coro):
    return asyncio.run(coro)


# ── bundled language data ────────────────────────────────────────────

def test_languages_english_first_and_default():
    langs = get_languages()
    assert langs[0]["id"] == "1000"
    assert langs[0]["name"] == "English"
    assert DEFAULT_LANGUAGE_ID == "1000"


def test_languages_complete_and_wellformed():
    langs = get_languages()
    assert len(langs) == 51
    ids = {lang["id"] for lang in langs}
    assert len(ids) == 51  # no dupes
    for lang in langs:
        assert lang["id"].isdigit()
        assert lang["name"]
        assert lang["code"]
    # spot-check a couple of well-known constants
    assert language_name("1003") == "Spanish"
    assert language_name("1019") == "Arabic"
    # unknown id echoes back
    assert language_name("999999") == "999999"
    # NO "English (Australia)" pseudo-language exists in the set
    assert not any("australia" in lang["name"].lower() for lang in langs)


def test_languages_route_returns_english_first():
    out = _run(targeting_router.list_languages())
    assert out[0].id == "1000"
    assert out[0].name == "English"
    assert len(out) == 51


# ── geo suggest (SDK mocked) ─────────────────────────────────────────

class _FakeGeo:
    def __init__(self, gid, name, canon, ttype, cc):
        self.id = gid
        self.name = name
        self.canonical_name = canon
        self.target_type = ttype
        self.country_code = cc


class _FakeSuggestion:
    def __init__(self, geo, reach):
        self.geo_target_constant = geo
        self.reach = reach


class _FakeService:
    def __init__(self, suggestions):
        self._suggestions = suggestions

    def suggest_geo_target_constants(self, request=None):  # noqa: ARG002
        return SimpleNamespace(geo_target_constant_suggestions=self._suggestions)


class _FakeClient:
    def __init__(self, suggestions):
        self._suggestions = suggestions

    def get_service(self, _name):
        return _FakeService(self._suggestions)

    def get_type(self, _name):
        # MagicMock-free stand-in: only attribute assignment + .names.extend used
        return SimpleNamespace(
            locale="", country_code="",
            location_names=SimpleNamespace(names=[]),
        )


def test_suggest_geo_targets_maps_sorts_and_caps(monkeypatch):
    suggestions = [
        _FakeSuggestion(_FakeGeo(1000013, "Dubai", "Dubai,Dubai,UAE", "City", "AE"), 11_400_000),
        _FakeSuggestion(_FakeGeo(9041083, "Dubai", "Dubai,UAE", "Province", "AE"), 11_400_000),
        _FakeSuggestion(_FakeGeo(9197694, "Dubai Marina", "Dubai Marina,Dubai,UAE", "Neighborhood", "AE"), 218_000),
    ]
    monkeypatch.setattr(
        targeting_service, "_build_client", lambda: _FakeClient(suggestions)
    )
    rows = _run(targeting_service.suggest_geo_targets("Dubai", limit=2))
    assert len(rows) == 2  # capped
    ids = {r["id"] for r in rows}
    assert ids == {"1000013", "9041083"}  # the two highest-reach
    assert rows[0]["name"] == "Dubai"
    assert rows[0]["country_code"] == "AE"
    assert rows[0]["target_type"] in ("City", "Province")


def test_suggest_geo_targets_empty_query_short_circuits(monkeypatch):
    def _boom():  # pragma: no cover - must never be called
        raise AssertionError("SDK client must not be built for an empty query")

    monkeypatch.setattr(targeting_service, "_build_client", _boom)
    assert _run(targeting_service.suggest_geo_targets("   ")) == []


# ── geo resolve (query mocked) ───────────────────────────────────────

def test_resolve_geo_targets_maps_and_preserves_order(monkeypatch):
    rows = [
        SimpleNamespace(geo_target_constant=_FakeGeo(2400, "Jordan", "Jordan", "Country", "JO")),
        SimpleNamespace(geo_target_constant=_FakeGeo(2512, "Oman", "Oman", "Country", "OM")),
    ]

    def _fake_run_query(_cid, _q):
        return rows

    monkeypatch.setattr(targeting_service, "_run_query", _fake_run_query)
    out = _run(targeting_service.resolve_geo_targets(["2512", "2400", "abc"]))
    # non-numeric filtered; order preserved (2512 then 2400)
    assert [r["id"] for r in out] == ["2512", "2400"]
    assert out[0]["name"] == "Oman"
    assert out[1]["name"] == "Jordan"


def test_resolve_geo_targets_unknown_id_echoes(monkeypatch):
    monkeypatch.setattr(targeting_service, "_run_query", lambda _c, _q: [])
    out = _run(targeting_service.resolve_geo_targets(["999999"]))
    assert out == [{"id": "999999", "name": "999999", "canonical_name": "999999"}]


def test_resolve_geo_targets_all_nonnumeric_returns_empty(monkeypatch):
    def _boom(_c, _q):  # pragma: no cover - must never be called
        raise AssertionError("no query for all-invalid ids")

    monkeypatch.setattr(targeting_service, "_run_query", _boom)
    assert _run(targeting_service.resolve_geo_targets(["x", ""])) == []
