"""V2 Multi-account management endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.database import get_db
from app.models.schemas import (
    AccountAddRequest,
    AccountV2Response,
    AlertResponse,
    CampaignGoalResponse,
    CampaignGoalUpdateRequest,
    DashboardResponse,
    AccountHealthResponse,
    OnboardingScanResult,
)
from app.services.credentials import CredentialStore
from app.services.onboarding import OnboardingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["accounts"])

_cred_store = CredentialStore()
_onboarding = OnboardingService()


# ── Account CRUD ───────────────────────────────────────────────────


@router.get("/v2/accounts", response_model=list[AccountV2Response])
async def list_accounts():
    """List all connected accounts."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM accounts_v2 WHERE is_active = 1 ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [AccountV2Response(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.post("/v2/accounts", response_model=AccountV2Response)
async def add_account(req: AccountAddRequest):
    """Add a new Google Ads account with credentials."""
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException

    # 1. Validate credentials by attempting an API call
    config = {
        "developer_token": req.developer_token,
        "client_id": req.client_id,
        "client_secret": req.client_secret,
        "refresh_token": req.refresh_token,
        "login_customer_id": req.login_customer_id,
        "use_proto_plus": True,
    }
    try:
        client = GoogleAdsClient.load_from_dict(config)
        service = client.get_service("GoogleAdsService")
        query = "SELECT customer_client.descriptive_name, customer_client.id FROM customer_client LIMIT 1"
        cid = req.login_customer_id.replace("-", "")

        # Run in thread to avoid blocking
        def _validate():
            results = []
            for batch in service.search_stream(customer_id=cid, query=query):
                for row in batch.results:
                    results.append(row)
            return results

        rows = await asyncio.to_thread(_validate)
    except GoogleAdsException as e:
        raise HTTPException(status_code=400, detail=f"Invalid credentials: {e.failure.errors[0].message}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")

    # 2. Get account name from first result
    account_name = f"Account {req.login_customer_id}"
    if rows:
        account_name = rows[0].customer_client.descriptive_name or account_name

    # 3. Store account record
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO accounts_v2 (id, name, mcc_id, level, onboarded_at)
               VALUES (?, ?, NULL, 'mcc', datetime('now'))""",
            (req.login_customer_id, account_name),
        )
        await db.commit()
    finally:
        await db.close()

    # 4. Store encrypted credentials
    await _cred_store.store_credentials(req.login_customer_id, {
        "developer_token": req.developer_token,
        "client_id": req.client_id,
        "client_secret": req.client_secret,
        "refresh_token": req.refresh_token,
        "login_customer_id": req.login_customer_id,
    })

    return AccountV2Response(
        id=req.login_customer_id,
        name=account_name,
        level="mcc",
        is_active=True,
    )


@router.delete("/v2/accounts/{account_id}")
async def remove_account(account_id: str):
    """Remove an account and all associated data."""
    db = await get_db()
    try:
        # Delete in dependency order
        await db.execute("DELETE FROM alerts WHERE account_id = ?", (account_id,))
        await db.execute("DELETE FROM campaign_goals WHERE account_id = ?", (account_id,))
        await db.execute("DELETE FROM session_summaries WHERE account_id = ?", (account_id,))
        await db.execute(
            "DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE account_id = ?)",
            (account_id,),
        )
        await db.execute("DELETE FROM conversations WHERE account_id = ?", (account_id,))
        await db.execute("DELETE FROM cache WHERE key LIKE ?", (f"{account_id}:%",))
        await db.execute("DELETE FROM account_credentials WHERE account_id = ?", (account_id,))
        await db.execute("DELETE FROM accounts_v2 WHERE id = ?", (account_id,))
        await db.commit()
    finally:
        await db.close()

    return {"deleted": True, "account_id": account_id}


@router.get("/v2/accounts/{account_id}", response_model=AccountV2Response)
async def get_account(account_id: str):
    """Get a single account's details."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM accounts_v2 WHERE id = ?", (account_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        return AccountV2Response(**dict(row))
    finally:
        await db.close()


# ── Onboarding ─────────────────────────────────────────────────────


