"""Local metrics store — syncs daily campaign data from Google Ads to SQLite.

The agent reads from this local store instead of making live API calls,
cutting response time from seconds to milliseconds and saving API quota.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.database import get_db

logger = logging.getLogger(__name__)


class MetricsStore:
    """Read/write daily campaign metrics from local SQLite."""

    # ── Write: Sync from API ──────────────────────────────────

    async def sync_campaigns(
        self, account_id: str, campaigns: list[dict], metrics_date: str | None = None
    ) -> int:
        """Store campaign-level daily metrics.

        Args:
            account_id: Google Ads client account ID
            campaigns: List of campaign dicts with metrics (from GoogleAdsService)
            metrics_date: Date for these metrics (default: date range from data)

        Returns:
            Number of rows upserted.
        """
        if not campaigns:
            return 0

        db = await get_db()
        count = 0
        try:
            for c in campaigns:
                d = metrics_date or date.today().isoformat()
                await db.execute(
                    """INSERT OR REPLACE INTO campaign_daily_metrics
                       (account_id, campaign_id, campaign_name, date,
                        impressions, clicks, cost_micros, conversions, ctr, avg_cpc_micros,
                        campaign_status, bidding_strategy, budget_micros, synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (
                        account_id,
                        c.get("id") or c.get("campaign_id", ""),
                        c.get("name") or c.get("campaign_name", ""),
                        d,
                        c.get("impressions", 0),
                        c.get("clicks", 0),
                        c.get("cost_micros", 0),
                        c.get("conversions", 0),
                        c.get("ctr", 0),
                        c.get("avg_cpc_micros", 0),
                        c.get("status", ""),
                        c.get("bidding_strategy", ""),
                        c.get("budget_micros", 0),
                    ),
                )
                count += 1
            await db.commit()
        finally:
            await db.close()
        return count

    async def sync_daily_metrics(
        self, account_id: str, daily_data: list[dict], campaign_id: str, campaign_name: str = ""
    ) -> int:
        """Store day-by-day metrics for a single campaign (from chart endpoint)."""
        if not daily_data:
            return 0

        db = await get_db()
        count = 0
        try:
            for d in daily_data:
                # INSERT OR REPLACE would blow away campaign_status /
                # bidding_strategy / budget_micros (this chart path doesn't carry
                # them) — RC-5 corruption. Upsert ONLY the metric columns
                # (+ campaign_name if provided) so metadata written by the sync
                # engine survives a chart refresh.
                await db.execute(
                    """INSERT INTO campaign_daily_metrics
                       (account_id, campaign_id, campaign_name, date,
                        impressions, clicks, cost_micros, conversions, ctr, avg_cpc_micros,
                        synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                       ON CONFLICT(account_id, campaign_id, date) DO UPDATE SET
                           campaign_name = COALESCE(NULLIF(excluded.campaign_name, ''), campaign_daily_metrics.campaign_name),
                           impressions    = excluded.impressions,
                           clicks         = excluded.clicks,
                           cost_micros    = excluded.cost_micros,
                           conversions    = excluded.conversions,
                           ctr            = excluded.ctr,
                           avg_cpc_micros = excluded.avg_cpc_micros,
                           synced_at      = datetime('now')""",
                    (
                        account_id,
                        campaign_id,
                        campaign_name,
                        d["date"],
                        d.get("impressions", 0),
                        d.get("clicks", 0),
                        int(d.get("cost", 0) * 1_000_000),
                        d.get("conversions", 0),
                        d.get("ctr", 0),
                        int(d.get("cpc", 0) * 1_000_000) if d.get("cpc") else 0,
                    ),
                )
                count += 1
            await db.commit()
        finally:
            await db.close()
        return count

    # ── Read: Fast local queries for agent ─────────────────────

    async def get_campaign_history(
        self, account_id: str, campaign_id: str, days: int = 30
    ) -> list[dict]:
        """Get daily metrics for a campaign from local store."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        db = await get_db()
        try:
            cur = await db.execute(
                """SELECT date, impressions, clicks, cost_micros, conversions, ctr,
                          avg_cpc_micros, campaign_status, bidding_strategy, budget_micros
                   FROM campaign_daily_metrics
                   WHERE account_id = ? AND campaign_id = ? AND date >= ?
                   ORDER BY date ASC""",
                (account_id, campaign_id, cutoff),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def get_account_summary(
        self, account_id: str, days: int = 7
    ) -> list[dict]:
        """Get per-campaign summary for last N days from local store."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        db = await get_db()
        try:
            cur = await db.execute(
                """SELECT campaign_id, campaign_name, campaign_status, bidding_strategy, budget_micros,
                          SUM(impressions) as impressions,
                          SUM(clicks) as clicks,
                          SUM(cost_micros) as cost_micros,
                          SUM(conversions) as conversions,
                          MAX(date) as last_date
                   FROM campaign_daily_metrics
                   WHERE account_id = ? AND date >= ?
                   GROUP BY campaign_id
                   ORDER BY cost_micros DESC""",
                (account_id, cutoff),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def get_recent_daily(
        self, account_id: str, campaign_id: str, days: int = 7
    ) -> list[dict]:
        """Get last N days of daily data for the agent's Layer 5."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        db = await get_db()
        try:
            cur = await db.execute(
                """SELECT date, impressions, clicks, cost_micros, conversions
                   FROM campaign_daily_metrics
                   WHERE account_id = ? AND campaign_id = ? AND date >= ?
                   ORDER BY date DESC""",
                (account_id, campaign_id, cutoff),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def has_recent_data(self, account_id: str, days: int = 1) -> bool:
        """Check if we have data from the last N days."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        db = await get_db()
        try:
            cur = await db.execute(
                "SELECT 1 FROM campaign_daily_metrics WHERE account_id = ? AND date >= ? LIMIT 1",
                (account_id, cutoff),
            )
            return bool(await cur.fetchone())
        finally:
            await db.close()

    async def _as_of_header(
        self, account_id: str, campaign_id: str | None
    ) -> str:
        """One-line LIVE-TRUTH context header for the agent (B4 / PART 2).

        Status/bidding are read from the `campaigns` roster (fresh source of
        truth), and the metrics data-through date from the `sync_state` ledger
        (domain='metrics'). Never a live Google Ads call — both are local reads.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        roster_status = roster_bidding = roster_synced = None
        data_through = None
        db = await get_db()
        try:
            if campaign_id:
                cur = await db.execute(
                    """SELECT status, bidding_strategy, last_synced_at
                       FROM campaigns
                       WHERE account_id = ? AND campaign_id = ?""",
                    (account_id, str(campaign_id)),
                )
                r = await cur.fetchone()
                if r is not None:
                    roster_status = r["status"]
                    roster_bidding = r["bidding_strategy"]
                    roster_synced = r["last_synced_at"]
            cur = await db.execute(
                """SELECT data_through_date FROM sync_state
                   WHERE account_id = ? AND domain = 'metrics'""",
                (account_id,),
            )
            sr = await cur.fetchone()
            if sr is not None:
                data_through = sr["data_through_date"]
        finally:
            await db.close()

        if campaign_id and (roster_status or roster_bidding):
            roster_bits = (
                f"status {roster_status or '—'} / bidding {roster_bidding or '—'} "
                f"from roster (synced {roster_synced or 'never'})"
            )
        else:
            roster_bits = "status/bidding from roster"
        through = data_through or "no data yet"
        return (
            f"=== AS OF {now} ===\n"
            f"Live control-plane truth: {roster_bits}. "
            f"Metrics data through {through} (analytics below reflect that "
            f"window; Google restates conversions for several days)."
        )

    async def format_for_agent(
        self, account_id: str, campaign_id: str | None, campaign_name: str | None
    ) -> str:
        """Generate Layer 5 context from local data + live supplemental data.

        Includes: daily metrics, ad groups, keywords, search terms — everything
        the agent needs so it doesn't have to make separate API calls.
        """
        from app.services.google_ads import GoogleAdsService
        from app.services.cache import CacheService

        parts = []
        _cache = CacheService()

        # ── LIVE-TRUTH as-of header (Dashboard v2.1, B4 / PART 2) ────────
        # Prepend one honest line so the agent stops confidently citing stale
        # control-plane state: status/bidding come from the `campaigns` roster
        # (the fresh ≤5-min single source of truth), and we note how far the
        # local METRICS data actually reaches (sync_state.data_through_date) so
        # analytics figures below are read with the right as-of in mind.
        try:
            parts.append(await self._as_of_header(account_id, campaign_id))
        except Exception:
            pass

        if campaign_id:
            # Day-by-day for selected campaign (from local store — instant)
            daily = await self.get_recent_daily(account_id, campaign_id, days=14)
            if daily:
                parts.append("=== DAY-BY-DAY PERFORMANCE (last 14 days) ===")
                parts.append(f"{'Date':<12} {'Impr':>6} {'Clicks':>7} {'Cost':>10} {'Conv':>5} {'CTR':>7} {'CPC':>8}")
                parts.append("-" * 62)
                for d in reversed(daily):
                    cost = d["cost_micros"] / 1_000_000
                    clicks = d["clicks"]
                    impr = d["impressions"]
                    conv = d["conversions"]
                    ctr = clicks / impr * 100 if impr > 0 else 0
                    cpc = cost / clicks if clicks > 0 else 0
                    parts.append(
                        f"{d['date']:<12} {impr:>6} {clicks:>7} ${cost:>8.2f} {conv:>5.0f} {ctr:>6.1f}% ${cpc:>6.2f}"
                    )

            # Ad groups (from cache — no API call if cached)
            try:
                ads_svc = GoogleAdsService()
                adgroups = await _cache.get_or_fetch(
                    f"{account_id}:{campaign_id}:adgroups",
                    lambda: ads_svc.get_adgroups(account_id, campaign_id),
                    ttl=300,
                )
                if adgroups:
                    parts.append(f"\n=== AD GROUPS ({len(adgroups)}) — id | name | status | clicks | cost | conv ===")
                    for ag in adgroups:
                        agid = ag.id if hasattr(ag, 'id') else ag.get('id', '')
                        name = ag.name if hasattr(ag, 'name') else ag.get('name', '')
                        status = ag.status if hasattr(ag, 'status') else ag.get('status', '')
                        m = ag.metrics if hasattr(ag, 'metrics') else ag.get('metrics', {})
                        clicks = m.clicks if hasattr(m, 'clicks') else m.get('clicks', 0)
                        conv = m.conversions if hasattr(m, 'conversions') else m.get('conversions', 0)
                        cost_m = m.cost_micros if hasattr(m, 'cost_micros') else m.get('cost_micros', 0)
                        cost = cost_m / 1_000_000
                        parts.append(f"  - {agid} | {name} | {status} | {clicks} clicks | ${cost:.2f} | {conv:.0f} conv")
            except Exception:
                pass

            # Ads + their final/landing URLs (from cache). Without this the
            # agent has to spelunk via tools to answer "update the landing
            # page" — the reported "looks dumb" behaviour.
            try:
                ads = await _cache.get_or_fetch(
                    f"{account_id}:{campaign_id}:ads",
                    lambda: ads_svc.get_ads(account_id, campaign_id),
                    ttl=300,
                )
                if ads:
                    parts.append(f"\n=== ADS ({len(ads)}) — ad ID | ad group | status | final URL ===")
                    for ad in ads:
                        adid = ad.id if hasattr(ad, 'id') else ad.get('id', '')
                        agn = ad.ad_group_name if hasattr(ad, 'ad_group_name') else ad.get('ad_group_name', '')
                        status = ad.status if hasattr(ad, 'status') else ad.get('status', '')
                        urls = ad.final_urls if hasattr(ad, 'final_urls') else ad.get('final_urls', [])
                        url = urls[0] if urls else "(no final URL)"
                        parts.append(f"  - {adid} | {agn} | {status} | {url}")
            except Exception:
                pass

            # Keywords (from cache)
            try:
                keywords = await _cache.get_or_fetch(
                    f"{account_id}:{campaign_id}:keywords",
                    lambda: ads_svc.get_keywords(account_id, campaign_id),
                    ttl=300,
                )
                if keywords:
                    parts.append(f"\n=== KEYWORDS ({len(keywords)}, top 25) ===")
                    for kw in keywords[:25]:
                        text = kw.text if hasattr(kw, 'text') else kw.get('text', '')
                        mt = kw.match_type if hasattr(kw, 'match_type') else kw.get('match_type', '')
                        status = kw.status if hasattr(kw, 'status') else kw.get('status', '')
                        qs = kw.quality_score if hasattr(kw, 'quality_score') else kw.get('quality_score')
                        m = kw.metrics if hasattr(kw, 'metrics') else kw.get('metrics', {})
                        clicks = m.clicks if hasattr(m, 'clicks') else m.get('clicks', 0)
                        conv = m.conversions if hasattr(m, 'conversions') else m.get('conversions', 0)
                        qs_str = f"QS:{qs}" if qs else "QS:--"
                        parts.append(f"  - [{mt}] {text}: {status}, {qs_str}, {clicks} clicks, {conv:.0f} conv")
            except Exception:
                pass

            # Search terms (from cache — 30 min TTL)
            try:
                from datetime import timedelta
                d_from = (date.today() - timedelta(days=6)).isoformat()
                d_to = date.today().isoformat()
                search_terms = await _cache.get_or_fetch(
                    f"{account_id}:{campaign_id}:search_terms",
                    lambda: ads_svc.get_search_terms(account_id, campaign_id, d_from, d_to, limit=40),
                    ttl=1800,
                )
                if search_terms:
                    parts.append(f"\n=== SEARCH TERMS (last 7 days, top {len(search_terms)}) ===")
                    parts.append(f"{'Term':<40} {'Clicks':>6} {'Cost':>8} {'Conv':>5} {'Status'}")
                    parts.append("-" * 70)
                    for st in search_terms:
                        term = st["search_term"][:39]
                        cost = st["cost_micros"] / 1_000_000
                        parts.append(
                            f"{term:<40} {st['clicks']:>6} ${cost:>6.2f} {st['conversions']:>5.0f} {st['status']}"
                        )
            except Exception:
                pass

            # Targeting (from cache — 1 hour TTL)
            try:
                targeting = await _cache.get_or_fetch(
                    f"{account_id}:{campaign_id}:targeting",
                    lambda: ads_svc.get_campaign_targeting(account_id, campaign_id),
                    ttl=3600,
                )
                if targeting:
                    locs = targeting.get("locations", []) if isinstance(targeting, dict) else []
                    langs = targeting.get("languages", []) if isinstance(targeting, dict) else []
                    parts.append(f"\n=== TARGETING ===\nLocations: {', '.join(locs)}\nLanguages: {', '.join(langs)}")
            except Exception:
                pass

        # Account-wide campaign summary (from local store)
        summary = await self.get_account_summary(account_id, days=7)
        if summary:
            enabled = [s for s in summary if s.get("campaign_status") == "ENABLED"]
            parts.append(f"\n=== ALL ENABLED CAMPAIGNS (last 7 days, {len(enabled)} campaigns) ===")
            for s in enabled:
                budget = s["budget_micros"] / 1_000_000 if s["budget_micros"] else 0
                cost = s["cost_micros"] / 1_000_000
                conv = s["conversions"]
                cpa = cost / conv if conv > 0 else 0
                parts.append(
                    f"  - {s['campaign_name']}: ${budget:.0f}/d, {s['bidding_strategy']}, "
                    f"{s['clicks']} clicks, ${cost:.2f}, {conv:.0f} conv, CPA: ${cpa:.2f}"
                )

        # The as-of header is always prepended now, so `parts` is never empty.
        # If it's the ONLY thing present, keep the original guidance for the
        # agent so "no local metrics" still reads clearly (below the honest
        # as-of line, not instead of it).
        if len(parts) <= 1:
            parts.append(
                "No local metrics data available. Data will be synced on next campaign view."
            )

        return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════
# Period-over-period overview (Story 13.7) — homepage KPI cards
# ══════════════════════════════════════════════════════════════════════
#
# The homepage KPI cards want DIRECTION, not naked lifetime totals: for each of
# four metrics — Spend · Conversions · CPA · Conv rate — a value for the current
# window, the value for the immediately-PRIOR equal window, a Δ% between them,
# and a per-day series for a sparkline. All computed from LOCAL
# `campaign_daily_metrics` (no live Google Ads call, no LLM).
#
# ENABLED scoping matches fast_signals.py exactly: the campaign set is taken
# from the `campaigns` table (status = 'ENABLED', the V11 single source of
# truth) so PAUSED / removed campaigns never inflate the account rollup.
#
# ZERO-STATE HONESTY (locked rule, research/homepage-redesign-brief.md):
#   - empty account (no rows) → a VALID shape whose values are null, never
#     zeros pretending to be data;
#   - a derived ratio (CPA = spend/conv, Conv rate = conv/clicks) is null when
#     its denominator is 0 — never a divide-by-zero;
#   - delta_pct is STRICTLY null when the prior window is missing OR its value
#     is 0 — never a fabricated +100% / +∞ jump. The UI hides a null delta.
#
# Window is caller-driven (`days`, default 7, from the header date-range
# picker). The prior window is the equal-length window immediately before it:
#     current : [today-(days-1) .. today]
#     prior   : [today-(2*days-1) .. today-days]

DEFAULT_OVERVIEW_DAYS = 7
MAX_OVERVIEW_DAYS = 365


def _clamp_days(days: int | None) -> int:
    """Coerce the caller's window to a sane positive integer."""
    try:
        n = int(days) if days is not None else DEFAULT_OVERVIEW_DAYS
    except (TypeError, ValueError):
        n = DEFAULT_OVERVIEW_DAYS
    if n < 1:
        n = DEFAULT_OVERVIEW_DAYS
    return min(n, MAX_OVERVIEW_DAYS)


def _safe_div(numer: float, denom: float) -> float | None:
    """A ratio, or None when the denominator is 0 (no divide-by-zero, ever)."""
    if not denom:
        return None
    return numer / denom


def _delta_pct(value: float | None, prev: float | None) -> float | None:
    """Percent change of value vs prev, or None when a delta would be a lie.

    Null (delta hidden by the UI) whenever the current OR prior figure is
    missing, or the prior figure is zero — a % change off a 0 base is +∞ /
    meaningless, not "+100%".
    """
    if value is None or prev is None or prev == 0:
        return None
    return round((value - prev) / prev * 100.0, 1)


def _kpi(value: float | None, prev: float | None) -> dict:
    """One KPI's self-describing block: current, prior, and honest delta."""
    return {
        "value": value,
        "prev_value": prev,
        "delta_pct": _delta_pct(value, prev),
    }


async def _fetch_daily_rollup(account_id: str, start: str, end: str) -> list[dict]:
    """Per-day account rollup of ENABLED campaigns over [start, end] inclusive.

    ENABLED scoping matches fast_signals.py: the roster comes from the
    `campaigns` table (status = 'ENABLED'), and only those campaigns' daily
    metrics contribute. Grouped by date so one query feeds both the window
    totals and the sparkline series.

    Returns {date, spend, conversions, clicks, cpa, conv_rate} rows sorted by
    date ascending. Days with no rows for the ENABLED set simply do not appear
    (a sparse series). An account with no ENABLED campaigns → [].
    """
    db = await get_db()
    try:
        # ENABLED roster first (single source of truth). None → short-circuit.
        cur = await db.execute(
            "SELECT campaign_id FROM campaigns "
            "WHERE account_id = ? AND status = 'ENABLED'",
            (account_id,),
        )
        enabled_ids = [str(r["campaign_id"]) for r in await cur.fetchall()]
        if not enabled_ids:
            return []

        placeholders = ",".join("?" for _ in enabled_ids)
        cur = await db.execute(
            f"""SELECT date,
                       SUM(cost_micros) AS cost_micros,
                       SUM(conversions) AS conversions,
                       SUM(clicks)      AS clicks
                FROM campaign_daily_metrics
                WHERE account_id = ? AND date >= ? AND date <= ?
                  AND campaign_id IN ({placeholders})
                GROUP BY date ORDER BY date ASC""",
            (account_id, start, end, *enabled_ids),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()

    out: list[dict] = []
    for r in rows:
        spend = (r["cost_micros"] or 0) / 1_000_000
        conv = float(r["conversions"] or 0.0)
        clicks = int(r["clicks"] or 0)
        cpa = _safe_div(spend, conv)
        rate = _safe_div(conv, clicks)
        out.append({
            "date": r["date"],
            "spend": round(spend, 2),
            "conversions": round(conv, 2),
            "clicks": clicks,
            "cpa": round(cpa, 2) if cpa is not None else None,
            "conv_rate": round(rate, 4) if rate is not None else None,
        })
    return out


def _totals(rows: list[dict]) -> dict:
    """Sum a window's daily rows into raw spend / conversions / clicks totals."""
    return {
        "spend": round(sum(r["spend"] for r in rows), 2),
        "conversions": round(sum(r["conversions"] for r in rows), 2),
        "clicks": sum(r["clicks"] for r in rows),
    }


def _has_data(totals: dict) -> bool:
    """True when the window carried any activity at all (spend/conv/clicks)."""
    return bool(totals["spend"] or totals["conversions"] or totals["clicks"])


async def get_overview(account_id: str, days: int | None = DEFAULT_OVERVIEW_DAYS) -> dict:
    """Period-over-period KPI overview for the homepage cards (Story 13.7).

    Rolls up ENABLED-campaign `campaign_daily_metrics` account-wide for the
    current `days`-length window and the equal window immediately before it,
    computes the 4 KPIs each as {value, prev_value, delta_pct}, and returns a
    per-day series for the CURRENT window for the sparklines.

    Local SQLite only. Honest nulls throughout: no fabricated deltas, no
    divide-by-zero, empty account → nulls not zeros.
    """
    n = _clamp_days(days)
    today = date.today()

    # Current window: [today-(n-1) .. today].  Prior: the n days before it.
    cur_start = today - timedelta(days=n - 1)
    cur_end = today
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=n - 1)

    cur_rows = await _fetch_daily_rollup(
        account_id, cur_start.isoformat(), cur_end.isoformat()
    )
    prev_rows = await _fetch_daily_rollup(
        account_id, prev_start.isoformat(), prev_end.isoformat()
    )

    cur_t = _totals(cur_rows)
    prev_t = _totals(prev_rows)
    cur_has = _has_data(cur_t)
    prev_has = _has_data(prev_t)

    def _r(x: float | None, nd: int) -> float | None:
        return round(x, nd) if x is not None else None

    # Volume metrics: value is null when the window carried no activity at all
    # (zero-state honesty — an empty window is not "0 spend, 0 conv").
    spend_val = cur_t["spend"] if cur_has else None
    conv_val = cur_t["conversions"] if cur_has else None
    spend_prev = prev_t["spend"] if prev_has else None
    conv_prev = prev_t["conversions"] if prev_has else None

    # Efficiency metrics: derived ratios, null when the denominator is 0.
    cpa_val = _safe_div(cur_t["spend"], cur_t["conversions"]) if cur_has else None
    cpa_prev = _safe_div(prev_t["spend"], prev_t["conversions"]) if prev_has else None
    rate_val = _safe_div(cur_t["conversions"], cur_t["clicks"]) if cur_has else None
    rate_prev = _safe_div(prev_t["conversions"], prev_t["clicks"]) if prev_has else None

    return {
        "account_id": account_id,
        "days": n,
        "window": {"start": cur_start.isoformat(), "end": cur_end.isoformat()},
        "prev_window": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
        "metrics": {
            "spend": _kpi(_r(spend_val, 2), _r(spend_prev, 2)),
            "conversions": _kpi(_r(conv_val, 2), _r(conv_prev, 2)),
            "cpa": _kpi(_r(cpa_val, 2), _r(cpa_prev, 2)),
            "conv_rate": _kpi(_r(rate_val, 4), _r(rate_prev, 4)),
        },
        # Per-day series for the CURRENT window sparklines. Sparse (only days
        # that carried data appear); ordered ascending by date.
        "series": [
            {
                "date": r["date"],
                "spend": r["spend"],
                "conversions": r["conversions"],
                "cpa": r["cpa"],
                "conv_rate": r["conv_rate"],
            }
            for r in cur_rows
        ],
    }
