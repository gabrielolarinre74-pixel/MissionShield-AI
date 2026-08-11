"""
MissionShield AI — backend configuration.

Reads environment variables via pydantic-settings.
The repository-root .env is loaded automatically when running locally.
Never print or expose actual secret values.
"""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Walk up from this file's location to find the repo-root .env.
# backend/app/config.py  ->  backend/app  ->  backend  ->  repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # IBM watsonx.ai (required for AI features — not needed for Phase 1 data layer)
    WATSONX_APIKEY: str = ""
    WATSONX_URL: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_MODEL_ID: str = ""

    # NASA DONKI API key.
    # Defaults to DEMO_KEY which is rate-limited — suitable for local development only.
    # Use a personal key in production: https://api.nasa.gov/
    NASA_API_KEY: str = "DEMO_KEY"

    # CORS — the frontend origin the backend will accept requests from.
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Cache TTL in seconds.
    CACHE_TTL_SECONDS: int = 300

    # External API request timeout in seconds.
    EXTERNAL_API_TIMEOUT_SECONDS: int = 10

    # Application metadata
    APP_VERSION: str = "0.1.0"
    APP_NAME: str = "MissionShield API"


# Module-level singleton — import `settings` everywhere.
settings = Settings()