@router.post("/v2/accounts/{account_id}/onboard", response_model=OnboardingScanResult)
async def onboard_account(account_id: str):
    """Run smart onboarding: scan campaigns, detect goals/phases, generate guidelines."""
    from app.services.google_ads import GoogleAdsService

    # Verify account exists
    db = await get_db()
    try:
        cursor = await db.execute("SELECT name FROM accounts_v2 WHERE id = ?", (account_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        account_name = row["name"]
    finally:
        await db.close()

    # Fetch campaigns via direct SDK
    # MCC accounts can't query metrics directly — discover child accounts first
    ads_service = GoogleAdsService()
    campaigns = []

    try:
        # First, try to get client accounts under this MCC
        accessible = await ads_service.get_accessible_accounts()
        client_ids = [a.id for a in accessible if a.level == "client"]

        if not client_ids:
            # Not an MCC — try querying directly
            client_ids = [account_id]

        for client_id in client_ids:
            try:
                campaigns_raw = await ads_service.get_campaigns(client_id)
                for c in campaigns_raw:
                    campaigns.append({
                        "id": c.id,
                        "name": c.name,
                        "status": c.status,
                        "campaign_type": c.campaign_type,
                        "budget_micros": c.budget_micros,
                        "bidding_strategy": c.bidding_strategy,
                        "impressions": c.metrics.impressions,
                        "clicks": c.metrics.clicks,
                        "cost_micros": c.metrics.cost_micros,
                        "conversions": c.metrics.conversions,
                    })
            except Exception as e:
                logger.warning("Failed to scan client %s: %s", client_id, e)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch campaigns: {str(e)}")

    # Run full onboarding
    result = await _onboarding.run_full_onboarding(account_id, account_name, campaigns)

    return OnboardingScanResult(
        account_id=result["account_id"],
        account_name=result.get("account_name", ""),
        campaigns_found=result["campaigns_found"],
        campaigns=[
            CampaignGoalResponse(
                campaign_id=c["campaign_id"],
                campaign_name=c["campaign_name"],
                objective=c["objective"],
                phase=c["phase"],
            )
            for c in result["campaigns"]
        ],
        guidelines_generated=result.get("guidelines_generated", []),
    )


# ── Campaign Goals ─────────────────────────────────────────────────


@router.get(
    "/v2/accounts/{account_id}/campaigns/{campaign_id}/goals",
    response_model=CampaignGoalResponse,
)
async def get_campaign_goals(account_id: str, campaign_id: str):
    """Get campaign goal and phase data."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM campaign_goals WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        row = await cursor.fetchone()
        if not row:
            return CampaignGoalResponse(campaign_id=campaign_id)
        return CampaignGoalResponse(**dict(row))
    finally:
        await db.close()


@router.put(
    "/v2/accounts/{account_id}/campaigns/{campaign_id}/goals",
    response_model=CampaignGoalResponse,
)
async def update_campaign_goals(
    account_id: str, campaign_id: str, req: CampaignGoalUpdateRequest
):
    """Update campaign goal, phase, or targets."""
    db = await get_db()
    try:
        # Upsert
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Check if exists
        cursor = await db.execute(
            "SELECT 1 FROM campaign_goals WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        exists = await cursor.fetchone()

        if exists:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [account_id, campaign_id]
            await db.execute(
                f"UPDATE campaign_goals SET {set_clause}, updated_at = datetime('now') "
                f"WHERE account_id = ? AND campaign_id = ?",
                values,
            )
        else:
            updates["account_id"] = account_id
            updates["campaign_id"] = campaign_id
            cols = ", ".join(updates.keys())
            placeholders = ", ".join("?" for _ in updates)
            await db.execute(
                f"INSERT INTO campaign_goals ({cols}) VALUES ({placeholders})",
                list(updates.values()),
            )

        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM campaign_goals WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        row = await cursor.fetchone()
        return CampaignGoalResponse(**dict(row))
    finally:
        await db.close()


# ── Alerts ─────────────────────────────────────────────────────────


@router.get("/v2/accounts/{account_id}/alerts", response_model=list[AlertResponse])
async def get_alerts(account_id: str, dismissed: bool = False):
    """Get active alerts for an account."""
    db = await get_db()
    try:
        if dismissed:
            cursor = await db.execute(
                "SELECT * FROM alerts WHERE account_id = ? ORDER BY created_at DESC",
                (account_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM alerts WHERE account_id = ? AND dismissed_at IS NULL ORDER BY severity DESC, created_at DESC",
                (account_id,),
            )
        rows = await cursor.fetchall()
        return [AlertResponse(**dict(row)) for row in rows]
    finally:
        await db.close()


@router.post("/v2/accounts/{account_id}/alerts/{alert_id}/dismiss")
async def dismiss_alert(account_id: str, alert_id: int):
    """Dismiss an alert."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE alerts SET dismissed_at = datetime('now') WHERE id = ? AND account_id = ?",
            (alert_id, account_id),
        )
        await db.commit()
        return {"dismissed": True}
    finally:
        await db.close()


# ── Dashboard ──────────────────────────────────────────────────────


@router.get("/v2/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """Agency dashboard — all accounts with health summary."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM accounts_v2 WHERE is_active = 1 ORDER BY name"
        )
        accounts = await cursor.fetchall()

        account_summaries = []
        total_alerts = 0
        total_spend = 0.0

        for acct in accounts:
            acct_id = acct["id"]

            # Count active alerts
            cursor = await db.execute(
                "SELECT COUNT(*) FROM alerts WHERE account_id = ? AND dismissed_at IS NULL",
                (acct_id,),
            )
            alert_count = (await cursor.fetchone())[0]

            # Count critical alerts for health
            cursor = await db.execute(
                "SELECT COUNT(*) FROM alerts WHERE account_id = ? AND dismissed_at IS NULL AND severity = 'critical'",
                (acct_id,),
            )
            critical_count = (await cursor.fetchone())[0]

            # Determine health
            if critical_count > 0:
                health = "critical"
            elif alert_count > 0:
                health = "warning"
            else:
                health = "healthy"

            total_alerts += alert_count

            account_summaries.append(AccountHealthResponse(
                id=acct_id,
                name=acct["name"],
                health=health,
                alert_count=alert_count,
                last_synced=acct["last_synced"],
            ))

        return DashboardResponse(
            accounts=account_summaries,
            total_alerts=total_alerts,
            total_spend_30d=total_spend,
        )
    finally:
        await db.close()
