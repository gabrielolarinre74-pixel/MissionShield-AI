"""
MissionShield AI — pytest configuration and shared fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> list | dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def kp_fixture():
    return load_fixture("noaa_kp.json")


@pytest.fixture
def wind_fixture():
    return load_fixture("noaa_wind.json")


@pytest.fixture
def mag_fixture():
    return load_fixture("noaa_mag.json")


@pytest.fixture
def proton_fixture():
    return load_fixture("noaa_proton.json")


@pytest.fixture
def flares_fixture():
    return load_fixture("nasa_flares.json")


@pytest.fixture
def cmes_fixture():
    return load_fixture("nasa_cmes.json")


@pytest.fixture
def gst_fixture():
    return load_fixture("nasa_gst.json")


@pytest.fixture
def sep_fixture():
    return load_fixture("nasa_sep.json")


@pytest_asyncio.fixture
async def test_client():
    """Async HTTP test client backed by the FastAPI app directly (no live server)."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
