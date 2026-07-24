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

-- Context management: conversation compaction checkpoints
CREATE TABLE IF NOT EXISTS conversation_checkpoints (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    checkpoint_number INTEGER NOT NULL,
    summary TEXT NOT NULL,
    messages_compressed INTEGER DEFAULT 0,
    tokens_saved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    UNIQUE(conversation_id, checkpoint_number)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_conv
    ON conversation_checkpoints(conversation_id, checkpoint_number);
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

        # V3: Context management tables (idempotent)
        # V4: Outcome tracking tables
        if version < 4:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    conversation_id TEXT,
                    action_type TEXT NOT NULL,
                    action_detail TEXT NOT NULL,
                    baseline_metrics_json TEXT,
                    status TEXT DEFAULT 'executed',
                    outcome TEXT,
                    outcome_delta_json TEXT,
                    measured_at TEXT,
                    executed_at TEXT DEFAULT (datetime('now')),
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_rec_campaign ON recommendations(account_id, campaign_id, status);
                CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status, executed_at);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (4)")
            await db.commit()
            logger.info("V4 migration complete (recommendations table).")

        if version < 3:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS conversation_checkpoints (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    checkpoint_number INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    messages_compressed INTEGER DEFAULT 0,
                    tokens_saved INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    UNIQUE(conversation_id, checkpoint_number)
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_conv
                    ON conversation_checkpoints(conversation_id, checkpoint_number);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
            await db.commit()
            logger.info("V3 migration complete (conversation_checkpoints).")

        # V5: Skill evolution tables
        if version < 5:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS skill_versions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    score REAL,
                    success_rate REAL,
                    techniques_count INTEGER,
                    optimization_notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(account_id, role_id, version)
                );
                CREATE TABLE IF NOT EXISTS skill_optimizations (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    role_id TEXT NOT NULL,
                    from_version INTEGER,
                    to_version INTEGER,
                    changes_summary TEXT,
                    score_before REAL,
                    score_after REAL,
                    status TEXT DEFAULT 'applied',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_skill_versions_role
                    ON skill_versions(account_id, role_id, version);
                CREATE INDEX IF NOT EXISTS idx_skill_optimizations_role
                    ON skill_optimizations(account_id, role_id, created_at);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (5)")
            await db.commit()
            logger.info("V5 migration complete (skill evolution tables).")

        # V7: Media library for the Studio page — rendered videos + uploaded images/files
        # that can be attached to PMax/Video campaign creative.
        if version < 7:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS ad_assets (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    campaign_id TEXT,
                    type TEXT NOT NULL,            -- video | image | audio | other
                    filename TEXT NOT NULL,
                    url TEXT NOT NULL,             -- public URL the frontend can play/download
                    width INTEGER,
                    height INTEGER,
                    duration REAL,                 -- seconds, for video/audio
                    size_bytes INTEGER,
                    script TEXT,                   -- spoken text, for generated videos
                    thumbnail_url TEXT,
                    source TEXT NOT NULL,          -- generated | uploaded
                    voice_id TEXT,
                    avatar_id TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_ad_assets_account
                    ON ad_assets(account_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_ad_assets_campaign
                    ON ad_assets(campaign_id, created_at DESC);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (7)")
            await db.commit()
            logger.info("V7 migration complete (ad_assets table).")

        # V6: Tag messages with campaign_id so switching campaigns mid-conversation
        # doesn't bleed the previous campaign's Q&A into the new context.
        if version < 6:
            cursor = await db.execute("PRAGMA table_info(messages)")
            cols = [row[1] for row in await cursor.fetchall()]
            if "campaign_id" not in cols:
                await db.execute("ALTER TABLE messages ADD COLUMN campaign_id TEXT")
                await db.execute(
                    "UPDATE messages SET campaign_id = "
                    "(SELECT campaign_id FROM conversations WHERE conversations.id = messages.conversation_id) "
                    "WHERE campaign_id IS NULL"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_conv_campaign "
                    "ON messages(conversation_id, campaign_id)"
                )
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (6)")
            await db.commit()
            logger.info("V6 migration complete (messages.campaign_id).")

        # V8: Guideline edit proposals (E7 — agent suggests, user reviews/applies).
        if version < 8:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS guideline_proposals (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    filename TEXT NOT NULL,            -- e.g. "GREECE_CAMPAIGN_GUIDELINES.md"
                    based_on_hash TEXT NOT NULL,       -- sha256 of source content used to generate
                    based_on_content TEXT NOT NULL,    -- full source content (for diff rendering + apply guard)
                    proposed_content TEXT NOT NULL,    -- full proposed file content
                    rationale TEXT,                    -- why the model is suggesting this
                    evidence_summary TEXT,             -- what sessions/corrections informed it
                    status TEXT DEFAULT 'pending',     -- pending | applied | discarded | stale
                    applied_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_proposals_file
                    ON guideline_proposals(account_id, filename, status, created_at DESC);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (8)")
            await db.commit()
            logger.info("V8 migration complete (guideline_proposals table).")

        # V9: Claude Code handoff flag on conversations.
        # awaits_claude_code is set to 1 when the user clicks the
        # "Send to Claude Code" button in the chat UI. Claude Code's
        # MCP server polls list_conversations(awaits_claude_code=true)
        # to pick up these threads.
        if version < 9:
            for ddl in (
                "ALTER TABLE conversations ADD COLUMN awaits_claude_code INTEGER DEFAULT 0",
                "ALTER TABLE conversations ADD COLUMN handoff_note TEXT",
            ):
                try:
                    await db.execute(ddl)
                except aiosqlite.OperationalError:
                    # column already exists — migration is idempotent
                    pass
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (9)")
            await db.commit()
            logger.info("V9 migration complete (Claude Code handoff columns).")

        # V10: Resumable Claude session id on conversations.
        # When the agent stops mid-task (cost cap, max continuations, user
        # stop) the Claude CLI session id is saved here so the next message
        # in the conversation can --resume it instead of cold-starting and
        # losing the work. Cleared on natural completion / after it is used.
        if version < 10:
            try:
                await db.execute(
                    "ALTER TABLE conversations ADD COLUMN resume_session_id TEXT"
                )
            except aiosqlite.OperationalError:
                pass  # column already exists — idempotent
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (10)")
            await db.commit()
            logger.info("V10 migration complete (resume_session_id column).")

        # V11: first-class `campaigns` table — single source of truth.
        # Until V11 the sidebar, agent, memory panel, and reports each
        # invented their own read path (a JSON blob in `cache`, the live
        # Google Ads API, `_ads_svc.get_campaigns` ad-hoc, `campaign_daily_metrics`
        # rows whose `campaign_status` was always NULL). Anything that
        # disagreed silently won — the same split-brain that bit the chat
        # panel. From V11 onward every consumer reads here.
        if version < 11:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    name TEXT,
                    status TEXT,
                    channel TEXT,
                    bidding_strategy TEXT,
                    budget_micros INTEGER,
                    location TEXT,
                    language TEXT,
                    last_synced_at TEXT NOT NULL DEFAULT (datetime('now')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (account_id, campaign_id)
                );
                CREATE INDEX IF NOT EXISTS idx_campaigns_account
                    ON campaigns(account_id);
                CREATE INDEX IF NOT EXISTS idx_campaigns_account_status
                    ON campaigns(account_id, status);
                CREATE INDEX IF NOT EXISTS idx_campaigns_synced
                    ON campaigns(account_id, last_synced_at);
            """)
            # Best-effort backfill from the JSON blob in `cache` so the
            # table is immediately useful for accounts that already have
            # cached data. Sync worker (Story 2) will refresh on first
            # access anyway, so a corrupt/missing blob is harmless.
            try:
                cur = await db.execute(
                    "SELECT key, data FROM cache WHERE key LIKE '%:campaigns:%'"
                )
                rows = await cur.fetchall()
                imported = 0
                for row in rows:
                    account_id = row["key"].split(":", 1)[0]
                    try:
                        import json as _json
                        payload = _json.loads(row["data"])
                    except Exception:
                        continue
                    if not isinstance(payload, list):
                        continue
                    for c in payload:
                        if not isinstance(c, dict):
                            continue
                        cid = c.get("id") or c.get("campaign_id")
                        if not cid:
                            continue
                        await db.execute(
                            """INSERT OR IGNORE INTO campaigns
                               (campaign_id, account_id, name, status, channel,
                                bidding_strategy, budget_micros, last_synced_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                            (
                                str(cid), account_id,
                                c.get("name"), c.get("status"),
                                c.get("channel") or c.get("advertising_channel_type"),
                                c.get("bidding_strategy"),
                                c.get("budget_micros"),
                            ),
                        )
                        imported += 1
                logger.info("V11 backfill: imported %d campaign rows from cache blob.", imported)
            except Exception as e:
                logger.warning("V11 backfill skipped: %s", e)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (11)")
            await db.commit()
            logger.info("V11 migration complete (campaigns table — single source of truth).")

        # V12: `asset_groups` table — single source of truth for PMax
        # asset groups, mirror of V11's `campaigns` table. Tracks the
        # creative bundle we sent to Google so the wizard / agent can
        # show, edit, and reason about it without re-fetching from the
        # API every read. JSON columns hold the structured copy + asset
        # references because the shape is wide and nested; we don't
        # query inside them, so flattening would be premature.
        if version < 12:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS asset_groups (
                    asset_group_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    name TEXT,
                    status TEXT,
                    final_urls TEXT,          -- JSON list[str]
                    business_name TEXT,
                    headlines TEXT,           -- JSON list[str]
                    long_headlines TEXT,      -- JSON list[str]
                    descriptions TEXT,        -- JSON list[str]
                    asset_refs TEXT,          -- JSON {logos, landscape, square, portrait, videos}
                    signals TEXT,             -- JSON list[dict] (audience signals)
                    last_synced_at TEXT NOT NULL DEFAULT (datetime('now')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (account_id, asset_group_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asset_groups_campaign
                    ON asset_groups(account_id, campaign_id);
                CREATE INDEX IF NOT EXISTS idx_asset_groups_synced
                    ON asset_groups(account_id, last_synced_at);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (12)")
            await db.commit()
            logger.info("V12 migration complete (asset_groups table — PMax single source of truth).")

        # V13: extend `ad_assets` with higgsfield generation metadata.
        # ad_assets stays the single source of truth for everything
        # Studio produces — uploaded files, brand-reel renders, premium-
        # reel renders, and now higgsfield image/video generations. The
        # additions are nullable so existing rows (all `source=uploaded`
        # or `source=generated` for the older video pipelines) remain
        # valid; only higgsfield-sourced rows populate the new columns.
        if version < 13:
            # SQLite doesn't support ADD COLUMN with UNIQUE inline, so
            # the UNIQUE index for higgsfield_job_id is created
            # separately. UNIQUE is essential: the retry path in
            # higgsfield_client can re-poll a job that already submitted
            # successfully, and we MUST NOT create a duplicate row when
            # the second invocation finally completes.
            for col, decl in [
                ("higgsfield_job_id",         "TEXT"),
                ("higgsfield_model",          "TEXT"),
                ("prompt",                    "TEXT"),
                ("aspect_ratio",              "TEXT"),
                ("soul_id",                   "TEXT"),
                ("status",                    "TEXT DEFAULT 'completed'"),
                ("generation_cost_credits",   "INTEGER"),
                ("higgsfield_cdn_url",        "TEXT"),
                ("error_code",                "TEXT"),
                ("error_message",             "TEXT"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE ad_assets ADD COLUMN {col} {decl}")
                except aiosqlite.OperationalError:
                    pass  # column already exists — idempotent
            await db.executescript("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_assets_higgsfield_job
                    ON ad_assets(higgsfield_job_id)
                    WHERE higgsfield_job_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_ad_assets_status
                    ON ad_assets(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_ad_assets_source_account
                    ON ad_assets(source, account_id, created_at);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (13)")
            await db.commit()
            logger.info("V13 migration complete (ad_assets extended with higgsfield columns).")

        # V14: `soul_characters` table — per-account library of trained
        # Higgsfield Soul references. Each row maps our internal id +
        # account_id to a higgsfield soul_id (UUID returned by
        # `higgsfield soul-id create`). status moves pending → training
        # → ready | failed via a background `soul-id wait` task.
        # reference_image_paths stores the local paths of the 5-20
        # photos we uploaded for training (JSON list, used for the UI
        # to show the training inputs).
        if version < 14:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS soul_characters (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    soul_id TEXT UNIQUE,
                    training_model TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reference_image_paths TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    ready_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_soul_characters_account
                    ON soul_characters(account_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_soul_characters_status
                    ON soul_characters(status, created_at);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (14)")
            await db.commit()
            logger.info("V14 migration complete (soul_characters table — Soul library).")

        # V15: Director-orchestrated workflow runs. A workflow is one
        # Director-planned, multi-specialist audit: pre-fetch → plan →
        # parallel specialist reports → debate → synthesis. `workflow_runs`
        # is the run header (goal, plan, status, cost, final output);
        # `workflow_reports` holds each agent's per-phase output so the UI
        # can render the phase tree and the debate/synthesis can read peers.
        if version < 15:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    campaign_id TEXT,
                    campaign_name TEXT,
                    conversation_id TEXT,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',  -- running | done | error | stopped
                    plan_json TEXT,                          -- Director's structured plan
                    final_output TEXT,                       -- Marketing Director synthesis
                    cost REAL NOT NULL DEFAULT 0,
                    budget REAL,
                    stop_reason TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS workflow_reports (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    phase TEXT NOT NULL,                     -- plan | specialist | debate | synthesis
                    role_id TEXT,
                    role_name TEXT,
                    task TEXT,                               -- the prompt this agent was given
                    content TEXT,                            -- the agent's report/output
                    cost REAL NOT NULL DEFAULT 0,
                    seq INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_runs_account
                    ON workflow_runs(account_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_workflow_runs_campaign
                    ON workflow_runs(campaign_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_workflow_reports_run
                    ON workflow_reports(run_id, seq);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (15)")
            await db.commit()
            logger.info("V15 migration complete (workflow_runs + workflow_reports).")

        # V16: timeframe label on workflow runs (daily/weekly/monthly/
        # quarterly/yearly/lifetime) so history can be filtered/compared by
        # period and the UI can group "this week's audit vs last week's".
        if version < 16:
            try:
                await db.execute("ALTER TABLE workflow_runs ADD COLUMN timeframe TEXT")
            except aiosqlite.OperationalError:
                pass  # idempotent
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (16)")
            await db.commit()
            logger.info("V16 migration complete (workflow_runs.timeframe).")

        # V17: Scheduled Plans. Decisions made in chat (or added manually)
        # become time-bound actions the scheduler fires. Safe actions
        # auto-execute; spend/structural ones wait for approval. Recurring
        # plans re-arm after each run. `scheduled_plan_runs` is per-fire history.
        if version < 17:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS scheduled_plans (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    campaign_id TEXT,
                    campaign_name TEXT,
                    conversation_id TEXT,              -- originating chat (nullable)
                    title TEXT NOT NULL,               -- short action label
                    action_detail TEXT NOT NULL,       -- full instruction the agent runs
                    context_snippet TEXT,              -- chat excerpt carried over
                    action_category TEXT DEFAULT 'other', -- budget|bids|status|geo|search_terms|audit|report|other
                    mode TEXT NOT NULL DEFAULT 'approval', -- auto | approval
                    schedule_type TEXT NOT NULL DEFAULT 'once', -- once | recurring
                    run_at TEXT,                       -- ISO datetime for one-time
                    recurrence TEXT,                   -- e.g. 'weekly:mon:09:00' | 'daily:09:00'
                    timezone TEXT DEFAULT 'UTC',
                    status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled|due|running|awaiting_approval|done|failed|paused
                    next_run_at TEXT,                  -- when the scheduler should fire next
                    last_run_at TEXT,
                    last_result TEXT,
                    last_cost REAL DEFAULT 0,
                    proposed_change TEXT,              -- approval-mode diff awaiting sign-off
                    run_count INTEGER DEFAULT 0,
                    created_by TEXT DEFAULT 'user',    -- user | agent
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS scheduled_plan_runs (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL,              -- running|done|failed|skipped|awaiting_approval
                    result TEXT,
                    cost REAL DEFAULT 0,
                    started_at TEXT NOT NULL DEFAULT (datetime('now')),
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_plans_account
                    ON scheduled_plans(account_id, next_run_at);
                CREATE INDEX IF NOT EXISTS idx_plans_campaign
                    ON scheduled_plans(campaign_id, next_run_at);
                CREATE INDEX IF NOT EXISTS idx_plans_due
                    ON scheduled_plans(status, next_run_at);
                CREATE INDEX IF NOT EXISTS idx_plan_runs_plan
                    ON scheduled_plan_runs(plan_id, started_at DESC);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (17)")
            await db.commit()
            logger.info("V17 migration complete (scheduled_plans + scheduled_plan_runs).")

        # V18: `ad_assets.prompt_hash` — cache key for higgsfield clips
        # used as storyboard scenes (Epic 11 P1). A re-render of the
        # same storyboard must NOT re-burn credits: the renderer hashes
        # (model | prompt | duration | aspect) and reuses any completed
        # row with the same hash whose local file still exists.
        if version < 18:
            try:
                await db.execute("ALTER TABLE ad_assets ADD COLUMN prompt_hash TEXT")
            except aiosqlite.OperationalError:
                pass  # idempotent
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ad_assets_prompt_hash
                    ON ad_assets(prompt_hash)
                    WHERE prompt_hash IS NOT NULL
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (18)")
            await db.commit()
            logger.info("V18 migration complete (ad_assets.prompt_hash for clip reuse).")

        # V19: account-mode audit report read model + runner reliability.
        #
        # `account_reports` = latest-wins persistence of the normalized
        # `account_report` the orchestrator emits for an account-mode run
        # (Story 13.2). One row per (account_id) is the "latest" — we UPSERT
        # on account_id so the homepage read is O(1): SELECT ... WHERE
        # account_id = ?. History is retained via source run_id + generated_at
        # (older reports are overwritten in the latest slot but the underlying
        # workflow_runs / workflow_reports rows remain the audit trail).
        #
        # `workflow_runs` also gains a `stop_reason` (already present from V15)
        # and now needs nothing new for stop — status already has a 'stopped'
        # value in the CHECK-comment. The zombie sweeper flips stale 'running'
        # rows to 'failed' with stop_reason='stale' using existing columns.
        if version < 19:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS account_reports (
                    account_id TEXT PRIMARY KEY,          -- latest-wins: one row per account
                    run_id TEXT NOT NULL,                 -- source workflow_runs.id
                    findings_json TEXT NOT NULL,          -- JSON: full normalized account_report
                    total_recoverable_wk REAL NOT NULL DEFAULT 0,
                    campaigns_audited INTEGER NOT NULL DEFAULT 0,
                    campaigns_excluded INTEGER NOT NULL DEFAULT 0,
                    parse_ok INTEGER NOT NULL DEFAULT 0,
                    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_account_reports_generated
                    ON account_reports(account_id, generated_at DESC);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (19)")
            await db.commit()
            logger.info("V19 migration complete (account_reports latest-wins read model).")

        # V20: finding→action decision state (Story 13.3).
        #
        # The homepage fix list turns each persisted account-report finding
        # (and each fast-signal) into a concrete approvable ACTION. This table
        # records the OPERATOR'S DECISION on each one — approved / approved_once
        # / denied — plus the resulting Scheduled Plan id when the action was
        # routed into the plan/approval lifecycle.
        #
        # Keyed by (account_id, finding_key): finding_key is a stable content
        # hash of the source finding/signal (category + campaigns + title), so
        # the SAME finding across re-audits maps to the SAME row — a DENY
        # persists and keeps the finding suppressed until the finding's content
        # actually changes (i.e. it's genuinely re-surfaced by a new audit).
        # No Google Ads mutation ever lives here; execution is always the plan
        # path (scheduler.py), which is scope-guarded.
        if version < 20:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS finding_actions (
                    account_id TEXT NOT NULL,
                    finding_key TEXT NOT NULL,          -- stable content hash of the finding/signal
                    source TEXT NOT NULL DEFAULT 'finding', -- finding | signal
                    title TEXT,                         -- snapshot for audit/debug
                    action_category TEXT,               -- scheduler taxonomy at decision time
                    status TEXT NOT NULL DEFAULT 'proposed', -- proposed|approved|approved_once|denied
                    plan_id TEXT,                       -- resulting scheduled_plans.id (nullable)
                    dollar_impact_wk REAL,              -- snapshot of the $ estimate (nullable)
                    decided_by TEXT DEFAULT 'user',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (account_id, finding_key)
                );
                CREATE INDEX IF NOT EXISTS idx_finding_actions_account
                    ON finding_actions(account_id, status);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (20)")
            await db.commit()
            logger.info("V20 migration complete (finding_actions decision state).")

        # V21: sync_state ledger (Dashboard v2.1 — Epic A, P0 freshness).
        #
        # The canonical per-account, per-domain freshness ledger. Every sync
        # ATTEMPT writes here (in_progress flag + last_attempt_at at start;
        # last_success_at / data_through_date / consecutive_failures / last_error
        # at the end). This is the single source of truth the dashboard reads to
        # answer "is this account's data fresh, syncing, stale, or erroring?" —
        # replacing the ambiguous sync_status (which conflated "checked, no data"
        # with "never checked"). `data_through_date` is the MAX(date) actually
        # written for the account so freshness compares against real coverage,
        # not a wall-clock guess. Keyed by (account_id, domain) so future domains
        # (search_terms, assets, …) get their own row without schema churn.
        if version < 21:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS sync_state (
                    account_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    last_attempt_at TEXT,
                    last_success_at TEXT,
                    last_error TEXT,
                    consecutive_failures INTEGER DEFAULT 0,
                    in_progress INTEGER DEFAULT 0,
                    data_through_date TEXT,
                    PRIMARY KEY (account_id, domain)
                );
                CREATE INDEX IF NOT EXISTS idx_sync_state_account
                    ON sync_state(account_id, domain);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (21)")
            await db.commit()
            logger.info("V21 migration complete (sync_state freshness ledger).")

        # V22: Chat Orchestration v2 — turn runner persistence (Epic 1.1).
        #
        # `chat_turns` = one row per agent turn (a single POST /message run).
        # It is the durable lifecycle record the chat_runner's detached task
        # owns: the runner mints turn_id up front, inserts the row before
        # launching, and flips `status` (running→done|failed|stopped|stale)
        # from the driver — so a restart shows honest terminal states via the
        # same zombie-sweep idea as workflow_runs (workflow_runner.py:222-248).
        # `parent_turn_id` is nullable and baked in now for Epic 8 sub-turns
        # (NULL for every top-level turn) — one column now saves a migration
        # later. `mode` = direct|orchestrated|delegated; direct is today's
        # single-persona passthrough.
        #
        # `chat_turn_events` = the append-only, batched-flush event log per
        # turn (seq is the monotonic hub cursor). History replay reads this
        # table, so a reconnect after a restart still catches up — fixing the
        # process-local `_agent_buffers` loss (chat.py:35-38).
        #
        # `messages.turn_id` links a persisted assistant/user message to its
        # originating turn (nullable — legacy rows keep rendering exactly as
        # today). `workflow_reports.origin` distinguishes chat-dispatched
        # specialist reports ('chat') from Team-Audit workflow reports
        # ('workflow', the default) so Epic 2's recall can scope its reads.
        if version < 22:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS chat_turns (
                    turn_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    campaign_id TEXT,
                    parent_turn_id TEXT,                    -- nullable; Epic-8 sub-turns only, NULL for top-level
                    mode TEXT NOT NULL DEFAULT 'direct',    -- direct|orchestrated|delegated
                    status TEXT NOT NULL DEFAULT 'running', -- running|done|failed|stopped|stale
                    cost REAL NOT NULL DEFAULT 0,
                    agents_used INTEGER DEFAULT 0,
                    conflicts INTEGER DEFAULT 0,
                    started_at TEXT DEFAULT (datetime('now')),
                    finished_at TEXT,
                    final_message_id TEXT,
                    stop_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_chat_turns_conversation
                    ON chat_turns(conversation_id, started_at DESC);

                CREATE TABLE IF NOT EXISTS chat_turn_events (
                    turn_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (turn_id, seq)
                );
                CREATE INDEX IF NOT EXISTS idx_chat_turn_events_turn
                    ON chat_turn_events(turn_id, seq);
            """)
            # Additive columns — guard each with PRAGMA table_info so re-running
            # init_db on an already-migrated DB never raises (V16/V18 idiom).
            cursor = await db.execute("PRAGMA table_info(messages)")
            msg_cols = [row[1] for row in await cursor.fetchall()]
            if "turn_id" not in msg_cols:
                await db.execute("ALTER TABLE messages ADD COLUMN turn_id TEXT")
            cursor = await db.execute("PRAGMA table_info(workflow_reports)")
            wr_cols = [row[1] for row in await cursor.fetchall()]
            if "origin" not in wr_cols:
                await db.execute(
                    "ALTER TABLE workflow_reports ADD COLUMN origin TEXT DEFAULT 'workflow'"
                )
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (22)")
            await db.commit()
            logger.info("V22 migration complete (chat_turns + chat_turn_events + turn linkage).")

        # V23: Studio video-director foundation (studio redesign §6.5, §10.2).
        #
        # `studio_video_projects` = one row per AI-Video-Studio project — the
        # durable source of truth for a Video-Director-led video (brief →
        # model → storyboard → render). It is deliberately a table, not
        # browser state: after the builder-state failure (memory
        # `feedback_builder_frustration.md`) and the PMax localStorage lesson,
        # in-progress work must survive a refresh, a tab close, or a second
        # machine. `conversation_id` binds to the Director's chat thread;
        # `storyboard_json` holds the latest full storyboard (DB = truth);
        # `status` walks drafting→storyboard→rendering→done|abandoned;
        # `consult_director` defaults ON when campaign-linked (§13).
        #
        # `brand_avatars` = a persistent, reusable AI avatar per account —
        # it references an already-trained Higgsfield Soul (`soul_id`, the
        # reference_id returned by the existing SoulCreator flow) plus a TTS
        # `voice_id`, so a brand's face + voice can be reused across projects
        # without re-training. Both tables ALTER nothing existing (additive).
        if version < 23:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS studio_video_projects (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    campaign_id TEXT,
                    conversation_id TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    brief TEXT DEFAULT '',
                    model_id TEXT NOT NULL,
                    target_seconds INTEGER NOT NULL,
                    aspect TEXT NOT NULL DEFAULT '16:9',
                    consult_director INTEGER NOT NULL DEFAULT 1,   -- §13 default: consult ON when campaign-linked
                    storyboard_json TEXT,
                    status TEXT NOT NULL DEFAULT 'drafting',        -- drafting|storyboard|rendering|done|abandoned
                    asset_id TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_studio_video_projects_account
                    ON studio_video_projects(account_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS brand_avatars (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    soul_id TEXT,          -- trained Higgsfield Soul reference_id (reuses existing SoulCreator output)
                    voice_id TEXT,         -- TTS voice
                    style_notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_brand_avatars_account
                    ON brand_avatars(account_id, created_at DESC);
            """)
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (23)")
            await db.commit()
            logger.info("V23 migration complete (studio_video_projects + brand_avatars).")

        # V24: persist the draft brief source on a video project. Additive —
        # a JSON string of {type, url} recording how the operator seeded the
        # draft (text | campaign | landing_page). NULL for pre-V24 rows and
        # for plain-text drafts (default "text" behavior unchanged).
        if version < 24:
            cursor = await db.execute("PRAGMA table_info(studio_video_projects)")
            svp_cols = [row[1] for row in await cursor.fetchall()]
            if "brief_source" not in svp_cols:
                await db.execute(
                    "ALTER TABLE studio_video_projects ADD COLUMN brief_source TEXT"
                )
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (24)")
            await db.commit()
            logger.info("V24 migration complete (studio_video_projects.brief_source).")

        # V25: `change_log` — the campaign Changelog with 1-click revert. Every
        # write the app can attribute (app-user button, chat-specialist MCP tool,
        # scheduler plan, API) is captured here with before→after state and, when
        # the inverse is safe, a `revert_spec` describing how to undo it via the
        # existing service layer. External (out-of-app) changes surface from the
        # `external_change` table (revertible=0). See app/services/change_log.py
        # + change_capture.py + change_revert.py.
        if version < 25:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL DEFAULT (datetime('now')),
                    actor_type TEXT NOT NULL DEFAULT 'api',
                    actor_detail TEXT,
                    account_id TEXT,
                    campaign_id TEXT,
                    resource TEXT NOT NULL DEFAULT 'unknown',
                    resource_name TEXT,
                    action TEXT NOT NULL DEFAULT 'update',
                    field TEXT,
                    before_value TEXT,
                    after_value TEXT,
                    summary TEXT,
                    tool_name TEXT,
                    batch_id TEXT,
                    batch_count INTEGER DEFAULT 1,
                    revertible INTEGER NOT NULL DEFAULT 0,
                    revert_reason TEXT,
                    revert_spec TEXT,
                    reverts INTEGER,
                    reverted_by INTEGER,
                    reverted_at TEXT
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_change_log_account_ts "
                "ON change_log(account_id, ts)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_change_log_campaign_ts "
                "ON change_log(campaign_id, ts)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_change_log_batch "
                "ON change_log(batch_id)"
            )
            await db.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (25)")
            await db.commit()
            logger.info("V25 migration complete (change_log — Changelog + revert).")

        if version >= 25:
            logger.info("Database schema is V25 (up to date).")
    finally:
        await db.close()
