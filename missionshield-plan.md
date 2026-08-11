# MissionShield AI — Implementation Plan

## Overview

Build MissionShield AI: an AI-powered space mission decision-support platform for the IBM AI Builders Challenge (August 2026 theme: Advance Space Exploration with AI).

The system ingests live space-weather data from NASA DONKI and NOAA SWPC, computes mission-specific risk scores, and delivers AI-generated mission briefs and conversational Q&A via IBM watsonx.ai / Granite. A premium mission-control-style Next.js dashboard serves as the user interface.

**Scope boundary:** MVP must be completable and reliably demoable before August 31, 2026.

**Starting point:** A working `test_watsonx.py` script proves the IBM watsonx.ai connection. Everything else is new.

---

## Proposed Repository Structure

```
MissionShield-AI/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory, CORS, startup
│   │   ├── config.py                # Pydantic Settings — loads all env vars
│   │   ├── dependencies.py          # FastAPI dependency injectors (AI client, cache)
│   │   ├── models/                  # Pydantic domain models (shared response shapes)
│   │   │   ├── space_weather.py
│   │   │   ├── mission.py
│   │   │   └── risk.py
│   │   ├── clients/                 # External API clients (pure fetch + normalize)
│   │   │   ├── nasa_donki.py        # NASA DONKI REST client
│   │   │   └── noaa_swpc.py         # NOAA SWPC JSON feed client
│   │   ├── services/                # Business logic (no HTTP, no AI SDK here)
│   │   │   ├── risk_engine.py       # Risk scoring per mission profile
│   │   │   ├── anomaly.py           # Lightweight anomaly/outlier detection
│   │   │   └── cache.py             # In-memory TTL cache wrapper
│   │   ├── ai/
│   │   │   ├── watsonx_client.py    # Wraps Credentials + ModelInference; singleton
│   │   │   ├── prompts.py           # All prompt templates in one place
│   │   │   └── mission_ai.py        # Brief generation + Q&A orchestration
│   │   └── routes/
│   │       ├── space_weather.py     # GET /api/space-weather/*
│   │       ├── mission.py           # GET /api/mission/risk
│   │       ├── ai.py                # POST /api/ai/brief, POST /api/ai/chat
│   │       └── health.py            # GET /api/health
│   ├── tests/
│   │   ├── test_risk_engine.py
│   │   ├── test_clients.py          # Uses recorded fixtures, no live calls
│   │   └── conftest.py
│   ├── requirements.txt
│   └── .env.example                 # Template — never commit real .env
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router pages
│   │   │   ├── page.tsx             # Dashboard (root)
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   │   ├── SpaceWeatherPanel.tsx
│   │   │   │   ├── MissionSelector.tsx
│   │   │   │   ├── RiskScoreCard.tsx
│   │   │   │   ├── RiskFactorList.tsx
│   │   │   │   ├── MissionBrief.tsx
│   │   │   │   ├── EventTimeline.tsx
│   │   │   │   └── SimulationPanel.tsx
│   │   │   ├── chat/
│   │   │   │   └── MissionChat.tsx
│   │   │   └── ui/                  # Generic reusable primitives
│   │   │       ├── StatusBadge.tsx
│   │   │       ├── DataCard.tsx
│   │   │       ├── LoadingState.tsx
│   │   │       ├── ErrorState.tsx
│   │   │       └── SimBadge.tsx     # "SIMULATED DATA" watermark component
│   │   ├── hooks/
│   │   │   ├── useSpaceWeather.ts
│   │   │   ├── useMissionRisk.ts
│   │   │   └── useSimulation.ts
│   │   ├── lib/
│   │   │   ├── api.ts               # Typed fetch wrappers for backend routes
│   │   │   └── formatters.ts        # Date, unit, severity formatters
│   │   └── types/
│   │       └── index.ts             # Shared TypeScript types matching backend models
│   ├── public/
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── next.config.ts
│   └── package.json
├── test_watsonx.py                  # Original connection proof (keep, do not delete)
├── AGENTS.md
├── .bob/
├── .gitignore
├── .bobignore
└── .env.example
```

---

## Sub-Tasks

---

### Sub-Task 1 — Backend Scaffold and Configuration

**Status:** [ ] pending

**Intent:**  
Establish the Python package structure, FastAPI app, and configuration layer. All later sub-tasks depend on this foundation being correct. Secrets must only be accessible server-side from this point forward.

**Expected Outcomes:**
- `backend/` directory exists with `requirements.txt` and a working FastAPI app that starts with `uvicorn`.
- `config.py` loads and validates all required env vars using Pydantic `BaseSettings`.
- `/api/health` returns `{ "status": "ok" }`.
- No secrets are hardcoded or echoed in responses.

**Todo List:**
1. Create `backend/requirements.txt` with: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `httpx`, `ibm_watsonx_ai==1.6.1`, `pandas`, `scikit-learn`, `pytest`, `pytest-asyncio`, `httpx` (test client).
2. Create `backend/app/config.py` using `pydantic_settings.BaseSettings` to load: `WATSONX_APIKEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID`, `WATSONX_MODEL_ID`, `NASA_API_KEY` (optional, defaults to `DEMO_KEY`), `CACHE_TTL_SECONDS` (default 300).
3. Create `backend/app/main.py`: FastAPI app factory with CORS configured to allow the Next.js dev origin (`localhost:3000`) and a production origin env var.
4. Create `backend/app/routes/health.py` with `GET /api/health`.
5. Register the health router in `main.py`.
6. Create `backend/.env.example` listing all supported vars with empty values and comments.
7. Verify the app starts: `uvicorn app.main:app --reload` from `backend/`.

