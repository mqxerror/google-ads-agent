"""Campaign Chronicle — persistent, structured timeline of everything important.

Unlike session summaries (lossy, limited to 5, dropped first), the chronicle
is a living document that grows slowly and is ALWAYS loaded into agent context.

Structure:
    data/memory/{account_id}/{campaign_id}/CHRONICLE.md

Each agent conversation appends key events: decisions, metrics, findings.
Older entries stay — nothing is ever removed. The chronicle IS the long-term memory.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_MEMORY_ROOT = settings.MEMORY_DIR


def _chronicle_path(account_id: str, campaign_id: str) -> Path:
    d = _MEMORY_ROOT / account_id / campaign_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "CHRONICLE.md"


def load_chronicle(account_id: str, campaign_id: str) -> str:
    """Load the campaign chronicle. Returns empty string if none exists."""
    path = _chronicle_path(account_id, campaign_id)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _init_chronicle(account_id: str, campaign_id: str, campaign_name: str) -> str:
    """Create a new chronicle file with header."""
    now = datetime.now().strftime("%Y-%m-%d")
    content = f"""# Campaign Chronicle: {campaign_name}
Last updated: {now}

## Timeline

## Key Metrics Milestones

## Critical Decisions (never expire)
"""
    path = _chronicle_path(account_id, campaign_id)
    path.write_text(content, encoding="utf-8")
    return content


async def update_chronicle(
    account_id: str,
    campaign_id: str,
    campaign_name: str | None,
    role_name: str,
    user_question: str,
    agent_response: str,
    tool_calls: list[dict] | None = None,
):
    """Extract key events from a conversation and append to the chronicle.

    Called after each substantive agent response (>500 chars).
    Uses a short Sonnet call to extract structured events.
    """
    if not account_id or not campaign_id:
        return

    path = _chronicle_path(account_id, campaign_id)
    existing = load_chronicle(account_id, campaign_id)

    if not existing:
        existing = _init_chronicle(account_id, campaign_id, campaign_name or f"Campaign {campaign_id}")

    # Extract the key event using Sonnet
    entry = await _extract_chronicle_entry(
        role_name=role_name,
        user_question=user_question,
        agent_response=agent_response,
        tool_calls=tool_calls,
    )

    if not entry or len(entry.strip()) < 20:
        # Fallback: create a simple entry from the response
        entry = _naive_entry(role_name, user_question, agent_response, tool_calls)

    if not entry:
        return

    # Determine the current month section header
    now = datetime.now()
    month_header = f"### {now.strftime('%B %Y')}"
    date_prefix = f"- **{now.strftime('%b %d')}**"

    # Format the entry line
    entry_line = f"{date_prefix} — [{role_name}] {entry.strip()}"

    # Insert under the right month in the Timeline section
    updated = _insert_entry(existing, month_header, entry_line)

    # Update the "Last updated" line
    updated = re.sub(
        r"Last updated: .*",
        f"Last updated: {now.strftime('%Y-%m-%d')}",
        updated,
        count=1,
    )

    path.write_text(updated, encoding="utf-8")
    logger.info("Chronicle updated for %s/%s: %s", account_id, campaign_id, entry[:80])


def _insert_entry(chronicle: str, month_header: str, entry_line: str) -> str:
    """Insert an entry under the correct month in the Timeline section."""
    lines = chronicle.split("\n")

    # Find "## Timeline" section
    timeline_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Timeline":
            timeline_idx = i
            break

    if timeline_idx is None:
        # No Timeline section — add it
        lines.append("\n## Timeline")
        lines.append(month_header)
        lines.append(entry_line)
        return "\n".join(lines)

    # Find the month header within Timeline
    month_idx = None
    next_section_idx = None
    for i in range(timeline_idx + 1, len(lines)):
        if lines[i].strip().startswith("## ") and not lines[i].strip().startswith("### "):
            next_section_idx = i
            break
        if lines[i].strip() == month_header.strip():
            month_idx = i
            break

    if month_idx is not None:
        # Month exists — insert after the month header
        lines.insert(month_idx + 1, entry_line)
    elif next_section_idx is not None:
        # Month doesn't exist — add it before the next section
        lines.insert(next_section_idx, "")
        lines.insert(next_section_idx, entry_line)
        lines.insert(next_section_idx, month_header)
    else:
        # No next section — add at end of Timeline
        lines.insert(timeline_idx + 1, month_header)
        lines.insert(timeline_idx + 2, entry_line)

    return "\n".join(lines)


async def _extract_chronicle_entry(
    role_name: str,
    user_question: str,
    agent_response: str,
    tool_calls: list[dict] | None,
) -> str | None:
    """Use Sonnet to extract a concise chronicle entry from a conversation turn."""
    tools_text = ""
    if tool_calls:
        tool_names = [t.get("name", "") for t in tool_calls[:5]]
        tools_text = f"\nTools used: {', '.join(tool_names)}"

    prompt = f"""Extract a 1-2 line chronicle entry from this agent conversation turn.
