"""
Phase 3 targeted quality fix tests.

Tests added for:
  - Granite prompt discipline (structured sections, no Markdown)
  - Brief cache key isolation (ROCKET_LAUNCH cannot receive ASTRONAUT_EVA content)
  - Simulation / live context separation in cache
  - Brief generation idempotence across different profiles
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.ai.watsonx_client import WatsonxClient
from app.ai.mission_ai import (
    generate_brief,
    _brief_cache_key,
    _brief_cache,
)
from app.ai.prompts import BRIEF_SYSTEM_PROMPT, format_brief_messages
from app.models.mission import MissionProfile, SimulationOverrides
from app.models.risk import MissionRiskReport, RiskFactor, RiskLevel
from app.models.space_weather import (
    DataFreshness,
    DataSource,
    KpReading,
    SpaceWeatherSnapshot,
)

_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
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
    profile: MissionProfile = MissionProfile.ASTRONAUT_EVA,
    is_simulated: bool = False,
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
        mission_profile=profile,
        risk_score=risk_score,
        risk_level=risk_level,
        primary_risk_factor="Geomagnetic Disturbance",
        factors=[geo_factor],
        is_simulated=is_simulated,
        computed_at=_NOW.isoformat(),
        missing_factors=[],
        confidence="full",
    )


def _make_client(response_text: str = "READINESS\nOK.\n\nPRIMARY DRIVERS\n- Kp\n\nMONITOR\n- Kp trend\n\nCONTEXT\nData complete.") -> WatsonxClient:
    client = WatsonxClient.__new__(WatsonxClient)
    mock_model = MagicMock()
    mock_model.chat.return_value = {
        "choices": [{"message": {"content": response_text}}]
    }
    client._model = mock_model
    return client


# ---------------------------------------------------------------------------
# Issue 6: Prompt discipline — structured output, no Markdown instructions
# ---------------------------------------------------------------------------

class TestBriefPromptDiscipline:
    def test_prompt_instructs_no_markdown(self):
        """Brief system prompt must tell Granite not to use Markdown formatting."""
        assert "No Markdown syntax" in BRIEF_SYSTEM_PROMPT or "no **" in BRIEF_SYSTEM_PROMPT

    def test_prompt_instructs_section_headers(self):
        """Brief prompt must specify the four required section headers."""
        for header in ["READINESS", "PRIMARY DRIVERS", "MONITOR", "CONTEXT"]:
            assert header in BRIEF_SYSTEM_PROMPT, f"Expected section header '{header}' in brief prompt"

    def test_prompt_instructs_no_repeated_disclaimer(self):
        """Brief prompt must instruct Granite not to repeat the disclaimer inside the brief."""
        assert "Do not repeat the MissionShield disclaimer" in BRIEF_SYSTEM_PROMPT

    def test_prompt_instructs_derive_from_risk_report(self):
        """Brief prompt must tell Granite to derive factor claims from the supplied report."""
        assert "Derive" in BRIEF_SYSTEM_PROMPT or "derive" in BRIEF_SYSTEM_PROMPT

    def test_prompt_instructs_no_go_nogo(self):
        """Brief prompt must not allow go/no-go decisions."""
        assert "go/no-go" in BRIEF_SYSTEM_PROMPT.lower() or "decision-support" in BRIEF_SYSTEM_PROMPT.lower()

    def test_prompt_instructs_simulation_note(self):
        """Brief prompt must instruct Granite to note simulated values under CONTEXT."""
        assert "SIMULATED" in BRIEF_SYSTEM_PROMPT or "simulation mode" in BRIEF_SYSTEM_PROMPT.lower()

    def test_prompt_is_concise_token_budget(self):
        """Brief prompt should be shorter than the old 3-5 paragraph instruction.
        No hard limit — just verify we are not back to the old verbose format."""
        # Old prompt ended with 'End with the MissionShield disclaimer on its own line.'
        assert "End with the MissionShield disclaimer on its own line." not in BRIEF_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Issue 3/D: Brief cache key isolation
# ---------------------------------------------------------------------------

class TestBriefCacheKeyIsolation:
    def test_different_profiles_have_different_keys(self):
        snapshot = _make_snapshot()
        eva_report = _make_report(MissionProfile.ASTRONAUT_EVA, risk_score=30.0)
        rl_report = _make_report(MissionProfile.ROCKET_LAUNCH, risk_score=30.0)

        eva_key = _brief_cache_key(MissionProfile.ASTRONAUT_EVA, eva_report, snapshot)
        rl_key = _brief_cache_key(MissionProfile.ROCKET_LAUNCH, rl_report, snapshot)

        assert eva_key != rl_key, (
            "ASTRONAUT_EVA and ROCKET_LAUNCH must have different cache keys"
        )

    def test_simulated_and_live_have_different_keys(self):
        snapshot = _make_snapshot()
        live_report = _make_report(MissionProfile.ROCKET_LAUNCH, is_simulated=False)
        sim_report = _make_report(MissionProfile.ROCKET_LAUNCH, is_simulated=True, risk_score=85.0)

        live_key = _brief_cache_key(MissionProfile.ROCKET_LAUNCH, live_report, snapshot)
        sim_key = _brief_cache_key(MissionProfile.ROCKET_LAUNCH, sim_report, snapshot)

        assert live_key != sim_key, (
            "Simulated and live reports must have different cache keys"
        )

    def test_same_profile_same_context_same_key(self):
        snapshot = _make_snapshot()
        report1 = _make_report(MissionProfile.LEO_SATELLITE, risk_score=25.0)
        report2 = _make_report(MissionProfile.LEO_SATELLITE, risk_score=25.0)

        key1 = _brief_cache_key(MissionProfile.LEO_SATELLITE, report1, snapshot)
        key2 = _brief_cache_key(MissionProfile.LEO_SATELLITE, report2, snapshot)

        assert key1 == key2, "Same context must produce same cache key"

    def test_rocket_launch_cannot_receive_eva_content(self):
        """
        The most critical isolation requirement:
        A brief generated for ASTRONAUT_EVA must not be retrievable as ROCKET_LAUNCH.
        """
        snapshot = _make_snapshot()
        eva_report = _make_report(MissionProfile.ASTRONAUT_EVA, risk_score=30.0)
        rl_report = _make_report(MissionProfile.ROCKET_LAUNCH, risk_score=30.0)

        eva_client = _make_client("READINESS\nEVA brief.\nPRIMARY DRIVERS\n- Kp\nMONITOR\n- Kp\nCONTEXT\nOK.")

        # Generate brief for EVA — this stores in cache under EVA key.
        eva_result = generate_brief(
            MissionProfile.ASTRONAUT_EVA, eva_report, snapshot, [], eva_client,
            force_refresh=True,
        )
        assert "EVA brief" in eva_result["brief"]

        # Now generate brief for ROCKET_LAUNCH with a different response.
        rl_client = _make_client("READINESS\nRocket Launch brief.\nPRIMARY DRIVERS\n- Kp\nMONITOR\n- Kp\nCONTEXT\nOK.")
        rl_result = generate_brief(
            MissionProfile.ROCKET_LAUNCH, rl_report, snapshot, [], rl_client,
            force_refresh=True,
        )

        # ROCKET_LAUNCH result must NOT contain EVA brief content.
        assert "EVA brief" not in rl_result["brief"], (
            "ROCKET_LAUNCH received ASTRONAUT_EVA brief content — cache isolation failure"
        )
        assert "Rocket Launch brief" in rl_result["brief"]

    def test_all_four_profiles_isolated(self):
        """Each of the four mission profiles must store independently in the brief cache."""
        profiles = [
            MissionProfile.ROCKET_LAUNCH,
            MissionProfile.LEO_SATELLITE,
            MissionProfile.ASTRONAUT_EVA,
            MissionProfile.LUNAR_MISSION,
        ]
        snapshot = _make_snapshot()

        keys = []
        for p in profiles:
            report = _make_report(p, risk_score=20.0)
            key = _brief_cache_key(p, report, snapshot)
            keys.append(key)

        assert len(set(keys)) == 4, (
            f"Expected 4 unique cache keys for 4 profiles, got {len(set(keys))}"
        )


# ---------------------------------------------------------------------------
# Issue 7: Simulation context separation
# ---------------------------------------------------------------------------

class TestSimulationBriefSeparation:
    def test_live_brief_cached_separately_from_sim(self):
        """
        A live brief and a simulated brief must be cached under distinct keys
        so that changing simulation parameters cannot serve the live brief.
        """
        snapshot = _make_snapshot()
        live_report = _make_report(MissionProfile.ROCKET_LAUNCH, is_simulated=False, risk_score=20.0)
        sim_report = _make_report(MissionProfile.ROCKET_LAUNCH, is_simulated=True, risk_score=90.0)

        live_key = _brief_cache_key(MissionProfile.ROCKET_LAUNCH, live_report, snapshot)
        sim_key = _brief_cache_key(MissionProfile.ROCKET_LAUNCH, sim_report, snapshot)

        assert live_key != sim_key

    def test_generate_brief_for_live_then_sim(self):
        """Generating a live brief then a sim brief for the same profile
        must produce distinct results stored independently."""
        snapshot = _make_snapshot()

        live_report = _make_report(MissionProfile.LUNAR_MISSION, is_simulated=False, risk_score=20.0)
        sim_report = _make_report(MissionProfile.LUNAR_MISSION, is_simulated=True, risk_score=80.0)

        live_client = _make_client("READINESS\nLive: low risk.\nPRIMARY DRIVERS\n- Kp\nMONITOR\n- Kp\nCONTEXT\nOK.")
        sim_client = _make_client("READINESS\nSim: extreme risk.\nPRIMARY DRIVERS\n- Kp\nMONITOR\n- Kp\nCONTEXT\nSimulated.")

        live_result = generate_brief(
            MissionProfile.LUNAR_MISSION, live_report, snapshot, [], live_client,
            force_refresh=True,
        )
        sim_result = generate_brief(
            MissionProfile.LUNAR_MISSION, sim_report, snapshot, [], sim_client,
            force_refresh=True,
        )

        assert "Live:" in live_result["brief"]
        assert "Sim:" in sim_result["brief"]
        assert live_result["brief"] != sim_result["brief"]
