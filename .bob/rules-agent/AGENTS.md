# Project Coding Rules (Non-Obvious Only)

## Backend (FastAPI / Python)

- Run uvicorn from `backend/` directory so `app` package is importable: `uvicorn app.main:app`.
- `config.py` auto-discovers `.env` by walking up two parent directories from `backend/app/` — no need to copy `.env` into `backend/`.
- New required env vars go into `backend/app/config.py` `Settings` class AND `backend/.env.example`. Never add defaults for secrets.
- `ModelInference.chat()` response shape: `response["choices"][0]["message"]["content"]` (same as `test_watsonx.py`).
- All async tests require `@pytest.mark.asyncio` — pytest-asyncio runs in STRICT mode.
- Use the `conftest.py` `test_client` fixture for FastAPI endpoint tests (ASGITransport, no live server needed).
- `_noaa_val()` in `noaa_swpc.py` must be used for every numeric NOAA field — it converts the `-9999` sentinel to `None`.
- NOAA SWPC wind/mag feeds have multiple instrument rows per timestamp. The `active=true` row is the designated primary.
- NASA DONKI SEP events are records, not measurements. Numerical proton flux = `ProtonFluxReading` from NOAA GOES.
- Do not add `CME arrival probability` — it doesn't exist in the upstream API. Use `enlilList[].isEarthGB` + `estimatedShockArrivalTime`.
- `SpaceWeatherService._safe_fetch()` wraps every coroutine call — catch `DataSourceUnavailableError` there, not in routes.
- `get_space_weather_service()` in `dependencies.py` returns a new service instance per call but shares the cached `TTLCache` singleton via `get_cache()`.
- Code style: 4-space indent, `from __future__ import annotations` at top, blank lines between logical sections.
- No scikit-learn in Phase 1 — anomaly detection is Phase 2.
