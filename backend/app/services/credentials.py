"""Encrypted credential storage for multi-account Google Ads credentials."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


class CredentialStore:
    """Encrypt/decrypt Google Ads credentials in SQLite."""

    def __init__(self):
        self._fernet = Fernet(self._derive_key())

    @staticmethod
    def _derive_key() -> bytes:
        """Derive a stable encryption key from machine-specific data."""
        machine_id = str(uuid.getnode())  # MAC address — stable across restarts
        key = hashlib.pbkdf2_hmac(
            "sha256", machine_id.encode(), b"google-ads-agent-v2", 100_000
        )
        return base64.urlsafe_b64encode(key)

    def _encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def _decrypt(self, token: bytes) -> str:
        return self._fernet.decrypt(token).decode()

    async def store_credentials(
        self,
        account_id: str,
        credentials: dict,
    ) -> None:
        """Encrypt and store credentials for an account."""
        db = await get_db()
        try:
            await db.execute(
                """INSERT OR REPLACE INTO account_credentials
                   (account_id, developer_token_encrypted, client_id_encrypted,
                    client_secret_encrypted, refresh_token_encrypted,
                    login_customer_id, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    account_id,
                    self._encrypt(credentials["developer_token"]),
                    self._encrypt(credentials["client_id"]),
                    self._encrypt(credentials["client_secret"]),
                    self._encrypt(credentials["refresh_token"]),
                    credentials.get("login_customer_id", account_id),
                ),
            )
            await db.commit()
        finally:
            await db.close()

    async def get_credentials(self, account_id: str) -> dict | None:
        """Retrieve and decrypt credentials for an account.

        Returns None if no credentials found. Falls back to .env for the
        default account (V1 compatibility).
        """
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT developer_token_encrypted, client_id_encrypted,
                          client_secret_encrypted, refresh_token_encrypted,
                          login_customer_id
                   FROM account_credentials WHERE account_id = ?""",
                (account_id,),
            )
            row = await cursor.fetchone()
        finally:
            await db.close()

        if row:
            try:
                return {
                    "developer_token": self._decrypt(row["developer_token_encrypted"]),
                    "client_id": self._decrypt(row["client_id_encrypted"]),
                    "client_secret": self._decrypt(row["client_secret_encrypted"]),
                    "refresh_token": self._decrypt(row["refresh_token_encrypted"]),
                    "login_customer_id": row["login_customer_id"] or account_id,
                }
            except InvalidToken:
                logger.error("Failed to decrypt credentials for account %s", account_id)
                return None

        # V1 fallback: if no DB credentials, try .env
        if settings.has_google_ads_credentials:
            return {
                "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
                "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
            }

        return None

    async def delete_credentials(self, account_id: str) -> None:
        """Remove credentials for an account."""
        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM account_credentials WHERE account_id = ?",
                (account_id,),
            )
            await db.commit()
        finally:
            await db.close()

    async def has_credentials(self, account_id: str) -> bool:
        """Check if encrypted credentials exist for an account."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT 1 FROM account_credentials WHERE account_id = ?",
                (account_id,),
            )
            return bool(await cursor.fetchone())
        finally:
            await db.close()

    async def migrate_env_credentials(self, account_id: str) -> bool:
        """Migrate .env credentials into encrypted DB storage.

        Returns True if migration happened, False if skipped.
        """
        if not settings.has_google_ads_credentials:
            return False

        if await self.has_credentials(account_id):
            return False  # Already migrated

        await self.store_credentials(account_id, {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": settings.GOOGLE_ADS_CLIENT_ID,
            "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
            "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
        })
        logger.info("Migrated .env credentials for account %s to encrypted DB", account_id)
        return True
