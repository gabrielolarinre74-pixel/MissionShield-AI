"""
MissionShield AI — mission domain models.

Defines the four supported mission profiles and the simulation override schema.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MissionProfile(str, Enum):
    """The four mission types supported by the risk engine."""

    ROCKET_LAUNCH = "ROCKET_LAUNCH"
    LEO_SATELLITE = "LEO_SATELLITE"
    ASTRONAUT_EVA = "ASTRONAUT_EVA"
    LUNAR_MISSION = "LUNAR_MISSION"


class SimulationOverrides(BaseModel):
    """
    What-If mode parameter overrides.

    Any field left as None means "use the live value".
    When any field is set, is_simulated must be treated as True by the risk engine.
    """

    model_config = ConfigDict(frozen=True)

    # Override Kp index (0.0 – 9.0 scale).
    kp_index: float | None = Field(default=None, ge=0.0, le=9.0)
    # Override solar wind speed in km/s.
    solar_wind_speed_km_s: float | None = Field(default=None, ge=200.0, le=2000.0)
    # Override IMF Bz in nT (negative = southward = geoeffective).
    bz_gsm_nt: float | None = Field(default=None, ge=-100.0, le=50.0)
    # Override: pretend an Earth-directed CME is active (True) or not present (False).
    cme_earth_directed: bool | None = None
    # Override: pretend a recent SEP event occurred (True) or not (False).
    sep_event_active: bool | None = None
