"""
MissionShield AI — deterministic mission risk engine.

This module converts a SpaceWeatherSnapshot into a MissionRiskReport for a
given MissionProfile.  It is a pure function: no I/O, no randomness, no LLM.

ARCHITECTURE
------------
Four primary hazard factors are scored independently then combined with
mission-specific weights:

  1. GEO   — Geomagnetic disturbance   (NOAA Kp / G-scale)
  2. RAD   — Solar radiation            (NOAA GOES >=10 MeV proton flux / S-scale)
  3. FLARE — Solar flare / radio env    (NASA DONKI FLR / NOAA R-scale reference)
  4. CME   — Earth-directed CME watch   (MissionShield prototype heuristic)

NOAA SCALE REFERENCES (official anchor points used here)
---------------------------------------------------------
G1=Kp5, G2=Kp6, G3=Kp7, G4=Kp8, G5=Kp9
S1=10 pfu, S2=100, S3=1,000, S4=10,000, S5=100,000
R1=M1, R2=M5, R3=X1, R4=X10, R5=X20

DOUBLE-COUNTING POLICY
-----------------------
DONKI SEP events and DONKI GST records are used only as explanatory context.
The numerical hazard score for radiation comes solely from NOAA GOES proton flux.
The numerical score for geomagnetic disturbance comes solely from NOAA Kp.
This prevents double-counting correlated observations from different sources
that describe the same physical phenomenon.

MISSING DATA POLICY
-------------------
Unavailable factor data is NOT treated as zero risk.
Weights are renormalized among available factors.
A data_completeness fraction and confidence indicator are exposed.
If coverage < MIN_COMPLETENESS_FOR_CONFIDENCE the report is marked "degraded".

SIMULATION
----------
SimulationOverrides replace specific live values before scoring.
The original snapshot is NEVER mutated — a derived scoring-only view is used.
is_simulated=True is set on the returned report.
Simulated values are never described as NASA/NOAA observations.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from app.models.mission import MissionProfile, SimulationOverrides
from app.models.risk import MissionRiskReport, RiskFactor, RiskLevel
from app.models.space_weather import CMEEvent, SolarFlareEvent, SpaceWeatherSnapshot
from app.services.risk_policy import (
    CME_ARRIVAL_SEVERITY,
    FLARE_RECENCY_HOURS_FULL,
    FLARE_RECENCY_HOURS_ZERO,
    MIN_COMPLETENESS_FOR_CONFIDENCE,
    NOAA_G_THRESHOLDS,
    NOAA_R_THRESHOLDS,
    NOAA_S_THRESHOLDS,
    PROFILE_WEIGHTS,
    RISK_LEVEL_BANDS,
)

logger = logging.getLogger(__name__)

# Factor index constants — match ordering in PROFILE_WEIGHTS lists.
_IDX_GEO = 0
_IDX_RAD = 1
_IDX_FLARE = 2
_IDX_CME = 3


# ---------------------------------------------------------------------------
# Factor-severity functions.
# Each returns (severity: float [0..1], observed_value: str|None,
#               units: str|None, reference_scale: str|None, explanation: str)
# ---------------------------------------------------------------------------

def _kp_to_noaa_g(kp: float) -> str | None:
    """Return the NOAA G-scale label for a given Kp value, or None if below G1."""
    # Iterate from G5 down so we pick the correct highest level.
    for level in ("G5", "G4", "G3", "G2", "G1"):
        if kp >= NOAA_G_THRESHOLDS[level]:
            return level
    return None  # Below G1 threshold — not an official storm


def _geomagnetic_severity(
    kp: float,
) -> tuple[float, str, str | None, str, str]:
    """
    Compute geomagnetic disturbance severity from Kp index.

    Uses the official NOAA G-scale reference thresholds as severity anchors.
    The severity curve is piecewise linear between the G-scale Kp thresholds.

    Returns: (severity, observed_value, units, reference_scale, explanation)
    """
    g_label = _kp_to_noaa_g(kp)

    if kp >= NOAA_G_THRESHOLDS["G5"]:  # Kp >= 9
        severity = 1.0
        explanation = (
            f"Extreme geomagnetic storm (NOAA G5 reference level, Kp={kp:.2f}). "
            "Widespread infrastructure effects possible."
        )
    elif kp >= NOAA_G_THRESHOLDS["G4"]:  # Kp 8–8.99
        severity = 0.80 + 0.20 * (kp - 8.0)
        explanation = (
            f"Severe geomagnetic storm (NOAA G4 reference level, Kp={kp:.2f}). "
            "Significant satellite navigation and HF communication impacts."
        )
    elif kp >= NOAA_G_THRESHOLDS["G3"]:  # Kp 7–7.99
        severity = 0.60 + 0.20 * (kp - 7.0)
        explanation = (
            f"Strong geomagnetic storm (NOAA G3 reference level, Kp={kp:.2f}). "
            "Satellite orientation irregularities; HF radio intermittent."
        )
    elif kp >= NOAA_G_THRESHOLDS["G2"]:  # Kp 6–6.99
        severity = 0.40 + 0.20 * (kp - 6.0)
        explanation = (
            f"Moderate geomagnetic storm (NOAA G2 reference level, Kp={kp:.2f}). "
            "Some satellite drag increase; power systems may experience fluctuations."
        )
    elif kp >= NOAA_G_THRESHOLDS["G1"]:  # Kp 5–5.99
        severity = 0.20 + 0.20 * (kp - 5.0)
        explanation = (
            f"Minor geomagnetic storm (NOAA G1 reference level, Kp={kp:.2f}). "
            "Weak power grid fluctuations; minor HF radio effects."
        )
    else:  # Kp < 5 — below G1; not an official storm
        # Scale linearly 0→0.20 for Kp 0→5.
        severity = 0.20 * (kp / 5.0)
        explanation = (
            f"Quiet to unsettled geomagnetic conditions (Kp={kp:.2f}, below NOAA G1 threshold). "
            "No significant storm-level effects expected."
        )

    severity = max(0.0, min(1.0, severity))
    return severity, f"{kp:.2f}", None, g_label, explanation


def _s_scale_from_flux(flux_pfu: float) -> str | None:
    """Return NOAA S-scale label for a proton flux value, or None if below S1."""
    for level in ("S5", "S4", "S3", "S2", "S1"):
        if flux_pfu >= NOAA_S_THRESHOLDS[level]:
            return level
    return None


def _radiation_severity(
    flux_pfu: float,
) -> tuple[float, str, str | None, str, str]:
    """
    Compute solar radiation severity from NOAA GOES >=10 MeV proton flux.

    Uses official NOAA S-scale thresholds (pfu) as severity anchors.
    The severity curve is log-linear between scale levels.

    Returns: (severity, observed_value, units, reference_scale, explanation)
    """
    s_label = _s_scale_from_flux(flux_pfu)

    # Safe log for scaling — handle zero/negative flux gracefully.
    if flux_pfu <= 0:
        severity = 0.0
        explanation = (
            f"Proton flux below detection threshold ({flux_pfu:.3f} pfu). "
            "No solar radiation storm activity."
        )
        return severity, f"{flux_pfu:.3f}", "pfu", None, explanation

    # Piecewise linear severity anchored at official NOAA S-scale boundaries.
    # Anchors: S1=0.20, S2=0.40, S3=0.60, S4=0.80, S5=1.00
    # Below S1: linear 0 → 0.20 on log10 scale from 0.1 pfu → 10 pfu.
    log_flux = math.log10(flux_pfu)
    log_s1 = math.log10(NOAA_S_THRESHOLDS["S1"])   # log10(10) = 1.0
    log_s2 = math.log10(NOAA_S_THRESHOLDS["S2"])   # log10(100) = 2.0
    log_s3 = math.log10(NOAA_S_THRESHOLDS["S3"])   # log10(1000) = 3.0
    log_s4 = math.log10(NOAA_S_THRESHOLDS["S4"])   # log10(10000) = 4.0
    log_s5 = math.log10(NOAA_S_THRESHOLDS["S5"])   # log10(100000) = 5.0

    if log_flux < log_s1:
        # Below S1: scale from 0 at log10(0.1)=-1 to 0.20 at S1.
        # Use 0 at any sub-threshold value.
        severity = 0.20 * max(0.0, (log_flux - (-1.0)) / (log_s1 - (-1.0)))
    elif log_flux < log_s2:
        t = (log_flux - log_s1) / (log_s2 - log_s1)
        severity = 0.20 + t * 0.20  # 0.20 → 0.40
    elif log_flux < log_s3:
        t = (log_flux - log_s2) / (log_s3 - log_s2)
        severity = 0.40 + t * 0.20  # 0.40 → 0.60
    elif log_flux < log_s4:
        t = (log_flux - log_s3) / (log_s4 - log_s3)
        severity = 0.60 + t * 0.20  # 0.60 → 0.80
    elif log_flux < log_s5:
        t = (log_flux - log_s4) / (log_s5 - log_s4)
        severity = 0.80 + t * 0.20  # 0.80 → 1.00
    else:
        severity = 1.0

    severity = max(0.0, min(1.0, severity))

    if s_label:
        explanation = (
            f"Solar radiation storm at NOAA {s_label} reference level "
            f"(>=10 MeV flux: {flux_pfu:.2f} pfu). "
            "Radiation hazard to astronauts, spacecraft electronics, and HF communications."
        )
    else:
        explanation = (
            f"Solar radiation below NOAA S1 threshold (>=10 MeV flux: {flux_pfu:.2f} pfu). "
            "No storm-level radiation activity."
        )

    return severity, f"{flux_pfu:.3f}", "pfu", s_label, explanation


def _parse_flare_class(class_type: str | None) -> tuple[str, float]:
    """
    Parse a GOES flare class string into (letter, magnitude).

    e.g. "M1.5" → ("M", 1.5), "X3.2" → ("X", 3.2), "C2.4" → ("C", 2.4).
    Returns ("?", 0.0) on parse failure.
    """
    if not class_type:
        return ("?", 0.0)
    s = class_type.strip().upper()
    if not s:
        return ("?", 0.0)
    letter = s[0]
    if letter not in ("A", "B", "C", "M", "X"):
        return ("?", 0.0)
    try:
        magnitude = float(s[1:]) if len(s) > 1 else 1.0
    except ValueError:
        magnitude = 1.0
    return (letter, magnitude)


def _flare_to_noaa_r(letter: str, magnitude: float) -> str | None:
    """
    Derive the NOAA R-scale reference label from a flare class.

    This is a MissionShield-derived reference, not a value from DONKI itself.
    Returns None if below the R1 threshold.
    """
    for level in ("R5", "R4", "R3", "R2", "R1"):
        ref_letter, ref_mag = NOAA_R_THRESHOLDS[level]
        if letter == ref_letter and magnitude >= ref_mag:
            return level
        # R3+ requires X class; R1/R2 require M class.
        if level in ("R4", "R5") and letter == "X" and magnitude >= ref_mag:
            return level
    # Walk down in order
    if letter == "X":
        if magnitude >= NOAA_R_THRESHOLDS["R5"][1]:
            return "R5"
        if magnitude >= NOAA_R_THRESHOLDS["R4"][1]:
            return "R4"
        return "R3"  # Any X class is at least R3
    if letter == "M":
        if magnitude >= NOAA_R_THRESHOLDS["R2"][1]:
            return "R2"
        return "R1"
    return None  # C class and below — below R1


def _flare_severity_single(
    letter: str, magnitude: float
) -> float:
    """
    Compute severity [0..1] for a single flare from its GOES class letter+magnitude.

    Severity anchors:
      C-class: 0.0 – 0.10  (sub-R1 level)
      M1 (R1): 0.15
      M5 (R2): 0.35
      X1 (R3): 0.55
      X10 (R4): 0.75
      X20 (R5): 0.90
      X20+ capped at: 1.0
    """
    if letter == "X":
        if magnitude >= 20.0:
            return min(1.0, 0.90 + 0.005 * (magnitude - 20.0))
        if magnitude >= 10.0:
            return 0.75 + 0.015 * (magnitude - 10.0)
        return 0.55 + 0.020 * (magnitude - 1.0)
    if letter == "M":
        if magnitude >= 5.0:
            return 0.35 + 0.040 * (magnitude - 5.0)
        return 0.15 + 0.040 * (magnitude - 1.0)
    if letter in ("A", "B", "C"):
        return 0.05
    return 0.0


def _recency_factor(event_time: datetime, now: datetime) -> float:
    """
    Compute a recency weight [0..1] for a flare event.

    Full weight within FLARE_RECENCY_HOURS_FULL.
    Linear decay from full to zero between FLARE_RECENCY_HOURS_FULL and
    FLARE_RECENCY_HOURS_ZERO.
    Zero beyond FLARE_RECENCY_HOURS_ZERO.
    """
    age_hours = (now - event_time).total_seconds() / 3600.0
    if age_hours <= FLARE_RECENCY_HOURS_FULL:
        return 1.0
    if age_hours >= FLARE_RECENCY_HOURS_ZERO:
        return 0.0
    decay_range = FLARE_RECENCY_HOURS_ZERO - FLARE_RECENCY_HOURS_FULL
    return 1.0 - (age_hours - FLARE_RECENCY_HOURS_FULL) / decay_range


def _flare_factor_severity(
    flares: list[SolarFlareEvent],
    now: datetime | None = None,
) -> tuple[float, str | None, str | None, str]:
    """
    Compute the solar flare factor severity from a list of recent flares.

    Takes the worst flare weighted by recency.  Does not sum flares to avoid
    artificial amplification.

    Returns: (severity, observed_value, reference_scale, explanation)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not flares:
        return (
            0.0,
            None,
            None,
            "No recent solar flares detected from NASA DONKI.",
        )

    best_severity = 0.0
    best_class = None
    best_r_label = None

    for flare in flares:
        letter, magnitude = _parse_flare_class(flare.class_type)
        raw_severity = _flare_severity_single(letter, magnitude)
        recency = _recency_factor(flare.begin_time, now)
        effective = raw_severity * recency

        if effective > best_severity:
            best_severity = effective
            best_class = flare.class_type
            best_r_label = _flare_to_noaa_r(letter, magnitude) if letter != "?" else None

    if best_class and best_r_label:
        explanation = (
            f"Most significant recent flare: {best_class} "
            f"(NOAA R-scale reference: {best_r_label}, recency-weighted severity applied). "
            "High-frequency radio communications and GPS may be affected."
        )
    elif best_class:
        explanation = (
            f"Recent flare detected: {best_class} (below NOAA R1 reference threshold). "
            "Minor HF radio effects possible."
        )
    else:
        explanation = "Recent minor or unclassified flare activity detected."

    return (
        max(0.0, min(1.0, best_severity)),
        best_class,
        best_r_label,
        explanation,
    )


