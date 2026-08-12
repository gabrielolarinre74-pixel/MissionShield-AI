# MissionShield AI

MissionShield AI is a prototype AI-powered space-mission decision-support platform. It
ingests live space-weather observations from NASA DONKI and NOAA SWPC/GOES, computes a
mission-specific risk assessment with a transparent deterministic engine, and uses
IBM Granite (via IBM watsonx.ai) to turn that computed context into human-readable mission
briefs and operator Q&A.

It is a prototype decision-support system. It is **not** an official NASA or NOAA safety
rating, and it is **not** an official go/no-go authority.

---

## The Problem

Space-weather events — geomagnetic storms, solar radiation storms, solar flares, and
Earth-directed coronal mass ejections (CMEs) — can disrupt spacecraft electronics, increase
atmospheric drag, degrade communications, and threaten crew health. The severity of these
hazards depends heavily on the mission context: what is exposed, and where.

Different mission profiles have very different sensitivities:

- An **astronaut EVA** is acutely sensitive to radiation exposure and geomagnetic disturbance.
- A **lunar mission** leaves Earth's protective magnetosphere and depends on situational
  awareness for radiation and CME timing.
- A **LEO satellite** is most affected by geomagnetic activity (drag, charging, uplink disruption).
- A **rocket launch** touches every hazard: range-safety communication, ascent radiation,
  HF radio blackouts, and the possibility of placing crew inside a developing storm.

Raw telemetry alone does not answer the operator's real question: *"What does this mean for
my mission, right now?"* Answering that requires combining authoritative observations with a
mission-aware interpretation of their significance.

## The Solution

MissionShield AI provides a single mission-control-style dashboard that:

1. Fetches current observations from NASA DONKI (flares, CMEs, geomagnetic storms, SEP events)
   and NOAA SWPC/GOES (Kp index, solar wind, IMF, ≥10 MeV proton flux).
2. Computes a deterministic 0–100 risk score per mission profile from four primary hazard
   factors, using official NOAA G/S/R scale thresholds as scientific anchor points and a
   MissionShield prototype weight matrix for mission sensitivity.
3. Detects statistically unusual readings (robust z-score anomaly detection) as situational
   awareness signals, kept separate from the risk score.
4. Explains the risk with full factor-level provenance — observed value, units, source,
   NOAA reference scale, and contribution to the score.
5. Lets operators run what-if simulations (override Kp, solar wind, IMF Bz, CME direction)
   to see how a hypothetical scenario would change the risk posture.
6. Uses IBM Granite to summarize the computed context into a Mission Brief and to answer
   operator questions grounded in the current data.

Everything is deterministic and auditable: the risk score is computed in Python code, and
Granite explains and summarizes that computed context — it does not invent the score.

## Core Capabilities

- **Live NASA DONKI space-weather event ingestion** — solar flares (FLR), CMEs with WSA-ENLIL
  Earth-directed model runs, geomagnetic storms (GST), and SEP event records.
- **Live NOAA SWPC telemetry** — Kp index, solar wind speed, IMF Bz, and NOAA GOES integral
  proton flux (≥10 MeV).
- **Mission-specific deterministic risk intelligence** — transparent, factor-level scoring.
- **Four mission profiles** — Rocket Launch, LEO Satellite, Astronaut EVA, Lunar Mission,
  each with its own sensitivity weighting.
- **Geomagnetic / radiation / flare / CME factor analysis** — per-factor severity, weights,
  and contribution with NOAA reference-scale attribution.
- **Space-weather anomaly detection** — robust z-score (median/MAD) flags for Kp, solar wind,
  IMF Bz, and proton flux, clearly separated from the hazard score.
- **Scenario simulation** — what-if overrides for Kp, solar wind speed, IMF Bz, Earth-directed
  CME, and SEP activity, with simulated values always labeled as such.
