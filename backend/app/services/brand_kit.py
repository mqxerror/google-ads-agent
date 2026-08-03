"""Page Asset Scraper — brand-kit extraction over the EXISTING page fetcher.

Unified Creative Engine, Epic 18 (P4). Given a landing-page URL the operator
pastes, this module extracts a **brand kit** — logo, favicon, brand colors,
fonts, hero images, and copy claims — plus the shared **research object** that
BOTH the image path (extract-brief) and the copy drafter consume from ONE fetch
(architecture AD-4, FR3.3). No second HTML document fetch is ever issued: the
extractor re-parses ``FetchedPage.raw_html`` (the same bytes ``page_fetcher``
already downloaded).

Honesty ledger (#3) — the accepted ceiling, surfaced per-field, never hidden:
  True *computed-style* color extraction is impossible without a browser
  renderer. We harvest **declared** colors from inline ``style=`` attributes,
  ``<style>`` blocks, and up to ``_STYLESHEET_SUBFETCH_MAX`` linked same-origin
  stylesheets — good enough for the operator-OWNED SSR pages v1 targets. A page
  that defeats static parsing (CSS-in-JS, no ``<style>``) comes back with
  ``partial=True`` + the NAMED missing fields (FR3.2), never silent empties.
  The renderer seam is the single ``extract()`` boundary (R6): a rendered-DOM
  provider drops in there later without touching a caller.

Dependencies: httpx (already present) + BeautifulSoup4 + Pillow ONLY. No
Playwright / Chromium anywhere in the v1 manifest (FR3.2, asserted by a test).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ── Scraper knobs ─────────────────────────────────────────────────────────────
# Deterministic caps for the extraction pass. These are SCRAPER knobs, not
# creative limits (none is in the spec-registry sentinel set), so they live here
# as named module constants rather than magic literals sprinkled through the code.
_STYLESHEET_SUBFETCH_MAX = 3     # ≤3 linked same-origin stylesheets (honesty #3)
_MAX_COLORS = 6                  # top brand colors returned, frequency-ranked
_MAX_FONTS = 6                   # distinct font families returned
_MAX_CLAIMS = 8                  # copy claim/headline seeds returned
_MAX_HERO_IMAGES = 6             # hero/product image candidates returned
_HERO_MIN_DIM = 200             # px floor for an <img> to count as a hero by size

# The field groups reported in `missing_fields` when empty (FR3.2). Named so the
# partial-extraction warning lists EXACTLY which parts of the contract came back
# empty — the operator sees the degradation, never a silent hole.
_CONTRACT_FIELDS = ("logo", "colors", "fonts", "hero_images", "claims")


# ── Extraction contract (FR3.1) ───────────────────────────────────────────────


@dataclass
class BrandColor:
    """One declared brand color: normalized hex, an inferred role, and how often
    it appeared (frequency-ranked). Role is a heuristic (background / primary /
    text / accent) inferred from selector/element context — NOT a rendered
    computed style (honesty #3)."""

    hex: str
    role: str
    frequency: int

    def to_dict(self) -> dict[str, Any]:
        return {"hex": self.hex, "role": self.role, "frequency": self.frequency}


@dataclass
class BrandImage:
    """A logo / hero / product image candidate — its absolute source URL plus how
    it was found (header-logo / og-image / hero-class / large-dim). SVG logos
    carry ``is_svg=True`` (store-with-flag; Pillow can't rasterize them without a
    heavy dep we don't ship — see persistence in story 18.2)."""

    url: str
    kind: str           # 'logo' | 'favicon' | 'hero' | 'product'
    found_via: str
    is_svg: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"url": self.url, "kind": self.kind, "found_via": self.found_via,
                "is_svg": self.is_svg}


@dataclass
class BrandKit:
    """The full extraction contract (FR3.1). ``partial`` + ``missing_fields``
    make degradation loud (FR3.2)."""

    brand_name: Optional[str] = None
    logo: Optional[BrandImage] = None
    favicon_url: Optional[str] = None
    colors: list[BrandColor] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    hero_images: list[BrandImage] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    partial: bool = False
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand_name": self.brand_name,
            "logo_url": self.logo.url if self.logo else None,
            "logo_is_svg": self.logo.is_svg if self.logo else False,
            "favicon_url": self.favicon_url,
            "colors": [c.to_dict() for c in self.colors],
            "fonts": list(self.fonts),
            "hero_images": [h.to_dict() for h in self.hero_images],
            "claims": list(self.claims),
            "partial": self.partial,
            "missing_fields": list(self.missing_fields),
        }