**Relevant Context:**
- Existing `test_watsonx.py` shows the four required `WATSONX_*` var names — reuse exactly.
- Python 3.14 is required.
- `.env` is gitignored at repo root; backend should also read from repo-root `.env` via `python-dotenv` load path, or its own `.env`.

---

### Sub-Task 2 — Domain Models

**Status:** [ ] pending

**Intent:**  
Define Pydantic models for all data flowing through the system. These act as contracts between clients, services, and routes, and mirror the TypeScript types on the frontend.

**Expected Outcomes:**
- `models/space_weather.py`: models for solar flares, CMEs, geomagnetic storms, SEPs, Kp index, solar wind, magnetometer readings.
- `models/mission.py`: `MissionProfile` enum (`ROCKET_LAUNCH`, `LEO_SATELLITE`, `ASTRONAUT_EVA`, `LUNAR_MISSION`), `SimulationOverrides` for what-if parameters.
- `models/risk.py`: `RiskScore` (0–100 float), `RiskLevel` enum (`LOW`, `MODERATE`, `HIGH`, `EXTREME`), `RiskFactor` (label, value, contribution), `MissionRiskReport`.
- All models use `model_config = ConfigDict(frozen=True)` where appropriate.

**Todo List:**
1. Define `SolarFlareEvent`, `CMEEvent`, `GeomagneticStormEvent`, `SEPEvent` in `space_weather.py`.
2. Define `KpReading`, `SolarWindReading`, `MagnetometerReading` as time-series point models.
3. Define `SpaceWeatherSnapshot` aggregating the above into a single state object passed around internally.
4. Define `MissionProfile` enum and `SimulationOverrides` in `mission.py`.
5. Define `RiskFactor`, `RiskScore`, `RiskLevel`, `MissionRiskReport` in `risk.py`.
6. Export matching TypeScript types to `frontend/src/types/index.ts` (manually authored to match).

**Relevant Context:**
- NOAA SWPC provides Kp as a 3-hour planetary index (0–9 scale).
- NASA DONKI returns events with `beginTime`, `peakTime`, `classType` (for flares), `speed` (for CMEs).
- The risk report must include a disclaimer field: `"This is prototype decision-support intelligence, not an official NASA/NOAA safety rating."`.

---

### Sub-Task 3 — External Data Clients

**Status:** [ ] pending

**Intent:**  
Build isolated, testable HTTP clients for NASA DONKI and NOAA SWPC. These are the only modules that make outbound HTTP calls. They normalize raw API responses into the domain models from Sub-Task 2.

**Expected Outcomes:**
- `clients/nasa_donki.py`: fetches FLR (flares), CME, GST (geomagnetic storms), SEP events for a configurable lookback window (default: 7 days).
- `clients/noaa_swpc.py`: fetches current Kp index, solar wind speed/density/Bz, and magnetometer data from the NOAA JSON feeds.
- Both clients use `httpx.AsyncClient` with a configurable timeout.
- Both clients return typed domain models.
- Both clients raise a custom `DataSourceUnavailableError` on failure rather than propagating raw HTTP errors to routes.
- Fixture-based tests in `tests/test_clients.py` cover the normalization logic without live calls.

**Todo List:**
1. Implement `NASADONKIClient` with methods: `get_flares()`, `get_cmes()`, `get_geomagnetic_storms()`, `get_seps()`. Use `NASA_API_KEY` from config.
2. Implement `NOAASWPCClient` with methods: `get_kp_index()`, `get_solar_wind()`, `get_magnetometer()`. Use known public NOAA JSON endpoints (no key required).
3. Define `DataSourceUnavailableError` in a shared `exceptions.py`.
4. Write `tests/test_clients.py` using saved JSON fixtures for both clients.
5. Document the exact NOAA endpoint URLs used in comments (they are not obvious).

**Relevant Context:**
- NASA DONKI base URL: `https://api.nasa.gov/DONKI/`
- NOAA SWPC Kp JSON: `https://services.swpc.noaa.gov/json/planetary_k_index_1m.json`
- NOAA SWPC solar wind: `https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json`
- NOAA SWPC mag: `https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json`
- NOAA feeds require no API key but may have CORS restrictions — backend-only access required.

---

### Sub-Task 4 — Caching Layer

**Status:** [ ] pending

**Intent:**  
External API calls are slow and rate-limited. A TTL cache prevents redundant calls and provides resilience when upstream sources are temporarily unavailable. This also enables the What-If mode to work without live data.

**Expected Outcomes:**
- `services/cache.py`: a simple async-safe in-memory TTL cache keyed by data type.
- Cached `SpaceWeatherSnapshot` is served stale with a `stale: true` flag and `last_updated` timestamp when upstream fails.
- Cache TTL is configurable via `CACHE_TTL_SECONDS` env var (default 300 s / 5 min).
- No external cache dependency (Redis is out of scope for MVP — avoid overengineering).

**Todo List:**
1. Implement `TTLCache` class in `services/cache.py` using a dict + `asyncio.Lock` + timestamp tracking.
2. Wrap `NASADONKIClient` and `NOAASWPCClient` calls in a `SpaceWeatherService` that checks the cache first.
3. `SpaceWeatherService.get_snapshot()` returns `SpaceWeatherSnapshot` and sets `data_freshness` metadata (`live`, `cached`, `stale`).
4. On complete upstream failure with no cache entry, return a clear error response (not fake data).

**Relevant Context:**
- The `SpaceWeatherSnapshot` from Sub-Task 2 must carry `fetched_at: datetime` and `freshness: Literal["live","cached","stale"]`.
- This service is injected via FastAPI `Depends`.

---

