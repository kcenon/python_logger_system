"""
Health check functionality for logger monitoring

Provides health status checks for monitoring logger
system health and detecting issues.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from logger_module.core.logger import Logger
    from logger_module.monitoring.metrics import LoggerMetrics


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """
    Result of a health check.

    Contains status, issues found, and details about
    the current health of the logger system.
    """
    status: HealthStatus
    issues: List[str] = field(default_factory=list)
    details: Dict[str, any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """
        Convert to dictionary for JSON export.

        Returns:
            Dictionary representation
        """
        return {
            "status": self.status.value,
            "issues": self.issues,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == HealthStatus.HEALTHY


class HealthChecker:
    """
    Check logger health status.

    Monitors queue depth, error rates, and processing
    state to determine overall health.

    Example:
        from logger_module.monitoring import HealthChecker

        health = HealthChecker(logger)
        result = health.check()

        if not result.is_healthy:
            print(f"Issues: {result.issues}")
    """

    def __init__(
        self,
        logger: "Logger",
        max_queue_depth: int = 10000,
        max_error_rate: float = 0.01,
        max_dropped_rate: float = 0.001,
        stale_threshold_seconds: int = 300
    ):
        """
        Initialize health checker.

        Args:
            logger: Logger instance to monitor
            max_queue_depth: Maximum acceptable queue depth
            max_error_rate: Maximum acceptable error rate (0-1)
            max_dropped_rate: Maximum acceptable dropped message rate (0-1)
            stale_threshold_seconds: Seconds before considering logs stale
        """
        self._logger = logger
        self.max_queue_depth = max_queue_depth
        self.max_error_rate = max_error_rate
        self.max_dropped_rate = max_dropped_rate
        self.stale_threshold = timedelta(seconds=stale_threshold_seconds)

    def check(self) -> HealthCheckResult:
        """
        Perform health check.

        Returns:
            HealthCheckResult with status and any issues found
        """
        metrics = self._get_metrics()
        issues: List[str] = []
        details: Dict[str, any] = {}

        # Check queue depth
        queue_status = self._check_queue_depth(metrics, issues, details)

        # Check error rate
        error_status = self._check_error_rate(metrics, issues, details)

        # Check dropped rate
        dropped_status = self._check_dropped_rate(metrics, issues, details)

        # Check processing state
        stale_status = self._check_processing(metrics, issues, details)

        # Determine overall status
        status = self._determine_status(
            queue_status,
            error_status,
            dropped_status,
            stale_status
        )

        # Add metrics summary to details
        details["total_messages"] = metrics.total_messages
        details["messages_per_second"] = metrics.messages_per_second
        details["queue_depth"] = metrics.queue_depth
        details["dropped_messages"] = metrics.dropped_messages
        details["writer_errors"] = metrics.writer_errors

        return HealthCheckResult(
            status=status,
            issues=issues,
            details=details
        )

    def _get_metrics(self) -> "LoggerMetrics":
        """Get metrics from logger."""
        # Try to get enhanced metrics if available
        if hasattr(self._logger, 'get_detailed_metrics'):
            return self._logger.get_detailed_metrics()

        # Fall back to basic metrics
        from logger_module.monitoring.metrics import LoggerMetrics
        basic_metrics = self._logger.get_metrics()
        return LoggerMetrics(
            total_messages=basic_metrics.get("logged", 0),
            dropped_messages=basic_metrics.get("dropped", 0),
            queue_depth=0
        )

    def _check_queue_depth(
        self,
        metrics: "LoggerMetrics",
        issues: List[str],
        details: Dict[str, any]
    ) -> HealthStatus:
        """Check queue depth status."""
        if metrics.queue_depth >= self.max_queue_depth:
            issues.append("queue_at_capacity")
            details["queue_utilization"] = 1.0
            return HealthStatus.UNHEALTHY
        elif metrics.queue_depth >= self.max_queue_depth * 0.9:
            issues.append("queue_near_capacity")
            details["queue_utilization"] = metrics.queue_depth / self.max_queue_depth
            return HealthStatus.DEGRADED
        else:
            details["queue_utilization"] = (
                metrics.queue_depth / self.max_queue_depth
                if self.max_queue_depth > 0 else 0
            )
            return HealthStatus.HEALTHY

    def _check_error_rate(
        self,
        metrics: "LoggerMetrics",
        issues: List[str],
        details: Dict[str, any]
    ) -> HealthStatus:
        """Check error rate status."""
        if metrics.total_messages == 0:
            details["error_rate"] = 0.0
            return HealthStatus.HEALTHY

        error_rate = metrics.writer_errors / metrics.total_messages
        details["error_rate"] = error_rate

        if error_rate >= self.max_error_rate:
            issues.append("high_error_rate")
            return HealthStatus.UNHEALTHY
        elif error_rate >= self.max_error_rate * 0.5:
            issues.append("elevated_error_rate")
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _check_dropped_rate(
        self,
        metrics: "LoggerMetrics",
        issues: List[str],
        details: Dict[str, any]
    ) -> HealthStatus:
        """Check dropped message rate status."""
        if metrics.total_messages == 0:
            details["dropped_rate"] = 0.0
            return HealthStatus.HEALTHY

        total = metrics.total_messages + metrics.dropped_messages
        dropped_rate = metrics.dropped_messages / total
        details["dropped_rate"] = dropped_rate

        if dropped_rate >= self.max_dropped_rate:
            issues.append("high_drop_rate")
            return HealthStatus.UNHEALTHY
        elif dropped_rate >= self.max_dropped_rate * 0.5:
            issues.append("elevated_drop_rate")
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _check_processing(
        self,
        metrics: "LoggerMetrics",
        issues: List[str],
        details: Dict[str, any]
    ) -> HealthStatus:
        """Check if processing is stalled."""
        if metrics.last_message_at is None:
            return HealthStatus.HEALTHY

        time_since_last = datetime.now() - metrics.last_message_at
        details["time_since_last_message_seconds"] = time_since_last.total_seconds()

        # Only check for stall if there are queued messages
        if metrics.queue_depth > 0 and time_since_last > self.stale_threshold:
            issues.append("processing_stalled")
            return HealthStatus.UNHEALTHY

        return HealthStatus.HEALTHY

    def _determine_status(self, *statuses: HealthStatus) -> HealthStatus:
        """Determine overall status from individual checks."""
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


class LivenessChecker:
    """
    Simple liveness check for container orchestration.

    Returns basic alive/not-alive status suitable for
    Kubernetes liveness probes.
    """

    def __init__(self, logger: "Logger"):
        """
        Initialize liveness checker.

        Args:
            logger: Logger instance to check
        """
        self._logger = logger

    def check(self) -> Tuple[bool, str]:
        """
        Check if logger is alive.

        Returns:
            Tuple of (is_alive, reason)
        """
        try:
            # Check if logger exists and can accept messages
            if self._logger is None:
                return False, "logger_not_initialized"

            # Check if shutdown
            if hasattr(self._logger, '_running'):
                if not self._logger._running and self._logger._config.async_mode:
                    return False, "logger_shutdown"

            return True, "ok"
        except Exception as e:
            return False, f"error: {str(e)}"


class ReadinessChecker:
    """
    Readiness check for container orchestration.

    Returns whether logger is ready to accept traffic.
    Suitable for Kubernetes readiness probes.
    """

    def __init__(
        self,
        logger: "Logger",
        max_queue_utilization: float = 0.9
    ):
        """
        Initialize readiness checker.

        Args:
            logger: Logger instance to check
            max_queue_utilization: Maximum queue utilization before not ready
        """
        self._logger = logger
        self.max_queue_utilization = max_queue_utilization

    def check(self) -> Tuple[bool, str]:
        """
        Check if logger is ready.

        Returns:
            Tuple of (is_ready, reason)
        """
        try:
            # Check liveness first
            liveness = LivenessChecker(self._logger)
            alive, reason = liveness.check()
            if not alive:
                return False, reason

            # Check queue capacity
            if hasattr(self._logger, '_log_queue') and self._logger._log_queue:
                queue = self._logger._log_queue
                utilization = queue.qsize() / queue.maxsize
                if utilization >= self.max_queue_utilization:
                    return False, "queue_nearly_full"

            return True, "ok"
        except Exception as e:
            return False, f"error: {str(e)}"
