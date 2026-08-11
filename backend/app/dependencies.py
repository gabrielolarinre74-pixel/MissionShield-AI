"""
MissionShield AI — FastAPI dependency injectors.

Provides singleton instances of shared services via FastAPI Depends.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.services.cache import TTLCache
from app.services.space_weather import SpaceWeatherService


@lru_cache(maxsize=1)
def get_cache() -> TTLCache:
    """Return the application-wide TTL cache singleton."""
    return TTLCache(ttl_seconds=settings.CACHE_TTL_SECONDS)


def get_space_weather_service() -> SpaceWeatherService:
    """Return a SpaceWeatherService backed by the shared cache."""
    return SpaceWeatherService(cache=get_cache())


def get_watsonx_client():
    """Return the WatsonxClient singleton (lazy-initialized on first use)."""
    from app.ai.watsonx_client import get_watsonx_client as _get
    return _get()
