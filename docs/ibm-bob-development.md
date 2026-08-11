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

## Upcoming Phases

- **Phase 2** — Risk engine (weighted scoring per mission profile) + anomaly detection
- **Phase 3** — IBM Granite AI service (mission brief + contextual Q&A)
- **Phase 4** — Next.js frontend (design system → dashboard → Mission AI panel → simulation)
- **Phase 5** — Deployment (Railway backend, Vercel frontend)
- **Phase 6** — Documentation and final polish
