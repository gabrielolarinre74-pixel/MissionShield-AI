"""
MissionShield AI — space-weather domain models.

All models use UTC-aware datetimes.
Missing upstream values are represented as None, never silently coerced to zero.
Units are explicit in field names or descriptions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DataSource(str, Enum):
    NASA_DONKI = "NASA DONKI"
    NOAA_SWPC = "NOAA SWPC"
    NOAA_GOES = "NOAA GOES"


class DataFreshness(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"


# ---------------------------------------------------------------------------
# NOAA SWPC — point measurements
# ---------------------------------------------------------------------------


class KpReading(BaseModel):
    """One 1-minute Kp reading from NOAA SWPC planetary_k_index_1m.json."""

    model_config = ConfigDict(frozen=True)

    # Raw timestamp string from feed; naive UTC (no Z suffix in source).
    time_tag: datetime
    # Integer Kp (0–9) bucket.
    kp_index: int
    # Fractional estimated Kp (0.00–9.00); preferred for scoring.
    estimated_kp: float
    # String code, e.g. "0P", "3+".
    kp_text: str | None = None
    source: DataSource = DataSource.NOAA_SWPC


class SolarWindReading(BaseModel):
    """One real-time solar-wind measurement from NOAA SWPC rtsw_wind_1m.json."""

    model_config = ConfigDict(frozen=True)

    time_tag: datetime
    # Upstream instrument source tag, e.g. "ACE", "IMAP".
    instrument_source: str | None = None
    # True when this row is the designated active/primary source.
    active: bool = False
    # Proton bulk speed in km/s. Null if measurement unavailable.
    proton_speed_km_s: float | None = None
    # Proton density in cm⁻³. Null if unavailable.
    proton_density_cm3: float | None = None
    # Proton temperature in K. Null if unavailable.
    proton_temperature_k: float | None = None
    # Overall quality flag from upstream (0 = good).
    overall_quality: int | None = None
    source: DataSource = DataSource.NOAA_SWPC


class MagneticFieldReading(BaseModel):
    """One real-time IMF measurement from NOAA SWPC rtsw_mag_1m.json."""

    model_config = ConfigDict(frozen=True)

    time_tag: datetime
    instrument_source: str | None = None
    active: bool = False
    # Total field magnitude in nT.
    bt_nt: float | None = None
    # Bz component in GSM coordinates (nT). Negative = southward = geoeffective.
    bz_gsm_nt: float | None = None
    # By component in GSM coordinates (nT).
    by_gsm_nt: float | None = None
    # Bx component in GSM coordinates (nT).
    bx_gsm_nt: float | None = None
    overall_quality: int | None = None
    source: DataSource = DataSource.NOAA_SWPC


class ProtonFluxReading(BaseModel):
    """
    One integral-proton flux measurement from NOAA GOES integral-protons-6-hour.json.

    The feed contains multiple energy channels per timestamp.
    The >=10 MeV channel is the standard space-weather alert threshold.
    Units: pfu (particle flux units = particles cm⁻² s⁻¹ sr⁻¹).
    """

    model_config = ConfigDict(frozen=True)

    time_tag: datetime
    # GOES satellite number, e.g. 16, 18.
    satellite: int | None = None
    # Integral flux value in pfu.
    flux_pfu: float | None = None
    # Energy channel string from upstream, e.g. ">=10 MeV".
    energy_channel: str
    source: DataSource = DataSource.NOAA_GOES


# ---------------------------------------------------------------------------
# NASA DONKI — event records
# ---------------------------------------------------------------------------


class LinkedEvent(BaseModel):
    """A cross-reference to another DONKI event by activity ID."""

    model_config = ConfigDict(frozen=True)

    activity_id: str


class CMEAnalysis(BaseModel):
    """
    WSA-ENLIL model output attached to a CME event.

    Only fields actually returned by the upstream API are modelled.
    Do NOT add fields not present in the real DONKI response.
    """

    model_config = ConfigDict(frozen=True)

    is_most_accurate: bool = False
    # Propagation time to 21.5 solar radii (Z).
    time_21_5: datetime | None = None
    latitude_deg: float | None = None
    longitude_deg: float | None = None
    half_angle_deg: float | None = None
    speed_km_s: float | None = None
    # Type code, e.g. "C" (cone), "S" (Flux Rope).
    cme_type: str | None = None
    # WSA-ENLIL model runs attached to this analysis.
    enlil_runs: list[EnlilRun] = Field(default_factory=list)
    link: str | None = None


class EnlilRun(BaseModel):
    """
    One WSA-ENLIL model run result for a CME.

    isEarthGB = True means the model predicts an Earth-directed glancing
    or direct hit.  estimatedShockArrivalTime is the model's best estimate;
    it is NOT a probability — do not label it as such.
    """

    model_config = ConfigDict(frozen=True)

    model_completion_time: datetime | None = None
    # Estimated shock arrival time at Earth. Null if not Earth-directed.
    estimated_shock_arrival_time: datetime | None = None
    estimated_duration_hours: float | None = None
    # Modelled Kp at 18°, 90°, 135°, 180° from Sun-Earth line.
    kp_18: int | None = None
    kp_90: int | None = None
    kp_135: int | None = None
    kp_180: int | None = None
    # True if model predicts Earth is within the CME impact zone.
    is_earth_directed: bool = False
    is_earth_minor_impact: bool = False
    link: str | None = None


class SolarFlareEvent(BaseModel):
    """Solar flare event from NASA DONKI FLR endpoint."""

    model_config = ConfigDict(frozen=True)

    flr_id: str
    begin_time: datetime
    peak_time: datetime | None = None
    end_time: datetime | None = None
    # GOES class string, e.g. "C2.4", "M1.5", "X3.2".
    class_type: str | None = None
    # Heliographic source location, e.g. "N14W102".
    source_location: str | None = None
    active_region_num: int | None = None
    linked_events: list[LinkedEvent] = Field(default_factory=list)
    link: str | None = None
    source: DataSource = DataSource.NASA_DONKI


class CMEEvent(BaseModel):
    """Coronal mass ejection event from NASA DONKI CME endpoint."""

    model_config = ConfigDict(frozen=True)

    activity_id: str
    start_time: datetime
    source_location: str | None = None
    active_region_num: int | None = None
    note: str | None = None
    # CME analyses (may include WSA-ENLIL model runs).
    analyses: list[CMEAnalysis] = Field(default_factory=list)
    linked_events: list[LinkedEvent] = Field(default_factory=list)
    link: str | None = None
    source: DataSource = DataSource.NASA_DONKI


class GeomagneticStormEvent(BaseModel):
    """Geomagnetic storm event from NASA DONKI GST endpoint."""

    model_config = ConfigDict(frozen=True)

    gst_id: str
    start_time: datetime
    # Observed Kp readings recorded during this storm.
    observed_kp_readings: list[ObservedKpPoint] = Field(default_factory=list)
    linked_events: list[LinkedEvent] = Field(default_factory=list)
    link: str | None = None
    source: DataSource = DataSource.NASA_DONKI


class ObservedKpPoint(BaseModel):
    """One Kp observation within a GST event record."""

    model_config = ConfigDict(frozen=True)

    observed_time: datetime
    kp_index: float
    kp_source: str | None = None


class SEPEvent(BaseModel):
    """
    Solar Energetic Particle event from NASA DONKI SEP endpoint.

    IMPORTANT: This is an event record, not a numerical flux measurement.
    The instruments field names the detector/model that triggered the event.
    For numerical proton flux use ProtonFluxReading from NOAA GOES.
    """

    model_config = ConfigDict(frozen=True)

    sep_id: str
    event_time: datetime
    # Instrument(s) that detected/modelled this SEP.
    instruments: list[str] = Field(default_factory=list)
    linked_events: list[LinkedEvent] = Field(default_factory=list)
    link: str | None = None
    source: DataSource = DataSource.NASA_DONKI


# ---------------------------------------------------------------------------
# Source status — tracks per-source fetch health
# ---------------------------------------------------------------------------


class SourceStatus(BaseModel):
    """Health status for one upstream data source within a snapshot."""

    model_config = ConfigDict(frozen=True)

    source: DataSource
    available: bool
    # Human-readable error description (no credentials, no stack traces).
    error: str | None = None


# ---------------------------------------------------------------------------
# Aggregate snapshot
# ---------------------------------------------------------------------------


class SpaceWeatherSnapshot(BaseModel):
    """
    Normalized, combined view of current space-weather conditions.

    Provenance metadata allows the frontend to truthfully display
    data freshness and source attribution.
    """

    model_config = ConfigDict(frozen=True)

    # When this snapshot was assembled (UTC).
    fetched_at: datetime
    freshness: DataFreshness

    # When upstream data was last successfully retrieved (may differ from fetched_at when stale).
    last_successful_fetch: datetime | None = None

    # Per-source availability status.
    source_status: list[SourceStatus] = Field(default_factory=list)

    # --- NOAA SWPC real-time measurements ---
    # Most-recent Kp reading (from the active primary source row).
    latest_kp: KpReading | None = None
    # Most-recent solar wind reading from the active primary source.
    latest_solar_wind: SolarWindReading | None = None
    # Most-recent magnetic field reading from the active primary source.
    latest_mag_field: MagneticFieldReading | None = None
    # Most-recent >=10 MeV proton flux from NOAA GOES primary.
    latest_proton_flux_10mev: ProtonFluxReading | None = None

    # --- NASA DONKI events (last 7 days by default) ---
    recent_flares: list[SolarFlareEvent] = Field(default_factory=list)
    recent_cmes: list[CMEEvent] = Field(default_factory=list)
    recent_geomagnetic_storms: list[GeomagneticStormEvent] = Field(default_factory=list)
    recent_sep_events: list[SEPEvent] = Field(default_factory=list)
