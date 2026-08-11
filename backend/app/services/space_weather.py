"""
MissionShield AI — SpaceWeatherService.

Orchestrates the NASA DONKI and NOAA SWPC clients into a single
normalised SpaceWeatherSnapshot.

Failure-tolerance rules:
  - If NOAA succeeds but NASA fails, return the NOAA data with NASA marked unavailable.
  - If NASA succeeds but NOAA fails, return NASA events with NOAA marked unavailable.
  - If all upstream sources fail and the cache has a valid entry, serve CACHED.
  - If all upstream sources fail and only a stale entry exists, serve STALE.
  - If all upstream sources fail and there is no cache at all, raise DataSourceUnavailableError.

The service never fabricates or invents measurement values.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.clients.nasa_donki import NASADONKIClient
from app.clients.noaa_swpc import NOAASWPCClient
from app.exceptions import DataSourceUnavailableError
from app.models.space_weather import (
    DataFreshness,
    DataSource,
    KpReading,
    MagneticFieldReading,
    ProtonFluxReading,
    SolarWindReading,
    SourceStatus,
    SpaceWeatherSnapshot,
)
from app.services.cache import TTLCache

logger = logging.getLogger(__name__)

_SNAPSHOT_KEY = "space_weather_snapshot"


def _pick_active(readings: list, *, field: str = "active") -> object | None:
    """
    Return the most-recent reading where active=True, or the most-recent
    reading overall if no active row exists.
    """
    if not readings:
        return None
    active = [r for r in readings if getattr(r, field, False)]
    candidates = active if active else readings
    return max(candidates, key=lambda r: r.time_tag)


def _latest_proton_10mev(readings: list[ProtonFluxReading]) -> ProtonFluxReading | None:
    """Return the most-recent >=10 MeV proton flux reading."""
    filtered = [r for r in readings if r.energy_channel == ">=10 MeV"]
    if not filtered:
        return None
    return max(filtered, key=lambda r: r.time_tag)


class SpaceWeatherService:
    """
    High-level service that assembles a SpaceWeatherSnapshot from all data sources.

    Inject via FastAPI Depends — see dependencies.py.
    """

    def __init__(self, cache: TTLCache) -> None:
        self._cache = cache
        self._nasa = NASADONKIClient()
        self._noaa = NOAASWPCClient()

    async def get_snapshot(self) -> SpaceWeatherSnapshot:
        """
        Return a fresh or cached SpaceWeatherSnapshot.

        Checks the cache first. On a cache miss, fetches from all sources
        concurrently and assembles a snapshot. Partial failures are tolerated.
        """
        # 1. Cache hit (within TTL)?
        valid_entry = await self._cache.get_valid(_SNAPSHOT_KEY)
        if valid_entry is not None:
            logger.debug("SpaceWeatherService: serving cached snapshot")
            # Re-serialize with CACHED freshness so the client knows.
            snapshot: SpaceWeatherSnapshot = valid_entry.value
            return snapshot.model_copy(update={"freshness": DataFreshness.CACHED})

        # 2. Attempt live fetch from all sources concurrently.
        snapshot = await self._fetch_live()

        # 3. Store successful (even partial) snapshots in the cache.
        await self._cache.set(_SNAPSHOT_KEY, snapshot)
        return snapshot

    async def _fetch_live(self) -> SpaceWeatherSnapshot:
        """
        Fetch from all upstream sources concurrently.
        Returns a SpaceWeatherSnapshot; marks unavailable sources in source_status.
        Falls back to stale cache if everything fails.
        """
        now = datetime.now(timezone.utc)

        # Run all upstream fetches concurrently.
        (
            kp_result,
            wind_result,
            mag_result,
            proton_result,
            flares_result,
            cmes_result,
            storms_result,
            seps_result,
        ) = await asyncio.gather(
            self._safe_fetch(self._noaa.get_kp_index, "NOAA SWPC Kp"),
            self._safe_fetch(self._noaa.get_solar_wind, "NOAA SWPC solar wind"),
            self._safe_fetch(self._noaa.get_magnetic_field, "NOAA SWPC magnetic field"),
            self._safe_fetch(self._noaa.get_proton_flux, "NOAA GOES proton flux"),
            self._safe_fetch(self._nasa.get_flares, "NASA DONKI FLR"),
            self._safe_fetch(self._nasa.get_cmes, "NASA DONKI CME"),
            self._safe_fetch(self._nasa.get_geomagnetic_storms, "NASA DONKI GST"),
            self._safe_fetch(self._nasa.get_sep_events, "NASA DONKI SEP"),
        )

        # Unpack (data, error) tuples.
        kp_data, kp_err = kp_result
        wind_data, wind_err = wind_result
        mag_data, mag_err = mag_result
        proton_data, proton_err = proton_result
        flares_data, flares_err = flares_result
        cmes_data, cmes_err = cmes_result
        storms_data, storms_err = storms_result
        seps_data, seps_err = seps_result

        # Determine per-source availability.
        noaa_available = not any([kp_err, wind_err, mag_err, proton_err])
        nasa_available = not any([flares_err, cmes_err, storms_err, seps_err])

        # If everything failed, fall back to stale cache.
        if not noaa_available and not nasa_available:
            stale_entry = await self._cache.get(_SNAPSHOT_KEY)
            if stale_entry is not None:
                logger.warning("All upstream sources failed; serving stale snapshot")
                stale: SpaceWeatherSnapshot = stale_entry.value
                return stale.model_copy(update={"freshness": DataFreshness.STALE})
            # No cache at all — propagate the failure.
            raise DataSourceUnavailableError(
                source="All sources",
                detail="NASA DONKI and NOAA SWPC are both unavailable and no cached data exists.",
            )

        # Build source status list.
        noaa_error = "; ".join(filter(None, [kp_err, wind_err, mag_err, proton_err]))
        nasa_error = "; ".join(filter(None, [flares_err, cmes_err, storms_err, seps_err]))

        source_status = [
            SourceStatus(
                source=DataSource.NOAA_SWPC,
                available=noaa_available,
                error=noaa_error or None,
            ),
            SourceStatus(
                source=DataSource.NASA_DONKI,
                available=nasa_available,
                error=nasa_error or None,
            ),
            SourceStatus(
                source=DataSource.NOAA_GOES,
                available=proton_err is None,
                error=proton_err or None,
            ),
        ]

        # Pick active/latest readings.
        latest_kp: KpReading | None = None
        if kp_data:
            latest_kp = max(kp_data, key=lambda r: r.time_tag)

        latest_wind: SolarWindReading | None = None
        if wind_data:
            latest_wind = _pick_active(wind_data)  # type: ignore[arg-type]

        latest_mag: MagneticFieldReading | None = None
        if mag_data:
            latest_mag = _pick_active(mag_data)  # type: ignore[arg-type]

        latest_proton: ProtonFluxReading | None = None
        if proton_data:
            latest_proton = _latest_proton_10mev(proton_data)

        return SpaceWeatherSnapshot(
            fetched_at=now,
            freshness=DataFreshness.LIVE,
            last_successful_fetch=now,
            source_status=source_status,
            latest_kp=latest_kp,
            latest_solar_wind=latest_wind,
            latest_mag_field=latest_mag,
            latest_proton_flux_10mev=latest_proton,
            recent_flares=flares_data or [],
            recent_cmes=cmes_data or [],
            recent_geomagnetic_storms=storms_data or [],
            recent_sep_events=seps_data or [],
        )

    @staticmethod
    async def _safe_fetch(coro_fn, label: str) -> tuple[list | None, str | None]:
        """
        Execute an async fetch function and return (result, error_string).
        Never raises — errors are captured as strings.
        """
        try:
            data = await coro_fn()
            return data, None
        except DataSourceUnavailableError as exc:
            logger.warning("Source unavailable [%s]: %s", label, exc.detail)
            return None, exc.detail
        except Exception as exc:
            logger.error("Unexpected error fetching [%s]: %s", label, exc, exc_info=True)
            return None, str(exc)
