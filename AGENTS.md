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
- Next.js 16.3.0 + TypeScript + Tailwind CSS v4 + App Router — frontend (`frontend/`)
- `lucide-react` — minimal icon set for navigation
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

## Running the frontend

```powershell
# From repo root — starts Next.js dev server at http://localhost:3000
cd frontend
npm run dev
```

Or from the `frontend/` directory:
```powershell
npm run dev   # development server
npm run build # production build
npm run lint  # ESLint
npm start     # production server (after build)
```

The frontend requires the backend to be running at `http://localhost:8000`.
The frontend URL is configured in `frontend/.env.local` via `NEXT_PUBLIC_API_URL`.

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
    dependencies.py    # FastAPI Depends injectors (cache, services, AI client)
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
      risk_policy.py   # (Phase 2) Profile weights, NOAA scale thresholds, CME heuristic
      risk_engine.py   # (Phase 2) Deterministic compute_risk() pure function
      anomaly.py       # (Phase 2) Robust z-score anomaly detection
    ai/
      watsonx_client.py # (Phase 2) WatsonxClient wrapping ibm_watsonx_ai SDK
      prompts.py        # (Phase 2) All Granite prompt templates
      mission_ai.py     # (Phase 2) generate_brief(), answer_question(), brief cache
    routes/
      health.py        # GET /api/health
      space_weather.py # GET /api/space-weather/snapshot, /events, /anomalies
      mission.py       # (Phase 2) POST /api/mission/risk
      ai.py            # (Phase 2) POST /api/ai/brief, POST /api/ai/chat
  tests/
    fixtures/          # Sanitised real-API JSON fixtures (no live calls in tests)
    conftest.py        # Shared fixtures including async FastAPI test client
    test_health.py
    test_nasa_client.py
    test_noaa_client.py
    test_space_weather_service.py
    test_risk_engine.py     # (Phase 2) 74 deterministic risk engine tests
    test_anomaly.py         # (Phase 2) 27 anomaly detection tests
    test_granite.py         # (Phase 2) 22 mocked Granite integration tests
    test_phase2_endpoints.py # (Phase 2) 22 endpoint acceptance tests
```

## Frontend structure (Phase 3)

```
frontend/
  src/
    app/
      layout.tsx         # Minimal root layout, dark color-scheme
      page.tsx           # Root application shell (single-page, section routing)
      globals.css        # Design tokens (CSS vars), IBM Plex fonts, skeleton/spin animations
    components/
      shell/
        NavRail.tsx      # Left navigation rail (220px expanded, 56px collapsed)
        StatusBar.tsx    # Top status bar (freshness, source status, refresh, AI toggle)
      overview/
        MissionSelector.tsx    # Segmented 4-mission profile selector
        MissionReadiness.tsx   # Mission readiness module (score, level, factors summary)
        RiskFactorBreakdown.tsx # Expandable 4-factor risk breakdown with bars + methodology
      telemetry/
        TelemetryStrip.tsx     # 4-column Kp/Wind/Bz/Proton coherent telemetry surface
      risk/
        SpaceWeatherView.tsx   # Detailed Space Weather section (measurement cards)
        RiskAnalysisView.tsx   # Deep risk analysis (factor table, official vs prototype)
      simulation/
        SimulationPanel.tsx    # What-if simulation controls + simulated risk result
      events/
        EventsPanel.tsx        # NASA DONKI event timeline + anomaly detection panel
      ai/
        MissionAIPanel.tsx     # Right-side Mission AI: brief + chat + starter questions
      ui/
        FreshnessBadge.tsx     # LIVE/CACHED/STALE badge with pulsing dot
        RiskBadge.tsx          # Semantic risk level badge
        SimBadge.tsx           # Amber simulation badge
        Skeleton.tsx           # Content-shaped loading skeletons
        ErrorState.tsx         # 6-variant error/degraded state component
    hooks/
      useSpaceWeather.ts    # Snapshot fetch + 5-min polling + abort
      useMissionRisk.ts     # Risk report fetch driven by profile + overrides
      useMissionAI.ts       # Brief (4-min client cache) + bounded chat history
      useSimulation.ts      # Simulation override state
    lib/
      api.ts              # Typed fetch client (ApiClientError, all 7 endpoints)
      formatters.ts       # UTC, Kp, flux, risk color, completeness, freshness formatters
      constants.ts        # Poll interval, chat max, sim ranges, NOAA scale descriptions
    types/
      index.ts            # TypeScript mirror of all backend Pydantic models
  .env.local              # NEXT_PUBLIC_API_URL=http://localhost:8000 (gitignored)
  .env.local.example      # Safe placeholder for documentation
  eslint.config.mjs       # ESLint config (react-hooks/set-state-in-effect disabled for fetch patterns)
