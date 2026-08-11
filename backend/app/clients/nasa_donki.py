"""
MissionShield AI — NASA DONKI async HTTP client.

Fetches space-weather event data from the NASA DONKI REST API and normalises
responses into typed domain models.

Only fields actually returned by the upstream API are parsed.
No scientific values are invented or fabricated.
On network/HTTP failure a DataSourceUnavailableError is raised — raw HTTP
errors never propagate to route handlers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.exceptions import DataSourceUnavailableError
from app.models.space_weather import (
    CMEAnalysis,
    CMEEvent,
    EnlilRun,
    GeomagneticStormEvent,
    LinkedEvent,
    ObservedKpPoint,
    SEPEvent,
    SolarFlareEvent,
    DataSource,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.nasa.gov/DONKI"
_SOURCE = DataSource.NASA_DONKI


def _parse_dt(value: str | None) -> datetime | None:
    """Parse a DONKI datetime string (ISO 8601 with trailing Z) to UTC datetime."""
    if not value:
        return None
    try:
        # DONKI uses formats like "2026-08-10T12:34Z" or "2026-08-10T12:34:00Z"
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        logger.warning("Could not parse DONKI datetime: %r", value)
        return None


def _linked_events(raw: list[dict] | None) -> list[LinkedEvent]:
    if not raw:
        return []
    result = []
    for item in raw:
        aid = item.get("activityID")
        if aid:
            result.append(LinkedEvent(activity_id=str(aid)))
    return result


def _parse_enlil_run(raw: dict) -> EnlilRun | None:
    try:
        return EnlilRun(
            model_completion_time=_parse_dt(raw.get("modelCompletionTime")),
            estimated_shock_arrival_time=_parse_dt(raw.get("estimatedShockArrivalTime")),
            estimated_duration_hours=raw.get("estimatedDuration"),
            kp_18=raw.get("kp_18"),
            kp_90=raw.get("kp_90"),
            kp_135=raw.get("kp_135"),
            kp_180=raw.get("kp_180"),
            is_earth_directed=bool(raw.get("isEarthGB", False)),
            is_earth_minor_impact=bool(raw.get("isEarthMinorImpact", False)),
            link=raw.get("link"),
        )
    except Exception:
        logger.warning("Skipping malformed ENLIL run entry", exc_info=True)
        return None


def _parse_cme_analysis(raw: dict) -> CMEAnalysis | None:
    try:
        enlil_runs = []
        for run_raw in raw.get("enlilList") or []:
            run = _parse_enlil_run(run_raw)
            if run is not None:
                enlil_runs.append(run)
        return CMEAnalysis(
            is_most_accurate=bool(raw.get("isMostAccurate", False)),
            time_21_5=_parse_dt(raw.get("time21_5")),
            latitude_deg=raw.get("latitude"),
            longitude_deg=raw.get("longitude"),
            half_angle_deg=raw.get("halfAngle"),
            speed_km_s=raw.get("speed"),
            cme_type=raw.get("type"),
            enlil_runs=enlil_runs,
            link=raw.get("link"),
        )
    except Exception:
        logger.warning("Skipping malformed CME analysis entry", exc_info=True)
        return None


def _date_params(lookback_days: int) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    return {"startDate": start, "endDate": end, "api_key": settings.NASA_API_KEY}


class NASADONKIClient:
    """
    Async client for the NASA DONKI REST API.

    Create a new instance per-request or share a singleton —
    the underlying httpx client manages connection pooling.
    """

    def __init__(self, timeout: int | None = None) -> None:
        self._timeout = timeout or settings.EXTERNAL_API_TIMEOUT_SECONDS

    async def get_flares(self, lookback_days: int = 7) -> list[SolarFlareEvent]:
        """Fetch FLR (solar flare) events."""
        raw_list = await self._get("/FLR", _date_params(lookback_days))
        results: list[SolarFlareEvent] = []
        for item in raw_list:
            try:
                flr_id = item.get("flrID") or item.get("flrId")
                begin = _parse_dt(item.get("beginTime"))
                if not flr_id or begin is None:
                    continue
                results.append(
                    SolarFlareEvent(
                        flr_id=str(flr_id),
                        begin_time=begin,
                        peak_time=_parse_dt(item.get("peakTime")),
                        end_time=_parse_dt(item.get("endTime")),
                        class_type=item.get("classType"),
                        source_location=item.get("sourceLocation"),
                        active_region_num=item.get("activeRegionNum"),
                        linked_events=_linked_events(item.get("linkedEvents")),
                        link=item.get("link"),
                        source=_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed FLR event", exc_info=True)
        return results

    async def get_cmes(self, lookback_days: int = 7) -> list[CMEEvent]:
        """Fetch CME (coronal mass ejection) events."""
        raw_list = await self._get("/CME", _date_params(lookback_days))
        results: list[CMEEvent] = []
        for item in raw_list:
            try:
                activity_id = item.get("activityID")
                start = _parse_dt(item.get("startTime"))
                if not activity_id or start is None:
                    continue
                analyses = []
                for a_raw in item.get("cmeAnalyses") or []:
                    analysis = _parse_cme_analysis(a_raw)
                    if analysis is not None:
                        analyses.append(analysis)
                results.append(
                    CMEEvent(
                        activity_id=str(activity_id),
                        start_time=start,
                        source_location=item.get("sourceLocation") or None,
                        active_region_num=item.get("activeRegionNum"),
                        note=item.get("note") or None,
                        analyses=analyses,
                        linked_events=_linked_events(item.get("linkedEvents")),
                        link=item.get("link"),
                        source=_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed CME event", exc_info=True)
        return results

    async def get_geomagnetic_storms(self, lookback_days: int = 7) -> list[GeomagneticStormEvent]:
        """Fetch GST (geomagnetic storm) events."""
        raw_list = await self._get("/GST", _date_params(lookback_days))
        results: list[GeomagneticStormEvent] = []
        for item in raw_list:
            try:
                gst_id = item.get("gstID")
                start = _parse_dt(item.get("startTime"))
                if not gst_id or start is None:
                    continue
                kp_readings = []
                for kp_raw in item.get("allKpIndex") or []:
                    obs_time = _parse_dt(kp_raw.get("observedTime"))
                    kp_val = kp_raw.get("kpIndex")
                    if obs_time is not None and kp_val is not None:
                        kp_readings.append(
                            ObservedKpPoint(
                                observed_time=obs_time,
                                kp_index=float(kp_val),
                                kp_source=kp_raw.get("source"),
                            )
                        )
                results.append(
                    GeomagneticStormEvent(
                        gst_id=str(gst_id),
                        start_time=start,
                        observed_kp_readings=kp_readings,
                        linked_events=_linked_events(item.get("linkedEvents")),
                        link=item.get("link"),
                        source=_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed GST event", exc_info=True)
        return results

    async def get_sep_events(self, lookback_days: int = 7) -> list[SEPEvent]:
        """
        Fetch SEP (Solar Energetic Particle) events.

        Returns event records only — NOT numerical flux measurements.
        The instrument field names the detector or model that triggered the event.
        For numerical proton flux use NOAASWPCClient.get_proton_flux().
        """
        raw_list = await self._get("/SEP", _date_params(lookback_days))
        results: list[SEPEvent] = []
        for item in raw_list:
            try:
                sep_id = item.get("sepID")
                event_time = _parse_dt(item.get("eventTime"))
                if not sep_id or event_time is None:
                    continue
                instruments = [
                    instr["displayName"]
                    for instr in (item.get("instruments") or [])
                    if instr.get("displayName")
                ]
                results.append(
                    SEPEvent(
                        sep_id=str(sep_id),
                        event_time=event_time,
                        instruments=instruments,
                        linked_events=_linked_events(item.get("linkedEvents")),
                        link=item.get("link"),
                        source=_SOURCE,
                    )
                )
            except Exception:
                logger.warning("Skipping malformed SEP event", exc_info=True)
        return results

    async def _get(self, path: str, params: dict) -> list[dict]:
        """
        Execute a GET request against the DONKI API.

        Returns a list of raw dicts (DONKI always returns a JSON array).
        Raises DataSourceUnavailableError on network or HTTP failure.
        """
        url = f"{_BASE_URL}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                # DONKI returns null for date ranges with no events.
                if data is None:
                    return []
                if not isinstance(data, list):
                    logger.warning("DONKI %s returned unexpected type: %s", path, type(data))
                    return []
                return data
        except httpx.TimeoutException as exc:
            raise DataSourceUnavailableError(
                source="NASA DONKI", detail=f"Request timed out for {path}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise DataSourceUnavailableError(
                source="NASA DONKI",
                detail=f"HTTP {exc.response.status_code} for {path}",
            ) from exc
        except httpx.RequestError as exc:
            raise DataSourceUnavailableError(
                source="NASA DONKI", detail=f"Network error for {path}"
            ) from exc
