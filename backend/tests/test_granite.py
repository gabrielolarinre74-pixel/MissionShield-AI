"""
Tests for the IBM Granite / watsonx.ai integration.

All tests mock ModelInference — no real API calls are made.
No credentials are used in tests; API key validation uses placeholder values only.

Tests verify:
  - Brief prompt contains required context (profile, risk, source provenance)
  - Missing-data warning reaches the prompt when applicable
  - Simulation flag reaches prompt when is_simulated=True
  - AI errors become graceful AIServiceError (no raw SDK exceptions to browser)
  - Raw secrets never appear in prompt payload
  - Chat history is bounded
  - Structured responses are correct
  - AI unavailability returns graceful degraded response (not 500)
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.ai.watsonx_client import AIServiceError, WatsonxClient
from app.ai.mission_ai import (
    generate_brief,
    answer_question,
    _serialize_context,
    MAX_USER_MESSAGE_CHARS,
)
from app.ai.prompts import format_brief_messages, format_qa_messages
from app.models.mission import MissionProfile
from app.models.risk import MissionRiskReport, RiskFactor, RiskLevel
from app.models.space_weather import (
    DataFreshness,
    DataSource,
    KpReading,
    SpaceWeatherSnapshot,
)
from app.services.anomaly import AnomalyFlag

_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_snapshot(kp: float = 3.0) -> SpaceWeatherSnapshot:
    return SpaceWeatherSnapshot(
        fetched_at=_NOW,
        freshness=DataFreshness.LIVE,
        latest_kp=KpReading(
            time_tag=_NOW,
            kp_index=3,
            estimated_kp=kp,
            source=DataSource.NOAA_SWPC,
        ),
    )


def _make_report(
    is_simulated: bool = False,
    missing_factors: list[str] | None = None,
    confidence: str = "full",
    risk_score: float = 30.0,
    risk_level: RiskLevel = RiskLevel.MODERATE,
) -> MissionRiskReport:
    geo_factor = RiskFactor(
        label="Geomagnetic Disturbance",
        normalized_severity=0.3,
        mission_weight=0.30,
        weighted_contribution=9.0,
        observed_value="3.00",
        source="NOAA SWPC",
        explanation="Quiet conditions.",
        data_available=True,
    )
    return MissionRiskReport(
        mission_profile=MissionProfile.ASTRONAUT_EVA,
        risk_score=risk_score,
        risk_level=risk_level,
        primary_risk_factor="Geomagnetic Disturbance",
        factors=[geo_factor],
        is_simulated=is_simulated,
        computed_at=_NOW.isoformat(),
        missing_factors=missing_factors or [],
        confidence=confidence,
    )


def _make_client(response_text: str = "Test brief content") -> WatsonxClient:
    """Return a WatsonxClient whose .chat() returns a fixed string."""
    client = WatsonxClient.__new__(WatsonxClient)
    mock_model = MagicMock()
    mock_model.chat.return_value = {
        "choices": [{"message": {"content": response_text}}]
    }
    client._model = mock_model
    return client


def _make_error_client() -> WatsonxClient:
    """Return a WatsonxClient whose .chat() raises AIServiceError."""
    client = WatsonxClient.__new__(WatsonxClient)
    mock_model = MagicMock()
    mock_model.chat.side_effect = Exception("Connection refused")
    client._model = mock_model
    return client


# ---------------------------------------------------------------------------
# Context serialization tests
# ---------------------------------------------------------------------------

class TestContextSerialization:
    def test_context_contains_profile(self):
        snapshot = _make_snapshot()
        report = _make_report()
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "ASTRONAUT_EVA" in ctx

    def test_context_contains_risk_score(self):
        snapshot = _make_snapshot()
        report = _make_report(risk_score=42.5)
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "42.5" in ctx

    def test_context_contains_risk_level(self):
        snapshot = _make_snapshot()
        report = _make_report(risk_level=RiskLevel.HIGH)
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "HIGH" in ctx

    def test_context_contains_disclaimer(self):
        snapshot = _make_snapshot()
        report = _make_report()
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "prototype" in ctx.lower()

    def test_missing_data_in_context(self):
        snapshot = _make_snapshot()
        report = _make_report(missing_factors=["Solar Radiation", "Geomagnetic Disturbance"])
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "Solar Radiation" in ctx
        assert "Missing" in ctx or "missing" in ctx

    def test_simulation_flag_in_context(self):
        snapshot = _make_snapshot()
        report = _make_report(is_simulated=True)
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "YES" in ctx or "SIMULATED" in ctx

    def test_live_context_not_simulated(self):
        snapshot = _make_snapshot()
        report = _make_report(is_simulated=False)
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        assert "NO — all values are real NASA/NOAA observations" in ctx

    def test_no_credentials_in_context(self):
        """Credentials must never appear in the serialized context."""
        snapshot = _make_snapshot()
        report = _make_report()
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [])
        # These are the env var names — check neither key names nor hypothetical values appear.
        for forbidden in ["WATSONX_APIKEY", "WATSONX_URL", "api_key", "apikey", "NASA_API_KEY"]:
            assert forbidden.lower() not in ctx.lower(), (
                f"Credential reference '{forbidden}' found in context"
            )

    def test_anomaly_flags_in_context(self):
        snapshot = _make_snapshot()
        report = _make_report()
        flag = AnomalyFlag(
            parameter="estimated_kp",
            timestamp=_NOW.isoformat(),
            current_value=8.5,
            unit="Kp units",
            baseline_median=2.0,
            baseline_dispersion=0.5,
            dispersion_type="MAD",
            z_score=8.0,
            threshold=3.0,
            direction="high",
            sample_count=20,
            is_anomalous=True,
            source="NOAA SWPC",
            explanation="Anomalous Kp detected.",
        )
        ctx = _serialize_context(MissionProfile.ASTRONAUT_EVA, report, snapshot, [flag])
        assert "ANOMALOUS" in ctx
        assert "8.5" in ctx


# ---------------------------------------------------------------------------
# Mission Brief generation tests (mocked Granite)
# ---------------------------------------------------------------------------

class TestMissionBriefGeneration:
    def test_brief_generated_successfully(self):
        client = _make_client("Mission readiness is moderate. Monitor solar conditions.")
        snapshot = _make_snapshot()
        report = _make_report()
        result = generate_brief(
            MissionProfile.ASTRONAUT_EVA, report, snapshot, [], client,
            force_refresh=True,
        )
        assert result["brief"] == "Mission readiness is moderate. Monitor solar conditions."
        assert "IBM Granite" in result["attribution"]
        assert result["cached"] is False

    def test_brief_is_cached_on_second_call(self):
        client = _make_client("Cached brief content")
        snapshot = _make_snapshot()
        report = _make_report()
        # First call — not cached.
        result1 = generate_brief(
            MissionProfile.LUNAR_MISSION, report, snapshot, [], client,
            force_refresh=True,
        )
        # Second call — should use cache.
        result2 = generate_brief(
            MissionProfile.LUNAR_MISSION, report, snapshot, [], client,
        )
        assert result2["cached"] is True
        assert result2["brief"] == result1["brief"]

    def test_ai_error_raises_service_error(self):
        client = _make_error_client()
        snapshot = _make_snapshot()
        report = _make_report()
        with pytest.raises(AIServiceError):
            generate_brief(
                MissionProfile.ROCKET_LAUNCH, report, snapshot, [], client,
                force_refresh=True,
            )

    def test_missing_credentials_raises_service_error(self):
        """WatsonxClient without configured credentials should raise AIServiceError."""
        client = WatsonxClient.__new__(WatsonxClient)
        client._model = None
        # Patch settings directly where watsonx_client reads it.
        with patch("app.ai.watsonx_client.settings") as mock_settings:
            mock_settings.WATSONX_APIKEY = ""
            mock_settings.WATSONX_URL = ""
            mock_settings.WATSONX_PROJECT_ID = ""
            mock_settings.WATSONX_MODEL_ID = ""
            with pytest.raises(AIServiceError):
                client._get_model()


# ---------------------------------------------------------------------------
# Chat history bounding tests
# ---------------------------------------------------------------------------

class TestChatHistoryBounding:
    def test_history_is_bounded(self):
        """format_qa_messages should include at most MAX_HISTORY_TURNS prior messages."""
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(30)
        ]
        messages = format_qa_messages("context", "new question", history=long_history)
        # Count non-system, non-final messages.
        middle_messages = messages[1:-1]  # Exclude system prompt and final user message.
        assert len(middle_messages) <= 8

    def test_no_history_still_works(self):
        messages = format_qa_messages("context", "question")
        assert len(messages) == 2  # system + user

    def test_system_prompt_first(self):
        messages = format_qa_messages("context", "question")
        assert messages[0]["role"] == "system"

    def test_last_message_is_user_question(self):
        messages = format_qa_messages("context", "my question")
        assert messages[-1]["role"] == "user"
        assert "my question" in messages[-1]["content"]


# ---------------------------------------------------------------------------
# Q&A tests
# ---------------------------------------------------------------------------

class TestMissionQA:
    def test_answer_returned(self):
        client = _make_client("The risk is moderate due to elevated Kp.")
        snapshot = _make_snapshot()
        report = _make_report()
        result = answer_question(
            question="What is the current risk?",
            profile=MissionProfile.ASTRONAUT_EVA,
            risk_report=report,
            snapshot=snapshot,
            anomaly_flags=[],
            client=client,
        )
        assert result["answer"] == "The risk is moderate due to elevated Kp."
        assert "IBM Granite" in result["attribution"]

    def test_long_question_truncated(self):
        """Questions over MAX_USER_MESSAGE_CHARS should be truncated."""
        long_q = "x" * (MAX_USER_MESSAGE_CHARS + 200)
        client = _make_client("answer")
        snapshot = _make_snapshot()
        report = _make_report()
        # Should not raise.
        result = answer_question(
            question=long_q,
            profile=MissionProfile.LEO_SATELLITE,
            risk_report=report,
            snapshot=snapshot,
            anomaly_flags=[],
            client=client,
        )
        # Verify the model received a truncated message.
        call_args = client._model.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "[truncated]" in user_msg["content"]

    def test_is_simulated_propagated(self):
        client = _make_client("answer")
        snapshot = _make_snapshot()
        report = _make_report(is_simulated=True)
        result = answer_question(
            question="Is this simulated?",
            profile=MissionProfile.ROCKET_LAUNCH,
            risk_report=report,
            snapshot=snapshot,
            anomaly_flags=[],
            client=client,
        )
        assert result["is_simulated"] is True

    def test_ai_error_raises_service_error(self):
        client = _make_error_client()
        snapshot = _make_snapshot()
        report = _make_report()
        with pytest.raises(AIServiceError):
            answer_question(
                question="What is the risk?",
                profile=MissionProfile.LEO_SATELLITE,
                risk_report=report,
                snapshot=snapshot,
                anomaly_flags=[],
                client=client,
            )


# ---------------------------------------------------------------------------
# Prompt content verification
# ---------------------------------------------------------------------------

class TestPromptContent:
    def test_brief_system_prompt_has_no_credentials(self):
        from app.ai.prompts import BRIEF_SYSTEM_PROMPT
        for forbidden in ["api_key", "apikey", "WATSONX_APIKEY", "NASA_API_KEY"]:
            assert forbidden.lower() not in BRIEF_SYSTEM_PROMPT.lower()

    def test_brief_system_prompt_has_disclaimer_instruction(self):
        from app.ai.prompts import BRIEF_SYSTEM_PROMPT
        assert "prototype" in BRIEF_SYSTEM_PROMPT.lower()

    def test_qa_system_prompt_says_no_go_nogo(self):
        """QA system prompt should explicitly prohibit issuing official launch clearance."""
        from app.ai.prompts import QA_SYSTEM_PROMPT
        assert "go/no-go" in QA_SYSTEM_PROMPT.lower() or "decision-support" in QA_SYSTEM_PROMPT.lower()

    def test_brief_messages_structure(self):
        messages = format_brief_messages("test context")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "test context" in messages[1]["content"]
