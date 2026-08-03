"""Story 14.3 — PMax validation-gap closures (FR1.4) + soft-limit channel (FR1.3).

Every NEW rejection the registry now enforces gets a test here (the task's
"gap closure ⇒ prove the new rejection" rule), plus the accept-with-warning
path for the unverified ≤60 short-description rule. All go through the refactored
``pmax_orchestrator._validate_bundle(bundle, spec)`` which returns a
``ValidationReport``.

Run: cd backend && .venv/bin/python -m pytest tests/test_creative_validation.py -q
"""

from __future__ import annotations

from typing import Any, Dict

from app.services import creative_specs
from google_ads.services.campaign import pmax_orchestrator as pmax

_SPEC = creative_specs.get("pmax")


def _valid_pmax(**over: Any) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {
        "name": "PMax Test",
        "budget_micros": 10_000_000,
        "final_urls": ["https://example.com/landing"],
        "business_name": "Example Co",
        "headlines": ["Head one", "Head two", "Head three"],
        "long_headlines": ["A long headline for the asset group"],
        # two descriptions, at least one ≤60 so the soft rule is satisfied
        "descriptions": ["Short punchy description under sixty chars.",
                         "Second description that is also reasonably short."],
        "logos": ["logo-uuid"],
        "marketing_images": {"landscape": ["land-uuid"], "square": ["sq-uuid"], "portrait": []},
        "video_youtube_ids": [],
        "audience_signals": None,
    }
    bundle.update(over)
    return bundle


def _errs(**over: Any):
    return pmax._validate_bundle(_valid_pmax(**over), _SPEC).errors


def _warns(**over: Any):
    return pmax._validate_bundle(_valid_pmax(**over), _SPEC).warnings


def _join(items):
    return "; ".join(items)


# ── the valid baseline ────────────────────────────────────────────────────────

def test_valid_bundle_has_no_errors():
    assert _errs() == []


# ── FR1.4 gap closures — each NEW rejection ───────────────────────────────────

def test_16_headlines_rejected():
    errs = _errs(headlines=[f"Headline {i}" for i in range(16)])
    assert "too many headlines: 16 (max 15)" in _join(errs)


def test_16th_headline_is_the_boundary():
    assert _errs(headlines=[f"Headline {i}" for i in range(15)]) == []       # 15 ok
    assert "too many headlines" in _join(_errs(headlines=[f"H{i}" for i in range(16)]))


def test_26_char_business_name_rejected():
    errs = _errs(business_name="z" * 26)
    assert "business_name is 26 chars (max 25)" in _join(errs)
    assert _errs(business_name="z" * 25) == []   # 25 ok


def test_21st_image_across_ratios_rejected():
    # cross-slot sum: 7 landscape + 7 square + 7 portrait = 21 > 20 (honesty #8)
    errs = _errs(marketing_images={
        "landscape": [f"l{i}" for i in range(7)],
        "square": [f"s{i}" for i in range(7)],
        "portrait": [f"p{i}" for i in range(7)],
    })
    assert "too many images: 21 across ratios (max 20 per asset group)" in _join(errs)


def test_20_images_across_ratios_ok():
    errs = _errs(marketing_images={
        "landscape": [f"l{i}" for i in range(7)],
        "square": [f"s{i}" for i in range(7)],
        "portrait": [f"p{i}" for i in range(6)],
    })
    assert not any("too many images" in e for e in errs)


def test_26th_search_theme_rejected():
    errs = _errs(audience_signals=[f"theme {i}" for i in range(26)])
    assert "too many search themes: 26 (max 25)" in _join(errs)
    assert not any("too many search themes" in e
                   for e in _errs(audience_signals=[f"theme {i}" for i in range(25)]))


def test_81_char_search_theme_rejected():
    errs = _errs(audience_signals=["t" * 81])
    assert any("search theme is 81 chars (max 80)" in e for e in errs)
    assert not any("search theme is" in e for e in _errs(audience_signals=["t" * 80]))


def test_search_theme_dict_shape_counted():
    errs = _errs(audience_signals=[{"search_theme": "t" * 81}])
    assert any("81 chars (max 80)" in e for e in errs)


def test_saved_audience_not_counted_as_search_theme():
    # a saved audience is NOT a search theme — 26 of them must not trip the cap
    sigs = [{"audience_resource_name": f"customers/1/audiences/{i}"} for i in range(26)]
    assert not any("search theme" in e for e in _errs(audience_signals=sigs))


def test_malformed_final_url_rejected():
    assert any("malformed final URL" in e for e in _errs(final_urls=["not a url"]))
    assert any("malformed final URL" in e for e in _errs(final_urls=["ftp://example.com"]))
    assert _errs(final_urls=["https://example.com/ok"]) == []


def test_too_long_headline_still_rejected():
    assert any("chars (max 30)" in e for e in _errs(headlines=["x" * 31, "b", "c"]))


# ── FR1.3 soft-limit channel — accept-with-warning ────────────────────────────

def test_zero_short_descriptions_warns_not_errors():
    # both descriptions > 60 chars ⇒ NO ≤60 short description present.
    long_descs = ["x" * 85, "y" * 85]
    errs = _errs(descriptions=long_descs)
    warns = _warns(descriptions=long_descs)
    assert not any("short description" in e for e in errs)   # NEVER an error
    assert any("short description" in w for w in warns)      # surfaced as a warning


def test_short_description_present_no_warning():
    assert not any("short description" in w for w in _warns())


def test_soft_limit_is_verified_false_in_registry():
    assert _SPEC.short_description is not None
    assert _SPEC.short_description.verified is False
