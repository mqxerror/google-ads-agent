"""SQLite database module using aiosqlite directly — V2 with multi-account support."""

import logging
import shutil
from pathlib import Path

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

# ── V1 Schema (original, kept for reference during migration) ──────

_V1_TABLES_SQL = """
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

# ── V2 New Tables ──────────────────────────────────────────────────

_V2_NEW_TABLES_SQL = """
-- Schema versioning
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

-- V2 account management (replaces V1 accounts for multi-MCC support)
CREATE TABLE IF NOT EXISTS accounts_v2 (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mcc_id TEXT,
    level TEXT NOT NULL DEFAULT 'mcc',
    is_active INTEGER DEFAULT 1,
    onboarded_at TEXT,
    last_synced TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Encrypted credentials per account
CREATE TABLE IF NOT EXISTS account_credentials (
    account_id TEXT PRIMARY KEY,
    developer_token_encrypted BLOB,
    client_id_encrypted BLOB,
    client_secret_encrypted BLOB,
    refresh_token_encrypted BLOB,
    login_customer_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

-- Marketing intelligence: campaign goals and phases
CREATE TABLE IF NOT EXISTS campaign_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    campaign_name TEXT,
    objective TEXT DEFAULT 'unknown',
    phase TEXT DEFAULT 'unknown',
    phase_detected_at TEXT,
    target_cpa REAL,
    target_roas REAL,
    monthly_budget_cap REAL,
    notes TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(account_id, campaign_id),
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

-- Proactive alerts
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    campaign_id TEXT,
    type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    recommendation TEXT,
    data_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    dismissed_at TEXT,
    resolved_at TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts_v2(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alerts_account ON alerts(account_id, dismissed_at);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity, created_at);

-- Conversation indexes for V2
CREATE INDEX IF NOT EXISTS idx_conversations_account ON conversations(account_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);

-- Session summary indexes
CREATE INDEX IF NOT EXISTS idx_summaries_campaign
    ON session_summaries(campaign_id, created_at);

-- Cache index
CREATE INDEX IF NOT EXISTS idx_cache_fetched ON cache(fetched_at);

-- Local metrics store — daily campaign data for fast agent access
CREATE TABLE IF NOT EXISTS campaign_daily_metrics (
    account_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    campaign_name TEXT,
    date TEXT NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    cost_micros INTEGER DEFAULT 0,
    conversions REAL DEFAULT 0,
    ctr REAL DEFAULT 0,
    avg_cpc_micros INTEGER DEFAULT 0,
    campaign_status TEXT,
    bidding_strategy TEXT,
    budget_micros INTEGER DEFAULT 0,
    synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (account_id, campaign_id, date)
);

CREATE INDEX IF NOT EXISTS idx_metrics_account_date
    ON campaign_daily_metrics(account_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_campaign_date
    ON campaign_daily_metrics(campaign_id, date DESC);

-- Playbooks (Phase 2 prep — create table now, populate later)
CREATE TABLE IF NOT EXISTS playbooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    vertical TEXT,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'built-in',
    version TEXT,
    installed_at TEXT DEFAULT (datetime('now'))
);

-- Sync status tracking
-- Add agent_role to messages for role attribution
-- (ALTER TABLE is idempotent via the migration below)

CREATE TABLE IF NOT EXISTS sync_status (
    account_id TEXT PRIMARY KEY,
    last_sync_at TEXT,
    last_sync_status TEXT DEFAULT 'pending',
    last_sync_error TEXT,
    campaigns_synced INTEGER DEFAULT 0,
    days_synced INTEGER DEFAULT 0
);

-- Decision log
CREATE TABLE IF NOT EXISTS decision_log (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    campaign_name TEXT,
    conversation_id TEXT,
    action TEXT NOT NULL,
    reason TEXT,
    outcome TEXT,
    role TEXT DEFAULT 'agent',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Pinned facts
CREATE TABLE IF NOT EXISTS pinned_facts (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    campaign_id TEXT,
    fact TEXT NOT NULL,
    source TEXT,
    pinned_by TEXT DEFAULT 'user',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decision_log_campaign
    ON decision_log(account_id, campaign_id, created_at);
CREATE INDEX IF NOT EXISTS idx_pinned_facts_campaign
    ON pinned_facts(account_id, campaign_id);
"""

# FTS5 must be created separately (not inside executescript easily)
_FTS5_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='rowid',
    tokenize='porter unicode61'
);
"""

# Triggers to keep FTS in sync with messages table
_FTS5_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;
"""


async def get_db() -> aiosqlite.Connection:
    """Open a new database connection with WAL mode and foreign keys enabled."""
    db_path = settings.database_path
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    """Return current schema version, or 0 if no version table exists."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if not await cursor.fetchone():
        return 0
    cursor = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cursor.fetchone()
    return row[0] if row and row[0] else 0


async def _migrate_v1_to_v2(db: aiosqlite.Connection) -> None:
    """Migrate V1 schema to V2. Idempotent — safe to run multiple times."""
    logger.info("Starting V1 → V2 database migration...")

    # 1. Create V2 tables
    await db.executescript(_V2_NEW_TABLES_SQL)

    # 2. Create FTS5 table and triggers
    try:
        await db.executescript(_FTS5_SQL)
        await db.executescript(_FTS5_TRIGGERS_SQL)
    except Exception as e:
        logger.warning("FTS5 setup skipped (may already exist): %s", e)

    # 3. Add account_id column to session_summaries if missing
    cursor = await db.execute("PRAGMA table_info(session_summaries)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "account_id" not in columns:
        await db.execute("ALTER TABLE session_summaries ADD COLUMN account_id TEXT")

    # 3b. Add agent_role column to messages for role attribution
    cursor = await db.execute("PRAGMA table_info(messages)")
    msg_columns = [row[1] for row in await cursor.fetchall()]
    if "agent_role" not in msg_columns:
        await db.execute("ALTER TABLE messages ADD COLUMN agent_role TEXT")
    if "agent_role_name" not in msg_columns:
        await db.execute("ALTER TABLE messages ADD COLUMN agent_role_name TEXT")

    # 4. Populate default account from .env if credentials exist
    default_account_id = settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID
    if default_account_id:
        # Create default account record
        await db.execute(
            """INSERT OR IGNORE INTO accounts_v2 (id, name, mcc_id, level, onboarded_at)
               VALUES (?, ?, NULL, 'mcc', datetime('now'))""",
            (default_account_id, f"Account {default_account_id}"),
        )

        # Backfill account_id on existing conversations
        await db.execute(
            "UPDATE conversations SET account_id = ? WHERE account_id IS NULL",
            (default_account_id,),
        )

        # Backfill account_id on existing session_summaries
        await db.execute(
            "UPDATE session_summaries SET account_id = ? WHERE account_id IS NULL",
            (default_account_id,),
        )

    # 5. Move V1 guideline files into account subfolder
    guidelines_dir = settings.GUIDELINES_DIR
    if default_account_id and guidelines_dir.exists():
        account_dir = guidelines_dir / default_account_id
        md_files = list(guidelines_dir.glob("*.md"))
        if md_files and not account_dir.exists():
            account_dir.mkdir(parents=True, exist_ok=True)
            for md_file in md_files:
                dest = account_dir / md_file.name
                if not dest.exists():
                    shutil.move(str(md_file), str(dest))
                    logger.info("Migrated guideline: %s → %s", md_file.name, dest)

    # 6. Index existing messages into FTS
    try:
        await db.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
    except Exception as e:
        logger.warning("FTS rebuild skipped: %s", e)

    # 7. Record migration
    await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")
    await db.commit()
    logger.info("V1 → V2 migration complete.")


async def init_db() -> None:
    """Create the data directory and all tables. Run migrations if needed."""
    db_path: Path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing DB before migration
    if db_path.exists():
        backup_path = db_path.with_suffix(".db.v1-backup")
        if not backup_path.exists():
            shutil.copy2(str(db_path), str(backup_path))
            logger.info("Backed up V1 database to %s", backup_path)

    db = await get_db()
    try:
        # Ensure V1 tables exist (idempotent)
        await db.executescript(_V1_TABLES_SQL)
        await db.commit()

        # Check schema version and migrate if needed
        version = await _get_schema_version(db)
        if version < 2:
            await _migrate_v1_to_v2(db)
        else:
            logger.info("Database schema is V2 (up to date).")
    finally:
        await db.close()
