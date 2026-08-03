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

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import get_db
from google_ads.services.campaign.creative_images import MAX_GOOGLE_IMAGE_BYTES

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

# Subordinate asset fetches (linked stylesheets, image downloads) — these are
# NOT HTML-document fetches and are counted separately by FR3.3's fetch-count spy
# (the spy watches page_fetcher.fetch). Kept tight because the source URL is
# operator-supplied → public.
_ASSET_FETCH_TIMEOUT_S = 8.0
_MAX_STYLESHEET_BYTES = 2 * 1024 * 1024     # 2MB per linked stylesheet
# Download cap BEFORE transcode = 3× Google's 5MB post-transcode ceiling, so a
# large source can still be compressed down. Derived from the imported cap (no
# baked byte literal — creative-limit numbers live in creative_images / registry).
_MAX_IMAGE_BYTES = 3 * MAX_GOOGLE_IMAGE_BYTES
_BRAND_LABEL_MAX = 48                        # brand-kit row filename label length
_ASSET_USER_AGENT = "google-ads-agent/0.1 (+studio brand-kit fetcher)"

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


# ─────────────────────────────────────────────────────────────────────────────
# Story 18.2 — the shared research object (ONE fetch, two consumers) + persistence
# ─────────────────────────────────────────────────────────────────────────────


def research_object(page: Any) -> dict[str, Any]:
    """The SHARED, deterministic, LLM-free research object that BOTH the image
    path (extract-brief Stage-1) and the copy drafter consume (FR3.3). It is the
    page signals Stage-1 already reads — so refactoring extract-brief onto this is
    behavior-stable — never a second fetch. ``research_hash`` over this object is
    the identity both consumers assert on their job row."""
    return {
        "url": getattr(page, "url", "") or "",
        "final_url": getattr(page, "final_url", "") or "",
        "title": getattr(page, "title", None),
        "description": getattr(page, "description", None),
        "og": dict(getattr(page, "og", {}) or {}),
        "h1": getattr(page, "h1", None),
        "body_excerpt": getattr(page, "body_excerpt", "") or "",
    }


def research_hash(obj: dict[str, Any]) -> str:
    """Stable content hash of a research object — the FR3.3 identity token. Same
    page content → same hash on every consumer, so the image path and the copy
    drafter can be PROVEN to have received the same object (job-row assert)."""
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ── Subordinate asset fetches (NOT HTML-document fetches — FR3.3 spy) ──────────


def _same_origin(base: str, url: str) -> bool:
    try:
        b, u = urlparse(base), urlparse(url)
        return (b.scheme, b.netloc) == (u.scheme, u.netloc) or b.netloc == u.netloc
    except Exception:
        return False


async def fetch_linked_css(page: Any, *, client: Optional[httpx.AsyncClient] = None) -> list[str]:
    """Fetch up to ``_STYLESHEET_SUBFETCH_MAX`` linked SAME-ORIGIN stylesheets so
    ``extract`` can harvest their declared colors/fonts (honesty #3). These are
    subordinate ASSET fetches — the FR3.3 fetch-count spy watches
    ``page_fetcher.fetch`` (HTML documents), which these deliberately are not."""
    raw_html = getattr(page, "raw_html", "") or ""
    base = getattr(page, "final_url", "") or getattr(page, "url", "") or ""
    soup = BeautifulSoup(raw_html, "html.parser")
    hrefs: list[str] = []
    for link in soup.find_all("link", rel=True):
        rels = " ".join(link.get("rel") or []).lower()
        if "stylesheet" in rels:
            abs_u = _abs_url(base, link.get("href"))
            if abs_u and _same_origin(base, abs_u):
                hrefs.append(abs_u)
        if len(hrefs) >= _STYLESHEET_SUBFETCH_MAX:
            break

    if not hrefs:
        return []
    out: list[str] = []
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=_ASSET_FETCH_TIMEOUT_S, follow_redirects=True,
        headers={"User-Agent": _ASSET_USER_AGENT},
    )
    try:
        for href in hrefs:
            try:
                r = await client.get(href)
                if r.status_code < 400 and len(r.content) <= _MAX_STYLESHEET_BYTES:
                    out.append(r.text)
            except httpx.RequestError as e:
                logger.info("brand_kit: stylesheet sub-fetch failed %s: %s", href, e)
    finally:
        if owns_client:
            await client.aclose()
    return out


