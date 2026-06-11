"""PMax campaign creation — REST wrapper around the MCP orchestrator.

This endpoint exists so the visual wizard (PMaxWizard.tsx) can drive
the same flow the chat agent uses via MCP. Both surfaces call the
identical PMaxOrchestrator instance — no duplicated logic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from google_ads.services.campaign.pmax_orchestrator import (
    ApiCtx,
    PMaxOrchestrator,
    PMaxStepError,
    PMaxValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["pmax"])

# One orchestrator per process — primitive service clients are cached
# inside it. The orchestrator is stateless aside from those service
# refs, so concurrent requests are safe.
_orchestrator = PMaxOrchestrator()


def _ensure_sdk_client() -> None:
    """The google_ads SDK client is normally initialised by the MCP
    subprocess's lifespan (mcp_main.py). The REST wizard path runs in the
    FastAPI process, which never called set_sdk_client — so the first live
    submit failed with 'SDK client not initialized'. Lazily initialise from
    env here (backend/.env is already loaded into os.environ by
    app/mcp_server.py's load_dotenv at import time)."""
    from google_ads.sdk_client import GoogleAdsSdkClient, get_sdk_client, set_sdk_client

    try:
        get_sdk_client()
    except Exception:
        set_sdk_client(GoogleAdsSdkClient())
        logger.info("Initialized Google Ads SDK client for the REST PMax path")


class PMaxMarketingImages(BaseModel):
    landscape: List[str] = Field(default_factory=list)
    square: List[str] = Field(default_factory=list)
    portrait: List[str] = Field(default_factory=list)


class PMaxCreateRequest(BaseModel):
    """Wizard submit payload. All fields validated server-side too —
    the wizard's client-side validation is a UX nicety; the orchestrator
    rejects anything that doesn't meet Google's hard minimums."""

    name: str
    budget_micros: int
    final_urls: List[str]
    business_name: str
    headlines: List[str]
    long_headlines: List[str]
    descriptions: List[str]
    logos: List[str] = Field(default_factory=list)
    marketing_images: PMaxMarketingImages = Field(default_factory=PMaxMarketingImages)
    video_youtube_ids: List[str]
    audience_signals: Optional[List[Dict[str, Any]]] = None
    final_mobile_urls: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PMaxCreateResponse(BaseModel):
    campaign_id: str
    budget_id: str
    asset_group_id: str
    asset_ids: Dict[str, List[str]]
    warnings: List[str] = Field(default_factory=list)


class PMaxDraftRequest(BaseModel):
    brief: str = ""
    final_url: str = ""
    business_name: str = ""
    campaign_name: str = ""


class PMaxDraftResponse(BaseModel):
    headlines: List[str]
    long_headlines: List[str]
    descriptions: List[str]


# Google's hard limits, enforced server-side on whatever the model returns.
_DRAFT_LIMITS = {
    "headlines": (3, 15, 30),
    "long_headlines": (1, 5, 90),
    "descriptions": (2, 5, 90),
}


# Draft jobs run in the background and the wizard POLLS for the result —
# a single 1-3 minute HTTP request kept dying when the Vite dev proxy or
# either server blipped mid-draft (hit live 2026-06-10). In-memory store is
# fine: drafts are ephemeral and single-process.
_draft_jobs: Dict[str, Dict[str, Any]] = {}


async def _run_draft_job(job_id: str, account_id: str, body: PMaxDraftRequest) -> None:
    try:
        result = await _draft_pmax_copy_inner(account_id, body)
        _draft_jobs[job_id] = {"status": "done", "result": result.model_dump()}
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, dict) else {"message": str(e.detail)}
        _draft_jobs[job_id] = {"status": "error", "message": detail.get("message", "draft failed")}
    except Exception as e:
        logger.exception("PMax draft job %s failed", job_id)
        _draft_jobs[job_id] = {"status": "error", "message": str(e)[:300]}


@router.post("/accounts/{account_id}/pmax/draft-copy")
async def start_draft_pmax_copy(account_id: str, body: PMaxDraftRequest) -> Dict[str, str]:
    """Start a Creative Director draft job; poll GET .../draft-copy/{id}."""
    import asyncio
    import uuid as _uuid

    job_id = str(_uuid.uuid4())
    _draft_jobs[job_id] = {"status": "running"}
    asyncio.create_task(_run_draft_job(job_id, account_id, body))
    return {"draft_id": job_id, "status": "running"}


@router.get("/pmax/draft-copy/{draft_id}")
async def get_draft_pmax_copy(draft_id: str) -> Dict[str, Any]:
    job = _draft_jobs.get(draft_id)
    if not job:
        return {"status": "error", "message": "unknown draft id (server restarted?) — start a new draft"}
    return job


