"""change_log persistence + the merged Changelog feed (app-process, async).

The `change_log` table (migration V25) is the durable record of every write the
app can attribute — an app-user button (`operations.py`), a chat-specialist MCP
tool (the `CampaignScopeMiddleware` hook, written via `change_capture`), a
scheduler plan, or an API call — each with before→after state and, when safe, a
`revert_spec`. This module writes rows from the app side and builds the feed the
Changelog page renders.

The feed MERGES two sources into one timeline:
  * `change_log`     — in-app writes (may be revertible).
  * `external_change`— out-of-band changes (Google UI / other operators), always
                       revertible=0, attributed via the external-change service.

Batch writes (e.g. 24 negatives added in one op) share a `batch_id` and collapse
into a single feed entry whose revert undoes all members.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import get_db
from app.services import change_capture

logger = logging.getLogger(__name__)

_INSERT_COLS = (
    "actor_type", "actor_detail", "account_id", "campaign_id", "resource",
    "resource_name", "action", "field", "before_value", "after_value", "summary",
    "tool_name", "batch_id", "batch_count", "revertible", "revert_reason",
    "revert_spec", "reverts",
)


async def record(row: dict[str, Any], *, db=None) -> int:
    """INSERT one change_log row (async). Accepts a partial dict — missing columns
    default. Returns the new row id. Reuses an open connection when `db` is given
    (so a revert can insert + update the original atomically)."""
    own = db is None
    if own:
        db = await get_db()
    try:
        cols = [c for c in _INSERT_COLS if c in row]
        placeholders = ", ".join("?" for _ in cols)
        cur = await db.execute(
            f"INSERT INTO change_log ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(row.get(c) for c in cols),
        )
        if own:
            await db.commit()
        return cur.lastrowid
    finally:
        if own:
            await db.close()


async def get(change_id: int) -> dict[str, Any] | None:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM change_log WHERE id = ?", (change_id,))
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_rows(
    *,
    account_id: str | None = None,
    campaign_id: str | None = None,
    actor_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if account_id:
        where.append("account_id = ?")
        params.append(account_id)
    if campaign_id:
        where.append("campaign_id = ?")
        params.append(campaign_id)
    if actor_type:
        where.append("actor_type = ?")
        params.append(actor_type)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    db = await get_db()
    try:
        cur = await db.execute(
            f"SELECT * FROM change_log{clause} "
            f"ORDER BY datetime(ts) DESC, id DESC LIMIT ?",
            (*params, limit),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


async def mark_reverted(change_id: int, revert_row_id: int, *, db=None) -> None:
    own = db is None
    if own:
        db = await get_db()
    try:
        await db.execute(
            "UPDATE change_log SET reverted_by = ?, reverted_at = datetime('now') "
            "WHERE id = ?",
            (revert_row_id, change_id),
        )
        if own:
            await db.commit()
    finally:
        if own:
            await db.close()


async def batch_members(batch_id: str) -> list[dict[str, Any]]:
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT * FROM change_log WHERE batch_id = ? ORDER BY id ASC",
            (batch_id,),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


# ── Feed assembly (merge + batch-group) ───────────────────────────────────────

def _entry_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a change_log row into an API feed entry."""
    return {
        "id": row["id"],
        "ts": row["ts"],
        "source": "revert" if row.get("actor_type") == "revert" else "app",
        "actor_type": row.get("actor_type"),
        "actor_detail": row.get("actor_detail"),
        "account_id": row.get("account_id"),
        "campaign_id": row.get("campaign_id"),
        "resource": row.get("resource"),
        "action": row.get("action"),
        "field": row.get("field"),
        "summary": row.get("summary"),
        "before_value": row.get("before_value"),
        "after_value": row.get("after_value"),
        "revertible": bool(row.get("revertible")),
        "revert_reason": row.get("revert_reason"),
        "reverts": row.get("reverts"),
        "reverted_by": row.get("reverted_by"),
        "reverted_at": row.get("reverted_at"),
        "tool_name": row.get("tool_name"),
        "batch_id": row.get("batch_id"),
        "batch_count": row.get("batch_count") or 1,
    }


