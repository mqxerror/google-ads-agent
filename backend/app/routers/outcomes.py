"""Outcome tracking endpoints — view agent recommendation results."""

from fastapi import APIRouter

from app.services.outcome_tracker import get_outcome_dashboard, get_outcomes_for_prompt

router = APIRouter(prefix="/api", tags=["outcomes"])


@router.get("/accounts/{account_id}/outcomes")
async def get_outcomes(account_id: str) -> dict:
    """Get outcome dashboard data for an account."""
    return await get_outcome_dashboard(account_id)


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/outcomes")
async def get_campaign_outcomes(account_id: str, campaign_id: str) -> dict:
    """Get outcomes for a specific campaign."""
    from app.database import get_db
    import json

    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT id, action_type, action_detail, outcome, outcome_delta_json,
                      executed_at, measured_at, status
               FROM recommendations
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY executed_at DESC LIMIT 20""",
            (account_id, campaign_id),
        )
        rows = await cur.fetchall()

        return {
            "campaign_id": campaign_id,
            "recommendations": [
                {
                    "id": r["id"],
                    "action_type": r["action_type"],
                    "action_detail": r["action_detail"],
                    "outcome": r["outcome"],
                    "status": r["status"],
                    "delta": json.loads(r["outcome_delta_json"]) if r["outcome_delta_json"] else None,
                    "executed_at": r["executed_at"],
                    "measured_at": r["measured_at"],
                }
                for r in rows
            ],
        }
    finally:
        await db.close()