- **Mission Brief generation** — IBM Granite summarizes the deterministic risk context.
- **Mission-context AI Q&A** — bounded-history chat grounded in the current snapshot and report.
- **Resilient data layer** — in-memory TTL caching with LIVE / CACHED / STALE freshness
  semantics and partial source-failure tolerance.

## AI Architecture

The system deliberately separates data, computation, and language:

1. **NASA DONKI and NOAA SWPC/GOES** provide the observed space-weather data.
2. **MissionShield's risk engine** performs deterministic, mission-specific risk computation
   in pure Python — no AI, no randomness.
3. The **deterministic risk report is the authoritative output** inside the prototype. Every
   factor carries its source, value, units, and contribution.
4. **IBM Granite** receives that computed context and explains/summarizes it in plain language
   for Mission Briefs and Q&A.
5. **Granite does not invent the risk score** — it never calculates or changes the numeric
   result, and it is explicitly instructed not to invent measurements or claim official
   endorsement.
6. **Simulation inputs are explicitly distinguished** from observed/live data in the report,
   in the UI, and in the AI prompt context.

## Technology

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.3.0, TypeScript, Tailwind CSS v4, lucide-react |
| Backend | FastAPI, Python, pydantic-settings, httpx |
| AI | IBM watsonx.ai, IBM Granite (via the `ibm_watsonx_ai` SDK) |
| Data | NASA DONKI API, NOAA SWPC / NOAA GOES JSON feeds |
| Development | IBM Bob (AI-assisted development environment) |

No database is required — the backend uses an in-memory TTL cache only.

## Project Architecture

```text
NASA DONKI ─────┐
                ├──> FastAPI Data Layer ──> In-memory TTL cache (LIVE/CACHED/STALE)
NOAA SWPC ──────┘               │
                                ▼
                       Mission Risk Engine
                      (deterministic 0–100 score,
                       GEO / RAD / FLARE / CME factors)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
              Next.js UI               IBM Granite (watsonx.ai)
        (dashboard, telemetry,               │
         simulation, events)                 ▼
                                    Mission Brief / Q&A
```

```
backend/   FastAPI application (clients, models, services, AI, routes, tests)
frontend/  Next.js dashboard (components, hooks, typed API client, tests)
docs/      Risk methodology and IBM Bob development record
```

## Mission Profiles

MissionShield supports four mission profiles, each scored with a mission-specific weight
matrix across the four primary hazard factors. The weights are MissionShield prototype design
decisions (documented in full in `docs/risk-methodology.md`) — they are not official NASA or
NOAA operational weights:

| Profile | Emphasis |
|---|---|
| Astronaut EVA | Radiation-dominant; high geomagnetic sensitivity |
| Lunar Mission | Radiation-dominant; elevated CME-watch sensitivity |
| LEO Satellite | Geomagnetic-dominant (drag, charging, uplink) |
| Rocket Launch | Balanced across all four factors |

## Risk Methodology

The risk score is a transparent, deterministic heuristic. Each of the four primary factors —
geomagnetic disturbance (GEO), solar radiation (RAD), solar flare/radio environment (FLARE),
and Earth-directed CME watch (CME) — is normalized to a severity using official NOAA G/S/R
scale thresholds as anchor points, then combined with the mission profile weights.

Key design properties:

- Weights are renormalized among available factors when data is missing — missing data is
  **not** treated as zero risk.
- `data_completeness` and a `confidence` indicator communicate degraded coverage.
- Risk level bands (LOW / MODERATE / HIGH / EXTREME) are MissionShield prototype bands, not
  NOAA categories.

The full methodology — including the weight matrix, NOAA scale mappings, the CME watch
heuristic, anomaly-detection method, and limitations — is documented in
[`docs/risk-methodology.md`](docs/risk-methodology.md).

## Data Sources

- **NASA DONKI** — solar flare (FLR), CME (including WSA-ENLIL Earth-directed model runs),
  geomagnetic storm (GST), and SEP event records.
- **NOAA SWPC** — planetary Kp index, solar wind (L1), IMF magnetic field (L1).
- **NOAA GOES** — integral proton flux (≥10 MeV) from the primary GOES satellite.

