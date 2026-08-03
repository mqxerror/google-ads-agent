"""Creative endpoints — the runtime surface of the Creative Spec Registry.

``GET /api/creative/specs`` serves the frozen registry verbatim so the frontend
wizards derive their validation from ONE source instead of baked constants
(FR1.2, NFR-D1). Static data → cheap and cacheable (NFR-P2, <100 ms).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services import creative_specs

router = APIRouter(prefix="/api/creative", tags=["creative"])


@router.get("/specs")
def get_creative_specs() -> Dict[str, Any]:
    """Full registry: every campaign type's limits + engine knobs + version.

    Shape (architecture §6): ``{campaign_types, engine, version}``. The client
    caches the last response and renders validation from it immediately
    (stale-while-revalidate); this endpoint is pure static data."""
    return {
        "campaign_types": creative_specs.serialize_registry(),
        "engine": {
            "near_dup_threshold": creative_specs.ENGINE.near_dup_threshold,
            "batch_tile_cap": creative_specs.ENGINE.batch_tile_cap,
            "batch_retry_max": creative_specs.ENGINE.batch_retry_max,
        },
        "version": creative_specs.VERSION,
    }
