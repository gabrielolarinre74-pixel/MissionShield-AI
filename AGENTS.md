# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

**MissionShield AI** — AI-powered space mission decision-support platform.
IBM AI Builders Challenge, August 2026 theme: Advance Space Exploration with AI.

## Stack

- Python 3.14 (venv at `.venv/`) — backend
- FastAPI + pydantic-settings + httpx — REST API
- `ibm_watsonx_ai==1.6.1` — IBM Granite / watsonx.ai (AI layer, Phase 2+)
- `python-dotenv` — loads `.env` from repo root
- Next.js + TypeScript + Tailwind CSS — frontend (Phase 4, not yet scaffolded)
- No database — in-memory TTL cache only

## Running the backend

```powershell
# From repo root
cd backend
& "..\..\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
```
Or from repo root:
```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
`--reload` requires running from `backend/` so uvicorn can find the `app` package.

## Running tests

```powershell
# From repo root — always use the venv Python
.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

## Running a single test

```powershell
.venv\Scripts\python.exe -m pytest backend/tests/test_noaa_client.py::test_kp_normalizes_correctly -v
```

## Live sanity check (real API calls)

```powershell
.venv\Scripts\python.exe backend/sanity_check.py
```

## Required `.env` file (gitignored — never committed)

Located at repo root. Backend reads it automatically via `config.py`.
See `backend/.env.example` for all supported variable names.

Required for IBM AI features (Phases 2+):
```
WATSONX_APIKEY=
WATSONX_URL=
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=
```

Required for data layer (Phase 1+):
```
NASA_API_KEY=DEMO_KEY   # DEMO_KEY works locally but is rate-limited
```

Optional:
```
FRONTEND_ORIGIN=http://localhost:3000
CACHE_TTL_SECONDS=300
EXTERNAL_API_TIMEOUT_SECONDS=10
```

## Backend structure

```
backend/
  app/
    config.py          # pydantic-settings; reads repo-root .env
    exceptions.py      # DataSourceUnavailableError, PartialDataError, etc.
    dependencies.py    # FastAPI Depends injectors (cache, services)
    main.py            # FastAPI app factory, CORS, lifespan, routers
    models/
      space_weather.py # All space-weather Pydantic models (with units)
      mission.py       # MissionProfile enum, SimulationOverrides
      risk.py          # RiskLevel, RiskFactor, MissionRiskReport (Phase 2)
    clients/
      nasa_donki.py    # Async NASA DONKI client (FLR, CME, GST, SEP)
      noaa_swpc.py     # Async NOAA SWPC + NOAA GOES client
    services/
      cache.py         # In-memory async TTL cache (LIVE/CACHED/STALE)
      space_weather.py # SpaceWeatherService — orchestrates clients + cache
    routes/
      health.py        # GET /api/health
      space_weather.py # GET /api/space-weather/snapshot, /events
  tests/
    fixtures/          # Sanitised real-API JSON fixtures (no live calls in tests)
    conftest.py        # Shared fixtures including async FastAPI test client
    test_health.py
    test_nasa_client.py
    test_noaa_client.py
    test_space_weather_service.py
```

## Key non-obvious patterns

- `config.py` walks up from `backend/app/` to the repo root to find `.env` automatically.
- NOAA feeds use `-9999` as a missing-data sentinel — `_noaa_val()` in `noaa_swpc.py` normalises these to `None`. Never convert to zero.
- NASA DONKI SEP records are **event records**, not flux values. For numerical proton flux use the NOAA GOES `integral-protons-6-hour.json` feed (`ProtonFluxReading`).
- CME Earth-direction comes from `enlilList[].isEarthGB` in the analysis. There is no "CME arrival probability" field — do not invent one.
- `SpaceWeatherService` tolerates partial source failures: if NOAA is down but NASA is up, it returns a partial snapshot rather than raising.
- `DataFreshness`: LIVE = fresh from upstream; CACHED = within TTL; STALE = expired cache served because upstream failed.
- `active=true` in NOAA wind/mag feeds marks the designated primary instrument source row.
- All datetimes are UTC-aware. NOAA timestamps have no timezone suffix but are implicitly UTC.
- Tests use `pytest-asyncio` in STRICT mode — all async tests need `@pytest.mark.asyncio`.

## Security constraints

- `.env` is in both `.gitignore` and `.bobignore` — never commit it.
- Never print, log, or return `WATSONX_APIKEY`, `NASA_API_KEY`, or any credential value.
- Only refer to variable names, never values.
- `/api/health` deliberately returns only name and version — no config values.

## IBM Bob evidence

- `docs/ibm-bob-development.md` — development record for competition submission.
- `missionshield-plan.md` — full architecture and implementation plan.
