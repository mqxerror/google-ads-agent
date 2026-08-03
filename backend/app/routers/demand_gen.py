"""Demand Gen ad-image update — REST wrapper around the MCP orchestrator.

Lets the Studio "Push to campaign ad" action drive the SAME in-place image
refresh the chat agent / MCP tool (`demand_gen_update_ad_images`) uses — one
shared `DemandGenOrchestrator`, no duplicated logic. The reject-the-AI-creative
→ push-my-own-property-photos flow: replace or append the marketing / square /
portrait / tall / logo images on a live DemandGenMultiAssetAd, in place.

Mirrors app/routers/pmax.py (SDK-client lazy init, 422 for validation, 502 for
a Google API rejection).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import creative_specs
from google_ads.services.campaign.demand_gen_orchestrator import (
    ApiCtx,
    DemandGenAdUpdateError,
    DemandGenOrchestrator,
    DemandGenStepError,
    DemandGenValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["demand_gen"])

# One orchestrator per process (service clients cached inside it); stateless
# aside from those refs, so concurrent requests are safe.
_orchestrator = DemandGenOrchestrator()


def _ensure_sdk_client() -> None:
    """The google_ads SDK client is normally initialised by the MCP subprocess
    lifespan; the REST path runs in the FastAPI process, so lazily initialise
    from env (backend/.env is already loaded by app/mcp_server.py at import)."""
    from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client

    try:
        get_sdk_client()
    except Exception:
        set_sdk_client(GoogleAdsSdkClient())
        logger.info("Initialized Google Ads SDK client for the REST Demand Gen path")


class DemandGenMarketingImages(BaseModel):
    """Marketing-image slots for the Demand Gen multi-asset ad. All refs may be
    Google asset resource names, bare numeric asset ids, OR local library UUIDs
    (uploaded / generated) — the orchestrator uploads + crops local files to
    each slot's exact aspect at submit."""

    landscape: List[str] = Field(default_factory=list)      # 1.91:1
    square: List[str] = Field(default_factory=list)         # 1:1
    portrait: List[str] = Field(default_factory=list)       # 4:5
    tall_portrait: List[str] = Field(default_factory=list)  # 9:16


class DemandGenChannels(BaseModel):
    """The six explicitly-selectable Demand Gen channels. Defaults match the
    orchestrator's DEFAULT_CHANNELS — Gmail OFF, everything else ON — so an
    omitted block still produces the intended out-of-the-box shape."""

    youtube_in_stream: bool = True
    youtube_in_feed: bool = True
    youtube_shorts: bool = True
    discover: bool = True
    gmail: bool = False   # OFF by default — the whole point of this surface
    display: bool = True


class DemandGenCreateRequest(BaseModel):
    """Wizard submit payload. Every field is validated server-side too — the
    wizard's client-side validation is a UX nicety; the orchestrator rejects
    anything that doesn't meet Google's hard minimums (headlines ≤5/≤40c,
    descriptions ≤5/≤90c, business_name ≤25c, at least one channel ON)."""

    name: str
    budget_micros: int
    final_urls: List[str]
    business_name: str
    headlines: List[str]
    descriptions: List[str]
    logos: List[str] = Field(default_factory=list)
    marketing_images: DemandGenMarketingImages = Field(default_factory=DemandGenMarketingImages)
    channels: DemandGenChannels = Field(default_factory=DemandGenChannels)
    call_to_action_text: Optional[str] = None
    target_cpa_micros: Optional[int] = None
    location_ids: Optional[List[str]] = None
    excluded_location_ids: Optional[List[str]] = None
    language_ids: Optional[List[str]] = None
    audience_user_list_ids: Optional[List[str]] = None
    excluded_user_list_ids: Optional[List[str]] = None
    final_mobile_urls: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class DemandGenCreateResponse(BaseModel):
    campaign_id: str
    budget_id: str
    ad_group_id: str
    ad_group_ad_id: str
    channels: Dict[str, bool]
    image_asset_ids: Dict[str, List[str]]
    warnings: List[str] = Field(default_factory=list)