Data freshness is tracked per response as **LIVE** (fresh from upstream), **CACHED** (served
within the TTL), or **STALE** (expired cache served because an upstream source failed). When a
source is unavailable, the service degrades gracefully and reports the partial state rather
than fabricating data.

## Reliability and Safety

Verified behaviors in the current implementation:

- **Deterministic risk computation** — the score is a pure function of the snapshot, profile,
  and optional simulation overrides.
- **Missing-data handling** — unavailable factors are marked, weights renormalized, and
  confidence downgraded below 50% data completeness.
- **Data completeness** — reported per response so uncertainty is visible to operators.
- **Caching** — in-memory TTL cache with explicit freshness semantics.
- **Stale-data awareness** — STALE responses are labeled and timestamped in the UI.
- **Graceful AI failure** — if Granite is unavailable, brief/chat degrade gracefully and
  deterministic data remains fully functional.
- **Simulation labeling** — simulated values are always marked with an explicit simulation
  badge and never mixed into live telemetry.

## IBM AI Builders Challenge

MissionShield AI is being developed for the **IBM AI Builders Challenge — August 2026**
(challenge theme: *Advance Space Exploration with AI*).

The project addresses the theme directly: it uses AI (IBM Granite) to make authoritative
space-weather data actionable for space-mission operators, while keeping the decision-critical
risk computation deterministic and auditable — demonstrating a responsible pattern for
applying AI in safety-relevant domains.

## Built with IBM Bob

IBM Bob was used as the primary AI-assisted development environment across the major
implementation phases of this project:

- **Phase 0** — repository analysis, architecture planning, and the implementation plan in
  `missionshield-plan.md`.
- **Phase 1** — backend data foundation (NASA/NOAA clients, caching, FastAPI service).
- **Phase 2** — deterministic risk engine, anomaly detection, and IBM Granite AI integration.
- **Phase 3** — production-quality Next.js frontend and quality fixes.

A detailed development record, including live validation results, is documented in
[`docs/ibm-bob-development.md`](docs/ibm-bob-development.md).

## Local Development

### Prerequisites

- Python 3.14 (a virtual environment is recommended)
- Node.js (for the frontend)
- Optional API keys: `NASA_API_KEY` (defaults to `DEMO_KEY` — rate-limited, fine for local
  development) and IBM watsonx.ai credentials (required for AI features)

### Backend

1. From the repository root, create a `.env` file (see `backend/.env.example` for all
   supported variables). Never commit real values.

```text
NASA_API_KEY=your_nasa_api_key
WATSONX_APIKEY=your_watsonx_api_key
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_PROJECT_ID=your_project_id
WATSONX_MODEL_ID=your_granite_model_id
```

2. Install dependencies:

```bash
pip install -r backend/requirements.txt
pip install ibm_watsonx_ai==1.6.1   # required for the AI layer
```

3. Start the API:

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

The API is served at `http://localhost:8000` (interactive docs at `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard runs at `http://localhost:3000` and expects the backend at
`http://localhost:8000`. Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if the backend
runs elsewhere.

## Tests / Validation

Verified on the `main` branch before publication:

```text
Backend tests:            210 passed
Frontend lint:            passed
Frontend production build: passed
Phase 3 frontend quality tests: passed
```

Run them yourself:

```bash
.venv/Scripts/python.exe -m pytest backend/tests -q
cd frontend && npm run lint && npm run build
```

## Deployment

Production deployment is part of the next delivery phase.

## Disclaimer

MissionShield AI is a prototype decision-support platform. It is **not** an official NASA,
NOAA, launch-provider, spacecraft-operator, or mission-control safety system. Its risk score
is a MissionShield prototype heuristic and does not constitute official go/no-go authority,
a NASA-certified risk assessment, or a NOAA-endorsed operational rating. Nothing in this
repository or in the application's outputs should be used as the sole basis for a real
mission-safety decision.
