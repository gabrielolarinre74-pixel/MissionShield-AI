"""
Phase 2 endpoint acceptance tests.

All tests use the FastAPI ASGI test client (no live server, no Uvicorn).
AI endpoints use mocked Granite clients — no real watsonx tokens consumed.

Tests verify:
  - POST /api/mission/risk — success, validation, service error
  - GET /api/space-weather/anomalies — success
  - POST /api/ai/brief — success with mocked AI, graceful AI failure
  - POST /api/ai/chat — success with mocked AI, graceful AI failure
  - Phase 1 endpoints remain working (regression)
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.space_weather import (
    DataFreshness,
    DataSource,
    KpReading,
    ProtonFluxReading,
    SpaceWeatherSnapshot,
)
from app.ai.watsonx_client import AIServiceError

_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async test client using ASGI transport (no live server)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _make_full_snapshot() -> SpaceWeatherSnapshot:
    return SpaceWeatherSnapshot(
        fetched_at=_NOW,
        freshness=DataFreshness.LIVE,
        latest_kp=KpReading(
            time_tag=_NOW,
            kp_index=3,
            estimated_kp=3.0,
            source=DataSource.NOAA_SWPC,
        ),
        latest_proton_flux_10mev=ProtonFluxReading(
            time_tag=_NOW,
            flux_pfu=0.5,
            energy_channel=">=10 MeV",
            source=DataSource.NOAA_GOES,
        ),
    )


# ---------------------------------------------------------------------------
# Phase 1 regression tests
# ---------------------------------------------------------------------------

class TestPhase1Regression:
    @pytest.mark.asyncio
    async def test_health_still_works(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        # Health endpoint must not expose secrets.
        text = str(resp.json())
        assert "WATSONX_APIKEY" not in text
        assert "NASA_API_KEY" not in text

    @pytest.mark.asyncio
    async def test_snapshot_endpoint_exists(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.get("/api/space-weather/snapshot")
        assert resp.status_code == 200
        assert "freshness" in resp.json()

    @pytest.mark.asyncio
    async def test_events_endpoint_exists(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.get("/api/space-weather/events")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/mission/risk
# ---------------------------------------------------------------------------

class TestMissionRiskEndpoint:
    @pytest.mark.asyncio
    async def test_risk_returns_200_for_valid_profile(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.post(
                "/api/mission/risk",
                json={"profile": "ASTRONAUT_EVA"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_score" in data
        assert "risk_level" in data
        assert "factors" in data
        assert "disclaimer" in data
        assert 0.0 <= data["risk_score"] <= 100.0

    @pytest.mark.asyncio
    async def test_risk_all_profiles(self, client):
        snapshot = _make_full_snapshot()
        profiles = ["ASTRONAUT_EVA", "LUNAR_MISSION", "LEO_SATELLITE", "ROCKET_LAUNCH"]
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            for profile in profiles:
                resp = await client.post("/api/mission/risk", json={"profile": profile})
                assert resp.status_code == 200, f"Profile {profile} failed: {resp.json()}"
                assert resp.json()["mission_profile"] == profile

    @pytest.mark.asyncio
    async def test_risk_invalid_profile_422(self, client):
        resp = await client.post("/api/mission/risk", json={"profile": "INVALID_PROFILE"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_risk_with_simulation_override(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.post(
                "/api/mission/risk",
                json={
                    "profile": "ASTRONAUT_EVA",
                    "simulation_overrides": {"kp_index": 9.0},
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_simulated"] is True

    @pytest.mark.asyncio
    async def test_risk_completeness_field_present(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.post("/api/mission/risk", json={"profile": "LEO_SATELLITE"})
        data = resp.json()
        assert "data_completeness" in data
        assert "missing_factors" in data
        assert "confidence" in data

    @pytest.mark.asyncio
    async def test_risk_503_when_snapshot_unavailable(self, client):
        from app.exceptions import DataSourceUnavailableError
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            side_effect=DataSourceUnavailableError("All sources"),
        ):
            resp = await client.post("/api/mission/risk", json={"profile": "ROCKET_LAUNCH"})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_risk_response_has_no_credentials(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.post("/api/mission/risk", json={"profile": "ROCKET_LAUNCH"})
        text = resp.text
        for forbidden in ["WATSONX_APIKEY", "NASA_API_KEY"]:
            assert forbidden not in text


# ---------------------------------------------------------------------------
# GET /api/space-weather/anomalies
# ---------------------------------------------------------------------------

class TestAnomaliesEndpoint:
    @pytest.mark.asyncio
    async def test_anomalies_returns_200(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.get("/api/space-weather/anomalies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_anomalies_empty_without_series(self, client):
        """Without time-series data (single point snapshot), anomalies should be empty."""
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.get("/api/space-weather/anomalies")
        assert resp.json() == []  # No time-series data in minimal snapshot.

    @pytest.mark.asyncio
    async def test_anomalies_freshness_header(self, client):
        snapshot = _make_full_snapshot()
        with patch(
            "app.services.space_weather.SpaceWeatherService.get_snapshot",
            new_callable=AsyncMock,
            return_value=snapshot,
        ):
            resp = await client.get("/api/space-weather/anomalies")
        assert "x-data-freshness" in resp.headers


# ---------------------------------------------------------------------------
# POST /api/ai/brief
# ---------------------------------------------------------------------------

class TestAIBriefEndpoint:
    def _mock_ai_client(self, text: str = "Test brief"):
        from app.ai.watsonx_client import WatsonxClient
        client = WatsonxClient.__new__(WatsonxClient)
        mock_model = MagicMock()
        mock_model.chat.return_value = {
            "choices": [{"message": {"content": text}}]
        }
        client._model = mock_model
        return client

    @pytest.mark.asyncio
    async def test_brief_returns_200(self, client):
        snapshot = _make_full_snapshot()
        ai_client = self._mock_ai_client("Mission is ready.")
        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch("app.ai.watsonx_client.get_watsonx_client", return_value=ai_client),
        ):
            resp = await client.post(
                "/api/ai/brief",
                json={"profile": "ROCKET_LAUNCH", "force_refresh": True},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "brief" in data
        assert "attribution" in data
        assert "disclaimer" in data
        assert "IBM Granite" in data["attribution"]

    @pytest.mark.asyncio
    async def test_brief_graceful_when_ai_unavailable(self, client):
        """AI failure should return 200 with a graceful-degraded message, not 500."""
        snapshot = _make_full_snapshot()
        from app.ai.watsonx_client import WatsonxClient
        ai_client = WatsonxClient.__new__(WatsonxClient)
        ai_client._model = None

        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch("app.ai.watsonx_client.get_watsonx_client", return_value=ai_client),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.WATSONX_APIKEY = ""
            mock_settings.WATSONX_URL = ""
            mock_settings.WATSONX_PROJECT_ID = ""
            mock_settings.WATSONX_MODEL_ID = ""
            # Force the brief route to catch AIServiceError gracefully.
            with patch(
                "app.routes.ai.generate_brief",
                side_effect=AIServiceError("unavailable"),
            ):
                resp = await client.post(
                    "/api/ai/brief",
                    json={"profile": "ROCKET_LAUNCH", "force_refresh": True},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["brief"]  # Non-empty graceful message.

    @pytest.mark.asyncio
    async def test_brief_no_credentials_in_response(self, client):
        snapshot = _make_full_snapshot()
        ai_client = self._mock_ai_client("Brief text")
        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch("app.ai.watsonx_client.get_watsonx_client", return_value=ai_client),
        ):
            resp = await client.post(
                "/api/ai/brief",
                json={"profile": "ROCKET_LAUNCH", "force_refresh": True},
            )
        text = resp.text
        for forbidden in ["WATSONX_APIKEY", "NASA_API_KEY"]:
            assert forbidden not in text


# ---------------------------------------------------------------------------
# POST /api/ai/chat
# ---------------------------------------------------------------------------

class TestAIChatEndpoint:
    def _mock_ai_client(self, text: str = "Answer here"):
        from app.ai.watsonx_client import WatsonxClient
        client = WatsonxClient.__new__(WatsonxClient)
        mock_model = MagicMock()
        mock_model.chat.return_value = {
            "choices": [{"message": {"content": text}}]
        }
        client._model = mock_model
        return client

    @pytest.mark.asyncio
    async def test_chat_returns_200(self, client):
        snapshot = _make_full_snapshot()
        ai_client = self._mock_ai_client("The risk is moderate.")
        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch("app.ai.watsonx_client.get_watsonx_client", return_value=ai_client),
        ):
            resp = await client.post(
                "/api/ai/chat",
                json={
                    "profile": "ASTRONAUT_EVA",
                    "message": "What is the current space weather risk?",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "attribution" in data
        assert "disclaimer" in data

    @pytest.mark.asyncio
    async def test_chat_with_bounded_history(self, client):
        snapshot = _make_full_snapshot()
        ai_client = self._mock_ai_client("answer")
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(16)
        ]
        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch("app.ai.watsonx_client.get_watsonx_client", return_value=ai_client),
        ):
            resp = await client.post(
                "/api/ai/chat",
                json={
                    "profile": "LEO_SATELLITE",
                    "message": "Summary?",
                    "history": history,
                },
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_empty_message_422(self, client):
        resp = await client.post(
            "/api/ai/chat",
            json={"profile": "ROCKET_LAUNCH", "message": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_graceful_when_ai_unavailable(self, client):
        snapshot = _make_full_snapshot()
        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch(
                "app.routes.ai.answer_question",
                side_effect=AIServiceError("model unavailable"),
            ),
        ):
            resp = await client.post(
                "/api/ai/chat",
                json={"profile": "ASTRONAUT_EVA", "message": "What is happening?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"]  # Graceful message, not empty.

    @pytest.mark.asyncio
    async def test_chat_simulated_flag_in_response(self, client):
        snapshot = _make_full_snapshot()
        ai_client = self._mock_ai_client("answer")
        with (
            patch(
                "app.services.space_weather.SpaceWeatherService.get_snapshot",
                new_callable=AsyncMock,
                return_value=snapshot,
            ),
            patch("app.ai.watsonx_client.get_watsonx_client", return_value=ai_client),
        ):
            resp = await client.post(
                "/api/ai/chat",
                json={
                    "profile": "ASTRONAUT_EVA",
                    "message": "What is the simulated risk?",
                    "simulation_overrides": {"kp_index": 8.5},
                },
            )
        assert resp.status_code == 200
        assert resp.json()["is_simulated"] is True
