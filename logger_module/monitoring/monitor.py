"""
Monitor protocol interface for monitoring backends

Defines the interface for exporting metrics to various
monitoring systems (Prometheus, Datadog, StatsD, etc.)
"""

from __future__ import annotations
from typing import Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class Monitor(Protocol):
    """
    Interface for monitoring backends.

    Implementations export metrics to external monitoring
    systems like Prometheus, Datadog, or CloudWatch.

    Example:
        class MyMonitor:
            def record_counter(self, name, value, tags=None):
                # Export counter to monitoring system
                pass

            def record_gauge(self, name, value, tags=None):
                # Export gauge to monitoring system
                pass

            def record_histogram(self, name, value, tags=None):
                # Export histogram to monitoring system
                pass
    """

    def record_counter(
        self,
        name: str,
        value: int,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a counter metric.

        Counters are cumulative metrics that only increase.
        Examples: total messages logged, total errors.

        Args:
            name: Metric name
            value: Counter value (increment)
            tags: Optional metric tags/labels
        """
        ...

    def record_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a gauge metric.

        Gauges represent a single numeric value that can
        increase or decrease. Examples: queue depth, rate.

        Args:
            name: Metric name
            value: Gauge value
            tags: Optional metric tags/labels
        """
        ...

    def record_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a histogram/distribution metric.

        Histograms track the distribution of values over time.
        Examples: write latency, message size.

        Args:
            name: Metric name
            value: Observation value
            tags: Optional metric tags/labels
        """
        ...


class NullMonitor:
    """
    No-op monitor implementation.

    Used when monitoring is disabled or not configured.
    All methods are no-ops with minimal overhead.
    """

    def record_counter(
        self,
        name: str,
        value: int,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op counter."""
        pass

    def record_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op gauge."""
        pass

    def record_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """No-op histogram."""
        pass


class InMemoryMonitor:
    """
    In-memory monitor for testing.

    Stores all metrics in memory for later inspection.
    Useful for unit tests and debugging.
    """

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}

    def record_counter(
        self,
        name: str,
        value: int,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record counter in memory."""
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def record_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record gauge in memory."""
        key = self._make_key(name, tags)
        self._gauges[key] = value

    def record_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record histogram value in memory."""
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def _make_key(
        self,
        name: str,
        tags: Optional[Dict[str, str]]
    ) -> str:
        """Create unique key from name and tags."""
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{name}{{{tag_str}}}"
        return name

    def get_counter(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> int:
        """Get counter value."""
        key = self._make_key(name, tags)
        return self._counters.get(key, 0)

    def get_gauge(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> float:
        """Get gauge value."""
        key = self._make_key(name, tags)
        return self._gauges.get(key, 0.0)

    def get_histogram(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> list:
        """Get histogram values."""
        key = self._make_key(name, tags)
        return self._histograms.get(key, [])

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
