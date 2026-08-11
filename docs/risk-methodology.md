# MissionShield AI — Risk Methodology

**Version:** Phase 2  
**Status:** Prototype / Research  

---

## Disclaimer

**MissionShield provides prototype decision-support intelligence and is not an official NASA, NOAA, or flight-safety rating.**

This document describes the methodology behind the MissionShield 0–100 risk score.
Nothing in this document, or in MissionShield's API responses, constitutes:

- Official mission go/no-go authority
- A NASA-certified risk assessment
- A NOAA-endorsed operational rating
- Flight-certified software output

MissionShield is designed for the IBM AI Builders Challenge (August 2026).
It is a demonstration of AI-assisted decision support, not a production safety system.

---

## 1. What the MissionShield Risk Score Means

The risk score is a **transparent, deterministic, prototype heuristic** that combines
four primary space-weather hazard measurements into a single 0–100 number tailored
to a specific mission type.

**It means:** "Based on current NASA and NOAA observations, and using MissionShield's
prototype weighting model, this mission profile has this level of assessed exposure
to four primary space-weather hazards."

**It does NOT mean:**
- An official safety clearance or denial
- A NASA or NOAA operational risk rating
- A flight-certified risk assessment
- A guarantee of any level of safety or danger

---

## 2. Official NOAA Reference Scales Used

MissionShield uses official NOAA space-weather scale thresholds as **scientific anchor
points** for the severity calculation.  These scales are real and published by NOAA.
Their use as anchors in this prototype does not imply NOAA endorsement.

### Geomagnetic Storm Scale (G-scale)

| NOAA Level | Minimum Kp | MissionShield Usage |
|---|---|---|
| G1 (Minor) | Kp ≥ 5 | Severity anchor at 0.20 |
| G2 (Moderate) | Kp ≥ 6 | Severity anchor at 0.40 |
| G3 (Strong) | Kp ≥ 7 | Severity anchor at 0.60 |
| G4 (Severe) | Kp ≥ 8 | Severity anchor at 0.80 |
| G5 (Extreme) | Kp ≥ 9 | Severity = 1.0 (maximum) |

Sub-G1 conditions (Kp < 5) are NOT labelled as official G-scale storms.
Severity scales linearly from 0 at Kp=0 to 0.20 at Kp=5.

**Source:** NOAA Kp index from `planetary_k_index_1m.json` (NOAA SWPC, `estimated_kp` field).

### Solar Radiation Storm Scale (S-scale)

| NOAA Level | Threshold (≥10 MeV flux) | MissionShield Usage |
|---|---|---|
| S1 (Minor) | ≥ 10 pfu | Severity anchor at 0.20 |
| S2 (Moderate) | ≥ 100 pfu | Severity anchor at 0.40 |
| S3 (Strong) | ≥ 1,000 pfu | Severity anchor at 0.60 |
| S4 (Severe) | ≥ 10,000 pfu | Severity anchor at 0.80 |
| S5 (Extreme) | ≥ 100,000 pfu | Severity = 1.0 (maximum) |

Severity is piecewise linear on a log10 scale between each boundary.

**Source:** NOAA GOES primary satellite integral proton flux from
`integral-protons-6-hour.json` (NOAA GOES, `>=10 MeV` energy channel).

### Solar Radio Blackout Scale (R-scale) — Flare Reference

MissionShield derives a NOAA R-scale **reference** from NASA DONKI flare class strings.
This is a MissionShield derivation, not a value assigned by DONKI itself.

| NOAA Level | Flare Class | MissionShield Usage |
|---|---|---|
| R1 (Minor) | M1+ | Severity anchor at 0.15 |
| R2 (Moderate) | M5+ | Severity anchor at 0.35 |
| R3 (Strong) | X1+ | Severity anchor at 0.55 |
| R4 (Severe) | X10+ | Severity anchor at 0.75 |
| R5 (Extreme) | X20+ | Severity anchor at 0.90–1.0 |

Flares below M1 (C-class, B-class, A-class) contribute a background severity of 0.05.

**Recency decay (prototype heuristic):** A flare's contribution is weighted by how recently
it occurred.  Full weight within 6 hours; linear decay to zero at 48 hours.  This prevents
a week-old flare from contributing the same urgency as a current one.

**Source:** NASA DONKI FLR endpoint (`classType` field).

---

## 3. Four Primary Hazard Factors

MissionShield uses exactly four primary factors to avoid double-counting correlated
observations.

### Factor 1: Geomagnetic Disturbance (GEO)

- **Source:** NOAA SWPC Kp index (most recent `estimated_kp` value)
- **Scale reference:** NOAA G-scale thresholds (see above)
- **Rationale:** Kp is the primary numerical indicator of geomagnetic activity.
  It directly measures the impact of solar wind and magnetic field disturbances on
  Earth's magnetosphere.

