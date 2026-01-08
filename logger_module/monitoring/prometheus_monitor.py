"""
Prometheus monitor implementation

Exports logger metrics to Prometheus format using
the prometheus_client library.
"""

from __future__ import annotations
from typing import Dict, Optional

# Optional dependency
try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    Counter = None
    Gauge = None
    Histogram = None
    REGISTRY = None


class PrometheusMonitor:
    """
    Export logger metrics to Prometheus.

    Requires prometheus_client package:
        pip install prometheus-client

    Metrics are exposed via Prometheus client library
    and can be scraped by Prometheus server.

    Example:
        from logger_module.monitoring import PrometheusMonitor

        monitor = PrometheusMonitor(prefix="myapp_logger")

        # Metrics available:
        # myapp_logger_messages_total{level="INFO"}
        # myapp_logger_queue_depth
        # myapp_logger_dropped_total
        # myapp_logger_write_latency_seconds
        # myapp_logger_errors_total
    """

    def __init__(
        self,
        prefix: str = "logger",
        registry=None
    ):
        """
        Initialize Prometheus monitor.

        Args:
            prefix: Metric name prefix
            registry: Optional custom registry (uses default if None)

        Raises:
            ImportError: If prometheus_client is not installed
        """
        if not HAS_PROMETHEUS:
            raise ImportError(
                "prometheus_client not installed. "
                "Install with: pip install prometheus-client"
            )

        self._prefix = prefix
        self._registry = registry or REGISTRY

        # Message counter
        self._messages_total = Counter(
            f"{prefix}_messages_total",
            "Total log messages",
            ["level"],
            registry=self._registry
        )

        # Queue depth gauge
        self._queue_depth = Gauge(
            f"{prefix}_queue_depth",
            "Current async queue depth",
            registry=self._registry
        )

        # Dropped messages counter
        self._dropped_total = Counter(
            f"{prefix}_dropped_total",
            "Total dropped messages",
            registry=self._registry
        )

        # Write latency histogram
        self._write_latency = Histogram(
            f"{prefix}_write_latency_seconds",
            "Log write latency in seconds",
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
            registry=self._registry
        )

        # Writer errors counter
        self._errors_total = Counter(
            f"{prefix}_errors_total",
            "Total writer errors",
            registry=self._registry
        )

        # Bytes written counter
        self._bytes_written = Counter(
            f"{prefix}_bytes_written_total",
            "Total bytes written",
            registry=self._registry
        )

        # Messages per second gauge
        self._messages_rate = Gauge(
            f"{prefix}_messages_per_second",
            "Current message rate",
            registry=self._registry
        )

    def record_counter(
        self,
        name: str,
        value: int,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a counter metric.

        Args:
            name: Metric name
            value: Counter increment
            tags: Optional labels
        """
        if name == "messages":
            level = tags.get("level", "unknown") if tags else "unknown"
            self._messages_total.labels(level=level).inc(value)
        elif name == "dropped":
            self._dropped_total.inc(value)
        elif name == "errors":
            self._errors_total.inc(value)
        elif name == "bytes_written":
            self._bytes_written.inc(value)

    def record_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a gauge metric.

        Args:
            name: Metric name
            value: Gauge value
            tags: Optional labels
        """
        if name == "queue_depth":
            self._queue_depth.set(value)
        elif name == "messages_per_second":
            self._messages_rate.set(value)

    def record_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a histogram metric.

        Args:
            name: Metric name
            value: Observation value
            tags: Optional labels
        """
        if name == "write_latency":
            # Convert ms to seconds for Prometheus
            self._write_latency.observe(value / 1000.0)


class StatsdMonitor:
    """
    Export logger metrics to StatsD/Datadog.

    Requires statsd package:
        pip install statsd

    Example:
        from logger_module.monitoring import StatsdMonitor

        monitor = StatsdMonitor(
            host="localhost",
            port=8125,
            prefix="myapp.logger"
        )
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "logger"
    ):
        """
        Initialize StatsD monitor.

        Args:
            host: StatsD host
            port: StatsD port
            prefix: Metric name prefix

        Raises:
            ImportError: If statsd is not installed
        """
        try:
            import statsd
        except ImportError:
            raise ImportError(
                "statsd not installed. "
                "Install with: pip install statsd"
            )

        self._client = statsd.StatsClient(
            host=host,
            port=port,
            prefix=prefix
        )

    def record_counter(
        self,
        name: str,
        value: int,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a counter metric."""
        metric_name = self._make_name(name, tags)
        self._client.incr(metric_name, value)

    def record_gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a gauge metric."""
        metric_name = self._make_name(name, tags)
        self._client.gauge(metric_name, value)

    def record_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a histogram/timing metric."""
        metric_name = self._make_name(name, tags)
        self._client.timing(metric_name, value)

    def _make_name(
        self,
        name: str,
        tags: Optional[Dict[str, str]]
    ) -> str:
        """Create metric name with tags."""
        if tags:
            tag_parts = [f"{k}.{v}" for k, v in sorted(tags.items())]
            return f"{name}.{'.'.join(tag_parts)}"
        return name