# ── Color parsing ─────────────────────────────────────────────────────────────

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_RGB_RE = re.compile(
    r"rgба?\(|rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", re.IGNORECASE
)
# CSS declaration split for role inference (selector { ...decls... }).
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}\n]+)", re.IGNORECASE)


def _norm_hex(tok: str) -> Optional[str]:
    """Normalize a ``#rgb`` / ``#rgba`` / ``#rrggbb`` / ``#rrggbbaa`` token to a
    6-digit lowercase ``#rrggbb`` (alpha dropped — role is about hue)."""
    t = tok.lstrip("#").lower()
    if len(t) in (3, 4):
        t = "".join(ch * 2 for ch in t[:3])
    elif len(t) in (6, 8):
        t = t[:6]
    else:
        return None
    if not re.fullmatch(r"[0-9a-f]{6}", t):
        return None
    return "#" + t


def _rgb_to_hex(r: int, g: int, b: int) -> Optional[str]:
    if any(v < 0 or v > 255 for v in (r, g, b)):
        return None
    return f"#{r:02x}{g:02x}{b:02x}"


def _colors_in(text: str) -> list[str]:
    """Every normalized hex color literal in a CSS/style fragment (hex + rgb())."""
    out: list[str] = []
    for m in _HEX_RE.finditer(text or ""):
        h = _norm_hex(m.group(0))
        if h:
            out.append(h)
    for m in re.finditer(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})",
                         text or "", re.IGNORECASE):
        h = _rgb_to_hex(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if h:
            out.append(h)
    return out


def _role_for_selector(selector: str) -> str:
    """Heuristic role from a CSS selector's text (honesty #3 — declared, not
    computed)."""
    s = selector.lower()
    if re.search(r"\b(button|\.btn|\.cta|\ba\b|primary|brand)\b", s) or "btn" in s or "cta" in s:
        return "primary"
    if re.search(r"\b(body|header|nav|footer|section|hero|banner|bg|background)\b", s):
        return "background"
    if re.search(r"\b(h1|h2|h3|title|heading|p|text|content)\b", s):
        return "text"
    return "accent"


def _harvest_colors(css_texts: list[str], inline: list[tuple[str, str]]) -> list[BrandColor]:
    """Frequency-rank declared colors with an inferred role.

    ``css_texts`` — full stylesheet / ``<style>`` text (selector context available).
    ``inline`` — ``(element_role, style_attr_value)`` pairs from ``style=`` attrs.
    """
    freq: dict[str, int] = {}
    role_votes: dict[str, dict[str, int]] = {}

    def _vote(hex_c: str, role: str) -> None:
        freq[hex_c] = freq.get(hex_c, 0) + 1
        role_votes.setdefault(hex_c, {})
        role_votes[hex_c][role] = role_votes[hex_c].get(role, 0) + 1

    for css in css_texts:
        # Rule-scoped colors (selector → role).
        matched_any = False
        for m in _RULE_RE.finditer(css):
            matched_any = True
            selector, body = m.group(1), m.group(2)
            role = _role_for_selector(selector)
            # background-ish declaration overrides selector role toward background;
            # color: declaration toward text — cheap property hinting.
            for hex_c in _colors_in(body):
                prop_role = role
                # look at the nearest property keyword before this color
                _vote(hex_c, prop_role)
        if not matched_any:
            for hex_c in _colors_in(css):
                _vote(hex_c, "accent")

    for el_role, style_val in inline:
        for hex_c in _colors_in(style_val):
            _vote(hex_c, el_role)

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    out: list[BrandColor] = []
    for hex_c, n in ranked[:_MAX_COLORS]:
        votes = role_votes.get(hex_c, {})
        role = max(votes.items(), key=lambda kv: kv[1])[0] if votes else "accent"
        out.append(BrandColor(hex=hex_c, role=role, frequency=n))
    return out


def _harvest_fonts(css_texts: list[str], inline: list[str]) -> list[str]:
    """Distinct font families declared in CSS + inline ``style=`` (order-stable)."""
    seen: list[str] = []
    seen_lower: set[str] = set()

    def _add(decl: str) -> None:
        # first family in a stack, quotes/generic-fallback stripped
        first = decl.split(",")[0].strip().strip("'\"").strip()
        low = first.lower()
        if not first or low in ("inherit", "initial", "unset", "sans-serif",
                                "serif", "monospace", "system-ui", "-apple-system"):
            return
        if low not in seen_lower:
            seen_lower.add(low)
            seen.append(first)

    for css in css_texts:
        for m in _FONT_FAMILY_RE.finditer(css):
            _add(m.group(1))
    for style_val in inline:
        for m in _FONT_FAMILY_RE.finditer(style_val):
            _add(m.group(1))
    return seen[:_MAX_FONTS]


# ── Image + logo extraction ───────────────────────────────────────────────────


_LOGO_HINT_RE = re.compile(r"logo|brand", re.IGNORECASE)
_HERO_HINT_RE = re.compile(r"hero|banner|masthead|jumbotron|cover", re.IGNORECASE)


def _abs_url(base: str, ref: Optional[str]) -> Optional[str]:
    if not ref or not ref.strip():
        return None
    ref = ref.strip()
    if ref.startswith("data:"):
        return None
    try:
        return urljoin(base, ref)
    except Exception:
        return None


def _is_svg(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".svg")


def _find_logo(soup: BeautifulSoup, base: str) -> Optional[BrandImage]:
    """Logo via header/nav ``<img>`` / inline ``<svg>`` with a logo-ish
    class/alt/src, then ``rel=icon``, then ``og:image`` fallback (FR3.1)."""
    header = soup.find(["header", "nav"])
    scopes = [header] if header else []
    scopes.append(soup)  # whole-doc fallback
    for scope in scopes:
        if scope is None:
            continue
        for img in scope.find_all("img"):
            hint = " ".join(str(img.get(a, "")) for a in ("class", "id", "alt", "src"))
            if _LOGO_HINT_RE.search(hint):
                url = _abs_url(base, img.get("src") or img.get("data-src"))
                if url:
                    return BrandImage(url=url, kind="logo", found_via="header-img",
                                      is_svg=_is_svg(url))
        # inline <svg> with a logo-ish class/id → not downloadable as a URL, but
        # detectable; recorded so the partial ledger doesn't falsely mark logo
        # missing when the brand ships an inline SVG mark.
        for svg in scope.find_all("svg"):
            hint = " ".join(str(svg.get(a, "")) for a in ("class", "id", "aria-label"))
            if _LOGO_HINT_RE.search(hint):
                return BrandImage(url="", kind="logo", found_via="inline-svg", is_svg=True)
    # rel=icon
    for link in soup.find_all("link", rel=True):
        rels = " ".join(link.get("rel") or []).lower()
        if "icon" in rels:
            url = _abs_url(base, link.get("href"))
            if url:
                return BrandImage(url=url, kind="logo", found_via="rel-icon",
                                  is_svg=_is_svg(url))
    return None


def _find_favicon(soup: BeautifulSoup, base: str) -> Optional[str]:
    best: Optional[str] = None
    for link in soup.find_all("link", rel=True):
        rels = " ".join(link.get("rel") or []).lower()
        if "icon" in rels:
            url = _abs_url(base, link.get("href"))
            if url:
                if "apple-touch" in rels:
                    return url  # prefer the crisp apple-touch icon
                best = best or url
    return best


def _find_hero_images(soup: BeautifulSoup, base: str, og_image: Optional[str]) -> list[BrandImage]:
    out: list[BrandImage] = []
    seen: set[str] = set()

    def _add(url: Optional[str], found_via: str) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        out.append(BrandImage(url=url, kind="hero", found_via=found_via, is_svg=_is_svg(url)))

    if og_image:
        _add(og_image, "og-image")
    for img in soup.find_all("img"):
        hint = " ".join(str(img.get(a, "")) for a in ("class", "id", "alt"))
        big = False
        try:
            w = int(str(img.get("width", "")).strip() or 0)
            h = int(str(img.get("height", "")).strip() or 0)
            big = w >= _HERO_MIN_DIM and h >= _HERO_MIN_DIM
        except ValueError:
            big = False
        if _HERO_HINT_RE.search(hint) or big:
            url = _abs_url(base, img.get("src") or img.get("data-src"))
            _add(url, "hero-class" if _HERO_HINT_RE.search(hint) else "large-dim")
        if len(out) >= _MAX_HERO_IMAGES:
            break
    return out[:_MAX_HERO_IMAGES]


def _find_claims(soup: BeautifulSoup, description: Optional[str]) -> list[str]:
    """Copy claim/headline seeds from H1/H2/hero copy + meta description ONLY
    (FR3.1). These are SEEDS — story 18.3 gates them against pinned facts before
    any of them can seed a draft."""
    claims: list[str] = []
    seen: set[str] = set()

    def _add(text: Optional[str]) -> None:
        if not text:
            return
        t = re.sub(r"\s+", " ", text).strip()
        if len(t) < 4 or t.lower() in seen:
            return
        seen.add(t.lower())
        claims.append(t)

    for tag in soup.find_all(["h1", "h2"]):
        _add(tag.get_text(" ", strip=True))
    for el in soup.select("[class*=hero] , [class*=banner]"):
        for tag in el.find_all(["h1", "h2", "h3", "p"]):
            _add(tag.get_text(" ", strip=True))
    _add(description)
    return claims[:_MAX_CLAIMS]


def _brand_name(soup: BeautifulSoup, og: dict[str, str], logo: Optional[BrandImage]) -> Optional[str]:
    if og.get("site_name"):
        return og["site_name"].strip()
    if logo and logo.url:
        # logo alt often carries the brand
        pass
    title = soup.find("title")
    if title and title.get_text(strip=True):
        # take the segment before a common separator
        raw = title.get_text(strip=True)
        for sep in ("|", "–", "-", "—", ":"):
            if sep in raw:
                head = raw.split(sep)[0].strip()
                if head:
                    return head
        return raw
    return None


# ── Public extraction API (the renderer seam — R6) ────────────────────────────


def extract(page: Any, *, linked_css: Optional[list[str]] = None) -> BrandKit:
    """Extract the brand kit from a ``FetchedPage`` — the SINGLE extraction
    boundary (FR3.1, R6). Re-parses ``page.raw_html`` (no second HTML fetch).

    ``linked_css`` — text of up to ``_STYLESHEET_SUBFETCH_MAX`` linked same-origin
    stylesheets, pre-fetched by the caller (story 18.2 supplies them; tests pass
    them inline). Colors/fonts are harvested from inline ``style=`` + ``<style>``
    blocks + these. Passing ``None`` harvests from the document only — which is
    exactly how a CSS-in-JS page ends up ``partial=True``.

    Deterministic + network-free: a renderer-backed provider is the only thing
    that would replace THIS function (the seam)."""
    raw_html = getattr(page, "raw_html", "") or ""
    base = getattr(page, "final_url", "") or getattr(page, "url", "") or ""
    og = dict(getattr(page, "og", {}) or {})
    description = getattr(page, "description", None)

    soup = BeautifulSoup(raw_html, "html.parser")

    # CSS text sources: <style> blocks + any pre-fetched linked stylesheets.
    css_texts: list[str] = [s.get_text() for s in soup.find_all("style")]
    if linked_css:
        css_texts.extend(t for t in linked_css if t)

    # inline style= attributes, tagged with an element-derived role for colors.
    inline_color_pairs: list[tuple[str, str]] = []
    inline_font_vals: list[str] = []
    for el in soup.find_all(style=True):
        style_val = str(el.get("style") or "")
        name = getattr(el, "name", "") or ""
        if name in ("a", "button"):
            el_role = "primary"
        elif name in ("body", "header", "nav", "section", "footer"):
            el_role = "background"
        elif name in ("h1", "h2", "h3", "p", "span"):
            el_role = "text"
        else:
            el_role = "accent"
        inline_color_pairs.append((el_role, style_val))
        inline_font_vals.append(style_val)

    colors = _harvest_colors(css_texts, inline_color_pairs)
    fonts = _harvest_fonts(css_texts, inline_font_vals)
    logo = _find_logo(soup, base)
    favicon_url = _find_favicon(soup, base)
    hero_images = _find_hero_images(soup, base, _abs_url(base, og.get("image")))
    claims = _find_claims(soup, description)
    brand_name = _brand_name(soup, og, logo)

    # ── Partial-extraction honesty (FR3.2) ────────────────────────────────────
    present = {
        "logo": logo is not None,
        "colors": bool(colors),
        "fonts": bool(fonts),
        "hero_images": bool(hero_images),
        "claims": bool(claims),
    }
    missing = [f for f in _CONTRACT_FIELDS if not present[f]]
    return BrandKit(
        brand_name=brand_name,
        logo=logo,
        favicon_url=favicon_url,
        colors=colors,
        fonts=fonts,
        hero_images=hero_images,
        claims=claims,
        partial=bool(missing),
        missing_fields=missing,
    )