### Sub-Task 5 — Risk Engine

**Status:** [ ] pending

**Intent:**  
Compute a numerical mission risk score from a `SpaceWeatherSnapshot` and a selected `MissionProfile`. This is the core AI-adjacent intelligence component. It must be transparent: the output must show which factors contributed to the score and by how much.

**Expected Outcomes:**
- `services/risk_engine.py`: pure function (no I/O) `compute_risk(snapshot, profile, overrides?) -> MissionRiskReport`.
- Four mission profiles each have different factor weights (e.g., EVA is highly sensitive to Kp and SEP; rocket launch is sensitive to solar wind speed and CME arrival time).
- Output includes: overall score (0–100), risk level, list of `RiskFactor` objects each with a human-readable label and numeric contribution.
- Simulation overrides (from What-If mode) replace live values before scoring — the report must flag `is_simulated: true`.
- Unit tests cover all four profiles and boundary conditions.

**Expected Risk Factor Inputs:**

| Factor | Source | Notes |
|---|---|---|
| Kp index (current) | NOAA SWPC | `estimated_kp` float from planetary_k_index_1m.json |
| Solar wind speed | NOAA SWPC | `proton_speed` km/s from rtsw_wind_1m.json |
| Solar wind Bz (southward) | NOAA SWPC | `bz_gsm` nT from rtsw_mag_1m.json; negative = southward |
| Active X/M-class flares | NASA DONKI FLR | `classType` field; only X/M classes contribute meaningfully |
| CME Earth-directed + WSA-ENLIL model | NASA DONKI CME | Use `enlilList[].isEarthGB` and `estimatedShockArrivalTime`; do NOT invent a "probability" value |
| SEP event (qualitative) | NASA DONKI SEP | DONKI SEP is an event record, not a flux number; treat presence/recency as a qualitative risk flag |
| Proton flux (numerical) | NOAA GOES integral-protons-6-hour.json | `flux` pfu at `>=10 MeV` channel from GOES primary satellite |
| Active geomagnetic storm level | NASA DONKI GST | `allKpIndex[].kpIndex` peak observed Kp; linked events show causal chain |

**Profile Sensitivity Notes (weights guide, not final values):**

| Factor | Rocket Launch | LEO Satellite | EVA | Lunar |
|---|---|---|---|---|
| Kp index | Medium | High | Very High | Medium |
| Solar wind speed | High | Medium | High | High |
| Bz southward | Medium | High | Very High | High |
| X/M flares | High | High | Very High | Very High |
| CME arrival | Very High | High | Very High | Very High |
| SEP flux | Medium | Medium | Very High | Very High |
| Geomagnetic storm | Medium | High | Very High | Medium |

**Todo List:**
1. Define factor extraction functions: `extract_kp_score()`, `extract_solar_wind_score()`, `extract_flare_score()`, `extract_cme_score()`, `extract_sep_score()`, `extract_storm_score()` — each returns a 0–1 normalized subscale value.
2. Define `PROFILE_WEIGHTS` dict mapping `MissionProfile` to factor weight vectors.
3. Implement `compute_risk()` as a weighted sum → normalize to 0–100 → map to `RiskLevel`.
4. Implement `apply_overrides()` to inject simulation values into the snapshot before scoring.
5. Write `tests/test_risk_engine.py` with parametrized tests for all profiles and edge cases.

**Relevant Context:**
- This module must be fully pure (no HTTP, no AI). It is the most testable component.
- The disclaimer string must be attached to every `MissionRiskReport`.

---

### Sub-Task 6 — Anomaly Detection

**Status:** [ ] pending

**Intent:**  
Provide a lightweight signal that current space-weather readings are statistically unusual relative to recent history. This adds credibility to the risk score without requiring a complex ML pipeline.

**Expected Outcomes:**
- `services/anomaly.py`: given a short time-series of Kp or solar wind readings, flags anomalous points using a simple method (Z-score or IQR over the last 24 hours of NOAA data).
- Anomaly flags are attached to the `SpaceWeatherSnapshot` and surfaced in the frontend as visual indicators.
- scikit-learn `IsolationForest` may be used as an optional enhancement but is not required for MVP if it adds fragility.

**Todo List:**
1. Implement `detect_anomalies(readings: list[KpReading]) -> list[AnomalyFlag]` using rolling Z-score (simple, no sklearn dependency for MVP).
2. Define `AnomalyFlag` model: `{ timestamp, parameter, value, z_score, is_anomalous }`.
3. Attach anomaly results to the `SpaceWeatherSnapshot` as `anomalies: list[AnomalyFlag]`.
4. Add a note in the implementation that IsolationForest can replace Z-score as a stretch enhancement.

**Relevant Context:**
- Keep it simple — Z-score over ~24 data points is sufficient for a demo and easier to explain to judges.
- The .venv already has `scikit-learn` available if needed.

---

### Sub-Task 7 — AI Service (Granite Integration)

**Status:** [ ] pending

**Intent:**  
Wrap the IBM watsonx.ai / Granite connection into a proper service layer. Generate structured Mission Briefs and answer operator questions in the context of current space-weather data. Secrets must never leave the backend.

**Expected Outcomes:**
- `ai/watsonx_client.py`: initializes `Credentials` + `ModelInference` once (singleton via FastAPI dependency) using the four `WATSONX_*` env vars.
- `ai/prompts.py`: all prompt templates as named constants — one for brief generation, one for Q&A.
- `ai/mission_ai.py`: `generate_brief(snapshot, risk_report, profile) -> str` and `answer_question(question, snapshot, risk_report) -> str`.
- The Q&A method includes the current snapshot and risk report in context so Granite answers are grounded in live data.
- Responses are streamed where the Granite model supports it; otherwise returned as a complete string.
- On AI service failure, routes return a graceful error — not a 500 crash.