async def _download_image(url: str, *, client: Optional[httpx.AsyncClient] = None
                          ) -> Optional[tuple[bytes, str]]:
    """Download an image (subordinate asset fetch). Returns ``(bytes, content_type)``
    or ``None`` on failure / over-cap."""
    owns_client = client is None
    client = client or httpx.AsyncClient(
        timeout=_ASSET_FETCH_TIMEOUT_S, follow_redirects=True,
        headers={"User-Agent": _ASSET_USER_AGENT},
    )
    try:
        r = await client.get(url)
        if r.status_code >= 400 or len(r.content) > _MAX_IMAGE_BYTES:
            return None
        return r.content, (r.headers.get("content-type") or "").split(";")[0].strip()
    except httpx.RequestError as e:
        logger.info("brand_kit: image download failed %s: %s", url, e)
        return None
    finally:
        if owns_client:
            await client.aclose()


def _min_dims_for(kind: str) -> tuple[int, int]:
    """Min-size floor for a scraped image, IMPORTED from creative_images (never a
    baked literal — fence F2). Logos use the 1:1 logo minimum; heroes/products
    use the square marketing minimum so tracking pixels / tiny icons are rejected
    before they enter the library."""
    from google_ads.services.campaign.creative_images import IMAGE_SLOT_SPECS
    slot = "logos" if kind in ("logo", "favicon") else "square"
    spec = IMAGE_SLOT_SPECS[slot]
    return spec["min_w"], spec["min_h"]


def validate_scraped_image(raw: bytes, kind: str) -> Optional[tuple[bytes, str, int, int]]:
    """Run a downloaded image through the EXISTING creative_images validation:
    open with Pillow (reject non-images), enforce the imported min-size floor
    (reject tiny junk), and transcode under Google's 5MB cap via
    ``encode_for_google``. Returns ``(bytes, mime, w, h)`` or ``None`` (rejected).

    SVG is handled by the caller (store-with-flag) — Pillow can't rasterize it
    without a heavy dep we don't ship."""
    from io import BytesIO

    from PIL import Image
    from google_ads.services.campaign.creative_images import encode_for_google

    try:
        with Image.open(BytesIO(raw)) as opened:
            opened.load()
            w, h = opened.size
            if not w or not h:
                return None
            min_w, min_h = _min_dims_for(kind)
            if w < min_w or h < min_h:
                logger.info("brand_kit: rejected %s image %dx%d (below %dx%d floor)",
                            kind, w, h, min_w, min_h)
                return None
            encoded = encode_for_google(opened)
            if encoded is None:
                logger.info("brand_kit: %s image can't compress under the 5MB cap", kind)
                return None
            data, mime = encoded
            return data, mime, w, h
    except Exception as e:  # noqa: BLE001 — a bad image is a rejection, not a crash
        logger.info("brand_kit: image validation failed (%s): %s", kind, e)
        return None


# ── Persistence (ad_assets, source='scraped' — no new table) ──────────────────

_ASSETS_DIR = settings.DATA_DIR / "ad_assets"
_MIME_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
             "image/webp": ".webp", "image/svg+xml": ".svg"}


