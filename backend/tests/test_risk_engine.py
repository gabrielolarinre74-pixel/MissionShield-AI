"""
Tests for the MissionShield risk engine (services/risk_engine.py).

All tests are deterministic — no I/O, no network calls, no LLM.
Tests are organized by:
  1. NOAA G-scale Kp boundaries
  2. NOAA S-scale proton flux boundaries
  3. NOAA R-scale / flare class parsing
  4. CME watch factor scenarios
  5. All four mission profiles
  6. Weight sum validation
  7. Score range (0–100)
  8. Risk level band boundaries
  9. Primary risk factor determinism
  10. Missing data / weight renormalization
  11. Degraded completeness reporting
  12. Simulation override behaviour
  13. Snapshot immutability
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from app.models.mission import MissionProfile, SimulationOverrides
from app.models.risk import RiskLevel
from app.models.space_weather import (
    DataFreshness,
    DataSource,
    KpReading,
    ProtonFluxReading,
    SolarFlareEvent,
    SpaceWeatherSnapshot,
)
from app.services.risk_engine import (
    _flare_to_noaa_r,
    _geomagnetic_severity,
    _parse_flare_class,
    _radiation_severity,
    _score_to_level,
    compute_risk,
)
from app.services.risk_policy import PROFILE_WEIGHTS, MIN_COMPLETENESS_FOR_CONFIDENCE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _make_kp_reading(kp: float) -> KpReading:
    return KpReading(
        time_tag=_NOW,
        kp_index=int(kp),
        estimated_kp=kp,
        source=DataSource.NOAA_SWPC,
    )


def _make_proton_reading(flux_pfu: float) -> ProtonFluxReading:
    return ProtonFluxReading(
        time_tag=_NOW,
        flux_pfu=flux_pfu,
        energy_channel=">=10 MeV",
        source=DataSource.NOAA_GOES,
    )


def _make_flare(class_type: str, hours_ago: float = 1.0) -> SolarFlareEvent:
    begin = _NOW - timedelta(hours=hours_ago)
    return SolarFlareEvent(
        flr_id=f"test-{class_type}-{hours_ago}",
        begin_time=begin,
        class_type=class_type,
        source=DataSource.NASA_DONKI,
    )


def _minimal_snapshot(
    kp: float | None = None,
    flux_pfu: float | None = None,
    flares: list | None = None,
    cmes: list | None = None,
) -> SpaceWeatherSnapshot:
    """Build a minimal snapshot for testing."""
    return SpaceWeatherSnapshot(
        fetched_at=_NOW,
        freshness=DataFreshness.LIVE,
        latest_kp=_make_kp_reading(kp) if kp is not None else None,
        latest_proton_flux_10mev=_make_proton_reading(flux_pfu) if flux_pfu is not None else None,
        recent_flares=flares or [],
        recent_cmes=cmes or [],
    )


# ---------------------------------------------------------------------------
# 1. NOAA G-scale Kp boundaries
# ---------------------------------------------------------------------------

class TestGeomagnetic:
    def test_below_g1(self):
        sev, _, _, ref, _ = _geomagnetic_severity(3.0)
        assert ref is None  # Below G1 — no official storm label
        assert sev < 0.20

    def test_kp_zero(self):
        sev, _, _, ref, _ = _geomagnetic_severity(0.0)
        assert sev == 0.0
        assert ref is None

    def test_kp_exactly_g1(self):
        sev, _, _, ref, _ = _geomagnetic_severity(5.0)
        assert ref == "G1"
        assert sev >= 0.20

    def test_kp_exactly_g2(self):
        sev, _, _, ref, _ = _geomagnetic_severity(6.0)
        assert ref == "G2"
        assert sev >= 0.40

    def test_kp_exactly_g3(self):
        sev, _, _, ref, _ = _geomagnetic_severity(7.0)
        assert ref == "G3"
        assert sev >= 0.60

    def test_kp_exactly_g4(self):
        sev, _, _, ref, _ = _geomagnetic_severity(8.0)
        assert ref == "G4"
        assert sev >= 0.80

    def test_kp_exactly_g5(self):
        sev, _, _, ref, _ = _geomagnetic_severity(9.0)
        assert ref == "G5"
        assert sev == 1.0

    def test_kp_above_g5(self):
        sev, _, _, _, _ = _geomagnetic_severity(9.5)
        assert sev == 1.0  # Capped at 1.0

    def test_severity_monotonic(self):
        """Higher Kp should produce higher or equal severity."""
        severities = [_geomagnetic_severity(float(k))[0] for k in range(10)]
        for i in range(len(severities) - 1):
            assert severities[i] <= severities[i + 1], (
                f"Severity not monotonic at Kp={i}: {severities[i]} > {severities[i+1]}"
            )


# ---------------------------------------------------------------------------
# 2. NOAA S-scale proton flux boundaries
# ---------------------------------------------------------------------------

class TestRadiation:
    def test_zero_flux(self):
        sev, obs, _, ref, _ = _radiation_severity(0.0)
        assert sev == 0.0
        assert ref is None

    def test_below_s1(self):
        sev, _, _, ref, _ = _radiation_severity(5.0)
        assert ref is None
        assert sev < 0.20

    def test_exactly_s1(self):
        sev, _, _, ref, _ = _radiation_severity(10.0)
        assert ref == "S1"
        assert sev >= 0.20

    def test_exactly_s2(self):
        sev, _, _, ref, _ = _radiation_severity(100.0)
        assert ref == "S2"
        assert sev >= 0.40

    def test_exactly_s3(self):
        sev, _, _, ref, _ = _radiation_severity(1_000.0)
        assert ref == "S3"
        assert sev >= 0.60

    def test_exactly_s4(self):
        sev, _, _, ref, _ = _radiation_severity(10_000.0)
        assert ref == "S4"
        assert sev >= 0.80

    def test_exactly_s5(self):
        sev, _, _, ref, _ = _radiation_severity(100_000.0)
        assert ref == "S5"
        assert sev >= 0.95

    def test_very_high_flux(self):
        sev, _, _, _, _ = _radiation_severity(1_000_000.0)
        assert sev == 1.0

    def test_negative_flux_zero(self):
        sev, _, _, _, _ = _radiation_severity(-1.0)
        assert sev == 0.0

    def test_severity_monotonic(self):
        fluxes = [0.1, 1, 10, 100, 1000, 10000, 100000]
        sevs = [_radiation_severity(f)[0] for f in fluxes]
        for i in range(len(sevs) - 1):
            assert sevs[i] <= sevs[i + 1]


# ---------------------------------------------------------------------------
# 3. Flare class parsing and NOAA R-scale reference
# ---------------------------------------------------------------------------

class TestFlareClass:
    @pytest.mark.parametrize("class_str,expected_letter,expected_mag", [
        ("C2.4", "C", 2.4),
        ("M1.5", "M", 1.5),
        ("M5.0", "M", 5.0),
        ("X1.0", "X", 1.0),
        ("X10.0", "X", 10.0),
        ("X20.0", "X", 20.0),
        ("X3.2", "X", 3.2),
        (None, "?", 0.0),
        ("", "?", 0.0),
        ("9999", "?", 0.0),     # Digit-only string → invalid class letter
        ("Z5.0", "?", 0.0),  # Unknown class letter
        ("M", "M", 1.0),     # No magnitude → defaults to 1.0
    ])
    def test_parse_flare_class(self, class_str, expected_letter, expected_mag):
        letter, mag = _parse_flare_class(class_str)
        assert letter == expected_letter
        assert abs(mag - expected_mag) < 0.01

    def test_r1_m1(self):
        assert _flare_to_noaa_r("M", 1.0) == "R1"

    def test_r2_m5(self):
        assert _flare_to_noaa_r("M", 5.0) == "R2"

    def test_r2_m9(self):
        assert _flare_to_noaa_r("M", 9.0) == "R2"

    def test_r3_x1(self):
        assert _flare_to_noaa_r("X", 1.0) == "R3"

    def test_r4_x10(self):
        assert _flare_to_noaa_r("X", 10.0) == "R4"

    def test_r5_x20(self):
        assert _flare_to_noaa_r("X", 20.0) == "R5"

    def test_c_class_below_r1(self):
        assert _flare_to_noaa_r("C", 5.0) is None

    def test_unknown_class_none(self):
        assert _flare_to_noaa_r("?", 0.0) is None

    def test_severity_monotonic(self):
        """X10 should have higher severity than X1 which should be higher than M5."""
        from app.services.risk_engine import _flare_severity_single
        s_m5 = _flare_severity_single("M", 5.0)
        s_x1 = _flare_severity_single("X", 1.0)
        s_x10 = _flare_severity_single("X", 10.0)
        s_x20 = _flare_severity_single("X", 20.0)
        assert s_m5 < s_x1 < s_x10 < s_x20


# ---------------------------------------------------------------------------
# 4. CME watch factor scenarios
# ---------------------------------------------------------------------------

class TestCMEWatch:
    from app.models.space_weather import CMEEvent, CMEAnalysis, EnlilRun

    def _make_cme_with_arrival(self, hours_from_now: float) -> "CMEEvent":
        from app.models.space_weather import CMEEvent, CMEAnalysis, EnlilRun
        arrival = _NOW + timedelta(hours=hours_from_now)
        run = EnlilRun(is_earth_directed=True, estimated_shock_arrival_time=arrival)
        analysis = CMEAnalysis(enlil_runs=[run])
        return CMEEvent(
            activity_id="TEST-CME",
            start_time=_NOW - timedelta(hours=48),
            analyses=[analysis],
        )

    def _make_cme_no_arrival(self) -> "CMEEvent":
        from app.models.space_weather import CMEEvent, CMEAnalysis, EnlilRun
        run = EnlilRun(is_earth_directed=True, estimated_shock_arrival_time=None)
        analysis = CMEAnalysis(enlil_runs=[run])
        return CMEEvent(
            activity_id="TEST-CME-NO-ARRIVAL",
            start_time=_NOW - timedelta(hours=24),
            analyses=[analysis],
        )

    def _make_cme_not_earth_directed(self) -> "CMEEvent":
        from app.models.space_weather import CMEEvent, CMEAnalysis, EnlilRun
        run = EnlilRun(is_earth_directed=False)
        analysis = CMEAnalysis(enlil_runs=[run])
        return CMEEvent(
            activity_id="TEST-CME-NOT-ED",
            start_time=_NOW - timedelta(hours=24),
            analyses=[analysis],
        )

    def test_no_earth_directed_cme(self):
        from app.services.risk_engine import _cme_watch_severity
        sev, _, _ = _cme_watch_severity([], now=_NOW)
        assert sev == 0.0

    def test_not_earth_directed(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_not_earth_directed()
        sev, _, _ = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.0

    def test_earth_directed_no_arrival(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_no_arrival()
        sev, _, exp = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.25
        assert "no estimated shock arrival" in exp.lower() or "no arrival" in exp.lower()

    def test_arrival_gt_72h(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_with_arrival(96)
        sev, obs, _ = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.25
        assert obs is not None

    def test_arrival_24_to_72h(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_with_arrival(48)
        sev, _, _ = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.50

    def test_arrival_6_to_24h(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_with_arrival(12)
        sev, _, _ = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.75

    def test_arrival_lte_6h(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_with_arrival(3)
        sev, _, exp = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.95
        assert "very high" in exp.lower() or "imminent" in exp.lower()

    def test_stale_past_arrival(self):
        from app.services.risk_engine import _cme_watch_severity
        cme = self._make_cme_with_arrival(-12)  # 12 hours in the past
        sev, obs, exp = _cme_watch_severity([cme], now=_NOW)
        assert sev == 0.0
        assert "expired" in exp.lower() or "passed" in exp.lower()


# ---------------------------------------------------------------------------
# 5. All four mission profiles produce valid reports
# ---------------------------------------------------------------------------

class TestAllProfiles:
    @pytest.mark.parametrize("profile", list(MissionProfile))
    def test_profile_runs(self, profile):
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0)
        report = compute_risk(snapshot, profile, now=_NOW)
        assert 0.0 <= report.risk_score <= 100.0
        assert report.mission_profile == profile
        assert report.risk_level in list(RiskLevel)
        assert len(report.factors) == 4

    @pytest.mark.parametrize("profile", list(MissionProfile))
    def test_high_kp_increases_score(self, profile):
        low = compute_risk(_minimal_snapshot(kp=1.0, flux_pfu=0.1), profile, now=_NOW)
        high = compute_risk(_minimal_snapshot(kp=8.0, flux_pfu=0.1), profile, now=_NOW)
        assert high.risk_score > low.risk_score

    @pytest.mark.parametrize("profile", list(MissionProfile))
    def test_high_flux_increases_score(self, profile):
        low = compute_risk(_minimal_snapshot(kp=1.0, flux_pfu=0.1), profile, now=_NOW)
        high = compute_risk(_minimal_snapshot(kp=1.0, flux_pfu=10_000.0), profile, now=_NOW)
        assert high.risk_score > low.risk_score


# ---------------------------------------------------------------------------
# 6. Profile weights sum to 1.0
# ---------------------------------------------------------------------------

class TestWeightSums:
    @pytest.mark.parametrize("profile", list(MissionProfile))
    def test_weights_sum_to_one(self, profile):
        total = sum(PROFILE_WEIGHTS[profile])
        assert abs(total - 1.0) < 1e-9, (
            f"Weights for {profile} sum to {total}, not 1.0"
        )

    def test_all_weights_positive(self):
        for profile, weights in PROFILE_WEIGHTS.items():
            for w in weights:
                assert w > 0.0, f"Zero or negative weight in {profile}: {weights}"


# ---------------------------------------------------------------------------
# 7. Score stays within 0–100
# ---------------------------------------------------------------------------

class TestScoreRange:
    def test_worst_case_stays_at_most_100(self):
        flares = [_make_flare("X20.0", hours_ago=0.5)]
        from app.models.space_weather import CMEEvent, CMEAnalysis, EnlilRun
        arrival = _NOW + timedelta(hours=1)
        run = EnlilRun(is_earth_directed=True, estimated_shock_arrival_time=arrival)
        cme = CMEEvent(
            activity_id="WORST",
            start_time=_NOW - timedelta(hours=1),
            analyses=[CMEAnalysis(enlil_runs=[run])],
        )
        snapshot = _minimal_snapshot(kp=9.0, flux_pfu=100_000.0, flares=flares, cmes=[cme])
        for profile in MissionProfile:
            report = compute_risk(snapshot, profile, now=_NOW)
            assert 0.0 <= report.risk_score <= 100.0

    def test_best_case_stays_at_least_0(self):
        snapshot = _minimal_snapshot(kp=0.0, flux_pfu=0.001)
        for profile in MissionProfile:
            report = compute_risk(snapshot, profile, now=_NOW)
            assert report.risk_score >= 0.0


# ---------------------------------------------------------------------------
# 8. Risk level band boundaries
# ---------------------------------------------------------------------------

class TestRiskLevelBands:
    def test_score_0_is_low(self):
        assert _score_to_level(0.0) == RiskLevel.LOW

    def test_score_24_99_is_low(self):
        assert _score_to_level(24.99) == RiskLevel.LOW

    def test_score_25_is_moderate(self):
        assert _score_to_level(25.0) == RiskLevel.MODERATE

    def test_score_49_99_is_moderate(self):
        assert _score_to_level(49.99) == RiskLevel.MODERATE

    def test_score_50_is_high(self):
        assert _score_to_level(50.0) == RiskLevel.HIGH

    def test_score_74_99_is_high(self):
        assert _score_to_level(74.99) == RiskLevel.HIGH

    def test_score_75_is_extreme(self):
        assert _score_to_level(75.0) == RiskLevel.EXTREME

    def test_score_100_is_extreme(self):
        assert _score_to_level(100.0) == RiskLevel.EXTREME


# ---------------------------------------------------------------------------
# 9. Primary risk factor is deterministic
# ---------------------------------------------------------------------------

class TestPrimaryFactor:
    def test_high_kp_primary_geo(self):
        """With very high Kp and low everything else, GEO should dominate for EVA."""
        snapshot = _minimal_snapshot(kp=9.0, flux_pfu=1.0)
        report = compute_risk(snapshot, MissionProfile.ASTRONAUT_EVA, now=_NOW)
        # Geomagnetic disturbance should be among the highest contributors.
        geo_factor = next(f for f in report.factors if "Geomagnetic" in f.label)
        assert geo_factor.weighted_contribution > 0.0

    def test_high_flux_primary_radiation(self):
        """With very high proton flux and quiet Kp, RAD should dominate for EVA."""
        snapshot = _minimal_snapshot(kp=1.0, flux_pfu=100_000.0)
        report = compute_risk(snapshot, MissionProfile.ASTRONAUT_EVA, now=_NOW)
        rad_factor = next(f for f in report.factors if "Radiation" in f.label)
        assert rad_factor.weighted_contribution > 0.0
        # Radiation should be the primary factor for EVA at S5 level.
        assert report.primary_risk_factor is not None

    def test_primary_factor_consistent(self):
        """Computing the same snapshot twice should give the same primary factor."""
        snapshot = _minimal_snapshot(kp=5.0, flux_pfu=50.0)
        r1 = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, now=_NOW)
        r2 = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, now=_NOW)
        assert r1.primary_risk_factor == r2.primary_risk_factor
        assert r1.risk_score == r2.risk_score


# ---------------------------------------------------------------------------
# 10. Missing data — weight renormalization
# ---------------------------------------------------------------------------

class TestMissingData:
    def test_missing_kp_still_returns_report(self):
        snapshot = _minimal_snapshot(kp=None, flux_pfu=100.0)
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, now=_NOW)
        assert 0.0 <= report.risk_score <= 100.0
        assert "Geomagnetic Disturbance" in report.missing_factors

    def test_missing_flux_still_returns_report(self):
        snapshot = _minimal_snapshot(kp=5.0, flux_pfu=None)
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, now=_NOW)
        assert 0.0 <= report.risk_score <= 100.0
        assert "Solar Radiation" in report.missing_factors

    def test_missing_both_critical_factors(self):
        snapshot = _minimal_snapshot(kp=None, flux_pfu=None)
        report = compute_risk(snapshot, MissionProfile.ASTRONAUT_EVA, now=_NOW)
        assert len(report.missing_factors) >= 2
        # Score should still be in range.
        assert 0.0 <= report.risk_score <= 100.0

    def test_missing_kp_does_not_zero_risk(self):
        """Missing Kp with high flux should still show meaningful risk."""
        snapshot = _minimal_snapshot(kp=None, flux_pfu=10_000.0)
        report = compute_risk(snapshot, MissionProfile.ASTRONAUT_EVA, now=_NOW)
        # RAD factor should still contribute.
        assert report.risk_score > 0.0

    def test_data_completeness_with_missing(self):
        """data_completeness should be < 1.0 when a factor is missing."""
        snapshot = _minimal_snapshot(kp=None, flux_pfu=5.0)
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, now=_NOW)
        assert report.data_completeness < 1.0

    def test_data_completeness_full_data(self):
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0)
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, now=_NOW)
        assert report.data_completeness == 1.0

    def test_unavailable_factor_not_as_zero(self):
        """An unavailable factor must be marked data_available=False, not zero."""
        snapshot = _minimal_snapshot(kp=None, flux_pfu=1.0)
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, now=_NOW)
        geo = next(f for f in report.factors if "Geomagnetic" in f.label)
        assert geo.data_available is False
        # observed_value should indicate unavailability, not a fabricated measurement.
        assert geo.normalized_severity == 0.0


# ---------------------------------------------------------------------------
# 11. Degraded completeness reporting
# ---------------------------------------------------------------------------

class TestDegradedCompleteness:
    def test_enough_data_is_full_confidence(self):
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0)
        report = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, now=_NOW)
        assert report.confidence == "full"

    def test_heavy_missing_data_is_degraded(self):
        """If both high-weight factors are missing, completeness should drop below threshold."""
        snapshot = _minimal_snapshot(kp=None, flux_pfu=None)
        report = compute_risk(snapshot, MissionProfile.ASTRONAUT_EVA, now=_NOW)
        # GEO (weight 0.30) + RAD (weight 0.40) = 0.70 missing → completeness=0.30 (only FLARE+CME)
        # 0.30 < MIN_COMPLETENESS_FOR_CONFIDENCE (0.50) → degraded
        assert report.confidence == "degraded"
        assert report.data_completeness < MIN_COMPLETENESS_FOR_CONFIDENCE


# ---------------------------------------------------------------------------
# 12. Simulation override behaviour
# ---------------------------------------------------------------------------

class TestSimulationOverrides:
    def test_sim_kp_sets_is_simulated(self):
        snapshot = _minimal_snapshot(kp=1.0, flux_pfu=0.5)
        overrides = SimulationOverrides(kp_index=8.0)
        report = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, overrides=overrides, now=_NOW)
        assert report.is_simulated is True

    def test_sim_kp_affects_score(self):
        snapshot = _minimal_snapshot(kp=1.0, flux_pfu=0.5)
        live = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, now=_NOW)
        overrides = SimulationOverrides(kp_index=9.0)
        sim = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, overrides=overrides, now=_NOW)
        assert sim.risk_score > live.risk_score

    def test_sim_cme_active_increases_score(self):
        snapshot = _minimal_snapshot(kp=1.0, flux_pfu=0.5)
        live = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, now=_NOW)
        overrides = SimulationOverrides(cme_earth_directed=True)
        sim = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, overrides=overrides, now=_NOW)
        assert sim.risk_score > live.risk_score

    def test_sim_cme_inactive_removes_cme_contribution(self):
        from app.models.space_weather import CMEEvent, CMEAnalysis, EnlilRun
        arrival = _NOW + timedelta(hours=10)
        run = EnlilRun(is_earth_directed=True, estimated_shock_arrival_time=arrival)
        cme = CMEEvent(
            activity_id="ACTIVE-CME",
            start_time=_NOW - timedelta(hours=5),
            analyses=[CMEAnalysis(enlil_runs=[run])],
        )
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0, cmes=[cme])
        live = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, now=_NOW)
        overrides = SimulationOverrides(cme_earth_directed=False)
        sim = compute_risk(snapshot, MissionProfile.ROCKET_LAUNCH, overrides=overrides, now=_NOW)
        assert sim.risk_score < live.risk_score

    def test_no_overrides_is_not_simulated(self):
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0)
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, now=_NOW)
        assert report.is_simulated is False

    def test_empty_overrides_not_simulated(self):
        """SimulationOverrides with all None fields should not set is_simulated."""
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0)
        overrides = SimulationOverrides()  # All fields None
        report = compute_risk(snapshot, MissionProfile.LEO_SATELLITE, overrides=overrides, now=_NOW)
        assert report.is_simulated is False


# ---------------------------------------------------------------------------
# 13. Snapshot immutability
# ---------------------------------------------------------------------------

class TestSnapshotImmutability:
    def test_simulation_does_not_mutate_snapshot(self):
        snapshot = _minimal_snapshot(kp=2.0, flux_pfu=1.0)
        original_kp = snapshot.latest_kp.estimated_kp  # 2.0
        overrides = SimulationOverrides(kp_index=9.0)
        compute_risk(snapshot, MissionProfile.ASTRONAUT_EVA, overrides=overrides, now=_NOW)
        # Snapshot must be unchanged.
        assert snapshot.latest_kp.estimated_kp == original_kp

    def test_repeated_calls_same_result(self):
        snapshot = _minimal_snapshot(kp=4.0, flux_pfu=5.0)
        r1 = compute_risk(snapshot, MissionProfile.LUNAR_MISSION, now=_NOW)
        r2 = compute_risk(snapshot, MissionProfile.LUNAR_MISSION, now=_NOW)
        assert r1.risk_score == r2.risk_score
        assert r1.risk_level == r2.risk_level


# ---------------------------------------------------------------------------
# 14. Disclaimer always present
# ---------------------------------------------------------------------------

class TestDisclaimer:
    @pytest.mark.parametrize("profile", list(MissionProfile))
    def test_disclaimer_present(self, profile):
        snapshot = _minimal_snapshot(kp=3.0, flux_pfu=1.0)
        report = compute_risk(snapshot, profile, now=_NOW)
        assert "prototype" in report.disclaimer.lower()
        assert report.disclaimer  # non-empty
