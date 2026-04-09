"""Claude Code agent service — layered memory system."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import threading
import queue
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import AsyncIterator

from app.config import settings
from app.database import get_db
from app.services.google_ads import GoogleAdsService

logger = logging.getLogger(__name__)

_NODE_PATH = shutil.which("node") or "node"

# Find Claude CLI JS entry point — cross-platform
def _find_cli_js() -> Path:
    """Find the Claude Code CLI JS file across OS platforms."""
    candidates = [
        # Windows (npm global)
        Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js",
        # macOS/Linux (npm global)
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
        # nvm on macOS/Linux
        Path.home() / ".nvm/versions/node" / "*/lib/node_modules/@anthropic-ai/claude-code/cli.js",
    ]
    for p in candidates:
        if "*" in str(p):
            # Glob for nvm versioned paths
            import glob
            matches = glob.glob(str(p))
            if matches:
                return Path(matches[0])
        elif p.exists():
            return p
    # Fallback: try to find via npm root
    try:
        import subprocess as _sp
        result = _sp.run([shutil.which("npm") or "npm", "root", "-g"],
                         capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            npm_root = Path(result.stdout.strip())
            cli = npm_root / "@anthropic-ai/claude-code/cli.js"
            if cli.exists():
                return cli
    except Exception:
        pass
    # Last resort
    return Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js"

_CLI_JS = _find_cli_js()
_GUIDELINES_DIR = settings.GUIDELINES_DIR
_BACKEND_DIR = settings.PROJECT_ROOT  # backend/ directory
_MCP_MAIN = _BACKEND_DIR / "google_ads" / "mcp_main.py"
_UV_PATH = shutil.which("uv") or "uv"


def _find_modern_npx() -> str:
    """Find an npx binary with Node >= 20.19 (required by some MCP packages).

    Checks nvm versions first, then falls back to system npx.
    """
    import glob
    import subprocess as _sp
    from pathlib import Path as _Path

    # Check nvm versions (sorted newest first)
    nvm_dir = _Path.home() / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        versions = sorted(glob.glob(str(nvm_dir / "v*")), reverse=True)
        for v_dir in versions:
            npx_path = _Path(v_dir) / "bin" / "npx"
            node_path = _Path(v_dir) / "bin" / "node"
            if npx_path.exists() and node_path.exists():
                try:
                    result = _sp.run(
                        [str(node_path), "--version"],
                        capture_output=True, text=True, timeout=3,
                    )
                    version = result.stdout.strip().lstrip("v")
                    major, minor = map(int, version.split(".")[:2])
                    if (major, minor) >= (20, 19):
                        return str(npx_path)
                except Exception:
                    continue

    # Fallback to system npx
    return shutil.which("npx") or "npx"


_MODERN_NPX = _find_modern_npx()

# Track running agent subprocesses by conversation_id so users can cancel stuck tasks
_running_procs: dict[str, subprocess.Popen] = {}


def stop_agent(conversation_id: str) -> bool:
    """Stop a running agent subprocess for the given conversation. Returns True if a process was killed."""
    proc = _running_procs.get(conversation_id)
    if proc is None:
        return False
    try:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        return True
    except Exception:
        return False
    finally:
        _running_procs.pop(conversation_id, None)


def _get_mcp_config_path() -> Path:
    """Generate MCP config JSON for the Claude CLI and return its path."""
    backend_dir = str(_BACKEND_DIR)
    servers: dict = {
        "google-ads": {
            "type": "stdio",
            "command": _UV_PATH,
            "args": [
                "run", "--directory", backend_dir,
                "python", str(_MCP_MAIN),
                "--groups", "core,targeting,bidding,planning,reporting",
            ],
            "cwd": backend_dir,
            "env": {
                "PYTHONPATH": backend_dir,
            },
        }
    }

    # Chrome MCP — browser automation for GTM UI, landing pages, Google Ads UI
    if settings.CHROME_MCP_ENABLED:
        # Use modern npx (Node >= 20.19) for chrome-devtools-mcp compatibility
        cmd = _MODERN_NPX if settings.CHROME_MCP_COMMAND == "npx" else (
            shutil.which(settings.CHROME_MCP_COMMAND) or settings.CHROME_MCP_COMMAND
        )
        chrome_env = {}
        # Prepend the modern npx's bin dir to PATH so child processes also use modern node
        if cmd != "npx":
            npx_bin_dir = str(Path(cmd).parent)
            chrome_env["PATH"] = f"{npx_bin_dir}:{os.environ.get('PATH', '')}"

        # Build chrome args: base args + optional --browser-url to reuse existing Chrome
        chrome_args = list(settings.CHROME_MCP_ARGS)
        if settings.CHROME_REUSE_EXISTING:
            chrome_args.extend(["--browser-url", f"http://127.0.0.1:{settings.CHROME_DEBUG_PORT}"])

        servers["chrome"] = {
            "type": "stdio",
            "command": cmd,
            "args": chrome_args,
            **({"env": chrome_env} if chrome_env else {}),
        }

    # GTM MCP — Google Tag Manager API for programmatic tag management
    if settings.GTM_MCP_ENABLED and settings.GTM_MCP_COMMAND:
        gtm_cmd = shutil.which(settings.GTM_MCP_COMMAND) or settings.GTM_MCP_COMMAND
        if Path(gtm_cmd).exists():
            servers["gtm"] = {
                "type": "stdio",
                "command": gtm_cmd,
            }

    config = {"mcpServers": servers}
    config_path = _BACKEND_DIR / "data" / "mcp_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    return config_path



_ads_svc = GoogleAdsService()

AVAILABLE_MODELS = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


def _guidelines_dir_for_account(account_id: str | None) -> Path:
    """V2: Resolve guidelines directory — per-account if available, fallback to flat."""
    if account_id:
        acct_dir = _GUIDELINES_DIR / account_id
        if acct_dir.exists():
            return acct_dir
    return _GUIDELINES_DIR


# ── Layer 0: Marketing Intelligence (NEW in V2) ────────────────

async def _get_marketing_intelligence(
    account_id: str | None, campaign_id: str | None, campaign_name: str | None
) -> str:
    """Generate Layer 0: marketing intelligence context."""
    if not account_id or not campaign_id:
        return ""

    from app.services.marketing_intelligence import MarketingIntelligenceService, CampaignObjective, CampaignPhase

    mi = MarketingIntelligenceService()
    db = await get_db()
    try:
        # Load stored goal/phase
        cur = await db.execute(
            "SELECT objective, phase, target_cpa, target_roas, monthly_budget_cap, notes "
            "FROM campaign_goals WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        row = await cur.fetchone()

        if row:
            goal = CampaignObjective(row["objective"]) if row["objective"] else CampaignObjective.UNKNOWN
            phase = CampaignPhase(row["phase"]) if row["phase"] else CampaignPhase.UNKNOWN
        else:
            goal = CampaignObjective.UNKNOWN
            phase = CampaignPhase.UNKNOWN

        # Load active alerts for this campaign
        cur = await db.execute(
            "SELECT type, severity, title, message, recommendation FROM alerts "
            "WHERE account_id = ? AND (campaign_id = ? OR campaign_id IS NULL) AND dismissed_at IS NULL "
            "ORDER BY severity DESC LIMIT 5",
            (account_id, campaign_id),
        )
        alerts = [dict(r) for r in await cur.fetchall()]

        return mi.enrich_agent_prompt(goal, phase, alerts, campaign_name or "")
    except Exception as e:
        logger.warning("Marketing intelligence failed: %s", e)
        return ""
    finally:
        await db.close()


# ── Layer 1: Business Context ────────────────────────────────────

def _load_business_context(account_id: str | None = None) -> str:
    """Load the business context file (Layer 1 — always loaded, ~2K tokens)."""
    gdir = _guidelines_dir_for_account(account_id)
    path = gdir / "BUSINESS_CONTEXT.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# ── Layer 2: Campaign Guidelines ─────────────────────────────────

def _load_campaign_guidelines(campaign_name: str | None, account_id: str | None = None) -> str:
    """Load relevant guidelines for the campaign (Layer 2 — ~3K tokens)."""
    gdir = _guidelines_dir_for_account(account_id)
    parts = []

    # Always load global rules from main guidelines
    main_file = gdir / "CAMPAIGN_GUIDELINES.md"
    if main_file.exists():
        content = main_file.read_text(encoding="utf-8")
        # Extract global rules section
        lines = content.split("\n")
        in_global = False
        global_lines = []
        for line in lines:
            if "## Global Rules" in line:
                in_global = True
            elif in_global and (line.startswith("## ") and "Global Rules" not in line):
                break
            if in_global:
                global_lines.append(line)
        if global_lines:
            parts.append("## Global Campaign Rules\n" + "\n".join(global_lines[:80]))

        # Extract campaign-specific section
        if campaign_name:
            in_campaign = False
            campaign_lines = []
            for line in lines:
                if line.startswith("## ") and campaign_name.lower() in line.lower():
                    in_campaign = True
                elif in_campaign and line.startswith("## "):
                    break
                if in_campaign:
                    campaign_lines.append(line)
            if campaign_lines:
                parts.append("\n".join(campaign_lines[:100]))

    # Load region-specific guidelines
    if campaign_name:
        name_lower = campaign_name.lower()
        if "mena" in name_lower or "arabic" in name_lower:
            mena_file = gdir / "MENA_CAMPAIGN_GUIDELINES.md"
            if mena_file.exists():
                parts.append(mena_file.read_text(encoding="utf-8")[:2000])
        elif "greece" in name_lower:
            greece_file = gdir / "GREECE_CAMPAIGN_GUIDELINES.md"
            if greece_file.exists():
                parts.append(greece_file.read_text(encoding="utf-8")[:2000])

    return "\n\n".join(parts)


# ── Layer 3: Recent Conversation (sliding window) ────────────────

async def _get_recent_messages(conversation_id: str, limit: int = 10) -> list[dict]:
    """Get the last N messages from the conversation (Layer 3)."""
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = await cur.fetchall()
        # Reverse to chronological order
        return [{"role": r["role"], "content": r["content"][:500]} for r in reversed(rows)]
    finally:
        await db.close()


# ── Layer 4: Session Summaries (compressed history) ──────────────

async def _get_session_summaries(campaign_id: str | None, limit: int = 5) -> list[str]:
    """Get past session summaries for this campaign (Layer 4)."""
    if not campaign_id:
        return []
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT summary, created_at FROM session_summaries "
            "WHERE campaign_id = ? ORDER BY created_at DESC LIMIT ?",
            (campaign_id, limit),
        )
        rows = await cur.fetchall()
        return [f"[{r['created_at']}] {r['summary']}" for r in reversed(rows)]
    finally:
        await db.close()


async def _save_session_summary(
    conversation_id: str, campaign_id: str | None, campaign_name: str | None, summary: str
):
    """Save a session summary for future reference."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO session_summaries (id, conversation_id, campaign_id, campaign_name, summary) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, campaign_id, campaign_name, summary),
        )
        await db.commit()
    finally:
        await db.close()


