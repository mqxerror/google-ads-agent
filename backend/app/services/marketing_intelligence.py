"""Marketing Intelligence Service — goal detection, phase detection, proactive insights."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from enum import Enum

from app.database import get_db

logger = logging.getLogger(__name__)


class CampaignObjective(str, Enum):
    LEAD_GEN = "lead_gen"
    ECOMMERCE = "ecommerce"
    BRAND = "brand"
    TRAFFIC = "traffic"
    LOCAL = "local"
    UNKNOWN = "unknown"


class CampaignPhase(str, Enum):
    LAUNCH = "launch"
    LEARNING = "learning"
    OPTIMIZATION = "optimization"
    SCALING = "scaling"
    SUNSET = "sunset"
    UNKNOWN = "unknown"


PHASE_RULES = {
    CampaignPhase.LAUNCH: (
        "Campaign is new (<14 days). Gather data. Do NOT change bid strategy. "
        "Monitor closely. Focus on keyword and search term quality."
    ),
    CampaignPhase.LEARNING: (
        "Bid strategy is in learning phase (<30 conversions in lookback). "
        "Do NOT change bid strategy or make major structural changes. "
        "Minor keyword additions and negative keywords are safe."
    ),
    CampaignPhase.OPTIMIZATION: (
        "Stable data. Safe to adjust bids, budgets, keywords, and ad copy. "
        "Test one change at a time. Wait 7 days between major changes."
    ),
    CampaignPhase.SCALING: (
        "Performance is strong (CPA below target, room to grow). "
        "Recommend budget increases, new keywords, audience expansion. "
        "Monitor for diminishing returns."
    ),
    CampaignPhase.SUNSET: (
        "Declining performance. Recommend reducing budget or pausing. "
        "Document learnings before shutting down."
    ),
    CampaignPhase.UNKNOWN: "Phase not yet detected. Analyze before making changes.",
}


class MarketingIntelligenceService:
    """Analyzes campaign data to produce marketing intelligence."""

    def detect_campaign_goal(self, campaign_data: dict) -> CampaignObjective:
        """Infer campaign objective from bid strategy and campaign type."""
        bid_strategy = (campaign_data.get("bidding_strategy") or "").upper()
        campaign_type = (campaign_data.get("campaign_type") or "").upper()
        name = (campaign_data.get("name") or "").lower()

        # Bid strategy signals
        if "TARGET_ROAS" in bid_strategy or "MAXIMIZE_CONVERSION_VALUE" in bid_strategy:
            return CampaignObjective.ECOMMERCE
        if "TARGET_CPA" in bid_strategy or "MAXIMIZE_CONVERSIONS" in bid_strategy:
            return CampaignObjective.LEAD_GEN
        if "TARGET_IMPRESSION_SHARE" in bid_strategy:
            return CampaignObjective.BRAND
        if "MAXIMIZE_CLICKS" in bid_strategy:
            return CampaignObjective.TRAFFIC

        # Campaign type signals
        if "SHOPPING" in campaign_type:
            return CampaignObjective.ECOMMERCE
        if "DISPLAY" in campaign_type or "VIDEO" in campaign_type:
            return CampaignObjective.BRAND
        if "LOCAL" in campaign_type:
            return CampaignObjective.LOCAL

        # Name heuristics
        if any(kw in name for kw in ("brand", "awareness", "display")):
            return CampaignObjective.BRAND
        if any(kw in name for kw in ("shop", "product", "feed")):
            return CampaignObjective.ECOMMERCE

        return CampaignObjective.LEAD_GEN  # Default for Search campaigns

    def detect_campaign_phase(
        self,
        campaign_data: dict,
        conversions_30d: float = 0,
        cost_30d: float = 0,
        target_cpa: float | None = None,
    ) -> CampaignPhase:
        """Detect campaign lifecycle phase from data signals."""
        status = (campaign_data.get("status") or "").upper()
        if status == "PAUSED":
            return CampaignPhase.SUNSET

        # If we have very little data, it's likely a launch
        impressions = campaign_data.get("impressions", 0)
        clicks = campaign_data.get("clicks", 0)

        if impressions < 1000 and clicks < 50:
            return CampaignPhase.LAUNCH

        # Learning: few conversions
        if conversions_30d < 30:
            return CampaignPhase.LEARNING

        # Scaling: good CPA, room to grow
        if target_cpa and cost_30d > 0 and conversions_30d > 0:
            actual_cpa = cost_30d / conversions_30d
            if actual_cpa < target_cpa * 0.8:
                return CampaignPhase.SCALING

        # Sunset: very high CPA relative to target
        if target_cpa and conversions_30d > 0:
            actual_cpa = cost_30d / conversions_30d
            if actual_cpa > target_cpa * 2.0:
                return CampaignPhase.SUNSET

        return CampaignPhase.OPTIMIZATION

    async def generate_proactive_insights(
        self, account_id: str, campaigns: list[dict]
    ) -> list[dict]:
        """Surface issues and opportunities. Returns alert dicts ready for DB insert."""
        insights = []

        for c in campaigns:
            campaign_id = c.get("id", "")
            name = c.get("name", "")
            impressions = c.get("impressions", 0)
            clicks = c.get("clicks", 0)
            conversions = c.get("conversions", 0.0)
            cost_micros = c.get("cost_micros", 0)
            cost = cost_micros / 1_000_000 if cost_micros else 0

            # CPA calculation
            cpa = cost / conversions if conversions > 0 else 0

            # High CPA alert (> $50 and at least some spend)
            if cpa > 50 and cost > 100:
                insights.append({
                    "account_id": account_id,
                    "campaign_id": campaign_id,
                    "type": "high_cpa",
                    "severity": "warning",
                    "title": f"High CPA: {name}",
                    "message": f"CPA is ${cpa:.2f} for campaign '{name}'",
                    "recommendation": "Review search terms for irrelevant matches. Consider tightening keyword match types.",
                })

            # Zero conversions with significant spend
            if conversions == 0 and cost > 200:
                insights.append({
                    "account_id": account_id,
                    "campaign_id": campaign_id,
                    "type": "zero_conversions",
                    "severity": "critical",
                    "title": f"No conversions: {name}",
                    "message": f"Campaign '{name}' has spent ${cost:.2f} with zero conversions",
                    "recommendation": "Check conversion tracking setup. Review landing page and search terms.",
                })

            # Low quality (low CTR)
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            if ctr < 1.0 and impressions > 1000:
                insights.append({
                    "account_id": account_id,
                    "campaign_id": campaign_id,
                    "type": "low_ctr",
                    "severity": "info",
                    "title": f"Low CTR: {name}",
                    "message": f"CTR is {ctr:.1f}% for campaign '{name}'",
                    "recommendation": "Improve ad copy relevance. Review keyword-to-ad alignment.",
                })

        return insights

    async def store_insights(self, insights: list[dict]) -> int:
        """Store insights as alerts in DB, deduplicating by type+campaign."""
        if not insights:
            return 0

        db = await get_db()
        stored = 0
        try:
            for insight in insights:
                # Check for existing undismissed alert of same type+campaign
                cursor = await db.execute(
                    "SELECT 1 FROM alerts WHERE account_id = ? AND campaign_id = ? AND type = ? AND dismissed_at IS NULL",
                    (insight["account_id"], insight.get("campaign_id"), insight["type"]),
                )
                if await cursor.fetchone():
                    continue  # Deduplicate

                await db.execute(
                    """INSERT INTO alerts (account_id, campaign_id, type, severity, title, message, recommendation)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        insight["account_id"],
                        insight.get("campaign_id"),
                        insight["type"],
                        insight.get("severity", "info"),
                        insight["title"],
                        insight["message"],
                        insight.get("recommendation"),
                    ),
                )
                stored += 1

            await db.commit()
        finally:
            await db.close()
        return stored

    def enrich_agent_prompt(
        self,
        goal: CampaignObjective,
        phase: CampaignPhase,
        alerts: list[dict],
        campaign_name: str = "",
    ) -> str:
        """Generate Layer 0: Marketing Intelligence block for the agent system prompt."""
        alert_lines = ""
        if alerts:
            alert_lines = "\n".join(
                f"- {'⚠️' if a.get('severity') == 'warning' else '🔴' if a.get('severity') == 'critical' else 'ℹ️'} "
                f"[{a.get('severity', 'info').upper()}] {a.get('title', '')}: {a.get('message', '')}"
                + (f"\n  → {a['recommendation']}" if a.get("recommendation") else "")
                for a in alerts
            )
        else:
            alert_lines = "No active alerts."

        return f"""## Marketing Intelligence

**Campaign:** {campaign_name}
**Objective:** {goal.value.replace('_', ' ').title()}
**Phase:** {phase.value.title()}

### Phase Rules
{PHASE_RULES.get(phase, '')}

### Active Alerts
{alert_lines}
"""
