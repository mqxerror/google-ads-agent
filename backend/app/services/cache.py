"""Caching layer backed by the SQLite cache table."""

from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable

from app.config import settings
from app.database import get_db


class CacheService:
    """Simple JSON cache stored in the SQLite ``cache`` table."""

    def __init__(self, default_ttl: int | None = None):
        self.default_ttl = default_ttl or settings.CACHE_TTL_SECONDS

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl: int | None = None,
    ) -> Any:
        """Return cached data if fresh, otherwise call *fetch_fn* and store."""
        ttl = ttl if ttl is not None else self.default_ttl
        now = time.time()

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT data, fetched_at FROM cache WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()

            if row is not None:
                fetched_at = row["fetched_at"]
                if now - fetched_at < ttl:
                    return json.loads(row["data"])

            # Cache miss or stale -- fetch fresh data
            data = await fetch_fn()
            # Handle Pydantic models
            if isinstance(data, list) and data and hasattr(data[0], 'model_dump'):
                serializable = [item.model_dump() for item in data]
            elif hasattr(data, 'model_dump'):
                serializable = data.model_dump()
            else:
                serializable = data
            serialized = json.dumps(serializable, default=str)

            await db.execute(
                "INSERT OR REPLACE INTO cache (key, data, fetched_at) VALUES (?, ?, ?)",
                (key, serialized, now),
            )
            await db.commit()
            return data
        finally:
            await db.close()

    async def invalidate(self, key_prefix: str) -> int:
        """Delete all cache entries whose key starts with *key_prefix*.

        Returns the number of rows deleted.
        """
        db = await get_db()
        try:
            cursor = await db.execute(
                "DELETE FROM cache WHERE key LIKE ?", (f"{key_prefix}%",)
            )
            await db.commit()
            return cursor.rowcount
        finally:
            await db.close()

    async def clear_all(self) -> int:
        """Remove every entry from the cache table."""
        db = await get_db()
        try:
            cursor = await db.execute("DELETE FROM cache")
            await db.commit()
            return cursor.rowcount
        finally:
            await db.close()
