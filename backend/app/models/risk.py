"""
MissionShield AI — risk domain models.

Placeholder structures for the risk engine (Phase 2).
Defined here so routes and services can reference the types.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models.mission import MissionProfile


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class RiskFactor(BaseModel):
    """One contributing factor to the overall mission risk score."""

    model_config = ConfigDict(frozen=True)

    # Human-readable label, e.g. "Kp Index", "Solar Wind Speed".
    label: str
    # Normalised sub-score (0.0 – 1.0).
    sub_score: float = Field(ge=0.0, le=1.0)
    # Weighted contribution to the total score (0.0 – 100.0).
    contribution: float = Field(ge=0.0, le=100.0)
    # Raw value string for display, e.g. "4.67", "550 km/s".
    raw_value: str | None = None


class MissionRiskReport(BaseModel):
    """
    Output of the risk engine for one mission profile at one point in time.

    DISCLAIMER: This is prototype decision-support intelligence.
    It is NOT an official NASA, NOAA, or government safety rating.
    """

    model_config = ConfigDict(frozen=True)

    mission_profile: MissionProfile
    # Overall risk score 0–100.
    risk_score: float = Field(ge=0.0, le=100.0)
    risk_level: RiskLevel
    # The single most critical contributing factor label.
    primary_risk_factor: str | None = None
    # All contributing factors with their weighted contributions.
    factors: list[RiskFactor] = Field(default_factory=list)
    # True when any SimulationOverrides were applied.
    is_simulated: bool = False
    # UTC timestamp of the snapshot this report was computed from.
    computed_at: str
    disclaimer: str = (
        "This is prototype decision-support intelligence. "
        "It is NOT an official NASA, NOAA, or government safety rating."
    )
