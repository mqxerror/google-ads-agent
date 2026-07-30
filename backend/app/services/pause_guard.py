"""Working-campaign pause protection (2026-07-27 incident fix).

The incident: a user typed "pause this campaign" in a chat bound to the wrong
conversation; the Director seat treated the plain text as explicit owner
approval and paused MapleRoots (23847913167) — a live campaign converting at
~$57 CPA. It sat dark ~50 hours (~5 lost leads) before anyone noticed. The
user's requirement, verbatim: "a working campaign i will never stop, the pause
should be protected in my UI".

The fix (this module) is enforced at the ONE backend chokepoint every path
crosses — ``CampaignScopeMiddleware.on_call_tool`` in ``google_ads/mcp_main.py``
(chat persona seats, direct MCP tool calls, and the scheduler ALL spawn a Claude
CLI that mounts that MCP server). A status change to ``PAUSED`` or ``REMOVED`` on
a WORKING campaign is BLOCKED unless the call carries a valid, unconsumed
confirmation grant. Chat text ("pause this", "yes", "approved") can NEVER mint a
grant — only an explicit click on the UI confirm card can (POST
``/api/pause-confirmations``). Enabling a campaign is never gated (recovery must
stay easy). Non-working campaigns pause without friction, as before.

Definition of WORKING (hard-coded contract — no config knob):
    >= 1 conversion in the last 7 days  OR  cost >= $100 in the last 7 days.
Evaluated with a LIVE GAQL pull at gate time, and **fail-closed**: if the stats
lookup errors, the campaign is treated as working (so we block rather than risk
killing a converter on a transient API blip).

Grant lifecycle: mint (UI confirm) -> consume-once (chokepoint) -> gone. Grants
carry a short TTL and are scoped to exactly one (campaign_id, action).
"""

from __future__ import annotations

import logging
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Contract constants (hard-coded on purpose — NOT env/config knobs) ─────────
PAUSE_REMOVE_STATUSES = frozenset({"PAUSED", "REMOVED"})
WORKING_MIN_CONVERSIONS = 1.0            # >= 1 conversion in last 7 days
WORKING_MIN_COST_MICROS = 100_000_000    # >= $100 in last 7 days (micros)
GRANT_TTL_SECONDS = 600                  # 10 min — one confirm → one re-issue

# The canonical (drift-proof) tool name of the campaign-level status writer. The
# only registered tool that can set a campaign's status; ad-group / ad status
# writers are a different lane and out of scope for this gate.
_CAMPAIGN_STATUS_TOOL = "campaign_update_campaign"

_DIGITS = re.compile(r"\D+")


