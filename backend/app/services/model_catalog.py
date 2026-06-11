"""Server-side Higgsfield model catalog — single source of truth.

Epic 11 P1: the FE used to hardcode the model list in two shapes
(HiggsfieldGenerator's IMAGE_MODELS/VIDEO_MODELS) and the two copies
drifted. This module owns the catalog: a curated static list with the
per-model param contracts the CLI enforces (Veo duration is a string
ENUM 4/6/8; Kling takes an int <= 15; Wan wants enum strings 5/10/15),
plain-language tier labels, and cost text.

Liveness: we refresh the set of model ids from `higgsfield --json
model list` (cached, 1h TTL) and mark curated entries `available`.
When the CLI is missing/down we serve the static catalog unchanged —
the catalog must never 502 just because higgsfield is unreachable.

DECOUPLING (approved brief addendum 2026-06-11): this is studio
service layer — it must NEVER import google_ads code. Context flows
in from callers; nothing Ads-specific lives here.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Tier labels are operator-facing plain language (brief §8: no model
# jargon up front). Real model names surface in the Tune disclosure.
TIER_BEST = "Best quality"
TIER_FAST = "Fast"
TIER_BUDGET = "Budget"

# Curated catalog. `constraints` encodes the per-model CLI contract so
# the FE (and the storyboard scene validator) can clamp params BEFORE
# the CLI rejects them at render time:
#   duration_type: "enum"  -> `durations` lists the only legal values
#   duration_type: "int"   -> `max_duration` caps an integer seconds
#   duration_type: None    -> model takes no --duration
# Cost text is verified-live May 2026 (see reference_higgsfield_cli).
_CATALOG: list[dict[str, Any]] = [
    # ── Images ──────────────────────────────────────────────────────
    {
        "id": "nano_banana_2", "label": "Nano Banana Pro", "kind": "image",
        "tier": TIER_BEST, "cost_text": "about 2 credits per image",
        "default": True,
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "nano_banana_flash", "label": "Nano Banana 2", "kind": "image",
        "tier": TIER_FAST, "cost_text": "about 1-2 credits per image",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "nano_banana", "label": "Nano Banana", "kind": "image",
        "tier": TIER_BUDGET, "cost_text": "about 1 credit per image",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "gpt_image_2", "label": "GPT Image 2", "kind": "image",
        "tier": TIER_BEST, "cost_text": "a few credits per image; strongest at text in images",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "flux_2", "label": "FLUX.2", "kind": "image",
        "tier": TIER_FAST, "cost_text": "a few credits per image",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "seedream_v5_lite", "label": "Seedream V5 Lite", "kind": "image",
        "tier": TIER_BUDGET, "cost_text": "about 1 credit per image",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "text2image_soul_v2", "label": "Soul V2 (face-consistent)", "kind": "image",
        "tier": TIER_BEST, "cost_text": "a few credits per image; needs a trained Soul",
        "constraints": {
            "aspect_ratios": ["1:1", "4:5", "9:16", "16:9"],
            "duration_type": None, "supports_soul": True,
        },
    },
    {
        "id": "soul_cinematic", "label": "Soul Cinematic", "kind": "image",
        "tier": TIER_BEST, "cost_text": "a few credits per image; needs a trained Soul",
        "constraints": {
            "aspect_ratios": ["1:1", "4:5", "9:16", "16:9"],
            "duration_type": None, "supports_soul": True,
        },
    },
    {
        "id": "marketing_studio_image", "label": "Marketing Studio (text-in-image)", "kind": "image",
        "tier": TIER_BEST, "cost_text": "a few credits per image",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    {
        "id": "image_auto", "label": "Auto (Higgsfield picks)", "kind": "image",
        "tier": TIER_FAST, "cost_text": "varies by the model it picks",
        "constraints": {"aspect_ratios": ["1:1", "4:5", "9:16", "16:9"], "duration_type": None},
    },
    # ── Video ───────────────────────────────────────────────────────
    {
        "id": "veo3_1", "label": "Veo 3.1 (Google)", "kind": "video",
        "tier": TIER_BEST, "cost_text": "premium; tens of credits per clip",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16"],
            "duration_type": "enum", "durations": [4, 6, 8], "max_duration": 8,
            "qualities": ["basic", "high", "ultra"],
            "submodels": ["veo-3-1-fast", "veo-3-1-preview"],
        },
    },
    {
        "id": "veo3_1_lite", "label": "Veo 3.1 Lite", "kind": "video",
        "tier": TIER_BUDGET, "cost_text": "about 8 credits per 5s clip",
        "default": True,
        "constraints": {
            "aspect_ratios": ["16:9", "9:16"],
            "duration_type": "enum", "durations": [4, 6, 8], "max_duration": 8,
        },
    },
    {
        "id": "veo3", "label": "Veo 3 (older)", "kind": "video",
        "tier": TIER_FAST, "cost_text": "image-to-video only (needs an input image)",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16"],
            "duration_type": None, "requires_input_image": True,
        },
    },
    {
        "id": "kling3_0", "label": "Kling 3.0", "kind": "video",
        "tier": TIER_BEST, "cost_text": "about 10 credits per 5s in std mode; 4k costs multiples more",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "duration_type": "int", "max_duration": 15,
            "modes": ["std", "pro", "4k"], "sound": ["on", "off"],
        },
    },
    {
        "id": "kling2_6", "label": "Kling 2.6", "kind": "video",
        "tier": TIER_BUDGET, "cost_text": "cheaper Kling; std mode keeps cost down",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "duration_type": "int", "max_duration": 10,
            "modes": ["std", "pro"],
        },
    },
    {
        "id": "seedance_2_0", "label": "Seedance 2.0", "kind": "video",
        "tier": TIER_BEST, "cost_text": "tens of credits per clip",
        "constraints": {"aspect_ratios": ["16:9", "9:16", "1:1"], "duration_type": "int", "max_duration": 10},
    },
    {
        "id": "seedance1_5", "label": "Seedance 1.5 Pro", "kind": "video",
        "tier": TIER_FAST, "cost_text": "mid-priced per clip",
        "constraints": {"aspect_ratios": ["16:9", "9:16", "1:1"], "duration_type": "int", "max_duration": 10},
    },
    {
        "id": "minimax_hailuo", "label": "Minimax Hailuo", "kind": "video",
        "tier": TIER_FAST, "cost_text": "mid-priced per clip",
        "constraints": {"aspect_ratios": ["16:9", "9:16"], "duration_type": "int", "max_duration": 10},
    },
    {
        "id": "wan2_6", "label": "Wan 2.6", "kind": "video",
        "tier": TIER_BUDGET, "cost_text": "about 13 credits per clip",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "duration_type": "enum", "durations": [5, 10, 15], "max_duration": 15,
        },
    },
    {
        "id": "wan2_7", "label": "Wan 2.7", "kind": "video",
        "tier": TIER_FAST, "cost_text": "mid-priced per clip",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "duration_type": "enum", "durations": [5, 10, 15], "max_duration": 15,
        },
    },
    {
        "id": "soul_cast", "label": "Soul Cast (face-consistent)", "kind": "video",
        "tier": TIER_BEST, "cost_text": "premium; needs a trained Soul",
        "constraints": {
            "aspect_ratios": ["16:9", "9:16"], "duration_type": "int",
            "max_duration": 10, "supports_soul": True,
        },
    },
    {
        "id": "grok_video", "label": "Grok Video", "kind": "video",
        "tier": TIER_FAST, "cost_text": "mid-priced per clip",
        "constraints": {"aspect_ratios": ["16:9", "9:16"], "duration_type": "int", "max_duration": 10},
    },
]

# 1h TTL on the live-id refresh. The catalog itself is static in code;
# only the `available` marking is refreshed.
_LIVE_TTL_S = 3600.0
_live_cache: dict[str, Any] = {"ts": 0.0, "ids": None}   # ids: set[str] | None


def get_model(model_id: str) -> Optional[dict[str, Any]]:
    """Lookup one curated entry by id. Returns None for unknown ids
    (callers decide whether to reject or pass through to the CLI)."""
    for m in _CATALOG:
        if m["id"] == model_id:
            return m
    return None


def clamp_duration(model_id: str, requested: Optional[int]) -> Optional[int]:
    """Snap a requested duration to the model's legal values.

    Veo-style enum models snap to the nearest allowed value; int-capped
    models clamp to [1, max]; models with no duration param return None
    so callers omit --duration entirely.
    """
    m = get_model(model_id)
    if m is None:
        return requested
    c = m.get("constraints") or {}
    dtype = c.get("duration_type")
    if dtype is None:
        return None
    if requested is None:
        durations = c.get("durations")
        return int(durations[0]) if durations else 5
    if dtype == "enum":
        durations = c.get("durations") or [requested]
        return min(durations, key=lambda d: abs(int(d) - int(requested)))
    max_d = int(c.get("max_duration") or 60)
    return max(1, min(int(requested), max_d))


async def _live_model_ids() -> Optional[set[str]]:
    """Cached set of model ids the CLI reports as available. None when
    the CLI is missing or errors (catalog then serves static)."""
    now = time.monotonic()
    if _live_cache["ids"] is not None and (now - _live_cache["ts"]) < _LIVE_TTL_S:
        return _live_cache["ids"]
    try:
        from app.services.higgsfield_client import HiggsfieldClient

        client = HiggsfieldClient(timeout_s=30.0)
        items: list[dict[str, Any]] = []
        for kind in ("image", "video"):
            items.extend(await client.model_list(kind=kind))
        ids = {
            str(it.get("job_set_type") or "").strip()
            for it in items if isinstance(it, dict)
        }
        ids.discard("")
        if ids:
            _live_cache["ids"] = ids
            _live_cache["ts"] = now
            return ids
    except Exception as e:  # CLI missing / not logged in / upstream down
        logger.info("model catalog live refresh unavailable: %s", e)
    return _live_cache["ids"]  # possibly stale, possibly None — both fine


async def get_models(kind: Optional[str] = None) -> dict[str, Any]:
    """The catalog, optionally filtered by kind ('image' | 'video').

    Returns {"models": [...], "source": "live" | "static"}. Each model
    carries an `available` flag: True when the CLI confirmed the id,
    True-by-default when the CLI was unreachable (static mode).
    """
    live_ids = await _live_model_ids()
    out: list[dict[str, Any]] = []
    for m in _CATALOG:
        if kind in ("image", "video") and m["kind"] != kind:
            continue
        entry = dict(m)
        entry["available"] = True if live_ids is None else (m["id"] in live_ids)
        out.append(entry)
    return {
        "models": out,
        "source": "live" if live_ids is not None else "static",
    }
