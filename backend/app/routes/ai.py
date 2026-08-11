"""
MissionShield AI — AI route endpoints.

POST /api/ai/brief
  Generates an IBM Granite Mission Brief for the current risk context.

POST /api/ai/chat
  Answers an operator question grounded in the current MissionShield context.

Security rules:
  - Profile/mission identifiers come from the request body.
  - The backend constructs the authoritative NASA/NOAA intelligence context.
  - No raw telemetry, fabricated measurements, or credentials are accepted
    from the browser.
  - AI responses never contain credentials.
  - AIServiceError is caught and returns a structured degraded response.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.ai.mission_ai import answer_question, generate_brief
from app.ai.watsonx_client import AIServiceError, WatsonxClient, get_watsonx_client
from app.dependencies import get_space_weather_service
from app.exceptions import DataSourceUnavailableError
from app.models.mission import MissionProfile, SimulationOverrides
from app.services.anomaly import detect_snapshot_anomalies
from app.services.risk_engine import compute_risk
from app.services.space_weather import SpaceWeatherService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai")


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class BriefRequest(BaseModel):
    """Request body for POST /api/ai/brief."""

    model_config = ConfigDict(frozen=True)

    profile: MissionProfile
    simulation_overrides: SimulationOverrides | None = None
    # If True, bypass brief cache and force a new Granite request.
    force_refresh: bool = False


class BriefResponse(BaseModel):
    """Response from POST /api/ai/brief."""

    model_config = ConfigDict(frozen=True)

    brief: str
    attribution: str
    cached: bool
    risk_score: float
    risk_level: str
    is_simulated: bool
    disclaimer: str


class ChatMessage(BaseModel):
    """One message in the conversation history."""

    model_config = ConfigDict(frozen=True)

    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for POST /api/ai/chat."""

    model_config = ConfigDict(frozen=True)

    profile: MissionProfile
    message: str = Field(min_length=1, max_length=800)
    # Bounded prior conversation history (user/assistant pairs).
    history: list[ChatMessage] = Field(default_factory=list, max_length=16)
    simulation_overrides: SimulationOverrides | None = None


class ChatResponse(BaseModel):
    """Response from POST /api/ai/chat."""

    model_config = ConfigDict(frozen=True)

    answer: str
    attribution: str
    is_simulated: bool
    disclaimer: str


# ---------------------------------------------------------------------------
# Shared helper: build risk report + anomalies from snapshot.
# ---------------------------------------------------------------------------

async def _build_intelligence(
    svc: SpaceWeatherService,
    profile: MissionProfile,
    overrides: SimulationOverrides | None,
):
    """Fetch snapshot, compute risk, detect anomalies. Returns (snapshot, report, anomalies)."""
    try:
        snapshot = await svc.get_snapshot()
    except DataSourceUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DATA_SOURCE_UNAVAILABLE",
                "message": "Space-weather data unavailable.",
                "source": exc.source,
            },
        ) from exc
    except Exception as exc:
        logger.error("AI route: snapshot error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": "An internal error occurred."},
        ) from exc

    report = compute_risk(snapshot=snapshot, profile=profile, overrides=overrides)
    anomaly_flags = detect_snapshot_anomalies(snapshot)
    return snapshot, report, anomaly_flags


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

_DISCLAIMER = (
    "MissionShield provides prototype decision-support intelligence and is not "
    "an official NASA, NOAA, or flight-safety rating."
)
_AI_UNAVAILABLE_BRIEF = (
    "Mission Brief is temporarily unavailable because IBM Granite could not be reached. "
    "The deterministic risk score and space-weather data above remain accurate and available."
)
_AI_UNAVAILABLE_ANSWER = (
    "IBM Granite is temporarily unavailable. "
    "Please consult the risk score and space-weather data directly. "
    "MissionShield's deterministic analysis remains operational."
)


@router.post("/brief", response_model=BriefResponse)
async def get_mission_brief(
    request: BriefRequest,
    svc: Annotated[SpaceWeatherService, Depends(get_space_weather_service)],
    ai_client: Annotated[WatsonxClient, Depends(get_watsonx_client)],
) -> BriefResponse:
    """
    Generate an IBM Granite Mission Brief for the current space-weather and risk context.

    The backend constructs the authoritative intelligence context from live NASA/NOAA
    data — the browser supplies only the mission profile and optional simulation params.

    If IBM Granite is unavailable, returns a structured graceful-degraded response
    so deterministic intelligence continues to work.
    """
    snapshot, report, anomaly_flags = await _build_intelligence(
        svc, request.profile, request.simulation_overrides
    )

    try:
        result = generate_brief(
            profile=request.profile,
            risk_report=report,
            snapshot=snapshot,
            anomaly_flags=anomaly_flags,
            client=ai_client,
            force_refresh=request.force_refresh,
        )
        brief_text = result["brief"]
        attribution = result["attribution"]
        cached = result["cached"]
    except AIServiceError as exc:
        logger.warning("AI brief unavailable: %s", exc.detail)
        brief_text = _AI_UNAVAILABLE_BRIEF
        attribution = "IBM Granite unavailable — deterministic intelligence remains operational"
        cached = False

    return BriefResponse(
        brief=brief_text,
        attribution=attribution,
        cached=cached,
        risk_score=report.risk_score,
        risk_level=report.risk_level.value,
        is_simulated=report.is_simulated,
        disclaimer=_DISCLAIMER,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    svc: Annotated[SpaceWeatherService, Depends(get_space_weather_service)],
    ai_client: Annotated[WatsonxClient, Depends(get_watsonx_client)],
) -> ChatResponse:
    """
    Answer an operator question grounded in current MissionShield intelligence.

    The backend constructs the authoritative context — the browser supplies only
    the profile, bounded history, and question text.

    History is bounded to last 16 messages (8 user/assistant pairs).
    Each message is subject to the 800-character limit enforced in ChatRequest.

    If IBM Granite is unavailable, returns a graceful degraded response.
    """
    snapshot, report, anomaly_flags = await _build_intelligence(
        svc, request.profile, request.simulation_overrides
    )

    # Convert ChatMessage objects to plain dicts for the prompt builder.
    history_dicts = [
        {"role": msg.role, "content": msg.content}
        for msg in request.history
    ]

    try:
        result = answer_question(
            question=request.message,
            profile=request.profile,
            risk_report=report,
            snapshot=snapshot,
            anomaly_flags=anomaly_flags,
            client=ai_client,
            history=history_dicts,
        )
        answer_text = result["answer"]
        attribution = result["attribution"]
        is_sim = result["is_simulated"]
    except AIServiceError as exc:
        logger.warning("AI chat unavailable: %s", exc.detail)
        answer_text = _AI_UNAVAILABLE_ANSWER
        attribution = "IBM Granite unavailable — deterministic intelligence remains operational"
        is_sim = report.is_simulated

    return ChatResponse(
        answer=answer_text,
        attribution=attribution,
        is_simulated=is_sim,
        disclaimer=_DISCLAIMER,
    )
