"""Asset-groups repository — single source of truth for PMax asset groups.

Mirror of `campaigns_repo` (V11). The PMax orchestrator writes asset
group records here immediately after a successful create so the
wizard / agent / future read paths don't have to re-fetch from Google
to know what we sent.

Columns that hold structured data (headlines, descriptions, asset refs,
audience signals) are stored as JSON strings; the agent reads them as
dicts/lists. We never query inside the JSON, so flattening would be
premature.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from app.database import get_db

logger = logging.getLogger(__name__)


def _dumps(value: Any) -> str | None:
    """JSON-encode a value, returning None for None so the column stays NULL."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _loads(s: str | None) -> Any:
    """JSON-decode, tolerating None / empty / corrupt."""
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


async def upsert_asset_group(
    account_id: str,
    campaign_id: str,
    asset_group_id: str,
    *,
    name: str | None = None,
    status: str | None = None,
    final_urls: list[str] | None = None,
    business_name: str | None = None,
    headlines: list[str] | None = None,
    long_headlines: list[str] | None = None,
    descriptions: list[str] | None = None,
    asset_refs: dict[str, list[str]] | None = None,
    signals: list[dict[str, Any]] | None = None,
) -> None:
    """Insert-or-replace an asset group row. Called by the PMax orchestrator
    right after a successful create so the table tracks reality."""
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO asset_groups
                (asset_group_id, account_id, campaign_id, name, status,
                 final_urls, business_name, headlines, long_headlines,
                 descriptions, asset_refs, signals,
                 last_synced_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    datetime('now'), datetime('now'), datetime('now'))
            ON CONFLICT(account_id, asset_group_id) DO UPDATE SET
                campaign_id   = excluded.campaign_id,
                name          = excluded.name,
                status        = excluded.status,
                final_urls    = excluded.final_urls,
                business_name = excluded.business_name,
                headlines     = excluded.headlines,
                long_headlines= excluded.long_headlines,
                descriptions  = excluded.descriptions,
                asset_refs    = excluded.asset_refs,
                signals       = excluded.signals,
                last_synced_at= excluded.last_synced_at,
                updated_at    = excluded.updated_at
            """,
            (
                str(asset_group_id), account_id, str(campaign_id),
                name, status,
                _dumps(final_urls), business_name,
                _dumps(headlines), _dumps(long_headlines), _dumps(descriptions),
                _dumps(asset_refs), _dumps(signals),
            ),
        )
        await db.commit()
        logger.info(
            "asset_groups upsert: account=%s campaign=%s group=%s",
            account_id, campaign_id, asset_group_id,
        )
    finally:
        await db.close()


async def list_for_campaign(account_id: str, campaign_id: str) -> list[dict[str, Any]]:
    """All asset groups for a campaign, JSON columns decoded."""
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT asset_group_id, account_id, campaign_id, name, status,
                      final_urls, business_name, headlines, long_headlines,
                      descriptions, asset_refs, signals, last_synced_at
               FROM asset_groups
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY name""",
            (account_id, str(campaign_id)),
        )
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()


async def get_asset_group(account_id: str, asset_group_id: str) -> dict[str, Any] | None:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT asset_group_id, account_id, campaign_id, name, status,
                      final_urls, business_name, headlines, long_headlines,
                      descriptions, asset_refs, signals, last_synced_at
               FROM asset_groups
               WHERE account_id = ? AND asset_group_id = ?""",
            (account_id, str(asset_group_id)),
        )
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        await db.close()


async def last_synced_at(account_id: str) -> str | None:
    """For freshness display, mirrors campaigns_repo's symmetric helper."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT MAX(last_synced_at) ts FROM asset_groups WHERE account_id = ?",
            (account_id,),
        )
        row = await cur.fetchone()
        return row["ts"] if row and row["ts"] else None
    finally:
        await db.close()


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a sqlite Row to a dict, decoding JSON columns."""
    return {
        "asset_group_id": row["asset_group_id"],
        "account_id": row["account_id"],
        "campaign_id": row["campaign_id"],
        "name": row["name"],
        "status": row["status"],
        "final_urls": _loads(row["final_urls"]),
        "business_name": row["business_name"],
        "headlines": _loads(row["headlines"]),
        "long_headlines": _loads(row["long_headlines"]),
        "descriptions": _loads(row["descriptions"]),
        "asset_refs": _loads(row["asset_refs"]),
        "signals": _loads(row["signals"]),
        "last_synced_at": row["last_synced_at"],
    }
