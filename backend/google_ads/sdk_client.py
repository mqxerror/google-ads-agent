"""Google Ads SDK client for MCP server."""

import os
from typing import Optional, Dict, Any

import yaml
from google.ads.googleads.client import GoogleAdsClient

from google_ads.utils import get_logger

logger = get_logger(__name__)


class GoogleAdsSdkClient:
    """SDK client for Google Ads with OAuth or service account authentication."""

    def __init__(self, config_path: str = "./env/google-ads.yaml"):
        """Initialize the SDK client with configuration."""
        self.config_path = config_path
        self._client: Optional[GoogleAdsClient] = None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from env vars or YAML file."""
        # Try environment variables first (OAuth refresh token flow)
        developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
        if developer_token:
            config: Dict[str, Any] = {
                "developer_token": developer_token,
                "use_proto_plus": True,
            }

            client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
            refresh_token = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")

            if client_id and client_secret and refresh_token:
                config["client_id"] = client_id
                config["client_secret"] = client_secret
                config["refresh_token"] = refresh_token
            else:
                raise ValueError(
                    "OAuth credentials incomplete. Need GOOGLE_ADS_CLIENT_ID, "
                    "GOOGLE_ADS_CLIENT_SECRET, and GOOGLE_ADS_REFRESH_TOKEN"
                )

            login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
            if login_customer_id:
                config["login_customer_id"] = login_customer_id.replace("-", "")

            return config

        # Fall back to YAML file (service account flow)
        with open(self.config_path, "r") as f:
            yaml_config = yaml.safe_load(f)

        required_fields = ["developer_token", "json_key_file_path"]
        for field in required_fields:
            if field not in yaml_config:
                raise ValueError(f"Missing required field in config: {field}")

        return yaml_config

    @property
    def client(self) -> GoogleAdsClient:
        """Get or create the Google Ads client."""
        if self._client is None:
            config = self._load_config()

            # Build configuration dictionary for GoogleAdsClient
            client_config: Dict[str, Any] = {
                "developer_token": config["developer_token"],
                "use_proto_plus": True,
            }

            # OAuth refresh token auth
            if "client_id" in config:
                client_config["client_id"] = config["client_id"]
                client_config["client_secret"] = config["client_secret"]
                client_config["refresh_token"] = config["refresh_token"]
            # Service account auth
            elif "json_key_file_path" in config:
                client_config["json_key_file_path"] = config["json_key_file_path"]

            # Add optional login_customer_id
            if "login_customer_id" in config:
                login_customer_id = str(config["login_customer_id"]).replace("-", "")
                client_config["login_customer_id"] = login_customer_id

            # Create client from dictionary
            self._client = GoogleAdsClient.load_from_dict(client_config)
            logger.info("Google Ads SDK client initialized successfully")

        return self._client

    def close(self) -> None:
        """Close the client and clean up resources."""
        if self._client:
            # The SDK client doesn't have an explicit close method
            # but we can clear the reference
            self._client = None
            logger.info("Google Ads SDK client closed")


# Global client instance
_sdk_client: Optional[GoogleAdsSdkClient] = None


def get_sdk_client() -> GoogleAdsSdkClient:
    """Get the global SDK client instance."""
    global _sdk_client
    if _sdk_client is None:
        raise RuntimeError("SDK client not initialized. Call set_sdk_client first.")
    return _sdk_client


def set_sdk_client(client: GoogleAdsSdkClient) -> None:
    """Set the global SDK client instance."""
    global _sdk_client
    _sdk_client = client
