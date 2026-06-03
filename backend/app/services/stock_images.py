"""Stock image sourcing — Unsplash, Pexels, and Replicate FLUX.

When the Director writes a storyboard but the user hasn't supplied library
images for every scene, we can fetch a stock photo (free) or generate one with
AI (paid, opt-in). All fetched images are saved as `ad_assets` so the rest of
the render pipeline treats them identically to user uploads.

Free tier limits worth remembering:
- Unsplash: 50 requests/hr (production tier requires app review)
- Pexels:   200 requests/hr · 20,000/month (very generous)
- Replicate: pay-per-use, no rate limit on flux models
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StockMatch:
    """A single image candidate from a stock provider."""
    provider: str             # "unsplash" | "pexels" | "ai-flux"
    image_url: str            # full-size downloadable URL
    thumb_url: str            # small preview for the picker UI
    width: int
    height: int
    photographer: str = ""    # for attribution (Unsplash requires it)
    photographer_url: str = ""
    source_url: str = ""      # link back to original page
    description: str = ""


# ── Unsplash ──────────────────────────────────────────────────────────


async def search_unsplash(query: str, count: int = 4) -> list[StockMatch]:
    """Search Unsplash for landscape-oriented images matching the query.

    Returns up to `count` matches sorted by relevance. Empty list on any error
    or if no API key is configured (caller should try Pexels next).
    """
    if not settings.UNSPLASH_ACCESS_KEY:
        return []
    if not query.strip():
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": query,
                    "per_page": min(max(1, count), 10),
                    "orientation": "landscape",  # 16:9-ish, matches our 1920×1080 canvas
                    "content_filter": "high",
                },
                headers={
                    "Accept-Version": "v1",
                    "Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}",
                },
            )
            if r.status_code != 200:
                logger.warning("unsplash search failed: %s %s", r.status_code, r.text[:200])
                return []
            data = r.json()
            out: list[StockMatch] = []
            for hit in (data.get("results") or [])[:count]:
                urls = hit.get("urls") or {}
                user = hit.get("user") or {}
                out.append(StockMatch(
                    provider="unsplash",
                    image_url=urls.get("regular") or urls.get("full") or "",
                    thumb_url=urls.get("small") or urls.get("thumb") or "",
                    width=hit.get("width") or 1920,
                    height=hit.get("height") or 1080,
                    photographer=user.get("name") or "",
                    photographer_url=user.get("links", {}).get("html") or "",
                    source_url=hit.get("links", {}).get("html") or "",
                    description=(hit.get("alt_description") or hit.get("description") or "").strip(),
                ))
            return out
    except Exception:
        logger.exception("unsplash search exception")
        return []


# ── Pexels ────────────────────────────────────────────────────────────


async def search_pexels(query: str, count: int = 4) -> list[StockMatch]:
    """Search Pexels for landscape-oriented images. Same shape as Unsplash."""
    if not settings.PEXELS_API_KEY:
        return []
    if not query.strip():
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": min(max(1, count), 15),
                    "orientation": "landscape",
                    "size": "large",
                },
                headers={"Authorization": settings.PEXELS_API_KEY},
            )
            if r.status_code != 200:
                logger.warning("pexels search failed: %s %s", r.status_code, r.text[:200])
                return []
            data = r.json()
            out: list[StockMatch] = []
            for hit in (data.get("photos") or [])[:count]:
                src = hit.get("src") or {}
                out.append(StockMatch(
                    provider="pexels",
                    image_url=src.get("large2x") or src.get("large") or src.get("original") or "",
                    thumb_url=src.get("medium") or src.get("small") or "",
                    width=hit.get("width") or 1920,
                    height=hit.get("height") or 1080,
                    photographer=hit.get("photographer") or "",
                    photographer_url=hit.get("photographer_url") or "",
                    source_url=hit.get("url") or "",
                    description=(hit.get("alt") or "").strip(),
                ))
            return out
    except Exception:
        logger.exception("pexels search exception")
        return []


# ── Combined search (try Unsplash → Pexels) ───────────────────────────


async def search_stock(query: str, count: int = 4) -> list[StockMatch]:
    """Search both providers in parallel and merge results — Unsplash first
    (typically higher artistic quality), Pexels second (broader catalogue).
    Deduplicates by image_url.
    """
    if not query.strip():
        return []
    u_task = search_unsplash(query, count=count)
    p_task = search_pexels(query, count=count)
    u_results, p_results = await asyncio.gather(u_task, p_task, return_exceptions=False)

    seen: set[str] = set()
    merged: list[StockMatch] = []
    for batch in (u_results, p_results):
        for m in batch:
            if not m.image_url or m.image_url in seen:
                continue
            seen.add(m.image_url)
            merged.append(m)
    return merged[:count]


# ── Replicate FLUX (AI image generation) ───────────────────────────────


async def generate_with_flux(
    prompt: str,
    *,
    aspect_ratio: str = "16:9",
    model: str = "black-forest-labs/flux-schnell",  # cheapest, fastest variant
) -> Optional[bytes]:
    """Generate an image with Replicate FLUX. Returns the raw image bytes
    (PNG/JPG depending on model) or None if disabled / failed.

    flux-schnell:  ~$0.003/image, ~3-5s — good default for variety
    flux-1.1-pro:  ~$0.04/image,  ~6-10s — higher artistic quality

    The returned bytes can be written to disk and registered as an `ad_assets`
    row exactly like a user upload.
    """
    if not settings.REPLICATE_API_TOKEN:
        return None
    if not prompt.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Replicate's "predictions" endpoint with `Prefer: wait` returns the
            # finished result inline — no polling needed for fast models.
            r = await client.post(
                f"https://api.replicate.com/v1/models/{model}/predictions",
                headers={
                    "Authorization": f"Bearer {settings.REPLICATE_API_TOKEN}",
                    "Content-Type": "application/json",
                    "Prefer": "wait=60",
                },
                json={
                    "input": {
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "output_format": "jpg",
                        "output_quality": 90,
                        "num_outputs": 1,
                    },
                },
            )
            if r.status_code not in (200, 201):
                logger.warning("replicate FLUX failed: %s %s", r.status_code, r.text[:300])
                return None
            data = r.json()
            output = data.get("output")
            # `output` is a list of URLs (or a single URL string)
            url = (output[0] if isinstance(output, list) and output else output)
            if not isinstance(url, str):
                logger.warning("replicate FLUX returned no usable url: %s", str(data)[:300])
                return None
            img_r = await client.get(url)
            if img_r.status_code != 200:
                logger.warning("flux image fetch failed: %s", img_r.status_code)
                return None
            return img_r.content
    except Exception:
        logger.exception("flux generate exception")
        return None


# ── Download + save to ad_assets ──────────────────────────────────────


async def download_image(url: str) -> Optional[bytes]:
    """Fetch a remote image as bytes. Used when the user picks a stock match
    and we need to copy the file into our library so the renderer can read it
    locally.
    """
    if not url.startswith(("http://", "https://")):
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code != 200:
                logger.warning("download_image failed %s: %s", url, r.status_code)
                return None
            return r.content
    except Exception:
        logger.exception("download_image exception")
        return None


async def save_remote_to_assets(
    *,
    image_bytes: bytes,
    ext: str,
    account_id: Optional[str],
    campaign_id: Optional[str],
    description: str,
    source: str,           # "stock-unsplash" | "stock-pexels" | "ai-flux"
    width: Optional[int] = None,
    height: Optional[int] = None,
    attribution: str = "",
) -> dict:
    """Persist an image (downloaded or generated) into the ad_assets library.
    Returns a row-shaped dict for the frontend.
    """
    from app.routers.assets import ASSETS_DIR
    from app.database import get_db

    asset_id = str(uuid.uuid4())
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    if safe_ext not in (".jpg", ".jpeg", ".png", ".webp"):
        safe_ext = ".jpg"
    stored = f"{asset_id}{safe_ext}"
    dest = ASSETS_DIR / stored
    dest.write_bytes(image_bytes)

    if width is None or height is None:
        try:
            from PIL import Image as _PIL
            with _PIL.open(dest) as im:
                width, height = im.size
        except Exception:
            pass

    public_url = f"/api/assets/file/{stored}"
    # Preserve attribution in the script field so it surfaces in the asset card
    script = description.strip()
    if attribution:
        script = (script + f" · {attribution}").strip(" ·")

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO ad_assets (id, account_id, campaign_id, type, filename, url,
                                       width, height, size_bytes, script, source)
               VALUES (?, ?, ?, 'image', ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, account_id, campaign_id, stored, public_url,
             width, height, len(image_bytes), script, source),
        )
        await db.commit()
    finally:
        await db.close()

    return {
        "id": asset_id,
        "filename": stored,             # stored UUID name — what the renderer expects
        "url": public_url,
        "width": width,
        "height": height,
        "source": source,
        "script": script,
    }


def _ext_from_url(url: str) -> str:
    """Extract a sensible file extension from a remote URL."""
    lower = url.lower().split("?", 1)[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if lower.endswith(ext):
            return ext
    # Default: stock APIs serve JPEGs
    return ".jpg"
