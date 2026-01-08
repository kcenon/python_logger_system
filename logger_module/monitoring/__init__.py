"""
Monitoring module for logger metrics and health checks

Provides comprehensive monitoring integration for observability
platforms including Prometheus, Datadog, and CloudWatch.

Example:
    from logger_module import LoggerBuilder
    from logger_module.monitoring import (
        PrometheusMonitor,
        HealthChecker,
        LoggerMetrics
    )

    # Create with Prometheus monitoring
    monitor = PrometheusMonitor(prefix="myapp_logger")

    logger = (LoggerBuilder()
        .with_console()
        .with_monitoring(monitor, metrics_enabled=True)
        .build())

    # Health check
    health = HealthChecker(logger)
    result = health.check()
    print(f"Status: {result.status.value}")
"""

from logger_module.monitoring.metrics import LoggerMetrics, MetricsCollector
from logger_module.monitoring.monitor import (
    Monitor,
    NullMonitor,
    InMemoryMonitor,
)
from logger_module.monitoring.health_checker import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    LivenessChecker,
    ReadinessChecker,
)

# Optional monitors (may raise ImportError if dependencies not installed)
try:
    from logger_module.monitoring.prometheus_monitor import (
        PrometheusMonitor,
        HAS_PROMETHEUS,
    )
except ImportError:
    PrometheusMonitor = None
    HAS_PROMETHEUS = False

try:
    from logger_module.monitoring.prometheus_monitor import StatsdMonitor
except ImportError:
    StatsdMonitor = None

__all__ = [
    # Core metrics
    "LoggerMetrics",
    "MetricsCollector",
    # Monitor interfaces
    "Monitor",
    "NullMonitor",
    "InMemoryMonitor",
    # Optional monitors
    "PrometheusMonitor",
    "StatsdMonitor",
    "HAS_PROMETHEUS",
    # Health checks
    "HealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    "LivenessChecker",
    "ReadinessChecker",
]
