"""
MissionShield AI — NOAA SWPC + NOAA GOES async HTTP client.

Fetches real-time space-weather measurements from official NOAA JSON feeds
and normalises them into typed domain models.

Feed URLs are documented inline — they are non-obvious and should not be
guessed or changed without verifying the upstream schema.

On network/HTTP failure a DataSourceUnavailableError is raised.
Missing upstream values are preserved as None — never coerced to zero.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.exceptions import DataSourceUnavailableError
from app.models.space_weather import (
    KpReading,
    MagneticFieldReading,
    ProtonFluxReading,
    SolarWindReading,
    DataSource,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Official NOAA feed URLs — do not change without verifying the schema.
# ---------------------------------------------------------------------------

# 1-minute planetary K-index feed (rolling window, ~hours of data).
_KP_URL = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"

# Real-time solar wind from L1 monitors (ACE, IMAP, etc.).
_WIND_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"

# Real-time interplanetary magnetic field from L1 monitors.
_MAG_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json"

# NOAA GOES primary satellite integral-proton flux, 6-hour window.
# Contains multiple energy channels per timestamp: >=1, >=5, >=10, >=30, >=50, >=60, >=100, >=500 MeV.
# The >=10 MeV channel is the standard S-class space-weather alert threshold.
_PROTON_URL = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json"

_NOAA_SOURCE = DataSource.NOAA_SWPC
_GOES_SOURCE = DataSource.NOAA_GOES

# Sentinel value used in some NOAA fields to indicate missing/bad data.
_NOAA_MISSING_SENTINEL = -9999


def _noaa_val(v: float | int | None) -> float | None:
    """Return None if the value is the NOAA missing-data sentinel (-9999) or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and v == _NOAA_MISSING_SENTINEL:
        return None
    return float(v)


def _parse_noaa_dt(value: str | None) -> datetime | None:
    """
    Parse a NOAA timestamp string to a UTC-aware datetime.

    NOAA uses two formats:
    - "2026-08-11T07:30:00" (no timezone suffix — implicitly UTC)
    - "2026-08-11T07:30:00Z"
    """
    if not value:
        return None
    try:
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        # If naive, assume UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        logger.warning("Could not parse NOAA datetime: %r", value)
        return None


class NOAASWPCClient:
    """
    Async client for NOAA SWPC and NOAA GOES real-time data feeds.

    All feeds are publicly accessible with no API key.
    CORS restrictions mean these must be fetched server-side only.
    """

    def __init__(self, timeout: int | None = None) -> None:
        self._timeout = timeout or settings.EXTERNAL_API_TIMEOUT_SECONDS

    async def get_kp_index(self) -> list[KpReading]:
        """
        Fetch 1-minute Kp index readings from NOAA SWPC.

        Returns the full available window (typically several hours).
        The most-recent entry is the latest observed Kp.
        """
        data = await self._get(_KP_URL, source_label="NOAA SWPC Kp")
        results: list[KpReading] = []
        for row in data:
            try:
                time_tag = _parse_noaa_dt(row.get("time_tag"))
                if time_tag is None:
                    continue
                kp_index = row.get("kp_index")
                estimated_kp = row.get("estimated_kp")
                if kp_index is None or estimated_kp is None:
                    continue
                results.append(
                    KpReading(
                        time_tag=time_tag,
                        kp_index=int(kp_index),
                        estimated_kp=float(estimated_kp),
                        kp_text=row.get("kp"),
                        source=_NOAA_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed Kp row", exc_info=True)
        return results

    async def get_solar_wind(self) -> list[SolarWindReading]:
        """
        Fetch real-time solar wind measurements from NOAA SWPC L1 monitors.

        The feed contains rows from multiple instrument sources.
        The active=true row is the designated primary.
        """
        data = await self._get(_WIND_URL, source_label="NOAA SWPC solar wind")
        results: list[SolarWindReading] = []
        for row in data:
            try:
                time_tag = _parse_noaa_dt(row.get("time_tag"))
                if time_tag is None:
                    continue
                results.append(
                    SolarWindReading(
                        time_tag=time_tag,
                        instrument_source=row.get("source"),
                        active=bool(row.get("active", False)),
                        proton_speed_km_s=_noaa_val(row.get("proton_speed")),
                        proton_density_cm3=_noaa_val(row.get("proton_density")),
                        proton_temperature_k=_noaa_val(row.get("proton_temperature")),
                        overall_quality=row.get("overall_quality"),
                        source=_NOAA_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed solar-wind row", exc_info=True)
        return results

    async def get_magnetic_field(self) -> list[MagneticFieldReading]:
        """
        Fetch real-time IMF measurements from NOAA SWPC L1 monitors.

        bz_gsm_nt: negative values are southward — relevant for geomagnetic coupling.
        """
        data = await self._get(_MAG_URL, source_label="NOAA SWPC magnetic field")
        results: list[MagneticFieldReading] = []
        for row in data:
            try:
                time_tag = _parse_noaa_dt(row.get("time_tag"))
                if time_tag is None:
                    continue
                results.append(
                    MagneticFieldReading(
                        time_tag=time_tag,
                        instrument_source=row.get("source"),
                        active=bool(row.get("active", False)),
                        bt_nt=_noaa_val(row.get("bt")),
                        bz_gsm_nt=_noaa_val(row.get("bz_gsm")),
                        by_gsm_nt=_noaa_val(row.get("by_gsm")),
                        bx_gsm_nt=_noaa_val(row.get("bx_gsm")),
                        overall_quality=row.get("overall_quality"),
                        source=_NOAA_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed mag-field row", exc_info=True)
        return results

    async def get_proton_flux(self) -> list[ProtonFluxReading]:
        """
        Fetch NOAA GOES integral-proton flux (6-hour window).

        The feed contains multiple energy channels per timestamp.
        Each row is one energy channel at one timestamp from one satellite.
        Source: NOAA GOES primary satellite (integral-protons-6-hour.json).
        Units: pfu (particles cm⁻² s⁻¹ sr⁻¹).
        """
        data = await self._get(_PROTON_URL, source_label="NOAA GOES proton flux")
        results: list[ProtonFluxReading] = []
        for row in data:
            try:
                time_tag = _parse_noaa_dt(row.get("time_tag"))
                energy = row.get("energy")
                if time_tag is None or not energy:
                    continue
                results.append(
                    ProtonFluxReading(
                        time_tag=time_tag,
                        satellite=row.get("satellite"),
                        flux_pfu=_noaa_val(row.get("flux")),
                        energy_channel=str(energy),
                        source=_GOES_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed proton-flux row", exc_info=True)
        return results

    async def _get(self, url: str, source_label: str) -> list[dict]:
        """
        Execute a GET request and return parsed JSON array.

        Raises DataSourceUnavailableError on network or HTTP failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                if data is None:
                    return []
                if not isinstance(data, list):
                    logger.warning("%s returned unexpected type: %s", source_label, type(data))
                    return []
                return data
        except httpx.TimeoutException as exc:
            raise DataSourceUnavailableError(
                source=source_label, detail="Request timed out"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise DataSourceUnavailableError(
                source=source_label,
                detail=f"HTTP {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise DataSourceUnavailableError(
                source=source_label, detail="Network error"
            ) from exc
