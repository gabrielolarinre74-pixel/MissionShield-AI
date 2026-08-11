"""
Tests for SpaceWeatherService — caching, partial-failure tolerance, and snapshot assembly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import DataSourceUnavailableError
from app.models.space_weather import DataFreshness, DataSource
from app.services.cache import TTLCache
from app.services.space_weather import SpaceWeatherService


def _make_service(ttl: int = 300) -> SpaceWeatherService:
    cache = TTLCache(ttl_seconds=ttl)
    return SpaceWeatherService(cache=cache)


def _kp_reading():
    from app.models.space_weather import KpReading
    return KpReading(
        time_tag=datetime(2026, 8, 11, 7, 50, tzinfo=timezone.utc),
        kp_index=3,
        estimated_kp=3.67,
        kp_text="3+",
    )


def _wind_reading():
    from app.models.space_weather import SolarWindReading
    return SolarWindReading(
        time_tag=datetime(2026, 8, 11, 13, 25, tzinfo=timezone.utc),
        instrument_source="ACE",
        active=True,
        proton_speed_km_s=411.36,
    )


def _mag_reading():
    from app.models.space_weather import MagneticFieldReading
    return MagneticFieldReading(
        time_tag=datetime(2026, 8, 11, 13, 25, tzinfo=timezone.utc),
        instrument_source="SOLAR1",
        active=True,
        bt_nt=7.51,
        bz_gsm_nt=-2.21,
    )


def _proton_reading():
    from app.models.space_weather import ProtonFluxReading
    return ProtonFluxReading(
        time_tag=datetime(2026, 8, 11, 7, 35, tzinfo=timezone.utc),
        satellite=18,
        flux_pfu=0.2374,
        energy_channel=">=10 MeV",
        source=DataSource.NOAA_GOES,
    )


@pytest.mark.asyncio
async def test_live_snapshot_assembled_correctly():
    svc = _make_service()

    with (
        patch.object(svc._noaa, "get_kp_index", AsyncMock(return_value=[_kp_reading()])),
        patch.object(svc._noaa, "get_solar_wind", AsyncMock(return_value=[_wind_reading()])),
        patch.object(svc._noaa, "get_magnetic_field", AsyncMock(return_value=[_mag_reading()])),
        patch.object(svc._noaa, "get_proton_flux", AsyncMock(return_value=[_proton_reading()])),
        patch.object(svc._nasa, "get_flares", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_cmes", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_geomagnetic_storms", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_sep_events", AsyncMock(return_value=[])),
    ):
        snapshot = await svc.get_snapshot()

    assert snapshot.freshness == DataFreshness.LIVE
    assert snapshot.latest_kp is not None
    assert snapshot.latest_kp.estimated_kp == pytest.approx(3.67)
    assert snapshot.latest_solar_wind is not None
    assert snapshot.latest_solar_wind.proton_speed_km_s == pytest.approx(411.36)
    assert snapshot.latest_mag_field is not None
    assert snapshot.latest_mag_field.bz_gsm_nt == pytest.approx(-2.21)
    assert snapshot.latest_proton_flux_10mev is not None
    assert snapshot.latest_proton_flux_10mev.flux_pfu == pytest.approx(0.2374)


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_freshness():
    svc = _make_service(ttl=300)

    with (
        patch.object(svc._noaa, "get_kp_index", AsyncMock(return_value=[_kp_reading()])),
        patch.object(svc._noaa, "get_solar_wind", AsyncMock(return_value=[_wind_reading()])),
        patch.object(svc._noaa, "get_magnetic_field", AsyncMock(return_value=[_mag_reading()])),
        patch.object(svc._noaa, "get_proton_flux", AsyncMock(return_value=[_proton_reading()])),
        patch.object(svc._nasa, "get_flares", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_cmes", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_geomagnetic_storms", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_sep_events", AsyncMock(return_value=[])),
    ):
        first = await svc.get_snapshot()
        second = await svc.get_snapshot()

    assert first.freshness == DataFreshness.LIVE
    assert second.freshness == DataFreshness.CACHED


@pytest.mark.asyncio
async def test_partial_failure_noaa_down_still_returns_snapshot():
    """If NOAA fails but NASA succeeds, snapshot is still returned with NASA data."""
    svc = _make_service()

    noaa_error = DataSourceUnavailableError("NOAA SWPC Kp", "timeout")

    with (
        patch.object(svc._noaa, "get_kp_index", AsyncMock(side_effect=noaa_error)),
        patch.object(svc._noaa, "get_solar_wind", AsyncMock(side_effect=noaa_error)),
        patch.object(svc._noaa, "get_magnetic_field", AsyncMock(side_effect=noaa_error)),
        patch.object(svc._noaa, "get_proton_flux", AsyncMock(side_effect=noaa_error)),
        patch.object(svc._nasa, "get_flares", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_cmes", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_geomagnetic_storms", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_sep_events", AsyncMock(return_value=[])),
    ):
        snapshot = await svc.get_snapshot()

    # Should still return a snapshot rather than raising.
    assert snapshot.freshness == DataFreshness.LIVE
    # NOAA measurements should be None (not fabricated).
    assert snapshot.latest_kp is None
    assert snapshot.latest_solar_wind is None
    # NOAA source should be marked unavailable.
    noaa_status = next(s for s in snapshot.source_status if s.source == DataSource.NOAA_SWPC)
    assert noaa_status.available is False
    assert noaa_status.error is not None
    # NASA source should be available.
    nasa_status = next(s for s in snapshot.source_status if s.source == DataSource.NASA_DONKI)
    assert nasa_status.available is True


@pytest.mark.asyncio
async def test_all_sources_fail_with_no_cache_raises():
    """When everything fails and there is no cache, raise DataSourceUnavailableError."""
    svc = _make_service()
    error = DataSourceUnavailableError("test", "forced failure")

    with (
        patch.object(svc._noaa, "get_kp_index", AsyncMock(side_effect=error)),
        patch.object(svc._noaa, "get_solar_wind", AsyncMock(side_effect=error)),
        patch.object(svc._noaa, "get_magnetic_field", AsyncMock(side_effect=error)),
        patch.object(svc._noaa, "get_proton_flux", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_flares", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_cmes", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_geomagnetic_storms", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_sep_events", AsyncMock(side_effect=error)),
    ):
        with pytest.raises(DataSourceUnavailableError):
            await svc.get_snapshot()


@pytest.mark.asyncio
async def test_all_sources_fail_with_stale_cache_returns_stale():
    """When everything fails but a stale cache entry exists, serve it as STALE."""
    svc = _make_service(ttl=1)  # 1-second TTL

    # First call populates the cache.
    with (
        patch.object(svc._noaa, "get_kp_index", AsyncMock(return_value=[_kp_reading()])),
        patch.object(svc._noaa, "get_solar_wind", AsyncMock(return_value=[_wind_reading()])),
        patch.object(svc._noaa, "get_magnetic_field", AsyncMock(return_value=[_mag_reading()])),
        patch.object(svc._noaa, "get_proton_flux", AsyncMock(return_value=[_proton_reading()])),
        patch.object(svc._nasa, "get_flares", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_cmes", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_geomagnetic_storms", AsyncMock(return_value=[])),
        patch.object(svc._nasa, "get_sep_events", AsyncMock(return_value=[])),
    ):
        await svc.get_snapshot()

    # Wait for TTL to expire.
    await asyncio.sleep(1.1)

    error = DataSourceUnavailableError("test", "forced failure")
    with (
        patch.object(svc._noaa, "get_kp_index", AsyncMock(side_effect=error)),
        patch.object(svc._noaa, "get_solar_wind", AsyncMock(side_effect=error)),
        patch.object(svc._noaa, "get_magnetic_field", AsyncMock(side_effect=error)),
        patch.object(svc._noaa, "get_proton_flux", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_flares", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_cmes", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_geomagnetic_storms", AsyncMock(side_effect=error)),
        patch.object(svc._nasa, "get_sep_events", AsyncMock(side_effect=error)),
    ):
        stale = await svc.get_snapshot()

    assert stale.freshness == DataFreshness.STALE
    # Data should still be present (from the original live fetch).
    assert stale.latest_kp is not None
