"""Claude Code agent service — layered memory system."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import re
import threading
import queue
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import AsyncIterator

from app.config import settings
from app.database import get_db
from app.services.google_ads import GoogleAdsService
from app.services.token_counter import (
    TokenBudget, LayerAllocation, allocate_budget, build_layer_breakdown,
    P_CRITICAL, P_IMPORTANT, P_NICE_TO_HAVE, P_DROPPABLE,
)
from app.services.message_selector import select_relevant_messages, format_selected_messages
from app.services.campaign_memory import build_campaign_context
from app.services import campaigns_repo
from app.services.compaction import (
    get_compaction_status, compact_conversation, load_checkpoint_context,
    WARN_THRESHOLD, COMPACT_THRESHOLD,
)

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

# Native-binary install location (curl installer) — the operator's actual
# logged-in, auto-updating CLI. The npm cli.js copy on this machine can be
# 100+ builds stale, so the native binary must win discovery.
_NATIVE_CLAUDE = Path.home() / ".local/bin/claude"


def _find_cli() -> list[str]:
    """Resolve the CLI launch argv prefix, preferring the native binary.

    Resolution order:
    1. ``~/.local/bin/claude`` exists (native-binary install) → ``[that path]``
       directly, no node. Checked explicitly FIRST because ``shutil.which``
       can miss ``~/.local/bin`` under a stripped PATH (pm2/nohup) or resolve
       a wrapper script instead.
    2. npm ``cli.js`` exists (legacy layout) → ``[node, cli.js]``.
    3. ``shutil.which("claude")`` → ``[that path]``.
    4. Nothing found → the best-guess ``[node, cli.js]`` so the spawn raises
       a clear FileNotFoundError.
    """
    if _NATIVE_CLAUDE.exists():
        return [str(_NATIVE_CLAUDE)]
    if _CLI_JS.exists():
        return [_NODE_PATH, str(_CLI_JS)]
    which_claude = shutil.which("claude")
    if which_claude:
        return [which_claude]
    return [_NODE_PATH, str(_CLI_JS)]


_CLI_CMD = _find_cli()
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

# Track running agent subprocesses by conversation_id so users can cancel stuck
# tasks. Value is a SET because parallel workflow specialists share one
# conversation_id and each registers its own CLI child — a dict would clobber
# all but the last, letting a stop reach only one (possibly the wrong) process.
_running_procs: dict[str, set[subprocess.Popen]] = {}

# Conversation ids for which a stop was requested. Set by stop_agent (even when
# no proc is registered — a stop that lands between segments must still block
# the continuation relaunch) and consulted by _run_cli. Cleared at the top of a
# fresh stream_agent_response run so a later legit message isn't perma-blocked.
_stop_requested: set[str] = set()

# ── Chat Orchestration v2 process registry (Epic 1.5/1.6/2.6) ────────
# A SECOND, distinct registry keyed by (turn_id, call_id) that lives ALONGSIDE
# the conversation-keyed _running_procs above. The v2 chat turn runner threads a
# `proc_key=(turn_id, call_id)` through stream_agent_response; when set, _run_cli
# ALSO registers/deregisters the Popen here so a per-turn or per-specialist stop
# reaches exactly the right child (the conversation-keyed path is last-writer-
# wins across parallel specialists — the F7 bug). call_id for a direct-mode turn
# is the literal "director"; specialists use the plan's call_id (c1, c2, …). The
# Epic 0 conversation-keyed logic is untouched — this is purely additive.
_turn_procs: dict[tuple[str, str], set[subprocess.Popen]] = {}

# (turn_id, call_id) OR (turn_id, "*") entries for which a stop was requested.
# A (turn_id, "*") entry is a whole-turn stop and also blocks the continuation
# relaunch for every call under that turn. Consulted by _run_cli's guard sites.
_turn_stop_requested: set[tuple[str, str]] = set()


def _turn_stop_pending(proc_key: tuple[str, str] | None) -> bool:
    """True if a v2 stop was requested for this proc_key or its whole turn.

    A `(turn_id, call_id)` stop blocks just that call; a `(turn_id, "*")` stop
    (whole-turn) blocks every call under the turn — including a would-be
    continuation relaunch. Returns False when proc_key is None (direct/legacy
    callers ride the conversation-keyed path only).
    """
    if proc_key is None:
        return False
    return proc_key in _turn_stop_requested or (proc_key[0], "*") in _turn_stop_requested


def _killpg(proc: subprocess.Popen) -> bool:
    """Kill a subprocess's WHOLE process group: SIGTERM, wait 2s, then SIGKILL.

    Popen is created with start_new_session=True (agent.py:1608) so the CLI is
    its own process-group leader and this reaches its children (google-ads MCP
    via uv, chrome MCP via npx, headless Chrome). Returns True if a signal was
    delivered; an already-dead group counts as a successful stop (True).
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
        return True
    except (ProcessLookupError, OSError):
        # Process (group) already gone — treat as a successful stop.
        return True


def stop_agent(conversation_id: str) -> bool:
    """Stop all running agent subprocesses for the given conversation.

    Kills each registered CLI child's WHOLE process group (SIGTERM, then
    SIGKILL after a short grace) so the CLI's own children (google-ads MCP via
    uv, chrome MCP via npx, headless Chrome) die with it. ALWAYS flags the
    conversation as stop-requested so a stop between segments still blocks the
    continuation relaunch. Returns True if any process was killed.
    """
    # Flag first — a stop between segments (no proc registered right now) must
    # still block the continuation loop from relaunching.
    _stop_requested.add(conversation_id)
    procs = set(_running_procs.get(conversation_id, set()))
    killed = False
    try:
        for proc in procs:
            killed = True
            _killpg(proc)
        return killed
    finally:
        _running_procs.pop(conversation_id, None)


def stop_turn(turn_id: str) -> dict:
    """Process-level stop for a whole v2 chat turn.

    Flags `(turn_id, "*")` as stop-requested (blocks any pending continuation
    relaunch for every call under the turn) and process-group-kills every child
    registered under any `(turn_id, *)` key. Idempotent: a second call finds no
    live procs and returns an empty `killed` list. Returns the list of call_ids
    whose process groups were signalled.

    NOTE: this is the PROCESS half only. The chat_runner owns the asyncio task
    cancel + terminal `turn_stopped` event + chat_turns.status flip and calls
    this for the killpg.
    """
    _turn_stop_requested.add((turn_id, "*"))
    killed: list[str] = []
    # Snapshot the keys first — _killpg may mutate nothing here, but popping
    # while iterating the dict would raise.
    keys = [k for k in list(_turn_procs.keys()) if k[0] == turn_id]
    for key in keys:
        procs = set(_turn_procs.get(key, set()))
        if procs:
            killed.append(key[1])
            for proc in procs:
                _killpg(proc)
        _turn_procs.pop(key, None)
    return {"turn_id": turn_id, "killed": killed}


def stop_call(turn_id: str, call_id: str) -> dict:
    """Process-level stop for ONE specialist call within a turn (story 2.6).

    Flags `(turn_id, call_id)` as stop-requested and process-group-kills only
    that call's registered children; the rest of the turn continues. Idempotent.
    Returns `{killed: bool}` — True if any process was signalled for the call.
    """
    _turn_stop_requested.add((turn_id, call_id))
    procs = set(_turn_procs.get((turn_id, call_id), set()))
    killed = False
    for proc in procs:
        killed = True
        _killpg(proc)
    _turn_procs.pop((turn_id, call_id), None)
    return {"turn_id": turn_id, "call_id": call_id, "killed": killed}


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
                # Full 311-tool surface (assets/extensions, batch, planning, etc.)
                # — restores the 2026-06-16 Windows-session decision that never
                # synced to this Mac. Tool-mispick risk contained by the campaign
                # scope-guard middleware + per-agent allowlist + approval flow.
                "--groups", "all",
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

    # Microsoft Clarity MCP — heatmaps, session recordings, behavioral analytics
    if settings.CLARITY_MCP_ENABLED and settings.CLARITY_API_TOKEN:
        clarity_npx = _MODERN_NPX if settings.CHROME_MCP_COMMAND == "npx" else (shutil.which("npx") or "npx")
        servers["clarity"] = {
            "type": "stdio",
            "command": clarity_npx,
            "args": ["-y", "@microsoft/clarity-mcp-server", f"--clarity_api_token={settings.CLARITY_API_TOKEN}"],
        }

    config = {"mcpServers": servers}
    config_path = _BACKEND_DIR / "data" / "mcp_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2))
    return config_path



