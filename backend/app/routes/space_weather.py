"""
MissionShield AI — space-weather API routes.

All external API access happens through the SpaceWeatherService —
never directly inside route functions.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.dependencies import get_space_weather_service
from app.exceptions import DataSourceUnavailableError, PartialDataError
from app.models.space_weather import SpaceWeatherSnapshot
from app.services.anomaly import AnomalyFlag, detect_snapshot_anomalies
from app.services.space_weather import SpaceWeatherService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/space-weather")


@router.get("/snapshot", response_model=SpaceWeatherSnapshot)
async def get_snapshot(
    response: Response,
    svc: Annotated[SpaceWeatherService, Depends(get_space_weather_service)],
) -> SpaceWeatherSnapshot:
    """
    Return the current SpaceWeatherSnapshot.

    Freshness is indicated in the response body (live / cached / stale)
    and via the X-Data-Freshness response header.

    Source attribution is preserved in source_status.
    """
    try:
        snapshot = await svc.get_snapshot()
    except DataSourceUnavailableError as exc:
        logger.error("Space weather snapshot unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATA_SOURCE_UNAVAILABLE",
                "message": "Space-weather data sources are currently unavailable. Please try again shortly.",
                "source": exc.source,
            },
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error building snapshot: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": "An internal error occurred."},
        ) from exc

    # Surface freshness and source attribution in response headers.
    response.headers["X-Data-Freshness"] = snapshot.freshness.value
    response.headers["X-Data-Sources"] = "NASA DONKI, NOAA SWPC, NOAA GOES"
    return snapshot


@router.get("/events")
async def get_events(
    response: Response,
    svc: Annotated[SpaceWeatherService, Depends(get_space_weather_service)],
) -> dict:
    """
    Return recent space-weather events from NASA DONKI (last 7 days).

    Events are extracted from the current snapshot so they benefit from caching.
    """
    try:
        snapshot = await svc.get_snapshot()
    except DataSourceUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATA_SOURCE_UNAVAILABLE",
                "message": "Space-weather event data is currently unavailable.",
                "source": exc.source,
            },
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error fetching events: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": "An internal error occurred."},
        ) from exc

    response.headers["X-Data-Freshness"] = snapshot.freshness.value
    response.headers["X-Data-Sources"] = "NASA DONKI"

    return {
        "freshness": snapshot.freshness.value,
        "fetched_at": snapshot.fetched_at.isoformat(),
        "flares": [f.model_dump(mode="json") for f in snapshot.recent_flares],
        "cmes": [c.model_dump(mode="json") for c in snapshot.recent_cmes],
        "geomagnetic_storms": [g.model_dump(mode="json") for g in snapshot.recent_geomagnetic_storms],
        "sep_events": [s.model_dump(mode="json") for s in snapshot.recent_sep_events],
    }


@router.get("/anomalies", response_model=list[AnomalyFlag])
async def get_anomalies(
    response: Response,
    svc: Annotated[SpaceWeatherService, Depends(get_space_weather_service)],
) -> list[AnomalyFlag]:
    """
    Return statistical anomaly detection results for the current space-weather snapshot.

    Uses the robust z-score method on available time-series data.
    An empty list means either no anomalies were detected or insufficient
    time-series data is available (e.g. fresh cache or first fetch).

    Note: statistical anomaly flags are situational awareness — they are
    separate from the mission risk score and do not imply danger.
    """
    try:
        snapshot = await svc.get_snapshot()
    except DataSourceUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATA_SOURCE_UNAVAILABLE",
                "message": "Space-weather data unavailable.",
                "source": exc.source,
            },
        ) from exc
    except Exception as exc:
        logger.error("Anomaly endpoint error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": "An internal error occurred."},
        ) from exc

    response.headers["X-Data-Freshness"] = snapshot.freshness.value
    flags = detect_snapshot_anomalies(snapshot)
    return flags
