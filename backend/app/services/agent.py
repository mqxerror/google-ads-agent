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
_CLI_JS = Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js"
_GUIDELINES_DIR = settings.GUIDELINES_DIR

_ads_svc = GoogleAdsService()

AVAILABLE_MODELS = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


# ── Layer 1: Business Context ────────────────────────────────────

def _load_business_context() -> str:
    """Load the business context file (Layer 1 — always loaded, ~2K tokens)."""
    path = _GUIDELINES_DIR / "BUSINESS_CONTEXT.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# ── Layer 2: Campaign Guidelines ─────────────────────────────────

def _load_campaign_guidelines(campaign_name: str | None) -> str:
    """Load relevant guidelines for the campaign (Layer 2 — ~3K tokens)."""
    parts = []

    # Always load global rules from main guidelines
    main_file = _GUIDELINES_DIR / "CAMPAIGN_GUIDELINES.md"
    if main_file.exists():
        content = main_file.read_text(encoding="utf-8")
        # Extract global rules section
        lines = content.split("\n")
        in_global = False
        global_lines = []
        for line in lines:
            if "## Global Rules" in line:
                in_global = True
            elif in_global and line.startswith("## Campaign:"):
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
                if f"## Campaign:" in line and campaign_name.lower() in line.lower():
                    in_campaign = True
                elif in_campaign and line.startswith("## Campaign:"):
                    break
                if in_campaign:
                    campaign_lines.append(line)
            if campaign_lines:
                parts.append("\n".join(campaign_lines[:100]))

    # Load region-specific guidelines
    if campaign_name:
        name_lower = campaign_name.lower()
        if "mena" in name_lower or "arabic" in name_lower:
            mena_file = _GUIDELINES_DIR / "MENA_CAMPAIGN_GUIDELINES.md"
            if mena_file.exists():
                parts.append(mena_file.read_text(encoding="utf-8")[:2000])
        elif "greece" in name_lower:
            greece_file = _GUIDELINES_DIR / "GREECE_CAMPAIGN_GUIDELINES.md"
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


# ── Layer 5: Live Campaign Data ──────────────────────────────────