_ads_svc = GoogleAdsService()

AVAILABLE_MODELS = {
    # "fable" is the default (claude-fable-5[1m], 1M-context variant). If the
    # bracket notation ever breaks on the CLI, fall back to plain "claude-fable-5".
    "fable": "claude-fable-5[1m]",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
    "haiku": "claude-haiku-4-5-20251001",
}

# ── Usage/rate-limit fallback ───────────────────────────────────
# The configured model (default Fable 5) can hit a usage cap or per-minute
# rate limit on this subscription. When that happens the CLI's stream-json
# `result` event carries a non-success subtype / error, or the process exits
# non-zero with a "usage limit" / "rate limit" / "limit reached" / 429 line on
# stderr. Rather than surface a hard failure, we retry the SAME prompt ONCE
# with the model swapped to Opus 4.8 (a distinct model that isn't sharing
# Fable's cap). Mirrors the meta-ads-agent claude_runner fallback contract.
_FALLBACK_MODEL = "claude-opus-4-8"
# Case-insensitive signals for a transient usage/rate/limit condition, matched
# against the CLI's result-event error, stderr, and any api_retry event error.
_LIMIT_RE = re.compile(r"usage limit|rate limit|limit reached|429", re.I)


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
                parts.append(mena_file.read_text(encoding="utf-8"))
        elif "greece" in name_lower:
            greece_file = gdir / "GREECE_CAMPAIGN_GUIDELINES.md"
            if greece_file.exists():
                parts.append(greece_file.read_text(encoding="utf-8"))

    return "\n\n".join(parts)


# ── Layer 3: Recent Conversation (sliding window) ────────────────

