"""Background sync engine — pulls Google Ads data on a schedule, stores in SQLite.

Data flows: Google Ads API → campaign_daily_metrics table → agent reads from DB.
The agent NEVER hits the API directly during conversation — only this sync engine
does.

READ-ONLY toward Google Ads: every call here is a GAQL SELECT. Nothing in this
module mutates a Google Ads account.

Dashboard v2.1 (Epic A) rewrite: the old per-campaign × per-day loop issued
~lookback × campaigns API calls (a quota bomb) AND wrote ghost columns
(`id`/`metric_date`/`status`) that don't exist on campaign_daily_metrics, so it
always failed silently. This version does ONE account-wide daily-metrics stream
+ ONE roster refresh, writes the REAL columns (`date`, `campaign_status`, …), and
records every attempt in the `sync_state` ledger — the canonical freshness
source for the dashboard.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from app.config import settings
from app.database import get_db
from app.services import campaigns_repo
from app.services.google_ads import GoogleAdsService

logger = logging.getLogger(__name__)

_ads_svc = GoogleAdsService()
_sync_task: asyncio.Task | None = None
_watchdog_task: asyncio.Task | None = None

# The freshness ledger domain this engine owns.
_DOMAIN = "metrics"

# Watchdog / heartbeat config.
_HEARTBEAT_KEY = "sync_heartbeat"
_WATCHDOG_INTERVAL_SECONDS = 60
_PER_ACCOUNT_TIMEOUT_SECONDS = 120
_BACKOFF_CAP_SECONDS = 60 * 60  # 60 min ceiling


# ── sync_state ledger helpers (canonical freshness source) ──────────────


async def _mark_attempt_start(db, account_id: str) -> None:
    """Upsert the ledger row for this attempt: in_progress=1, stamp attempt."""
    await db.execute(
        """INSERT INTO sync_state
               (account_id, domain, last_attempt_at, in_progress)
           VALUES (?, ?, datetime('now'), 1)
           ON CONFLICT(account_id, domain) DO UPDATE SET
               last_attempt_at = datetime('now'),
               in_progress = 1""",
        (account_id, _DOMAIN),
    )
    await db.commit()


async def _mark_success(db, account_id: str, data_through_date: str | None) -> None:
    await db.execute(
        """INSERT INTO sync_state
               (account_id, domain, last_attempt_at, last_success_at,
                data_through_date, consecutive_failures, in_progress, last_error)
           VALUES (?, ?, datetime('now'), datetime('now'), ?, 0, 0, NULL)
           ON CONFLICT(account_id, domain) DO UPDATE SET
               last_success_at = datetime('now'),
               data_through_date = excluded.data_through_date,
               consecutive_failures = 0,
               in_progress = 0,
               last_error = NULL""",
        (account_id, _DOMAIN, data_through_date),
    )
    await db.commit()


async def _mark_failure(db, account_id: str, error: str) -> None:
    await db.execute(
        """INSERT INTO sync_state
               (account_id, domain, last_attempt_at, consecutive_failures,
                in_progress, last_error)
           VALUES (?, ?, datetime('now'), 1, 0, ?)
           ON CONFLICT(account_id, domain) DO UPDATE SET
               consecutive_failures = sync_state.consecutive_failures + 1,
               in_progress = 0,
               last_error = excluded.last_error""",
        (account_id, _DOMAIN, error),
    )
    await db.commit()


# ── Core sync ────────────────────────────────────────────────────────────


async def sync_account(account_id: str, days: int | None = None) -> dict:
    """Pull campaign metrics for an account and store day-by-day snapshots.

    ONE account-wide daily-metrics stream + ONE roster refresh (≤3 API ops
    total, minus none). Writes the REAL campaign_daily_metrics columns and the
    sync_state ledger (start / success / failure). Returns a summary dict.
    """
    lookback = days or settings.SYNC_LOOKBACK_DAYS
    today = date.today()
    date_from = (today - timedelta(days=lookback - 1)).isoformat()
    date_to = today.isoformat()

    # Mark the attempt in the ledger up front (in_progress=1) so the dashboard
    # can show "syncing" even mid-run.
    db = await get_db()
    try:
        await _mark_attempt_start(db, account_id)
    finally:
        await db.close()

    try:
        # 1) Refresh the roster FIRST so new campaigns are known before we
        #    compute the enabled set for zero-rows. Roster sync opens/closes its
        #    own connection (1 API op: get_campaigns).
        try:
            await campaigns_repo.sync_campaigns(account_id)
        except Exception as e:
            logger.warning(
                "Roster refresh failed for %s: %s — continuing with existing roster.",
                account_id, e,
            )

        # 2) ONE account-wide daily-metrics stream (1 API op).
        rows = await _ads_svc.get_campaign_daily_metrics(
            account_id, date_from, date_to
        )
    except Exception as e:
        logger.error("Sync failed to fetch metrics for %s: %s", account_id, e)
        # Open circuit breaker so the read path doesn't also hang.
        import time
        from app.services.cache import CacheService
        CacheService._circuit_open_until = time.time() + 300
        db = await get_db()
        try:
            await _mark_failure(db, account_id, str(e))
            await _update_sync_status(db, account_id, "error", str(e), 0, 0)
        finally:
            await db.close()
        return {"status": "error", "error": str(e)}

    # 3) Batch upsert every returned (campaign, date) row in ONE short
    #    transaction, then zero-fill enabled campaigns for days Google returned
    #    nothing. Keep the connection open only for this write phase.
    written_dates: set[str] = set()
    seen: set[tuple[str, str]] = set()  # (campaign_id, date) actually written
    campaigns_seen: set[str] = set()

    db = await get_db()
    try:
        for r in rows:
            cid = str(r["campaign_id"])
            d_str = str(r["date"])
            impressions = r.get("impressions", 0) or 0
            clicks = r.get("clicks", 0) or 0
            cost_micros = r.get("cost_micros", 0) or 0
            conversions = r.get("conversions", 0.0) or 0.0
            ctr = (clicks / impressions * 100) if impressions else 0.0
            avg_cpc = (cost_micros // clicks) if clicks else 0

            await db.execute(
                """INSERT INTO campaign_daily_metrics
                       (account_id, campaign_id, campaign_name, date,
                        impressions, clicks, cost_micros, conversions, ctr,
                        avg_cpc_micros, campaign_status, bidding_strategy,
                        budget_micros, synced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(account_id, campaign_id, date) DO UPDATE SET
                       campaign_name  = excluded.campaign_name,
                       impressions    = excluded.impressions,
                       clicks         = excluded.clicks,
                       cost_micros    = excluded.cost_micros,
                       conversions    = excluded.conversions,
                       ctr            = excluded.ctr,
                       avg_cpc_micros = excluded.avg_cpc_micros,
                       campaign_status = excluded.campaign_status,
                       bidding_strategy = excluded.bidding_strategy,
                       budget_micros  = excluded.budget_micros,
                       synced_at      = datetime('now')""",
                (
                    account_id, cid, r.get("campaign_name", ""), d_str,
                    impressions, clicks, cost_micros, conversions, ctr,
                    avg_cpc, r.get("campaign_status", ""),
                    r.get("bidding_strategy", ""), r.get("budget_micros", 0) or 0,
                ),
            )
            written_dates.add(d_str)
            seen.add((cid, d_str))
            campaigns_seen.add(cid)
        await db.commit()

        # Zero-fill: for every ENABLED campaign (from the freshly-refreshed
        # roster) on each day in the window that Google returned NO row, insert
        # a zero-row so "checked, no data" != "never checked". ON CONFLICT DO
        # NOTHING keeps real rows intact.
        cur = await db.execute(
            "SELECT campaign_id, name FROM campaigns "
            "WHERE account_id = ? AND status = 'ENABLED'",
            (account_id,),
        )
        enabled = [(str(row["campaign_id"]), row["name"] or "") for row in await cur.fetchall()]

        window_days = [
            (today - timedelta(days=i)).isoformat() for i in range(lookback)
        ]
        for cid, cname in enabled:
            for d_str in window_days:
                if (cid, d_str) in seen:
                    continue
                await db.execute(
                    """INSERT INTO campaign_daily_metrics
                           (account_id, campaign_id, campaign_name, date,
                            campaign_status, synced_at)
                       VALUES (?, ?, ?, ?, 'ENABLED', datetime('now'))
                       ON CONFLICT(account_id, campaign_id, date) DO NOTHING""",
                    (account_id, cid, cname, d_str),
                )
                written_dates.add(d_str)
                campaigns_seen.add(cid)
        await db.commit()

        # data_through_date = MAX(date) actually present for this account.
        cur = await db.execute(
            "SELECT MAX(date) AS mx FROM campaign_daily_metrics WHERE account_id = ?",
            (account_id,),
        )
        row = await cur.fetchone()
        data_through = row["mx"] if row and row["mx"] else None

        days_synced = len(written_dates)
        campaigns_synced = len(campaigns_seen)

        await _mark_success(db, account_id, data_through)
        await _update_sync_status(
            db, account_id, "success", None, campaigns_synced, days_synced
        )
    finally:
        await db.close()

    # Push an SSE `sync_completed` nudge (Epic C / C1) so the dashboard's
    # freshness chip flips to "live" and the KPI/ranked caches invalidate
    # without a reload. Lazy import avoids an import cycle; best-effort — a
    # failed emit must never fail the sync.
    try:
        from app.services import account_events

        account_events.publish(
            account_id,
            {
                "type": "sync_completed",
                "domain": _DOMAIN,
                "data_through_date": data_through,
            },
        )
    except Exception as _e:  # pragma: no cover — defensive
        logger.warning("sync_completed SSE emit failed for %s: %s", account_id, _e)

    logger.info(
        "Sync complete for %s: %d campaigns, %d days, through %s",
        account_id, campaigns_synced, days_synced, data_through,
    )
    return {
        "status": "success",
        "campaigns_synced": campaigns_synced,
        "days_synced": days_synced,
        "data_through_date": data_through,
    }


async def _update_sync_status(
    db, account_id: str, status: str, error: str | None,
    campaigns: int, days: int,
) -> None:
    """Upsert the legacy sync_status row (back-compat). sync_state is canonical."""
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
            """SELECT date, impressions, clicks, cost_micros,
                      conversions, ctr, avg_cpc_micros, budget_micros,
                      bidding_strategy, campaign_status
               FROM campaign_daily_metrics
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY date DESC
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
            """SELECT campaign_id, campaign_name, campaign_status, budget_micros, bidding_strategy,
                      SUM(impressions) as impressions,
                      SUM(clicks) as clicks,
                      SUM(cost_micros) as cost_micros,
                      SUM(conversions) as conversions
               FROM campaign_daily_metrics
               WHERE account_id = ? AND date >= ?
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
            f"""SELECT date, {metric}
                FROM campaign_daily_metrics
                WHERE account_id = ? AND campaign_id = ?
                ORDER BY date DESC
                LIMIT ?""",
            (account_id, campaign_id, days),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ── Self-heal (sync-on-read) ───────────────────────────────────
#
# A read endpoint answers instantly from SQLite, then calls maybe_kick_sync()
# to REPAIR the data in the background if it's stale — the read response is
# NEVER blocked on Google. Guards (all read from the sync_state ledger):
#   • single-flight: skip if in_progress = 1 (a sync is already running);
#   • stampede: skip if last_attempt_at < MIN_INTERVAL min ago (tab spam);
#   • staleness: kick only if data_through_date < yesterday
#     OR last_success_at age > METRICS_HOT_SYNC_MINUTES (or never succeeded).
#
# Returns a small decision dict (kicked/skipped + reason) for observability and
# tests — the DECISION is pure ledger logic; the ACTUAL task is fire-and-forget.


async def _self_heal_decision(account_id: str) -> tuple[bool, str]:
    """Pure decision: should a background refresh be kicked for this account?

    Reads ONLY the sync_state ledger — no Google Ads call. Returns
    (should_kick, reason). Order matters: single-flight and the stampede guard
    short-circuit BEFORE the staleness check so an in-flight or just-attempted
    sync is never re-kicked, even when the data still looks stale.
    """
    from datetime import datetime as _dt, timezone as _tz

    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT last_attempt_at, last_success_at, in_progress,
                      data_through_date
               FROM sync_state WHERE account_id = ? AND domain = ?""",
            (account_id, _DOMAIN),
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    # No ledger row yet → never synced → kick (nothing in flight, no attempt).
    if row is None:
        return True, "never_synced"

    # 1) Single-flight: a sync is already running for this account.
    if row["in_progress"]:
        return False, "in_progress"

    # 2) Stampede guard: an attempt was made very recently (success OR failure).
    #    Blocks tab-storms from looping the sync regardless of staleness.
    min_interval = settings.METRICS_SELF_HEAL_MIN_INTERVAL_MINUTES * 60.0
    last_attempt = row["last_attempt_at"]
    if last_attempt:
        try:
            la = _dt.fromisoformat(last_attempt)
            if la.tzinfo is None:
                la = la.replace(tzinfo=_tz.utc)
            attempt_age = (_dt.now(_tz.utc) - la).total_seconds()
            if attempt_age < min_interval:
                return False, "recent_attempt"
        except (ValueError, TypeError):
            pass  # unparseable stamp → fall through to staleness check

    # 3) Staleness: kick if data doesn't cover yesterday OR the last success is
    #    older than the hot-sync interval (or there's never been a success).
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    data_through = row["data_through_date"]
    if not data_through or data_through < yesterday:
        return True, "data_stale"

    last_success = row["last_success_at"]
    if not last_success:
        return True, "never_succeeded"
    try:
        ls = _dt.fromisoformat(last_success)
        if ls.tzinfo is None:
            ls = ls.replace(tzinfo=_tz.utc)
        success_age_min = (_dt.now(_tz.utc) - ls).total_seconds() / 60.0
        if success_age_min > settings.METRICS_HOT_SYNC_MINUTES:
            return True, "success_aged"
    except (ValueError, TypeError):
        return True, "unparseable_success"

    return False, "fresh"


async def maybe_kick_sync(
    account_id: str, hot_window_days: int | None = None
) -> dict:
    """Self-heal trigger for read endpoints. Decides (via _self_heal_decision)
    whether the account's local data needs a background refresh; if so, fires a
    hot-window sync via asyncio.create_task and returns immediately. The caller's
    read response is NEVER blocked on Google.

    `hot_window_days` scopes how many days the kicked sync pulls (defaults to
    settings.METRICS_HOT_WINDOW_DAYS — the cheap hot window). Returns a decision
    dict: {"kicked": bool, "reason": str}.
    """
    if not settings.SYNC_ENABLED or not account_id:
        return {"kicked": False, "reason": "disabled"}

    should_kick, reason = await _self_heal_decision(account_id)
    if not should_kick:
        return {"kicked": False, "reason": reason}

    days = hot_window_days or settings.METRICS_HOT_WINDOW_DAYS
    # Fire-and-forget: _run_one_account applies the per-account timeout fence and
    # marks the ledger (in_progress set inside sync_account) so a second read
    # arriving mid-run sees in_progress=1 and skips (single-flight).
    asyncio.create_task(_run_one_account_scoped(account_id, days))
    return {"kicked": True, "reason": reason}


async def _run_one_account_scoped(account_id: str, days: int) -> None:
    """Hot-window sync with the same timeout fence + ledger marking as the
    scheduler's _run_one_account, but at an explicit day-scope (self-heal)."""
    try:
        await asyncio.wait_for(
            sync_account(account_id, days=days),
            timeout=_PER_ACCOUNT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Self-heal sync timed out (>%ss) for %s",
            _PER_ACCOUNT_TIMEOUT_SECONDS, account_id,
        )
        db = await get_db()
        try:
            await _mark_failure(db, account_id, "timeout")
        finally:
            await db.close()
    except Exception as e:
        logger.error("Self-heal sync failed for %s: %s", account_id, e)


# ── Background scheduler ───────────────────────────────────────


async def _active_account_ids() -> list[str]:
    """The sync roster: active accounts from accounts_v2 (falls back to the
    login customer id if the roster is empty)."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id FROM accounts_v2 WHERE is_active = 1"
        )
        ids = [r["id"] for r in await cur.fetchall()]
    finally:
        await db.close()
    if not ids:
        login_id = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
        if login_id:
            ids = [login_id]
    return ids


async def _consecutive_failures(account_id: str) -> tuple[int, str | None]:
    """(consecutive_failures, last_attempt_at) from the ledger, for backoff."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT consecutive_failures, last_attempt_at FROM sync_state "
            "WHERE account_id = ? AND domain = ?",
            (account_id, _DOMAIN),
        )
        row = await cur.fetchone()
        if not row:
            return 0, None
        return int(row["consecutive_failures"] or 0), row["last_attempt_at"]
    finally:
        await db.close()


