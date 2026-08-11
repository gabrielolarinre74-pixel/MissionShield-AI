"""
MissionShield AI — lightweight statistical anomaly detection.

Detects statistically unusual readings in space-weather time series using a
robust z-score (median / MAD) approach.

IMPORTANT DISTINCTION
---------------------
"Statistically unusual" does NOT automatically mean "dangerous."
Anomaly flags are situational-awareness signals, separate from the mission
risk score.  They are NOT added to the risk score numerically.

METHOD: Robust Z-Score (median / MAD)
--------------------------------------
  z = 0.6745 * (x - median) / MAD

where MAD = median(|x_i - median(x)|).
The constant 0.6745 makes the robust z-score comparable to a conventional
z-score when data are approximately Gaussian.

MAD = 0 handling: when MAD is zero (constant series), fall back to
conventional z-score using sample standard deviation.  If both are zero,
mark the latest point as not anomalous (constant readings are by definition
not outliers).

THRESHOLD: abs(z) >= 3.0 is flagged as anomalous.

MINIMUM SAMPLE COUNT: At least MIN_SAMPLES readings are required before
anomaly detection is run.  With too few samples the statistics are unreliable.

No scikit-learn or machine learning is used — the method is fully
explainable from first principles.
"""

from __future__ import annotations

import logging
import math
import statistics
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# Minimum number of readings required for anomaly detection.
MIN_SAMPLES = 5

# Anomaly threshold: |z| >= this value is flagged.
ANOMALY_THRESHOLD = 3.0

# Scaling constant for robust z-score (makes it comparable to conventional z-score).
_MAD_SCALE = 0.6745


class AnomalyFlag(BaseModel):
    """
    One anomaly detection result for a specific parameter at a specific time.

    The is_anomalous field is True only when abs(z_score) >= ANOMALY_THRESHOLD
    AND there were at least MIN_SAMPLES readings to compute statistics from.
    """

    model_config = ConfigDict(frozen=True)

    # Parameter being evaluated, e.g. "estimated_kp", "proton_speed_km_s".
    parameter: str

    # ISO timestamp of the measurement being evaluated.
    timestamp: str

    # The specific value being checked.
    current_value: float

    # Units string, e.g. "Kp units", "km/s", "pfu".
    unit: str

    # Median of the baseline series.
    baseline_median: float

    # MAD of the baseline series (or std dev if MAD=0).
    baseline_dispersion: float

    # Type of dispersion: "MAD" or "std_dev".
    dispersion_type: str

    # Robust z-score of current_value relative to the baseline.
    z_score: float

    # Threshold used (abs(z) >= this value → anomalous).
    threshold: float

    # Direction of anomaly: "high", "low", or "none".
    direction: str

    # Number of samples used in baseline statistics.
    sample_count: int

    # True when abs(z_score) >= threshold AND sample_count >= MIN_SAMPLES.
    is_anomalous: bool

    # Data source attribution.
    source: str

    # Human-readable explanation of the anomaly finding.
    explanation: str


def _compute_robust_z(value: float, series: list[float]) -> tuple[float, float, float, str]:
    """
    Compute a robust z-score for `value` relative to `series`.

    Returns (z_score, median, dispersion, dispersion_type).

    When MAD = 0 (constant or near-constant baseline):
      - If the new value equals the baseline constant: z = 0 (not anomalous).
      - If the new value differs from the constant baseline: the value is
        infinitely unusual.  We cap z at ±10 (flagging it as anomalous) rather
        than returning NaN/inf.  This is conservative and explainable.
    """
    med = statistics.median(series)
    deviations = [abs(x - med) for x in series]
    mad = statistics.median(deviations)

    if mad > 1e-10:
        z = _MAD_SCALE * (value - med) / mad
        return z, med, mad, "MAD"

    # MAD is zero — try conventional std dev.
    if len(series) >= 2:
        std = statistics.stdev(series)
    else:
        std = 0.0

    if std > 1e-10:
        z = (value - med) / std
        return z, med, std, "std_dev"

    # Both MAD and std are zero (constant series).
    # If the new value differs from the constant, cap z at ±10.
    diff = value - med
    if abs(diff) > 1e-10:
        z = 10.0 if diff > 0 else -10.0
    else:
        z = 0.0
    return z, med, 0.0, "std_dev"