# ── Layer 5: Campaign Data (local-first, API fallback) ──────────

async def _get_campaign_data(account_id: str | None, campaign_id: str | None) -> str:
    """Get campaign data — reads from local metrics store first (milliseconds),
    falls back to live API only if no local data exists."""
    if not account_id:
        return "No account selected."

    # Try local metrics store first (fast — no API calls)
    from app.services.metrics_store import MetricsStore
    metrics_store = MetricsStore()

    has_local = await metrics_store.has_recent_data(account_id, days=2)
    if has_local:
        local_data = await metrics_store.format_for_agent(account_id, campaign_id, None)
        if local_data and "No local metrics" not in local_data:
            return local_data + "\n\n(Data from local store. Use API endpoints for real-time data if needed.)"

    # Fallback: fetch from API (slow but always fresh)
    parts = []
    today = date.today()

    try:
        # Day-by-day for selected campaign (last 7 days)
        if campaign_id:
            parts.append(f"Day-by-day performance (last 7 days):")
            parts.append(f"{'Date':<12} {'Impr':>6} {'Clicks':>7} {'Cost':>10} {'Conv':>5} {'CTR':>7} {'CPC':>8}")
            parts.append("-" * 62)
            for i in range(7):
                d = today - timedelta(days=i)
                d_str = d.isoformat()
                try:
                    day_data = await _ads_svc.get_campaigns(account_id, d_str, d_str)
                    day_c = next((c for c in day_data if c.id == campaign_id), None)
                    if day_c and day_c.metrics.impressions > 0:
                        m = day_c.metrics
                        cost = m.cost_micros / 1_000_000
                        cpc = cost / m.clicks if m.clicks > 0 else 0
                        ctr = m.clicks / m.impressions * 100 if m.impressions > 0 else 0
                        parts.append(f"{d_str:<12} {m.impressions:>6} {m.clicks:>7} ${cost:>8.2f} {m.conversions:>5.0f} {ctr:>6.1f}% ${cpc:>6.2f}")
                    else:
                        parts.append(f"{d_str:<12}      0       0      $0.00     0    0.0%   $0.00")
                except Exception:
                    pass

            # Ad groups and keywords
            try:
                adgroups = await _ads_svc.get_adgroups(account_id, campaign_id)
                parts.append(f"\nAd Groups ({len(adgroups)}):")
                for ag in adgroups:
                    parts.append(f"  - {ag.name}: {ag.status}, Clicks: {ag.metrics.clicks}, Conv: {ag.metrics.conversions}")
            except Exception:
                pass

            try:
                keywords = await _ads_svc.get_keywords(account_id, campaign_id)
                parts.append(f"\nKeywords ({len(keywords)}):")
                for kw in keywords[:20]:
                    qs = f"QS:{kw.quality_score}" if kw.quality_score else "QS:--"
                    parts.append(f"  - [{kw.match_type}] {kw.text}: {kw.status}, {qs}, Clicks: {kw.metrics.clicks}, Conv: {kw.metrics.conversions}")
            except Exception:
                pass

            try:
                targeting = await _ads_svc.get_campaign_targeting(account_id, campaign_id)
                parts.append(f"\nTargeting: {', '.join(targeting['locations'])} | {', '.join(targeting['languages'])}")
            except Exception:
                pass

            # Search terms (last 3 days)
            try:
                three_days_ago = (today - timedelta(days=2)).isoformat()
                search_terms = await _ads_svc.get_search_terms(
                    account_id, campaign_id, three_days_ago, today.isoformat(), limit=40
                )
                if search_terms:
                    parts.append(f"\nSearch Terms (last 3 days, top {len(search_terms)}):")
                    parts.append(f"{'Search Term':<45} {'Clicks':>6} {'Impr':>6} {'Cost':>8} {'Conv':>5} {'Status'}")
                    parts.append("-" * 85)
                    for st in search_terms:
                        cost = st["cost_micros"] / 1_000_000
                        parts.append(
                            f"{st['search_term'][:44]:<45} {st['clicks']:>6} {st['impressions']:>6} ${cost:>6.2f} {st['conversions']:>5.0f} {st['status']}"
                        )
            except Exception as e:
                parts.append(f"\nSearch terms: could not fetch ({e})")

        # Account-wide ENABLED campaigns summary
        campaigns = await _ads_svc.get_campaigns(account_id, (today - timedelta(days=6)).isoformat(), today.isoformat())
        enabled = [c for c in campaigns if c.status == "ENABLED"]
        parts.append(f"\nAll ENABLED campaigns (last 7 days):")
        for c in enabled:
            budget = c.budget_micros / 1_000_000
            cost = c.metrics.cost_micros / 1_000_000
            parts.append(f"  - {c.name}: ${budget}/d, {c.bidding_strategy}, {c.metrics.clicks} clicks, ${cost:.2f}, {c.metrics.conversions} conv")

    except Exception as e:
        parts.append(f"Error: {e}")

    return "\n".join(parts)


