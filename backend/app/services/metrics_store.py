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
                await db.execute(
                    """INSERT OR REPLACE INTO campaign_daily_metrics
                       (account_id, campaign_id, campaign_name, date,
                        impressions, clicks, cost_micros, conversions, ctr, avg_cpc_micros,
                        synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
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
                    parts.append(f"\n=== AD GROUPS ({len(adgroups)}) ===")
                    for ag in adgroups:
                        name = ag.name if hasattr(ag, 'name') else ag.get('name', '')
                        status = ag.status if hasattr(ag, 'status') else ag.get('status', '')
                        m = ag.metrics if hasattr(ag, 'metrics') else ag.get('metrics', {})
                        clicks = m.clicks if hasattr(m, 'clicks') else m.get('clicks', 0)
                        conv = m.conversions if hasattr(m, 'conversions') else m.get('conversions', 0)
                        cost_m = m.cost_micros if hasattr(m, 'cost_micros') else m.get('cost_micros', 0)
                        cost = cost_m / 1_000_000
                        parts.append(f"  - {name}: {status}, {clicks} clicks, ${cost:.2f}, {conv:.0f} conv")
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

        if not parts:
            return "No local metrics data available. Data will be synced on next campaign view."

        return "\n".join(parts)