async def _get_recent_messages(
    conversation_id: str,
    limit: int = 30,
    campaign_id: str | None = None,
) -> list[dict]:
    """Get the last N messages with role attribution (Layer 3).

    When campaign_id is supplied, only messages tagged with that campaign (or
    pre-migration untagged rows) are returned. This prevents cross-campaign
    context from leaking when the user switches campaigns on the same
    conversation.

    Returns full content (no truncation) — the message selector handles
    relevance-based filtering and the token budget enforces size limits.
    """
    db = await get_db()
    try:
        if campaign_id:
            cur = await db.execute(
                "SELECT role, content, created_at, agent_role, agent_role_name FROM messages "
                "WHERE conversation_id = ? AND (campaign_id = ? OR campaign_id IS NULL) "
                "ORDER BY created_at DESC LIMIT ?",
                (conversation_id, campaign_id, limit),
            )
        else:
            cur = await db.execute(
                "SELECT role, content, created_at, agent_role, agent_role_name FROM messages WHERE conversation_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (conversation_id, limit),
            )
        rows = await cur.fetchall()
        result = []
        for r in reversed(rows):
            entry = {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
            # Add role attribution for assistant messages
            if r["role"] == "assistant" and r["agent_role_name"]:
                entry["agent_role"] = r["agent_role"]
                entry["agent_role_name"] = r["agent_role_name"]
            result.append(entry)
        return result
    finally:
        await db.close()


# ── Layer 4: Session Summaries (compressed history) ──────────────

async def _get_session_summaries(campaign_id: str | None, limit: int | None = None) -> list[str]:
    """Get past session summaries with tiered compression.

    Recent 5: full text
    Older: grouped by month ("March 2026 (12 sessions): keyword optimization, CRO audit...")
    """
    if not campaign_id:
        return []
    db = await get_db()
    try:
        query = "SELECT summary, created_at FROM session_summaries WHERE campaign_id = ? ORDER BY created_at DESC"
        params: list = [campaign_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        if not rows:
            return []

        all_summaries = list(reversed(rows))
        recent_count = 5

        if len(all_summaries) <= recent_count:
            return [f"[{r['created_at']}] {r['summary']}" for r in all_summaries]

        # Recent 5: full detail
        recent = all_summaries[-recent_count:]
        older = all_summaries[:-recent_count]

        # Compress older by month
        months: dict[str, list[str]] = {}
        for r in older:
            month_key = (r["created_at"] or "")[:7]
            if month_key not in months:
                months[month_key] = []
            # Take first 30 chars of each summary as a keyword
            snippet = (r["summary"] or "")[:40].strip()
            months[month_key].append(snippet)

        result = []
        for month_key in sorted(months.keys()):
            snippets = months[month_key]
            try:
                from datetime import datetime as dt
                month_label = dt.strptime(month_key, "%Y-%m").strftime("%B %Y")
            except (ValueError, TypeError):
                month_label = month_key
            topics = ", ".join(dict.fromkeys(s for s in snippets[:4] if s))
            result.append(f"[{month_label}] ({len(snippets)} sessions): {topics}")

        result.append("--- Recent sessions ---")
        for r in recent:
            result.append(f"[{r['created_at']}] {r['summary']}")

        return result
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


# ── Resumable session (recover work after a cost-cap / max-turn stop) ──

# Stops where the task is unfinished but the Claude session can be resumed.
_RESUMABLE_STOPS = {"cost_cap", "max_continuations", "user_stopped"}


async def _take_resume_session(conversation_id: str | None) -> str | None:
    """Read and CLEAR the stored resume session id for a conversation.

    Consume-once: returning it also nulls it so a later unrelated message in
    the same conversation doesn't keep resuming a huge stale session. If the
    resumed run stops again unfinished, it's re-saved by _save_resume_session.
    """
    if not conversation_id:
        return None
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT resume_session_id FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = await cur.fetchone()
        sid = row["resume_session_id"] if row else None
        if sid:
            await db.execute(
                "UPDATE conversations SET resume_session_id = NULL WHERE id = ?",
                (conversation_id,),
            )
            await db.commit()
        return sid
    except Exception:
        return None
    finally:
        await db.close()


async def _save_resume_session(conversation_id: str | None, session_id: str | None) -> None:
    """Persist the Claude session id so the next message can --resume it."""
    if not conversation_id or not session_id:
        return
    db = await get_db()
    try:
        await db.execute(
            "UPDATE conversations SET resume_session_id = ? WHERE id = ?",
            (session_id, conversation_id),
        )
        await db.commit()
    except Exception:
        pass
    finally:
        await db.close()


# ── Layer 5: Campaign Data (local-first, API fallback) ──────────

async def _get_campaign_data(account_id: str | None, campaign_id: str | None) -> str:
    """Get campaign data — reads from local metrics store first (milliseconds),
    falls back to live API only if no local data exists.

    All numeric values are in the account's billing currency (USD for the
    Mercan account). Every block is prefixed with a Currency: header so each
    role sees the unit inline and doesn't reach for outside £/€ benchmarks.
    """
    if not account_id:
        return "No account selected."

    # Currency anchor for everything below. The account is billed in USD,
    # so cost_micros / budget_micros are already USD. Surface that explicitly.
    currency_header = (
        "Currency: USD (account billing currency — every $ figure below is in USD).\n"
        "If a recommendation needs to compare against UK/EU CPC norms, convert those to USD first.\n\n"
    )

    # Try local metrics store first (fast — no API calls)
    from app.services.metrics_store import MetricsStore
    metrics_store = MetricsStore()

    has_local = await metrics_store.has_recent_data(account_id, days=2)
    if has_local:
        local_data = await metrics_store.format_for_agent(account_id, campaign_id, None)
        if local_data and "No local metrics" not in local_data:
            # WS2 — even on the fast local-metrics path, fetch the live landing
            # page so page/form/tracking claims aren't diagnosed off stale data
            # (the exact post-mortem failure). Best-effort; never blocks the read.
            lp = ""
            if campaign_id:
                try:
                    lp = await fetch_ad_landing_pages(account_id, campaign_id)
                except Exception:
                    lp = ""
            lp_block = ("\n\n" + lp) if lp else ""
            return (currency_header + local_data +
                    "\n\n(Data from local store. Use API endpoints for real-time data if needed.)"
                    + lp_block)

    # Fallback: fetch from API (slow but always fresh)
    parts = [currency_header.rstrip()]
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
                parts.append(f"\nAd Groups ({len(adgroups)}) — id | name | status | clicks | conv:")
                for ag in adgroups:
                    parts.append(f"  - {ag.id} | {ag.name} | {ag.status} | {ag.metrics.clicks} clicks | {ag.metrics.conversions} conv")
            except Exception:
                pass

            # Ads + final/landing URLs so URL-change requests don't trigger
            # tool spelunking (and the page_size tool errors that follow).
            try:
                ads = await _ads_svc.get_ads(account_id, campaign_id)
                parts.append(f"\nAds ({len(ads)}) — ad ID | ad group | status | final URL:")
                for ad in ads:
                    url = ad.final_urls[0] if ad.final_urls else "(no final URL)"
                    parts.append(f"  - {ad.id} | {ad.ad_group_name} | {ad.status} | {url}")
            except Exception:
                pass

            # WS2 — fetch the actual landing pages THIS session so page/form/
            # tracking claims are verified against live HTML, not stale memory.
            try:
                lp = await fetch_ad_landing_pages(account_id, campaign_id)
                if lp:
                    parts.append("\n" + lp)
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

        # Account-wide ENABLED campaigns summary — reads from the V11
        # single-source-of-truth `campaigns` table via campaigns_repo so the
        # agent's view matches the sidebar's exactly (no stale-by-5-min drift).
        # Metrics aren't included here — this list is for "what's running right
        # now"; per-campaign metrics already appear elsewhere in the context.
        try:
            enabled = await campaigns_repo.list_campaigns(account_id, status="ENABLED")
            parts.append(f"\nAll ENABLED campaigns (currently {len(enabled)}):")
            for c in enabled:
                budget = (c.get("budget_micros") or 0) / 1_000_000
                parts.append(
                    f"  - {c.get('name')}: ${budget}/d, "
                    f"{c.get('bidding_strategy') or '—'}"
                )
        except Exception as e:
            parts.append(f"\nAll ENABLED campaigns: could not load ({e})")

    except Exception as e:
        parts.append(f"Error: {e}")

    return "\n".join(parts)


# ── WS2: verify-before-diagnose — live landing-page state ──────────

# CONSERVATIVE cap: fetch at most this many DISTINCT final URLs per call so an
# ordinary campaign chat doesn't fan out into many synchronous fetches. Tune here.
_MAX_LANDING_FETCH = 3

# Stripped-text signals (page_fetcher returns text, not raw HTML) that a lead
# form / contact affordance is present, and that a tag/tracking token is present.
_FORM_SIGNALS = ('<form', 'type="email"', 'type=email', 'type="tel"',
                 'type=tel', 'mailto:', 'tel:')
_TRACKING_SIGNALS = ('gtag', 'gtm', 'datalayer', 'googletagmanager')


async def fetch_ad_landing_pages(account_id: str | None, campaign_id: str | None) -> str:
    """Best-effort: fetch THIS campaign's ad final_urls THIS session so a persona
    can verify page/form/tracking claims against the live page (not month-old
    memory). Returns a compact text block, or "" when nothing to fetch.

    NEVER raises — every failure degrades to a labelled UNKNOWN line so the caller
    (and the persona) treats page state as unverified rather than assumed.
    """
    if not account_id or not campaign_id:
        return ""

    from app.services import page_fetcher

    # Collect + dedupe final URLs across the campaign's ads, cap at _MAX_LANDING_FETCH.
    urls: list[str] = []
    try:
        ads = await _ads_svc.get_ads(account_id, campaign_id)
    except Exception:
        return ""
    for ad in ads:
        for u in (ad.final_urls or []):
            if u and u not in urls:
                urls.append(u)
            if len(urls) >= _MAX_LANDING_FETCH:
                break
        if len(urls) >= _MAX_LANDING_FETCH:
            break

    if not urls:
        return ""

    lines = ["=== LIVE LANDING PAGE STATE (fetched this session) ===",
             "(Verify page/form/tracking claims against THIS, not stored findings.)"]
    for url in urls:
        try:
            page = await page_fetcher.fetch(url)
        except Exception:
            lines.append(f"- {url} → COULD NOT FETCH — treat page state as UNKNOWN")
            continue
        # body_excerpt is stripped text; search it + h1 + title defensively.
        hay = " ".join(str(x or "") for x in (
            page.body_excerpt, page.h1, page.title, page.description)).lower()
        form_hit = any(sig in hay for sig in _FORM_SIGNALS) or ("@" in hay and "email" in hay)
        track_hit = any(sig in hay for sig in _TRACKING_SIGNALS)
        title = (page.title or "").strip()[:80] or "(no title)"
        h1 = (page.h1 or "").strip()[:80] or "(no h1)"
        lines.append(
            f"- {url} → HTTP {page.status} | title: {title} | h1: {h1} | "
            f"form signal: {'YES' if form_hit else 'none detected'} | "
            f"tracking token: {'YES' if track_hit else 'none detected'}"
        )
    return "\n".join(lines)


async def fetch_conversion_actions(account_id: str | None) -> tuple[str, list[dict]]:
    """Best-effort: pull THIS account's ENABLED conversion actions LIVE this turn
    so the Director's "which conversion actions exist" claims trace to the live
    account, not a stale/remembered registry (Fix 4).

    Returns (block, rows):
      * block — a compact text block for context injection + provenance harvest,
        or "" when there is nothing to fetch / the fetch failed.
      * rows  — the structured list [{id, name, status, primary_for_goal}, ...],
        or [] on failure.

    NEVER raises — every failure degrades to ("", []) so the caller treats the
    registry as simply unrefreshed rather than crashing the turn.
    """
    if not account_id:
        return "", []
    try:
        rows = await _ads_svc.get_conversion_actions(account_id)
    except Exception:
        return "", []
    if not rows:
        return "", []

    lines = [
        "LIVE CONVERSION ACTIONS (fetched this turn — supersedes any remembered "
        "registry):",
    ]
    for ca in rows:
        primary = "YES" if ca.get("primary_for_goal") else "no"
        lines.append(
            f"- {ca.get('name')} (id {ca.get('id')}) "
            f"status={ca.get('status')} primary={primary}"
        )
    return "\n".join(lines), rows


def _condense_for_memory(response_text: str, user_message: str, max_chars: int = 3000) -> str:
    """Condense an agent response into a memory-friendly format.

    Priority: preserve operational details (IDs, labels, URLs, container names)
    that the next role MUST know to continue work correctly.
    """
    import re
    lines = response_text.split("\n")
    parts = [f"**Task:** {user_message[:200]}"]

    # FIRST: Extract critical operational details that must never be lost
    critical_patterns = [
        (r'GTM-[A-Z0-9]+', 'GTM Container'),
        (r'AW-\d+', 'Google Ads Account'),
        (r'Conversion ID:\s*\d+', 'Conversion ID'),
        (r'Label:\s*[\w-]+', 'Conversion Label'),
        (r'(?:https?://[^\s<>"]+)', 'URL'),
        (r'campaign[_\s]?id[=:\s]+\d+', 'Campaign ID'),
    ]
    found_critical = set()
    for pattern, label in critical_patterns:
        for match in re.finditer(pattern, response_text, re.IGNORECASE):
            val = match.group(0)
            if val not in found_critical:
                found_critical.add(val)

    if found_critical:
        parts.append(f"\n**Critical Details:** {', '.join(found_critical)}")

    # THEN: Keep headings, key findings, recommendations — skip noise
    skip_section = False
    kept_chars = 0
    for line in lines:
        ls = line.strip()
        if not ls:
            continue
        if ls.startswith("```") or ls.startswith("---"):
            skip_section = not skip_section if ls.startswith("```") else False
            continue
        if skip_section:
            continue
        if ls.count("|") > 3 and any(c.isdigit() for c in ls):
            continue
        parts.append(ls[:400])
        kept_chars += len(ls)
        if kept_chars >= max_chars:
            parts.append("... (truncated)")
            break

    return "\n".join(parts)


# ── Story 1.4: partial-message streaming ─────────────────────────

def _extract_stream_text_delta(data: dict) -> str:
    """Pull the incremental text out of a CLI `stream_event` line.

    With --include-partial-messages the CLI wraps Anthropic streaming events:
    {"type":"stream_event","event":{"type":"content_block_delta",
     "delta":{"type":"text_delta","text":"<chunk>"}}}
    Returns the text chunk for a content_block_delta/text_delta, else "".
    Tolerant of missing keys / other event shapes (returns "").
    """
    event = data.get("event")
    if not isinstance(event, dict) or event.get("type") != "content_block_delta":
        return ""
    delta = event.get("delta")
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return ""
    text = delta.get("text")
    return text if isinstance(text, str) else ""


def _emit_assistant_blocks(blocks: list, result_queue, full_response_text: list, *, stream_partial: bool) -> None:
    """Parse assistant message content blocks into queue events.

    Module-level (extracted from the `_run_cli` closure) so the Story 1.4 dedup
    rule is unit-testable. `full_response_text` MUST accumulate text in BOTH
    modes (it feeds persistence + findings-JSON parsing). When `stream_partial`
    is True the token-level `text_delta` events already streamed the text, so
    the `text` event is suppressed here to avoid DOUBLING — but tool_use /
    tool_result blocks are always emitted.
    """
    for block in blocks:
        if block.get("type") == "text":
            text = block["text"]
            full_response_text.append(text)
            if not stream_partial:
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


# ── Main: Assemble All Layers ────────────────────────────────────

async def stream_agent_response(
    user_message: str,
    account_id: str | None = None,
    campaign_id: str | None = None,
    campaign_name: str | None = None,
    conversation_id: str | None = None,
    base_guidelines: str | None = None,
    campaign_guidelines: str | None = None,
    model: str = "fable",
    active_role: str | None = None,
    attachments: list[dict] | None = None,
    tool_allowlist: list[str] | None = None,
    proc_key: tuple[str, str] | None = None,
) -> AsyncIterator[dict]:
    """Stream agent responses with full layered memory.

    tool_allowlist: when provided, restricts the Google Ads MCP tools this run
    may call to names containing any of these substrings (enforced physically
    by CampaignScopeMiddleware via the LANGAR_AGENT_TOOL_ALLOWLIST env var).
    An empty list means "no Google Ads tools" — pure analysis of injected
    context, which is the safest mode for rate-limited audit workflows. None
    means unrestricted (normal chat behaviour).

    proc_key: OPTIONAL (turn_id, call_id) for Chat Orchestration v2. When set,
    _run_cli ALSO registers/deregisters the CLI Popen under _turn_procs[proc_key]
    and consults _turn_stop_requested for both proc_key and (proc_key[0], "*") at
    both stop-guard sites, so a per-turn / per-specialist stop reaches exactly
    this child. The Epic 0 conversation-keyed path (_running_procs /
    _stop_requested) stays intact and unchanged; this is purely additive.
    """
    from app.services.roles import classify_intent, get_role, get_default_role

    model_id = AVAILABLE_MODELS.get(model, AVAILABLE_MODELS["fable"])
    today = date.today()

    # Fresh run for this conversation clears any prior stop request so a later
    # legit message isn't perma-blocked by an earlier stop (see _stop_requested).
    if conversation_id:
        _stop_requested.discard(conversation_id)

    # ── Intent classification → resolve role ────────────────
    intent = classify_intent(user_message)
    resolved_role = active_role or intent["role_id"]
    role_obj = get_role(resolved_role) or get_default_role()

    # Emit routing info to frontend
    yield {
        "type": "routing",
        "gear": intent["gear"],
        "role_id": role_obj.id,
        "role_name": role_obj.name,
        "role_avatar": role_obj.avatar,
        "confidence": intent["confidence"],
        "reason": intent["reason"],
    }

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

    # Use passed-in campaign_id directly (from conversation record)
    # Only fall back to name lookup if no ID was provided. Reads from the
    # V11 campaigns table — same source as the sidebar — so a "campaign
    # named X" lookup can't disagree with the UI.
    if not campaign_id and campaign_name:
        try:
            campaigns = await campaigns_repo.list_campaigns(api_account_id)
            match = next((c for c in campaigns if c.get("name") == campaign_name), None)
            if match:
                campaign_id = str(match.get("campaign_id"))
        except Exception:
            pass

    # ── Load all context layers ──────────────────────────────

    # Layer 0: Marketing Intelligence
    marketing_intel = await _get_marketing_intelligence(account_id, campaign_id, campaign_name)

    # Layer 1: Business context
    business_ctx = _load_business_context(account_id)

    # Layer 2: Campaign guidelines
    guidelines = _load_campaign_guidelines(campaign_name, account_id)

    # Layer 3: Recent conversation (load more, select smartly)
    all_recent_msgs = []
    if conversation_id:
        all_recent_msgs = await _get_recent_messages(conversation_id, limit=30, campaign_id=campaign_id)

    # Layer 4: Past session summaries
    summaries = await _get_session_summaries(campaign_id, limit=5)

    # Layer 5: Live data
    live_data = await _get_campaign_data(api_account_id, campaign_id)

    # Layer 6: Campaign memory (decisions, pinned facts, role notes)
    campaign_memory_ctx = ""
    if account_id and campaign_id:
        campaign_memory_ctx = build_campaign_context(account_id, campaign_id, active_role=role_obj.id if role_obj else None)

    # Layer 7: Outcome history (what worked, what didn't)
    outcome_ctx = ""
    if account_id and campaign_id:
        try:
            from app.services.outcome_tracker import get_outcomes_for_prompt
            outcome_ctx = await get_outcomes_for_prompt(account_id, campaign_id)
        except Exception:
            pass

    # Layer 8: Campaign chronicle (long-term structured timeline)
    chronicle_ctx = ""
    if account_id and campaign_id:
        try:
            from app.services.chronicle import load_chronicle
            chronicle_ctx = load_chronicle(account_id, campaign_id)
        except Exception:
            pass

    # Layer 9: Conversation checkpoint (compressed older messages)
    checkpoint_ctx = ""
    if conversation_id:
        checkpoint_ctx = await load_checkpoint_context(conversation_id)

    # Smart message selection — relevance-based instead of blind window
    selected_msgs = select_relevant_messages(
        query=user_message,
        messages=all_recent_msgs,
        max_messages=settings.CONTEXT_MAX_SELECTED_MESSAGES,
        relevance_weight=settings.CONTEXT_RELEVANCE_WEIGHT,
        recency_weight=settings.CONTEXT_RECENCY_WEIGHT,
        pin_last_n=settings.CONTEXT_PRESERVE_LAST_N,
    )
    selected_messages_text = format_selected_messages(selected_msgs)

    # ── Build system prompt ──────────────────────────────────

    cid = api_account_id

    system_parts = [
        f"You are an expert Google Ads campaign manager and senior PPC strategist. Today is {today.isoformat()}.",
        "You have deep knowledge of digital marketing, campaign optimization, and Google Ads best practices.",
        "Always use specific numbers. Compare day-by-day when asked. Give actionable recommendations.",
        "Think like a senior paid media strategist: consider campaign goals, phases, audience intent, and budget efficiency.",
        "",
    ]

    # Campaign identity — stated as a plain fact so the agent NEVER burns tool
    # calls rediscovering the campaign it is already scoped to. This is the fix
    # for the agent searching all campaigns to "find the relevant campaign"
    # when the user is already inside it.
    if campaign_id:
        system_parts.insert(3, (
            "=== CAMPAIGN YOU ARE WORKING ON (already resolved — do NOT search for it) ===\n"
            f"Campaign name: {campaign_name or '(name not provided — use the ID)'}\n"
            f"Campaign ID: {campaign_id}\n"
            f"Customer/account ID: {api_account_id}\n"
            "'This campaign' = exactly this campaign ID. Its ad groups, ads (with "
            "final URLs), keywords, targeting and metrics are ALL provided below "
            "in LIVE CAMPAIGN DATA. Do NOT call search/list/GAQL tools to find "
            "this campaign or its ad groups/ads/URLs — read them from context. "
            "Use tools only to WRITE changes, or to fetch something genuinely "
            "absent from the context provided.\n"
            "HARD RULE — CAMPAIGN LOCK: Operate ONLY on this campaign ID. NEVER "
            "analyze, report on, clean up, or modify a different campaign — not "
            "even if another campaign has more data, more search terms, or seems "
            "more relevant to the request. If THIS campaign has little or no data "
            "for what's asked (e.g. a brand-new campaign with no search terms or "
            "metrics yet), say that plainly and STOP — ask the user whether they "
            "meant a different campaign. Do NOT silently substitute another "
            "campaign's data or pivot to the campaign that happens to have data."
        ))
    else:
        system_parts.insert(3, (
            "=== NO CAMPAIGN SELECTED ===\n"
            "No specific campaign is in scope for this conversation. If the user "
            "says 'this campaign', 'rerun it', or asks for any campaign-specific "
            "analysis or change, do NOT guess and do NOT pick the campaign with "
            "the most data — ask them which campaign they mean (by name or ID) "
            "before doing any analysis, cleanup, or modifications."
        ))

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
        "CRITICAL PERFORMANCE RULE — READ THIS:",
        "Campaign data (daily metrics, ad groups, keywords, search terms, targeting) is ALREADY in your context below.",
        "DO NOT call any API, MCP search tool, or curl command to re-fetch data that is already provided.",
        "This wastes time and makes responses slow. Use the data in your context FIRST.",
        "Only use MCP tools for: (1) WRITE actions (pause, budget, keywords), (2) data explicitly NOT in context, (3) user says 'refresh'.",
        "For READ operations: answer from the data below. Do NOT run search__search_campaigns or google_ads__search_google_ads for data already shown.",
        "Be FAST — answer the question directly from the context data. No unnecessary tool calls.",
        "",
        "",
        "CRITICAL — MEMORY & CONTINUITY RULES (READ BEFORE EVERY RESPONSE):",
        "1. BEFORE doing ANYTHING, read ALL sections below: PINNED FACTS, PAST DECISIONS, ROLE NOTES.",
        "2. If a previous role already did work (GTM setup, search term audit, etc.), START from where they left off. NEVER redo completed work.",
        "3. Use SPECIFIC details from memory: container IDs, conversion labels, URLs, tag names — not vague references.",
        "4. When the user says 'continue' or 'finish the task', read the role notes to find exactly where work stopped.",
        "5. If you find critical operational details (container IDs, conversion labels, account numbers, URLs), STATE THEM in your response so they persist in the next role notes.",
        "6. ALWAYS acknowledge prior work: 'Per the GTM Specialist notes, container GTM-K6864NBH has 5 tags configured...'",
        "7. Do NOT navigate to a different container/account/page than what's documented in the notes unless the user explicitly asks.",
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

    # Microsoft Clarity MCP — behavioral analytics (conditional)
    if settings.CLARITY_MCP_ENABLED:
        clarity_project = settings.CLARITY_PROJECT_ID
        system_parts.extend([
            "",
            "=== MICROSOFT CLARITY (mcp__clarity__*) ===",
            f"Clarity Project ID: {clarity_project}",
            "You have access to Microsoft Clarity for behavioral analytics — heatmaps, session recordings, and user behavior data.",
            "",
            "KEY TOOLS:",
            "  - get_project_info(project_id) — Get project details and setup status",
            "  - get_session_recordings(project_id, ...) — Fetch session recordings with filters",
            "  - get_heatmap_data(project_id, url) — Get click/scroll heatmap data for a page",
            "  - get_metrics_summary(project_id, date_range) — Engagement metrics summary",
            "  - get_funnel_data(project_id, ...) — Conversion funnel analysis",
            "",
            "USE CASES:",
            "  - After landing page changes: check if user behavior improved (scroll depth, click patterns)",
            "  - CRO analysis: identify where users drop off, what they click/ignore",
            "  - A/B test validation: compare session recordings before/after changes",
            "  - Form optimization: see where users abandon the form",
            "  - Correlate with Google Ads: match ad clicks → landing page behavior → conversions",
            "",
            "=== AUTO-INSTALL TRACKING SCRIPTS ===",
            "When you audit a landing page and find MISSING tracking, install it automatically:",
            "",
            "CLARITY NOT INSTALLED on a landing page?",
            f"  → Use GTM MCP to create a Custom HTML tag with the Clarity script (project: {clarity_project})",
            "  → Trigger: All Pages",
            "  → The Clarity install script:",
            f'  <script>(function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y)}})(window,document,"clarity","script","{clarity_project}");</script>',
            "",
            "CONVERSION TRACKING MISSING?",
            "  → Use GTM MCP to create Google Ads conversion tag",
            "  → Or use Chrome browser to navigate to GTM UI and set it up",
            "",
            "GA4 NOT INSTALLED?",
            "  → Use GTM MCP to create GA4 Configuration tag",
            "",
            "ALWAYS: After installing any tag, create a version and publish via GTM MCP.",
            "ALWAYS: Verify the tag is firing by checking network requests via Chrome MCP.",
        ])

    # Inject active role prompt — prefer evolved skill file over static prompt
    if role_obj.id != "director":
        system_parts.append(f"\n=== YOUR ACTIVE ROLE: {role_obj.name} ===")
        system_parts.append(f"Specialty: {role_obj.specialty}")

        # Try loading evolved skill file for this account
        evolved_skill = None
        if account_id:
            try:
                from app.services.skill_loader import load_skill
                evolved_skill = load_skill(account_id, role_obj.id)
            except Exception:
                pass

        if evolved_skill:
            system_parts.append(f"\n=== EVOLVED SKILL (learned from this account's history) ===")
            system_parts.append(evolved_skill)
        else:
            system_parts.append(role_obj.system_prompt)

        system_parts.append(f"\nYou are responding as the {role_obj.name}. Sign your analysis with your role perspective.")

    # === VERIFICATION & INTEGRITY GUARDRAILS === (global; survives role overrides)
    system_parts.append(
        "=== VERIFICATION & INTEGRITY GUARDRAILS ===\n"
        "VERIFY BEFORE YOU DIAGNOSE: NEVER assert that the landing page has or "
        "lacks a form, or that tracking/conversions are or aren't firing, without "
        "a SAME-SESSION fetch of the ad's actual final_url. If a "
        "'LIVE LANDING PAGE STATE (fetched this session)' block is present, treat "
        "IT as ground truth over any stored note. If page state is unknown or the "
        "fetch failed, SAY SO and fetch/ask — do NOT assume.\n"
        "STALE FINDINGS: Findings marked ⚠️ STALE reflect a PAST state; re-verify "
        "with a live pull/fetch before ANY budget, bid, status, or URL "
        "recommendation. Do not act on stale numbers as if current.\n"
        "ID INTEGRITY: Never state a specific conversion action ID, GTM container "
        "ID (GTM-…), Google Ads conversion ID (AW-…), GA4 measurement ID (G-…), or "
        "conversion label unless it came from a live query/tag pull THIS session — "
        "and LABEL it with its source. If an ID isn't confirmed live, say "
        "'ID not verified — pull it before relying on it' rather than reciting from memory.\n"
        "MECHANISM CLAIMS NEED THE PULL: any explanation of a metric DISCREPANCY "
        "(X in the UI vs Y in the API/CRM — e.g. 'the 5 = 3 primary + 2 GA4 "
        "secondary fires') MUST cite a live SEGMENTED conversion pull run THIS "
        "session (by conversion_action / source). Without that pull, phrase it as "
        "an UNVERIFIED HYPOTHESIS with the segmented pull as the next step — never "
        "'almost certainly' about the breakdown before you have queried it."
    )

    # Assemble the base system prompt (P0 — always included)
    system_prompt_base = "\n".join(system_parts)

    # Resolve @[title](conv:ID) references
    ref_parts = []
    ref_pattern = re.compile(r'@\[([^\]]+)\]\(conv:([a-f0-9-]+)\)')
    ref_matches = ref_pattern.findall(user_message)
    if ref_matches:
        for ref_title, ref_conv_id in ref_matches:
            try:
                ref_msgs = await _get_recent_messages(ref_conv_id, limit=15)
                if ref_msgs:
                    ref_parts.append(f"\n=== REFERENCED CONVERSATION: {ref_title} ===")
                    for msg in ref_msgs:
                        if msg["role"] == "user":
                            ref_parts.append(f"User: {msg['content'][:300]}")
                        else:
                            rl = msg.get("agent_role_name", "Assistant")
                            ref_parts.append(f"[{rl}]: {msg['content'][:400]}")
            except Exception:
                pass
        clean_message = ref_pattern.sub(lambda m: f"(ref: {m.group(1)})", user_message)
    else:
        clean_message = user_message

    # Build attachment context
    attachment_ctx = ""
    if attachments:
        att_parts = [
            "\n=== USER ATTACHMENTS ===",
            "The user has attached the following files. Use the Read tool to view them.",
            "For images, Read will show you the image directly. For documents, you'll get the text content.",
        ]
        for att in attachments:
            kind = "image" if att.get("is_image") else "file"
            att_parts.append(f"- {kind}: {att.get('filename', 'unknown')} → path: {att.get('path', '')}")
        att_parts.append("READ EACH ATTACHMENT before responding so you can reference what's in them.")
        attachment_ctx = "\n".join(att_parts)

    # ── Budget-aware context assembly ──────────────────────────
    budget = TokenBudget.for_model(model_id)

    layers = [
        LayerAllocation("system_base", system_prompt_base, priority=P_CRITICAL),
        LayerAllocation("campaign_memory", f"\n=== CAMPAIGN MEMORY (decisions, facts, role notes) ===\n{campaign_memory_ctx}" if campaign_memory_ctx else "", priority=P_IMPORTANT),
        LayerAllocation("outcome_history", outcome_ctx if outcome_ctx else "", priority=P_IMPORTANT),
        LayerAllocation("chronicle", f"\n=== CAMPAIGN CHRONICLE (complete history) ===\n{chronicle_ctx}" if chronicle_ctx else "", priority=P_IMPORTANT),
        LayerAllocation("business_context", f"\n=== BUSINESS CONTEXT ===\n{business_ctx}" if business_ctx else "", priority=P_IMPORTANT),
        LayerAllocation("guidelines", f"\n=== CAMPAIGN GUIDELINES ===\n{guidelines}" if guidelines else "", priority=P_IMPORTANT),
        LayerAllocation("checkpoint_history", checkpoint_ctx, priority=P_NICE_TO_HAVE),
        LayerAllocation("live_data", (
            f"=== LIVE CAMPAIGN DATA (as of {today.isoformat()}) ===\n"
            "This data includes daily metrics, ad groups, keywords, search terms, and targeting.\n"
            "Use this data directly for analysis. Do NOT re-fetch it via API calls.\n\n"
            f"{live_data}"
        ), priority=P_IMPORTANT),
        LayerAllocation("recent_messages", (
            f"=== RECENT CONVERSATION (smart-selected for relevance) ===\n{selected_messages_text}"
            if selected_messages_text else ""
        ), priority=P_NICE_TO_HAVE),
        LayerAllocation("referenced_conversations", "\n".join(ref_parts) if ref_parts else "", priority=P_NICE_TO_HAVE),
        LayerAllocation("attachments", attachment_ctx, priority=P_IMPORTANT),
        LayerAllocation("session_summaries", (
            "=== PAST SESSION HISTORY ===\n" + "\n".join(summaries)
            if summaries else ""
        ), priority=P_DROPPABLE),
        LayerAllocation("current_question", f"\n=== CURRENT QUESTION ===\n{clean_message}", priority=P_CRITICAL),
    ]

    # Filter empty layers
    layers = [la for la in layers if la.content.strip()]

    budget_result = allocate_budget(layers, budget)

    # Log budget warnings
    for warning in budget_result.warnings:
        logger.warning("Context budget: %s", warning)

    # Build combined prompt from allocated layers
    combined_parts = [la.content for la in budget_result.layers if not la.was_dropped and la.content.strip()]
    combined_prompt = "\n\n---\n\n".join(combined_parts)

    # ── Check compaction ──────────────────────────────────────
    compaction_status = None
    if conversation_id:
        compaction_status = await get_compaction_status(conversation_id, budget_result.usage_ratio)

        if compaction_status["should_compact"] and all_recent_msgs:
            checkpoint = await compact_conversation(
                conversation_id, all_recent_msgs,
                preserve_last_n=settings.CONTEXT_PRESERVE_LAST_N,
            )
            if checkpoint:
                logger.info("Auto-compacted conversation %s: saved ~%d tokens", conversation_id, checkpoint.get("tokens_saved", 0))

    # ── Emit context metadata to frontend ─────────────────────
    context_meta = {
        "type": "context_meta",
        **build_layer_breakdown(budget_result),
    }
    if compaction_status:
        context_meta["compaction"] = compaction_status

    # Refresh runtime settings from DB, then regenerate MCP config so toggles
    # in the Settings UI take effect immediately without a backend restart.
    from app.routers.settings import load_settings_overrides
    await load_settings_overrides()
    mcp_config_path = _get_mcp_config_path()

    # If a prior turn stopped unfinished (cost cap / max continuations / user
    # stop), resume that exact Claude session instead of cold-starting — the
    # session already holds the full work context (e.g. an hour of GTM browser
    # state), so we only feed the new instruction. Consume-once (cleared on read).
    resume_sid = await _take_resume_session(conversation_id)

    # Pipe via stdin to avoid Windows command line length limits
    # High max-turns for harness mode — agent runs until done, not until an arbitrary limit.
    # Browser automation can easily need 100+ turns. Safety caps in _run_cli prevent runaway costs.
    max_turns = str(settings.AGENT_MAX_TURNS_PER_SEGMENT)
    # Story 1.4: token-level streaming previews. When ON, the CLI ALSO emits
    # `stream_event` lines carrying Anthropic content_block_delta text_deltas
    # (parsed below into `text_delta` events). Default OFF — no behavior change.
    partial_flags = ["--include-partial-messages"] if settings.AGENT_STREAM_PARTIAL_MESSAGES else []
    cmd = [
        *_CLI_CMD,
        "--print", "--verbose", "--output-format", "stream-json",
        "--max-turns", max_turns,
        "--model", model_id,
        "--permission-mode", "bypassPermissions",
        "--mcp-config", str(mcp_config_path),
        *partial_flags,
    ]

    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}
    # Remove nesting detection vars so CLI can launch from within a Claude Code session
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_SESSION", None)
    # MONEY SAFETY: force subscription billing. If an Anthropic API key/token is
    # present in the environment the Claude Code CLI would silently bill
    # PER-TOKEN against the API instead of the logged-in Max subscription. Strip
    # every API-auth env var so the CLI can ONLY use the subscription OAuth
    # creds. Hard invariant (mirrors seo-supreme-agent cli_transport._build_env).
    for _k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        env.pop(_k, None)
    # Scope-lock the Google Ads MCP server to this conversation's campaign.
    # The MCP middleware (google_ads/mcp_main.py · CampaignScopeMiddleware)
    # rejects any tool call whose arguments name a different campaign id —
    # physical enforcement, not just a prompt rule.
    #
    # Skipped when no campaign is bound (account-level / "create me a new
    # campaign" chats need full tool surface) AND when the bound id is a
    # `build-*` temp namespace (Campaign Builder conversations legitimately
    # create the real numeric campaign id mid-flow, so locking the build id
    # would block the very tool calls that promote the build to live).
    is_build_namespace = isinstance(campaign_id, str) and campaign_id.startswith("build-")
    if campaign_id and not is_build_namespace:
        env["LANGAR_BOUND_CAMPAIGN_ID"] = str(campaign_id)
        if campaign_name:
            env["LANGAR_BOUND_CAMPAIGN_NAME"] = str(campaign_name)
    else:
        env.pop("LANGAR_BOUND_CAMPAIGN_ID", None)
        env.pop("LANGAR_BOUND_CAMPAIGN_NAME", None)
    # Per-agent tool scoping (workflow orchestrator sets this). The same MCP
    # middleware enforces it. A sentinel "__NONE__" means "no Google Ads tools
    # at all" (pure context analysis — zero API calls, safest for audits);
    # a non-empty list restricts to matching tool names; absent = unrestricted.
    if tool_allowlist is not None:
        env["LANGAR_AGENT_TOOL_ALLOWLIST"] = ",".join(tool_allowlist) if tool_allowlist else "__NONE__"
    else:
        env.pop("LANGAR_AGENT_TOOL_ALLOWLIST", None)

    result_queue: queue.Queue[dict | None] = queue.Queue()
    full_response_text: list[str] = []

    def _parse_assistant_blocks(blocks: list):
        """Thin delegator to the module-level parser (read the flag at call
        time so runtime setting overrides apply). Story 1.4."""
        _emit_assistant_blocks(
            blocks, result_queue, full_response_text,
            stream_partial=settings.AGENT_STREAM_PARTIAL_MESSAGES,
        )

    def _run_cli():
        """Run CLI subprocess with auto-continuation on max-turns exhaustion."""
        accumulated_cost = 0.0
        accumulated_turns = 0
        continuation_count = 0
        current_session_id = None
        is_first_run = True
        # The model actually served this run. Starts as the configured model
        # and is swapped to _FALLBACK_MODEL exactly once if the configured
        # model hits a usage/rate limit (see the limit-fallback block below).
        active_model_id = model_id
        fallback_used = False

        while True:
            # A stop requested before this segment launches (e.g. between
            # segments, or before the first run) must block the relaunch. Emit
            # the same user_stopped done event as the mid-segment path — no
            # segment ran here, so resume from current_session_id. Both the
            # conversation-keyed (Epic 0) and the v2 turn-keyed stop are honored.
            if (conversation_id and conversation_id in _stop_requested) \
                    or _turn_stop_pending(proc_key):
                result_queue.put({"type": "done", "cost": accumulated_cost, "turns": accumulated_turns, "model": active_model_id, "continuations": continuation_count, "stop_reason": "user_stopped", "resume_session_id": current_session_id})
                break

            # Build command — first run uses original cmd, subsequent runs use --resume
            if is_first_run and resume_sid:
                # Resuming a stopped session: the Claude session already has the
                # full system prompt + work context, so we --resume it and feed
                # only the new instruction (not the rebuilt combined_prompt).
                run_cmd = [
                    *_CLI_CMD,
                    "--print", "--verbose", "--output-format", "stream-json",
                    "--resume", resume_sid,
                    "--max-turns", max_turns,
                    "--model", active_model_id,
                    "--permission-mode", "bypassPermissions",
                    "--mcp-config", str(mcp_config_path),
                    *partial_flags,
                ]
            elif is_first_run:
                # Reuse the pre-built cmd, but honor a limit-fallback model swap.
                run_cmd = list(cmd)
                if active_model_id != model_id:
                    m_idx = run_cmd.index("--model") + 1
                    run_cmd[m_idx] = active_model_id
            else:
                run_cmd = [
                    *_CLI_CMD,
                    "--print", "--verbose", "--output-format", "stream-json",
                    "--resume", current_session_id,
                    "--max-turns", max_turns,
                    "--model", active_model_id,
                    "--permission-mode", "bypassPermissions",
                    "--mcp-config", str(mcp_config_path),
                    *partial_flags,
                ]

            segment_session_id = None
            segment_subtype = None
            # Set when this run's CLI output indicates a usage/rate limit for the
            # active model (result-event error, non-success subtype text, or an
            # api_retry event) — drives the one-shot Opus fallback below.
            limit_hit = False
            proc = None

            try:
                # start_new_session=True puts the CLI in its own process group so
                # stop_agent's killpg reaches the CLI's own children (google-ads
                # MCP via uv, chrome MCP via npx, headless Chrome) instead of
                # orphaning them.
                proc = subprocess.Popen(run_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=0, start_new_session=True)
                if conversation_id:
                    _running_procs.setdefault(conversation_id, set()).add(proc)
                # v2: ALSO register under the turn-keyed registry so a per-turn /
                # per-specialist stop reaches exactly this child (additive).
                if proc_key is not None:
                    _turn_procs.setdefault(proc_key, set()).add(proc)

                if is_first_run:
                    # On a resume, the session already has the context — only
                    # send the new instruction. Otherwise send the full prompt.
                    first_input = user_message if resume_sid else combined_prompt
                    if resume_sid:
                        result_queue.put({"type": "resumed", "session_id": resume_sid})
                    proc.stdin.write(first_input.encode("utf-8"))
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
                    elif msg_type == "stream_event":
                        # Story 1.4: token-level streaming. With
                        # --include-partial-messages the CLI emits stream_event
                        # lines wrapping Anthropic streaming deltas. Surface the
                        # incremental text as a distinct `text_delta` event —
                        # NOT `text`, because the final `assistant` message still
                        # carries the same complete text (dedup handled above).
                        _delta = _extract_stream_text_delta(data)
                        if _delta:
                            result_queue.put({"type": "text_delta", "content": _delta})
                    elif msg_type == "api_retry":
                        # The CLI emits api_retry when it hits a retryable server
                        # condition (rate limit / 529 / etc.). If it names a
                        # usage/rate limit, flag for the Opus fallback.
                        if _LIMIT_RE.search(str(data.get("error", "")) or ""):
                            limit_hit = True
                    elif msg_type == "result":
                        segment_session_id = data.get("session_id")
                        segment_subtype = data.get("subtype", "end_turn")
                        accumulated_cost += data.get("total_cost_usd", 0) or 0
                        accumulated_turns += data.get("num_turns", 0) or 0
                        # A non-success result subtype whose text mentions a
                        # usage/rate limit (e.g. "error_max_turns" is fine, but
                        # a limit-flavored error is not) triggers the fallback.
                        _result_blob = f"{segment_subtype} {data.get('error', '')} {data.get('errors', '')}"
                        if segment_subtype not in ("end_turn", "max_turns", "error_max_turns") \
                                and _LIMIT_RE.search(_result_blob):
                            limit_hit = True
                        logger.info(
                            "CLI result: subtype=%s turns=%d cost=$%.4f session=%s errors=%s",
                            segment_subtype, accumulated_turns, accumulated_cost,
                            segment_session_id, data.get("errors", []),
                        )

                proc.wait()
                logger.info("CLI exited: returncode=%s subtype=%s", proc.returncode, segment_subtype)

                # Read stderr once (drives both the limit-fallback check and the
                # error path below). A non-zero exit with no result event may be
                # a rate-limit exit that only printed to stderr.
                err_text = ""
                if proc.returncode != 0:
                    err_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
                    if not limit_hit and _LIMIT_RE.search(err_text):
                        limit_hit = True

                # ── One-shot usage/rate-limit fallback → Opus 4.8 ──────────
                # If the configured (non-fallback) model hit a usage/rate limit
                # on this first attempt, retry the SAME prompt ONCE with Opus.
                # Guards: only before any continuation, only once, and never
                # when the active model is already the fallback (no recursion).
                if (
                    limit_hit
                    and not fallback_used
                    and continuation_count == 0
                    and active_model_id != _FALLBACK_MODEL
                ):
                    logger.warning(
                        "model %s hit a usage/rate limit — retrying once with fallback %s",
                        active_model_id, _FALLBACK_MODEL,
                    )
                    active_model_id = _FALLBACK_MODEL
                    fallback_used = True
                    # Re-run from scratch: same prompt, swapped model. Reset the
                    # first-run flag so the full combined_prompt is re-sent.
                    is_first_run = True
                    continue

                if proc.returncode != 0 and segment_subtype is None:
                    # User stopped or unexpected error (no result event received).
                    # Key "user stopped" off the explicit stop flag — with a
                    # set-based registry the old "key absence" heuristic is
                    # unreliable (a sibling specialist may still hold the key).
                    if conversation_id and conversation_id in _stop_requested:
                        result_queue.put({"type": "done", "cost": accumulated_cost, "turns": accumulated_turns, "model": active_model_id, "continuations": continuation_count, "stop_reason": "user_stopped", "resume_session_id": segment_session_id or current_session_id})
                    else:
                        logger.error("CLI error (rc=%d): %s", proc.returncode, err_text[:500])
                        result_queue.put({"type": "error", "message": f"CLI error: {err_text[:300]}"})
                    break

            except Exception as e:
                result_queue.put({"type": "error", "message": str(e)})
                break
            finally:
                # Discard only THIS proc from the conversation's set; pop the key
                # once the last proc for the conversation is gone. proc may be
                # None if Popen threw before assignment.
                if conversation_id and proc is not None:
                    _procs = _running_procs.get(conversation_id)
                    if _procs is not None:
                        _procs.discard(proc)
                        if not _procs:
                            _running_procs.pop(conversation_id, None)
                # v2: mirror the deregistration for the turn-keyed registry.
                if proc_key is not None and proc is not None:
                    _tprocs = _turn_procs.get(proc_key)
                    if _tprocs is not None:
                        _tprocs.discard(proc)
                        if not _tprocs:
                            _turn_procs.pop(proc_key, None)

            # --- Decide: continue or stop ---
            should_continue = (
                segment_subtype in ("max_turns", "error_max_turns")
                and segment_session_id is not None
                and continuation_count < settings.AGENT_MAX_CONTINUATIONS
                and accumulated_cost < settings.AGENT_MAX_TOTAL_COST_USD
                and not (conversation_id and conversation_id in _stop_requested)
                and not _turn_stop_pending(proc_key)
            )

            if not should_continue:
                stop_reason = "natural"
                if segment_subtype in ("max_turns", "error_max_turns"):
                    if continuation_count >= settings.AGENT_MAX_CONTINUATIONS:
                        stop_reason = "max_continuations"
                    elif accumulated_cost >= settings.AGENT_MAX_TOTAL_COST_USD:
                        stop_reason = "cost_cap"
                # Carry the session id only when the stop is resumable so the
                # consumer persists it; a natural finish leaves it None and
                # clears any prior saved id.
                resumable_sid = (
                    (segment_session_id or current_session_id)
                    if stop_reason in _RESUMABLE_STOPS else None
                )
                result_queue.put({"type": "done", "cost": accumulated_cost, "turns": accumulated_turns, "model": active_model_id, "continuations": continuation_count, "stop_reason": stop_reason, "resume_session_id": resumable_sid})
                break

            # --- Auto-continue ---
            continuation_count += 1
            current_session_id = segment_session_id
            logger.info("Auto-continuing session %s (#%d, %d turns, $%.4f)", current_session_id, continuation_count, accumulated_turns, accumulated_cost)

        result_queue.put(None)  # sentinel

    # Yield context metadata BEFORE starting the CLI
    yield context_meta

    # Global CLI concurrency gate (chat-hardening item 1): acquire ONE shared
    # slot right before spawning the Claude subprocess so total concurrent CLI
    # runs across chat / orchestrator / audit / scheduler / video-director stay
    # bounded (settings.LLM_GLOBAL_MAX_CONCURRENCY). Held only for the CLI's
    # lifetime — released in the `finally` before post-processing — and released
    # on cancellation / generator-close too. See app/services/llm_gate.py.
    from app.services.llm_gate import get_gate
    _cli_gate = get_gate()
    await _cli_gate.acquire()
    _cli_gate_released = False

    thread = threading.Thread(target=_run_cli, daemon=True)
    thread.start()

    detected_actions: list[dict] = []  # Track tool calls for outcome recording

    try:
        while True:
            try:
                event = await asyncio.get_event_loop().run_in_executor(None, lambda: result_queue.get(timeout=0.1))
            except queue.Empty:
                continue
            if event is None:
                break
            # Detect trackable tool executions for outcome recording
            if event.get("type") == "tool_call" and event.get("source") == "google-ads-mcp":
                from app.services.outcome_tracker import detect_action_from_tool
                action = detect_action_from_tool(event.get("name", ""), event.get("input", {}))
                if action:
                    detected_actions.append({"type": action[0], "detail": action[1], "input": event.get("input", {})})
            # Persist (or clear) the resumable session id so the next message
            # in this conversation can --resume an unfinished task. A natural
            # finish sends resume_session_id=None which clears any prior id.
            if event.get("type") == "done" and conversation_id:
                if event.get("stop_reason") in _RESUMABLE_STOPS and event.get("resume_session_id"):
                    await _save_resume_session(conversation_id, event["resume_session_id"])
                    logger.info(
                        "Saved resumable session for %s (stop=%s) — next message will --resume",
                        conversation_id, event.get("stop_reason"),
                    )
            yield event
            if event.get("type") in ("done", "error"):
                break
    except Exception as e:
        yield {"type": "error", "message": str(e)}
    finally:
        # Release the global CLI slot the moment the subprocess stream ends (or
        # the generator is cancelled/closed mid-stream). Post-processing below
        # is pure DB/summary work and must NOT hold a scarce CLI slot.
        if not _cli_gate_released:
            _cli_gate.release()
            _cli_gate_released = True

    # ── Record detected actions as recommendations for outcome tracking ──
    if detected_actions and account_id and campaign_id:
        from app.services.outcome_tracker import record_recommendation
        for action in detected_actions:
            try:
                await record_recommendation(
                    account_id=account_id,
                    campaign_id=campaign_id,
                    action_type=action["type"],
                    action_detail=action["detail"],
                    conversation_id=conversation_id,
                )
            except Exception as e:
                logger.warning("Failed to record recommendation: %s", e)

    # ── Auto-summarize for Layer 4 (if response was substantial) ──
    response_text = "".join(full_response_text)
    if len(response_text) > 500 and conversation_id and campaign_id:
        role_label = role_obj.name if role_obj else "Agent"
        summary_parts = []
        if campaign_name:
            summary_parts.append(f"[{role_label}] Campaign: {campaign_name}.")
        summary_parts.append(f"Q: {user_message[:120]}")

        # Extract key conclusions — look for headings, bold text, recommendations
        conclusion_markers = [
            "recommend", "action", "pause", "increase", "decrease", "switch",
            "add", "remove", "conclusion", "summary", "finding", "result",
            "root cause", "fix", "issue", "verified", "confirmed", "critical",
            "should", "must", "priority", "##", "**",
        ]
        for line in response_text.split("\n"):
            ls = line.strip()
            if not ls or len(ls) < 20:
                continue
            if any(kw in ls.lower() for kw in conclusion_markers):
                # Clean markdown formatting for compact storage
                clean = ls.replace("**", "").replace("##", "").strip()
                summary_parts.append(clean[:200])
                if len(summary_parts) > 6:
                    break

        summary = " | ".join(summary_parts)
        try:
            await _save_session_summary(conversation_id, campaign_id, campaign_name, summary[:800])
        except Exception:
            pass

    # ── Auto-update chronicle (long-term structured timeline) ──
    if len(response_text) > 500 and account_id and campaign_id:
        try:
            from app.services.chronicle import update_chronicle
            await update_chronicle(
                account_id=account_id,
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                role_name=role_obj.name if role_obj else "Agent",
                user_question=user_message,
                agent_response=response_text,
                tool_calls=[{"name": a["type"]} for a in detected_actions] if detected_actions else None,
            )
        except Exception as e:
            logger.warning("Chronicle update failed: %s", e)

    # ── Auto-save to campaign memory (persistent across sessions) ──
    if len(response_text) > 300 and account_id and campaign_id:
        try:
            from app.services.campaign_memory import append_decision, save_role_notes

            # Auto-extract decisions to campaign memory files
            action_patterns = [
                ("paused", "pause"), ("enabled", "enable"),
                ("added negative", "add negative"), ("changed budget", "budget change"),
                ("adjusted bid", "bid adjustment"), ("added keyword", "add keyword"),
                ("removed", "remove"), ("created", "create"), ("updated", "update"),
                ("fixed", "fix"), ("verified", "verify"), ("confirmed", "confirm"),
                ("flagged", "flag"), ("identified", "identify"),
            ]
            decisions_logged = 0
            for line in response_text.split("\n"):
                line_lower = line.lower().strip()
                if decisions_logged >= 5:
                    break
                for pattern, action_type in action_patterns:
                    if pattern in line_lower and len(line.strip()) > 20:
                        append_decision(
                            account_id, campaign_id,
                            action=line.strip()[:300],
                            reason=f"User asked: {user_message[:150]}",
                            outcome="pending",
                            role=role_obj.id if role_obj else "agent",
                        )
                        decisions_logged += 1
                        break

            # Save role findings — smart: full audit overwrites, follow-ups append
            role_id = role_obj.id if role_obj else "director"
            if role_id != "director":
                from app.services.campaign_memory import append_role_notes

                condensed = _condense_for_memory(response_text, user_message, max_chars=10000)

                # Detect if this is a full audit/report (multiple ### STEP headings or ## sections)
                step_count = len(re.findall(r'(?:^|\n)#{2,3}\s*(?:STEP\s*\d+|step\s*\d+)', response_text))
                section_count = len(re.findall(r'(?:^|\n)#{2,3}\s+\w+', response_text))
                is_full_audit = step_count >= 3 or section_count >= 8

                if is_full_audit:
                    # Replace the existing report
                    save_role_notes(account_id, campaign_id, role_id, condensed)
                else:
                    # Append as a follow-up entry, preserving the existing report
                    append_role_notes(
                        account_id, campaign_id, role_id, condensed,
                        section_title=user_message[:80],
                    )
        except Exception:
            pass
