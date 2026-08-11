"""
MissionShield AI — mission risk API routes.

POST /api/mission/risk
  Input:  { profile: MissionProfile, simulation_overrides?: SimulationOverrides }
  Output: MissionRiskReport

GET /api/space-weather/anomalies
  Output: AnomalyResult (list of AnomalyFlag + snapshot metadata)

Both endpoints use the SpaceWeatherService via Depends — never make direct
client calls inside route functions.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.dependencies import get_space_weather_service
from app.exceptions import DataSourceUnavailableError
from app.models.mission import MissionProfile, SimulationOverrides
from app.models.risk import MissionRiskReport
from app.services.anomaly import AnomalyFlag, detect_snapshot_anomalies
from app.services.risk_engine import compute_risk
from app.services.space_weather import SpaceWeatherService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mission")


class RiskRequest(BaseModel):
    """Request body for POST /api/mission/risk."""

    model_config = ConfigDict(frozen=True)

    profile: MissionProfile
    simulation_overrides: SimulationOverrides | None = None


@router.post("/risk", response_model=MissionRiskReport)
async def get_mission_risk(
    request: RiskRequest,
    svc: Annotated[SpaceWeatherService, Depends(get_space_weather_service)],
) -> MissionRiskReport:
    """
    Compute a deterministic MissionRiskReport for the given mission profile.

    The backend fetches the current space-weather snapshot (using the TTL cache),
    runs the risk engine, and returns the structured report.

    Simulation overrides, if provided, replace specific live values for scoring
    only.  The underlying snapshot is never modified.  is_simulated=True is set
    on the returned report when any override is active.
    """
    try:
        snapshot = await svc.get_snapshot()
    except DataSourceUnavailableError as exc:
        logger.error("Risk endpoint: snapshot unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATA_SOURCE_UNAVAILABLE",
                "message": "Space-weather data is currently unavailable. Risk cannot be computed.",
                "source": exc.source,
            },
        ) from exc
    except Exception as exc:
        logger.error("Risk endpoint: unexpected error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": "An internal error occurred."},
        ) from exc

    try:
        report = compute_risk(
            snapshot=snapshot,
            profile=request.profile,
            overrides=request.simulation_overrides,
        )
    except Exception as exc:
        logger.error("Risk engine error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "RISK_ENGINE_ERROR", "message": "Risk computation failed."},
        ) from exc

    return report
