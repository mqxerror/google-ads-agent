"""Outcome tracking — records agent recommendations and measures their impact.

Inspired by Karpathy's autoresearch results.tsv: each agent action is an
experiment, and we measure whether it actually improved campaign metrics.

Flow:
1. Agent executes a tool (add negatives, change budget, etc.)
2. We snapshot current metrics as baseline
3. After 7/14 days, we compare baseline vs actual
4. Outcome: improved / degraded / no_change
5. Outcomes are injected into future agent prompts
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta

import aiosqlite

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# Tool name → action type mapping
TOOL_ACTION_MAP = {
    "keyword__add_keywords": "add_keywords",
    "campaign_criterion__add_negative_keyword_criteria": "add_negatives",
    "campaign__update_campaign": "update_campaign",
    "campaign__create_campaign": "create_campaign",
    "budget__create_campaign_budget": "budget_change",
    "ad__create_responsive_search_ad": "create_ad",
    "ad_group__create_ad_group": "create_ad_group",
    "keyword__update_keyword_bid": "update_bid",
    "keyword__remove_keyword": "remove_keyword",
    "ad__update_ad_status": "update_ad_status",
}

# How many days to wait before measuring outcome
MEASUREMENT_DELAYS = [7, 14]


async def record_recommendation(
    account_id: str,
    campaign_id: str,
    action_type: str,
    action_detail: str,
    conversation_id: str | None = None,
) -> str | None:
    """Record a recommendation with baseline metrics snapshot.

    Called when the agent executes a tool that modifies campaign state.
    Returns the recommendation ID, or None if metrics unavailable.
    """
    db = await get_db()
    try:
        # Snapshot current metrics as baseline
        cur = await db.execute(
            """SELECT impressions, clicks, cost_micros, conversions, ctr, avg_cpc_micros
               FROM campaign_daily_metrics
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY date DESC LIMIT 7""",
            (account_id, campaign_id),
        )
        rows = await cur.fetchall()

        if not rows:
            logger.info("No metrics data for %s/%s — skipping recommendation recording", account_id, campaign_id)
            return None

        # Compute 7-day averages as baseline
        total_impressions = sum(r["impressions"] for r in rows)
        total_clicks = sum(r["clicks"] for r in rows)
        total_cost = sum(r["cost_micros"] for r in rows)
        total_conversions = sum(r["conversions"] for r in rows)
        days = len(rows)

        baseline = {
            "days": days,
            "avg_impressions": round(total_impressions / days, 1),
            "avg_clicks": round(total_clicks / days, 1),
            "avg_cost": round(total_cost / days / 1_000_000, 2),
            "avg_conversions": round(total_conversions / days, 2),
            "avg_cpa": round((total_cost / 1_000_000) / total_conversions, 2) if total_conversions > 0 else None,
            "avg_ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
        }

        rec_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO recommendations
               (id, account_id, campaign_id, conversation_id, action_type, action_detail, baseline_metrics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rec_id, account_id, campaign_id, conversation_id, action_type, action_detail, json.dumps(baseline)),
        )
        await db.commit()

        logger.info(
            "Recorded recommendation %s: %s on %s/%s (baseline CPA: %s)",
            rec_id[:8], action_type, account_id, campaign_id, baseline.get("avg_cpa"),
        )
        return rec_id
    except Exception as e:
        logger.warning("Failed to record recommendation: %s", e)
        return None
    finally:
        await db.close()


async def measure_pending_outcomes(account_id: str) -> int:
    """Measure outcomes for recommendations that are old enough.

    Called by sync_engine after each metrics sync.
    Returns the number of outcomes measured.
    """
    db = await get_db()
    measured = 0
    try:
        # Find recommendations executed 7+ days ago that haven't been measured
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        cur = await db.execute(
            """SELECT id, campaign_id, action_type, baseline_metrics_json, executed_at
               FROM recommendations
               WHERE account_id = ? AND status = 'executed' AND executed_at <= ?
               ORDER BY executed_at""",
            (account_id, cutoff),
        )
        pending = await cur.fetchall()

        for rec in pending:
            outcome = await _measure_single_outcome(db, rec, account_id)
            if outcome:
                measured += 1

        await db.commit()
        if measured:
            logger.info("Measured %d outcomes for account %s", measured, account_id)
    except Exception as e:
        logger.warning("Outcome measurement failed for %s: %s", account_id, e)
    finally:
        await db.close()

    return measured


async def _measure_single_outcome(
    db: aiosqlite.Connection,
    rec: aiosqlite.Row,
    account_id: str,
) -> bool:
    """Measure outcome for a single recommendation."""
    baseline = json.loads(rec["baseline_metrics_json"]) if rec["baseline_metrics_json"] else {}
    if not baseline:
        return False

    campaign_id = rec["campaign_id"]
    executed_at = rec["executed_at"]

    # Get metrics for 7 days AFTER the recommendation was executed
    try:
        exec_date = datetime.fromisoformat(executed_at)
    except (ValueError, TypeError):
        return False

    after_start = (exec_date + timedelta(days=1)).strftime("%Y-%m-%d")
    after_end = (exec_date + timedelta(days=8)).strftime("%Y-%m-%d")

    cur = await db.execute(
        """SELECT impressions, clicks, cost_micros, conversions
           FROM campaign_daily_metrics
           WHERE account_id = ? AND campaign_id = ? AND date BETWEEN ? AND ?""",
        (account_id, campaign_id, after_start, after_end),
    )
    after_rows = await cur.fetchall()

    if len(after_rows) < 3:
        # Not enough post-data yet
        return False

    # Compute post-action averages
    days = len(after_rows)
    total_impressions = sum(r["impressions"] for r in after_rows)
    total_clicks = sum(r["clicks"] for r in after_rows)
    total_cost = sum(r["cost_micros"] for r in after_rows)
    total_conversions = sum(r["conversions"] for r in after_rows)

    actual_cpa = round((total_cost / 1_000_000) / total_conversions, 2) if total_conversions > 0 else None
    actual_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0

    baseline_cpa = baseline.get("avg_cpa")
    baseline_ctr = baseline.get("avg_ctr", 0)

    # Compute deltas
    delta = {
        "cpa_before": baseline_cpa,
        "cpa_after": actual_cpa,
        "ctr_before": baseline_ctr,
        "ctr_after": actual_ctr,
        "conversions_before": baseline.get("avg_conversions", 0),
        "conversions_after": round(total_conversions / days, 2),
    }

    if baseline_cpa and actual_cpa:
        delta["cpa_change_pct"] = round((actual_cpa - baseline_cpa) / baseline_cpa * 100, 1)

    # Determine outcome
    outcome = "no_change"
    if baseline_cpa and actual_cpa:
        cpa_change = (actual_cpa - baseline_cpa) / baseline_cpa
        if cpa_change < -0.05:  # CPA dropped >5%
            outcome = "improved"
        elif cpa_change > 0.10:  # CPA increased >10%
            outcome = "degraded"
    elif baseline_ctr and actual_ctr:
        ctr_change = (actual_ctr - baseline_ctr) / baseline_ctr
        if ctr_change > 0.05:
            outcome = "improved"
        elif ctr_change < -0.10:
            outcome = "degraded"

    # Update the recommendation
    await db.execute(
        """UPDATE recommendations
           SET status = 'measured', outcome = ?, outcome_delta_json = ?, measured_at = ?
           WHERE id = ?""",
        (outcome, json.dumps(delta), datetime.now().isoformat(), rec["id"]),
    )

    logger.info(
        "Outcome for %s (%s): %s (CPA: %s → %s)",
        rec["id"][:8], rec["action_type"], outcome, baseline_cpa, actual_cpa,
    )
    return True


async def get_outcomes_for_prompt(account_id: str, campaign_id: str) -> str:
    """Format recent outcomes for injection into agent prompt.

    Returns a markdown table of past recommendations and their results.
    """
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT action_type, action_detail, outcome, outcome_delta_json, executed_at
               FROM recommendations
               WHERE account_id = ? AND campaign_id = ? AND status = 'measured'
               ORDER BY executed_at DESC LIMIT 10""",
            (account_id, campaign_id),
        )
        rows = await cur.fetchall()

        if not rows:
            return ""

        parts = ["=== PAST RESULTS (what worked and what didn't) ==="]
        parts.append("| Date | Action | Outcome | CPA Change |")
        parts.append("|------|--------|---------|------------|")

        success_count = 0
        total = len(rows)

        for r in rows:
            date = r["executed_at"][:10] if r["executed_at"] else "?"
            action = r["action_detail"][:40]
            outcome = r["outcome"] or "pending"
            delta = json.loads(r["outcome_delta_json"]) if r["outcome_delta_json"] else {}

            cpa_change = delta.get("cpa_change_pct")
            cpa_str = f"{cpa_change:+.1f}%" if cpa_change is not None else "N/A"

            outcome_emoji = {"improved": "IMPROVED", "degraded": "DEGRADED", "no_change": "NO CHANGE"}.get(outcome, outcome)
            parts.append(f"| {date} | {action} | {outcome_emoji} | {cpa_str} |")

            if outcome == "improved":
                success_count += 1

        if total >= 3:
            rate = round(success_count / total * 100)
            parts.append(f"\nSuccess rate: {rate}% ({success_count}/{total} recommendations improved metrics)")

        return "\n".join(parts)
    finally:
        await db.close()


