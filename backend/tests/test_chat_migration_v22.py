"""Chat Orchestration v2 — Migration V22 (Epic 1.1).

Applies migrations on a temp DB, asserts the new tables/columns exist with the
expected shape, schema_version == 22, and that re-running init_db is idempotent
(no crash, still 22). Repo test style: stdlib unittest, a REAL temp SQLite from
init_db(), no live calls.

Run:  cd backend && .venv/bin/python -m unittest tests.test_chat_migration_v22 -v
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

# Throwaway data dir BEFORE any table is touched.
_TMP = Path(tempfile.mkdtemp(prefix="chat-migration-v22-test-"))
settings.DATA_DIR = _TMP

from app.database import get_db, init_db  # noqa: E402


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


async def _columns(table: str) -> list[str]:
    db = await get_db()
    try:
        cur = await db.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in await cur.fetchall()]
    finally:
        await db.close()


async def _schema_version() -> int:
    db = await get_db()
    try:
        cur = await db.execute("SELECT MAX(version) FROM schema_version")
        row = await cur.fetchone()
        return row[0] if row and row[0] else 0
    finally:
        await db.close()


class MigrationV22(unittest.TestCase):
    def test_schema_version_at_least_22(self):
        # V22 is no longer the head (V23+ have landed); this migration only
        # needs the schema to be AT OR ABOVE 22 for its tables to exist.
        self.assertGreaterEqual(_run(_schema_version()), 22)

    def test_chat_turns_columns(self):
        cols = _run(_columns("chat_turns"))
        for expected in (
            "turn_id", "conversation_id", "campaign_id", "parent_turn_id",
            "mode", "status", "cost", "agents_used", "conflicts",
            "started_at", "finished_at", "final_message_id", "stop_reason",
        ):
            self.assertIn(expected, cols, f"chat_turns missing {expected}")

    def test_chat_turn_events_columns(self):
        cols = _run(_columns("chat_turn_events"))
        for expected in ("turn_id", "seq", "type", "payload", "created_at"):
            self.assertIn(expected, cols, f"chat_turn_events missing {expected}")

    def test_messages_has_turn_id(self):
        self.assertIn("turn_id", _run(_columns("messages")))

    def test_workflow_reports_has_origin(self):
        self.assertIn("origin", _run(_columns("workflow_reports")))

    def test_chat_turn_events_pk_is_turn_seq(self):
        """(turn_id, seq) is the primary key → a duplicate seq per turn is
        rejected, which is what makes the batched INSERT OR IGNORE re-flush safe."""
        async def _check():
            db = await get_db()
            try:
                await db.execute(
                    "INSERT INTO chat_turns (turn_id, conversation_id, mode) "
                    "VALUES ('t-pk', 'c-pk', 'direct')"
                )
                await db.execute(
                    "INSERT INTO chat_turn_events (turn_id, seq, type, payload) "
                    "VALUES ('t-pk', 1, 'text', '{}')"
                )
                # Same (turn_id, seq) again with OR IGNORE → silently ignored.
                await db.execute(
                    "INSERT OR IGNORE INTO chat_turn_events (turn_id, seq, type, payload) "
                    "VALUES ('t-pk', 1, 'DUP', '{}')"
                )
                await db.commit()
                cur = await db.execute(
                    "SELECT type FROM chat_turn_events WHERE turn_id = 't-pk' AND seq = 1"
                )
                row = await cur.fetchone()
                return row["type"]
            finally:
                await db.close()

        self.assertEqual(_run(_check()), "text")  # original kept, dup ignored

    def test_rerun_init_db_is_idempotent(self):
        """Re-running init_db on an already-migrated DB must not crash and the
        V22 tables must survive (head is >= 22 once later migrations land)."""
        _run(init_db())
        _run(init_db())
        self.assertGreaterEqual(_run(_schema_version()), 22)
        # Tables still intact after re-run.
        self.assertIn("turn_id", _run(_columns("chat_turns")))
        self.assertIn("origin", _run(_columns("workflow_reports")))


if __name__ == "__main__":
    unittest.main()
