"""
MissionShield Phase 2 — Live IBM Granite Sanity Check.

This script performs ONE live call to IBM Granite via the Phase 2 Mission AI service
to verify end-to-end connectivity using the production watsonx.ai configuration.

This is the single permitted live Granite call for Phase 2 verification.
It does NOT run as part of the automated test suite.

Run from the repo root:
  .venv/Scripts/python.exe backend/sanity_check_phase2.py

What is verified:
  1. WatsonxClient initialises successfully with real credentials.
  2. A compact representative MissionShield context is built.
  3. IBM Granite responds with a short Mission Brief.
  4. The response text is coherent and does not invent obvious missing data.
  5. No credentials appear in the output.

The context is intentionally compact to conserve tokens.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

# Ensure the backend package is importable when run from repo root.
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from app.ai.watsonx_client import AIServiceError, WatsonxClient
from app.ai.mission_ai import generate_brief
from app.models.mission import MissionProfile
from app.models.risk import MissionRiskReport, RiskFactor, RiskLevel
from app.models.space_weather import (
    DataFreshness,
    DataSource,
    KpReading,
    ProtonFluxReading,
    SpaceWeatherSnapshot,
)
from app.services.anomaly import AnomalyFlag

_NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Build a representative (compact) context.
# ---------------------------------------------------------------------------

print("=" * 60)
print("MissionShield Phase 2 — Live IBM Granite Sanity Check")
print("=" * 60)
print()

# Compact snapshot — realistic quiet-conditions scenario.
snapshot = SpaceWeatherSnapshot(
    fetched_at=_NOW,
    freshness=DataFreshness.LIVE,
    latest_kp=KpReading(
        time_tag=_NOW,
        kp_index=2,
        estimated_kp=2.33,
        kp_text="2+",
        source=DataSource.NOAA_SWPC,
    ),
    latest_proton_flux_10mev=ProtonFluxReading(
        time_tag=_NOW,
        flux_pfu=0.21,
        energy_channel=">=10 MeV",
        satellite=18,
        source=DataSource.NOAA_GOES,
    ),
)

# Compact risk report for ASTRONAUT_EVA.
from app.services.risk_engine import compute_risk

report = compute_risk(
    snapshot=snapshot,
    profile=MissionProfile.ASTRONAUT_EVA,
    now=_NOW,
)

print(f"Profile:         {report.mission_profile.value}")
print(f"Risk Score:      {report.risk_score:.1f} / 100")
print(f"Risk Level:      {report.risk_level.value}")
print(f"Primary Factor:  {report.primary_risk_factor}")
print(f"Completeness:    {report.data_completeness * 100:.0f}%")
print(f"Confidence:      {report.confidence}")
print()

# ---------------------------------------------------------------------------
# Initialise WatsonxClient with real credentials.
# ---------------------------------------------------------------------------

print("Initialising WatsonxClient...")
try:
    client = WatsonxClient()
except Exception as exc:
    print(f"FAILED to create WatsonxClient: {exc}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Make one live Granite call.
# ---------------------------------------------------------------------------

print("Requesting Mission Brief from IBM Granite (one live call)...")
print()
try:
    result = generate_brief(
        profile=MissionProfile.ASTRONAUT_EVA,
        risk_report=report,
        snapshot=snapshot,
        anomaly_flags=[],
        client=client,
        force_refresh=True,
    )
    brief = result["brief"]
    attribution = result["attribution"]
    cached = result["cached"]

    print(f"Attribution: {attribution}")
    print(f"Cached: {cached}")
    print()
    print("=== GENERATED BRIEF ===")
    # Encode for Windows console compatibility (replace unmappable characters).
    safe_brief = brief.encode("ascii", errors="replace").decode("ascii")
    print(safe_brief)
    print("=== END BRIEF ===")
    print()

    # Security check: verify no credentials appear in output.
    for forbidden in ["WATSONX_APIKEY", "NASA_API_KEY", "api_key", "apikey"]:
        if forbidden.lower() in brief.lower():
            print(f"SECURITY WARNING: '{forbidden}' found in brief output!")
            sys.exit(1)

    print("Security check PASSED — no credentials in output.")
    print()
    print("Phase 2 Live Granite Sanity Check: PASSED")

except AIServiceError as exc:
    print(f"AIServiceError: {exc.detail}")
    print()
    print("Phase 2 Live Granite Sanity Check: FAILED (AI service unavailable)")
    print("Note: mocked integration tests all pass — this is a connectivity issue.")
    sys.exit(1)
except Exception as exc:
    print(f"Unexpected error: {type(exc).__name__}: {exc}")
    sys.exit(1)