async def _persist_image(*, account_id: Optional[str], campaign_id: Optional[str],
                         img: BrandImage, client: httpx.AsyncClient) -> Optional[str]:
    """Download + validate + store ONE scraped image as an ``ad_assets`` row
    (``source='scraped'``, pickable in LibraryPicker unchanged). Returns the new
    asset id, or ``None`` when the image was rejected / undownloadable.

    SVG logos are STORED-WITH-FLAG (``meta_json.svg=true``): kept in the library
    and referenced by the brand kit, but flagged as needing rasterization before
    use in Google raster image slots (no heavy SVG dep shipped)."""
    if not img.url:
        return None
    dl = await _download_image(img.url, client=client)
    if dl is None:
        return None
    raw, content_type = dl
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    asset_id = str(uuid.uuid4())

    if img.is_svg or content_type == "image/svg+xml":
        # store-with-flag: no Pillow validation (can't rasterize without a heavy dep)
        if len(raw) > _MAX_IMAGE_BYTES:
            return None
        ext = ".svg"
        data = raw
        width = height = None
        meta = {"svg": True, "rasterized": False, "found_via": img.found_via,
                "note": "SVG asset — rasterize before use in Google raster image slots"}
    else:
        validated = validate_scraped_image(raw, img.kind)
        if validated is None:
            return None
        data, mime, width, height = validated
        ext = _MIME_EXT.get(mime, ".png")
        meta = {"found_via": img.found_via}

    stored_name = f"{asset_id}{ext}"
    (_ASSETS_DIR / stored_name).write_bytes(data)
    public_url = f"/api/assets/file/{stored_name}"
    filename = Path(urlparse(img.url).path).name or f"scraped{ext}"

    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO ad_assets (id, account_id, campaign_id, type, filename, url, "
            "width, height, size_bytes, source, meta_json) "
            "VALUES (?, ?, ?, 'image', ?, ?, ?, ?, ?, 'scraped', ?)",
            (asset_id, account_id, campaign_id, filename, public_url, width, height,
             len(data), json.dumps(meta)),
        )
        await db.commit()
    finally:
        await db.close()
    return asset_id


async def persist_brand_kit(
    *, account_id: Optional[str], campaign_id: Optional[str], kit: BrandKit,
    gated_claims: list[str], research_hash_val: str,
) -> dict[str, Any]:
    """Persist a brand kit into the library (FR3.3): each downloadable logo/hero
    image becomes an ``ad_assets`` row (``source='scraped'``); the non-file fields
    (brand_name, colors, fonts, RAW claims) persist as ONE ``ad_assets`` row of
    ``type='brand_kit'`` whose ``meta_json`` carries the kit + its sibling image
    ids — account-scoped, no new table. Returns the persisted ids + counts."""
    logo_asset_id: Optional[str] = None
    hero_asset_ids: list[str] = []
    async with httpx.AsyncClient(
        timeout=_ASSET_FETCH_TIMEOUT_S, follow_redirects=True,
        headers={"User-Agent": _ASSET_USER_AGENT},
    ) as client:
        if kit.logo is not None:
            logo_asset_id = await _persist_image(
                account_id=account_id, campaign_id=campaign_id, img=kit.logo, client=client)
        for hero in kit.hero_images:
            hid = await _persist_image(
                account_id=account_id, campaign_id=campaign_id, img=hero, client=client)
            if hid:
                hero_asset_ids.append(hid)

    kit_asset_id = str(uuid.uuid4())
    # RAW claims live on the brand-kit row (so a claim "appears in the raw brand
    # kit" — FR3.4); the GATED seed set is what feeds copy (story 18.3).
    meta = {
        **kit.to_dict(),
        "gated_claims": gated_claims,
        "logo_asset_id": logo_asset_id,
        "hero_asset_ids": hero_asset_ids,
        "research_hash": research_hash_val,
    }
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO ad_assets (id, account_id, campaign_id, type, filename, url, "
            "source, meta_json) VALUES (?, ?, ?, 'brand_kit', ?, '', 'scraped', ?)",
            (kit_asset_id, account_id, campaign_id,
             f"brand-kit-{(kit.brand_name or 'site')[:_BRAND_LABEL_MAX]}", json.dumps(meta)),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "kit_asset_id": kit_asset_id,
        "logo_asset_id": logo_asset_id,
        "hero_asset_ids": hero_asset_ids,
        "hero_images": hero_asset_ids,
    }


