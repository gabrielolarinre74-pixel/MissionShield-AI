# IBM Bob Development Record — MissionShield AI

This file documents how IBM Bob was used as the primary development tool
throughout the MissionShield AI project.

It is intended to support the competition README section:
**"How IBM Bob was used."**

Do NOT add fabricated timestamps, invented prompts, or work that did not happen.

---

## Phase 0 — Planning and Architecture

**Tool:** IBM Bob Plan Mode

- Repository analysed using Bob's `/init` command, which read all existing files
  and produced the initial `AGENTS.md` and `.bob/rules-*/AGENTS.md` context files.
- Full application architecture designed in Bob Plan Mode:
  - Proposed backend (FastAPI + Python), frontend (Next.js + TypeScript + Tailwind),
    AI layer (IBM Granite via watsonx.ai), and data layer (NASA DONKI + NOAA SWPC).
  - Plan written to `missionshield-plan.md` with 14 ordered sub-tasks.
- UI/UX design direction reviewed and refined in Bob Plan Mode:
  - Premium mission-control aesthetic defined.
  - IBM Plex Sans / Plex Mono typography specified.
  - Full design token system (color, surface hierarchy, spacing, motion) documented
    in the plan before any frontend code was written.
  - Design quality gate established as a prerequisite for Sub-Task 9.
- Plan corrections applied after user review:
  - Removed fabricated "CME arrival probability" — replaced with actual ENLIL model fields.
  - Corrected SEP event handling — DONKI SEP records are events, not flux measurements.
  - Added NOAA GOES integral-proton feed as the authoritative numerical proton source.
  - Railway set as preferred deployment target (Render as fallback).
  - Deployment reclassified from stretch to MVP quality requirement.

**Artefacts produced:**
- `missionshield-plan.md`
- `AGENTS.md`
- `.bob/rules-agent/AGENTS.md`
- `.bob/rules-ask/AGENTS.md`
- `.bob/rules-plan/AGENTS.md`

---

## Phase 1 — Backend Foundation

**Tool:** IBM Bob Agent Mode

### What was built

All backend code was written by IBM Bob Agent Mode in a single implementation session.

**API client layer:**
- `backend/app/clients/nasa_donki.py` — Async NASA DONKI client (FLR, CME, GST, SEP).
  Normalises all events into typed Pydantic models. Preserves ENLIL WSA model run data
  including `isEarthGB` and `estimatedShockArrivalTime`. Raises `DataSourceUnavailableError`
  on failure.
- `backend/app/clients/noaa_swpc.py` — Async NOAA SWPC + NOAA GOES client.
  Feeds: Kp index, solar wind (L1), magnetic field (L1), GOES integral-proton flux.
  Handles NOAA `-9999` missing-data sentinel (normalised to `None`).
  Active/primary row selection for wind and mag-field.

**Domain models:**
- `backend/app/models/space_weather.py` — All space-weather domain types with explicit units,
  UTC-aware datetimes, and per-source provenance.
- `backend/app/models/mission.py` — `MissionProfile` enum and `SimulationOverrides`.
- `backend/app/models/risk.py` — Risk domain types (placeholder for Phase 2 risk engine).

**Services:**
- `backend/app/services/cache.py` — Async-safe in-memory TTL cache with LIVE/CACHED/STALE semantics.
- `backend/app/services/space_weather.py` — `SpaceWeatherService`: concurrent multi-source fetch,
  partial-failure tolerance (NOAA up + NASA down = return partial snapshot, not an error),
  stale-cache fallback.

**Application:**
- `backend/app/config.py` — `pydantic-settings` configuration; reads repo-root `.env` automatically.
- `backend/app/exceptions.py` — Domain exception hierarchy.
- `backend/app/dependencies.py` — FastAPI dependency injectors.
- `backend/app/main.py` — FastAPI app factory with CORS, lifespan handler, structured error handlers.
- `backend/app/routes/health.py` — `GET /api/health`
- `backend/app/routes/space_weather.py` — `GET /api/space-weather/snapshot`, `GET /api/space-weather/events`

**Tests (24 total, all passing):**
- `backend/tests/test_health.py` — Health endpoint; secret non-exposure verified.
- `backend/tests/test_nasa_client.py` — All four DONKI endpoints; null handling; error handling.
- `backend/tests/test_noaa_client.py` — Kp, wind, mag, proton; `-9999` sentinel; error handling.
- `backend/tests/test_space_weather_service.py` — Live assembly, cache hit, partial failure,
  all-sources-fail-no-cache, stale-cache fallback.
- `backend/tests/fixtures/` — 8 sanitised real-API JSON fixtures.

### Live validation (against real APIs)

Bob ran `backend/sanity_check.py` against live NASA DONKI and NOAA SWPC endpoints.

Results at time of Phase 1 completion:
- NOAA Kp: 358 readings parsed; latest `estimated_kp=1.0`, `kp_index=1`
- NOAA Solar Wind: 3,576 rows; active speed ~401–428 km/s (SOLAR1/ACE)
- NOAA Magnetic Field: 3,514 rows; active `bz_gsm` ~+1.5 to -7.6 nT (SOLAR1)
- NOAA GOES Proton: 560 rows; latest `>=10 MeV` ~0.21 pfu (GOES-18)
- NASA DONKI Flares (7d): 1 event (C2.4 class)
- NASA DONKI CMEs (7d): 26 events; 4 ENLIL Earth-directed model runs
- NASA DONKI GST (30d): 2 events
- NASA DONKI SEP (30d): 6 event records (correctly not treated as flux values)

