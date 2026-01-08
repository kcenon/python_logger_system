"""
Logger metrics collection and aggregation

Equivalent to C++ monitoring_interface.h
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import threading
import time

from logger_module.core.log_level import LogLevel


@dataclass
class LoggerMetrics:
    """
    Metrics collected by the logger.

    Contains counters, gauges, and timing information
    for monitoring logger performance and behavior.
    """

    # Message counts
    total_messages: int = 0
    messages_by_level: Dict[LogLevel, int] = field(default_factory=dict)

    # Queue metrics (for async mode)
    queue_depth: int = 0
    queue_max_depth: int = 0
    dropped_messages: int = 0

    # Performance metrics
    messages_per_second: float = 0.0
    avg_write_latency_ms: float = 0.0
    max_write_latency_ms: float = 0.0
    p99_write_latency_ms: float = 0.0

    # Writer metrics
    writer_errors: int = 0
    writer_retries: int = 0
    bytes_written: int = 0

    # Timing
    started_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """
        Convert to dictionary for JSON export.

        Returns:
            Dictionary representation of metrics
        """
        return {
            "total_messages": self.total_messages,
            "messages_by_level": {k.name: v for k, v in self.messages_by_level.items()},
            "queue_depth": self.queue_depth,
            "queue_max_depth": self.queue_max_depth,
            "dropped_messages": self.dropped_messages,
            "messages_per_second": self.messages_per_second,
            "avg_write_latency_ms": self.avg_write_latency_ms,
            "max_write_latency_ms": self.max_write_latency_ms,
            "p99_write_latency_ms": self.p99_write_latency_ms,
            "writer_errors": self.writer_errors,
            "writer_retries": self.writer_retries,
            "bytes_written": self.bytes_written,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
        }


class MetricsCollector:
    """
    Collects and aggregates logger metrics.

    Thread-safe metrics collection with support for
    rate calculation and latency tracking.
    """

    def __init__(self, rate_window_seconds: int = 60):
        """
        Initialize metrics collector.

        Args:
            rate_window_seconds: Time window for rate calculation
        """
        self._metrics = LoggerMetrics(started_at=datetime.now())
        self._lock = threading.Lock()
        self._latency_samples: List[float] = []
        self._max_samples = 1000
        self._rate_window: List[tuple] = []  # (timestamp, count) pairs
        self._rate_window_seconds = rate_window_seconds

    def record_message(self, level: LogLevel, latency_ms: float = 0.0) -> None:
        """
        Record a logged message.

        Args:
            level: Log level of the message
            latency_ms: Write latency in milliseconds
        """
        with self._lock:
            self._metrics.total_messages += 1
            self._metrics.messages_by_level[level] = (
                self._metrics.messages_by_level.get(level, 0) + 1
            )
            self._metrics.last_message_at = datetime.now()

            # Track latency
            if latency_ms > 0:
                self._latency_samples.append(latency_ms)
                if len(self._latency_samples) > self._max_samples:
                    self._latency_samples = self._latency_samples[-self._max_samples:]

            # Update rate tracking
            self._update_rate()

    def record_dropped(self, count: int = 1) -> None:
        """
        Record dropped messages.

        Args:
            count: Number of dropped messages
        """
        with self._lock:
            self._metrics.dropped_messages += count

    def record_queue_depth(self, depth: int) -> None:
        """
        Record current queue depth.

        Args:
            depth: Current queue depth
        """
        with self._lock:
            self._metrics.queue_depth = depth
            if depth > self._metrics.queue_max_depth:
                self._metrics.queue_max_depth = depth

    def record_writer_error(self) -> None:
        """Record a writer error."""
        with self._lock:
            self._metrics.writer_errors += 1

    def record_writer_retry(self) -> None:
        """Record a writer retry."""
        with self._lock:
            self._metrics.writer_retries += 1

    def record_bytes_written(self, count: int) -> None:
        """
        Record bytes written.

        Args:
            count: Number of bytes written
        """
        with self._lock:
            self._metrics.bytes_written += count

    def _update_rate(self) -> None:
        """Update message rate calculation."""
        now = time.time()
        self._rate_window.append((now, 1))

        # Remove old entries
        cutoff = now - self._rate_window_seconds
        self._rate_window = [
            (ts, cnt) for ts, cnt in self._rate_window if ts > cutoff
        ]

        # Calculate rate
        if self._rate_window:
            total = sum(cnt for _, cnt in self._rate_window)
            time_span = now - self._rate_window[0][0]
            if time_span > 0:
                self._metrics.messages_per_second = total / time_span

    def _calculate_percentile(self, percentile: float) -> float:
        """
        Calculate a percentile from latency samples.

        Args:
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value in milliseconds
        """
        if not self._latency_samples:
            return 0.0

        sorted_samples = sorted(self._latency_samples)
        index = int(len(sorted_samples) * percentile / 100)
        index = min(index, len(sorted_samples) - 1)
        return sorted_samples[index]

    def get_metrics(self) -> LoggerMetrics:
        """
        Get current metrics snapshot.

        Returns:
            Copy of current LoggerMetrics
        """
        with self._lock:
            # Calculate latency statistics
            avg_latency = 0.0
            max_latency = 0.0
            p99_latency = 0.0

            if self._latency_samples:
                avg_latency = sum(self._latency_samples) / len(self._latency_samples)
                max_latency = max(self._latency_samples)
                p99_latency = self._calculate_percentile(99)

            # Create metrics copy with calculated values
            return LoggerMetrics(
                total_messages=self._metrics.total_messages,
                messages_by_level=dict(self._metrics.messages_by_level),
                queue_depth=self._metrics.queue_depth,
                queue_max_depth=self._metrics.queue_max_depth,
                dropped_messages=self._metrics.dropped_messages,
                messages_per_second=self._metrics.messages_per_second,
                avg_write_latency_ms=avg_latency,
                max_write_latency_ms=max_latency,
                p99_write_latency_ms=p99_latency,
                writer_errors=self._metrics.writer_errors,
                writer_retries=self._metrics.writer_retries,
                bytes_written=self._metrics.bytes_written,
                started_at=self._metrics.started_at,
                last_message_at=self._metrics.last_message_at,
            )

    def reset(self) -> None:
        """Reset all metrics to initial values."""
        with self._lock:
            self._metrics = LoggerMetrics(started_at=datetime.now())
            self._latency_samples.clear()
            self._rate_window.clear()
