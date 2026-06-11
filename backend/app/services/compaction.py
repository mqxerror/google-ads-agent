"""Conversation auto-compaction with warn-then-compress strategy.

When a conversation approaches the token budget:
1. At 70%: emit a warning to the frontend (yellow badge)
2. At 85%: auto-compress older messages into a summary checkpoint
3. Future messages load the checkpoint summary instead of old messages

Summarization uses Haiku (cheap/fast) via a separate CLI call.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.config import settings
from app.database import get_db
from app.services.token_counter import TokenBudget, estimate_tokens

logger = logging.getLogger(__name__)

# Thresholds for compaction actions
WARN_THRESHOLD = 0.70    # Show warning badge at 70%
COMPACT_THRESHOLD = 0.85  # Auto-compact at 85%

# Messages to always keep verbatim (never compact the most recent ones)
PRESERVE_LAST_N = 4


async def get_compaction_status(
    conversation_id: str,
    current_usage_ratio: float,
) -> dict:
    """Check compaction status for a conversation.

    Returns:
        {
            "should_warn": bool,
            "should_compact": bool,
            "usage_ratio": float,
            "checkpoint_count": int,
            "last_checkpoint_summary": str | None,
        }
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT COUNT(*) as cnt, MAX(checkpoint_number) as latest "
            "FROM conversation_checkpoints WHERE conversation_id = ?",
            (conversation_id,),
        )
        row = await cur.fetchone()
        checkpoint_count = row["cnt"] if row else 0

        last_summary = None
        if checkpoint_count > 0:
            cur = await db.execute(
                "SELECT summary FROM conversation_checkpoints "
                "WHERE conversation_id = ? ORDER BY checkpoint_number DESC LIMIT 1",
                (conversation_id,),
            )
            sr = await cur.fetchone()
            if sr:
                last_summary = sr["summary"]

        return {
            "should_warn": current_usage_ratio >= WARN_THRESHOLD,
            "should_compact": current_usage_ratio >= COMPACT_THRESHOLD,
            "usage_ratio": current_usage_ratio,
            "checkpoint_count": checkpoint_count,
            "last_checkpoint_summary": last_summary,
        }
    finally:
        await db.close()


async def compact_conversation(
    conversation_id: str,
    messages: list[dict],
    preserve_last_n: int = PRESERVE_LAST_N,
) -> dict | None:
    """Compact older messages into a summary checkpoint.

    Args:
        conversation_id: The conversation to compact
        messages: All messages in the conversation (chronological)
        preserve_last_n: Number of recent messages to keep verbatim

    Returns:
        Checkpoint dict if created, None if not enough messages to compact
    """
    if len(messages) <= preserve_last_n + 2:
        # Not enough messages to compact
        return None

    # Split: messages to compress vs messages to keep
    to_compress = messages[:-preserve_last_n]
    kept = messages[-preserve_last_n:]

    if not to_compress:
        return None

    # Generate summary of compressed messages
    summary = await _generate_summary(to_compress)
    if not summary:
        # Fallback: naive extraction
        summary = _naive_summary(to_compress)

    # Get next checkpoint number
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT COALESCE(MAX(checkpoint_number), 0) + 1 as next_num "
            "FROM conversation_checkpoints WHERE conversation_id = ?",
            (conversation_id,),
        )
        row = await cur.fetchone()
        checkpoint_number = row["next_num"]

        tokens_before = sum(estimate_tokens(m.get("content", "")) for m in to_compress)
        tokens_after = estimate_tokens(summary)

        checkpoint = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "checkpoint_number": checkpoint_number,
            "summary": summary,
            "messages_compressed": len(to_compress),
            "tokens_saved": tokens_before - tokens_after,
            "created_at": datetime.now().isoformat(),
        }

        await db.execute(
            "INSERT INTO conversation_checkpoints "
            "(id, conversation_id, checkpoint_number, summary, messages_compressed, tokens_saved) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                checkpoint["id"],
                conversation_id,
                checkpoint_number,
                summary,
                len(to_compress),
                tokens_before - tokens_after,
            ),
        )
        await db.commit()

        logger.info(
            "Compacted conversation %s: %d messages → checkpoint #%d, saved ~%d tokens",
            conversation_id, len(to_compress), checkpoint_number,
            tokens_before - tokens_after,
        )

        return checkpoint
    finally:
        await db.close()


async def load_checkpoint_context(conversation_id: str) -> str:
    """Load the most recent checkpoint summary for a conversation.

    Returns the summary text to inject as compressed history context.
    """
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT summary, checkpoint_number, messages_compressed, created_at "
            "FROM conversation_checkpoints "
            "WHERE conversation_id = ? ORDER BY checkpoint_number DESC LIMIT 1",
            (conversation_id,),
        )
        row = await cur.fetchone()
        if not row:
            return ""

        return (
            f"=== CONVERSATION HISTORY (compressed from {row['messages_compressed']} earlier messages) ===\n"
            f"{row['summary']}"
        )
    finally:
        await db.close()


