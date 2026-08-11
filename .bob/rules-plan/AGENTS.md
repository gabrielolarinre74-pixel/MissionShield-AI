# Project Architecture Rules (Non-Obvious Only)

## Established constraints (Phase 1)

- Single repo, two main sub-projects: `backend/` (FastAPI, Python 3.14) and `frontend/` (Next.js, not yet created).
- No database — the only state store is the in-memory `TTLCache` in `backend/app/services/cache.py`.
- External API access is exclusively in `backend/app/clients/` — never in routes or services directly.
- `SpaceWeatherService` is the only consumer of the clients. Routes call the service only.
- Partial upstream failure is tolerated by design: `SpaceWeatherService._fetch_live()` returns a partial snapshot rather than raising when one source is down.
- NOAA SWPC and NOAA GOES are separate logical sources despite being the same agency. They have separate `DataSource` enum values and separate `SourceStatus` entries in the snapshot.
- All datetimes in domain models are UTC-aware. NOAA naive timestamps are coerced to UTC on ingestion; never stored as naive.
- `DataFreshness.STALE` means the cache TTL has expired but the cached snapshot is being deliberately served because upstream failed. The age must be surfaced to the frontend.
- The risk engine (Phase 2) is a pure function: `compute_risk(snapshot, profile, overrides) -> MissionRiskReport`. No I/O.
- IBM Granite integration (Phase 2) must initialise `Credentials` + `ModelInference` as a FastAPI dependency singleton, not per-request. Auth pattern is identical to `test_watsonx.py`.
- Deployment target: Railway (backend), Vercel (frontend). App must remain portable — no Railway-specific code in `app/`.
- `FRONTEND_ORIGIN` env var controls CORS. In production this must be set to the exact Vercel deployment URL.
