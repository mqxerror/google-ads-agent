"""Caching layer backed by the SQLite cache table."""

from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable

from app.config import settings
from app.database import get_db


class CacheService:
    """Simple JSON cache stored in the SQLite ``cache`` table.

    Includes a circuit breaker: after an API failure, skip live fetches
    for 60 seconds and serve stale cache immediately.
    """

    _circuit_open_until: float = 0  # timestamp when circuit breaker closes

    def __init__(self, default_ttl: int | None = None):
        self.default_ttl = default_ttl or settings.CACHE_TTL_SECONDS

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable[[], Awaitable[Any]],
        ttl: int | None = None,
        return_meta: bool = False,
    ) -> Any:
        """Return cached data if fresh, otherwise call *fetch_fn* and store.

        Default (``return_meta=False``): behaviour is IDENTICAL to before — the
        raw data (or ``[]`` on open-circuit-with-no-cache) is returned. Existing
        callers are unaffected.

        Cache honesty (``return_meta=True``): returns ``(data, meta)`` where
        ``meta`` is::

            {"stale": bool, "fetched_at": float | None,
             "circuit_open": bool, "empty": bool, "live": bool}

        - ``live`` is True ONLY when the data came from a fresh ``fetch_fn`` call
          this invocation (so callers can avoid re-stamping cached serves).
        - ``stale`` is True when a cached value was served past its TTL (circuit
          open) or when the circuit was open with no cache to serve.
        - On open-circuit-with-no-cache, ``data`` is ``None`` and ``meta`` is
          ``{"stale": True, "fetched_at": None, "circuit_open": True,
          "empty": True, "live": False}`` — distinguishable from a genuine
          empty-but-fresh result (which is ``([], {..., "empty": True,
          "stale": False})``).
        """
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
                    data = json.loads(row["data"])
                    if return_meta:
                        return data, {
                            "stale": False, "fetched_at": fetched_at,
                            "circuit_open": False,
                            "empty": not bool(data), "live": False,
                        }
                    return data

            # Circuit breaker: if API recently failed, skip live fetch
            if now < CacheService._circuit_open_until:
                if row is not None:
                    data = json.loads(row["data"])
                    if return_meta:
                        return data, {
                            "stale": True, "fetched_at": row["fetched_at"],
                            "circuit_open": True,
                            "empty": not bool(data), "live": False,
                        }
                    return data
                # No cache and circuit open.
                if return_meta:
                    return None, {
                        "stale": True, "fetched_at": None,
                        "circuit_open": True, "empty": True, "live": False,
                    }
                return []  # No cache and circuit open — return empty

            # Cache miss or stale -- fetch fresh data
            try:
                data = await fetch_fn()
            except Exception:
                # API failed — open circuit breaker for 60 seconds
                CacheService._circuit_open_until = now + 60
                if row is not None:
                    served = json.loads(row["data"])
                    if return_meta:
                        return served, {
                            "stale": True, "fetched_at": row["fetched_at"],
                            "circuit_open": True,
                            "empty": not bool(served), "live": False,
                        }
                    return served
                raise
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
            if return_meta:
                return data, {
                    "stale": False, "fetched_at": now, "circuit_open": False,
                    "empty": not bool(data), "live": True,
                }
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