async def get_outcome_dashboard(account_id: str) -> dict:
    """Aggregate outcome data for the frontend dashboard."""
    db = await get_db()
    try:
        # Total counts by status
        cur = await db.execute(
            """SELECT status, outcome, COUNT(*) as cnt
               FROM recommendations WHERE account_id = ?
               GROUP BY status, outcome""",
            (account_id,),
        )
        counts = await cur.fetchall()

        total = 0
        measured = 0
        improved = 0
        degraded = 0
        no_change = 0
        pending = 0

        for r in counts:
            cnt = r["cnt"]
            total += cnt
            if r["status"] == "measured":
                measured += cnt
                if r["outcome"] == "improved":
                    improved += cnt
                elif r["outcome"] == "degraded":
                    degraded += cnt
                else:
                    no_change += cnt
            else:
                pending += cnt

        # Action type breakdown
        cur = await db.execute(
            """SELECT action_type, COUNT(*) as cnt,
                      SUM(CASE WHEN outcome = 'improved' THEN 1 ELSE 0 END) as improved_cnt
               FROM recommendations WHERE account_id = ? AND status = 'measured'
               GROUP BY action_type ORDER BY cnt DESC""",
            (account_id,),
        )
        action_rows = await cur.fetchall()
        top_actions = [
            {
                "type": r["action_type"],
                "count": r["cnt"],
                "success_rate": round(r["improved_cnt"] / r["cnt"] * 100) if r["cnt"] > 0 else 0,
            }
            for r in action_rows
        ]

        # Recent recommendations
        cur = await db.execute(
            """SELECT id, campaign_id, action_type, action_detail, outcome,
                      outcome_delta_json, executed_at, measured_at
               FROM recommendations WHERE account_id = ?
               ORDER BY executed_at DESC LIMIT 15""",
            (account_id,),
        )
        recent_rows = await cur.fetchall()
        recent = [
            {
                "id": r["id"],
                "campaign_id": r["campaign_id"],
                "action_type": r["action_type"],
                "action_detail": r["action_detail"],
                "outcome": r["outcome"],
                "delta": json.loads(r["outcome_delta_json"]) if r["outcome_delta_json"] else None,
                "executed_at": r["executed_at"],
                "measured_at": r["measured_at"],
            }
            for r in recent_rows
        ]

        return {
            "total_recommendations": total,
            "measured": measured,
            "pending": pending,
            "improved": improved,
            "degraded": degraded,
            "no_change": no_change,
            "success_rate": round(improved / measured * 100) if measured > 0 else 0,
            "top_actions": top_actions,
            "recent": recent,
        }
    finally:
        await db.close()


