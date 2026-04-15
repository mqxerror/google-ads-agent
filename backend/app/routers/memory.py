"""Memory explorer endpoints — view and manage agent memory per campaign."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.database import get_db
from app.services.campaign_memory import (
    load_memory_index, load_decisions, load_pinned_facts, load_profile, load_account_memory,
)
from app.services.chronicle import load_chronicle
from app.services.token_counter import estimate_tokens

router = APIRouter(prefix="/api", tags=["memory"])


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/memory-explorer")
async def get_memory_explorer(account_id: str, campaign_id: str) -> dict:
    """Get complete memory overview for a campaign — what the agent sees."""

    memory_dir = settings.MEMORY_DIR / account_id / campaign_id

    # Chronicle
    chronicle = load_chronicle(account_id, campaign_id)
    chronicle_entries = len([l for l in chronicle.split("\n") if l.strip().startswith("- **")])

    # Pinned facts
    pinned = load_pinned_facts(account_id, campaign_id)
    pinned_lines = [l for l in pinned.split("\n") if l.strip().startswith("- **")]

    # Decisions (all, with compression)
    decisions_full = load_decisions(account_id, campaign_id)
    decisions_all_raw = ""
    decisions_file = memory_dir / "decisions.md"
    total_decisions = 0
    if decisions_file.exists():
        content = decisions_file.read_text(encoding="utf-8")
        total_decisions = len([l for l in content.split("\n") if l.strip().startswith("|") and "Date" not in l and "---" not in l])

    # Profile
    profile = load_profile(account_id, campaign_id)

    # Role notes
    role_notes_info = []
    role_notes_dir = memory_dir / "role_notes"
    if role_notes_dir.exists():
        for f in sorted(role_notes_dir.glob("*.md")):
            stat = f.stat()
            role_notes_info.append({
                "role_id": f.stem,
                "role_name": f.stem.replace("_", " ").title(),
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 1),
                "tokens": estimate_tokens(f.read_text(encoding="utf-8")),
            })

    # Conversations + messages count
    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        conv_count = (await cur.fetchone())["cnt"]

        cur = await db.execute(
            """SELECT COUNT(*) as cnt FROM messages
               WHERE conversation_id IN (
                   SELECT id FROM conversations WHERE account_id = ? AND campaign_id = ?
               )""",
            (account_id, campaign_id),
        )
        msg_count = (await cur.fetchone())["cnt"]

        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM session_summaries WHERE campaign_id = ?",
            (campaign_id,),
        )
        summary_count = (await cur.fetchone())["cnt"]

        # Outcomes
        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM recommendations WHERE account_id = ? AND campaign_id = ?",
            (account_id, campaign_id),
        )
        outcome_count = (await cur.fetchone())["cnt"]

    finally:
        await db.close()

    # Account memory
    account_mem = load_account_memory(account_id)

    # Token estimates for what the agent actually loads
    layers = {
        "chronicle": {"content": chronicle, "tokens": estimate_tokens(chronicle), "loaded": True},
        "pinned_facts": {"content": pinned, "tokens": estimate_tokens(pinned), "loaded": True},
        "decisions": {"content": decisions_full, "tokens": estimate_tokens(decisions_full), "loaded": True},
        "profile": {"content": profile, "tokens": estimate_tokens(profile), "loaded": True},
        "role_notes": {"tokens": sum(r["tokens"] for r in role_notes_info), "loaded": True},
        "account_memory": {"content": account_mem, "tokens": estimate_tokens(account_mem), "loaded": True},
    }
    total_memory_tokens = sum(l["tokens"] for l in layers.values())

    return {
        "campaign_id": campaign_id,
        "account_id": account_id,

        "chronicle": {
            "exists": bool(chronicle),
            "entries": chronicle_entries,
            "size_kb": round(len(chronicle.encode()) / 1024, 1),
            "tokens": estimate_tokens(chronicle),
            "content": chronicle,
        },

        "pinned_facts": {
            "count": len(pinned_lines),
            "tokens": estimate_tokens(pinned),
            "items": [l.strip().lstrip("- ") for l in pinned_lines],
            "content": pinned,
        },

        "decisions": {
            "total": total_decisions,
            "tokens": estimate_tokens(decisions_full),
            "content": decisions_full,
        },

        "role_notes": {
            "roles": role_notes_info,
            "total_tokens": sum(r["tokens"] for r in role_notes_info),
        },

        "conversations": {
            "count": conv_count,
            "messages": msg_count,
            "summaries": summary_count,
        },

        "outcomes": {
            "count": outcome_count,
        },

        "profile": {
            "tokens": estimate_tokens(profile),
            "content": profile,
        },

        "account_memory": {
            "tokens": estimate_tokens(account_mem),
            "content": account_mem,
        },

        "total_memory_tokens": total_memory_tokens,
        "context_budget": 161_808,  # Approximate effective budget
        "usage_percent": round(total_memory_tokens / 161_808 * 100, 1),
    }


@router.get("/accounts/{account_id}/campaigns/{campaign_id}/chronicle")
async def get_chronicle(account_id: str, campaign_id: str) -> dict:
    """Get the campaign chronicle."""
    content = load_chronicle(account_id, campaign_id)
    return {"content": content, "tokens": estimate_tokens(content)}


@router.put("/accounts/{account_id}/campaigns/{campaign_id}/chronicle")
async def update_chronicle_content(account_id: str, campaign_id: str, body: dict) -> dict:
    """Manually edit the chronicle."""
    content = body.get("content", "")
    path = settings.MEMORY_DIR / account_id / campaign_id / "CHRONICLE.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"status": "saved", "tokens": estimate_tokens(content)}
