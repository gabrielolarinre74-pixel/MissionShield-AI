"""
MissionShield AI — domain exception types.

These are raised by clients and services and caught at the route layer.
They never expose raw HTTP errors, credentials, or stack traces to callers.
"""

from __future__ import annotations


class MissionShieldError(Exception):
    """Base class for all MissionShield domain errors."""


class DataSourceUnavailableError(MissionShieldError):
    """
    Raised when an external data source (NASA DONKI, NOAA SWPC) cannot be
    reached or returns an unrecoverable error response.

    Attributes:
        source: Human-readable name of the failing source, e.g. "NASA DONKI".
        detail: Optional additional context (never include credentials).
    """

    def __init__(self, source: str, detail: str = "") -> None:
        self.source = source
        self.detail = detail
        super().__init__(f"Data source unavailable: {source}" + (f" — {detail}" if detail else ""))


class PartialDataError(MissionShieldError):
    """
    Raised when some but not all data sources failed.
    Callers may still return partial results but must mark freshness accordingly.
    """

    def __init__(self, failed_sources: list[str], detail: str = "") -> None:
        self.failed_sources = failed_sources
        self.detail = detail
        super().__init__(
            f"Partial data: sources unavailable: {', '.join(failed_sources)}"
            + (f" — {detail}" if detail else "")
        )


class ConfigurationError(MissionShieldError):
    """Raised when required configuration is missing or invalid."""