def _backoff_seconds(failures: int) -> float:
    """Exponential backoff (1→2→4→…min) capped at _BACKOFF_CAP_SECONDS."""
    if failures <= 0:
        return 0.0
    return min(2 ** (failures - 1) * 60.0, _BACKOFF_CAP_SECONDS)


async def _should_skip_for_backoff(account_id: str) -> bool:
    """True if this account is inside its exponential backoff window."""
    failures, last_attempt = await _consecutive_failures(account_id)
    if failures <= 0 or not last_attempt:
        return False
    from datetime import datetime, timezone
    try:
        last = datetime.fromisoformat(last_attempt).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed < _backoff_seconds(failures)


async def _write_heartbeat() -> None:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO config (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value, updated_at = datetime('now')""",
            (_HEARTBEAT_KEY, now),
        )
        await db.commit()
    finally:
        await db.close()


async def _run_one_account(account_id: str, full: bool) -> None:
    """Sync one account with a hard timeout + post-sync side-effects."""
    days = (
        settings.METRICS_FULL_SYNC_LOOKBACK if full
        else settings.METRICS_HOT_WINDOW_DAYS
    )
    try:
        await asyncio.wait_for(
            sync_account(account_id, days=days),
            timeout=_PER_ACCOUNT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("Sync timed out (>%ss) for %s", _PER_ACCOUNT_TIMEOUT_SECONDS, account_id)
        db = await get_db()
        try:
            await _mark_failure(db, account_id, "timeout")
        finally:
            await db.close()
        return
    except Exception as e:
        logger.error("Background sync failed for %s: %s", account_id, e)
        return

    # Post-sync side effects (best-effort, never break the loop).
    try:
        from app.services.outcome_tracker import measure_pending_outcomes
        measured = await measure_pending_outcomes(account_id)
        if measured:
            logger.info("Measured %d outcomes for %s", measured, account_id)
    except Exception as oe:
        logger.warning("Outcome measurement failed for %s: %s", account_id, oe)
    try:
        from app.services.skill_optimizer import optimize_all_roles
        opt_results = await optimize_all_roles(account_id)
        optimized = [r for r in opt_results if r.get("status") == "optimized"]
        if optimized:
            logger.info("Optimized %d role skills for %s", len(optimized), account_id)
    except Exception as se:
        logger.warning("Skill optimization failed for %s: %s", account_id, se)


async def _sync_loop():
    """Runs in background, syncs all active accounts on a hot cadence, with a
    daily full re-pull for conversion-lag restatement. Per-account exponential
    backoff, per-account timeout, and a heartbeat each cycle."""
    from datetime import date as _date
    interval = settings.METRICS_HOT_SYNC_MINUTES * 60
    last_full_day: str | None = None

    while True:
        try:
            await _write_heartbeat()

            today_str = _date.today().isoformat()
            do_full = last_full_day != today_str

            account_ids = await _active_account_ids()
            for account_id in account_ids:
                # Full re-pull runs regardless of backoff (it's the daily
                # restatement); hot syncs respect the backoff window.
                if not do_full and await _should_skip_for_backoff(account_id):
                    logger.info("Skipping %s this cycle (backoff)", account_id)
                    continue
                await _run_one_account(account_id, full=do_full)

            if do_full:
                last_full_day = today_str

        except Exception as e:
            logger.error("Background sync loop error: %s", e)

        await asyncio.sleep(interval)


async def _boot_sync():
    """Kick an immediate sync for every active account on startup."""
    try:
        account_ids = await _active_account_ids()
        for account_id in account_ids:
            await _run_one_account(account_id, full=True)
    except Exception as e:
        logger.error("Boot sync error: %s", e)


async def _watchdog_loop():
    """Restart the sync task if it dies; log a stalled heartbeat."""
    from datetime import datetime, timezone
    while True:
        await asyncio.sleep(_WATCHDOG_INTERVAL_SECONDS)
        try:
            global _sync_task
            if _sync_task is None or _sync_task.done():
                logger.warning("Sync task not running — restarting.")
                _sync_task = asyncio.create_task(_sync_loop())

            # Heartbeat staleness check.
            db = await get_db()
            try:
                cur = await db.execute(
                    "SELECT value FROM config WHERE key = ?", (_HEARTBEAT_KEY,)
                )
                row = await cur.fetchone()
            finally:
                await db.close()
            if row and row["value"]:
                try:
                    hb = datetime.fromisoformat(row["value"])
                    if hb.tzinfo is None:
                        hb = hb.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - hb).total_seconds()
                    if age > 2 * settings.METRICS_HOT_SYNC_MINUTES * 60:
                        logger.warning(
                            "Sync heartbeat stale (%.0fs old) — loop may be wedged.", age
                        )
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            logger.warning("Sync watchdog error: %s", e)


def start_background_sync():
    """Start the background sync loop + watchdog. Call once at app startup."""
    global _sync_task, _watchdog_task
    if not settings.SYNC_ENABLED:
        logger.info("Background sync disabled")
        return
    if _sync_task is None or _sync_task.done():
        _sync_task = asyncio.create_task(_sync_loop())
    if _watchdog_task is None or _watchdog_task.done():
        _watchdog_task = asyncio.create_task(_watchdog_loop())
    # Kick an immediate boot sync so the dashboard isn't empty on cold start.
    asyncio.create_task(_boot_sync())
    logger.info(
        "Background sync started (hot: %dmin/%dd, full: %dd daily)",
        settings.METRICS_HOT_SYNC_MINUTES,
        settings.METRICS_HOT_WINDOW_DAYS,
        settings.METRICS_FULL_SYNC_LOOKBACK,
    )


def stop_background_sync():
    """Stop the background sync loop + watchdog."""
    global _sync_task, _watchdog_task
    if _sync_task:
        _sync_task.cancel()
        _sync_task = None
    if _watchdog_task:
        _watchdog_task.cancel()
        _watchdog_task = None
    logger.info("Background sync stopped")