**Todo List:**
1. Implement `watsonx_client.py` mirroring `test_watsonx.py` auth pattern, exposed as a `get_ai_client()` FastAPI dependency.
2. Write `BRIEF_PROMPT_TEMPLATE` in `prompts.py`: system prompt establishes Granite as a mission-safety analyst; user turn injects snapshot summary, risk factors, and profile.
3. Write `QA_PROMPT_TEMPLATE`: system prompt establishes context; user turn is the operator question with snapshot data injected.
4. Implement `generate_brief()` calling `model.chat()` with the brief prompt.
5. Implement `answer_question()` with chat history support (pass prior turns as messages list).
6. Add a `max_tokens` cap to prevent runaway responses.
7. Validate: AI responses never echo back raw env vars or credentials.

**Relevant Context:**
- `test_watsonx.py` response shape: `response["choices"][0]["message"]["content"]`.
- `ModelInference.chat()` is the synchronous REST path.
- The `ibm_watsonx_ai` SDK is already installed in `.venv`.
- Granite should be framed as a "mission AI assistant" in prompts, not a generic chatbot.

---

### Sub-Task 8 — API Routes

**Status:** [ ] pending

**Intent:**  
Expose backend services through clean, typed FastAPI routes. All secret-touching code (watsonx, NASA key) lives here on the server — nothing sensitive is forwarded to the browser.

**Expected Outcomes:**
- `GET /api/health` — liveness probe.
- `GET /api/space-weather/snapshot` — returns current `SpaceWeatherSnapshot` (live or cached).
- `GET /api/space-weather/events` — returns recent DONKI events list.
- `POST /api/mission/risk` — body: `{ profile, simulation_overrides? }` — returns `MissionRiskReport`.
- `POST /api/ai/brief` — body: `{ profile, snapshot_id? }` — returns AI-generated mission brief string.
- `POST /api/ai/chat` — body: `{ message, history? }` — returns Granite answer.
- All routes return structured error responses (not raw exceptions).
- OpenAPI docs auto-generated at `/docs`.

**Todo List:**
1. Implement `routes/space_weather.py` with snapshot and events endpoints.
2. Implement `routes/mission.py` with risk endpoint.
3. Implement `routes/ai.py` with brief and chat endpoints.
4. Register all routers in `main.py` under `/api` prefix.
5. Add `X-Data-Source` and `X-Freshness` response headers to space-weather endpoints so the frontend can display source attribution.
6. Add rate limiting note (out of scope for MVP but document as stretch).

**Relevant Context:**
- CORS must allow `http://localhost:3000` in development.
- Simulation overrides arriving via the risk endpoint must set `is_simulated: true` on the returned report.

---

### Sub-Task 9 — Frontend Scaffold and Design System

**Status:** [ ] pending

**Intent:**
Initialize the Next.js + TypeScript + Tailwind project and establish the complete design system foundation before any feature components are built. All subsequent frontend sub-tasks must be built on top of this foundation without deviation. The design must feel like premium professional software — the restraint and clarity of serious engineering tools, not a generic AI dashboard.

**Design Quality Gate — must be fully defined in this sub-task before components begin:**

- Design tokens (all CSS custom properties in `globals.css`)
- Typography scale and typeface assignment
- Spacing scale
- Surface hierarchy (4 levels)
- Semantic color set
- Layout grid and breakpoints
- Navigation structure
- Component state definitions (loading skeleton, error, empty, stale)

**Expected Outcomes:**
- `frontend/` bootstrapped with Next.js App Router, TypeScript, Tailwind CSS.
- IBM Plex Sans (UI text) and IBM Plex Mono (telemetry values) loaded via `next/font/google`.
- All design tokens defined as Tailwind custom tokens and CSS variables in `globals.css`.
- `lib/api.ts`: typed async functions for each backend route, all using `NEXT_PUBLIC_API_URL` env var.
- `types/index.ts` mirroring backend Pydantic models.
- Recharts installed for analytical charts.
- `app/layout.tsx` renders the persistent chrome: top status bar + left nav rail + main content area + collapsible right panel slot.
- The root page opens directly into the product — no landing page, no hero, no "Get Started" CTA.
- A design token reference comment block in `tailwind.config.ts` documents every intentional token decision.

**Design System Specification:**

**Typography:**
- UI typeface: IBM Plex Sans (weights: 400, 500, 600) — all labels, body, navigation, headings
- Telemetry typeface: IBM Plex Mono (weight: 400, 500) — risk score numbers, Kp values, solar wind readings, timestamps, technical identifiers
- Do not use monospace for body text, descriptions, or AI output
- Type scale: `text-xs` (11px labels), `text-sm` (13px secondary), `text-base` (15px body), `text-lg` (17px section heads), `text-2xl` (24px module titles), `text-4xl` (36px risk score display)

**Color Tokens (defined in `tailwind.config.ts` and as CSS vars):**