```

## Frontend API boundary

- Only `NEXT_PUBLIC_API_URL` is exposed to the browser — defaults to `http://localhost:8000`.
- No credentials (`WATSONX_APIKEY`, `NASA_API_KEY`) appear in the frontend.
- Frontend sends only: mission profile, optional simulation overrides, chat message, bounded history.
- Backend constructs authoritative NASA/NOAA intelligence context for all AI calls.

## Frontend design rules

- Background/surface: `--background: #0B0D10`, `--surface-1/2/3` hierarchy
- Typography: IBM Plex Sans (UI), IBM Plex Mono (telemetry values, timestamps, scores)
- Risk colors: LOW=green, MODERATE/HIGH=orange, EXTREME=red
- Simulation: amber `--sim-color` — clearly distinguishable from live data
- Freshness: LIVE=green, CACHED=blue, STALE=orange
- No gradient backgrounds, glassmorphism, decorative animations, or fake data
- Skeleton loading states rather than spinners; error states per failure type
- Semantic colors used only where data warrants them (never decorative)

## Frontend simulation semantics

- `SimulationOverrides` fields match the backend model exactly: `kp_index`, `solar_wind_speed_km_s`, `bz_gsm_nt`, `cme_earth_directed`, `sep_event_active`
- Simulated values never mix with live telemetry display
- `SimBadge` appears in status bar, mission readiness, AI panel, and risk result when active
- Chat history is cleared on profile change to prevent cross-mission contamination
- Brief is not auto-regenerated on every render — only on profile change or manual action

## Frontend AI request constraints

- Mission Brief: auto-generated once on profile load; client-side cached for 4 min; regenerate on explicit request only
- Chat: bounded to ≤16 messages (matches backend `max_length=16`); abort-ref prevents orphaned requests
- AI unavailability is surfaced as a designed error state; deterministic risk data is unaffected
- If Granite is unavailable, brief and chat degrade gracefully — no whole-page failure

## Risk engine architecture (Phase 2)

- `compute_risk(snapshot, profile, overrides?)` in `risk_engine.py` is a pure function — no I/O, no randomness, no LLM.
- Four primary factors: GEO (Kp/G-scale), RAD (GOES flux/S-scale), FLARE (DONKI FLR/R-scale ref), CME (prototype watch).
- NOAA G/S/R thresholds are **official reference values** — our weights are **prototype heuristics**.
- Missing factor data does NOT become zero risk — weights are renormalized among available factors.
- `data_completeness < 0.50` → `confidence="degraded"`.
- Simulation overrides (SimulationOverrides) replace live values for scoring only; original snapshot is never mutated.
- `is_simulated=True` when any override is active.

## Official reference vs MissionShield prototype heuristic

| Concept | Type | Description |
|---|---|---|
| NOAA G/S/R scale thresholds | **OFFICIAL** | Kp/flux/flare-class boundaries published by NOAA |
| Mission profile weight matrix | **PROTOTYPE** | MissionShield design choice; not official |
| 0–100 risk score | **PROTOTYPE** | Not a NOAA or NASA rating |
| Risk level bands (LOW/MODERATE/HIGH/EXTREME) | **PROTOTYPE** | Not NOAA categories |
| CME watch severity tiers | **PROTOTYPE** | No official NOAA equivalent |
| Anomaly z-score threshold (3.0) | **PROTOTYPE** | Statistical convention |

## AI service boundaries (Phase 2)

- Granite **does not** calculate the numerical risk score.
- Granite **does** convert the deterministic risk context into human-readable language.
- Context sent to Granite: mission profile, risk score, factor breakdown, observations, anomaly flags, freshness, simulation status.
- Context sent to Granite: **no credentials, no API keys, no config values**.
- `AIServiceError` is caught at the route level — AI failure does not take down deterministic risk/data.
- Brief cache TTL: 300 seconds. Keyed on profile + risk score + simulation status + snapshot timestamp.

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
- `recent_*_series` fields on `SpaceWeatherSnapshot` carry time-series for anomaly detection; they are excluded from the public API JSON (`exclude=True`).
- Anomaly detection is separate from the risk score — never add z-scores to risk factors.

## Security constraints

- `.env` is in both `.gitignore` and `.bobignore` — never commit it.
- Never print, log, or return `WATSONX_APIKEY`, `NASA_API_KEY`, or any credential value.
- Only refer to variable names, never values.
- `/api/health` deliberately returns only name and version — no config values.
- Granite prompt context contains only scientific/mission data — `_serialize_context()` in `mission_ai.py` must never include credentials.
- Do not trust browser-submitted telemetry in AI routes — backend constructs authoritative context.

## IBM Bob evidence

- `docs/ibm-bob-development.md` — development record for competition submission.
- `docs/risk-methodology.md` — risk algorithm documentation.
- `missionshield-plan.md` — full architecture and implementation plan.
