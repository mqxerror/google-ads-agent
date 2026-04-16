"""Campaign Report endpoints — generate professional reports from campaign data."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import settings
from app.database import get_db
from app.services.campaign_memory import (
    load_profile, load_pinned_facts, load_decisions, load_role_notes,
)
from app.services.chronicle import load_chronicle
from app.services.token_counter import estimate_tokens

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/report")
async def get_campaign_report(account_id: str, campaign_id: str) -> dict:
    """Generate a full campaign report as structured JSON."""

    # Campaign name from DB
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT DISTINCT campaign_name FROM conversations WHERE account_id = ? AND campaign_id = ? LIMIT 1",
            (account_id, campaign_id),
        )
        row = await cur.fetchone()
        campaign_name = row["campaign_name"] if row else f"Campaign {campaign_id}"

        # Metrics from daily store
        cur = await db.execute(
            """SELECT date, impressions, clicks, cost_micros, conversions, ctr, avg_cpc_micros
               FROM campaign_daily_metrics
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY date DESC LIMIT 30""",
            (account_id, campaign_id),
        )
        metrics_rows = [dict(r) for r in await cur.fetchall()]

        # Outcome recommendations
        cur = await db.execute(
            """SELECT action_type, action_detail, outcome, outcome_delta_json, executed_at, status
               FROM recommendations
               WHERE account_id = ? AND campaign_id = ?
               ORDER BY executed_at DESC LIMIT 20""",
            (account_id, campaign_id),
        )
        recommendations = [dict(r) for r in await cur.fetchall()]

        # Decision count
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM decision_log WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        decision_count = (await cur.fetchone())["cnt"]

        # Conversation count
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        conv_count = (await cur.fetchone())["cnt"]
    finally:
        await db.close()

    # Memory files
    profile = load_profile(account_id, campaign_id)
    pinned_facts = load_pinned_facts(account_id, campaign_id)
    decisions = load_decisions(account_id, campaign_id)
    chronicle = load_chronicle(account_id, campaign_id)

    # Role notes
    role_findings = []
    memory_dir = settings.MEMORY_DIR / account_id / campaign_id / "role_notes"
    if memory_dir.exists():
        for f in sorted(memory_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            role_findings.append({
                "role_id": f.stem,
                "role_name": f.stem.replace("_", " ").title(),
                "content": content,
                "size": len(content),
            })

    # Aggregate metrics
    total_impressions = sum(r.get("impressions", 0) for r in metrics_rows)
    total_clicks = sum(r.get("clicks", 0) for r in metrics_rows)
    total_cost = sum(r.get("cost_micros", 0) for r in metrics_rows)
    total_conversions = sum(r.get("conversions", 0) for r in metrics_rows)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpa = (total_cost / 1_000_000 / total_conversions) if total_conversions > 0 else 0

    # Parse pinned facts into list
    fact_items = [
        l.strip().lstrip("- ") for l in pinned_facts.split("\n")
        if l.strip().startswith("- **")
    ]

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "generated_at": date.today().isoformat(),
        "account_id": account_id,

        "summary": {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_cost": round(total_cost / 1_000_000, 2),
            "total_conversions": total_conversions,
            "avg_ctr": round(avg_ctr, 2),
            "avg_cpa": round(avg_cpa, 2),
            "days_of_data": len(metrics_rows),
            "decision_count": decision_count,
            "conversation_count": conv_count,
        },

        "daily_metrics": list(reversed(metrics_rows)),
        "role_findings": role_findings,
        "recommendations": recommendations,
        "decisions": decisions,
        "pinned_facts": fact_items,
        "profile": profile,
        "chronicle": chronicle,
    }


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/report/html")
async def get_campaign_report_html(account_id: str, campaign_id: str) -> HTMLResponse:
    """Generate a self-contained HTML report for download/print."""
    from fastapi.responses import HTMLResponse

    # Get the report data
    # (reuse the JSON endpoint logic)
    report = await get_campaign_report(account_id, campaign_id)

    # Build HTML
    html = _build_html_report(report)
    return HTMLResponse(content=html, headers={
        "Content-Disposition": f'attachment; filename="{report["campaign_name"]}_report_{report["generated_at"]}.html"',
    })


def _build_html_report(r: dict) -> str:
    """Build a self-contained HTML report with inline CSS."""
    s = r["summary"]
    name = r["campaign_name"]
    generated = r["generated_at"]

    # Role findings sections
    role_sections = ""
    for rf in r.get("role_findings", []):
        content_html = rf["content"].replace("\n", "<br>").replace("**", "<strong>").replace("##", "<h4>")
        role_sections += f"""
        <div class="role-card">
            <h3>{rf["role_name"]}</h3>
            <div class="role-content">{content_html[:2000]}</div>
        </div>"""

    # Pinned facts
    facts_html = "".join(f"<li>{f}</li>" for f in r.get("pinned_facts", []))

    # Metrics table
    metrics_rows = ""
    for m in r.get("daily_metrics", [])[:14]:
        cost = m.get("cost_micros", 0) / 1_000_000
        metrics_rows += f"""
        <tr>
            <td>{m.get("date", "")}</td>
            <td>{m.get("impressions", 0):,}</td>
            <td>{m.get("clicks", 0):,}</td>
            <td>{m.get("ctr", 0):.1f}%</td>
            <td>${cost:,.2f}</td>
            <td>{m.get("conversions", 0)}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} — Campaign Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; background: #fff; line-height: 1.6; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 40px 32px; }}
        .header {{ border-bottom: 3px solid #2563eb; padding-bottom: 24px; margin-bottom: 32px; }}
        .header h1 {{ font-size: 28px; font-weight: 700; color: #1a1a2e; }}
        .header p {{ color: #64748b; font-size: 14px; margin-top: 4px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }}
        .metric-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }}
        .metric-card .label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
        .metric-card .value {{ font-size: 28px; font-weight: 700; color: #1a1a2e; margin-top: 4px; }}
        .metric-card .sub {{ font-size: 11px; color: #94a3b8; margin-top: 2px; }}
        h2 {{ font-size: 20px; font-weight: 600; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0; }}
        .role-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; }}
        .role-card h3 {{ font-size: 16px; font-weight: 600; color: #2563eb; margin-bottom: 8px; }}
        .role-content {{ font-size: 13px; color: #475569; white-space: pre-wrap; word-break: break-word; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 16px 0; }}
        th {{ text-align: left; padding: 8px 12px; background: #f1f5f9; border-bottom: 2px solid #e2e8f0; font-weight: 600; color: #475569; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }}
        tr:hover td {{ background: #f8fafc; }}
        .facts-list {{ list-style: none; }}
        .facts-list li {{ padding: 8px 12px; background: #fffbeb; border-left: 3px solid #f59e0b; margin-bottom: 8px; border-radius: 0 8px 8px 0; font-size: 13px; }}
        .chronicle {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; font-size: 13px; white-space: pre-wrap; color: #475569; max-height: 400px; overflow-y: auto; }}
        .footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center; }}
        @media print {{
            body {{ font-size: 11px; }}
            .container {{ padding: 20px; }}
            .metric-card .value {{ font-size: 22px; }}
            .role-card, .chronicle {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{name}</h1>
            <p>Campaign Report · Generated {generated}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="label">Impressions</div>
                <div class="value">{s["total_impressions"]:,}</div>
                <div class="sub">{s["days_of_data"]} days of data</div>
            </div>
            <div class="metric-card">
                <div class="label">Clicks</div>
                <div class="value">{s["total_clicks"]:,}</div>
                <div class="sub">CTR: {s["avg_ctr"]}%</div>
            </div>
            <div class="metric-card">
                <div class="label">Total Cost</div>
                <div class="value">${s["total_cost"]:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="label">Conversions</div>
                <div class="value">{s["total_conversions"]}</div>
                <div class="sub">CPA: ${s["avg_cpa"]:,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="label">Decisions Made</div>
                <div class="value">{s["decision_count"]}</div>
            </div>
            <div class="metric-card">
                <div class="label">Conversations</div>
                <div class="value">{s["conversation_count"]}</div>
            </div>
        </div>

        <h2>Daily Performance</h2>
        <table>
            <thead>
                <tr><th>Date</th><th>Impressions</th><th>Clicks</th><th>CTR</th><th>Cost</th><th>Conv</th></tr>
            </thead>
            <tbody>{metrics_rows}</tbody>
        </table>

        <h2>Role Findings</h2>
        {role_sections or '<p style="color:#94a3b8">No role findings recorded yet.</p>'}

        {"<h2>Pinned Facts</h2><ul class='facts-list'>" + facts_html + "</ul>" if facts_html else ""}

        {"<h2>Campaign Chronicle</h2><div class='chronicle'>" + r.get("chronicle", "").replace(chr(10), "<br>") + "</div>" if r.get("chronicle") else ""}

        <div class="footer">
            Generated by Google Ads Agent · {generated}
        </div>
    </div>
</body>
</html>"""
