"""
Tests for the NOAA SWPC client normalization logic.
No live HTTP calls — all responses are mocked from fixture files.
"""

from __future__ import annotations

from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.noaa_swpc import NOAASWPCClient
from app.exceptions import DataSourceUnavailableError
from app.models.space_weather import DataSource


def _mock_response(data: list | dict):
    """Build a mock httpx Response that returns the given JSON data."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Kp index
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kp_normalizes_correctly(kp_fixture):
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(kp_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_kp_index()

    assert len(readings) == 5
    # All timestamps should be UTC-aware.
    for r in readings:
        assert r.time_tag.tzinfo is not None
        assert r.time_tag.tzinfo == timezone.utc
    # Latest reading should have kp_index=3.
    latest = max(readings, key=lambda r: r.time_tag)
    assert latest.kp_index == 3
    assert latest.estimated_kp == 3.67
    assert latest.source == DataSource.NOAA_SWPC


@pytest.mark.asyncio
async def test_kp_returns_empty_on_null_response(kp_fixture):
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(None))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_kp_index()

    assert readings == []


# ---------------------------------------------------------------------------
# Solar wind
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_solar_wind_normalizes_correctly(wind_fixture):
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(wind_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_solar_wind()

    assert len(readings) == 3
    active_rows = [r for r in readings if r.active]
    assert len(active_rows) == 1
    active = active_rows[0]
    assert active.proton_speed_km_s == pytest.approx(411.36)
    assert active.instrument_source == "ACE"
    assert active.source == DataSource.NOAA_SWPC


@pytest.mark.asyncio
async def test_solar_wind_sentinel_is_none(wind_fixture):
    """NOAA -9999 sentinel values must be normalised to None."""
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(wind_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_solar_wind()

    # The third row has proton_density=-9999 — must be None.
    third = [r for r in readings if r.instrument_source == "ACE" and not r.active]
    assert len(third) == 1
    assert third[0].proton_density_cm3 is None


# ---------------------------------------------------------------------------
# Magnetic field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mag_normalizes_bz_gsm(mag_fixture):
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(mag_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_magnetic_field()

    assert len(readings) == 3
    active_rows = [r for r in readings if r.active]
    assert len(active_rows) == 1
    active = active_rows[0]
    # bz_gsm is -2.21 nT (southward).
    assert active.bz_gsm_nt == pytest.approx(-2.21)
    assert active.source == DataSource.NOAA_SWPC


@pytest.mark.asyncio
async def test_mag_sentinel_bz_is_none(mag_fixture):
    """bz_gsm=-9999 in third row must be normalised to None."""
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(mag_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_magnetic_field()

    non_active_solar1 = [
        r for r in readings if r.instrument_source == "SOLAR1" and not r.active
    ]
    assert len(non_active_solar1) == 1
    assert non_active_solar1[0].bz_gsm_nt is None


# ---------------------------------------------------------------------------
# Proton flux (NOAA GOES)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proton_flux_normalizes_channels(proton_fixture):
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(proton_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_proton_flux()

    # There are 9 rows in the fixture; all should be parsed (null flux is valid).
    assert len(readings) == 9
    ten_mev = [r for r in readings if r.energy_channel == ">=10 MeV"]
    assert len(ten_mev) == 2
    # All have satellite 18.
    assert all(r.satellite == 18 for r in readings)
    from app.models.space_weather import DataSource as DS
    assert all(r.source == DS.NOAA_GOES for r in readings)


@pytest.mark.asyncio
async def test_proton_flux_null_flux_is_none(proton_fixture):
    """A null flux in the fixture must produce flux_pfu=None."""
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(proton_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        readings = await client.get_proton_flux()

    null_rows = [r for r in readings if r.flux_pfu is None]
    assert len(null_rows) == 1
    assert null_rows[0].energy_channel == ">=30 MeV"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noaa_raises_on_timeout():
    import httpx
    client = NOAASWPCClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await client.get_kp_index()

    assert "NOAA SWPC Kp" in str(exc_info.value)