| Token | Value | Usage |
|---|---|---|
| `surface-base` | `#0B0D10` | Page background |
| `surface-secondary` | `#111419` | Nav rail, top bar, panel backgrounds |
| `surface-elevated` | `#171A20` | Cards, data modules |
| `surface-overlay` | `#1E2330` | Hover states, dropdowns |
| `text-primary` | `#F4F6F8` | Primary readable text |
| `text-secondary` | `#9AA4B2` | Labels, metadata, secondary info |
| `text-muted` | `#5A6578` | Disabled, placeholders, divider text |
| `accent` | `#6EA8FE` | Interactive elements, focus rings, links |
| `border-subtle` | `rgba(255,255,255,0.08)` | All borders and dividers |
| `border-focus` | `rgba(110,168,254,0.5)` | Focus rings |
| `risk-nominal` | `#22C55E` | LOW risk, nominal status |
| `risk-caution` | `#F59E0B` | MODERATE risk, caution |
| `risk-high` | `#F97316` | HIGH risk |
| `risk-critical` | `#EF4444` | EXTREME risk, critical alerts |
| `sim-amber` | `#D97706` | Simulation mode indicator only |
| `data-live` | `#22C55E` | Live data freshness dot |
| `data-cached` | `#9AA4B2` | Cached data freshness |
| `data-stale` | `#F97316` | Stale data warning |

Semantic colors must only be used for their assigned meaning. No decorative use.

**Surface Hierarchy:**
- Level 0 (`surface-base`): page background
- Level 1 (`surface-secondary`): persistent chrome (nav rail, top bar)
- Level 2 (`surface-elevated`): data modules and panels
- Level 3 (`surface-overlay`): popovers, dropdowns, tooltips

**Spacing Scale:** use Tailwind default 4px base unit. Section gaps: `gap-6` (24px). Module internal padding: `p-5` (20px). Compact rows: `py-2 px-3`.

**Corner Radii:** `rounded-xl` (12px) for modules. `rounded-lg` (10px) for inputs and smaller containers. `rounded-md` (8px) for badges and tags. No `rounded-full` on rectangular containers.

**Borders:** 1px solid `border-subtle` on all module edges. No box-shadow on normal modules. Subtle box-shadow only for overlays.

**Motion:** transitions at `duration-150` to `duration-200`. `ease-out` easing. `prefers-reduced-motion` respected via Tailwind `motion-reduce:` prefix. No decorative animations. No floating or pulsing elements except a single 2px live-status dot with a subtle pulse only when data freshness is `live`.

**Layout Structure:**
```
┌─────────────────────────────────────────────────────────┐
│  Top Status Bar (h-10, surface-secondary)               │
│  MissionShield | data freshness | source status | UTC   │
├──────────┬──────────────────────────────────┬───────────┤
│ Nav Rail │   Central Analysis Workspace     │ Mission AI│
│  (w-14   │   (flex-1, scrollable)           │  Panel    │
│  icons + │                                  │ (w-80,    │
│  labels) │                                  │ collapse) │
└──────────┴──────────────────────────────────┴───────────┘
```

**Left Navigation Rail:** icon + short label for each section. Active state: `accent` left border + slightly elevated background. Sections: Overview, Space Weather, Risk Analysis, Simulation, Events. For MVP all sections are anchors within the single page, not separate routes.

**Top Status Bar:** left — MissionShield wordmark (text, not logo image). Center — current data freshness dot + label. Right — NOAA status indicator, NASA status indicator, last sync UTC timestamp. No decorative elements.

**Component State Rules:**
- Loading: skeleton shimmer using `animate-pulse` on placeholder shapes that match the real content geometry — not a spinner in the center of the module
- Error: icon + short description + retry action — no full-screen error pages
- Empty: neutral message, no illustrative art
- Stale: amber timestamp label + `data-stale` dot — module remains visible and usable
- AI generating: fading text placeholder with a single subtle animated bar, not a spinning wheel

**What to avoid (enforced at this stage):**
- No gradients in backgrounds (except the most subtle 2-stop gradient used purposefully, e.g., on the risk score)
- No glassmorphism (backdrop-blur on panels)
- No glow or neon effects on cards
- No rounded-full on section containers
- No hero imagery, illustrations, or decorative icons
- No oversized marketing-style headlines

**Todo List:**
1. Run `npx create-next-app@latest frontend --typescript --tailwind --app` with `src/` directory structure.
2. Install IBM Plex Sans and IBM Plex Mono via `next/font/google` in `layout.tsx`.
3. Define all color tokens listed above in `tailwind.config.ts` under `theme.extend.colors`.
4. Define all tokens as CSS custom properties in `globals.css` for use in non-Tailwind contexts.
5. Build the persistent app chrome in `app/layout.tsx`: top status bar, left nav rail, main content slot, right panel slot.
6. Implement `TopStatusBar` component: wordmark, data freshness dot, source status indicators, UTC timestamp.
7. Implement `NavRail` component: icon + label navigation items, active state styling.
8. Install Recharts (`npm install recharts`).
9. Add `NEXT_PUBLIC_API_URL` env var (`http://localhost:8000` default); document in `frontend/.env.local.example`.
10. Implement `lib/api.ts` with typed fetch wrappers for all backend routes.
11. Author `types/index.ts` mirroring all backend Pydantic models.
12. Create `components/ui/` primitives: `Skeleton`, `ErrorState`, `EmptyState`, `StatusDot`, `SimulationBanner`, `Tooltip`.
13. Confirm the root page opens directly to the dashboard — no landing page.

**Relevant Context:**
- Vercel deployment target — no custom server, standard Next.js static patterns.
- The opening screen is the product itself. Judges open it and are immediately inside the mission control interface.
- IBM Plex Sans and Mono are IBM's own typefaces — appropriate for an IBM AI Builders submission and carry inherent technical credibility.

---

### Sub-Task 10 — Core Dashboard Layout and Mission Readiness Module

**Status:** [ ] pending

**Intent:**
Build the central analysis workspace. The information hierarchy must be deliberate: Mission Readiness is the primary visual object. Supporting telemetry exists to explain the risk, not to decorate the screen. Typography and spacing establish hierarchy before containers are added.

