"""Setup & credential management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database import get_db
from app.models.schemas import (
    SetupCredentialsRequest,
    SetupStatusResponse,
    SetupValidateResponse,
)

router = APIRouter(prefix="/api/setup", tags=["setup"])

_CREDENTIAL_KEYS = [
    "developer_token",
    "client_id",
    "client_secret",
    "refresh_token",
    "login_customer_id",
]


async def _get_config(key: str) -> str | None:
    db = await get_db()
    try:
        cur = await db.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else None
    finally:
        await db.close()


async def _set_config(key: str, value: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO config (key, value, updated_at) "
            "VALUES (?, ?, datetime('now'))",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/credentials")
async def store_credentials(body: SetupCredentialsRequest) -> dict:
    """Store Google Ads API credentials in the config table."""
    pairs = {
        "developer_token": body.developer_token,
        "client_id": body.client_id,
        "client_secret": body.client_secret,
        "refresh_token": body.refresh_token,
    }
    if body.login_customer_id:
        pairs["login_customer_id"] = body.login_customer_id
    for k, v in pairs.items():
        await _set_config(k, v)

    return {"status": "ok", "keys_stored": list(pairs.keys())}


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status() -> SetupStatusResponse:
    """Check which credentials are already configured."""
    db = await get_db()
    try:
        cur = await db.execute("SELECT key, value FROM config WHERE key IN ({})".format(
            ",".join("?" for _ in _CREDENTIAL_KEYS)
        ), _CREDENTIAL_KEYS)
        rows = await cur.fetchall()
    finally:
        await db.close()

    stored = {row["key"]: row["value"] for row in rows}
    return SetupStatusResponse(
        configured=all(
            stored.get(k) for k in ["developer_token", "client_id", "client_secret", "refresh_token"]
        ),
        has_developer_token=bool(stored.get("developer_token")),
        has_client_id=bool(stored.get("client_id")),
        has_client_secret=bool(stored.get("client_secret")),
        has_refresh_token=bool(stored.get("refresh_token")),
        has_login_customer_id=bool(stored.get("login_customer_id")),
    )


@router.post("/validate", response_model=SetupValidateResponse)
async def validate_credentials() -> SetupValidateResponse:
    """Validate that stored credentials are non-empty (basic check)."""
    required = ["developer_token", "client_id", "client_secret", "refresh_token"]
    errors: list[str] = []
    for key in required:
        val = await _get_config(key)
        if not val:
            errors.append(f"Missing or empty: {key}")
    return SetupValidateResponse(valid=len(errors) == 0, errors=errors)
