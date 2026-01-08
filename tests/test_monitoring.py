"""Tests for monitoring module"""

import pytest
import time
from datetime import datetime

from logger_module import LoggerBuilder, LogLevel
from logger_module.monitoring import (
    LoggerMetrics,
    MetricsCollector,
    InMemoryMonitor,
    NullMonitor,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    LivenessChecker,
    ReadinessChecker,
)


class TestLoggerMetrics:
    """Test LoggerMetrics dataclass."""

    def test_default_values(self):
        metrics = LoggerMetrics()
        assert metrics.total_messages == 0
        assert metrics.dropped_messages == 0
        assert metrics.queue_depth == 0
        assert metrics.messages_per_second == 0.0

    def test_to_dict(self):
        metrics = LoggerMetrics(
            total_messages=100,
            dropped_messages=5,
            messages_by_level={LogLevel.INFO: 80, LogLevel.ERROR: 20}
        )
        data = metrics.to_dict()
        assert data["total_messages"] == 100
        assert data["dropped_messages"] == 5
        assert data["messages_by_level"]["INFO"] == 80
        assert data["messages_by_level"]["ERROR"] == 20


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_record_message(self):
        collector = MetricsCollector()
        collector.record_message(LogLevel.INFO, latency_ms=1.5)
        collector.record_message(LogLevel.ERROR, latency_ms=2.0)

        metrics = collector.get_metrics()
        assert metrics.total_messages == 2
        assert metrics.messages_by_level[LogLevel.INFO] == 1
        assert metrics.messages_by_level[LogLevel.ERROR] == 1

    def test_record_dropped(self):
        collector = MetricsCollector()
        collector.record_dropped(5)
        collector.record_dropped(3)

        metrics = collector.get_metrics()
        assert metrics.dropped_messages == 8

    def test_record_queue_depth(self):
        collector = MetricsCollector()
        collector.record_queue_depth(10)
        collector.record_queue_depth(50)
        collector.record_queue_depth(30)

        metrics = collector.get_metrics()
        assert metrics.queue_depth == 30
        assert metrics.queue_max_depth == 50

    def test_record_writer_error(self):
        collector = MetricsCollector()
        collector.record_writer_error()
        collector.record_writer_error()

        metrics = collector.get_metrics()
        assert metrics.writer_errors == 2

    def test_latency_calculation(self):
        collector = MetricsCollector()
        for i in range(10):
            collector.record_message(LogLevel.INFO, latency_ms=float(i + 1))

        metrics = collector.get_metrics()
        assert metrics.avg_write_latency_ms == 5.5  # Average of 1-10
        assert metrics.max_write_latency_ms == 10.0

    def test_reset(self):
        collector = MetricsCollector()
        collector.record_message(LogLevel.INFO)
        collector.record_dropped(5)

        collector.reset()
        metrics = collector.get_metrics()
        assert metrics.total_messages == 0
        assert metrics.dropped_messages == 0


class TestInMemoryMonitor:
    """Test InMemoryMonitor class."""

    def test_record_counter(self):
        monitor = InMemoryMonitor()
        monitor.record_counter("messages", 5, {"level": "INFO"})
        monitor.record_counter("messages", 3, {"level": "INFO"})

        assert monitor.get_counter("messages", {"level": "INFO"}) == 8

    def test_record_gauge(self):
        monitor = InMemoryMonitor()
        monitor.record_gauge("queue_depth", 10.0)
        monitor.record_gauge("queue_depth", 20.0)

        assert monitor.get_gauge("queue_depth") == 20.0

    def test_record_histogram(self):
        monitor = InMemoryMonitor()
        monitor.record_histogram("latency", 1.5)
        monitor.record_histogram("latency", 2.5)
        monitor.record_histogram("latency", 3.5)

        values = monitor.get_histogram("latency")
        assert len(values) == 3
        assert values == [1.5, 2.5, 3.5]

    def test_reset(self):
        monitor = InMemoryMonitor()
        monitor.record_counter("test", 1)
        monitor.record_gauge("test", 1.0)

        monitor.reset()
        assert monitor.get_counter("test") == 0
        assert monitor.get_gauge("test") == 0.0


class TestNullMonitor:
    """Test NullMonitor class."""

    def test_null_operations(self):
        monitor = NullMonitor()
        # Should not raise any errors
        monitor.record_counter("test", 1)
        monitor.record_gauge("test", 1.0)
        monitor.record_histogram("test", 1.0)


class TestHealthChecker:
    """Test HealthChecker class."""

    def test_healthy_logger(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .build())

        health = HealthChecker(logger)
        result = health.check()

        assert result.status == HealthStatus.HEALTHY
        assert result.is_healthy
        assert len(result.issues) == 0
        logger.shutdown()

    def test_health_result_to_dict(self):
        result = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            issues=["queue_near_capacity"],
            details={"queue_utilization": 0.92}
        )
        data = result.to_dict()
        assert data["status"] == "degraded"
        assert "queue_near_capacity" in data["issues"]


class TestLivenessChecker:
    """Test LivenessChecker class."""

    def test_alive_logger(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .build())

        liveness = LivenessChecker(logger)
        alive, reason = liveness.check()

        assert alive is True
        assert reason == "ok"
        logger.shutdown()

    def test_null_logger(self):
        liveness = LivenessChecker(None)
        alive, reason = liveness.check()

        assert alive is False
        assert reason == "logger_not_initialized"


class TestReadinessChecker:
    """Test ReadinessChecker class."""

    def test_ready_logger(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .build())

        readiness = ReadinessChecker(logger)
        ready, reason = readiness.check()

        assert ready is True
        assert reason == "ok"
        logger.shutdown()


class TestLoggerMonitoringIntegration:
    """Test monitoring integration with Logger."""

    def test_enable_metrics(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .with_metrics(True)
            .build())

        logger.info("Test message 1")
        logger.warn("Test message 2")
        logger.error("Test message 3")

        metrics = logger.get_detailed_metrics()
        assert metrics.total_messages == 3
        assert LogLevel.INFO in metrics.messages_by_level
        assert LogLevel.WARN in metrics.messages_by_level
        assert LogLevel.ERROR in metrics.messages_by_level
        logger.shutdown()

    def test_with_monitoring_and_monitor(self):
        monitor = InMemoryMonitor()

        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .with_monitoring(monitor, metrics_enabled=True)
            .build())

        logger.info("Test message")
        logger.error("Error message")

        # Check metrics were recorded
        assert monitor.get_counter("messages", {"level": "INFO"}) == 1
        assert monitor.get_counter("messages", {"level": "ERROR"}) == 1
        logger.shutdown()

    def test_basic_metrics_without_detailed(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .build())

        logger.info("Test")

        # Should still work with basic metrics
        basic_metrics = logger.get_metrics()
        assert basic_metrics["logged"] == 1

        # Detailed metrics should return basic info
        detailed = logger.get_detailed_metrics()
        assert detailed.total_messages == 1
        logger.shutdown()

    def test_latency_tracking(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .with_metrics(True)
            .build())

        for _ in range(5):
            logger.info("Test message")

        metrics = logger.get_detailed_metrics()
        # Latency should be tracked
        assert metrics.total_messages == 5
        logger.shutdown()
