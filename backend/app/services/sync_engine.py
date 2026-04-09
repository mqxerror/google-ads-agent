"""Background sync engine — pulls Google Ads data on a schedule, stores in SQLite.

Data flows: Google Ads API → campaign_daily_metrics table → agent reads from DB.
The agent NEVER hits the API directly during conversation — only this sync engine does.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, timedelta

from app.config import settings
from app.database import get_db
from app.services.google_ads import GoogleAdsService

logger = logging.getLogger(__name__)

_ads_svc = GoogleAdsService()
_sync_task: asyncio.Task | None = None


async def sync_account(account_id: str, days: int | None = None) -> dict:
    """Pull campaign metrics for an account and store day-by-day snapshots.

    Returns a summary dict with counts and status.
    """
    lookback = days or settings.SYNC_LOOKBACK_DAYS
    today = date.today()
    db = await get_db()

    try:
        campaigns_synced = 0
        days_synced = 0
        errors = []

        # Fetch all campaigns for the full date range in ONE call (not N+1)
        date_from = (today - timedelta(days=lookback - 1)).isoformat()
        date_to = today.isoformat()

        try:
            campaigns = await _ads_svc.get_campaigns(account_id, date_from, date_to)
        except Exception as e:
            logger.error("Sync failed to fetch campaigns for %s: %s", account_id, e)
            await _update_sync_status(db, account_id, "error", str(e), 0, 0)
            return {"status": "error", "error": str(e)}

        # Now fetch day-by-day for each campaign
        for campaign in campaigns:
            if campaign.status == "REMOVED":
                continue
            try:
                await _sync_campaign_daily(
                    db, account_id, campaign.id, campaign.name,
                    campaign.budget_micros, campaign.bidding_strategy,
                    campaign.status, lookback,
                )
                campaigns_synced += 1
            except Exception as e:
                errors.append(f"{campaign.name}: {e}")
                logger.error("Sync error for campaign %s: %s", campaign.name, e)

        # Count actual days written
        cur = await db.execute(
            "SELECT COUNT(DISTINCT metric_date) FROM campaign_daily_metrics WHERE account_id = ?",
            (account_id,),
        )
        row = await cur.fetchone()
        days_synced = row[0] if row else 0

        status = "success" if not errors else "partial"
        error_msg = "; ".join(errors[:3]) if errors else None
        await _update_sync_status(db, account_id, status, error_msg, campaigns_synced, days_synced)

        logger.info(
            "Sync complete for %s: %d campaigns, %d days, %d errors",
            account_id, campaigns_synced, days_synced, len(errors),
        )
        return {
            "status": status,
            "campaigns_synced": campaigns_synced,
            "days_synced": days_synced,
            "errors": errors,
        }

    finally:
        await db.close()


async def _sync_campaign_daily(
    db,
    account_id: str,
    campaign_id: str,
    campaign_name: str,
    budget_micros: int,
    bidding_strategy: str,
    status: str,
    lookback: int,
) -> None:
    """Fetch and upsert daily metrics for a single campaign."""
    today = date.today()

    for i in range(lookback):
        d = today - timedelta(days=i)
        d_str = d.isoformat()

        try:
            day_data = await _ads_svc.get_campaigns(account_id, d_str, d_str)
            match = next((c for c in day_data if c.id == campaign_id), None)

            if match and match.metrics.impressions > 0:
                m = match.metrics
                cpc = m.cost_micros // m.clicks if m.clicks > 0 else 0
                ctr = m.clicks / m.impressions * 100 if m.impressions > 0 else 0.0

                await db.execute(
                    """INSERT INTO campaign_daily_metrics
                       (id, account_id, campaign_id, campaign_name, metric_date,
                        impressions, clicks, cost_micros, conversions, ctr,
                        avg_cpc_micros, budget_micros, bidding_strategy, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(account_id, campaign_id, metric_date)
                       DO UPDATE SET
                        impressions=excluded.impressions,
                        clicks=excluded.clicks,
                        cost_micros=excluded.cost_micros,
                        conversions=excluded.conversions,
                        ctr=excluded.ctr,
                        avg_cpc_micros=excluded.avg_cpc_micros,
                        budget_micros=excluded.budget_micros,
                        bidding_strategy=excluded.bidding_strategy,
                        status=excluded.status,
                        synced_at=datetime('now')
                    """,
                    (
                        str(uuid.uuid4()), account_id, campaign_id, campaign_name,
                        d_str, m.impressions, m.clicks, m.cost_micros,
                        m.conversions, ctr, cpc, budget_micros,
                        bidding_strategy, status,
                    ),
                )
            else:
                # No data for this day — insert zero row so we know we checked
                await db.execute(
                    """INSERT INTO campaign_daily_metrics
                       (id, account_id, campaign_id, campaign_name, metric_date,
                        budget_micros, bidding_strategy, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(account_id, campaign_id, metric_date) DO NOTHING
                    """,
                    (
                        str(uuid.uuid4()), account_id, campaign_id, campaign_name,
                        d_str, budget_micros, bidding_strategy, status,
                    ),
                )
        except Exception:
            # Skip individual days that fail — don't break the whole sync
            continue

    await db.commit()


async def _update_sync_status(
    db, account_id: str, status: str, error: str | None,
    campaigns: int, days: int,
) -> None:
    """Upsert sync status for an account."""
    await db.execute(
        """INSERT INTO sync_status (account_id, last_sync_at, last_sync_status, last_sync_error, campaigns_synced, days_synced)
           VALUES (?, datetime('now'), ?, ?, ?, ?)
           ON CONFLICT(account_id)
           DO UPDATE SET
            last_sync_at=datetime('now'),
            last_sync_status=excluded.last_sync_status,
            last_sync_error=excluded.last_sync_error,
            campaigns_synced=excluded.campaigns_synced,
            days_synced=excluded.days_synced
        """,
        (account_id, status, error, campaigns, days),
    )
    await db.commit()


# ── Query helpers — agent reads from these, never from API ──────


async def get_daily_metrics(
    account_id: str,
    campaign_id: str,
    days: int = 7,
) -> list[dict]:
    """Get day-by-day metrics for a campaign from local snapshots."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT metric_date, impressions, clicks, cost_micros,
                      conversions, ctr, avg_cpc_micros, budget_micros,
                      bidding_strategy, status
               FROM campaign_daily_metrics
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY metric_date DESC
               LIMIT ?""",
            (account_id, campaign_id, days),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_all_campaign_summaries(account_id: str, days: int = 7) -> list[dict]:
    """Get latest metrics for all campaigns in an account."""
    db = await get_db()
    try:
        date_from = (date.today() - timedelta(days=days - 1)).isoformat()
        cur = await db.execute(
            """SELECT campaign_id, campaign_name, status, budget_micros, bidding_strategy,
                      SUM(impressions) as impressions,
                      SUM(clicks) as clicks,
                      SUM(cost_micros) as cost_micros,
                      SUM(conversions) as conversions
               FROM campaign_daily_metrics
               WHERE account_id = ? AND metric_date >= ?
               GROUP BY campaign_id
               ORDER BY campaign_name""",
            (account_id, date_from),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_sync_status(account_id: str) -> dict | None:
    """Get the last sync status for an account."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM sync_status WHERE account_id = ?",
            (account_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_metric_trend(
    account_id: str, campaign_id: str, metric: str, days: int = 14,
) -> list[dict]:
    """Get a specific metric trend over time for trend analysis."""
    valid_metrics = {"impressions", "clicks", "cost_micros", "conversions", "ctr", "avg_cpc_micros"}
    if metric not in valid_metrics:
        return []

    db = await get_db()
    try:
        cur = await db.execute(
            f"""SELECT metric_date, {metric}
                FROM campaign_daily_metrics
                WHERE account_id = ? AND campaign_id = ?
                ORDER BY metric_date DESC
                LIMIT ?""",
            (account_id, campaign_id, days),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Background scheduler ───────────────────────────────────────


async def _sync_loop():
    """Runs in background, syncs all known accounts on a schedule."""
    interval = settings.SYNC_INTERVAL_HOURS * 3600
    while True:
        try:
            db = await get_db()
            try:
                # Get all accounts that have been used
                cur = await db.execute(
                    "SELECT DISTINCT account_id FROM conversations WHERE account_id IS NOT NULL"
                )
                rows = await cur.fetchall()
                account_ids = [r["account_id"] for r in rows]
            finally:
                await db.close()

            if not account_ids:
                # Fallback: try login customer ID
                login_id = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
                if login_id:
                    account_ids = [login_id]

            for account_id in account_ids:
                try:
                    await sync_account(account_id)
                except Exception as e:
                    logger.error("Background sync failed for %s: %s", account_id, e)

        except Exception as e:
            logger.error("Background sync loop error: %s", e)

        await asyncio.sleep(interval)


def start_background_sync():
    """Start the background sync loop. Call once at app startup."""
    global _sync_task
    if not settings.SYNC_ENABLED:
        logger.info("Background sync disabled")
        return
    if _sync_task is not None:
        logger.warning("Background sync already running")
        return
    _sync_task = asyncio.create_task(_sync_loop())
    logger.info("Background sync started (interval: %dh)", settings.SYNC_INTERVAL_HOURS)


def stop_background_sync():
    """Stop the background sync loop."""
    global _sync_task
    if _sync_task:
        _sync_task.cancel()
        _sync_task = None
        logger.info("Background sync stopped")
