"""Story 18.1 — brand-kit extraction over the existing fetcher + partial honesty.

All tests run against LOCAL fixture HTML (no live fetches — the suite is network-
free per the epic constraint). The two fixtures exercise the two ends of the
FR3.2 honesty contract: a full SSR page (`partial=False`, every field present) and
a CSS-in-JS page (`partial=True`, NAMED missing fields).
"""

from __future__ import annotations

from pathlib import Path

from app.services import brand_kit
from app.services.page_fetcher import FetchedPage

_FIX = Path(__file__).parent / "fixtures" / "brand_kit"


def _page(name: str, *, final_url: str, og: dict | None = None,
          description: str | None = None) -> FetchedPage:
    """Build a FetchedPage from a fixture the way page_fetcher.fetch would —
    raw_html carries the same bytes brand_kit re-parses (no second fetch)."""
    html = (_FIX / name).read_text(encoding="utf-8")
    return FetchedPage(
        url=final_url, final_url=final_url, title=None, description=description,
        og=og or {}, h1=None, body_excerpt="", status=200, raw_html=html,
    )


# ── SSR page → every field present, partial=False (FR3.1) ─────────────────────


def test_ssr_page_extracts_full_contract():
    page = _page(
        "ssr_page.html",
        final_url="https://www.mercan.com/lp/panama",
        og={"site_name": "Mercan Group", "title": "Panama Golden Visa",
            "image": "https://cdn.example.com/og/panama-hero.jpg"},
        description="Secure Panama residency by investment with Mercan Group's trusted program.",
    )
    kit = brand_kit.extract(page)

    assert kit.partial is False
    assert kit.missing_fields == []

    # brand name from og:site_name
    assert kit.brand_name == "Mercan Group"

    # logo from the header <img> with a logo-ish class/alt, absolute-resolved
    assert kit.logo is not None
    assert kit.logo.url == "https://www.mercan.com/img/mercan-logo.png"
    assert kit.logo.found_via == "header-img"

    # favicon prefers apple-touch, absolute-resolved
    assert kit.favicon_url == "https://www.mercan.com/apple-touch-icon.png"

    # colors: hex harvested + role-inferred + frequency-ranked
    hexes = {c.hex for c in kit.colors}
    assert "#0e3560" in hexes            # brand navy
    assert "#d4b26b" in hexes            # brand gold
    # the gold sits on button/cta selectors → primary role
    gold = next(c for c in kit.colors if c.hex == "#d4b26b")
    assert gold.role == "primary"

    # fonts: first family in each declared stack, generics stripped
    assert "Inter" in kit.fonts
    assert "Poppins" in kit.fonts
    assert "sans-serif" not in [f.lower() for f in kit.fonts]

    # hero images: og:image + hero-classed/large <img>, absolute
    hero_urls = {h.url for h in kit.hero_images}
    assert "https://cdn.example.com/og/panama-hero.jpg" in hero_urls
    assert "https://www.mercan.com/img/panama-skyline.jpg" in hero_urls

    # claims come from H1/H2/hero + meta description ONLY
    assert any("Panama Residency by Investment" in c for c in kit.claims)
    assert any("whole family" in c for c in kit.claims)
    assert any("Secure Panama residency" in c for c in kit.claims)


def test_ssr_linked_stylesheet_colors_are_included():
    """A color present ONLY in a linked same-origin stylesheet (pre-fetched by the
    caller, ≤3) is harvested and role-inferred — the honesty-#3 sub-fetch path."""
    page = _page("ssr_page.html", final_url="https://www.mercan.com/lp/panama",
                 og={"site_name": "Mercan Group"})
    linked = [".promo-badge { background: #ff5722; }"]
    kit = brand_kit.extract(page, linked_css=linked)
    assert "#ff5722" in {c.hex for c in kit.colors}


# ── CSS-in-JS page → partial=True + NAMED missing fields (FR3.2) ──────────────


def test_css_in_js_page_is_partial_with_named_missing_fields():
    page = _page("css_in_js_page.html", final_url="https://example.com/greece",
                 og={"title": "Greece Golden Visa"},
                 description="Greece residency by investment.")
    kit = brand_kit.extract(page)

    assert kit.partial is True
    # colors + fonts defeated by CSS-in-JS → named as missing, never silently empty
    assert "colors" in kit.missing_fields
    assert "fonts" in kit.missing_fields
    assert kit.colors == []
    assert kit.fonts == []

    # the H1 claim still parses from static HTML (proves it's not a blanket fail)
    assert any("Greece Residency by Investment" in c for c in kit.claims)
    assert "claims" not in kit.missing_fields


# ── Renderer-seam / manifest guarantees (FR3.2) ──────────────────────────────


def test_no_headless_browser_in_dependency_manifest():
    """The v1 manifest ships NO Playwright / Chromium / Selenium (D2). The seam
    for a rendered-DOM provider is the single extract() boundary, not a shipped
    browser."""
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text().lower()
    for banned in ("playwright", "chromium", "selenium", "pyppeteer"):
        assert banned not in pyproject, f"{banned!r} must not be a v1 dependency"


def test_extract_is_the_single_renderer_seam():
    """extract() is callable with just a page (no network) — the seam a renderer
    would replace. A page with empty raw_html degrades to all-missing, never
    raises."""
    empty = FetchedPage(url="https://x.test", final_url="https://x.test", title=None,
                        description=None, og={}, h1=None, body_excerpt="", status=200,
                        raw_html="")
    kit = brand_kit.extract(empty)
    assert kit.partial is True
    assert set(kit.missing_fields) == set(brand_kit._CONTRACT_FIELDS)