def detect_action_from_tool(tool_name: str, tool_input: dict) -> tuple[str, str] | None:
    """Detect an actionable recommendation from a tool call.

    Returns (action_type, action_detail) or None if not a trackable action.
    """
    # Strip MCP prefix
    clean_name = tool_name
    for prefix in ("mcp__google-ads__", "mcp__google_ads__"):
        if clean_name.startswith(prefix):
            clean_name = clean_name[len(prefix):]
            break

    action_type = TOOL_ACTION_MAP.get(clean_name)
    if not action_type:
        return None

    # Build human-readable detail
    detail = action_type.replace("_", " ").title()

    if action_type == "add_negatives":
        keywords = tool_input.get("keywords", [])
        if isinstance(keywords, list):
            detail = f"Added {len(keywords)} negative keywords"
        else:
            detail = "Added negative keywords"
    elif action_type == "add_keywords":
        keywords = tool_input.get("keywords", [])
        if isinstance(keywords, list):
            detail = f"Added {len(keywords)} keywords"
        else:
            detail = "Added keywords"
    elif action_type == "update_campaign":
        status = tool_input.get("status")
        if status:
            detail = f"Changed campaign status to {status}"
        else:
            detail = "Updated campaign settings"
    elif action_type == "budget_change":
        amount = tool_input.get("amount_micros")
        if amount:
            detail = f"Set budget to ${int(amount) / 1_000_000:.0f}/day"
        else:
            detail = "Changed budget"
    elif action_type == "create_ad":
        detail = "Created responsive search ad"
    elif action_type == "remove_keyword":
        detail = "Removed keyword"
    elif action_type == "update_bid":
        detail = "Updated keyword bid"

    return action_type, detail
