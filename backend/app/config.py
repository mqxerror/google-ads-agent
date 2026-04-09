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

    # Agent auto-continuation — prevents stopping mid-task
    AGENT_MAX_TURNS_PER_SEGMENT: int = 200  # turns per CLI invocation (high = harness mode)
    AGENT_MAX_CONTINUATIONS: int = 5        # auto-resume cycles if 200 isn't enough (up to 1000 total)
    AGENT_MAX_TOTAL_COST_USD: float = 10.0  # cost safety cap

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
    CACHE_TTL_SECONDS: int = 300

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