async def _draft_pmax_copy_inner(account_id: str, body: PMaxDraftRequest) -> PMaxDraftResponse:
    """Draft PMax text assets with the Creative Director role from the
    campaign brief + landing page. Analysis-only (no Google Ads tools);
    the agent may fetch the landing page to ground the copy. Limits are
    re-enforced here so the wizard never receives over-length lines."""
    import json as _json
    import re as _re

    from app.services.agent import stream_agent_response

    prompt = (
        "Draft Performance Max ad copy for this campaign. First fetch the "
        "landing page to ground every claim — never invent offers or numbers.\n\n"
        f"Landing page: {body.final_url or '(none given — use the brief only)'}\n"
        f"Business name: {body.business_name or '-'}\n"
        f"Campaign name: {body.campaign_name or '-'}\n"
        f"Brief from the operator: {body.brief or '(none — derive from the landing page)'}\n\n"
        "HARD LIMITS (Google rejects violations): headlines ≤30 chars each, "
        "long_headlines ≤90, descriptions ≤90. No em dashes. No third-party "
        "brand names. Vary the angles: benefit, urgency, social proof, "
        "question, specificity.\n\n"
        "Respond with ONLY this JSON, no prose:\n"
        '{"headlines": [8-12 strings ≤30 chars], '
        '"long_headlines": [3-5 strings ≤90 chars], '
        '"descriptions": [4-5 strings ≤90 chars]}'
    )

    parts: list[str] = []
    async for ev in stream_agent_response(
        user_message=prompt,
        account_id=account_id,
        active_role="creative_director",
        tool_allowlist=[],  # no Google Ads tools; built-in web fetch still works
    ):
        if ev.get("type") == "text":
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
    for field, (min_n, max_n, max_chars) in _DRAFT_LIMITS.items():
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
                    "message": f"Draft produced too few valid {field.replace('_', ' ')} "
                               f"({len(out[field])}/{min_n}) — try again.",
                },
            )
    return PMaxDraftResponse(**out)


@router.post(
    "/accounts/{account_id}/campaigns/pmax",
    response_model=PMaxCreateResponse,
)
async def create_pmax(account_id: str, body: PMaxCreateRequest) -> PMaxCreateResponse:
    """Create a Performance Max campaign from the wizard's bundle.

    Returns 422 (Unprocessable Entity) with field-by-field error list
    when Google's hard minimums aren't met. Returns 502 (Bad Gateway)
    when the Google Ads API itself rejects the create — the prior
    campaign + budget have already been rolled back by the orchestrator
    at this point, so a retry is safe.
    """
    bundle: Dict[str, Any] = {
        "name": body.name,
        "budget_micros": body.budget_micros,
        "final_urls": body.final_urls,
        "final_mobile_urls": body.final_mobile_urls,
        "business_name": body.business_name,
        "headlines": body.headlines,
        "long_headlines": body.long_headlines,
        "descriptions": body.descriptions,
        "logos": body.logos,
        "marketing_images": {
            "landscape": body.marketing_images.landscape,
            "square": body.marketing_images.square,
            "portrait": body.marketing_images.portrait,
        },
        "video_youtube_ids": body.video_youtube_ids,
        "audience_signals": body.audience_signals,
        "start_date": body.start_date,
        "end_date": body.end_date,
    }
    try:
        _ensure_sdk_client()
        result = await _orchestrator.create_pmax_campaign(
            ctx=ApiCtx(),
            customer_id=account_id,
            bundle=bundle,
        )
        return PMaxCreateResponse(**result)
    except PMaxValidationError as e:
        # 422 = the standard "your payload is invalid" code; structured
        # errors so the wizard can highlight the offending fields.
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_FAILED", "errors": e.errors},
        )
    except PMaxStepError as e:
        logger.exception(
            "PMax orchestrator failed for account=%s at step '%s'",
            account_id, e.step,
        )
        # 502 — a Google Ads call failed mid-recipe. The orchestrator
        # already rolled back; `message` is the full self-contained
        # story (step + cleanup + underlying error) so the wizard can
        # show it verbatim, with `step`/`rolled_back` available for
        # richer UI treatment later.
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
        logger.exception("PMax orchestrator failed for account=%s", account_id)
        # 502 — the upstream Google Ads call failed. Rollback already
        # happened inside the orchestrator.
        raise HTTPException(
            status_code=502,
            detail={"error": "GOOGLE_ADS_ERROR", "message": str(e)[:500]},
        )