**Information Hierarchy on the Main Screen:**
1. Mission selector (which mission are we evaluating?)
2. Mission Readiness / Risk Score (primary decision object — largest, clearest module)
3. Primary risk explanation and top contributing factor
4. Risk factor breakdown (why does this score exist?)
5. Supporting telemetry (Kp, solar wind, magnetometer)
6. Event timeline (recent DONKI events)

**Expected Outcomes:**
- `MissionSelector`: compact tab-style selector for the four profiles. Not a dropdown. Labels are short: "Rocket Launch", "LEO Satellite", "Astronaut EVA", "Lunar Mission". Active tab uses `accent` underline, not a filled pill.
- `ReadinessModule`: the visual centerpiece. Large IBM Plex Mono risk score number (e.g. "74"), risk level label below, thin color-coded left border in the risk semantic color. Primary risk explanation in `text-secondary` below. Most critical contributing factor callout. Data freshness inline. "Regenerate Brief" link. Prototype disclaimer in `text-muted text-xs` at the bottom.
- `RiskFactorBreakdown`: horizontal bar chart (Recharts) showing factor contributions. Bars use a single `accent` color (not rainbow). Grid lines are subtle. Axis labels use IBM Plex Mono. No legend (labels are on the axis). Chart height is proportional — not oversized.
- `TelemetryRow`: a horizontal strip of key readings (Kp index, solar wind speed, Bz, particle flux). Each reading is a compact `label / value / unit` triplet. Values in IBM Plex Mono. No cards-within-cards — these sit on a single elevated surface with dividers between them.
- `EventTimeline`: scrollable list of recent DONKI events. Each row: event type tag (4-letter abbreviated label: FLARE, CME, GST, SEP), timestamp (IBM Plex Mono UTC), short description. No decorative icons — use text labels only.
- `StatusDot`: 2px circle in `data-live`/`data-cached`/`data-stale` color, used inline next to freshness timestamps. The live dot has a subtle pulse `animate-ping` at 50% opacity — no other animations.
- All modules have intentionally designed loading skeletons that match the real content geometry.
- All modules have error states with a short message and retry action.

**Todo List:**
1. Build `MissionSelector` as tab-style component with `accent` active underline.
2. Build `ReadinessModule`: risk score display, risk level label, left border color, primary factor callout, freshness, disclaimer.
3. Build `RiskFactorBreakdown` using Recharts `BarChart` with single-color bars, minimal grid, IBM Plex Mono axes.
4. Build `TelemetryRow` as a divider-separated horizontal strip of value triplets on `surface-elevated`.
5. Build `EventTimeline` with text-label event types and IBM Plex Mono timestamps.
6. Build `StatusDot` with conditional `animate-ping` only for live state, respecting `prefers-reduced-motion`.
7. Build loading skeletons for `ReadinessModule`, `TelemetryRow`, `EventTimeline`.
8. Build `ErrorState` variants for each module.
9. Compose all into `app/page.tsx` central workspace using the layout grid from Sub-Task 9.
10. Implement `useSpaceWeather` hook (5-minute polling via `setInterval`).
11. Implement `useMissionRisk` hook (re-fetches on profile change or fresh snapshot).
12. Confirm: no gauge charts, no large circular displays, no oversized decorative numerics.

**Relevant Context:**
- Risk level color mapping: LOW → `risk-nominal`, MODERATE → `risk-caution`, HIGH → `risk-high`, EXTREME → `risk-critical`.
- Timestamps: always UTC, with a `text-muted` relative label "(3 min ago)" beside the absolute time.
- Source attribution line: `"Data: NASA DONKI · NOAA SWPC"` in `text-muted text-xs` below the TelemetryRow.
- The ReadinessModule left border should be `4px solid <risk-color>` — the only use of semantic color as a layout device.

---

### Sub-Task 11 — Mission AI Panel

**Status:** [ ] pending

**Intent:**
Integrate the IBM Granite AI features as a contextual right-side assistant panel — not a standalone chatbot. The panel understands the selected mission, the current risk score, and the live snapshot. It is collapsible so it does not dominate the workspace. IBM Granite attribution is present but not obtrusive.

**Expected Outcomes:**
- `MissionAIPanel`: collapsible right-side panel (`w-80` when open). Two sections within the panel:
  1. **Mission Brief** — auto-generated on profile/snapshot change. Shows Granite output in `text-sm text-primary`. A "Regenerate" text button (not a large CTA). A subtle `text-muted text-xs` label: "Generated by IBM Granite · watsonx.ai". Shows a generating state using a 3-line text skeleton.
  2. **Mission AI Chat** — question input pinned at the bottom of the panel. Scrollable message history above. Starter questions shown as subtle `text-secondary` chips when history is empty: "Why did risk increase?", "What should I monitor?", "Summarize current conditions.", "Which factor matters most?". Each assistant message has the same `text-muted text-xs` attribution line. No avatar icons, no user/AI bubbles with heavy background fills — use left-indentation and color to distinguish speaker.
- Panel open/close toggle button on the right edge of the top status bar.
- When simulation mode is active: AI Chat input is disabled with a `text-muted` label "Unavailable in simulation mode". Brief shows last real-data generation.
- On AI error: inline error message in `risk-high` color, `text-sm`, with retry.

**Todo List:**
1. Build `MissionAIPanel` with collapse/expand state, toggled from the top status bar.
2. Build `MissionBrief` section: auto-generate on mount and on profile/snapshot change, generating skeleton, Regenerate text button, attribution line.
3. Build `MissionChat` section: starter question chips, message history, input field pinned at bottom, attribution on assistant messages.
4. Implement `useMissionAI` hook: manages brief loading/error state, chat history, sends history array to `POST /api/ai/chat`.
5. Apply simulation mode guard: disable chat input, preserve last brief.
6. Implement `prefers-reduced-motion`-safe generating animation for brief skeleton.
7. Confirm IBM Granite and watsonx.ai attribution is visible in the rendered panel (competition requirement).