### Factor 2: Solar Radiation (RAD)

- **Source:** NOAA GOES primary satellite ≥10 MeV integral proton flux (most recent value)
- **Scale reference:** NOAA S-scale thresholds (see above)
- **Rationale:** The ≥10 MeV proton flux is the numerical basis for NOAA's official
  S-scale radiation storm levels.  It is the most relevant measurement for astronaut
  radiation hazard and spacecraft effects.

### Factor 3: Solar Flare / Radio Environment (FLARE)

- **Source:** NASA DONKI FLR events (last 7 days), with recency weighting
- **Scale reference:** NOAA R-scale reference derived from GOES class string
- **Rationale:** X-class and M-class flares create radio blackouts and ionospheric
  disturbances affecting communication systems.

### Factor 4: Earth-Directed CME Watch (CME)

- **Source:** NASA DONKI CME + WSA-ENLIL model runs (`isEarthGB`, `estimatedShockArrivalTime`)
- **Scale reference:** NONE — this is a **MissionShield prototype heuristic**.
  There is no official NOAA scale for CME watch in this form.

CME watch severity (prototype):

| Condition | Severity |
|---|---|
| No Earth-directed model run | 0.00 |
| Earth-directed, no arrival estimate | 0.25 |
| Arrival > 72 h | 0.25 (low watch) |
| Arrival 24–72 h | 0.50 (elevated watch) |
| Arrival 6–24 h | 0.75 (high watch) |
| Arrival ≤ 6 h | 0.95 (very high watch) |
| Arrival estimate past/expired | 0.00 (expired) |

---

## 4. Why Additional Correlated Signals Are Not Double-Counted

Several available data sources describe the **same physical phenomenon**:

| Physical Event | Available Signals |
|---|---|
| Geomagnetic disturbance | NOAA Kp, NASA DONKI GST events, IMF Bz |
| Solar radiation storm | NOAA GOES proton flux, NASA DONKI SEP events |
| Geomagnetic + CME | CME drives both Kp increase and GST events |

Using all of these as separate scored factors would **artificially inflate** the risk score
by counting the same storm multiple times.

MissionShield's policy:

- **Numerical Kp** represents the geomagnetic hazard.
  DONKI GST events and IMF Bz are used as **context/explanation** only.
- **NOAA GOES proton flux** represents the radiation hazard.
  DONKI SEP event records are used as **context/explanation** only.
  (DONKI SEP records are event notices, not flux measurements.)
- **CME watch** is a prospective factor — it looks ahead at potential future disturbances.
  It does not duplicate the current Kp measurement.

---

## 5. Mission Profile Weight Matrix

**These weights are MissionShield prototype design decisions.
They are NOT official NASA, NOAA, or space-agency operational weights.**

They are designed to be qualitatively consistent with NOAA's published descriptions
of storm effects on different systems, but have not been validated by any official body.

| Profile | GEO (Kp) | RAD (Flux) | FLARE | CME Watch |
|---|---|---|---|---|
| ASTRONAUT_EVA | 0.30 | **0.40** | 0.15 | 0.15 |
| LUNAR_MISSION | 0.25 | **0.40** | 0.15 | 0.20 |
| LEO_SATELLITE | **0.35** | 0.30 | 0.20 | 0.15 |
| ROCKET_LAUNCH | 0.25 | 0.25 | 0.25 | 0.25 |

**All weight rows sum to exactly 1.0** (validated at import time in `risk_policy.py`).

### Design Rationale

**ASTRONAUT_EVA:** Radiation is dominant (weight 0.40) because NOAA's S-scale explicitly
describes astronaut EVA radiation hazard as a primary effect at S1+.
Geomagnetic disturbance is also high (0.30) because EVA suits offer no radiation
belt shielding and geomagnetic activity affects radiation belt dynamics.

**LUNAR_MISSION:** Radiation is also dominant (0.40) because crew outside Earth's
magnetosphere depend entirely on situational awareness for radiation timing.
CME watch gets a slightly higher weight (0.20) because transits between Earth and
Moon can expose the crew to an arriving CME with no protective atmosphere.

**LEO_SATELLITE:** Geomagnetic disturbance is highest (0.35) because NOAA describes
spacecraft surface charging, drag increases, and uplink disruption at G1+.
Radiation is also important (0.30) for electronics and solar panels.

**ROCKET_LAUNCH:** Equal weights (0.25 each) reflect that all four factors affect
different aspects of launch operations: geomagnetic affects range-safety communication,
radiation affects crew on ascent, flares affect HF communications, CME watch matters
because a launch could place crew inside a developing storm.

---

## 6. Score Calculation

```
score = sum( severity_i * (weight_i / available_weight_total) * 100 )
        for each available primary factor i
```

