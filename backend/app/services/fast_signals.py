"""Fast-signals lane — deterministic, always-fresh account signals (Story 13.2).

Separate from the LLM Account Director audit: this is the cheap layer the
homepage fix list can show INSTANTLY on page load. Everything here is computed
from LOCAL data (SQLite) with plain arithmetic — no LLM, no live Google Ads
calls — so it answers in well under a second and is never stale the way a
persisted audit is.

Signals produced (each carries an estimated `$ impact` where derivable):

  1. pending_approvals — Scheduled Plans parked in `awaiting_approval`
     (money/structure changes waiting for the operator). Count + what.
  2. budget_pacing     — an ENABLED campaign whose recent daily spend projects
     to overrun its daily budget (from `campaigns.budget_micros` +
     `campaign_daily_metrics`). $ impact = projected monthly overspend.
  3. wasted_spend      — an ENABLED campaign with spend over the window and
     ZERO conversions (money going nowhere). $ impact = the window spend.
  4. tracking / disapproved flags — cheaply-derivable data-quality flags
     (e.g. a spending campaign with NO conversions data at all → possible
     conversion-tracking gap). These are conservative and clearly labelled.

The homepage merges these with the deep Account Director findings; the fast
signals render immediately, the audit findings render when present.

Reuses `campaigns_repo` (the V11 single source of truth) and
`campaign_daily_metrics` — NO duplicated query logic against the live API.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


def _pacing_ratio() -> float:
    try:
        return float(getattr(settings, "FAST_SIGNAL_PACING_RATIO", 0) or 1.2)
    except (TypeError, ValueError):
        return 1.2


def _waste_min_spend() -> float:
    try:
        return float(getattr(settings, "FAST_SIGNAL_WASTE_MIN_SPEND", 0) or 10.0)
    except (TypeError, ValueError):
        return 10.0


def _window_days() -> int:
    try:
        n = int(getattr(settings, "FAST_SIGNAL_WINDOW_DAYS", 0) or 7)
    except (TypeError, ValueError):
        n = 7
    return max(1, n)


async def _pending_approvals(account_id: str) -> list[dict]:
    """Scheduled Plans parked awaiting sign-off (money/structure). No $ impact
    is invented — the plan's category tells the UI what kind of change waits."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT id, campaign_id, campaign_name, title, action_category, "
            "proposed_change, next_run_at "
            "FROM scheduled_plans "
            "WHERE account_id = ? AND status = 'awaiting_approval' "
            "ORDER BY updated_at DESC",
            (account_id,),
        )
        rows = await cur.fetchall()
    finally:
        await db.close()
    out: list[dict] = []
    for r in rows:
        out.append({
            "type": "pending_approval",
            "plan_id": r["id"],
            "campaign_id": r["campaign_id"],
            "campaign_name": r["campaign_name"],
            "title": r["title"],
            "action_category": r["action_category"] or "other",
            "detail": (r["proposed_change"] or "").strip()[:400] or None,
            "dollar_impact_wk": None,       # honest: not derivable from the plan row
            "severity": "action",
        })
    return out