def _cme_watch_severity(
    cmes: list[CMEEvent],
    now: datetime | None = None,
) -> tuple[float, str | None, str]:
    """
    Compute the Earth-directed CME watch factor severity.

    This is a MissionShield prototype heuristic — NOT an official NOAA scale.
    Severity is based on estimated hours to shock arrival from the best
    available WSA-ENLIL model run for Earth-directed CMEs.

    Severity tiers (all prototype values):
      No Earth-directed run:             0.00
      Earth-directed, no arrival time:   0.25
      Arrival > 72 h:                    0.25
      Arrival 24–72 h:                   0.50
      Arrival 6–24 h:                    0.75
      Arrival ≤ 6 h (or past):           0.95
      Arrival estimate already past:     0.00  (expired watch)

    Returns: (severity, observed_value, explanation)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    best_severity = 0.0
    best_obs = None
    best_explanation = "No Earth-directed CME model run found. No CME watch active."

    for cme in cmes:
        for analysis in cme.analyses:
            for run in analysis.enlil_runs:
                if not run.is_earth_directed:
                    continue

                arrival = run.estimated_shock_arrival_time

                if arrival is None:
                    # Earth-directed but no usable arrival time.
                    sev = 0.25
                    obs = "Earth-directed (no arrival estimate)"
                    exp = (
                        "Earth-directed CME detected in WSA-ENLIL model run "
                        "but no estimated shock arrival time available. "
                        "MissionShield CME watch: low/moderate — monitor for updates. "
                        "[MissionShield prototype watch factor — not an official NOAA scale]"
                    )
                else:
                    hours_to_arrival = (arrival - now).total_seconds() / 3600.0

                    if hours_to_arrival < 0:
                        # Arrival estimate is in the past — expired watch.
                        sev = 0.0
                        obs = f"CME arrival estimate expired ({arrival.isoformat()})"
                        exp = (
                            "WSA-ENLIL estimated shock arrival time has passed. "
                            "No active CME watch from this event. "
                            "[MissionShield prototype watch factor — not an official NOAA scale]"
                        )
                    elif hours_to_arrival <= CME_ARRIVAL_SEVERITY[0][0]:  # <= 6 h
                        sev = CME_ARRIVAL_SEVERITY[0][1]  # 0.95
                        obs = f"CME arrival ~{hours_to_arrival:.1f} h"
                        exp = (
                            f"Earth-directed CME with estimated arrival in "
                            f"{hours_to_arrival:.1f} h. "
                            "Very high MissionShield watch — imminent potential impact. "
                            "[MissionShield prototype watch factor — not an official NOAA scale]"
                        )
                    elif hours_to_arrival <= CME_ARRIVAL_SEVERITY[1][0]:  # <= 24 h
                        sev = CME_ARRIVAL_SEVERITY[1][1]  # 0.75
                        obs = f"CME arrival ~{hours_to_arrival:.1f} h"
                        exp = (
                            f"Earth-directed CME with estimated arrival in "
                            f"{hours_to_arrival:.1f} h. "
                            "High MissionShield watch. "
                            "[MissionShield prototype watch factor — not an official NOAA scale]"
                        )
                    elif hours_to_arrival <= CME_ARRIVAL_SEVERITY[2][0]:  # <= 72 h
                        sev = CME_ARRIVAL_SEVERITY[2][1]  # 0.50
                        obs = f"CME arrival ~{hours_to_arrival:.1f} h"
                        exp = (
                            f"Earth-directed CME estimated arrival in "
                            f"{hours_to_arrival:.1f} h. "
                            "Elevated MissionShield watch. "
                            "[MissionShield prototype watch factor — not an official NOAA scale]"
                        )
                    else:  # > 72 h
                        sev = 0.25
                        obs = f"CME arrival ~{hours_to_arrival:.1f} h"
                        exp = (
                            f"Earth-directed CME with estimated arrival in "
                            f"{hours_to_arrival:.1f} h (>72 h). "
                            "Low MissionShield watch. "
                            "[MissionShield prototype watch factor — not an official NOAA scale]"
                        )

                # Always update explanation for expired/zero-severity Earth-directed events
                # so the caller gets an informative explanation even when sev=0.0.
                if sev > best_severity or (
                    best_severity == 0.0 and obs is not None
                ):
                    best_severity = sev
                    best_obs = obs
                    best_explanation = exp

    return (best_severity, best_obs, best_explanation)


# ---------------------------------------------------------------------------
# Risk level mapping
# ---------------------------------------------------------------------------

def _score_to_level(score: float) -> RiskLevel:
    """
    Map a 0–100 score to a RiskLevel band.

    MissionShield prototype score bands (NOT NOAA scales):
      75–100: EXTREME
      50–74:  HIGH
      25–49:  MODERATE
      0–24:   LOW
    """
    for min_score, level_name in RISK_LEVEL_BANDS:
        if score >= min_score:
            return RiskLevel(level_name)
    return RiskLevel.LOW


# ---------------------------------------------------------------------------
# Simulation override application
# ---------------------------------------------------------------------------

def _apply_overrides(
    snapshot: SpaceWeatherSnapshot,
    overrides: SimulationOverrides,
) -> dict:
    """
    Extract scoring-relevant values from the snapshot and apply simulation
    overrides.  Never modifies the original snapshot object.

    Returns a dict of scoring inputs used by compute_risk.
    """
    # Extract live values.
    kp_val = (
        snapshot.latest_kp.estimated_kp if snapshot.latest_kp else None
    )
    proton_flux = (
        snapshot.latest_proton_flux_10mev.flux_pfu
        if snapshot.latest_proton_flux_10mev
        else None
    )
    flares = list(snapshot.recent_flares)
    cmes = list(snapshot.recent_cmes)

    # Apply overrides (simulation values are clearly named, not mixed with observations).
    sim_kp = overrides.kp_index if overrides.kp_index is not None else kp_val
    sim_flux = proton_flux  # No proton flux override in current model.

    # CME override: inject a synthetic Earth-directed watch if requested.
    if overrides.cme_earth_directed is True:
        sim_cme_severity = 0.50  # Default "active watch" severity when no detail given.
        sim_cme_obs = "SIMULATED: Earth-directed CME active"
        sim_cme_exp = (
            "Simulation override: Earth-directed CME watch active. "
            "This is a simulated scenario — not an observed NASA/NOAA event. "
            "[MissionShield prototype CME watch factor]"
        )
        sim_cme_override = (sim_cme_severity, sim_cme_obs, sim_cme_exp)
    elif overrides.cme_earth_directed is False:
        sim_cme_override = (0.0, "SIMULATED: No CME watch", "Simulation override: no Earth-directed CME.")
    else:
        sim_cme_override = None  # Use live CME data.

    return {
        "kp": sim_kp,
        "proton_flux": sim_flux,
        "flares": flares,
        "cmes": cmes,
        "cme_override": sim_cme_override,
    }


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_risk(
    snapshot: SpaceWeatherSnapshot,
    profile: MissionProfile,
    overrides: SimulationOverrides | None = None,
    now: datetime | None = None,
) -> MissionRiskReport:
    """
    Compute a deterministic MissionRiskReport from a SpaceWeatherSnapshot.

    This is a pure function.  The snapshot is never modified.
    If overrides are provided, is_simulated=True is set on the returned report.

    Parameters
    ----------
    snapshot : SpaceWeatherSnapshot
        Current space-weather snapshot (from SpaceWeatherService).
    profile : MissionProfile
        The mission type to compute risk for.
    overrides : SimulationOverrides | None
        Optional simulation overrides.  When any override is set, the result
        is marked is_simulated=True.
    now : datetime | None
        Reference "current time" for recency/CME arrival calculations.
        Defaults to datetime.now(timezone.utc).  Injected for testing.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    is_simulated = overrides is not None and any(
        v is not None
        for v in [
            overrides.kp_index,
            overrides.solar_wind_speed_km_s,
            overrides.bz_gsm_nt,
            overrides.cme_earth_directed,
            overrides.sep_event_active,
        ]
    )

    # Resolve scoring inputs (with overrides applied).
    if overrides is not None:
        inputs = _apply_overrides(snapshot, overrides)
    else:
        inputs = {
            "kp": snapshot.latest_kp.estimated_kp if snapshot.latest_kp else None,
            "proton_flux": (
                snapshot.latest_proton_flux_10mev.flux_pfu
                if snapshot.latest_proton_flux_10mev
                else None
            ),
            "flares": list(snapshot.recent_flares),
            "cmes": list(snapshot.recent_cmes),
            "cme_override": None,
        }

    weights = PROFILE_WEIGHTS[profile]

    # -----------------------------------------------------------------------
    # Factor 1: Geomagnetic disturbance (NOAA Kp / G-scale).
    # -----------------------------------------------------------------------
    if inputs["kp"] is not None:
        kp_val = float(inputs["kp"])
        if is_simulated and overrides and overrides.kp_index is not None:
            kp_label = f"SIMULATED Kp={kp_val:.2f}"
        else:
            kp_label = f"{kp_val:.2f}"
        geo_sev, geo_obs, geo_units, geo_ref, geo_exp = _geomagnetic_severity(kp_val)
        if is_simulated and overrides and overrides.kp_index is not None:
            geo_exp = f"[SIMULATED SCENARIO] {geo_exp}"
        geo_available = True
    else:
        geo_sev = 0.0
        geo_obs = None
        geo_units = None
        geo_ref = None
        geo_exp = "Kp index data unavailable. Geomagnetic factor not scored."
        geo_available = False

    # -----------------------------------------------------------------------
    # Factor 2: Solar radiation (NOAA GOES >=10 MeV proton flux / S-scale).
    # -----------------------------------------------------------------------
    if inputs["proton_flux"] is not None:
        flux_val = float(inputs["proton_flux"])
        rad_sev, rad_obs, rad_units, rad_ref, rad_exp = _radiation_severity(flux_val)
        rad_available = True
    else:
        rad_sev = 0.0
        rad_obs = None
        rad_units = "pfu"
        rad_ref = None
        rad_exp = "NOAA GOES proton flux data unavailable. Radiation factor not scored."
        rad_available = False

    # -----------------------------------------------------------------------
    # Factor 3: Solar flare / radio environment (NASA DONKI FLR / R-scale ref).
    # -----------------------------------------------------------------------
    flare_sev, flare_obs, flare_ref, flare_exp = _flare_factor_severity(
        inputs["flares"], now=now
    )
    flare_available = True  # An empty flare list is valid (no flares = low severity).

    # -----------------------------------------------------------------------
    # Factor 4: Earth-directed CME watch (MissionShield prototype heuristic).
    # -----------------------------------------------------------------------
    if inputs["cme_override"] is not None:
        cme_sev, cme_obs, cme_exp = inputs["cme_override"]
    else:
        cme_sev, cme_obs, cme_exp = _cme_watch_severity(inputs["cmes"], now=now)
    cme_available = True  # An empty CME list is valid.

    # -----------------------------------------------------------------------
    # Assemble factors with availability flags.
    # -----------------------------------------------------------------------
    raw = [
        (geo_sev, geo_available, geo_obs, geo_units, "NOAA SWPC", geo_ref, geo_exp,
         "Geomagnetic Disturbance"),
        (rad_sev, rad_available, rad_obs, rad_units, "NOAA GOES", rad_ref, rad_exp,
         "Solar Radiation"),
        (flare_sev, flare_available, flare_obs, None, "NASA DONKI", flare_ref, flare_exp,
         "Solar Flare / Radio Environment"),
        (cme_sev, cme_available, cme_obs, None, "NASA DONKI CME / WSA-ENLIL", None, cme_exp,
         "Earth-Directed CME Watch"),
    ]

    # -----------------------------------------------------------------------
    # Renormalise weights among available factors.
    # -----------------------------------------------------------------------
    available_weight_total = sum(
        weights[i] for i, (_, avail, *_rest) in enumerate(raw) if avail
    )

    missing_factors = []
    factors: list[RiskFactor] = []
    total_score = 0.0

    for i, (sev, avail, obs, units, src, ref, exp, label) in enumerate(raw):
        w = weights[i]
        if not avail:
            missing_factors.append(label)
            # Include the factor in the list as unavailable with zero contribution.
            factors.append(
                RiskFactor(
                    label=label,
                    normalized_severity=0.0,
                    mission_weight=w,
                    weighted_contribution=0.0,
                    observed_value=obs,
                    units=units,
                    source=src,
                    explanation=exp,
                    reference_scale=ref,
                    data_available=False,
                )
            )
            continue

        # Renormalise weight.
        effective_weight = w / available_weight_total if available_weight_total > 0 else 0.0
        contribution = sev * effective_weight * 100.0
        total_score += contribution

        factors.append(
            RiskFactor(
                label=label,
                normalized_severity=sev,
                mission_weight=w,
                weighted_contribution=contribution,
                observed_value=obs,
                units=units,
                source=src,
                explanation=exp,
                reference_scale=ref,
                data_available=True,
            )
        )

    total_score = max(0.0, min(100.0, total_score))

    # -----------------------------------------------------------------------
    # Data completeness and confidence.
    # -----------------------------------------------------------------------
    data_completeness = available_weight_total  # = fraction of intended weight covered.
    if data_completeness < MIN_COMPLETENESS_FOR_CONFIDENCE:
        confidence = "degraded"
    else:
        confidence = "full"

    # -----------------------------------------------------------------------
    # Risk level and primary factor.
    # -----------------------------------------------------------------------
    risk_level = _score_to_level(total_score)

    available_factors = [f for f in factors if f.data_available]
    if available_factors:
        primary_factor = max(available_factors, key=lambda f: f.weighted_contribution)
        primary_risk_factor = primary_factor.label
    else:
        primary_risk_factor = None

    return MissionRiskReport(
        mission_profile=profile,
        risk_score=round(total_score, 2),
        risk_level=risk_level,
        primary_risk_factor=primary_risk_factor,
        factors=factors,
        is_simulated=is_simulated,
        computed_at=now.isoformat(),
        data_completeness=round(data_completeness, 4),
        missing_factors=missing_factors,
        confidence=confidence,
    )