# ── Grant table (mirrors change_capture's stdlib-sqlite pattern) ──────────────
# Created by migration V26 AND best-effort here, because the MCP server process
# consuming grants has no aiosqlite event loop of the app's.
_GRANT_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS pause_confirmation_grants (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    campaign_id TEXT NOT NULL,
    action TEXT NOT NULL,
    campaign_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    consumed_at TEXT
)
"""
_GRANT_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_pause_grants_lookup "
    "ON pause_confirmation_grants(campaign_id, action, consumed_at)"
)


def _db_path() -> str:
    from app.config import settings  # lazy — keeps import cheap for the MCP proc

    return str(settings.database_path)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ── Tool-call detection ───────────────────────────────────────────────────────
def is_campaign_pause_or_remove(
    tool_name: str, args: dict[str, Any] | None
) -> Optional[tuple[str, str, str]]:
    """Return ``(customer_id, campaign_id, action)`` when ``tool_name`` is the
    campaign status writer AND it is setting status to PAUSED/REMOVED on a
    concrete campaign; ``None`` otherwise (including ENABLE — never gated).

    Uses the shared canonicalizer so single-vs-double-underscore / case drift on
    the mounted tool name can never silently bypass the gate.
    """
    from google_ads.tool_registry import canonical_tool_name

    if canonical_tool_name(tool_name) != _CAMPAIGN_STATUS_TOOL:
        return None
    args = args or {}
    status = str(args.get("status") or "").strip().upper()
    if status not in PAUSE_REMOVE_STATUSES:
        return None
    campaign_id = str(args.get("campaign_id") or "").strip()
    if not campaign_id:
        return None
    customer_id = str(args.get("customer_id") or "").strip()
    return (customer_id, campaign_id, status)


# ── Live "working?" check (GAQL, fail-closed) ─────────────────────────────────
def _run_gaql(customer_id: str, query: str) -> list[Any]:
    """Execute a GAQL query and return the row list. Isolated so tests can
    monkeypatch it without touching the Google Ads SDK."""
    from google_ads.sdk_client import get_sdk_client

    ga = get_sdk_client().client.get_service("GoogleAdsService")
    return list(ga.search(customer_id=_DIGITS.sub("", customer_id), query=query))


def campaign_working_stats(customer_id: str, campaign_id: str) -> dict[str, Any]:
    """Live last-7-day stats + a WORKING verdict for one campaign.

    Returns a dict with: ``name``, ``cost`` (dollars), ``conversions``, ``cpa``
    (dollars or None), ``working`` (bool), ``lookup_ok`` (bool).

    Fail-closed: any error running the lookup yields ``working=True`` with
    ``lookup_ok=False`` — a transient API blip must never let a converter die.
    """
    query = (
        "SELECT campaign.name, metrics.conversions, metrics.cost_micros "
        "FROM campaign "
        f"WHERE campaign.id = {int(re.sub(r'[^0-9]', '', campaign_id) or 0)} "
        "AND segments.date DURING LAST_7_DAYS"
    )
    try:
        rows = _run_gaql(customer_id, query)
    except Exception as exc:  # noqa: BLE001 — fail closed
        logger.warning(
            "pause_guard: stats lookup failed for campaign %s (fail-closed → "
            "treated as WORKING): %s",
            campaign_id, exc,
        )
        return {
            "name": None,
            "cost": None,
            "conversions": None,
            "cpa": None,
            "working": True,
            "lookup_ok": False,
        }

    name: Optional[str] = None
    total_conv = 0.0
    total_cost_micros = 0
    for r in rows:
        camp = getattr(r, "campaign", None)
        if name is None and camp is not None:
            name = getattr(camp, "name", None) or None
        m = getattr(r, "metrics", None)
        if m is not None:
            total_conv += float(getattr(m, "conversions", 0) or 0)
            total_cost_micros += int(getattr(m, "cost_micros", 0) or 0)

    working = (
        total_conv >= WORKING_MIN_CONVERSIONS
        or total_cost_micros >= WORKING_MIN_COST_MICROS
    )
    cost = round(total_cost_micros / 1_000_000, 2)
    cpa = round((total_cost_micros / 1_000_000) / total_conv, 2) if total_conv > 0 else None
    return {
        "name": name,
        "cost": cost,
        "conversions": round(total_conv, 1),
        "cpa": cpa,
        "working": working,
        "lookup_ok": True,
    }


# ── Grants: mint (UI) + consume-once (chokepoint) ─────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=5.0)
    conn.execute(_GRANT_CREATE_SQL)
    conn.execute(_GRANT_INDEX_SQL)
    return conn


def mint_grant(
    customer_id: str,
    campaign_id: str,
    action: str,
    *,
    campaign_name: str | None = None,
    ttl_seconds: int = GRANT_TTL_SECONDS,
) -> dict[str, Any]:
    """Create a one-shot, short-TTL grant that authorizes exactly one PAUSE/REMOVE
    of exactly one campaign. Minted ONLY by the UI confirm endpoint."""
    action = action.strip().upper()
    if action not in PAUSE_REMOVE_STATUSES:
        raise ValueError(f"action must be one of {sorted(PAUSE_REMOVE_STATUSES)}")
    token = "pg_" + secrets.token_hex(16)
    now = _now()
    expires = now + timedelta(seconds=ttl_seconds)
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO pause_confirmation_grants "
            "(id, customer_id, campaign_id, action, campaign_name, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token, str(customer_id or ""), str(campaign_id), action,
             campaign_name, _iso(now), _iso(expires)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"token": token, "campaign_id": str(campaign_id), "action": action,
            "expires_at": _iso(expires)}


def consume_grant(campaign_id: str, action: str) -> bool:
    """Atomically claim the newest valid (unconsumed, unexpired) grant for
    exactly ``(campaign_id, action)``. Returns True if one was consumed (call is
    authorized), False otherwise. Consume-once: a claimed grant can never
    authorize a second write."""
    action = str(action or "").strip().upper()
    now_iso = _iso(_now())
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT id FROM pause_confirmation_grants "
            "WHERE campaign_id = ? AND action = ? AND consumed_at IS NULL "
            "AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
            (str(campaign_id), action, now_iso),
        )
        row = cur.fetchone()
        if not row:
            return False
        grant_id = row[0]
        # Guard the UPDATE with consumed_at IS NULL so a race can only consume
        # once (rowcount 0 means another consumer beat us to it).
        upd = conn.execute(
            "UPDATE pause_confirmation_grants SET consumed_at = ? "
            "WHERE id = ? AND consumed_at IS NULL",
            (now_iso, grant_id),
        )
        conn.commit()
        return upd.rowcount == 1
    finally:
        conn.close()


# ── Confirmation payload (rendered as the UI confirm card) ────────────────────
def build_confirmation_payload(
    customer_id: str, campaign_id: str, action: str, stats: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "pause_confirmation",
        "campaign_id": str(campaign_id),
        "customer_id": str(customer_id or ""),
        "campaign_name": stats.get("name") or f"Campaign {campaign_id}",
        "action": action,
        "cost": stats.get("cost"),
        "conversions": stats.get("conversions"),
        "cpa": stats.get("cpa"),
        "lookup_ok": bool(stats.get("lookup_ok", True)),
    }


# ── The gate the middleware calls ─────────────────────────────────────────────
def check_and_gate(tool_name: str, args: dict[str, Any] | None) -> Optional[dict[str, Any]]:
    """The single decision the chokepoint asks. Returns:
      * ``None``  → allow the tool call (not a pause/remove, non-working
                    campaign, or a valid grant was present and consumed).
      * a payload dict → BLOCK; the middleware raises it as CONFIRMATION_REQUIRED
                    so the chat UI renders the confirm card.

    Never raises: any error while gating a REAL pause/remove fails CLOSED (block),
    honoring the "working campaign is protected" invariant. Non-pause tool calls
    return None immediately and are never affected by a bug in here.
    """
    detected = is_campaign_pause_or_remove(tool_name, args)
    if detected is None:
        return None
    customer_id, campaign_id, action = detected
    try:
        stats = campaign_working_stats(customer_id, campaign_id)
        if not stats.get("working"):
            return None  # non-working campaign — pause freely, as before
        # Working campaign: only a UI-minted, one-shot grant authorizes it.
        if consume_grant(campaign_id, action):
            logger.info(
                "pause_guard: consumed a confirmation grant for campaign %s "
                "action %s — authorizing the %s.",
                campaign_id, action, action,
            )
            return None
        logger.warning(
            "pause_guard: BLOCKED %s of WORKING campaign %s (%s) — no confirmation "
            "grant. Awaiting an explicit UI confirm.",
            action, campaign_id, stats.get("name"),
        )
        return build_confirmation_payload(customer_id, campaign_id, action, stats)
    except Exception as exc:  # noqa: BLE001 — fail closed for a real pause/remove
        logger.error(
            "pause_guard: gating error for campaign %s action %s — failing CLOSED "
            "(blocking): %s",
            campaign_id, action, exc,
        )
        return build_confirmation_payload(
            customer_id, campaign_id, action,
            {"name": None, "cost": None, "conversions": None, "cpa": None,
             "working": True, "lookup_ok": False},
        )
