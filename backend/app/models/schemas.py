"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Accounts & Campaigns ───────────────────────────────────────────

class AccountResponse(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    level: str
    is_active: bool = True


class CampaignMetrics(BaseModel):
    impressions: int = 0
    clicks: int = 0
    cost_micros: int = 0
    conversions: float = 0.0
    ctr: float = 0.0
    avg_cpc_micros: int = 0


class CampaignResponse(BaseModel):
    id: str
    name: str
    status: str = "ENABLED"
    campaign_type: str = "SEARCH"
    budget_micros: int = 0
    bidding_strategy: str = ""
    metrics: CampaignMetrics = Field(default_factory=CampaignMetrics)


class AdGroupResponse(BaseModel):
    id: str
    name: str
    campaign_id: str
    status: str = "ENABLED"
    cpc_bid_micros: int = 0
    metrics: CampaignMetrics = Field(default_factory=CampaignMetrics)


class KeywordResponse(BaseModel):
    id: str
    text: str
    match_type: str = "BROAD"
    ad_group_id: str = ""
    ad_group_name: str = ""
    campaign_id: str = ""
    status: str = "ENABLED"
    quality_score: int | None = None
    metrics: CampaignMetrics = Field(default_factory=CampaignMetrics)


class AdResponse(BaseModel):
    id: str
    ad_group_id: str = ""
    ad_group_name: str = ""
    campaign_id: str = ""
    headlines: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    final_urls: list[str] = Field(default_factory=list)
    status: str = "ENABLED"
    metrics: CampaignMetrics = Field(default_factory=CampaignMetrics)


# ── Chat ────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    id: str
    tool_name: str
    tool_source: str = "google_ads"
    tool_input: dict | None = None
    tool_output: dict | str | None = None
    requires_confirmation: bool = False


class ChatMessageRequest(BaseModel):
    content: str
    account_id: str | None = None
    campaign_id: str | None = None
    model: str = "sonnet"  # sonnet, opus, haiku


class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: str = ""


class ToolConfirmRequest(BaseModel):
    approved: bool


# ── Conversations ───────────────────────────────────────────────────

class ConversationCreateRequest(BaseModel):
    account_id: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None
    title: str | None = None


class ConversationResponse(BaseModel):
    id: str
    account_id: str | None = None
    campaign_id: str | None = None
    campaign_name: str | None = None
    title: str | None = None
    created_at: str = ""
    updated_at: str = ""
    message_count: int = 0


# ── Setup ───────────────────────────────────────────────────────────

class SetupCredentialsRequest(BaseModel):
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str | None = None


class SetupStatusResponse(BaseModel):
    configured: bool
    has_developer_token: bool = False
    has_client_id: bool = False
    has_client_secret: bool = False
    has_refresh_token: bool = False
    has_login_customer_id: bool = False


class SetupValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


# ── Guidelines ──────────────────────────────────────────────────────

class GuidelineSection(BaseModel):
    heading: str
    level: int
    start_line: int
    end_line: int


class GuidelineFileResponse(BaseModel):
    filename: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    last_modified: float | None = None
    sections: list[GuidelineSection] = Field(default_factory=list)


class GuidelineContentResponse(BaseModel):
    filename: str
    content: str
    sections: list[GuidelineSection] = Field(default_factory=list)


class GuidelineCreateRequest(BaseModel):
    filename: str
    campaign_id: str | None = None
    campaign_name: str | None = None


class GuidelineUpdateRequest(BaseModel):
    content: str


# ── V2: Multi-Account ──────────────────────────────────────────────

class AccountV2Response(BaseModel):
    id: str
    name: str
    mcc_id: str | None = None
    level: str = "mcc"
    is_active: bool = True
    onboarded_at: str | None = None
    last_synced: str | None = None
    created_at: str = ""


class AccountAddRequest(BaseModel):
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str


class AccountHealthResponse(BaseModel):
    id: str
    name: str
    health: str = "unknown"  # healthy, warning, critical, unknown
    active_campaigns: int = 0
    total_spend_30d: float = 0.0
    total_conversions_30d: float = 0.0
    avg_cpa: float = 0.0
    alert_count: int = 0
    last_synced: str | None = None


class DashboardResponse(BaseModel):
    accounts: list[AccountHealthResponse] = Field(default_factory=list)
    total_alerts: int = 0
    total_spend_30d: float = 0.0


# ── V2: Campaign Goals ─────────────────────────────────────────────

class CampaignGoalResponse(BaseModel):
    campaign_id: str
    campaign_name: str | None = None
    objective: str = "unknown"
    phase: str = "unknown"
    phase_detected_at: str | None = None
    target_cpa: float | None = None
    target_roas: float | None = None
    monthly_budget_cap: float | None = None
    notes: str | None = None


class CampaignGoalUpdateRequest(BaseModel):
    objective: str | None = None
    phase: str | None = None
    target_cpa: float | None = None
    target_roas: float | None = None
    monthly_budget_cap: float | None = None
    notes: str | None = None


# ── V2: Alerts ─────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: int
    account_id: str
    campaign_id: str | None = None
    type: str
    severity: str = "info"
    title: str
    message: str
    recommendation: str | None = None
    created_at: str = ""
    dismissed_at: str | None = None


# ── V2: Onboarding ─────────────────────────────────────────────────

class OnboardingScanResult(BaseModel):
    account_id: str
    account_name: str = ""
    campaigns_found: int = 0
    campaigns: list[CampaignGoalResponse] = Field(default_factory=list)
    guidelines_generated: list[str] = Field(default_factory=list)


# ── V2: Conversation Search ────────────────────────────────────────

class ConversationSearchResult(BaseModel):
    conversation_id: str
    message_id: str
    content_snippet: str
    campaign_name: str | None = None
    created_at: str = ""


# ── Phase 1: Decision Log & Pinned Facts ──────────────────────────

class DecisionLogEntry(BaseModel):
    action: str
    reason: str
    outcome: str = "pending"
    role: str = "agent"


class PinnedFactEntry(BaseModel):
    fact: str
    source: str = "user"


class CampaignProfileUpdate(BaseModel):
    campaign_name: str
    goals: str | None = None
    constraints: str | None = None
    phase: str | None = None
