"""Live sanity check — verifies parsers work against real API responses."""
import asyncio
import sys
sys.path.insert(0, 'backend')

from app.clients.noaa_swpc import NOAASWPCClient
from app.clients.nasa_donki import NASADONKIClient


async def main():
    noaa = NOAASWPCClient()
    nasa = NASADONKIClient()

    print("--- NOAA Kp ---")
    kp = await noaa.get_kp_index()
    latest_kp = max(kp, key=lambda r: r.time_tag) if kp else None
    if latest_kp:
        print("  readings:", len(kp), "| latest kp_index:", latest_kp.kp_index,
              "| estimated_kp:", latest_kp.estimated_kp, "| time:", latest_kp.time_tag)
    else:
        print("  NO DATA")

    print("--- NOAA Solar Wind ---")
    wind = await noaa.get_solar_wind()
    active_wind = next((r for r in wind if r.active), None)
    if active_wind:
        print("  rows:", len(wind), "| active speed:", active_wind.proton_speed_km_s,
              "km/s | source:", active_wind.instrument_source)
    else:
        print("  rows:", len(wind), "| no active row")

    print("--- NOAA Magnetic Field ---")
    mag = await noaa.get_magnetic_field()
    active_mag = next((r for r in mag if r.active), None)
    if active_mag:
        print("  rows:", len(mag), "| active bz_gsm:", active_mag.bz_gsm_nt,
              "nT | bt:", active_mag.bt_nt, "nT")
    else:
        print("  rows:", len(mag), "| no active row")

    print("--- NOAA GOES Proton Flux (>=10 MeV) ---")
    proton = await noaa.get_proton_flux()
    ten_mev = [r for r in proton if r.energy_channel == ">=10 MeV"]
    latest_10 = max(ten_mev, key=lambda r: r.time_tag) if ten_mev else None
    if latest_10:
        print("  total rows:", len(proton), "| latest >=10 MeV flux:", latest_10.flux_pfu,
              "pfu | satellite:", latest_10.satellite)
    else:
        print("  total rows:", len(proton), "| no >=10 MeV rows found")

    print("--- NASA DONKI Flares (7d) ---")
    flares = await nasa.get_flares()
    latest_class = flares[-1].class_type if flares else "none"
    print("  events:", len(flares), "| most recent class:", latest_class)

    print("--- NASA DONKI CMEs (7d) ---")
    cmes = await nasa.get_cmes()
    earth_directed_count = sum(
        1 for c in cmes for a in c.analyses for r in a.enlil_runs if r.is_earth_directed
    )
    print("  events:", len(cmes), "| ENLIL Earth-directed model runs:", earth_directed_count)

    print("--- NASA DONKI GST (30d) ---")
    storms = await nasa.get_geomagnetic_storms(lookback_days=30)
    print("  events:", len(storms))

    print("--- NASA DONKI SEP (30d) ---")
    seps = await nasa.get_sep_events(lookback_days=30)
    print("  events:", len(seps), "(event records only — no fabricated flux values)")

    print()
    print("LIVE SANITY CHECK PASSED — all parsers accepted live API responses without error")


asyncio.run(main())
