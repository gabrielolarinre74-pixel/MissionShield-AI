"""
MissionShield AI — risk scoring policy configuration.

This module centralises all mission-profile weight matrices and scoring
constants so they can be read, audited, and tested independently.

IMPORTANT DISCLAIMERS
---------------------
- The four-factor weight matrices below are MissionShield prototype heuristics.
- They are NOT official NASA, NOAA, or any space-agency operational weights.
- They are designed to be qualitatively consistent with NOAA's published
  descriptions of storm effects (G, S, R scales) but have not been validated
  by or endorsed by any official body.
- The NOAA G / S / R reference thresholds below ARE official NOAA scale values.
  MissionShield uses them as reference anchor points only, not as certified
  flight-safety rules.

NOAA Reference Sources
----------------------
G-scale (geomagnetic): https://www.swpc.noaa.gov/noaa-scales-explanation
S-scale (radiation):    same URL
R-scale (radio):        same URL

Factor ordering throughout this module: [GEO, RAD, FLARE, CME]
  GEO   = Geomagnetic disturbance  (NOAA Kp / G-scale)
  RAD   = Solar radiation           (NOAA GOES >=10 MeV proton flux / S-scale)
  FLARE = Solar flare / radio env   (NASA DONKI FLR / R-scale reference)
  CME   = Earth-directed CME watch  (MissionShield prototype heuristic)
"""

from __future__ import annotations

from app.models.mission import MissionProfile

# ---------------------------------------------------------------------------
# NOAA G-scale reference thresholds (official Kp boundaries).
# ---------------------------------------------------------------------------
# These are the official Kp lower bounds for each NOAA geomagnetic storm level.
# Do NOT label sub-G1 activity as an official storm level.
NOAA_G_THRESHOLDS: dict[str, float] = {
    "G1": 5.0,
    "G2": 6.0,
    "G3": 7.0,
    "G4": 8.0,
    "G5": 9.0,
}

# ---------------------------------------------------------------------------
# NOAA S-scale reference thresholds (official >=10 MeV proton flux bounds).
# Units: pfu (particles cm⁻² s⁻¹ sr⁻¹).
# ---------------------------------------------------------------------------
NOAA_S_THRESHOLDS: dict[str, float] = {
    "S1": 10.0,
    "S2": 100.0,
    "S3": 1_000.0,
    "S4": 10_000.0,
    "S5": 100_000.0,
}

# ---------------------------------------------------------------------------
# NOAA R-scale reference flare-class lower bounds.
# The R scale is based on peak X-ray flux; we map GOES class strings.
# R1=M1, R2=M5, R3=X1, R4=X10, R5=X20.
# ---------------------------------------------------------------------------
NOAA_R_THRESHOLDS: dict[str, tuple[str, float]] = {
    # (class_letter, minimum_magnitude)
    "R1": ("M", 1.0),
    "R2": ("M", 5.0),
    "R3": ("X", 1.0),
    "R4": ("X", 10.0),
    "R5": ("X", 20.0),
}

# ---------------------------------------------------------------------------
# CME watch heuristic — hours-to-arrival severity mapping.
# This is a MissionShield prototype heuristic, NOT an official NOAA value.
# Severity is normalised to [0, 1].
# ---------------------------------------------------------------------------
# Key = maximum hours-until-arrival for this severity bucket.
# None = no usable estimated arrival time (Earth-directed but uncertain).
CME_ARRIVAL_SEVERITY: list[tuple[float | None, float]] = [
    # (hours_threshold, severity)
    (6.0, 0.95),    # <= 6 h  →  very high watch
    (24.0, 0.75),   # 6–24 h  →  high watch
    (72.0, 0.50),   # 24–72 h →  elevated watch
    (None, 0.25),   # Earth-directed but no usable arrival time → low/moderate
]

# Not Earth-directed: severity = 0.0
# Earth-directed with stale/past estimated arrival: severity = 0.0 (expired)

# ---------------------------------------------------------------------------
# Flare recency decay.
# Flares that occurred more than FLARE_RECENCY_HOURS_FULL ago receive reduced
# severity weight.  After FLARE_RECENCY_HOURS_ZERO hours the contribution
# decays to zero.
# This is a MissionShield prototype heuristic.
# ---------------------------------------------------------------------------
FLARE_RECENCY_HOURS_FULL = 6.0   # within 6 h → full severity
FLARE_RECENCY_HOURS_ZERO = 48.0  # older than 48 h → zero contribution

# ---------------------------------------------------------------------------
# Profile weight matrices.
# Order: [GEO, RAD, FLARE, CME]
# All weights MUST sum to exactly 1.0 — validated at import time.
#
# Design rationale (prototype heuristics):
#
# ASTRONAUT_EVA:
#   Radiation dominant — NOAA S-scale explicitly lists astronaut EVA hazard.
#   Geomagnetic also high — radiation belt dynamics and EVA suit limitations.
#
# LUNAR_MISSION:
#   Radiation very high — crew outside Earth's strongest magnetic shielding.
#   Geomagnetic moderate — some shielding lost en route and at lunar distance.
#
# LEO_SATELLITE:
#   Geomagnetic and radiation both important — NOAA describes spacecraft
#   charging, drag, and surface charging from G and S storms.
#
# ROCKET_LAUNCH:
#   Balanced across all four factors — launch windows are time-constrained,
#   all four hazards affect abort/range-safety decisions.
#   CME watch is meaningful because a launch could place crew inside a
#   developing radiation storm.
# ---------------------------------------------------------------------------
PROFILE_WEIGHTS: dict[MissionProfile, list[float]] = {
    #                       GEO   RAD   FLARE  CME
    MissionProfile.ASTRONAUT_EVA:  [0.30, 0.40, 0.15, 0.15],
    MissionProfile.LUNAR_MISSION:  [0.25, 0.40, 0.15, 0.20],
    MissionProfile.LEO_SATELLITE:  [0.35, 0.30, 0.20, 0.15],
    MissionProfile.ROCKET_LAUNCH:  [0.25, 0.25, 0.25, 0.25],
}

# Validate at import time — fail fast if any profile's weights don't sum to 1.0.
_TOLERANCE = 1e-9
for _profile, _weights in PROFILE_WEIGHTS.items():
    _total = sum(_weights)
    if abs(_total - 1.0) > _TOLERANCE:
        raise RuntimeError(
            f"Weight validation failed for {_profile}: "
            f"sum={_total} (must be 1.0). Fix PROFILE_WEIGHTS in risk_policy.py."
        )

# ---------------------------------------------------------------------------
# Score-to-RiskLevel band boundaries.
# These are MissionShield prototype score bands, NOT NOAA scale categories.
# ---------------------------------------------------------------------------
RISK_LEVEL_BANDS: list[tuple[float, str]] = [
    # (minimum_score_inclusive, level_name)
    (75.0, "EXTREME"),
    (50.0, "HIGH"),
    (25.0, "MODERATE"),
    (0.0, "LOW"),
]

# Minimum data completeness fraction before the report is flagged as degraded.
# If available weighted coverage < this threshold, confidence is "degraded".
MIN_COMPLETENESS_FOR_CONFIDENCE = 0.50
