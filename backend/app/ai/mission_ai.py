"""
MissionShield AI — Mission AI orchestration service.

Orchestrates:
  1. Context serialization: converts MissionRiskReport + SpaceWeatherSnapshot
     + AnomalyFlag list into a structured text context for Granite.
  2. Mission Brief generation via IBM Granite.
  3. Contextual Q&A via IBM Granite.

ARCHITECTURE
------------
  Risk engine (deterministic) → MissionRiskReport
  Anomaly detection (statistical) → list[AnomalyFlag]
  Both ↓
  Curated text context (no credentials, no secrets)
  ↓
  IBM Granite → human-readable mission intelligence

Brief caching:
  Generated briefs are cached in-memory for BRIEF_CACHE_TTL_SECONDS.
  Cache key = (profile, risk_score_bucket, is_simulated, snapshot_timestamp).
  Avoids wasteful repeat Granite calls when context has not changed.

AI failures:
  If Granite is unavailable, deterministic intelligence (risk score, anomaly
  flags) continues to work.  Routes handle AIServiceError gracefully.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.prompts import format_brief_messages, format_qa_messages
from app.ai.watsonx_client import AIServiceError, WatsonxClient
from app.models.mission import MissionProfile
from app.models.risk import MissionRiskReport
from app.models.space_weather import SpaceWeatherSnapshot
from app.services.anomaly import AnomalyFlag

logger = logging.getLogger(__name__)

# Brief cache TTL in seconds.
BRIEF_CACHE_TTL_SECONDS = 300  # 5 minutes

# Max tokens for brief generation.
BRIEF_MAX_TOKENS = 600

# Max tokens for Q&A responses.
QA_MAX_TOKENS = 400

# Maximum user message length (characters) accepted from the browser.
MAX_USER_MESSAGE_CHARS = 800


# ---------------------------------------------------------------------------
# In-memory brief cache
# ---------------------------------------------------------------------------

@dataclass
class _BriefCacheEntry:
    brief: str
    attribution: str
    cached_at: float  # time.time()


_brief_cache: dict[str, _BriefCacheEntry] = {}


def _brief_cache_key(
    profile: MissionProfile,
    risk_report: MissionRiskReport,
    snapshot: SpaceWeatherSnapshot,
) -> str:
    """
    Compute a deterministic cache key for the Mission Brief.

    Key factors: profile, risk score (rounded to 1 dp), risk level,
    is_simulated, snapshot timestamp.
    """
    key_data = {
        "profile": profile.value,
        "risk_score": round(risk_report.risk_score, 1),
        "risk_level": risk_report.risk_level.value,
        "is_simulated": risk_report.is_simulated,
        "fetched_at": snapshot.fetched_at.isoformat(),
    }
    raw = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Context serialization — builds the text passed to Granite.
# ---------------------------------------------------------------------------

def _serialize_context(
    profile: MissionProfile,
    risk_report: MissionRiskReport,
    snapshot: SpaceWeatherSnapshot,
    anomaly_flags: list[AnomalyFlag],
) -> str:
    """
    Serialize mission intelligence into a structured text context for Granite.

    SECURITY: This function must NEVER include credentials, API keys, or
    configuration values.  Only scientific/mission data is included.
    """
    lines: list[str] = []

    lines.append("=== MISSIONSHIELD INTELLIGENCE CONTEXT ===")
    lines.append(f"Mission Profile: {profile.value}")
    lines.append(f"Snapshot Time (UTC): {snapshot.fetched_at.isoformat()}")
    lines.append(f"Data Freshness: {snapshot.freshness.value.upper()}")
    lines.append(f"Simulation Mode: {'YES — values marked [SIM] are simulated, not real observations' if risk_report.is_simulated else 'NO — all values are real NASA/NOAA observations'}")
    lines.append("")

    lines.append("--- MISSIONSHIELD RISK ASSESSMENT ---")
    lines.append(f"Risk Score: {risk_report.risk_score:.1f} / 100")
    lines.append(f"Risk Level: {risk_report.risk_level.value}")
    lines.append(f"Primary Risk Driver: {risk_report.primary_risk_factor or 'N/A'}")
    lines.append(f"Data Completeness: {risk_report.data_completeness * 100:.0f}%")
    lines.append(f"Confidence: {risk_report.confidence.upper()}")
    if risk_report.missing_factors:
        lines.append(f"Missing Data: {', '.join(risk_report.missing_factors)}")
    lines.append(f"Disclaimer: {risk_report.disclaimer}")
    lines.append("")

    lines.append("--- RISK FACTOR BREAKDOWN ---")
    for factor in risk_report.factors:
        if not factor.data_available:
            lines.append(
                f"  {factor.label}: DATA UNAVAILABLE"
            )
        else:
            ref = f" [{factor.reference_scale}]" if factor.reference_scale else ""
            val = f" | Observed: {factor.observed_value}" if factor.observed_value else ""
            unit = f" {factor.units}" if factor.units else ""
            lines.append(
                f"  {factor.label}{ref}: severity={factor.normalized_severity:.2f}, "
                f"contribution={factor.weighted_contribution:.1f}/100{val}{unit}"
            )
            lines.append(f"    → {factor.explanation}")
    lines.append("")

    lines.append("--- CURRENT SPACE WEATHER READINGS ---")
    if snapshot.latest_kp:
        lines.append(
            f"  Kp Index: {snapshot.latest_kp.estimated_kp:.2f} "
            f"(NOAA SWPC, {snapshot.latest_kp.time_tag.isoformat()})"
        )
    else:
        lines.append("  Kp Index: UNAVAILABLE")

    if snapshot.latest_solar_wind and snapshot.latest_solar_wind.proton_speed_km_s is not None:
        lines.append(
            f"  Solar Wind Speed: {snapshot.latest_solar_wind.proton_speed_km_s:.0f} km/s "
            f"(NOAA SWPC)"
        )
    else:
        lines.append("  Solar Wind Speed: UNAVAILABLE")

    if snapshot.latest_mag_field and snapshot.latest_mag_field.bz_gsm_nt is not None:
        lines.append(
            f"  IMF Bz: {snapshot.latest_mag_field.bz_gsm_nt:.2f} nT (GSM) "
            f"(NOAA SWPC, {'southward/geoeffective' if snapshot.latest_mag_field.bz_gsm_nt < 0 else 'northward'})"
        )
    else:
        lines.append("  IMF Bz: UNAVAILABLE")

    if snapshot.latest_proton_flux_10mev and snapshot.latest_proton_flux_10mev.flux_pfu is not None:
        lines.append(
            f"  >=10 MeV Proton Flux: {snapshot.latest_proton_flux_10mev.flux_pfu:.4f} pfu "
            f"(NOAA GOES)"
        )
    else:
        lines.append("  >=10 MeV Proton Flux: UNAVAILABLE")
    lines.append("")

    lines.append("--- RECENT NASA DONKI EVENTS (last 7 days) ---")
    if snapshot.recent_flares:
        for f in snapshot.recent_flares[-3:]:  # Show up to 3 most recent.
            lines.append(
                f"  FLARE: {f.class_type or 'unknown'} at {f.begin_time.isoformat()} (NASA DONKI)"
            )
    else:
        lines.append("  No recent solar flares.")

    if snapshot.recent_cmes:
        earth_cmes = []
        for cme in snapshot.recent_cmes[-5:]:
            for analysis in cme.analyses:
                for run in analysis.enlil_runs:
                    if run.is_earth_directed:
                        arrival = run.estimated_shock_arrival_time
                        earth_cmes.append(
                            f"  CME (Earth-directed): started {cme.start_time.isoformat()}, "
                            f"estimated arrival: {arrival.isoformat() if arrival else 'unknown'}"
                        )
        if earth_cmes:
            lines.extend(earth_cmes)
        else:
            lines.append(f"  {len(snapshot.recent_cmes)} CME(s) detected — none Earth-directed in model runs.")
    else:
        lines.append("  No recent CMEs.")

    if snapshot.recent_geomagnetic_storms:
        lines.append(f"  {len(snapshot.recent_geomagnetic_storms)} geomagnetic storm event(s) in record (NASA DONKI).")
    if snapshot.recent_sep_events:
        lines.append(
            f"  {len(snapshot.recent_sep_events)} SEP event record(s) in last 7 days "
            f"(NASA DONKI; event records only — numerical flux from NOAA GOES above)."
        )
    lines.append("")

    if anomaly_flags:
        lines.append("--- STATISTICAL ANOMALY FLAGS ---")
        lines.append("Note: statistical anomaly ≠ danger. These are situational awareness signals.")
        for flag in anomaly_flags:
            status = "ANOMALOUS" if flag.is_anomalous else "normal"
            lines.append(
                f"  {flag.parameter}: {flag.current_value} {flag.unit} "
                f"[{status}, z={flag.z_score:.2f}] — {flag.explanation}"
            )
        lines.append("")

    lines.append("--- SOURCE ATTRIBUTION ---")
    for status in snapshot.source_status:
        avail = "available" if status.available else f"unavailable: {status.error}"
        lines.append(f"  {status.source.value}: {avail}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

_ATTRIBUTION = "AI-generated — IBM Granite via watsonx.ai"


def generate_brief(
    profile: MissionProfile,
    risk_report: MissionRiskReport,
    snapshot: SpaceWeatherSnapshot,
    anomaly_flags: list[AnomalyFlag],
    client: WatsonxClient,
    *,
    force_refresh: bool = False,
) -> dict[str, str]:
    """
    Generate a Mission Brief using IBM Granite.

    Returns a dict with:
      brief : str      — the generated text
      attribution : str — "AI-generated — IBM Granite via watsonx.ai"
      cached : bool    — True if served from brief cache

    Raises AIServiceError if Granite is unavailable.
    """
    # Check brief cache.
    cache_key = _brief_cache_key(profile, risk_report, snapshot)
    if not force_refresh and cache_key in _brief_cache:
        entry = _brief_cache[cache_key]
        if time.time() - entry.cached_at < BRIEF_CACHE_TTL_SECONDS:
            logger.debug("Mission Brief served from cache (key=%s)", cache_key)
            return {
                "brief": entry.brief,
                "attribution": entry.attribution,
                "cached": True,
            }

    context = _serialize_context(profile, risk_report, snapshot, anomaly_flags)
    messages = format_brief_messages(context)

    logger.info("Requesting Mission Brief from IBM Granite (profile=%s)", profile.value)
    brief_text = client.chat(messages, max_new_tokens=BRIEF_MAX_TOKENS)

    # Store in cache.
    _brief_cache[cache_key] = _BriefCacheEntry(
        brief=brief_text,
        attribution=_ATTRIBUTION,
        cached_at=time.time(),
    )

    return {
        "brief": brief_text,
        "attribution": _ATTRIBUTION,
        "cached": False,
    }


def answer_question(
    question: str,
    profile: MissionProfile,
    risk_report: MissionRiskReport,
    snapshot: SpaceWeatherSnapshot,
    anomaly_flags: list[AnomalyFlag],
    client: WatsonxClient,
    history: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """
    Answer an operator question grounded in the current MissionShield context.

    Parameters
    ----------
    question : str
        The operator's question.  Validated for max length before use.
    profile : MissionProfile
        Current mission profile.
    risk_report : MissionRiskReport
        Current deterministic risk report.
    snapshot : SpaceWeatherSnapshot
        Current space-weather snapshot.
    anomaly_flags : list[AnomalyFlag]
        Current anomaly detection results.
    client : WatsonxClient
        The AI client instance.
    history : list[dict] | None
        Bounded prior conversation history.

    Returns
    -------
    dict with:
      answer : str
      attribution : str
      is_simulated : bool

    Raises AIServiceError if Granite is unavailable.
    """
    # Validate user message length.
    if len(question) > MAX_USER_MESSAGE_CHARS:
        question = question[:MAX_USER_MESSAGE_CHARS] + " [truncated]"

    # Build context — does not include credentials or config values.
    context = _serialize_context(profile, risk_report, snapshot, anomaly_flags)

    # Build messages — history is bounded inside format_qa_messages.
    messages = format_qa_messages(context, question, history)

    logger.info(
        "Requesting Q&A answer from IBM Granite (profile=%s, q_len=%d)",
        profile.value,
        len(question),
    )
    answer_text = client.chat(messages, max_new_tokens=QA_MAX_TOKENS)

    return {
        "answer": answer_text,
        "attribution": _ATTRIBUTION,
        "is_simulated": risk_report.is_simulated,
    }