async def _get_campaign_data(account_id: str | None, campaign_id: str | None) -> str:
    """Fetch real-time campaign data (Layer 5 — ~3K tokens)."""
    parts = []
    today = date.today()

    if not account_id:
        return "No account selected."

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
    campaign_id = None
    if campaign_name:
        try:
            campaigns = await _ads_svc.get_campaigns(account_id or "7178239091")
            match = next((c for c in campaigns if c.name == campaign_name), None)
            if match:
                campaign_id = match.id
        except Exception:
            pass

    # ── Assemble layers ──────────────────────────────────────

    # Layer 1: Business context
    business_ctx = _load_business_context()

    # Layer 2: Campaign guidelines
    guidelines = _load_campaign_guidelines(campaign_name)

    # Layer 3: Recent conversation
    recent_msgs = []
    if conversation_id:
        recent_msgs = await _get_recent_messages(conversation_id, limit=10)

    # Layer 4: Past session summaries
    summaries = await _get_session_summaries(campaign_id, limit=5)

    # Layer 5: Live data
    live_data = await _get_campaign_data(account_id, campaign_id)

    # ── Build system prompt ──────────────────────────────────

    system_parts = [
        f"You are an expert Google Ads campaign manager for Mercan Group. Today is {today.isoformat()}.",
        "You have deep knowledge of the business, campaigns, and management rules.",
        "Always use specific numbers. Compare day-by-day when asked. Give actionable recommendations.",
        "When the user refers to 'this campaign', they mean the selected campaign shown in the context.",
        "",
        "IMPORTANT: You can fetch additional data and take actions using the local API at http://localhost:8000.",
        "Use curl commands to call these endpoints when you need more data or want to make changes:",
        "",
        "=== AVAILABLE API ENDPOINTS ===",
        "",
        "READ DATA:",
        f"  curl -s 'http://localhost:8000/api/accounts/7178239091/campaigns?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD'",
        f"  curl -s 'http://localhost:8000/api/accounts/7178239091/campaigns/CAMPAIGN_ID/adgroups'",
        f"  curl -s 'http://localhost:8000/api/accounts/7178239091/campaigns/CAMPAIGN_ID/keywords'",
        f"  curl -s 'http://localhost:8000/api/accounts/7178239091/campaigns/CAMPAIGN_ID/ads'",
        f"  curl -s 'http://localhost:8000/api/accounts/7178239091/campaigns/CAMPAIGN_ID/targeting'",
        "",
        "SEARCH TERMS (POST):",
        "  curl -s -X POST http://localhost:8000/api/operations/search-terms -H 'Content-Type: application/json' \\",
        f"    -d '{{\"customer_id\":\"7178239091\",\"campaign_id\":\"CAMPAIGN_ID\",\"date_from\":\"YYYY-MM-DD\",\"date_to\":\"YYYY-MM-DD\"}}'",
        "",
        "TAKE ACTIONS (POST):",
        "  # Pause/Enable campaign:",
        "  curl -s -X POST http://localhost:8000/api/operations/campaign/status -H 'Content-Type: application/json' \\",
        f"    -d '{{\"customer_id\":\"7178239091\",\"campaign_id\":\"ID\",\"status\":\"PAUSED\"}}'",
        "",
        "  # Change budget:",
        "  curl -s -X POST http://localhost:8000/api/operations/campaign/budget -H 'Content-Type: application/json' \\",
        f"    -d '{{\"customer_id\":\"7178239091\",\"campaign_id\":\"ID\",\"budget_micros\":200000000}}'",
        "",
        "  # Add keyword:",
        "  curl -s -X POST http://localhost:8000/api/operations/keyword/add -H 'Content-Type: application/json' \\",
        f"    -d '{{\"customer_id\":\"7178239091\",\"campaign_id\":\"ID\",\"ad_group_id\":\"AG_ID\",\"keyword_text\":\"text\",\"match_type\":\"EXACT\"}}'",
        "",
        "  # Pause/Enable keyword:",
        "  curl -s -X POST http://localhost:8000/api/operations/keyword/status -H 'Content-Type: application/json' \\",
        f"    -d '{{\"customer_id\":\"7178239091\",\"keyword_criterion_id\":\"KW_ID\",\"ad_group_id\":\"AG_ID\",\"status\":\"PAUSED\"}}'",
        "",
        "  # Add negative keyword:",
        "  curl -s -X POST http://localhost:8000/api/operations/campaign/negative-keyword -H 'Content-Type: application/json' \\",
        f"    -d '{{\"customer_id\":\"7178239091\",\"campaign_id\":\"ID\",\"keyword_text\":\"text\",\"match_type\":\"EXACT\"}}'",
        "",
        "Use these endpoints to fetch data you need or execute actions the user requests.",
        "For mutating actions (pause, budget change, add keyword), ALWAYS confirm with the user BEFORE executing.",
        "Show the user what you plan to do and wait for approval.",
    ]

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

    prompt_parts = [f"=== LIVE CAMPAIGN DATA (as of {today.isoformat()}) ===\n{live_data}"]

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

    # Pipe via stdin to avoid Windows command line length limits
    cmd = [
        _NODE_PATH, str(_CLI_JS),
        "--print", "--verbose", "--output-format", "stream-json",
        "--max-turns", "15",
        "--model", model_id,
        "--permission-mode", "bypassPermissions",
    ]

    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}

    result_queue: queue.Queue[dict | None] = queue.Queue()
    full_response_text: list[str] = []

    def _run_cli():
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=0)
            # Send prompt via stdin
            proc.stdin.write(combined_prompt.encode("utf-8"))
            proc.stdin.close()
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
                    for block in data.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            text = block["text"]
                            full_response_text.append(text)
                            result_queue.put({"type": "text", "content": text})
                        elif block.get("type") == "tool_use":
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})
                            # Show API calls to the user
                            if tool_name == "Bash":
                                cmd_text = tool_input.get("command", "")
                                if "localhost:8000" in cmd_text:
                                    result_queue.put({
                                        "type": "tool_call",
                                        "id": block.get("id", ""),
                                        "source": "google-ads",
                                        "name": "API Call",
                                        "input": {"command": cmd_text},
                                    })
                            else:
                                result_queue.put({
                                    "type": "tool_call",
                                    "id": block.get("id", ""),
                                    "source": "google-ads",
                                    "name": tool_name,
                                    "input": tool_input,
                                })
                        elif block.get("type") == "tool_result":
                            result_queue.put({
                                "type": "tool_result",
                                "id": block.get("tool_use_id", ""),
                                "source": "google-ads",
                                "output": str(block.get("content", ""))[:500],
                                "status": "success",
                            })
                elif msg_type == "result":
                    result_queue.put({"type": "done", "cost": data.get("total_cost_usd"), "turns": data.get("num_turns"), "model": model_id})
            proc.wait()
            if proc.returncode != 0:
                err = proc.stderr.read().decode("utf-8", errors="replace").strip()
                result_queue.put({"type": "error", "message": f"CLI error: {err[:300]}"})
        except Exception as e:
            result_queue.put({"type": "error", "message": str(e)})
        finally:
            result_queue.put(None)

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