Focus on: what ACTION was taken, what KEY DECISION was made, what METRIC changed, what was FOUND.
Be specific with numbers, campaign names, keyword counts, CPA values.
If nothing actionable happened (just a question or general discussion), return "SKIP".

Role: {role_name}
User asked: {user_question[:200]}
Agent response (first 1500 chars): {agent_response[:1500]}
{tools_text}

Return ONLY the chronicle entry text (1-2 lines, no bullets, no date prefix). Or "SKIP" if nothing noteworthy."""

    try:
        node_path = shutil.which("node") or "node"
        cli_js = _find_cli_js()
        if not cli_js:
            return None

        cmd = [
            node_path, str(cli_js),
            "--print", "--verbose", "--output-format", "stream-json",
            "--max-turns", "1",
            "--model", "claude-sonnet-4-6",
            "--permission-mode", "bypassPermissions",
        ]

        env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE_SESSION", None)

        proc = subprocess.run(
            cmd, input=prompt.encode("utf-8"),
            capture_output=True, timeout=30, env=env,
        )

        if proc.returncode != 0:
            return None

        text_parts = []
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "assistant":
                    for block in data.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
            except (json.JSONDecodeError, KeyError):
                continue

        result = " ".join(text_parts).strip()
        if result.upper() == "SKIP" or len(result) < 10:
            return None
        # Clean up — remove any bullet points or date prefixes the model might add
        result = re.sub(r"^[-•*]\s*", "", result)
        result = re.sub(r"^\*\*.*?\*\*\s*—?\s*", "", result)
        return result

    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        logger.warning("Chronicle extraction error: %s", e)
        return None


def _naive_entry(
    role_name: str,
    user_question: str,
    agent_response: str,
    tool_calls: list[dict] | None,
) -> str | None:
    """Fallback: create a simple chronicle entry without AI."""
    parts = []

    # Extract the gist from the user question
    q = user_question[:100].strip()
    if q:
        parts.append(f"User asked: {q}")

    # Count tool calls
    if tool_calls:
        tool_names = set(t.get("name", "") for t in tool_calls)
        parts.append(f"Used {len(tool_calls)} tools ({', '.join(list(tool_names)[:3])})")

    # Extract key numbers from response
    response_lower = agent_response[:500].lower()
    for kw in ["cpa", "ctr", "conversions", "impressions", "budget", "keywords", "negatives"]:
        if kw in response_lower:
            # Find the sentence containing the keyword
            for sentence in agent_response[:1000].split("."):
                if kw in sentence.lower() and any(c.isdigit() for c in sentence):
                    parts.append(sentence.strip()[:100])
                    break

    if not parts:
        return None

    return ". ".join(parts[:3])


def _find_cli_js() -> Path | None:
    """Find Claude CLI JS file."""
    import glob
    candidates = [
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
    ]
    for p in candidates:
        if p.exists():
            return p
    nvm_matches = glob.glob(str(Path.home() / ".nvm/versions/node/*/lib/node_modules/@anthropic-ai/claude-code/cli.js"))
    if nvm_matches:
        return Path(nvm_matches[0])
    try:
        result = subprocess.run([shutil.which("npm") or "npm", "root", "-g"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            cli = Path(result.stdout.strip()) / "@anthropic-ai/claude-code/cli.js"
            if cli.exists():
                return cli
    except Exception:
        pass
    return None
