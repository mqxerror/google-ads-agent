"""Campaign Builder — multi-role pipeline for creating campaigns from scratch.

The pipeline sends sequential chat messages to different specialist roles,
each building on the previous role's findings (stored in role_notes).

7 stages: CRO → Competitor → Keywords → Creative → PPC → GTM → Director
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["campaign-builder"])


class BuildSessionInput(BaseModel):
    account_id: str
    landing_page_url: str
    brief: str = ""
    budget_daily: float = 50.0
    geo_targets: list[str] = Field(default_factory=lambda: ["United States"])
    languages: list[str] = Field(default_factory=lambda: ["English"])
    attachments: list[dict] = Field(default_factory=list)


class BuildSession(BaseModel):
    id: str
    account_id: str
    created_at: str
    input: BuildSessionInput
    current_stage: int = 0
    stages: list[dict] = Field(default_factory=list)
    status: str = "pending"  # pending, running, paused, completed, failed


# In-memory store (simple for v1 — no persistence needed since pipelines are short-lived)
_sessions: dict[str, BuildSession] = {}

PIPELINE_STAGES = [
    {
        "stage": 1,
        "role_id": "cro_specialist",
        "role_name": "CRO Specialist",
        "avatar": "gauge",
        "title": "Landing Page Analysis",
        "prompt_template": """As the CRO Specialist, analyze this landing page for a new campaign build:

URL: {landing_page_url}
Brief: {brief}

Run a QUICK analysis (not full 12-point audit) focusing on:
1. What is the VALUE PROPOSITION on this page?
2. What CONVERSION ACTION exists? (form, phone, booking?)
3. What is the TARGET AUDIENCE based on the page content?
4. What KEYWORDS does the page naturally target?
5. Rate the page's conversion readiness (1-10)

{attachments_text}

Keep it concise. Save your findings to campaign memory. The next specialist (Competitor Intel) will read your notes.""",
    },
    {
        "stage": 2,
        "role_id": "competitor_intel",
        "role_name": "Competitor Intel",
        "avatar": "eye",
        "title": "Competitor Research",
        "prompt_template": """As Competitor Intel, research competitors for this new campaign:

Landing page: {landing_page_url}
Brief: {brief}
Target: {geo_targets}

READ the CRO Specialist's findings first (in your role notes context).

Then:
1. Identify 3 main competitors in this niche
2. What keywords are they likely bidding on?
3. What messaging angles are they using?
4. What gaps can we exploit?

{attachments_text}

Keep it concise. The Search Term Hunter will read your findings next.""",
    },
    {
        "stage": 3,
        "role_id": "search_term_hunter",
        "role_name": "Search Term Hunter",
        "avatar": "search",
        "title": "Keyword Strategy",
        "prompt_template": """As the Search Term Hunter, build the keyword strategy for this new campaign:

Landing page: {landing_page_url}
Brief: {brief}
Budget: ${budget_daily}/day
Target: {geo_targets}, {languages}

READ the CRO Specialist and Competitor Intel findings from role notes.

Build:
1. 30-50 high-intent keywords grouped by theme (3-5 ad groups)
2. Recommended match types for each group
3. Negative keyword seed list (20+ terms)
4. Estimated search volume tier (high/medium/low) for each group

Use MCP keyword research tools if available (keyword_plan_idea__generate_keyword_ideas_from_url).

Keep it structured. The Creative Director reads your plan next.""",
    },
    {
        "stage": 4,
        "role_id": "creative_director",
        "role_name": "Creative Director",
        "avatar": "palette",
        "title": "Ad Copy Creation",
        "prompt_template": """As the Creative Director, write the ad copy for this new campaign:

Landing page: {landing_page_url}
Brief: {brief}

READ the previous roles' findings (CRO, Competitor, Search Term Hunter).

For EACH ad group from the keyword plan, write:
- 15 distinct headlines (30 char max each) for Excellent ad strength
- 4 descriptions (90 char max each)
- Ensure keywords from each group appear in at least 3 headlines
- Mix: benefit-driven, feature-driven, urgency, trust, CTA
- Match the landing page value proposition
- Exploit competitor messaging gaps

Present in a clear table format. The PPC Strategist designs the structure next.""",
    },
    {
        "stage": 5,
        "role_id": "ppc_strategist",
        "role_name": "PPC Strategist",
        "avatar": "target",
        "title": "Campaign Structure",
        "prompt_template": """As the PPC Strategist, design the complete campaign structure:

Landing page: {landing_page_url}
Brief: {brief}
Budget: ${budget_daily}/day
Target: {geo_targets}, {languages}

READ all previous roles' findings (CRO, Competitor, Keywords, Creative).

Design:
1. Campaign settings: name, bidding strategy, budget, start date
2. Ad group structure (from keyword plan)
3. Match type strategy per ad group
4. Bid adjustments (device, location, schedule)
5. Targeting settings (locations, languages, audiences)
6. Budget allocation across ad groups
7. Expected CPA range and conversion targets

