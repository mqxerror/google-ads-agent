"""Campaigns repository — single source of truth for campaign metadata.

Every consumer of "what campaigns exist and what's their status / budget /
channel" reads from here, and ONLY the `sync_campaigns()` function below
talks to the live Google Ads API for that metadata. Daily performance
metrics still live in `campaign_daily_metrics` (different table, written
by `metrics_store.sync_daily_metrics`), and date-rangeable views join the
two — but the canonical "is this campaign ENABLED right now?" answer is
in the `campaigns` table.

Until V11 the sidebar read a JSON blob in `cache`, the agent context
called `_ads_svc.get_campaigns()` direct, and `campaign_daily_metrics`
had `campaign_status` NULL for every row. Three sources, no shared
schema, silent disagreement. This module is the fix.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.database import get_db
from app.services.google_ads import GoogleAdsService

logger = logging.getLogger(__name__)


# How long an account's campaign metadata may stay stale before a read
# triggers a fresh sync. Sidebar surfaces `last_synced_at` so this
# threshold is visible to the user too — no invisible TTLs.
STALE_AFTER_SECONDS = 300  # 5 minutes


_ads_svc = GoogleAdsService()


# ── Reads ─────────────────────────────────────────────────────────────


async def list_campaigns(
    account_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Return campaigns for an account from the DB.

    If the data is stale or the account has no rows yet, sync first; on
    sync failure (API down, quota, etc.) serve whatever's in the table
    rather than 500ing. The sidebar will show the (now older)
    last_synced_at so the user knows.
    """
    if await _is_stale(account_id):
        try:
            await sync_campaigns(account_id)
        except Exception as e:
            logger.warning(
                "sync_campaigns(%s) failed: %s — serving from DB anyway.",
                account_id, e,
            )
    return await _read(account_id, status)


async def get_campaign(
    account_id: str, campaign_id: str
) -> dict[str, Any] | None:
    """Single-campaign metadata lookup. Triggers sync if stale."""
    rows = await list_campaigns(account_id)
    return next(
        (r for r in rows if str(r.get("campaign_id")) == str(campaign_id)),
        None,
    )


async def last_synced_at(account_id: str) -> str | None:
    """Most recent sync timestamp for an account (ISO-ish string), or None
    if the account has no rows yet. Returned to the UI so the sidebar
    can show 'last synced X ago' instead of pretending data is fresh."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT MAX(last_synced_at) ts FROM campaigns WHERE account_id = ?",
            (account_id,),
        )
        row = await cur.fetchone()
        return row["ts"] if row and row["ts"] else None
    finally:
        await db.close()


# ── Writes (only the sync worker writes; everything else reads) ──────


async def sync_campaigns(account_id: str) -> int:
    """Pull live campaigns for an account and upsert the metadata into
    the `campaigns` table. Returns the number of rows touched.

    This is the ONLY function that talks to the Google Ads API for
    campaign metadata. Every other code path must go through
    `list_campaigns` / `get_campaign` above.
    """
    logger.info("Syncing campaigns for account %s...", account_id)
    live = await _ads_svc.get_campaigns(account_id)

    db = await get_db()
    try:
        # Snapshot the CURRENT roster values BEFORE the upsert so we can diff
        # old→new and detect out-of-band ("external") changes (Epic C / C5).
        # {campaign_id -> {status, bidding_strategy, budget_micros}}. Best-effort:
        # a snapshot failure must never block the sync.
        before_rows: dict[str, dict] = {}
        try:
            cur = await db.execute(
                "SELECT campaign_id, status, bidding_strategy, budget_micros "
                "FROM campaigns WHERE account_id = ?",
                (account_id,),
            )
            for row in await cur.fetchall():
                before_rows[str(row["campaign_id"])] = {
                    "status": row["status"],
                    "bidding_strategy": row["bidding_strategy"],
                    "budget_micros": row["budget_micros"],
                }
        except Exception as _e:  # pragma: no cover — defensive
            logger.warning("external-change snapshot failed for %s: %s", account_id, _e)
            before_rows = {}

        n = 0
        after_rows: dict[str, dict] = {}
        for item in live:
            d = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            cid = str(d.get("id") or d.get("campaign_id") or "").strip()
            if not cid:
                continue
            await db.execute(
                """
                INSERT INTO campaigns
                    (campaign_id, account_id, name, status, channel,
                     bidding_strategy, budget_micros,
                     last_synced_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        datetime('now'), datetime('now'), datetime('now'))
                ON CONFLICT(account_id, campaign_id) DO UPDATE SET
                    name           = excluded.name,
                    status         = excluded.status,
                    channel        = excluded.channel,
                    bidding_strategy = excluded.bidding_strategy,
                    budget_micros  = excluded.budget_micros,
                    last_synced_at = excluded.last_synced_at,
                    updated_at     = excluded.updated_at
                """,
                (
                    cid, account_id,
                    d.get("name"),
                    d.get("status"),
                    d.get("campaign_type") or d.get("channel"),
                    d.get("bidding_strategy"),
                    d.get("budget_micros"),
                ),
            )
            after_rows[cid] = {
                "status": d.get("status"),
                "bidding_strategy": d.get("bidding_strategy"),
                "budget_micros": d.get("budget_micros"),
            }
            n += 1
        await db.commit()
        logger.info("Synced %d campaigns for account %s.", n, account_id)
    finally:
        await db.close()

    # Detect + record out-of-band changes (Epic C / C5), AFTER the connection is
    # closed so the diff writer's own connection doesn't contend on the WAL.
    # Best-effort — external-change detection must never break the roster sync's
    # contract (it still returns the row count `n` unchanged).
    try:
        from app.services import external_change

        await external_change.diff_and_record(account_id, before_rows, after_rows)
    except Exception as _e:  # pragma: no cover — defensive
        logger.warning("external-change diff failed for %s: %s", account_id, _e)

    return n


# ── Internals ────────────────────────────────────────────────────────


async def _is_stale(account_id: str) -> bool:
    """True if the most recent sync for this account is older than
    STALE_AFTER_SECONDS, or if there are no rows yet."""
    ts = await last_synced_at(account_id)
    if not ts:
        return True
    try:
        # SQLite datetime('now') returns "YYYY-MM-DD HH:MM:SS" in UTC.
        last = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True
    delta = (datetime.now(timezone.utc) - last).total_seconds()
    return delta >= STALE_AFTER_SECONDS


async def _read(
    account_id: str, status: str | None
) -> list[dict[str, Any]]:
    db = await get_db()
    try:
        if status:
            cur = await db.execute(
                """
                SELECT campaign_id, account_id, name, status, channel,
                       bidding_strategy, budget_micros, last_synced_at
                FROM campaigns
                WHERE account_id = ? AND status = ?
                ORDER BY name
                """,
                (account_id, status),
            )
        else:
            cur = await db.execute(
                """
                SELECT campaign_id, account_id, name, status, channel,
                       bidding_strategy, budget_micros, last_synced_at
                FROM campaigns
                WHERE account_id = ?
                ORDER BY name
                """,
                (account_id,),
            )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()
