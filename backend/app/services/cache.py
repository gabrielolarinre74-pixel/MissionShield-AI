"""
MissionShield AI — in-memory async TTL cache.

Simple dict-based cache with asyncio.Lock for coroutine safety.
No external dependencies (no Redis, no database).

Freshness semantics:
  LIVE   — data retrieved from upstream in the current call.
  CACHED — valid cache entry, within TTL, served without a new upstream fetch.
  STALE  — expired cache entry being deliberately served because upstream failed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from app.config import settings
from app.models.space_weather import DataFreshness

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """One cached value with its store timestamp."""

    __slots__ = ("value", "stored_at")

    def __init__(self, value: T) -> None:
        self.value: T = value
        self.stored_at: datetime = datetime.now(timezone.utc)

    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.stored_at).total_seconds()

    def is_valid(self, ttl_seconds: int) -> bool:
        return self.age_seconds() < ttl_seconds


class TTLCache:
    """
    Async-safe in-memory TTL cache.

    Usage:
        cache = TTLCache()
        await cache.set("snapshot", my_snapshot)
        entry = await cache.get("snapshot")
        if entry is not None:
            ...
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = ttl_seconds if ttl_seconds is not None else settings.CACHE_TTL_SECONDS
        self._store: dict[str, CacheEntry[Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> CacheEntry[Any] | None:
        """Return the cache entry for key regardless of TTL, or None if absent."""
        async with self._lock:
            return self._store.get(key)

    async def get_valid(self, key: str) -> CacheEntry[Any] | None:
        """Return the cache entry only if it is within TTL, or None."""
        async with self._lock:
            entry = self._store.get(key)
            if entry and entry.is_valid(self._ttl):
                return entry
            return None

    async def set(self, key: str, value: Any) -> None:
        """Store a value under key, replacing any existing entry."""
        async with self._lock:
            self._store[key] = CacheEntry(value)

    async def invalidate(self, key: str) -> None:
        """Remove an entry from the cache."""
        async with self._lock:
            self._store.pop(key, None)

    def freshness_for(self, entry: CacheEntry[Any]) -> DataFreshness:
        """Return the DataFreshness label for a given cache entry."""
        if entry.is_valid(self._ttl):
            return DataFreshness.CACHED
        return DataFreshness.STALE