async def _pacing_and_waste(account_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Budget pacing + wasted-spend + tracking flags, all from local rows.

    Rolls up the last N days of `campaign_daily_metrics` per ENABLED campaign
    (status joined from the `campaigns` table so PAUSED/removed campaigns are
    never flagged), then:
      - pacing:  avg daily spend projects (×30) past the daily budget × ratio
      - waste:   window spend >= threshold AND zero conversions
      - tracking: spending campaign with zero conversions across the window AND
                  no conversions ever recorded → possible tracking gap (flagged
                  once, conservatively, distinct from 'waste')
    """
    days = _window_days()
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()

    db = await get_db()
    try:
        # ENABLED campaigns + their daily budget (single source of truth).
        cur = await db.execute(
            "SELECT campaign_id, name, budget_micros FROM campaigns "
            "WHERE account_id = ? AND status = 'ENABLED'",
            (account_id,),
        )
        campaigns = {
            str(r["campaign_id"]): {
                "name": r["name"] or f"Campaign {r['campaign_id']}",
                "budget": (r["budget_micros"] or 0) / 1_000_000,
            }
            for r in await cur.fetchall()
        }

        # Window rollup of spend + conversions + day count per campaign.
        cur = await db.execute(
            "SELECT campaign_id, campaign_name, "
            "SUM(cost_micros) AS cost_micros, SUM(conversions) AS conversions, "
            "COUNT(DISTINCT date) AS n_days "
            "FROM campaign_daily_metrics "
            "WHERE account_id = ? AND date >= ? "
            "GROUP BY campaign_id",
            (account_id, cutoff),
        )
        rollup = {str(r["campaign_id"]): dict(r) for r in await cur.fetchall()}
    finally:
        await db.close()

    ratio = _pacing_ratio()
    waste_min = _waste_min_spend()

    pacing: list[dict] = []
    waste: list[dict] = []
    tracking: list[dict] = []

    for cid, meta in campaigns.items():
        row = rollup.get(cid)
        if not row:
            continue
        spend = (row.get("cost_micros") or 0) / 1_000_000
        conv = row.get("conversions") or 0.0
        n_days = row.get("n_days") or 0
        name = meta["name"]
        budget = meta["budget"]

        # ── Budget pacing ──────────────────────────────────────────────
        # avg daily spend over the days we actually have data for.
        if budget > 0 and n_days > 0 and spend > 0:
            avg_daily = spend / n_days
            projected_monthly = avg_daily * 30.0
            budget_monthly = budget * 30.0
            if avg_daily >= budget * ratio:
                overspend = round(projected_monthly - budget_monthly, 2)
                pacing.append({
                    "type": "budget_pacing",
                    "campaign_id": cid,
                    "campaign_name": name,
                    "title": f"{name} pacing over budget",
                    "detail": (
                        f"Avg ${avg_daily:.2f}/day vs ${budget:.2f}/day budget "
                        f"(last {n_days}d) — projects ~${projected_monthly:.0f}/mo "
                        f"vs ${budget_monthly:.0f}/mo cap"
                    ),
                    "avg_daily_spend": round(avg_daily, 2),
                    "daily_budget": round(budget, 2),
                    # weekly framing of the overspend (monthly / ~4.33)
                    "dollar_impact_wk": round((projected_monthly - budget_monthly) / 4.345, 2),
                    "projected_monthly_overspend": overspend,
                    "action_category": "budget",
                    "severity": "warn",
                })

        # ── Wasted spend (0-conv) ──────────────────────────────────────
        if spend >= waste_min and conv <= 0:
            # weekly-normalized waste so the homepage total is per-week.
            waste_wk = round(spend / n_days * 7.0, 2) if n_days > 0 else round(spend, 2)
            waste.append({
                "type": "wasted_spend",
                "campaign_id": cid,
                "campaign_name": name,
                "title": f"Wasted spend on {name}",
                "detail": (
                    f"${spend:.2f} spent over {n_days}d with 0 conversions"
                ),
                "window_spend": round(spend, 2),
                "conversions": round(conv, 1),
                "dollar_impact_wk": waste_wk,
                "action_category": "search_terms",
                "severity": "warn",
            })

            # ── Tracking gap (subset of waste, flagged conservatively) ──
            # Spending real money, zero conversions across the whole window,
            # AND every day recorded shows zero → a plausible conversion-
            # tracking gap rather than mere inefficiency. Distinct, quieter.
            if spend >= waste_min and n_days >= max(3, days - 1):
                tracking.append({
                    "type": "tracking_gap",
                    "campaign_id": cid,
                    "campaign_name": name,
                    "title": f"Possible conversion-tracking gap on {name}",
                    "detail": (
                        f"${spend:.2f} spent across {n_days} days with no "
                        f"conversions recorded at all — verify conversion tracking"
                    ),
                    "dollar_impact_wk": None,   # can't quantify a tracking gap
                    "action_category": "audit",
                    "severity": "info",
                })

    pacing.sort(key=lambda s: -(s.get("dollar_impact_wk") or 0.0))
    waste.sort(key=lambda s: -(s.get("dollar_impact_wk") or 0.0))
    return pacing, waste, tracking


async def get_signals(account_id: str) -> dict:
    """Assemble the always-fresh fast-signals payload for an account.

    Deterministic, local-only. `total_impact_wk` sums the derivable weekly-$
    across all signals (pending approvals contribute nothing — no honest
    number). `count` lets the homepage collapse the strip when zero.
    """
    pending = await _pending_approvals(account_id)
    pacing, waste, tracking = await _pacing_and_waste(account_id)

    all_signals = pending + pacing + waste + tracking
    total_impact = round(
        sum(s.get("dollar_impact_wk") or 0.0 for s in all_signals), 2
    )
    return {
        "account_id": account_id,
        "signals": {
            "pending_approvals": pending,
            "budget_pacing": pacing,
            "wasted_spend": waste,
            "tracking_flags": tracking,
        },
        "count": len(all_signals),
        "total_impact_wk": total_impact,
        "window_days": _window_days(),
    }