def _entry_from_external(row: dict[str, Any]) -> dict[str, Any]:
    field = row.get("field") or "field"
    before, after = row.get("before"), row.get("after")
    if field == "budget_micros":
        summary = f"Budget {change_capture.money(before)} → {change_capture.money(after)} (outside the app)"
    elif field == "status":
        summary = f"Status {before or '?'} → {after or '?'} (outside the app)"
    else:
        summary = f"{field} {before or '?'} → {after or '?'} (outside the app)"
    return {
        "id": f"ext-{row['id']}",
        "ts": row.get("detected_at"),
        "source": "external",
        "actor_type": "external",
        "actor_detail": row.get("source") or "Google Ads (outside the app)",
        "account_id": row.get("account_id"),
        "campaign_id": row.get("campaign_id"),
        "resource": "campaign",
        "action": "update",
        "field": field,
        "summary": summary,
        "before_value": before,
        "after_value": after,
        "revertible": False,
        "revert_reason": "Made outside the app (Google Ads UI or another "
                         "operator) — this app can't undo it.",
        "reverts": None,
        "reverted_by": None,
        "reverted_at": None,
        "tool_name": None,
        "batch_id": None,
        "batch_count": 1,
    }


async def build_feed(
    *,
    account_id: str | None = None,
    campaign_id: str | None = None,
    actor_type: str | None = None,
    include_external: bool = True,
    limit: int = 200,
) -> dict[str, Any]:
    """Return {entries, history_begins}. Merges in-app + external changes newest-
    first and collapses batch writes into a single grouped entry."""
    rows = await list_rows(account_id=account_id, campaign_id=campaign_id,
                           actor_type=actor_type, limit=limit)

    # Group by batch_id (rows without one stay singular).
    grouped: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for row in rows:
        bid = row.get("batch_id")
        entry = _entry_from_row(row)
        if bid:
            g = grouped.get(bid)
            if g is None:
                entry["batch_id"] = bid
                entry["members"] = [row["id"]]
                entry["batch_count"] = max(entry.get("batch_count") or 1, 1)
                grouped[bid] = entry
                entries.append(entry)
            else:
                g["members"].append(row["id"])
                # Any member still revertible keeps the group revertible.
                g["revertible"] = g["revertible"] or entry["revertible"]
                if entry["reverted_at"] and not g.get("reverted_at"):
                    g["reverted_at"] = entry["reverted_at"]
        else:
            entries.append(entry)

    # Finalise batch counts + summaries from real member counts.
    for g in grouped.values():
        n = len(g["members"])
        if n > 1:
            g["batch_count"] = n
            noun = {"negative_keyword": "negative keyword", "keyword": "keyword"}.get(
                g.get("resource"), g.get("resource") or "change")
            g["summary"] = f"Added {n} {noun}s"

    if include_external and actor_type in (None, "external"):
        from app.services import external_change
        acct = account_id or ""
        if acct:
            ext = await external_change.list_external_changes(acct, limit=limit)
            for e in ext:
                if campaign_id and str(e.get("campaign_id") or "") != str(campaign_id):
                    continue
                entries.append(_entry_from_external(e))

    entries.sort(key=lambda e: (str(e.get("ts") or ""), str(e.get("id"))), reverse=True)
    entries = entries[:limit]

    history_begins = await earliest_ts(account_id=account_id)
    return {"entries": entries, "history_begins": history_begins}


async def earliest_ts(*, account_id: str | None = None) -> str | None:
    """The timestamp of the oldest captured change — the honest 'history begins'
    marker (we never fabricate pre-deploy history)."""
    db = await get_db()
    try:
        if account_id:
            cur = await db.execute(
                "SELECT MIN(ts) AS m FROM change_log WHERE account_id = ?",
                (account_id,),
            )
        else:
            cur = await db.execute("SELECT MIN(ts) AS m FROM change_log")
        row = await cur.fetchone()
        return row["m"] if row and row["m"] else None
    finally:
        await db.close()