def detect_kp_anomalies(
    readings: list,
    *,
    source: str = "NOAA SWPC",
) -> list[AnomalyFlag]:
    """
    Detect anomalies in a list of KpReading objects.

    Evaluates the most recent reading against the rest of the series as baseline.
    Returns a list containing one AnomalyFlag for the latest reading
    (or an empty list if insufficient data).

    Parameters
    ----------
    readings : list[KpReading]
        Time-ordered list of KpReading objects (most recent last).
    source : str
        Attribution string for the result.
    """
    if not readings or len(readings) < MIN_SAMPLES:
        logger.debug(
            "Kp anomaly detection skipped: only %d readings (need %d)",
            len(readings),
            MIN_SAMPLES,
        )
        return []

    values = [r.estimated_kp for r in readings if r.estimated_kp is not None]
    if len(values) < MIN_SAMPLES:
        return []

    latest = readings[-1]
    if latest.estimated_kp is None:
        return []

    current = latest.estimated_kp
    baseline = values[:-1]  # All readings except the latest.

    z, med, disp, disp_type = _compute_robust_z(current, baseline)
    is_anomalous = abs(z) >= ANOMALY_THRESHOLD
    direction = "high" if z > 0 else ("low" if z < 0 else "none")

    if is_anomalous:
        explanation = (
            f"Kp index {current:.2f} is statistically unusual relative to recent baseline "
            f"(median={med:.2f}, {disp_type}={disp:.4f}, z={z:.2f}). "
            f"Direction: {direction}. "
            "Note: statistical anomaly does not imply danger — see risk score for mission impact."
        )
    else:
        explanation = (
            f"Kp index {current:.2f} is within normal statistical range "
            f"(median={med:.2f}, z={z:.2f})."
        )

    return [
        AnomalyFlag(
            parameter="estimated_kp",
            timestamp=latest.time_tag.isoformat(),
            current_value=current,
            unit="Kp units",
            baseline_median=round(med, 4),
            baseline_dispersion=round(disp, 4),
            dispersion_type=disp_type,
            z_score=round(z, 4),
            threshold=ANOMALY_THRESHOLD,
            direction=direction,
            sample_count=len(baseline),
            is_anomalous=is_anomalous,
            source=source,
            explanation=explanation,
        )
    ]


def detect_solar_wind_anomalies(
    readings: list,
    *,
    source: str = "NOAA SWPC",
) -> list[AnomalyFlag]:
    """
    Detect anomalies in solar wind speed from a list of SolarWindReading objects.

    Focuses on proton_speed_km_s.  Returns one AnomalyFlag for the latest
    active reading, or an empty list if insufficient data.
    """
    # Filter to valid speed readings from the active source.
    valid = [
        r for r in readings
        if r.proton_speed_km_s is not None
    ]
    if len(valid) < MIN_SAMPLES:
        return []

    values = [r.proton_speed_km_s for r in valid]
    latest = valid[-1]
    current = latest.proton_speed_km_s

    baseline = values[:-1]
    z, med, disp, disp_type = _compute_robust_z(current, baseline)
    is_anomalous = abs(z) >= ANOMALY_THRESHOLD
    direction = "high" if z > 0 else ("low" if z < 0 else "none")

    if is_anomalous:
        explanation = (
            f"Solar wind speed {current:.1f} km/s is statistically unusual "
            f"(median={med:.1f} km/s, {disp_type}={disp:.2f}, z={z:.2f}). "
            f"Direction: {direction}. "
            "Note: statistical anomaly does not imply danger — see risk score for mission impact."
        )
    else:
        explanation = (
            f"Solar wind speed {current:.1f} km/s is within normal statistical range "
            f"(median={med:.1f} km/s, z={z:.2f})."
        )

    return [
        AnomalyFlag(
            parameter="proton_speed_km_s",
            timestamp=latest.time_tag.isoformat(),
            current_value=current,
            unit="km/s",
            baseline_median=round(med, 2),
            baseline_dispersion=round(disp, 2),
            dispersion_type=disp_type,
            z_score=round(z, 4),
            threshold=ANOMALY_THRESHOLD,
            direction=direction,
            sample_count=len(baseline),
            is_anomalous=is_anomalous,
            source=source,
            explanation=explanation,
        )
    ]