Present as a blueprint the Director can review and execute. The GTM Specialist checks tracking next.""",
    },
    {
        "stage": 6,
        "role_id": "gtm_specialist",
        "role_name": "GTM Specialist",
        "avatar": "code",
        "title": "Tracking Verification",
        "prompt_template": """As the GTM Specialist, verify conversion tracking readiness for this new campaign:

Landing page: {landing_page_url}

READ the CRO Specialist's findings about existing tracking.

Check:
1. Is Google Ads conversion tag present on the landing page?
2. Is GTM container loaded?
3. Is the conversion action set up in Google Ads?
4. Is consent mode configured?
5. Will the form/CTA fire the conversion event?

If tracking is NOT ready, provide exact setup instructions.
Present a tracking readiness checklist (pass/fail for each item).

The Director will synthesize everything next.""",
    },
    {
        "stage": 7,
        "role_id": "director",
        "role_name": "Agency Director",
        "avatar": "briefcase",
        "title": "Final Review & Execution Plan",
        "prompt_template": """As the Agency Director, synthesize all role findings into a final campaign plan:

Landing page: {landing_page_url}
Brief: {brief}
Budget: ${budget_daily}/day
Target: {geo_targets}, {languages}

READ ALL previous roles' findings (CRO, Competitor, Keywords, Creative, PPC, GTM).

Present the FINAL CAMPAIGN PLAN:

1. EXECUTIVE SUMMARY — 3-sentence campaign overview
2. CAMPAIGN STRUCTURE — from PPC Strategist
3. KEYWORD PLAN — from Search Term Hunter (summary)
4. AD COPY — from Creative Director (headline count + key themes)
5. TRACKING STATUS — from GTM Specialist
6. RISK ASSESSMENT — what could go wrong, mitigation
7. LAUNCH CHECKLIST — ordered steps to execute
8. EXPECTED RESULTS — CPA range, conversion estimate for first 30 days

End with: "Ready to create this campaign? Reply 'CREATE' to build it via Google Ads MCP."

When user says CREATE, execute using MCP tools:
1. budget__create_campaign_budget
2. campaign__create_campaign (PAUSED)
3. ad_group__create_ad_group (per group)
4. keyword__add_keywords (per group)
5. ad__create_responsive_search_ad (per group)
6. campaign_criterion__add_negative_keyword_criteria
7. campaign_criterion__add_location_criteria""",
    },
]


def _format_attachments(attachments: list[dict]) -> str:
    if not attachments:
        return ""
    lines = ["The user has attached these files for reference:"]
    for att in attachments:
        lines.append(f"- {att.get('filename', 'file')} (path: {att.get('path', '')})")
    lines.append("Read each attachment to incorporate the data into your analysis.")
    return "\n".join(lines)


@router.post("/campaigns/build")
async def create_build_session(body: BuildSessionInput):
    """Create a new campaign build session and return the pipeline stages."""
    session_id = str(uuid.uuid4())
    session = BuildSession(
        id=session_id,
        account_id=body.account_id,
        created_at=datetime.now().isoformat(),
        input=body,
        stages=[
            {
                "stage": s["stage"],
                "role_id": s["role_id"],
                "role_name": s["role_name"],
                "avatar": s["avatar"],
                "title": s["title"],
                "status": "pending",
                "prompt": s["prompt_template"].format(
                    landing_page_url=body.landing_page_url,
                    brief=body.brief or "No specific brief provided",
                    budget_daily=body.budget_daily,
                    geo_targets=", ".join(body.geo_targets),
                    languages=", ".join(body.languages),
                    attachments_text=_format_attachments(body.attachments),
                ),
            }
            for s in PIPELINE_STAGES
        ],
    )
    _sessions[session_id] = session
    return session.model_dump()


@router.get("/campaigns/build/{session_id}")
async def get_build_session(session_id: str):
    """Get the current state of a build session."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}
    return session.model_dump()


@router.get("/campaigns/build/{session_id}/stage/{stage_num}")
async def get_stage_prompt(session_id: str, stage_num: int):
    """Get the prompt for a specific stage (frontend sends this to chat)."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}
    stage = next((s for s in session.stages if s["stage"] == stage_num), None)
    if not stage:
        return {"error": "Stage not found"}
    return {
        "prompt": stage["prompt"],
        "role_id": stage["role_id"],
        "role_name": stage["role_name"],
        "stage": stage_num,
    }


@router.post("/campaigns/build/{session_id}/stage/{stage_num}/complete")
async def mark_stage_complete(session_id: str, stage_num: int):
    """Mark a pipeline stage as complete."""
    session = _sessions.get(session_id)
    if not session:
        return {"error": "Session not found"}
    for stage in session.stages:
        if stage["stage"] == stage_num:
            stage["status"] = "completed"
    session.current_stage = stage_num
    if stage_num >= len(PIPELINE_STAGES):
        session.status = "completed"
    return {"status": "ok", "current_stage": session.current_stage}
