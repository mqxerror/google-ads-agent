"""External-change detection (Dashboard v2.1 — Epic C / C5).

The "reverted settings" mystery: a campaign shows ENABLED after it was PAUSED, a
bidding strategy looks wrong — and the app never wrote anything (the freshness
plan RC-8). The account was changed OUTSIDE the app (Google Ads UI, an SDK
script, another operator) and the dashboard just displayed a stale snapshot as
truth. This module makes those out-of-band changes VISIBLE.

Mechanism (roster-diff): every roster sync (`campaigns_repo.sync_campaigns`)
snapshots the pre-upsert `status` / `bidding_strategy` / `budget_micros` per
campaign, then diffs against the freshly-synced values. Any field that changed
gets an `external_change` row, surfaced in the AgentActivity feed as
"Changed outside the app · <field> <before> → <after>".

── The lazy-table deviation ────────────────────────────────────────────────
The plan wants an `external_change` table as migration V21. We do NOT add a
migration here: a concurrent agent owns `app/database.py` and we must stay off
it entirely. Instead this module creates the table lazily the first time it's
touched, via `_ensure_table(db)` (CREATE TABLE IF NOT EXISTS) — idempotent and
self-contained. This trades the single canonical migration ledger for zero
coordination risk with the other agent; the schema is identical to the plan's
§PART2.1.

── Attribution scope (v1) ──────────────────────────────────────────────────
The plan's PART2.1 wants changes "not attributable to an app-side plan/operation"
recorded as external. For v1 we take the conservative path C5 explicitly allows:
record ALL detected roster diffs with source='external'. Roster-diff rows work
WITHOUT change_event attribution — attribution (who/when via the Google Ads
`change_event` GAQL resource) is the timeboxed BONUS (plan risk #6), DEFERRED.
Filtering app-side-attributable changes out is a follow-up (see the code comment
in `diff_and_record`).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# The three roster fields whose out-of-band changes we track (plan PART2.1).
_TRACKED_FIELDS = ("status", "bidding_strategy", "budget_micros")

_ensured = False  # process-level fast-path so we don't re-run the DDL each call


async def _ensure_table(db) -> None:
    """Create the `external_change` table if it doesn't exist (lazy, idempotent).

    See the module docstring: we can't add a database.py migration (a concurrent
    agent owns that file), so the table is created on first use here. Schema per
    the freshness plan §PART2.1.
    """
    global _ensured
    if _ensured:
        return
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS external_change (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT,
            account_id TEXT,
            field TEXT,
            before TEXT,
            after TEXT,
            detected_at TEXT DEFAULT (datetime('now')),
            source TEXT DEFAULT 'external'
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_change_account "
        "ON external_change(account_id, detected_at)"
    )
    await db.commit()
    _ensured = True


async def record_external_changes(account_id: str, diffs: list[dict]) -> int:
    """Insert `external_change` rows for a list of detected diffs.

    Each diff dict: {campaign_id, field, before, after}. `source` defaults to
    'external'. Emits an SSE `external_change` event (per account) when any rows
    are written so the AgentActivity feed refreshes without a reload. Returns the
    number of rows inserted.
    """
    if not diffs:
        return 0
    from app.database import get_db

    db = await get_db()
    try:
        await _ensure_table(db)
        for d in diffs:
            await db.execute(
                """INSERT INTO external_change
                       (campaign_id, account_id, field, before, after,
                        detected_at, source)
                   VALUES (?, ?, ?, ?, ?, datetime('now'), ?)""",
                (
                    str(d.get("campaign_id") or ""),
                    account_id,
                    d.get("field"),
                    None if d.get("before") is None else str(d.get("before")),
                    None if d.get("after") is None else str(d.get("after")),
                    d.get("source", "external"),
                ),
            )
        await db.commit()
    finally:
        await db.close()

    # Push an SSE nudge so the frontend AgentActivity feed invalidates + refetches.
    try:
        from app.services import account_events

        account_events.publish(
            account_id,
            {"type": "external_change", "count": len(diffs)},
        )
    except Exception as e:  # pragma: no cover — never let the emit break the write
        logger.warning("external_change SSE publish failed for %s: %s", account_id, e)

    return len(diffs)


async def list_external_changes(account_id: str, limit: int = 20) -> list[dict]:
    """Newest-first external-change rows for an account (AgentActivity feed).

    Returns [] (and creates the table if needed) when there are none — never
    500s on a fresh account that has never had a detected change.
    """
    from app.database import get_db

    db = await get_db()
    try:
        await _ensure_table(db)
        cur = await db.execute(
            """SELECT id, campaign_id, account_id, field, before, after,
                      detected_at, source
               FROM external_change
               WHERE account_id = ?
               ORDER BY datetime(detected_at) DESC, id DESC
               LIMIT ?""",
            (account_id, limit),
        )
        return [dict(r) for r in await cur.fetchall()]
    finally:
        await db.close()


def _norm(v) -> str:
    """Normalise a field value for comparison: None/'' collapse to '', everything
    else str()'d and stripped, so 'ENABLED' == ' ENABLED ' and 100 == '100'."""
    if v is None:
        return ""
    return str(v).strip()


async def diff_and_record(
    account_id: str, before_rows: dict, after_rows: dict
) -> list[dict]:
    """Compare pre-sync vs post-sync roster values and record the diffs.

    `before_rows` / `after_rows`: {campaign_id -> {status, bidding_strategy,
    budget_micros}}. For every campaign present in BOTH snapshots, any of the
    three tracked fields whose (normalised) value changed becomes an
    `external_change` row with source='external'. Campaigns that are brand-new
    (only in `after`) are NOT diffs — a first appearance isn't a "change" — and
    campaigns that vanished (only in `before`) are skipped too (removal is a
    roster concern, not a field change).

    NOTE (attribution follow-up): v1 records ALL detected diffs as 'external'.
    A future pass should cross-reference app-side plans/operations (change_event
    attribution) and skip diffs the app itself caused. Roster-diff rows are the
    C5 deliverable; attribution is the deferred bonus (plan risk #6).

    Returns the list of diff dicts that were recorded (also useful for tests).
    """
    diffs: list[dict] = []
    for cid, before in before_rows.items():
        after = after_rows.get(cid)
        if after is None:
            continue  # campaign no longer in the roster — not a field change
        for field in _TRACKED_FIELDS:
            b = _norm(before.get(field))
            a = _norm(after.get(field))
            if b != a:
                diffs.append(
                    {
                        "campaign_id": cid,
                        "field": field,
                        "before": before.get(field),
                        "after": after.get(field),
                        "source": "external",
                    }
                )
    if diffs:
        await record_external_changes(account_id, diffs)
    return diffs