# ── Main: Assemble All Layers ────────────────────────────────────

async def stream_agent_response(
    user_message: str,
    account_id: str | None = None,
    campaign_name: str | None = None,
    conversation_id: str | None = None,
    base_guidelines: str | None = None,
    campaign_guidelines: str | None = None,
    model: str = "sonnet",
) -> AsyncIterator[dict]:
    """Stream agent responses with full layered memory."""

    model_id = AVAILABLE_MODELS.get(model, AVAILABLE_MODELS["sonnet"])
    today = date.today()

    # Find campaign ID
    # ── Resolve the client account ID (MCC can't query metrics) ──
    api_account_id = account_id or "7178239091"
    try:
        accessible = await _ads_svc.get_accessible_accounts()
        clients = [a for a in accessible if a.level == "client"]
        if clients:
            # Pick the best client — prefer named accounts with "Main" or "Mercan"
            named = [c for c in clients if not c.name.startswith("Account ")]
            preferred = next(
                (c for c in named if "main" in c.name.lower() or "mercan" in c.name.lower()),
                named[0] if named else clients[0],
            )
            api_account_id = preferred.id
    except Exception:
        pass

    # Find campaign ID using the resolved client account (not MCC)
    campaign_id = None
    if campaign_name:
        try:
            campaigns = await _ads_svc.get_campaigns(api_account_id)
            match = next((c for c in campaigns if c.name == campaign_name), None)
            if match:
                campaign_id = match.id
        except Exception:
            pass

    # Layer 0: Marketing Intelligence (NEW in V2)
    marketing_intel = await _get_marketing_intelligence(account_id, campaign_id, campaign_name)

    # Layer 1: Business context
    business_ctx = _load_business_context(account_id)

    # Layer 2: Campaign guidelines
    guidelines = _load_campaign_guidelines(campaign_name, account_id)

    # Layer 3: Recent conversation
    recent_msgs = []
    if conversation_id:
        recent_msgs = await _get_recent_messages(conversation_id, limit=10)

    # Layer 4: Past session summaries
    summaries = await _get_session_summaries(campaign_id, limit=5)

    # Layer 5: Live data
    live_data = await _get_campaign_data(api_account_id, campaign_id)

    # ── Build system prompt ──────────────────────────────────

    cid = api_account_id

    system_parts = [
        f"You are an expert Google Ads campaign manager and senior PPC strategist. Today is {today.isoformat()}.",
        "You have deep knowledge of digital marketing, campaign optimization, and Google Ads best practices.",
        "Always use specific numbers. Compare day-by-day when asked. Give actionable recommendations.",
        "When the user refers to 'this campaign', they mean the selected campaign shown in the context.",
        "Think like a senior paid media strategist: consider campaign goals, phases, audience intent, and budget efficiency.",
        "",
    ]

    # Layer 0: Marketing Intelligence (injected first for maximum influence)
    if marketing_intel:
        system_parts.append(f"=== MARKETING INTELLIGENCE (use this to guide your recommendations) ===\n{marketing_intel}")

    system_parts.extend([
        "=== GOOGLE ADS MCP TOOLS (PRIMARY — USE THESE) ===",
        "You have access to a 'google-ads' MCP server with 87+ tools for managing Google Ads.",
        f"The customer ID for this account is: {cid}",
        "All tool names are prefixed with their service (e.g. campaign__create_campaign, ad__create_responsive_search_ad).",
        "",
        "KEY MCP TOOLS available to you (call via mcp__google-ads__<name>):",
        "",
        "READING DATA:",
        "  - google_ads__search_google_ads(customer_id, query) — Execute ANY GAQL query",
        "  - search__search_campaigns(customer_id, ...) — List campaigns with metrics",
        "  - search__search_ad_groups(customer_id, campaign_id) — List ad groups",
        "  - search__search_keywords(customer_id, campaign_id) — List keywords",
        "  - search__execute_query(customer_id, query) — Execute GAQL query",
        "",
        "CREATING (full campaign build workflow):",
        "  1. budget__create_campaign_budget(customer_id, name, amount_micros) → get budget_resource_name",
        "  2. campaign__create_campaign(customer_id, name, budget_resource_name, status=PAUSED) → campaign created",
        "  3. ad_group__create_ad_group(customer_id, campaign_id, name) → get ad_group resource",
        "  4. keyword__add_keywords(customer_id, ad_group_id, keywords=[{text, match_type}]) → keywords added",
        "  5. ad__create_responsive_search_ad(customer_id, ad_group_id, headlines, descriptions, final_urls) → RSA created",
        "",
        "MODIFYING:",
        "  - campaign__update_campaign(customer_id, campaign_id, status/name/dates)",
        "  - ad_group__update_ad_group(customer_id, ad_group_id, ...)",
        "  - keyword__update_keyword_bid(customer_id, ad_group_id, criterion_id, bid)",
        "  - keyword__remove_keyword(customer_id, ad_group_id, criterion_id)",
        "  - campaign_criterion__add_negative_keyword_criteria(customer_id, campaign_id, keywords)",
        "  - campaign_criterion__add_location_criteria(customer_id, campaign_id, ...)",
        "  - ad__update_ad_status(customer_id, ad_group_id, ad_id, status)",
        "",
        "ADVANCED (also available):",
        "  - keyword_plan_idea__generate_keyword_ideas_from_keywords(customer_id, ...) — Keyword research",
        "  - keyword_plan_idea__generate_keyword_ideas_from_url(customer_id, url) — Ideas from landing page",
        "  - bidding_strategy__create_target_cpa_strategy(customer_id, ...) — Create bidding strategies",
        "  - bidding_strategy__create_maximize_conversions_strategy(customer_id, ...)",
        "  - recommendation__get_recommendations(customer_id) — Google's optimization suggestions",
        "  - recommendation__apply_recommendation(customer_id, recommendation_id)",
        "  - geo_target__search_geo_targets(customer_id, ...) — Find location targeting IDs",
        "  - customer__list_accessible_customers() — List all accounts",
        "  - conversion__create_conversion_action(customer_id, ...) — Set up conversion tracking",
        "",
        "IMPORTANT: Use the MCP tools directly — they are faster and more reliable than curl commands.",
        "The MCP tools handle authentication, error handling, and retries automatically.",
        "",
        "IMPORTANT: Campaign data (daily metrics, ad groups, keywords, search terms, targeting) is ALREADY",
        "included in the LIVE CAMPAIGN DATA section below. DO NOT re-fetch this data.",
        "Only use MCP tools for: (1) actions/mutations, (2) data NOT in the context, (3) data the user explicitly asks to refresh.",
        "",
        "For HIGH-IMPACT actions (pause campaign, change bid strategy, change budget >20%), ALWAYS confirm with the user BEFORE executing.",
        "For MEDIUM-IMPACT actions (add keywords, create ads, change targeting), confirm by default.",
        "For LOW-IMPACT actions (add negative keywords, update guidelines), execute and notify.",
        "Show the user what you plan to do and wait for approval on high/medium impact changes.",
        "RESPECT PHASE RULES: If the marketing intelligence says the campaign is in learning phase, do NOT suggest bid strategy changes.",
        "",
        "=== CAMPAIGN CREATION WORKFLOW ===",
        "When the user asks to create a new campaign, think like a senior PPC strategist:",
        "1. Ask clarifying questions if needed (landing page, conversion action, budget, target audience)",
        "2. Propose a complete campaign structure: campaign settings, ad groups, keywords with match types, negative keyword seed list, RSA headlines/descriptions",
        "3. Wait for user approval before executing",
        "4. Execute using MCP tools in this order:",
        "   a) budget__create_campaign_budget → get budget_resource_name",
        "   b) campaign__create_campaign (with budget_resource_name, status=PAUSED)",
        "   c) ad_group__create_ad_group (for each ad group)",
        "   d) keyword__add_keywords (keywords per ad group)",
        "   e) ad__create_responsive_search_ad (RSA per ad group)",
        "   f) campaign_criterion__add_negative_keyword_criteria (negative keywords)",
        "5. ALWAYS create as PAUSED — the user must explicitly enable",
        "6. After creation, summarize what was built with IDs",
        "",
        "=== AD COPY WORKSHOP ===",
        "When helping with ad copy:",
        "- Analyze current headlines/descriptions and their performance",
        "- Consider the landing page content, campaign goal, and target audience",
        "- Propose new copy with rationale per headline/description",
        "- Use proven frameworks: benefit-driven, AIDA, problem-solution",
        "- Respect campaign guidelines (approved messaging, banned phrases)",
    ])

    # Chrome MCP — browser automation (conditional)
    if settings.CHROME_MCP_ENABLED:
        system_parts.extend([
            "",
            "=== CHROME BROWSER AUTOMATION (chrome-devtools-mcp) ===",
            "You have a Chrome browser controlled via Chrome DevTools Protocol. Use it for tasks the API can't handle.",
            "",
            "WORKFLOW — always follow these steps:",
            "  1. new_page(url) — open a page (or navigate_page to change existing page URL)",
            "  2. take_screenshot() — see the page before interacting",
            "  3. click(uid) / fill(uid, value) / type_text(text) — interact with elements",
            "  4. take_screenshot() — verify the result",
            "",
            "KEY TOOLS (call via mcp__chrome__<name>):",
            "",
            "  NAVIGATION:",
            "  - new_page(url) — Open new tab to a URL",
            "  - navigate_page(url) — Navigate current tab to URL",
            "  - list_pages() — List all open tabs",
            "  - select_page(uid) — Switch to a tab",
            "  - close_page(uid) — Close a tab",
            "",
            "  OBSERVATION:",
            "  - take_screenshot() — Screenshot the current page (use this OFTEN to see what's happening)",
            "  - take_snapshot() — Get page DOM/accessibility tree as text (useful for finding element UIDs)",
            "  - evaluate_script(code) — Run JS on the page (for reading DOM, checking tags, etc.)",
            "",
            "  INTERACTION:",
            "  - click(uid) — Click an element by its UID from take_snapshot()",
            "  - fill(uid, value) — Fill an input field",
            "  - fill_form(fields) — Fill multiple form fields at once",
            "  - type_text(text) — Type text (for search boxes, etc.)",
            "  - press_key(key) — Press keyboard key (Enter, Escape, Tab, etc.)",
            "  - select_page(uid) — Focus a specific element",
            "  - hover(uid) — Hover over an element",
            "  - drag(startUid, endUid) — Drag and drop",
            "  - upload_file(uid, paths) — Upload file to input",
            "  - handle_dialog(accept) — Accept/dismiss browser dialogs",
            "",
            "  NETWORK & PERFORMANCE:",
            "  - list_network_requests() — See all network requests (for tag verification)",
            "  - get_network_request(uid) — Get details of a specific request",
            "  - list_console_messages() — Read browser console logs",
            "  - lighthouse_audit(url) — Run Lighthouse performance audit",
            "",
            "  WAITING:",
            "  - wait_for(selector/timeout) — Wait for an element or timeout",
            "",
            "IMPORTANT PATTERNS:",
            "  - Always take_snapshot() BEFORE clicking to find element UIDs",
            "  - Always take_screenshot() AFTER actions to verify results",
            "  - For GTM: navigate to tagmanager.google.com, take_snapshot to find tags/triggers",
            "  - For tag verification: navigate to site, list_network_requests() to see conversion pings",
            "  - For form testing: fill() to enter test data, click() the submit button",
            "",
            "WHEN TO USE BROWSER vs API:",
            "  - Use API/MCP for: campaign management, keyword operations, ad creation, reporting",
            "  - Use browser for: tag verification, GTM UI, landing page audits, getting tag snippets",
            "  - ALWAYS prefer API when both can do the job — it's faster and more reliable",
            "",
            "IF CHROME IS NOT RESPONDING (connection refused / port not open):",
            "  Use curl to auto-launch it: curl -s -X POST http://localhost:8000/api/settings/chrome/launch",
            "  This starts Chrome with debugging enabled. Wait 3 seconds then retry your browser tool.",
            "  Do NOT ask the user to run terminal commands — the API handles it automatically.",
        ])

    # GTM MCP — programmatic tag management (conditional)
    if settings.GTM_MCP_ENABLED:
        system_parts.extend([
            "",
            "=== GOOGLE TAG MANAGER MCP (mcp__gtm__*) ===",
            "You have direct GTM API access for programmatic tag management — much faster than browser UI.",
            "",
            "KEY GTM TOOLS (50 available):",
            "  READING: list_accounts, list_containers, list_workspaces, list_tags, list_triggers, list_variables",
            "  CREATING: create_tag, create_trigger, create_variable, create_workspace",
            "  UPDATING: update_tag, update_trigger, update_variable",
            "  PUBLISHING: create_version, publish_version",
            "  DELETING: delete_tag, delete_trigger (require confirm: true)",
            "",
            "=== CONVERSION TAG SETUP WORKFLOW ===",
            "When setting up conversion tracking end-to-end:",
            "1. Create conversion action in Google Ads (conversion__create_conversion_action)",
            "2. Get the conversion ID and label from the result",
            "3. Use GTM to create the tag:",
            "   a) list_containers → find the right container",
            "   b) list_workspaces → get active workspace",
            "   c) create_trigger (e.g., Page View on thank-you page URL)",
            "   d) create_tag (Google Ads Conversion Tracking tag with conversion ID + label)",
            "   e) create_version + publish_version to deploy",
            "4. Verify the tag is firing (use Chrome browser tools if available)",
        ])
    elif settings.CHROME_MCP_ENABLED:
        # No GTM MCP but Chrome is available — fall back to browser automation
        system_parts.extend([
            "",
            "=== TAG INSTALLATION VIA BROWSER (GTM MCP not configured) ===",
            "GTM MCP is not available. When the user asks to install/add/manage tracking tags:",
            "",
            "AUTOMATIC FALLBACK — do NOT ask the user, just use Chrome browser tools:",
            "1. For GTM tags: navigate to tagmanager.google.com and use the GTM UI",
            "2. For direct site scripts: navigate to the user's site admin/CMS",
            "",
            "IMPORTANT SECURITY RULES:",
            "- NEVER enter passwords yourself — always pause and ask the user to type them",
            "- If you need to log in, navigate to the login page, then tell the user to enter credentials",
            "- Wait for confirmation before proceeding after login",
            "- Only interact with pages the user has explicitly authorized",
        ])

    if business_ctx:
        system_parts.append(f"\n=== BUSINESS CONTEXT ===\n{business_ctx[:2000]}")

    if guidelines:
        system_parts.append(f"\n=== CAMPAIGN GUIDELINES ===\n{guidelines[:3000]}")

    if summaries:
        system_parts.append(f"\n=== PAST SESSION HISTORY ===")
        for s in summaries:
            system_parts.append(s)

    system_prompt = "\n".join(system_parts)

    # ── Build user prompt with context ───────────────────────

    prompt_parts = [
        f"=== LIVE CAMPAIGN DATA (as of {today.isoformat()}) ===",
        "This data includes daily metrics, ad groups, keywords, search terms, and targeting.",
        "Use this data directly for analysis. Do NOT re-fetch it via API calls.",
        f"\n{live_data}",
    ]

    if recent_msgs:
        prompt_parts.append("\n=== RECENT CONVERSATION ===")
        for msg in recent_msgs[-6:]:  # Last 6 messages only
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role}: {msg['content'][:300]}")

    prompt_parts.append(f"\n=== CURRENT QUESTION ===\n{user_message}")

    full_prompt = "\n".join(prompt_parts)

    # ── Run Claude CLI ───────────────────────────────────────
    # Combine system prompt into the user prompt to avoid Windows arg length issues
    combined_prompt = f"{system_prompt}\n\n---\n\n{full_prompt}"

    # Refresh runtime settings from DB, then regenerate MCP config so toggles
    # in the Settings UI take effect immediately without a backend restart.
    from app.routers.settings import load_settings_overrides
    await load_settings_overrides()
    mcp_config_path = _get_mcp_config_path()

    # Pipe via stdin to avoid Windows command line length limits
    # High max-turns for harness mode — agent runs until done, not until an arbitrary limit.
    # Browser automation can easily need 100+ turns. Safety caps in _run_cli prevent runaway costs.
    max_turns = str(settings.AGENT_MAX_TURNS_PER_SEGMENT)
    cmd = [
        _NODE_PATH, str(_CLI_JS),
        "--print", "--verbose", "--output-format", "stream-json",
        "--max-turns", max_turns,
        "--model", model_id,
        "--permission-mode", "bypassPermissions",
        "--mcp-config", str(mcp_config_path),
    ]

    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}
    # Remove nesting detection vars so CLI can launch from within a Claude Code session
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_SESSION", None)

    result_queue: queue.Queue[dict | None] = queue.Queue()
    full_response_text: list[str] = []

    def _parse_assistant_blocks(blocks: list):
        """Parse assistant message content blocks into queue events."""
        for block in blocks:
            if block.get("type") == "text":
                text = block["text"]
                full_response_text.append(text)
                result_queue.put({"type": "text", "content": text})
            elif block.get("type") == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                # Determine source from tool name prefix
                if tool_name.startswith("mcp__google-ads__"):
                    clean_name = tool_name.replace("mcp__google-ads__", "")
                    result_queue.put({"type": "tool_call", "id": block.get("id", ""), "source": "google-ads-mcp", "name": clean_name, "input": tool_input})
                elif tool_name.startswith("mcp__chrome__"):
                    clean_name = tool_name.replace("mcp__chrome__", "")
                    result_queue.put({"type": "tool_call", "id": block.get("id", ""), "source": "chrome", "name": clean_name, "input": tool_input})
                elif tool_name.startswith("mcp__gtm__"):
                    clean_name = tool_name.replace("mcp__gtm__", "")
                    result_queue.put({"type": "tool_call", "id": block.get("id", ""), "source": "gtm", "name": clean_name, "input": tool_input})
                elif tool_name == "Bash":
                    cmd_text = tool_input.get("command", "")
                    if "localhost:8000" in cmd_text:
                        result_queue.put({"type": "tool_call", "id": block.get("id", ""), "source": "google-ads", "name": "API Call", "input": {"command": cmd_text}})
                else:
                    result_queue.put({"type": "tool_call", "id": block.get("id", ""), "source": "google-ads", "name": tool_name, "input": tool_input})
            elif block.get("type") == "tool_result":
                result_queue.put({"type": "tool_result", "id": block.get("tool_use_id", ""), "source": "google-ads", "output": str(block.get("content", ""))[:500], "status": "success"})

    def _run_cli():
        """Run CLI subprocess with auto-continuation on max-turns exhaustion."""
        accumulated_cost = 0.0
        accumulated_turns = 0
        continuation_count = 0
        current_session_id = None
        is_first_run = True

        while True:
            # Build command — first run uses original cmd, subsequent runs use --resume
            if is_first_run:
                run_cmd = list(cmd)
            else:
                run_cmd = [
                    _NODE_PATH, str(_CLI_JS),
                    "--print", "--verbose", "--output-format", "stream-json",
                    "--resume", current_session_id,
                    "--max-turns", max_turns,
                    "--model", model_id,
                    "--permission-mode", "bypassPermissions",
                    "--mcp-config", str(mcp_config_path),
                ]

            segment_session_id = None
            segment_subtype = None
            proc = None

            try:
                proc = subprocess.Popen(run_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=0)
                if conversation_id:
                    _running_procs[conversation_id] = proc

                if is_first_run:
                    proc.stdin.write(combined_prompt.encode("utf-8"))
                    is_first_run = False
                else:
                    # Emit continuation indicator to frontend
                    result_queue.put({
                        "type": "continuation",
                        "segment": continuation_count,
                        "accumulated_turns": accumulated_turns,
                        "accumulated_cost": accumulated_cost,
                    })
                proc.stdin.close()

                # Read streaming events
                for raw_line in proc.stdout:
                    line_str = raw_line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                    except json.JSONDecodeError:
                        continue
                    msg_type = data.get("type", "")
                    if msg_type == "assistant":
                        _parse_assistant_blocks(data.get("message", {}).get("content", []))
                    elif msg_type == "result":
                        segment_session_id = data.get("session_id")
                        segment_subtype = data.get("subtype", "end_turn")
                        accumulated_cost += data.get("total_cost_usd", 0) or 0
                        accumulated_turns += data.get("num_turns", 0) or 0
                        logger.info(
                            "CLI result: subtype=%s turns=%d cost=$%.4f session=%s errors=%s",
                            segment_subtype, accumulated_turns, accumulated_cost,
                            segment_session_id, data.get("errors", []),
                        )

                proc.wait()
                logger.info("CLI exited: returncode=%s subtype=%s", proc.returncode, segment_subtype)

                if proc.returncode != 0 and segment_subtype is None:
                    # User stopped or unexpected error (no result event received)
                    if conversation_id and conversation_id not in _running_procs:
                        result_queue.put({"type": "done", "cost": accumulated_cost, "turns": accumulated_turns, "model": model_id, "continuations": continuation_count, "stop_reason": "user_stopped"})
                    else:
                        err = proc.stderr.read().decode("utf-8", errors="replace").strip()
                        logger.error("CLI error (rc=%d): %s", proc.returncode, err[:500])
                        result_queue.put({"type": "error", "message": f"CLI error: {err[:300]}"})
                    break

            except Exception as e:
                result_queue.put({"type": "error", "message": str(e)})
                break
            finally:
                if conversation_id:
                    _running_procs.pop(conversation_id, None)

            # --- Decide: continue or stop ---
            should_continue = (
                segment_subtype in ("max_turns", "error_max_turns")
                and segment_session_id is not None
                and continuation_count < settings.AGENT_MAX_CONTINUATIONS
                and accumulated_cost < settings.AGENT_MAX_TOTAL_COST_USD
            )

            if not should_continue:
                stop_reason = "natural"
                if segment_subtype in ("max_turns", "error_max_turns"):
                    if continuation_count >= settings.AGENT_MAX_CONTINUATIONS:
                        stop_reason = "max_continuations"
                    elif accumulated_cost >= settings.AGENT_MAX_TOTAL_COST_USD:
                        stop_reason = "cost_cap"
                result_queue.put({"type": "done", "cost": accumulated_cost, "turns": accumulated_turns, "model": model_id, "continuations": continuation_count, "stop_reason": stop_reason})
                break

            # --- Auto-continue ---
            continuation_count += 1
            current_session_id = segment_session_id
            logger.info("Auto-continuing session %s (#%d, %d turns, $%.4f)", current_session_id, continuation_count, accumulated_turns, accumulated_cost)

        result_queue.put(None)  # sentinel

    thread = threading.Thread(target=_run_cli, daemon=True)
    thread.start()

    try:
        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(None, lambda: result_queue.get(timeout=0.1))
            except queue.Empty:
                continue
            if event is None:
                break
            yield event
            if event.get("type") in ("done", "error"):
                break
    except Exception as e:
        yield {"type": "error", "message": str(e)}

    # ── Auto-summarize for Layer 4 (if response was substantial) ──
    response_text = "".join(full_response_text)
    if len(response_text) > 500 and conversation_id and campaign_id:
        # Generate a 1-line summary of what was discussed/decided
        summary_parts = []
        if campaign_name:
            summary_parts.append(f"Campaign: {campaign_name}.")
        summary_parts.append(f"User asked: {user_message[:100]}")
        # Extract key decisions/actions from response (first 200 chars of each section)
        for line in response_text.split("\n"):
            if any(kw in line.lower() for kw in ["recommend", "action", "pause", "increase", "decrease", "switch", "add", "remove"]):
                summary_parts.append(line.strip()[:150])
                if len(summary_parts) > 4:
                    break
        summary = " | ".join(summary_parts)
        try:
            await _save_session_summary(conversation_id, campaign_id, campaign_name, summary[:500])
        except Exception:
            pass