**Relevant Context:**
- `ModelInference.chat()` response shape: `response["choices"][0]["message"]["content"]` (from Sub-Task 7).
- The panel collapses fully — the workspace expands to fill the right area when it is closed.
- Do not add IBM or watsonx logos to the UI — text attribution is sufficient and less cluttered.

---

### Sub-Task 12 — Simulation / What-If Mode

**Status:** [ ] pending

**Intent:**
Allow users to override space-weather parameters and see the risk score respond in real time. Simulation mode must look intentionally different — but remain within the same design system rather than becoming a separate visual theme. The separation between live readings and simulated overrides must be unambiguous at all times.

**Expected Outcomes:**
- `SimulationPanel`: accessible from the "Simulation" section of the left nav rail. Contains sliders and toggles for: Kp index (0–9), solar wind speed (300–1000 km/s), Bz southward (-40 to +5 nT), CME active (toggle), SEP active (toggle). Each control shows its current live value as a reference beside the simulation input so the operator can see the delta.
- When simulation mode is active:
  - A persistent amber `SIMULATION` indicator replaces the `StatusDot` in the top status bar (not a full banner).
  - The `ReadinessModule` shows an amber `4px` left border (replacing the risk-color border) and a small `SIM` label beside the score.
  - Live space-weather telemetry readings remain visible and unmodified. Only the risk score and factor breakdown reflect the simulation.
  - A short `text-muted text-xs` line beneath the risk score: "Risk computed from simulated inputs — live readings unaffected."
  - The `MissionAIPanel` chat input is disabled with a tooltip: "Mission AI is unavailable while simulation is active."
- Exiting simulation mode immediately restores live risk computation with no page reload.
- Simulation state does not persist across page reloads.

**Todo List:**
1. Build `SimulationPanel` with sliders (Radix UI Slider or native `<input type="range">`) and toggles, showing live value reference for each parameter.
2. Implement `useSimulation` hook: manages active/inactive state, current override values, reset action.
3. Wire simulation overrides into `useMissionRisk` — when active, include `simulation_overrides` in `POST /api/mission/risk` body.
4. Implement the amber `SIMULATION` top-bar status indicator.
5. Apply amber left-border and `SIM` label to `ReadinessModule` when `is_simulated: true` on the risk report.
6. Apply simulation guard to `MissionAIPanel` chat.
7. Confirm live telemetry readings (`TelemetryRow`, `EventTimeline`) are never modified by simulation state.

**Relevant Context:**
- Backend `risk_engine.py` returns `is_simulated: true` when overrides are present (Sub-Task 5).
- Radix UI Slider is preferred over a custom-built range component — install `@radix-ui/react-slider`.
- The simulation indicator is amber (`sim-amber` token) — distinct from all four risk-level colors.

---

### Sub-Task 13 — Deployment

**Status:** [ ] pending

**Intent:**
Publish a publicly reachable production build before final submission. A live URL is required for the judged submission — local-only demos are not sufficient. This is MVP, not stretch.

**Expected Outcomes:**
- Frontend deployed on Vercel, accessible via a public HTTPS URL.
- Backend deployed on Railway or Render (both support Python/uvicorn with zero-ops configuration).
- All environment variables configured in hosting platform dashboards — no `.env` files committed.
- CORS updated in `main.py` to allow the production Vercel domain.
- Health check (`GET /api/health`) returns `{ "status": "ok" }` on the live backend URL.
- `NEXT_PUBLIC_API_URL` on Vercel points to the live backend URL.
- `README.md` at the repo root includes the live demo URL and a brief description for judges.

**Todo List:**
1. Create `backend/Procfile` or `railway.toml` / `render.yaml` defining the start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. Verify the chosen host supports Python 3.14 before deploying.
3. Deploy backend; set all `WATSONX_*`, `NASA_API_KEY`, `CACHE_TTL_SECONDS`, and `CORS_ORIGINS` as secret environment variables in the platform dashboard.
4. Deploy frontend to Vercel; set `NEXT_PUBLIC_API_URL` to the live backend URL.
5. Update `CORS_ORIGINS` in `backend/app/main.py` to include the production Vercel domain (read from env var).
6. Smoke-test the live deployment: health check, snapshot, risk, AI brief, AI chat.
7. Write `README.md`: project description, live demo URL, IBM AI Builders Challenge context, local run instructions.

**Relevant Context:**
- Railway and Render both offer free tiers sufficient for a hackathon demo.
- Python 3.14 support must be confirmed on the host before starting deployment.
- All secrets enter via the hosting platform's environment variable dashboard — never via committed files.

---

### Sub-Task 14 — AGENTS.md and Documentation Update

**Status:** [ ] pending

**Intent:**
Update `AGENTS.md` and mode-specific files to reflect the full-stack architecture so future AI agents have correct guidance.

**Expected Outcomes:**
- `AGENTS.md` updated with: how to run backend, how to run frontend, all env vars, folder structure.
- `.bob/rules-agent/AGENTS.md` updated with FastAPI patterns, risk engine conventions.
- `.bob/rules-plan/AGENTS.md` updated with architectural constraints discovered during build.
- `backend/.env.example` and `frontend/.env.local.example` are complete.

