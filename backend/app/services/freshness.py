"""Freshness envelope (Dashboard v2.1 — Epic A, A3 backend).

A single async helper that reads the `sync_state` ledger and returns a small,
UI-ready dict describing how fresh an account's data is for a given domain
(default 'metrics'). Every dashboard read attaches this so the operator can tell
at a glance whether the numbers are fresh, still syncing, stale, or erroring —
instead of trusting silently-stale figures.

State machine (evaluated top-down):
  - 'syncing' : a sync is in progress right now (in_progress = 1).
  - 'fresh'   : data_through_date >= yesterday AND last_success_at age < 90 min.
  - 'error'   : there's a recorded failure (consecutive_failures > 0 or a
                last_error) and we're not fresh — detail carries last_error.
  - 'stale'   : anything else, including no ledger row yet ("never checked").

Local SQLite only — no Google Ads call, no LLM.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.database import get_db

# Freshness window: a successful sync older than this (even if the covered date
# is yesterday) is no longer "fresh".
_FRESH_MAX_AGE_MINUTES = 90


def _age_minutes(ts: str | None) -> float | None:
    """Minutes since an ISO/SQLite timestamp, or None if missing/unparseable."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0


async def compute_freshness(account_id: str, domain: str = "metrics") -> dict:
    """Freshness envelope for one account/domain from the `sync_state` ledger.

    Returns::

        {"account_id", "domain", "state", "data_through_date",
         "last_success_at", "age_minutes", "detail"?}

    `age_minutes` is minutes since `last_success_at` (None if never succeeded).
    `detail` is present only for the 'error' state (the last error string).
    """
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT last_attempt_at, last_success_at, last_error,
                      consecutive_failures, in_progress, data_through_date
               FROM sync_state WHERE account_id = ? AND domain = ?""",
            (account_id, domain),
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    if row is None:
        # Never checked — genuinely stale (distinct from "checked, no data").
        return {
            "account_id": account_id,
            "domain": domain,
            "state": "stale",
            "data_through_date": None,
            "last_success_at": None,
            "age_minutes": None,
        }

    in_progress = bool(row["in_progress"])
    data_through = row["data_through_date"]
    last_success = row["last_success_at"]
    last_error = row["last_error"]
    failures = int(row["consecutive_failures"] or 0)
    age = _age_minutes(last_success)

    env: dict = {
        "account_id": account_id,
        "domain": domain,
        "data_through_date": data_through,
        "last_success_at": last_success,
        "age_minutes": round(age, 1) if age is not None else None,
    }

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if in_progress:
        env["state"] = "syncing"
        return env

    is_covered = bool(data_through) and data_through >= yesterday
    is_recent = age is not None and age < _FRESH_MAX_AGE_MINUTES
    if is_covered and is_recent:
        env["state"] = "fresh"
        return env

    if failures > 0 or last_error:
        env["state"] = "error"
        env["detail"] = last_error
        return env

    env["state"] = "stale"
    return env
