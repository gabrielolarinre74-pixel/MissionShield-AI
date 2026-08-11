"""Endpoint integration test using the FastAPI test client (no live server needed)."""
import sys
import asyncio
sys.path.insert(0, 'backend')

from httpx import AsyncClient, ASGITransport
from app.main import app


async def run():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # --- health ---
        r = await client.get("/api/health")
        print("GET /api/health ->", r.status_code, r.json())
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # --- snapshot (live API call) ---
        print()
        print("GET /api/space-weather/snapshot -> (calling live APIs, please wait...)")
        r2 = await client.get("/api/space-weather/snapshot")
        print("  status:", r2.status_code)
        body = r2.json()
        print("  freshness:", body.get("freshness"))
        print("  fetched_at:", body.get("fetched_at"))

        kp = body.get("latest_kp")
        print("  latest_kp estimated_kp:", kp.get("estimated_kp") if kp else None)

        wind = body.get("latest_solar_wind")
        print("  solar_wind_speed_km_s:", wind.get("proton_speed_km_s") if wind else None)

        mag = body.get("latest_mag_field")
        print("  bz_gsm_nt:", mag.get("bz_gsm_nt") if mag else None)

        proton = body.get("latest_proton_flux_10mev")
        print("  proton_flux_10mev_pfu:", proton.get("flux_pfu") if proton else None)

        for s in body.get("source_status", []):
            status_str = "available" if s["available"] else "UNAVAILABLE"
            err = f" (error: {s['error']})" if s.get("error") else ""
            print(f"  source: {s['source']} -> {status_str}{err}")

        print("  X-Data-Freshness:", r2.headers.get("x-data-freshness"))
        print("  X-Data-Sources:", r2.headers.get("x-data-sources"))
        assert r2.status_code == 200
        assert body.get("freshness") == "live"

        # --- events (uses cached snapshot) ---
        print()
        print("GET /api/space-weather/events -> (cached snapshot)")
        r3 = await client.get("/api/space-weather/events")
        print("  status:", r3.status_code)
        ev = r3.json()
        print("  flares:", len(ev.get("flares", [])))
        print("  cmes:", len(ev.get("cmes", [])))
        print("  geomagnetic_storms:", len(ev.get("geomagnetic_storms", [])))
        print("  sep_events:", len(ev.get("sep_events", [])))
        print("  freshness:", ev.get("freshness"))
        assert r3.status_code == 200
        # Second call should be cached
        assert ev.get("freshness") == "cached"

        print()
        print("ALL ENDPOINT TESTS PASSED")


asyncio.run(run())
