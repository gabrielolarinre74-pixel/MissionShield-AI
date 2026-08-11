"""
Tests for the MissionShield anomaly detection service (services/anomaly.py).

All tests are deterministic and require no I/O.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from app.models.space_weather import (
    DataSource,
    KpReading,
    MagneticFieldReading,
    ProtonFluxReading,
    SolarWindReading,
)
from app.services.anomaly import (
    MIN_SAMPLES,
    ANOMALY_THRESHOLD,
    AnomalyFlag,
    detect_kp_anomalies,
    detect_mag_field_anomalies,
    detect_proton_flux_anomalies,
    detect_solar_wind_anomalies,
)

_BASE_TIME = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _ts(minutes_ago: int) -> datetime:
    return _BASE_TIME - timedelta(minutes=minutes_ago)


# ---------------------------------------------------------------------------
# KpReading helpers
# ---------------------------------------------------------------------------

def _make_kp_readings(values: list[float]) -> list[KpReading]:
    return [
        KpReading(
            time_tag=_ts(len(values) - i),
            kp_index=int(v),
            estimated_kp=v,
            source=DataSource.NOAA_SWPC,
        )
        for i, v in enumerate(values)
    ]


def _make_wind_readings(speeds: list[float]) -> list[SolarWindReading]:
    return [
        SolarWindReading(
            time_tag=_ts(len(speeds) - i),
            proton_speed_km_s=s,
            source=DataSource.NOAA_SWPC,
        )
        for i, s in enumerate(speeds)
    ]


def _make_mag_readings(bzs: list[float]) -> list[MagneticFieldReading]:
    return [
        MagneticFieldReading(
            time_tag=_ts(len(bzs) - i),
            bz_gsm_nt=b,
            source=DataSource.NOAA_SWPC,
        )
        for i, b in enumerate(bzs)
    ]


def _make_proton_readings(fluxes: list[float]) -> list[ProtonFluxReading]:
    return [
        ProtonFluxReading(
            time_tag=_ts(len(fluxes) - i),
            flux_pfu=f,
            energy_channel=">=10 MeV",
            source=DataSource.NOAA_GOES,
        )
        for i, f in enumerate(fluxes)
    ]


# ---------------------------------------------------------------------------
# Kp anomaly tests
# ---------------------------------------------------------------------------

class TestKpAnomalyDetection:
    def test_normal_series_no_anomaly(self):
        """Stable Kp series should produce no anomaly."""
        readings = _make_kp_readings([2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
        flags = detect_kp_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is False

    def test_obvious_high_outlier(self):
        """Kp jump to 9 in a quiet series should be anomalous."""
        readings = _make_kp_readings([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 9.0])
        flags = detect_kp_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is True
        assert flags[0].direction == "high"
        assert abs(flags[0].z_score) >= ANOMALY_THRESHOLD

    def test_obvious_low_outlier(self):
        """Sudden drop to 0 in a consistently elevated Kp series."""
        readings = _make_kp_readings([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 0.0])
        flags = detect_kp_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is True
        assert flags[0].direction == "low"

    def test_insufficient_samples_returns_empty(self):
        """Fewer than MIN_SAMPLES readings should return empty list."""
        readings = _make_kp_readings([1.0] * (MIN_SAMPLES - 1))
        flags = detect_kp_anomalies(readings)
        assert flags == []

    def test_exactly_min_samples(self):
        """MIN_SAMPLES readings is enough."""
        readings = _make_kp_readings([2.0] * MIN_SAMPLES)
        flags = detect_kp_anomalies(readings)
        assert len(flags) == 1  # Should produce one result.

    def test_mad_zero_constant_series(self):
        """Constant series (MAD=0) should not produce a false anomaly."""
        readings = _make_kp_readings([3.0] * 10)
        flags = detect_kp_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is False

    def test_result_has_correct_source(self):
        readings = _make_kp_readings([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        flags = detect_kp_anomalies(readings, source="TEST SOURCE")
        assert flags[0].source == "TEST SOURCE"

    def test_result_units_correct(self):
        readings = _make_kp_readings([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        flags = detect_kp_anomalies(readings)
        assert flags[0].unit == "Kp units"
        assert flags[0].parameter == "estimated_kp"

    def test_threshold_preserved(self):
        readings = _make_kp_readings([2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
        flags = detect_kp_anomalies(readings)
        assert flags[0].threshold == ANOMALY_THRESHOLD

    def test_sample_count_correct(self):
        n = 10
        readings = _make_kp_readings([2.0] * n)
        flags = detect_kp_anomalies(readings)
        # sample_count = baseline = n - 1 (latest excluded from baseline).
        assert flags[0].sample_count == n - 1


# ---------------------------------------------------------------------------
# Solar wind anomaly tests
# ---------------------------------------------------------------------------

class TestSolarWindAnomalyDetection:
    def test_normal_series_no_anomaly(self):
        readings = _make_wind_readings([400.0] * 10)
        flags = detect_solar_wind_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is False

    def test_extreme_speed_outlier(self):
        readings = _make_wind_readings([400.0] * 9 + [2000.0])
        flags = detect_solar_wind_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is True
        assert flags[0].direction == "high"

    def test_insufficient_samples(self):
        readings = _make_wind_readings([400.0] * (MIN_SAMPLES - 1))
        assert detect_solar_wind_anomalies(readings) == []

    def test_null_speed_filtered_out(self):
        """Readings with None proton_speed_km_s should be excluded."""
        readings = _make_wind_readings([400.0] * 8)
        # Inject readings with None speed — below MIN_SAMPLES for valid readings.
        null_readings = [
            SolarWindReading(time_tag=_ts(100), proton_speed_km_s=None, source=DataSource.NOAA_SWPC)
            for _ in range(3)
        ]
        flags = detect_solar_wind_anomalies(null_readings)
        assert flags == []

    def test_constant_series_not_anomalous(self):
        readings = _make_wind_readings([500.0] * 10)
        flags = detect_solar_wind_anomalies(readings)
        assert not flags[0].is_anomalous


# ---------------------------------------------------------------------------
# Magnetic field (Bz) anomaly tests
# ---------------------------------------------------------------------------

class TestMagFieldAnomalyDetection:
    def test_normal_bz_no_anomaly(self):
        readings = _make_mag_readings([2.0] * 10)
        flags = detect_mag_field_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is False

    def test_extreme_southward_bz_anomalous(self):
        """Sudden deep southward Bz in a northward series."""
        readings = _make_mag_readings([3.0] * 9 + [-40.0])
        flags = detect_mag_field_anomalies(readings)
        assert flags[0].is_anomalous is True
        assert flags[0].direction == "low"  # More negative than baseline

    def test_insufficient_samples(self):
        readings = _make_mag_readings([2.0] * (MIN_SAMPLES - 1))
        assert detect_mag_field_anomalies(readings) == []

    def test_null_bz_excluded(self):
        readings = [
            MagneticFieldReading(time_tag=_ts(i), bz_gsm_nt=None, source=DataSource.NOAA_SWPC)
            for i in range(10)
        ]
        assert detect_mag_field_anomalies(readings) == []


# ---------------------------------------------------------------------------
# Proton flux anomaly tests
# ---------------------------------------------------------------------------

class TestProtonFluxAnomalyDetection:
    def test_normal_flux_no_anomaly(self):
        readings = _make_proton_readings([0.2] * 10)
        flags = detect_proton_flux_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is False

    def test_large_flux_spike_anomalous(self):
        """Flux spike of several orders of magnitude should be anomalous."""
        readings = _make_proton_readings([0.1] * 9 + [10_000.0])
        flags = detect_proton_flux_anomalies(readings)
        assert len(flags) == 1
        assert flags[0].is_anomalous is True
        assert flags[0].direction == "high"

    def test_insufficient_samples(self):
        readings = _make_proton_readings([0.2] * (MIN_SAMPLES - 1))
        assert detect_proton_flux_anomalies(readings) == []

    def test_zero_flux_excluded(self):
        """Zero flux cannot be log-transformed — must be excluded."""
        readings = _make_proton_readings([0.0] * 10)
        flags = detect_proton_flux_anomalies(readings)
        assert flags == []

    def test_non_10mev_channel_excluded(self):
        """Only >=10 MeV channel readings should be used."""
        readings = [
            ProtonFluxReading(
                time_tag=_ts(i),
                flux_pfu=1000.0,
                energy_channel=">=100 MeV",
                source=DataSource.NOAA_GOES,
            )
            for i in range(10)
        ]
        flags = detect_proton_flux_anomalies(readings)
        # Should return empty because no >=10 MeV channel readings.
        assert flags == []

    def test_unit_is_pfu(self):
        readings = _make_proton_readings([0.2] * 10)
        flags = detect_proton_flux_anomalies(readings)
        assert "pfu" in flags[0].unit

    def test_parameter_name(self):
        readings = _make_proton_readings([0.2] * 10)
        flags = detect_proton_flux_anomalies(readings)
        assert "proton_flux" in flags[0].parameter


# ---------------------------------------------------------------------------
# Anomaly is NOT automatically danger
# ---------------------------------------------------------------------------

class TestAnomalyNotDanger:
    def test_anomaly_flag_has_disclaimer_in_explanation(self):
        readings = _make_kp_readings([1.0] * 9 + [9.0])
        flags = detect_kp_anomalies(readings)
        if flags[0].is_anomalous:
            assert "does not imply danger" in flags[0].explanation.lower()