Where `available_weight_total = sum(weight_i for available factors only)`.

Weights are renormalized among available factors when some data is missing.
This means if 3 of 4 factors are available, the score is still scaled to 0–100
using only those 3 factors' weights.

**Score capping:** The result is clamped to [0, 100].

---

## 7. Risk Level Bands

**These are MissionShield prototype score bands, NOT NOAA scale categories.**

| Score | Risk Level |
|---|---|
| 75–100 | EXTREME |
| 50–74 | HIGH |
| 25–49 | MODERATE |
| 0–24 | LOW |

---

## 8. Missing Data / Completeness Policy

MissionShield does NOT treat missing data as zero risk.

If a primary factor's source data is unavailable:
- The factor is marked `data_available=False` in the response.
- Its contribution is treated as zero for scoring purposes.
- Weights are renormalized among available factors.
- `data_completeness` = fraction of total intended weight that was available (0.0–1.0).
- `missing_factors` lists the unavailable factor names.
- `confidence` = `"degraded"` when `data_completeness < 0.50`.

**Minimum completeness threshold:** If less than 50% of the intended weighted factor
coverage is available, the report's `confidence` field is set to `"degraded"`.
The API caller and frontend must communicate this uncertainty to users.

---

## 9. Anomaly Detection

### Method

MissionShield uses a **robust z-score** (median / MAD) to detect statistically
unusual readings in space-weather time series.

```
z = 0.6745 × (x − median(baseline)) / MAD(baseline)
```

Where MAD = median(|x_i − median(x)|).
The constant 0.6745 makes the robust z-score comparable to a conventional z-score
under approximately Gaussian distributions.

**Fallback when MAD = 0:** If the baseline is constant (MAD=0), the algorithm
falls back to conventional z-score using sample standard deviation.
If both MAD and std are zero AND the new value differs from the constant baseline,
the value is flagged as anomalous (capped at |z| = 10).

### Threshold

`|z| ≥ 3.0` → flagged as anomalous.

### Parameters Evaluated

- Kp index (`estimated_kp`)
- Solar wind speed (`proton_speed_km_s`)
- IMF Bz (`bz_gsm_nt`)
- ≥10 MeV proton flux (log10-transformed, `proton_flux_10mev_pfu`)

### Minimum Sample Count

At least 5 readings are required in the baseline before anomaly detection runs.
With fewer readings, statistics are unreliable and results are withheld.

### IMPORTANT: Anomaly ≠ Danger

**A statistical anomaly flag does NOT automatically indicate a dangerous condition.**

An anomaly means the current reading is statistically unusual relative to the recent
baseline.  The hazard significance of an anomaly depends on its direction, magnitude,
and the mission context.

Anomaly flags are **situational awareness signals** surfaced separately from the
mission risk score.  They are not numerically added to the risk score.

---

## 10. Simulation Mode

When simulation overrides are active (`is_simulated=True`):

- Simulated values replace specific live measurements for risk scoring only.
- The original `SpaceWeatherSnapshot` is never modified.
- Simulated values are clearly labelled in the response and in Granite context.
- Granite's prompt explicitly identifies simulated scenarios.
- Simulation values are not described as NASA or NOAA observations.

Currently supported simulation overrides: Kp index, solar wind speed, IMF Bz,
CME Earth-directed toggle.

---

## 11. IBM Granite Integration

IBM Granite (via watsonx.ai) receives a curated text context containing:
- Mission profile
- Deterministic risk score and level
- Factor breakdown with source provenance
- Current NASA/NOAA observations
- Anomaly flags
- Data completeness and confidence
- Simulation status

Granite converts this structured material into human-readable decision-support language.

**Granite does NOT:**
- Calculate the numerical risk score (that is deterministic Python code)
- Invent measurements not provided in context
- Claim official NASA/NOAA endorsement
- Provide official go/no-go authority
- Receive or echo credentials or configuration secrets

---

## 12. Limitations

1. The weight matrix is a prototype design decision, not empirically validated.
2. CME watch severity is a heuristic — real CME impact probability is complex.
3. The recency decay for flares (full for 6h, zero at 48h) is a design choice.
4. Only four primary factors are included — other space-weather parameters exist.
5. The score does not account for mission-specific hardware tolerance thresholds.
6. Kp is a 3-hour average — short-duration events may not be fully captured.
7. Anomaly detection requires a time-series window; fresh cache returns no anomalies.
8. The system depends on NASA DONKI and NOAA SWPC uptime and data freshness.

---

## Source References

- NOAA Space Weather Scales: https://www.swpc.noaa.gov/noaa-scales-explanation
- NASA DONKI API: https://api.nasa.gov/DONKI/
- NOAA SWPC Real-Time Data: https://services.swpc.noaa.gov/
- NOAA GOES Proton Flux: https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json