async def _generate_summary(messages: list[dict]) -> str | None:
    """Generate a summary of messages using Haiku (cheap/fast).

    Falls back to naive summary if CLI call fails.
    """
    # Build a compact representation of the messages
    msg_text_parts = []
    for m in messages:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = m.get("content", "")[:500]  # Limit per message for the summary request
        msg_text_parts.append(f"{role}: {content}")

    messages_text = "\n".join(msg_text_parts)

    prompt = (
        "Summarize this conversation excerpt in 3-5 bullet points. "
        "Focus on: key decisions made, actions taken (tool calls, changes), "
        "important data points mentioned, and unresolved questions. "
        "Be specific with numbers, campaign names, and metric values. "
        "Do NOT include pleasantries or meta-commentary.\n\n"
        f"Conversation:\n{messages_text}"
    )

    try:
        # Use Haiku for cheap/fast summarization
        cmd = [
            *_find_cli(),
            "--print", "--verbose", "--output-format", "stream-json",
            "--max-turns", "1",
            "--model", "claude-sonnet-4-6",
            "--permission-mode", "bypassPermissions",
        ]

        env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_CODE_SESSION", None)

        proc = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=30,
            env=env,
        )

        if proc.returncode != 0:
            logger.warning("Haiku summary failed (rc=%d)", proc.returncode)
            return None

        # Parse the streaming JSON output to extract text
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
            except json.JSONDecodeError:
                continue

        if text_parts:
            return "\n".join(text_parts)

        return None
    except subprocess.TimeoutExpired:
        logger.warning("Haiku summary timed out")
        return None
    except Exception as e:
        logger.warning("Haiku summary error: %s", e)
        return None


def _naive_summary(messages: list[dict]) -> str:
    """Fallback summary when Haiku is unavailable."""
    parts = []
    user_questions = []
    assistant_actions = []

    for m in messages:
        content = m.get("content", "")
        if m.get("role") == "user":
            # Extract first line as the question
            first_line = content.split("\n")[0][:150]
            user_questions.append(first_line)
        else:
            # Extract action keywords from assistant responses
            for line in content.split("\n"):
                line_lower = line.lower()
                if any(kw in line_lower for kw in [
                    "recommend", "added", "removed", "paused", "enabled",
                    "changed", "created", "increased", "decreased", "found",
                ]):
                    assistant_actions.append(line.strip()[:150])
                    if len(assistant_actions) >= 5:
                        break

    parts.append(f"Topics discussed ({len(messages)} messages):")
    for q in user_questions[:5]:
        parts.append(f"  - {q}")

    if assistant_actions:
        parts.append("Key actions/findings:")
        for a in assistant_actions[:5]:
            parts.append(f"  - {a}")

    return "\n".join(parts)


def _find_cli_js() -> Path:
    """Find Claude CLI JS (duplicated from agent.py to avoid circular imports)."""
    import glob
    candidates = [
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
        Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js",
    ]
    for p in candidates:
        if p.exists():
            return p
    # nvm
    nvm_pattern = str(Path.home() / ".nvm/versions/node/*/lib/node_modules/@anthropic-ai/claude-code/cli.js")
    matches = glob.glob(nvm_pattern)
    if matches:
        return Path(matches[0])
    # npm root fallback
    try:
        result = subprocess.run(
            [shutil.which("npm") or "npm", "root", "-g"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            cli = Path(result.stdout.strip()) / "@anthropic-ai/claude-code/cli.js"
            if cli.exists():
                return cli
    except Exception:
        pass
    return Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/cli.js"


def _find_cli() -> list[str]:
    """Resolve the CLI launch argv prefix, preferring the native binary.

    ``~/.local/bin/claude`` (native-binary install — the logged-in,
    auto-updating CLI) is checked explicitly FIRST: shutil.which can miss
    ``~/.local/bin`` under a stripped PATH, and the npm cli.js copy can be
    badly stale. Falls back to ``[node, cli.js]``, then ``which claude``,
    then the best-guess ``[node, cli.js]`` so spawn errors are clear.
    """
    native = Path.home() / ".local/bin/claude"
    if native.exists():
        return [str(native)]
    node_path = shutil.which("node") or "node"
    cli_js = _find_cli_js()
    if cli_js.exists():
        return [node_path, str(cli_js)]
    which_claude = shutil.which("claude")
    if which_claude:
        return [which_claude]
    return [node_path, str(cli_js)]
