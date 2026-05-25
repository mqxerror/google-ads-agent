"""Public web page fetcher for Studio's brief extraction.

Ported from meta-ads-agent. Given a URL the operator pastes, fetch
the page + extract structured signals (title, description, og:*, h1,
body excerpt) so the prompt-drafter can ground its output in real
page content instead of guessing.

Constraints (kept tight because operator-typed input → public URL):
  - 5s timeout
  - 10 MB max response size
  - Only http(s) URLs; refuse file:// / data: / javascript: / private IPs
  - Strip script + style tags before extracting text
  - No JS rendering (static HTML only) — fine for marketing pages
"""

from __future__ import annotations

import html
import ipaddress
import re
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx


_MAX_BYTES = 10 * 1024 * 1024
_TIMEOUT_SECONDS = 5.0
_USER_AGENT = "google-ads-agent/0.1 (+studio brief fetcher)"


class PageFetchError(RuntimeError):
    """Raised when a URL fetch fails or is refused."""


@dataclass
class FetchedPage:
    url: str
    final_url: str
    title: str | None
    description: str | None
    og: dict[str, str]
    h1: str | None
    body_excerpt: str
    status: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── URL safety ──────────────────────────────────────────────────────────────


def _is_safe_url(url: str) -> tuple[bool, str | None]:
    """Allow http/https public URLs only. Refuse private/loopback/link-local."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "could not parse URL"
    if parsed.scheme not in ("http", "https"):
        return False, f"scheme must be http or https (got {parsed.scheme!r})"
    host = parsed.hostname
    if not host:
        return False, "URL missing host"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return False, f"refusing private/loopback IP ({host})"
    except ValueError:
        pass
    return True, None


# ── HTML parsing ────────────────────────────────────────────────────────────


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_RE = re.compile(
    r'<meta\s+[^>]*name=["\']?(description|keywords)["\']?\s+[^>]*content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_RE = re.compile(
    r'<meta\s+[^>]*(?:property|name)=["\']?og:([a-z_]+)["\']?\s+[^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_SCRIPT_STYLE_RE = re.compile(
    r"<(?:script|style|noscript)[^>]*>.*?</(?:script|style|noscript)>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    s = _SCRIPT_STYLE_RE.sub(" ", s)
    s = _TAG_RE.sub(" ", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return html.unescape(s).replace("\xa0", " ")


def _strip_cache_bust(u: str) -> str:
    parts = urlparse(u)
    if "_cb=" not in (parts.query or ""):
        return u
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k != "_cb"
    ]
    return urlunparse(parts._replace(query=urlencode(kept)))


def _decode_attr(s: str) -> str:
    return html.unescape(s.strip()).replace("\xa0", " ")


# ── Main fetch ──────────────────────────────────────────────────────────────


async def fetch(url: str) -> FetchedPage:
    """Fetch URL + extract page signals. Raises PageFetchError on failure."""
    ok, why = _is_safe_url(url)
    if not ok:
        raise PageFetchError(why or "unsafe URL")

    # Cache-bust: marketing pages behind Cloudflare can serve stale edge
    # copy; force a fresh origin hit so the extracted brief reflects the
    # CURRENT landing page, not yesterday's revision.
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,*/*;q=0.5",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    }
    bust = f"_cb={int(time.time() * 1000)}"
    fetch_url = f"{url}{'&' if '?' in url else '?'}{bust}"
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=5,
            headers=headers,
        ) as client:
            r = await client.get(fetch_url)
    except httpx.RequestError as e:
        raise PageFetchError(f"network error: {e}") from e

    if r.status_code >= 400:
        raise PageFetchError(f"HTTP {r.status_code}")

    body_bytes = r.content
    if len(body_bytes) > _MAX_BYTES:
        body_bytes = body_bytes[:_MAX_BYTES]

    final_url = _strip_cache_bust(str(r.url))
    ok, why = _is_safe_url(final_url)
    if not ok:
        raise PageFetchError(f"final URL after redirects unsafe: {why}")

    try:
        html_text = body_bytes.decode(r.encoding or "utf-8", errors="replace")
    except (LookupError, TypeError):
        html_text = body_bytes.decode("utf-8", errors="replace")

    # Title
    title_match = _TITLE_RE.search(html_text)
    title = _strip_html(title_match.group(1)).strip() if title_match else None

    # Meta description
    description: str | None = None
    for kind, content in _META_RE.findall(html_text):
        if kind.lower() == "description" and not description:
            description = _decode_attr(content)

    # og:* tags
    og: dict[str, str] = {}
    for key, content in _OG_RE.findall(html_text):
        og[key.lower()] = _decode_attr(content)
    if not title and og.get("title"):
        title = og["title"]
    if not description and og.get("description"):
        description = og["description"]

    # h1
    h1_match = _H1_RE.search(html_text)
    h1 = _strip_html(h1_match.group(1)).strip() if h1_match else None

    body = _strip_html(html_text)
    excerpt = body[:3000]

    return FetchedPage(
        url=url,
        final_url=final_url,
        title=title,
        description=description,
        og=og,
        h1=h1,
        body_excerpt=excerpt,
        status=r.status_code,
    )
