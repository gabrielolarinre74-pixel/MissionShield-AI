"""
Tests for the NASA DONKI client normalization logic.
No live HTTP calls — all responses are mocked from fixture files.
"""

from __future__ import annotations

from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.nasa_donki import NASADONKIClient
from app.exceptions import DataSourceUnavailableError
from app.models.space_weather import DataSource


def _mock_response(data: list | dict | None):
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Solar flares
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flares_normalized(flares_fixture):
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(flares_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        flares = await client.get_flares()

    assert len(flares) == 2
    first = flares[0]
    assert first.flr_id == "2026-08-10T12:34:00-FLR-001"
    assert first.class_type == "C2.4"
    assert first.source_location == "N14W102"
    assert first.active_region_num == 14498
    assert first.begin_time.tzinfo == timezone.utc
    assert len(first.linked_events) == 1
    assert first.linked_events[0].activity_id == "2026-08-10T13:25:00-CME-001"
    assert first.source == DataSource.NASA_DONKI


@pytest.mark.asyncio
async def test_flare_missing_optional_fields(flares_fixture):
    """Second fixture flare has null end_time, source_location, activeRegionNum."""
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(flares_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        flares = await client.get_flares()

    second = flares[1]
    assert second.end_time is None
    assert second.source_location is None
    assert second.active_region_num is None
    assert second.linked_events == []


@pytest.mark.asyncio
async def test_flares_null_response_returns_empty():
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(None))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        flares = await client.get_flares()

    assert flares == []


# ---------------------------------------------------------------------------
# CMEs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmes_normalized(cmes_fixture):
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(cmes_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        cmes = await client.get_cmes()

    assert len(cmes) == 2
    earth_cme = cmes[0]
    assert earth_cme.activity_id == "2026-08-04T11:23:00-CME-001"
    assert len(earth_cme.analyses) == 1
    analysis = earth_cme.analyses[0]
    assert analysis.is_most_accurate is True
    assert analysis.speed_km_s == pytest.approx(527.0)
    # ENLIL run must be parsed.
    assert len(analysis.enlil_runs) == 1
    run = analysis.enlil_runs[0]
    assert run.is_earth_directed is True
    assert run.estimated_shock_arrival_time is not None
    assert run.kp_90 == 2
    assert run.kp_135 == 3


@pytest.mark.asyncio
async def test_cme_no_enlil_runs(cmes_fixture):
    """Second CME has an empty enlilList."""
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(cmes_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        cmes = await client.get_cmes()

    second = cmes[1]
    assert len(second.analyses[0].enlil_runs) == 0
    assert second.analyses[0].is_most_accurate is True


# ---------------------------------------------------------------------------
# Geomagnetic storms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gst_normalized(gst_fixture):
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(gst_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        storms = await client.get_geomagnetic_storms()

    assert len(storms) == 1
    storm = storms[0]
    assert storm.gst_id == "2026-08-08T18:00:00-GST-001"
    assert len(storm.observed_kp_readings) == 1
    assert storm.observed_kp_readings[0].kp_index == pytest.approx(5.67)
    assert storm.observed_kp_readings[0].kp_source == "NOAA"
    assert len(storm.linked_events) == 2


# ---------------------------------------------------------------------------
# SEP events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sep_events_normalized(sep_fixture):
    """SEP events are event records. No numeric flux values should be invented."""
    client = NASADONKIClient()
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=_mock_response(sep_fixture))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        sep_events = await client.get_sep_events()

    assert len(sep_events) == 2
    first = sep_events[0]
    assert first.sep_id == "2026-07-30T18:45:00-SEP-001"
    assert "GOES-P: SEISS >10 MeV" in first.instruments
    assert len(first.linked_events) == 2
    assert first.source == DataSource.NASA_DONKI

    # Second has null linkedEvents — must be empty list.
    second = sep_events[1]
    assert second.linked_events == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nasa_raises_on_http_error():
    import httpx
    client = NASADONKIClient()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=MagicMock(status_code=429)
    )
    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await client.get_flares()

    assert "NASA DONKI" in str(exc_info.value)
