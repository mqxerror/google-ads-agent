"""Creative-copy job store — DB-row job lifecycle (Epic 15, story 15.3).

The draft jobs that used to live in per-router IN-MEMORY dicts (`_dg_draft_jobs`
in demand_gen.py, `_draft_jobs` in pmax.py) are now ``creative_jobs`` DB rows
from birth (fence F6 — job state has no memory home). A backend restart therefore
yields a recoverable ``interrupted`` status (swept at boot by
``database.sweep_interrupted_creative_jobs``), never a 404 — and the persisted
``request_json`` lets the wizard offer a one-click re-run (Honesty Ledger #4:
restart survival is NOT mid-LLM resume; the Claude CLI subprocess dies with the
process).

This module is the STORE ONLY in P1. The unified ``[{text, angle, tier}]``
copy-jobs contract + endpoints arrive in Epic 16 (story 16.1); the storage layer
lands here first so both draft routes stop keeping job state in memory.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from app.database import get_db


async def create_job(
    kind: str,
    account_id: str,
    campaign_type: str,
    request: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a new ``running`` job row and return its id. ``kind`` in
    {'draft', 'rewrite_row', 'diversify'}; ``request`` is persisted verbatim so
    an interrupted job can be re-run one-click."""
    job_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO creative_jobs (id, kind, account_id, campaign_type, status, request_json) "
            "VALUES (?, ?, ?, ?, 'running', ?)",
            (job_id, kind, account_id, campaign_type,
             json.dumps(request) if request is not None else None),
        )
        await db.commit()
    finally:
        await db.close()
    return job_id


async def complete_job(job_id: str, result: Dict[str, Any]) -> None:
    """Mark a job ``done`` with its result payload."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE creative_jobs SET status='done', result_json=?, error_message=NULL, "
            "updated_at=datetime('now') WHERE id=?",
            (json.dumps(result), job_id),
        )
        await db.commit()
    finally:
        await db.close()


async def fail_job(job_id: str, message: str) -> None:
    """Mark a job ``error`` with a message."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE creative_jobs SET status='error', error_message=?, "
            "updated_at=datetime('now') WHERE id=?",
            (message, job_id),
        )
        await db.commit()
    finally:
        await db.close()


def _loads(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return the poll-shape dict for a job, or ``None`` if it never existed.

    Shape is backward-compatible with the old in-memory poll (the wizard reads
    ``status`` + ``result`` / ``message`` unchanged):
      - running     → ``{"status": "running"}``
      - done        → ``{"status": "done", "result": {...}}``
      - error       → ``{"status": "error", "message": "..."}``
      - interrupted → ``{"status": "interrupted", "message": ..., "request": {...}}``
        (a restart killed the in-flight job; the wizard offers one-click re-run)
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT kind, campaign_type, status, request_json, result_json, error_message "
            "FROM creative_jobs WHERE id=?",
            (job_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        return None
    status = row["status"]
    out: Dict[str, Any] = {"status": status, "kind": row["kind"],
                           "campaign_type": row["campaign_type"]}
    if status == "done":
        out["result"] = _loads(row["result_json"]) or {}
    elif status == "error":
        out["message"] = row["error_message"] or "draft failed"
    elif status == "interrupted":
        out["message"] = "Draft was interrupted by a backend restart — re-run it."
        out["request"] = _loads(row["request_json"])
    return out