async def load_brand_kit_by_hash(account_id: Optional[str], research_hash_val: str
                                 ) -> Optional[dict[str, Any]]:
    """Load a persisted brand-kit row's ``meta_json`` by its ``research_hash`` —
    how a copy-job receives the SAME research object the scrape produced (FR3.3
    identity). Account-scoped."""
    if not research_hash_val:
        return None
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT meta_json FROM ad_assets WHERE type='brand_kit' AND account_id IS ? "
            "AND meta_json LIKE ? ORDER BY created_at DESC LIMIT 1",
            (account_id, f'%"research_hash": "{research_hash_val}"%'),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row or not row["meta_json"]:
        return None
    try:
        return json.loads(row["meta_json"])
    except (ValueError, TypeError):
        return None


# ── Ownership allowlist + robots posture (FR3.5 · R4) ─────────────────────────
#
# Fail-closed by design: a URL whose registrable domain is NOT on the
# `creative.owned_domains` config allowlist is REFUSED unless the caller passes
# `confirm_ownership=true`; every URL (owned or confirmed) must also pass
# robots.txt. Widening beyond owned properties stays a REVIEW, not a config flip
# (R4) — the allowlist is seeded (mercan.com), the confirm flag is per-request,
# and there is no code path that scrapes an unowned, unconfirmed URL.

# Seed fallback when the config row is absent (init_db seeds the row idempotently;
# this keeps the guard fail-closed even before the first boot writes it).
_DEFAULT_OWNED_DOMAINS = ("mercan.com",)
_OWNED_DOMAINS_KEY = "creative.owned_domains"

# robots.txt is fetched ONCE per host (cached) — a subordinate fetch, not an HTML
# document fetch (the FR3.3 spy is unaffected). Value None ⇒ no robots / fetch
# failed ⇒ allowed (fail-open on robots, fail-CLOSED on ownership).
_ROBOTS_CACHE: dict[str, Any] = {}


class ScrapeRefused(RuntimeError):
    """Raised when a scrape is refused by the ownership / robots posture (FR3.5).
    ``reason`` names the posture so the router can surface it verbatim."""

    def __init__(self, reason: str, status_code: int = 422):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


