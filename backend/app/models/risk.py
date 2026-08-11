"""
MissionShield AI — risk domain models.

These models are the output of the deterministic risk engine.

DISCLAIMER: The 0–100 MissionShield risk score is a transparent prototype
heuristic. It is NOT an official NASA, NOAA, or government safety rating.
The score is computed from real NASA/NOAA observations using a documented
weight matrix, but the weights themselves are prototype design decisions.
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
    """
    One contributing hazard factor in the MissionShield risk report.

    Exposes enough structured data for a frontend to show the full
    breakdown without re-parsing strings.
    """

    model_config = ConfigDict(frozen=True)

    # Human-readable factor label, e.g. "Geomagnetic Disturbance".
    label: str

    # Normalised severity 0.0 – 1.0 for this factor (before weighting).
    normalized_severity: float = Field(ge=0.0, le=1.0)

    # Mission-specific weight for this factor (0.0 – 1.0, profile-dependent).
    # MissionShield prototype heuristic — not an official operational weight.
    mission_weight: float = Field(ge=0.0, le=1.0)

    # Weighted contribution to the 0–100 total score (= severity * weight * 100).
    weighted_contribution: float = Field(ge=0.0, le=100.0)

    # Raw observed value as a string, e.g. "4.67", "550 km/s", "M1.5".
    # None when this factor's data was unavailable.
    observed_value: str | None = None

    # Physical units of the observed value, e.g. "pfu", "nT".
    units: str | None = None

    # Data source attribution, e.g. "NOAA SWPC", "NASA DONKI".
    source: str | None = None

    # Short human-readable explanation of this factor's contribution.
    explanation: str

    # Official NOAA reference scale label if applicable, e.g. "G2", "S1", "R3".
    # None when no official NOAA scale applies (e.g. CME watch is a prototype heuristic).
    reference_scale: str | None = None

    # Whether this factor's data was actually available (False = missing/unavailable).
    data_available: bool = True

    # Backward-compat alias — kept for any existing callers.
    @property
    def sub_score(self) -> float:
        return self.normalized_severity

    @property
    def contribution(self) -> float:
        return self.weighted_contribution


class MissionRiskReport(BaseModel):
    """
    Output of the MissionShield risk engine for one mission profile.

    DISCLAIMER: This is prototype decision-support intelligence.
    It is NOT an official NASA, NOAA, or government safety rating.
    The 0–100 score is a transparent MissionShield prototype heuristic.
    """

    model_config = ConfigDict(frozen=True)

    mission_profile: MissionProfile

    # Overall risk score 0–100 (MissionShield prototype heuristic).
    risk_score: float = Field(ge=0.0, le=100.0)

    # Risk level band (MissionShield prototype — not a NOAA scale).
    risk_level: RiskLevel

    # The single most critical contributing factor label.
    primary_risk_factor: str | None = None

    # All four primary factors with their contributions.
    factors: list[RiskFactor] = Field(default_factory=list)

    # True when any SimulationOverrides were applied.
    is_simulated: bool = False

    # UTC ISO timestamp of the snapshot this report was computed from.
    computed_at: str

    # Fraction of intended weighted factor coverage that was available (0.0–1.0).
    # 1.0 = all four primary factors had data.
    data_completeness: float = Field(default=1.0, ge=0.0, le=1.0)

    # List of factor labels whose data was unavailable.
    missing_factors: list[str] = Field(default_factory=list)

    # "full" when completeness >= threshold; "degraded" otherwise.
    # MissionShield prototype confidence indicator.
    confidence: str = "full"

    # Mandatory prototype disclaimer — must be surfaced to users.
    disclaimer: str = (
        "MissionShield provides prototype decision-support intelligence and is not "
        "an official NASA, NOAA, or flight-safety rating."
    )
