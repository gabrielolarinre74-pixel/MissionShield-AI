"""
MissionShield AI — health check route.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """
    Liveness probe.
    Returns service name and version only — no secret configuration values.
    """
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