def detect_mag_field_anomalies(
    readings: list,
    *,
    source: str = "NOAA SWPC",
) -> list[AnomalyFlag]:
    """
    Detect anomalies in IMF Bz from a list of MagneticFieldReading objects.

    bz_gsm_nt: negative values are southward and geoeffective.
    Returns one AnomalyFlag for the latest reading.
    """
    valid = [r for r in readings if r.bz_gsm_nt is not None]
    if len(valid) < MIN_SAMPLES:
        return []

    values = [r.bz_gsm_nt for r in valid]
    latest = valid[-1]
    current = latest.bz_gsm_nt

    baseline = values[:-1]
    z, med, disp, disp_type = _compute_robust_z(current, baseline)
    is_anomalous = abs(z) >= ANOMALY_THRESHOLD
    direction = "high" if z > 0 else ("low" if z < 0 else "none")

    if is_anomalous:
        explanation = (
            f"IMF Bz {current:.2f} nT is statistically unusual "
            f"(median={med:.2f} nT, {disp_type}={disp:.4f}, z={z:.2f}). "
            f"Direction: {direction}. "
            "Sustained southward Bz (negative) enhances geomagnetic coupling. "
            "Note: statistical anomaly does not imply danger."
        )
    else:
        explanation = (
            f"IMF Bz {current:.2f} nT is within normal statistical range "
            f"(median={med:.2f} nT, z={z:.2f})."
        )

    return [
        AnomalyFlag(
            parameter="bz_gsm_nt",
            timestamp=latest.time_tag.isoformat(),
            current_value=current,
            unit="nT",
            baseline_median=round(med, 4),
            baseline_dispersion=round(disp, 4),
            dispersion_type=disp_type,
            z_score=round(z, 4),
            threshold=ANOMALY_THRESHOLD,
            direction=direction,
            sample_count=len(baseline),
            is_anomalous=is_anomalous,
            source=source,
            explanation=explanation,
        )
    ]


def detect_proton_flux_anomalies(
    readings: list,
    *,
    source: str = "NOAA GOES",
) -> list[AnomalyFlag]:
    """
    Detect anomalies in >=10 MeV proton flux from a list of ProtonFluxReading objects.

    Uses log10-transformed flux values for the z-score calculation because
    proton flux spans many orders of magnitude and is log-normally distributed.
    """
    valid = [
        r for r in readings
        if r.flux_pfu is not None and r.flux_pfu > 0 and r.energy_channel == ">=10 MeV"
    ]
    if len(valid) < MIN_SAMPLES:
        return []

    # Log-transform for statistical stability.
    log_values = [math.log10(r.flux_pfu) for r in valid]
    latest = valid[-1]
    current = latest.flux_pfu
    current_log = math.log10(current)

    baseline = log_values[:-1]
    z, med_log, disp, disp_type = _compute_robust_z(current_log, baseline)
    is_anomalous = abs(z) >= ANOMALY_THRESHOLD
    direction = "high" if z > 0 else ("low" if z < 0 else "none")

    med_linear = 10 ** med_log

    if is_anomalous:
        explanation = (
            f">=10 MeV proton flux {current:.3f} pfu is statistically unusual "
            f"(log10 analysis — baseline median ~{med_linear:.3f} pfu, z={z:.2f}). "
            f"Direction: {direction}. "
            "Note: statistical anomaly does not imply danger — see radiation risk factor."
        )
    else:
        explanation = (
            f">=10 MeV proton flux {current:.3f} pfu is within normal statistical range "
            f"(log10 analysis — baseline median ~{med_linear:.3f} pfu, z={z:.2f})."
        )

    return [
        AnomalyFlag(
            parameter="proton_flux_10mev_pfu",
            timestamp=latest.time_tag.isoformat(),
            current_value=current,
            unit="pfu",
            baseline_median=round(med_linear, 6),
            baseline_dispersion=round(disp, 6),
            dispersion_type=f"log10_{disp_type}",
            z_score=round(z, 4),
            threshold=ANOMALY_THRESHOLD,
            direction=direction,
            sample_count=len(baseline),
            is_anomalous=is_anomalous,
            source=source,
            explanation=explanation,
        )
    ]


def detect_snapshot_anomalies(snapshot: "SpaceWeatherSnapshot") -> list[AnomalyFlag]:
    """
    Run all anomaly detectors against available data in a SpaceWeatherSnapshot.

    Uses the recent_kp_series, recent_solar_wind_series, etc. if present on
    the snapshot.  Falls back to empty lists when the snapshot only carries
    the latest single point (Phase 1 compatibility).

    Returns a list of AnomalyFlag objects (may be empty if insufficient data).
    """
    from app.models.space_weather import SpaceWeatherSnapshot  # local import to avoid circular

    flags: list[AnomalyFlag] = []

    # Kp anomaly — use recent_kp_series if available, else no-op.
    kp_series = getattr(snapshot, "recent_kp_series", [])
    if kp_series:
        flags.extend(detect_kp_anomalies(kp_series))

    # Solar wind speed anomaly.
    wind_series = getattr(snapshot, "recent_solar_wind_series", [])
    if wind_series:
        flags.extend(detect_solar_wind_anomalies(wind_series))

    # IMF Bz anomaly.
    mag_series = getattr(snapshot, "recent_mag_field_series", [])
    if mag_series:
        flags.extend(detect_mag_field_anomalies(mag_series))

    # Proton flux anomaly.
    proton_series = getattr(snapshot, "recent_proton_flux_series", [])
    if proton_series:
        flags.extend(detect_proton_flux_anomalies(proton_series))

    return flags