async def _owned_domains() -> list[str]:
    """The ``creative.owned_domains`` allowlist from the config table (JSON list),
    falling back to the seed default if the row is missing/malformed."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT value FROM config WHERE key = ?", (_OWNED_DOMAINS_KEY,))
        row = await cur.fetchone()
    finally:
        await db.close()
    if row and row["value"]:
        try:
            val = json.loads(row["value"])
            if isinstance(val, list) and val:
                return [str(d).strip().lower() for d in val if str(d).strip()]
        except (ValueError, TypeError):
            pass
    return list(_DEFAULT_OWNED_DOMAINS)


def _registrable_match(host: str, domain: str) -> bool:
    """True when ``host`` is ``domain`` or a subdomain of it (www.mercan.com and
    goldenvisas.mercan.com both match ``mercan.com``)."""
    host = (host or "").lower().rstrip(".")
    domain = (domain or "").lower().rstrip(".")
    return bool(domain) and (host == domain or host.endswith("." + domain))


async def _is_owned(url: str) -> bool:
    host = urlparse(url).hostname or ""
    domains = await _owned_domains()
    return any(_registrable_match(host, d) for d in domains)


async def _fetch_robots_txt(base_url: str) -> Optional[str]:
    """Fetch a host's robots.txt text (subordinate fetch). Returns None on any
    failure — robots is fail-OPEN, ownership is the fail-CLOSED gate."""
    parts = urlparse(base_url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        async with httpx.AsyncClient(
            timeout=_ASSET_FETCH_TIMEOUT_S, follow_redirects=True,
            headers={"User-Agent": _ASSET_USER_AGENT},
        ) as client:
            r = await client.get(robots_url)
            if r.status_code >= 400:
                return None
            return r.text
    except httpx.RequestError:
        return None


async def _robots_allows(url: str) -> tuple[bool, str]:
    """Evaluate robots.txt with ``urllib.robotparser`` (fetched once per host,
    cached). Returns ``(allowed, reason)``."""
    from urllib.robotparser import RobotFileParser

    parts = urlparse(url)
    host = parts.netloc
    if host not in _ROBOTS_CACHE:
        text = await _fetch_robots_txt(url)
        if text is None:
            _ROBOTS_CACHE[host] = None
        else:
            rp = RobotFileParser()
            rp.parse(text.splitlines())
            _ROBOTS_CACHE[host] = rp
    rp = _ROBOTS_CACHE[host]
    if rp is None:
        return True, ""
    if rp.can_fetch(_ASSET_USER_AGENT, url) or rp.can_fetch("*", url):
        return True, ""
    return False, f"robots.txt disallows fetching {parts.path or '/'} for this agent"


async def assert_scrapable(url: str, *, confirm_ownership: bool) -> None:
    """Fail-closed ownership + robots gate (FR3.5). A URL off the owned-domains
    allowlist requires ``confirm_ownership=true`` or is refused (422); a
    robots-disallowed URL is refused (403). Widening beyond owned properties is a
    review, not a flag flip (R4)."""
    if not (await _is_owned(url) or confirm_ownership):
        raise ScrapeRefused(
            "ownership not confirmed — this URL is not on the owned-properties "
            "allowlist (creative.owned_domains); pass confirm_ownership=true for a "
            "URL you own, or add its domain to the allowlist (a review, not a flag)",
            status_code=422,
        )
    allowed, reason = await _robots_allows(url)
    if not allowed:
        raise ScrapeRefused(reason, status_code=403)


# ── Claim seed gate (FR3.4 · Honesty ledger #5) ───────────────────────────────


def filter_claim_seeds(claims: list[str], account_id: Optional[str],
                       campaign_id: Optional[str]) -> tuple[list[str], list[dict]]:
    """Filter scraped claim seeds against the campaign's pinned facts BEFORE any
    of them can seed a draft (FR3.4) — so a scraped page can never resurrect the
    Panama stay-requirement class of error.

    Reuses ``prompt_drafter._load_pinned_claims`` (the pinned-fact store) +
    ``claim_gate``'s normalization/matching PRIMITIVES — never ``run_claim_gate``,
    which was built for chat-output auditing and would no-op on fragments
    (Honesty ledger #5). A dropped claim is LOGGED with its text.

    Returns ``(kept_claims, dropped)`` where ``dropped`` is
    ``[{claim, banned_phrase}]``. When no campaign context / no banned facts
    exist, every claim passes through unchanged."""
    from app.services import claim_gate
    from app.services.prompt_drafter import _load_pinned_claims

    if not account_id or not campaign_id:
        return list(claims), []

    pinned = _load_pinned_claims(account_id=account_id, campaign_id=campaign_id)
    banned = claim_gate.extract_banned_phrases(pinned)
    if not banned:
        return list(claims), []

    kept: list[str] = []
    dropped: list[dict] = []
    for c in claims:
        hit = claim_gate.claim_matches_banned(c, banned)
        if hit:
            dropped.append({"claim": c, "banned_phrase": hit})
            logger.warning(
                "brand_kit.filter_claim_seeds: DROPPED scraped claim seed as it "
                "asserts a pinned-banned phrase %r — claim text: %r "
                "(account=%s campaign=%s)", hit, c, account_id, campaign_id)
        else:
            kept.append(c)
    return kept, dropped