**Todo List:**
1. Update root `AGENTS.md` with new run commands, env vars, and folder structure.
2. Update `.bob/rules-agent/AGENTS.md` with FastAPI patterns, risk engine conventions.
3. Update `.bob/rules-plan/AGENTS.md` with architectural constraints discovered during build.
4. Verify `backend/.env.example` and `frontend/.env.local.example` are complete and all `.env` files are gitignored.

---

## Architecture Overview

### Data Flow

```
NOAA SWPC JSON feeds ──────┐
                           ├──► NOAASWPCClient ──► SpaceWeatherService ──► TTLCache
NASA DONKI REST API ───────┘    NASADONKIClient ──►                              │
                                                                                 │
Browser ──► Next.js ──► lib/api.ts ──► FastAPI routes ──► SpaceWeatherService ◄──┘
                                              │
                                              ├──► RiskEngine ──► MissionRiskReport
                                              │
                                              └──► WatsonxClient ──► Granite ──► Brief / Chat
```

### Security Approach

- All secrets (`WATSONX_*`, `NASA_API_KEY`) are backend-only; never sent to the browser.
- CORS restricts origins to the known frontend URL (`FRONTEND_ORIGIN` env var).
- The frontend uses only `NEXT_PUBLIC_API_URL` — the backend URL — no AI or data API keys.
- `.env` is in both `.gitignore` and `.bobignore`.
- `.env.example` files are committed (no values, safe defaults only).

### Deployment Target

- **Preferred:** Railway (Python 3.14 support, zero-ops configuration, `$PORT` env var)
- **Fallback:** Render
- FastAPI application must remain portable — no Railway-specific application logic.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- A live public deployment is an internal quality requirement for a polished submission, not an explicit competition rule.

### Caching and Failure Strategy

| Condition | Behavior |
|---|---|
| Fresh data available | Serve live; label `LIVE` |
| Cache hit, upstream down | Serve cached; label `CACHED`; show `last_updated` |
| Cache expired, upstream down | Serve stale; label `STALE`; show age warning |
| No cache, upstream down | Return structured error; frontend shows `ErrorState` |
| Simulation active | Use cached/live snapshot for display; override params for risk only |

### Testing Approach

- **Backend:** pytest with fixture-based client tests (no live API calls). Risk engine unit tests are fully parametrized. AI service tested with mocked `ModelInference`.
- **Frontend:** No test framework required for MVP (time risk). Manual demo testing.
- **Integration:** Manual end-to-end before submission.

---

## MVP vs Stretch Features

### MVP (must ship by August 31)
- Design system foundation (tokens, typography, layout chrome)
- Dashboard with live space-weather data (Kp, solar wind, DONKI events)
- Four mission profiles with risk scoring
- Mission Readiness module as the primary visual centrepiece
- Risk factor breakdown chart
- AI Mission Brief (IBM Granite via watsonx.ai)
- Mission AI collapsible panel with chat (IBM Granite)
- What-If Simulation mode with amber indicator
- Live / Cached / Stale data labeling throughout
- Intentionally designed loading, error, empty, and stale states
- Source attribution (NASA DONKI, NOAA SWPC) and data freshness timestamps
- Public deployment — Vercel (frontend) + Railway or Render (backend)
- README.md with live demo URL

### Stretch Features (only if MVP is complete and stable)
- Historical trend charts (Kp over 7 days)
- IsolationForest anomaly detection replacing Z-score
- Streaming AI responses via SSE
- Multiple concurrent mission profile comparison
- Rate limiting on AI endpoints
- Accessibility audit (ARIA labels, keyboard navigation)

---

## Major Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| NOAA/NASA APIs return unexpected schema | Medium | High | Validate with fixture tests before building risk engine; add defensive normalization |
| IBM Granite rate limits or latency | Medium | High | Cache last-generated brief; add timeout + graceful error |
| Python 3.14 package incompatibility | Low | High | Test all deps in venv before writing backend code |
| What-If mode confuses judges as "fake data" | Medium | Medium | Persistent SIM banner; never mix sim values into live display |
| Scope creep eating demo time | High | High | Strictly follow MVP list; stretch features only after full demo works |
| CORS misconfiguration breaks frontend-backend in demo | Medium | High | Test CORS with actual browser early in Sub-Task 9 |
| AI responses are slow (>5 s) and feel broken in demo | Medium | Medium | Add visible spinner; pregenerate brief on profile change |

---

## Development Phase Order

1. **Phase 1 — Backend foundation:** Sub-Tasks 1, 2, 3, 4 (scaffold, models, clients, cache)
2. **Phase 2 — Intelligence layer:** Sub-Tasks 5, 6, 7 (risk engine, anomaly, AI service)
3. **Phase 3 — API surface:** Sub-Task 8 (routes — connects phases 1+2 to the network)
4. **Phase 4 — Frontend:** Sub-Tasks 9, 10, 11, 12 (design system → dashboard → AI panel → simulation)
5. **Phase 5 — Deployment:** Sub-Task 13 (live public URLs, smoke-test)
6. **Phase 6 — Docs and polish:** Sub-Task 14 + demo rehearsal + bug fixes

---

## Simplification Recommendations

1. **Skip Redis/external cache.** In-memory TTL cache is sufficient for a demo and removes an ops dependency.
2. **Skip IsolationForest for MVP.** Z-score anomaly detection is explainable to judges and requires no model training.
3. **Skip streaming for MVP.** Synchronous Granite responses with a spinner are reliable; streaming adds SDK complexity.
4. **Skip historical charts for MVP.** The EventTimeline list delivers the same informational value with far less code.
5. **Single-page app.** One dashboard page is sufficient — avoid routing complexity.
6. **No auth/login.** Out of scope entirely for this submission.
7. **No database.** TTL cache in memory is the only state store needed.