@router.post(
    "/accounts/{account_id}/campaigns/demand-gen",
    response_model=DemandGenCreateResponse,
)
async def create_demand_gen(
    account_id: str, body: DemandGenCreateRequest
) -> DemandGenCreateResponse:
    """Create a Demand Gen campaign (PAUSED) from the wizard's bundle.

    Mirrors app/routers/pmax.py::create_pmax — the visual wizard and the chat
    agent both drive the SAME `DemandGenOrchestrator`, no duplicated logic.

    Returns 422 with a field-by-field error list when Google's hard minimums
    aren't met; 502 when a Google Ads call fails mid-recipe (the orchestrator
    has already rolled back the prior creations, so a retry is safe).
    """
    bundle: Dict[str, Any] = {
        "name": body.name,
        "budget_micros": body.budget_micros,
        "final_urls": body.final_urls,
        "final_mobile_urls": body.final_mobile_urls,
        "business_name": body.business_name,
        "headlines": body.headlines,
        "descriptions": body.descriptions,
        "call_to_action_text": body.call_to_action_text,
        "logos": body.logos,
        "marketing_images": {
            "landscape": body.marketing_images.landscape,
            "square": body.marketing_images.square,
            "portrait": body.marketing_images.portrait,
            "tall_portrait": body.marketing_images.tall_portrait,
        },
        "channels": body.channels.model_dump(),
        "target_cpa_micros": body.target_cpa_micros,
        "location_ids": body.location_ids,
        "excluded_location_ids": body.excluded_location_ids,
        "language_ids": body.language_ids,
        "audience_user_list_ids": body.audience_user_list_ids,
        "excluded_user_list_ids": body.excluded_user_list_ids,
        "start_date": body.start_date,
        "end_date": body.end_date,
    }
    try:
        _ensure_sdk_client()
        result = await _orchestrator.create_demand_gen_campaign(
            ctx=ApiCtx(),
            customer_id=account_id,
            bundle=bundle,
        )
        return DemandGenCreateResponse(**result)
    except DemandGenValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_FAILED", "errors": e.errors},
        )
    except DemandGenStepError as e:
        logger.exception(
            "Demand Gen orchestrator failed for account=%s at step '%s'",
            account_id, e.step,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "GOOGLE_ADS_ERROR",
                "step": e.step,
                "rolled_back": e.rollback_report,
                "message": str(e)[:800],
            },
        )
    except Exception as e:
        logger.exception("Demand Gen orchestrator failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )


# ── Assisted copy drafting (mirrors app/routers/pmax.py::draft-copy) ──────
#
# The DG wizard's assisted flow drafts business_name + headlines + descriptions
# from the campaign brief + landing page through the SAME pipeline PMax uses
# (`stream_agent_response` with the creative_director role, no Google Ads
# tools). It differs from PMax only in the OUTPUT shape: Demand Gen has NO long
# headlines and DOES carry a business_name, and its hard limits are DG's
# (headlines ≤5/≤40c, descriptions ≤5/≤90c, business_name ≤25c) — so a draft
# can never exceed what `_validate_bundle` will later accept.
#
# Same job+poll shape as PMax: a single 1-3 min HTTP request kept dying when the
# Vite dev proxy or either server blipped mid-draft, so the wizard POLLS. The
# in-memory store is fine — drafts are ephemeral and single-process.


class DGDraftRequest(BaseModel):
    brief: str = ""
    final_url: str = ""
    business_name: str = ""
    campaign_name: str = ""


class DGDraftResponse(BaseModel):
    business_name: str
    headlines: List[str]
    descriptions: List[str]


# Draft clamps + prompt limits are derived from the Creative Spec Registry
# (creative_specs.get("demand_gen")) — no local limit table (Epic 14, fence F1),
# so the prompt can never promise a number the validator would reject. Draft jobs
# are `creative_jobs` DB rows (story 15.3, fence F6) — no in-memory store — so a
# restart yields a recoverable `interrupted` status, never a lost job.


def _dg_draft_prompt(body: "DGDraftRequest", spec) -> str:
    """Build the Creative Director draft prompt from the registry spec (FR1.5).

    Pure + module-level so it can be snapshot-tested. The HARD-LIMITS block and
    the deliberate-40-char instruction both derive from ``spec`` — flipping a
    registry value changes the prompt with zero code change here."""
    return (
        "Draft Google Demand Gen ad copy for this campaign. First fetch the "
        "landing page to ground every claim — never invent offers or numbers.\n\n"
        f"Landing page: {body.final_url or '(none given — use the brief only)'}\n"
        f"Business name (brand): {body.business_name or '-'}\n"
        f"Campaign name: {body.campaign_name or '-'}\n"
        f"Brief from the operator: {body.brief or '(none — derive from the landing page)'}\n\n"
        f"{creative_specs.hard_limits_prompt(spec)}\n"
        f"{creative_specs.deliberate_length_note(spec, 'headlines')}\n"
        "DEMAND GEN POLICY: NO prices or discounts in the copy · NO citizenship "
        "or guaranteed-approval promises · avoid the symbols ~ | + (flagged as "
        "gimmicky). No em dashes. No third-party brand names. Vary the angles: "
        "benefit, aspiration, social proof, specificity.\n"
        "business_name is the advertiser's SHORT brand label shown on the ad — "
        f"keep it the real brand (≤{spec.business_name_max} chars), not a slogan.\n\n"
        "Respond with ONLY this JSON, no prose:\n"
        '{"business_name": "<brand, short>", '
        '"headlines": [several distinct strings], '
        '"descriptions": [several distinct strings]}'
    )


async def _run_dg_draft_job(job_id: str, account_id: str, body: DGDraftRequest) -> None:
    from app.services import creative_copy
    try:
        result = await _draft_dg_copy_inner(account_id, body)
        await creative_copy.complete_job(job_id, result.model_dump())
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
        await creative_copy.fail_job(job_id, detail.get("message", "draft failed"))
    except Exception as e:
        logger.exception("Demand Gen draft job %s failed", job_id)
        await creative_copy.fail_job(job_id, str(e)[:300])


@router.post("/accounts/{account_id}/demand-gen/draft-copy")
async def start_draft_demand_gen_copy(account_id: str, body: DGDraftRequest) -> Dict[str, str]:
    """Start a Creative Director draft job; poll GET .../demand-gen/draft-copy/{id}."""
    import asyncio

    from app.services import creative_copy

    job_id = await creative_copy.create_job("draft", account_id, "demand_gen", body.model_dump())
    asyncio.create_task(_run_dg_draft_job(job_id, account_id, body))
    return {"draft_id": job_id, "status": "running"}


@router.get("/demand-gen/draft-copy/{draft_id}")
async def get_draft_demand_gen_copy(draft_id: str) -> Dict[str, Any]:
    from app.services import creative_copy

    job = await creative_copy.get_job(draft_id)
    if not job:
        return {"status": "error", "message": "unknown draft id — start a new draft"}
    return job


async def _draft_dg_copy_inner(account_id: str, body: DGDraftRequest) -> DGDraftResponse:
    """Draft Demand Gen text assets with the Creative Director role from the
    campaign brief + landing page. Analysis-only (no Google Ads tools); the
    agent may fetch the landing page to ground the copy. DG's hard limits are
    re-enforced here so the wizard never receives an over-length or over-count
    bundle — over-length lines are DROPPED (never truncated into garbage) and a
    draft that yields too few valid lines fails so the operator regenerates."""
    import json as _json
    import re as _re

    from app.services.agent import stream_agent_response

    spec = creative_specs.get("demand_gen")
    prompt = _dg_draft_prompt(body, spec)

    parts: list[str] = []
    async for ev in stream_agent_response(
        user_message=prompt,
        account_id=account_id,
        active_role="creative_director",
        tool_allowlist=[],  # no Google Ads tools; built-in web fetch still works
    ):
        if ev.get("type") in ("text", "text_delta"):
            parts.append(ev.get("content", ""))
    raw = "".join(parts)

    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if not m:
        raise HTTPException(
            status_code=502,
            detail={"error": "DRAFT_FAILED", "message": "Creative Director returned no JSON — try again."},
        )
    try:
        parsed = _json.loads(m.group(0))
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={"error": "DRAFT_FAILED", "message": "Could not parse the draft — try again."},
        )

    out: Dict[str, List[str]] = {}
    clamps = creative_specs.draft_clamps(spec)
    for field in ("headlines", "descriptions"):
        min_n, max_n, max_chars = clamps[field]
        items = [
            s.strip() for s in (parsed.get(field) or [])
            if isinstance(s, str) and s.strip() and len(s.strip()) <= max_chars
        ]
        out[field] = items[:max_n]
        if len(out[field]) < min_n:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "DRAFT_FAILED",
                    "message": f"Draft produced too few valid {field} "
                               f"({len(out[field])}/{min_n}) — try again.",
                },
            )

    # business_name: the brand is a proper noun (unlikely to exceed the cap), so
    # clip defensively rather than fail; fall back to the operator's own entry
    # from the brief step if the model omitted it or returned an empty value.
    bn = str(parsed.get("business_name") or "").strip()
    if not bn:
        bn = (body.business_name or "").strip()
    bn = bn[:spec.business_name_max]

    return DGDraftResponse(business_name=bn, **out)


