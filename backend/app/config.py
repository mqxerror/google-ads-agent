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

    # Chrome MCP (optional, for future AI agent)
    CHROME_MCP_ENABLED: bool = False

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