### Endpoint test results

All three endpoints tested via `backend/endpoint_test.py` using the FastAPI ASGI test client:

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/health` | 200 OK | Returns `status: ok`, no secrets |
| `GET /api/space-weather/snapshot` | 200 OK | `freshness: live`, all 3 sources available, `X-Data-Freshness` header set |
| `GET /api/space-weather/events` | 200 OK | `freshness: cached` (second call, correct), 1 flare, 26 CMEs, 1 GST, 0 SEP in 7d window |

---

## Phase 2 — Mission Risk Intelligence + Anomaly Detection + IBM Granite

**Tool:** IBM Bob Agent Mode

### What was built

All Phase 2 code was written by IBM Bob Agent Mode in a single implementation session.

**Risk engine:**
- `backend/app/services/risk_policy.py` — Centralised weight matrix, NOAA G/S/R reference
  thresholds, CME watch heuristic, risk level bands.  All weights validated to sum to 1.0.
- `backend/app/services/risk_engine.py` — Pure deterministic scoring function.
  Four primary factors (Geomagnetic/GEO, Solar Radiation/RAD, Solar Flare/FLARE,
  Earth-directed CME Watch/CME) with piecewise severity functions anchored to NOAA
  G/S/R scale boundaries.  Missing-data renormalization, data_completeness,
  confidence indicator, simulation override support.

**Model updates:**
- `backend/app/models/risk.py` — Expanded `RiskFactor` (normalized_severity,
  mission_weight, weighted_contribution, observed_value, units, source, explanation,
  reference_scale, data_available) and `MissionRiskReport` (data_completeness,
  missing_factors, confidence).
- `backend/app/models/space_weather.py` — Added `recent_*_series` time-series fields
  to `SpaceWeatherSnapshot` for anomaly detection (excluded from public API).

**Anomaly detection:**
- `backend/app/services/anomaly.py` — Robust z-score (median/MAD) anomaly detection
  for Kp, solar wind speed, IMF Bz, ≥10 MeV proton flux.  MAD=0 fallback handles
  constant series.  Minimum sample count enforced.  Clearly separated from hazard score.

**IBM Granite AI service:**
- `backend/app/ai/__init__.py` — Package initializer.
- `backend/app/ai/watsonx_client.py` — WatsonxClient wrapping `ibm_watsonx_ai`
  `Credentials` + `ModelInference`.  Lazy initialization.  Credentials never logged.
- `backend/app/ai/prompts.py` — System and user prompt templates.  Constraints
  explicitly instruct Granite not to invent measurements, not to claim NASA/NOAA
  endorsement, and to distinguish simulated from observed data.
- `backend/app/ai/mission_ai.py` — `generate_brief()` and `answer_question()`.
  Context serialization (no credentials in context).  Brief cache (5-min TTL).
  Chat history bounded to last 8 messages.  AI failures raise `AIServiceError`.

**API routes:**
- `backend/app/routes/mission.py` — `POST /api/mission/risk`
- `backend/app/routes/ai.py` — `POST /api/ai/brief`, `POST /api/ai/chat`
- `backend/app/routes/space_weather.py` — Added `GET /api/space-weather/anomalies`
- `backend/app/main.py` — Registered new routers.
- `backend/app/dependencies.py` — Added `get_watsonx_client()` dependency.

**Services extension:**
- `backend/app/services/space_weather.py` — Extended `_fetch_live()` to retain
  time-series windows for anomaly detection.

**Documentation:**
- `docs/risk-methodology.md` — Full methodology documentation including NOAA
  official reference mappings, prototype disclaimers, weight matrix, CME heuristic,
  anomaly method.

### Tests (196 total, all passing)

Phase 2 added:
- `backend/tests/test_risk_engine.py` — 74 tests.
  NOAA G/S/R scale boundaries, all four profiles, weight sums, score bounds,
  risk level bands, primary factor determinism, missing data, degraded confidence,
  simulation override, snapshot immutability.
- `backend/tests/test_anomaly.py` — 27 tests.
  Normal/outlier/insufficient/MAD=0/null cases for all four parameters.
- `backend/tests/test_granite.py` — 22 tests (all mocked — no live API calls).
  Context serialization, credential security, brief caching, history bounding,
  AI error handling, prompt content verification.
- `backend/tests/test_phase2_endpoints.py` — 22 tests.
  All new routes, simulation, graceful AI failure, credential non-exposure,
  Phase 1 regression.

Phase 1's 24 tests continue passing (196 total across both phases).

### Live Granite sanity check

One live IBM Granite sanity check was performed via `backend/sanity_check_phase2.py`
to verify the Phase 2 Mission AI service works end-to-end with real credentials.
See that file for the result at time of Phase 2 completion.

---

## Upcoming Phases

- **Phase 3** — API surface completion and Phase 2/3 integration verification
- **Phase 4** — Next.js frontend (design system → dashboard → Mission AI panel → simulation)
- **Phase 5** — Deployment (Railway backend, Vercel frontend)
- **Phase 6** — Documentation and final polish
