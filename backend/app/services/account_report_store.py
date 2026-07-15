"""Account report store — latest-wins persistence + O(1) read (Story 13.2).

The workflow orchestrator (Story 13.1) emits a normalized `account_report`
for every account-mode run:

    {
      "mode": "account",
      "findings": [{title, campaign_ids, evidence, dollar_impact_wk,
                    action_category, recommended_action}],
      "total_recoverable_wk": float,
      "summary": str,
      "campaigns_audited": [{campaign_id, campaign_name, spend}],
      "campaigns_excluded": [{campaign_id, campaign_name, spend, reason}],
      "parse_ok": bool,
    }

This module persists it as THE latest report for the account (UPSERT on
account_id → the `account_reports` V19 table) and reads it back for the
homepage in a single indexed lookup — zero Google Ads calls, zero agent runs.

Story 13.3 will consume the persisted `findings` to build approvable actions;
the read shape below carries every field a finding needs (title,
campaign_ids, dollar_impact_wk, action_category, recommended_action) plus the
source `run_id` so a finding can be traced to its audit.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


def _stale_hours() -> float:
    try:
        return float(getattr(settings, "ACCOUNT_REPORT_STALE_HOURS", 0) or 24.0)
    except (TypeError, ValueError):
        return 24.0


async def save_latest(account_id: str, run_id: str, report: dict) -> None:
    """Persist `report` as the latest account report for `account_id`.

    Latest-wins: one row per account, UPSERT on the account_id primary key so
    the newest run always overwrites the slot the homepage reads. The full
    normalized report is stored as JSON; the scalar columns exist so the read
    (and any future filtering / sorting) never has to parse the blob.
    """
    if not account_id:
        return
    findings = report.get("findings") if isinstance(report, dict) else None
    audited = report.get("campaigns_audited") if isinstance(report, dict) else None
    excluded = report.get("campaigns_excluded") if isinstance(report, dict) else None
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO account_reports
                (account_id, run_id, findings_json, total_recoverable_wk,
                 campaigns_audited, campaigns_excluded, parse_ok, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(account_id) DO UPDATE SET
                run_id               = excluded.run_id,
                findings_json        = excluded.findings_json,
                total_recoverable_wk = excluded.total_recoverable_wk,
                campaigns_audited    = excluded.campaigns_audited,
                campaigns_excluded   = excluded.campaigns_excluded,
                parse_ok             = excluded.parse_ok,
                generated_at         = excluded.generated_at
            """,
            (
                account_id,
                run_id,
                json.dumps(report),
                float(report.get("total_recoverable_wk") or 0.0),
                len(audited) if isinstance(audited, list) else 0,
                len(excluded) if isinstance(excluded, list) else 0,
                1 if report.get("parse_ok") else 0,
            ),
        )
        await db.commit()
    finally:
        await db.close()


def _empty_report(account_id: str) -> dict:
    """The zero-state payload the homepage collapses when no audit exists yet.
    A valid-but-empty shape — never null, so the client renders the calm
    'no audit yet' state instead of erroring."""
    return {
        "account_id": account_id,
        "exists": False,
        "mode": "account",
        "run_id": None,
        "findings": [],
        "total_recoverable_wk": 0.0,
        "summary": "",
        "campaigns_audited": [],
        "campaigns_excluded": [],
        "parse_ok": False,
        "generated_at": None,
        "age_minutes": None,
        "age_hours": None,
        "is_stale": True,          # nothing there → treat as stale (prompt a run)
        "stale_after_hours": _stale_hours(),
    }


def _age(generated_at: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """(age_minutes, age_hours) for a SQLite 'YYYY-MM-DD HH:MM:SS' UTC stamp."""
    if not generated_at:
        return None, None
    try:
        gen = datetime.fromisoformat(generated_at.replace("Z", "").replace("T", " ").strip())
        gen = gen.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None, None
    delta = (datetime.now(timezone.utc) - gen).total_seconds()
    delta = max(delta, 0.0)
    return round(delta / 60.0, 1), round(delta / 3600.0, 2)


async def get_latest(account_id: str) -> dict:
    """Return the latest account report + staleness metadata.

    Answers from local SQLite in one indexed lookup. When no report exists
    yet, returns the explicit empty-but-valid shape (`exists: False`) so the
    homepage zero-state is a data contract, not a 404.
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT run_id, findings_json, total_recoverable_wk, campaigns_audited, "
            "campaigns_excluded, parse_ok, generated_at "
            "FROM account_reports WHERE account_id = ?",
            (account_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    if not row:
        return _empty_report(account_id)

    try:
        report: dict[str, Any] = json.loads(row["findings_json"])
    except (json.JSONDecodeError, TypeError):
        report = {}
    if not isinstance(report, dict):
        report = {}

    age_min, age_hr = _age(row["generated_at"])
    stale_after = _stale_hours()
    is_stale = age_hr is None or age_hr >= stale_after

    return {
        "account_id": account_id,
        "exists": True,
        "mode": report.get("mode", "account"),
        "run_id": row["run_id"],
        "findings": report.get("findings", []),
        "total_recoverable_wk": report.get("total_recoverable_wk", row["total_recoverable_wk"]),
        "summary": report.get("summary", ""),
        "campaigns_audited": report.get("campaigns_audited", []),
        "campaigns_excluded": report.get("campaigns_excluded", []),
        "parse_ok": bool(row["parse_ok"]),
        "generated_at": row["generated_at"],
        "age_minutes": age_min,
        "age_hours": age_hr,
        "is_stale": is_stale,
        "stale_after_hours": stale_after,
    }