class DemandGenAdOption(BaseModel):
    """One Demand Gen ad the Studio push-to-ad flow can target. Populates the
    operator's ad picker so the push target is a SELECTION, never a hardcoded
    live ad id."""

    ad_id: str
    ad_name: str
    ad_group_id: str
    ad_group_name: str
    campaign_id: str
    campaign_name: str
    status: str


@router.get(
    "/accounts/{account_id}/demand-gen/ads",
    response_model=list[DemandGenAdOption],
)
async def list_demand_gen_ads(account_id: str) -> list[DemandGenAdOption]:
    """List the account's Demand Gen ads so the Studio push-to-ad flow targets
    an operator-selected ad instead of a hardcoded live id. READ-ONLY; 502 on a
    Google API failure. Returns [] when the account has no Demand Gen ads yet."""
    from app.services.google_ads import GoogleAdsService

    try:
        ads = await GoogleAdsService().get_demand_gen_ads(account_id)
    except Exception as e:
        logger.exception("Demand Gen ad listing failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
    return [DemandGenAdOption(**a) for a in ads]


class DemandGenUpdateImagesRequest(BaseModel):
    """Studio push-to-ad payload. All refs may be Google asset resource names,
    bare numeric asset ids, OR local library UUIDs (uploaded / generated) — the
    orchestrator uploads + crops local files to each slot's exact aspect."""

    # Target ad — either the resource name, or both ad_group_id + ad_id.
    ad_resource_name: Optional[str] = None
    ad_group_id: Optional[str] = None
    ad_id: Optional[str] = None
    mode: str = "replace"  # 'replace' | 'append'
    logos: List[str] = Field(default_factory=list)
    landscape_images: List[str] = Field(default_factory=list)
    square_images: List[str] = Field(default_factory=list)
    portrait_images: List[str] = Field(default_factory=list)
    tall_portrait_images: List[str] = Field(default_factory=list)


class DemandGenUpdateImagesResponse(BaseModel):
    ad_id: str
    ad_resource_name: str
    mode: str
    updated_slots: Dict[str, List[str]]
    field_mask: List[str]


@router.post(
    "/accounts/{account_id}/demand-gen/update-ad-images",
    response_model=DemandGenUpdateImagesResponse,
)
async def update_demand_gen_ad_images(
    account_id: str, body: DemandGenUpdateImagesRequest
) -> DemandGenUpdateImagesResponse:
    """Replace or append the image creatives on an existing Demand Gen ad.

    422 with a field-by-field error list when the payload is invalid; 502 when
    Google rejects the mutate (nothing changed live — safe to retry).
    """
    bundle: Dict[str, Any] = {
        "ad_resource_name": body.ad_resource_name,
        "ad_group_id": body.ad_group_id,
        "ad_id": body.ad_id,
        "mode": body.mode,
        "logos": body.logos,
        "marketing_images": {
            "landscape": body.landscape_images,
            "square": body.square_images,
            "portrait": body.portrait_images,
            "tall_portrait": body.tall_portrait_images,
        },
    }
    try:
        _ensure_sdk_client()
        result = await _orchestrator.update_ad_images(
            ctx=ApiCtx(), customer_id=account_id, bundle=bundle
        )
        return DemandGenUpdateImagesResponse(**result)
    except DemandGenValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_FAILED", "errors": e.errors},
        )
    except DemandGenAdUpdateError as e:
        logger.exception("Demand Gen image update failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e.message)[:800]},
        )
    except Exception as e:
        logger.exception("Demand Gen image update failed for account=%s", account_id)
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
