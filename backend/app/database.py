"""SQLite database module using aiosqlite directly."""

import aiosqlite
from pathlib import Path

from app.config import settings

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT,
    level TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    account_id TEXT,
    campaign_id TEXT,
    campaign_name TEXT,
    title TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_name TEXT,
    tool_source TEXT,
    tool_input TEXT,
    tool_output TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS guidelines_meta (
    filename TEXT PRIMARY KEY,
    campaign_id TEXT,
    campaign_name TEXT,
    last_modified REAL,
    sections TEXT
);

CREATE TABLE IF NOT EXISTS session_summaries (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    campaign_id TEXT,
    campaign_name TEXT,
    summary TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
"""


async def get_db() -> aiosqlite.Connection:
    """Open a new database connection with WAL mode and foreign keys enabled."""
    db_path = settings.database_path
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Create the data directory and all tables."""
    db_path: Path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = await get_db()
    try:
        await db.executescript(_TABLES_SQL)
        await db.commit()
    finally:
        await db.close()
