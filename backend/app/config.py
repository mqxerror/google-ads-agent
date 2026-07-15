from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    # Paths
    PROJECT_ROOT: Path = _PROJECT_ROOT
    DATA_DIR: Path = _PROJECT_ROOT.parent / "data"
    GUIDELINES_DIR: Path = _PROJECT_ROOT.parent / "data" / "guidelines"

    # Google Ads API credentials
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""
    GOOGLE_ADS_CLIENT_ID: str = ""
    GOOGLE_ADS_CLIENT_SECRET: str = ""
    GOOGLE_ADS_REFRESH_TOKEN: str = ""
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = ""

    # Chrome MCP (optional — browser automation via Chrome DevTools Protocol)
    # Uses chrome-devtools-mcp (official from Google Chrome DevTools team, Apache-2.0)
    CHROME_MCP_ENABLED: bool = False
    CHROME_MCP_COMMAND: str = "npx"
    CHROME_MCP_ARGS: list[str] = ["-y", "chrome-devtools-mcp@latest"]
    # Connect to existing Chrome (preserves logged-in tabs) vs start fresh browser
    # When True, appends --browser-url=http://127.0.0.1:9222 to reuse user's Chrome
    # User must launch Chrome with --remote-debugging-port=9222 first
    CHROME_REUSE_EXISTING: bool = True
    CHROME_DEBUG_PORT: int = 9222
    # Use user's default Chrome profile (logins preserved) vs a clean agent profile
    CHROME_USE_DEFAULT_PROFILE: bool = True

    # GTM MCP (optional — Google Tag Manager API for tag creation/management)
    # Uses VasthavM/google-tag-manager-mcp (Go, MIT, 50 tools, local stdio)
    # Setup: git clone, go build, then set path below
    GTM_MCP_ENABLED: bool = False
    GTM_MCP_COMMAND: str = ""  # Path to compiled binary, e.g. /usr/local/bin/google-tag-manager-mcp

    # Microsoft Clarity MCP (optional — heatmaps, session recordings, behavioral analytics)
    # Uses @microsoft/clarity-mcp-server (official, npm)
    # Setup: get API token from Clarity → Settings → Data Export → Generate
    CLARITY_MCP_ENABLED: bool = False
    CLARITY_PROJECT_ID: str = ""
    CLARITY_API_TOKEN: str = ""

    # Video creative pipeline (Mercan account only for now)
    HEYGEN_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    YOUTUBE_UPLOAD_CHANNEL: str = "mercan"
    HEYGEN_DEFAULT_AVATAR_ID: str = "Abigail_expressive_2024112501"
    ELEVENLABS_DEFAULT_VOICE_ID: str = "EXAVITQu4vr4xnSDxMaL"  # Sarah — mature, reassuring

    # Stock image APIs (free) — used when Director needs a broll image and the
    # user hasn't supplied any from their library. Either or both work.
    UNSPLASH_ACCESS_KEY: str = ""        # https://unsplash.com/developers — 50 req/hr free tier
    PEXELS_API_KEY: str = ""             # https://www.pexels.com/api — generous free tier
    # AI image generation — Replicate runs FLUX cheaply (~$0.003/image, ~3s).
    # Only used when explicitly requested per scene; never auto-charged.
    REPLICATE_API_TOKEN: str = ""        # https://replicate.com/account/api-tokens

    # Agent auto-continuation — prevents stopping mid-task
    AGENT_MAX_TURNS_PER_SEGMENT: int = 200  # turns per CLI invocation (high = harness mode)
    AGENT_MAX_CONTINUATIONS: int = 5        # auto-resume cycles if 200 isn't enough (up to 1000 total)
    AGENT_MAX_TOTAL_COST_USD: float = 25.0  # cost safety cap (env: AGENT_MAX_TOTAL_COST_USD)

    # Workflow orchestrator (Team Audit)
    WORKFLOW_MAX_COST_USD: float = 50.0   # per-run cost cap — degrades to synthesis, never hard-fails
    WORKFLOW_MAX_CAMPAIGNS: int = 5       # account-wide mode: campaigns per run (highest recent spend first; excluded ones are named in the report)
    # Runner reliability (Story 13.2). A run executes in a detached background
    # task decoupled from the SSE stream; a client disconnect no longer cancels
    # it. The sweeper marks any run still 'running' whose updated_at is older
    # than WORKFLOW_MAX_RUNTIME_MINUTES * WORKFLOW_STALE_MULTIPLIER as failed —
    # this reaps orphaned zombies (e.g. from the pre-fix in-stream execution).
    WORKFLOW_MAX_RUNTIME_MINUTES: int = 20   # a generous ceiling for one full audit
    WORKFLOW_STALE_MULTIPLIER: float = 2.0   # sweep threshold = runtime * this
    WORKFLOW_SWEEP_INTERVAL_MINUTES: int = 10  # periodic zombie sweep cadence

    # Chat Orchestration v2 (Epic 1+). The turn runner executes each chat turn
    # in a detached background task decoupled from the SSE viewer (mirrors the
    # workflow runner). These caps bound an orchestrated turn; the sweeper marks
    # any chat_turn still 'running' past CHAT_ORCH_MAX_RUNTIME_MIN *
    # CHAT_ORCH_STALE_MULTIPLIER as stale so a restart shows honest state.
    CHAT_ORCH_MAX_COST_USD: float = 5.0        # per-turn orchestration cost cap
    CHAT_ORCH_MAX_RUNTIME_MIN: float = 6.0     # per-turn wall-clock ceiling
    CHAT_ORCH_MAX_SPECIALISTS: int = 3         # max parallel specialists per turn
    CHAT_ORCH_STALE_MULTIPLIER: float = 2.0    # zombie-sweep threshold = runtime * this
    CHAT_ORCH_SWEEP_INTERVAL_MINUTES: float = 5.0  # periodic chat-turn zombie sweep cadence
    CHAT_TURN_EVENT_FLUSH_COUNT: int = 20      # batch flush to chat_turn_events every N events
    CHAT_TURN_EVENT_FLUSH_MS: int = 500        # …or every this many ms, whichever first
    AGENT_STREAM_PARTIAL_MESSAGES: bool = False  # token-level streaming previews (story 1.4); requires a CLI that supports --include-partial-messages

    # Account report staleness (Story 13.2). The homepage shows "audited Nh ago"
    # and flags the report stale past this age so the operator knows to re-run.
    ACCOUNT_REPORT_STALE_HOURS: float = 24.0

    # Fast-signals lane (Story 13.2) — deterministic, always-fresh thresholds.
    # Budget pacing: flag a campaign whose day-so-far spend projects to exceed
    # its daily budget by this ratio (or is already over). Wasted spend: a
    # campaign with >= this spend over the window and ZERO conversions.
    FAST_SIGNAL_PACING_RATIO: float = 1.2       # projected spend / budget alert threshold
    FAST_SIGNAL_WASTE_MIN_SPEND: float = 10.0   # min $ over window to flag 0-conv waste
    FAST_SIGNAL_WINDOW_DAYS: int = 7            # window for pacing/waste rollups

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
    CACHE_TTL_SECONDS: int = 300

    # Background sync
    SYNC_INTERVAL_HOURS: int = 6
    SYNC_LOOKBACK_DAYS: int = 30
    SYNC_ENABLED: bool = True

    # Dashboard v2.1 (Epic A) — two-cadence metrics sync. The hot loop runs
    # every METRICS_HOT_SYNC_MINUTES over just the last METRICS_HOT_WINDOW_DAYS
    # (cheap, keeps "today/yesterday" fresh). Once per day the loop instead does
    # a full METRICS_FULL_SYNC_LOOKBACK-day re-pull to restate conversions that
    # Google attributes late (conversion lag). All READ-ONLY GAQL.
    METRICS_HOT_SYNC_MINUTES: int = 60
    METRICS_HOT_WINDOW_DAYS: int = 3
    METRICS_FULL_SYNC_LOOKBACK: int = 30
    # Self-heal (A4) stampede guard: a read-triggered background sync will NOT
    # kick if the last attempt for this account was under this many minutes ago,
    # so multiple tabs / rapid navigation can't loop the sync.
    METRICS_SELF_HEAL_MIN_INTERVAL_MINUTES: int = 10

    # MCP server bearer token — Claude Code uses this to call /mcp on the
    # backend. Leave blank to auto-generate per-process (token logged at
    # startup); set in .env for a stable value across restarts.
    MERCAN_MCP_TOKEN: str = ""

    # Memory
    MEMORY_DIR: Path = _PROJECT_ROOT.parent / "data" / "memory"

    # Context limits
    RECENT_MESSAGES_LIMIT: int = 10
    SESSION_SUMMARIES_LIMIT: int = 5
    MAX_SNAPSHOT_DAYS: int = 30

    # Context budget management
    CONTEXT_BUDGET_SAFETY_RATIO: float = 0.85   # Use 85% of model's context window
    CONTEXT_WARN_THRESHOLD: float = 0.70        # Show warning badge at 70%
    CONTEXT_COMPACT_THRESHOLD: float = 0.85     # Auto-compact at 85%
    CONTEXT_RELEVANCE_WEIGHT: float = 0.7       # Weight for keyword overlap in message selection
    CONTEXT_RECENCY_WEIGHT: float = 0.3         # Weight for recency in message selection
    CONTEXT_MAX_SELECTED_MESSAGES: int = 12     # Max messages after relevance selection
    CONTEXT_PRESERVE_LAST_N: int = 4            # Always keep last N messages verbatim

    model_config = {
        "env_prefix": "",
        "env_file": str(_PROJECT_ROOT / ".env"),
    }

    @property
    def database_path(self) -> Path:
        return self.DATA_DIR / "app.db"

    @property
    def has_google_ads_credentials(self) -> bool:
        return bool(
            self.GOOGLE_ADS_DEVELOPER_TOKEN
            and self.GOOGLE_ADS_CLIENT_ID
            and self.GOOGLE_ADS_CLIENT_SECRET
            and self.GOOGLE_ADS_REFRESH_TOKEN
        )


settings = Settings()
