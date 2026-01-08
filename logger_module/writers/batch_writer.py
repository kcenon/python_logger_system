"""
Batch writer for improved I/O performance

Buffers log entries and writes them in batches to reduce syscall overhead.
Essential for high-throughput logging scenarios.

Equivalent to C++ batch_writer.h
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from logger_module.core.log_entry import LogEntry


@dataclass
class BatchStats:
    """
    Statistics for batch writing monitoring.

    Tracks batch counts, buffer usage, and flush metrics.
    """

    entries_written: int = 0
    entries_dropped: int = 0
    batches_flushed: int = 0
    total_flush_time_ms: float = 0.0
    last_flush_time: Optional[datetime] = None
    buffer_overflows: int = 0
    current_buffer_size: int = 0
    max_buffer_size_reached: int = 0

    def record_write(self) -> None:
        """Record a successful entry write to buffer."""
        self.entries_written += 1

    def record_drop(self) -> None:
        """Record a dropped entry due to buffer overflow."""
        self.entries_dropped += 1
        self.buffer_overflows += 1

    def record_flush(self, batch_size: int, flush_time_ms: float) -> None:
        """Record a batch flush operation."""
        self.batches_flushed += 1
        self.total_flush_time_ms += flush_time_ms
        self.last_flush_time = datetime.now()

    def update_buffer_size(self, size: int) -> None:
        """Update current buffer size tracking."""
        self.current_buffer_size = size
        if size > self.max_buffer_size_reached:
            self.max_buffer_size_reached = size

    def to_dict(self) -> dict:
        """Convert stats to dictionary for serialization."""
        return {
            "entries_written": self.entries_written,
            "entries_dropped": self.entries_dropped,
            "batches_flushed": self.batches_flushed,
            "total_flush_time_ms": self.total_flush_time_ms,
            "average_flush_time_ms": (
                self.total_flush_time_ms / self.batches_flushed
                if self.batches_flushed > 0
                else 0.0
            ),
            "last_flush_time": (
                self.last_flush_time.isoformat()
                if self.last_flush_time
                else None
            ),
            "buffer_overflows": self.buffer_overflows,
            "current_buffer_size": self.current_buffer_size,
            "max_buffer_size_reached": self.max_buffer_size_reached,
        }


class BatchWriter:
    """
    Writer that batches log entries for efficient I/O.

    This wrapper buffers incoming log entries and writes them in batches
    to the inner writer, reducing syscall overhead and improving throughput
    for high-volume logging scenarios.

    Features:
    - Configurable batch size threshold
    - Periodic flush timer for stale entries
    - Buffer overflow protection
    - Thread-safe operations
    - Graceful shutdown with final flush

    Thread Safety:
        This class is thread-safe. All public methods use internal locking.

    Example:
        file_writer = FileWriter("app.log")
        batch_writer = BatchWriter(
            file_writer,
            max_batch_size=100,
            flush_interval=timedelta(seconds=1)
        )
        logger = LoggerBuilder().add_writer(batch_writer).build()
    """

    def __init__(
        self,
        inner_writer: Any,
        max_batch_size: int = 100,
        flush_interval: Optional[timedelta] = None,
        max_buffer_size: int = 10000,
    ):
        """
        Initialize batch writer.

        Args:
            inner_writer: Writer to wrap (must have write/flush methods)
            max_batch_size: Maximum entries before triggering batch flush
            flush_interval: Time interval for periodic flush (default: 1 second)
            max_buffer_size: Maximum buffer capacity before dropping entries
        """
        self.inner_writer = inner_writer
        self.max_batch_size = max_batch_size
        self.flush_interval = flush_interval or timedelta(seconds=1)
        self.max_buffer_size = max_buffer_size

        self._buffer: List["LogEntry"] = []
        self._lock = threading.Lock()
        self._stats = BatchStats()
        self._last_flush = datetime.now()
        self._flush_timer: Optional[threading.Timer] = None
        self._closed = False
        self._timer_lock = threading.Lock()

        self._schedule_flush()

    def write(self, entry: "LogEntry") -> None:
        """
        Write log entry to buffer.

        Entry is added to the buffer and flushed when batch size is reached
        or when the flush interval expires.

        Args:
            entry: Log entry to write
        """
        if self._closed:
            return

        with self._lock:
            if len(self._buffer) >= self.max_buffer_size:
                self._stats.record_drop()
                return

            self._buffer.append(entry)
            self._stats.record_write()
            self._stats.update_buffer_size(len(self._buffer))

            if len(self._buffer) >= self.max_batch_size:
                self._flush_batch()

    def flush(self) -> None:
        """Flush buffered entries to inner writer."""
        if self._closed:
            return

        with self._lock:
            self._flush_batch()

    def _flush_batch(self) -> None:
        """
        Flush current batch to inner writer.

        Caller must hold lock.
        """
        if not self._buffer:
            return

        start_time = time.perf_counter()
        batch = self._buffer
        self._buffer = []

        for entry in batch:
            try:
                self.inner_writer.write(entry)
            except Exception:
                pass  # Best effort - don't lose other entries

        if hasattr(self.inner_writer, 'flush'):
            try:
                self.inner_writer.flush()
            except Exception:
                pass  # Best effort

        flush_time_ms = (time.perf_counter() - start_time) * 1000
        self._stats.record_flush(len(batch), flush_time_ms)
        self._stats.update_buffer_size(0)
        self._last_flush = datetime.now()

    def _schedule_flush(self) -> None:
        """Schedule next periodic flush."""
        with self._timer_lock:
            if self._closed:
                return

            self._flush_timer = threading.Timer(
                self.flush_interval.total_seconds(),
                self._periodic_flush
            )
            self._flush_timer.daemon = True
            self._flush_timer.start()

    def _periodic_flush(self) -> None:
        """Called periodically to flush stale entries."""
        if self._closed:
            return

        with self._lock:
            if self._buffer:
                self._flush_batch()

        self._schedule_flush()

    def _cancel_timer(self) -> None:
        """Cancel the periodic flush timer."""
        with self._timer_lock:
            if self._flush_timer:
                self._flush_timer.cancel()
                self._flush_timer = None

    def close(self) -> None:
        """Close writer and flush remaining entries."""
        if self._closed:
            return

        self._closed = True
        self._cancel_timer()

        with self._lock:
            self._flush_batch()

        if hasattr(self.inner_writer, 'close'):
            self.inner_writer.close()

    def get_stats(self) -> BatchStats:
        """
        Get batch statistics.

        Returns:
            Copy of current batch statistics
        """
        with self._lock:
            return BatchStats(
                entries_written=self._stats.entries_written,
                entries_dropped=self._stats.entries_dropped,
                batches_flushed=self._stats.batches_flushed,
                total_flush_time_ms=self._stats.total_flush_time_ms,
                last_flush_time=self._stats.last_flush_time,
                buffer_overflows=self._stats.buffer_overflows,
                current_buffer_size=self._stats.current_buffer_size,
                max_buffer_size_reached=self._stats.max_buffer_size_reached,
            )

    def get_buffer_size(self) -> int:
        """
        Get current buffer size.

        Returns:
            Number of entries currently in buffer
        """
        with self._lock:
            return len(self._buffer)

    def __enter__(self) -> "BatchWriter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


class AdaptiveBatchWriter(BatchWriter):
    """
    BatchWriter that adapts batch size based on throughput.

    Automatically adjusts batch size to optimize performance based on
    the observed write rate. Higher throughput leads to larger batches,
    while lower throughput uses smaller batches for better latency.

    Features:
    - Dynamic batch size adjustment
    - Throughput monitoring with sliding window
    - Configurable min/max batch size bounds
    - All features of BatchWriter

    Thread Safety:
        This class is thread-safe. All public methods use internal locking.

    Example:
        file_writer = FileWriter("app.log")
        adaptive_writer = AdaptiveBatchWriter(
            file_writer,
            min_batch_size=10,
            max_batch_size=500,
            target_latency_ms=100
        )
        logger = LoggerBuilder().add_writer(adaptive_writer).build()
    """

    # Throughput thresholds for batch size adjustment
    HIGH_THROUGHPUT_THRESHOLD = 1000  # entries/second
    LOW_THROUGHPUT_THRESHOLD = 100    # entries/second

    def __init__(
        self,
        inner_writer: Any,
        min_batch_size: int = 10,
        max_batch_size: int = 500,
        initial_batch_size: int = 100,
        flush_interval: Optional[timedelta] = None,
        max_buffer_size: int = 10000,
        rate_window_seconds: int = 60,
        target_latency_ms: float = 100.0,
    ):
        """
        Initialize adaptive batch writer.

        Args:
            inner_writer: Writer to wrap (must have write/flush methods)
            min_batch_size: Minimum batch size limit
            max_batch_size: Maximum batch size limit
            initial_batch_size: Starting batch size
            flush_interval: Time interval for periodic flush
            max_buffer_size: Maximum buffer capacity
            rate_window_seconds: Time window for rate calculation
            target_latency_ms: Target latency for batch writes
        """
        super().__init__(
            inner_writer=inner_writer,
            max_batch_size=initial_batch_size,
            flush_interval=flush_interval,
            max_buffer_size=max_buffer_size,
        )

        self.min_batch_size = min_batch_size
        self._max_batch_size_limit = max_batch_size
        self.rate_window_seconds = rate_window_seconds
        self.target_latency_ms = target_latency_ms

        self._write_timestamps: List[float] = []
        self._recent_rates: List[float] = []
        self._last_adjustment = time.time()
        self._adjustment_interval = 5.0  # Adjust every 5 seconds

    def write(self, entry: "LogEntry") -> None:
        """
        Write log entry with throughput tracking.

        Args:
            entry: Log entry to write
        """
        if self._closed:
            return

        current_time = time.time()

        with self._lock:
            self._write_timestamps.append(current_time)
            self._cleanup_old_timestamps(current_time)

            if current_time - self._last_adjustment >= self._adjustment_interval:
                self._update_batch_size()
                self._last_adjustment = current_time

        super().write(entry)

    def _cleanup_old_timestamps(self, current_time: float) -> None:
        """
        Remove timestamps outside the rate window.

        Caller must hold lock.
        """
        cutoff = current_time - self.rate_window_seconds
        while self._write_timestamps and self._write_timestamps[0] < cutoff:
            self._write_timestamps.pop(0)

    def _calculate_current_rate(self) -> float:
        """
        Calculate current write rate in entries/second.

        Caller must hold lock.

        Returns:
            Current throughput rate
        """
        if len(self._write_timestamps) < 2:
            return 0.0

        time_span = self._write_timestamps[-1] - self._write_timestamps[0]
        if time_span <= 0:
            return 0.0

        return len(self._write_timestamps) / time_span

    def _update_batch_size(self) -> None:
        """
        Adjust batch size based on recent throughput.

        Caller must hold lock.
        """
        current_rate = self._calculate_current_rate()
        self._recent_rates.append(current_rate)

        # Keep only recent rate samples
        max_samples = 12  # 1 minute worth at 5-second intervals
        if len(self._recent_rates) > max_samples:
            self._recent_rates = self._recent_rates[-max_samples:]

        if not self._recent_rates:
            return

        avg_rate = sum(self._recent_rates) / len(self._recent_rates)

        # Adjust batch size based on throughput
        if avg_rate > self.HIGH_THROUGHPUT_THRESHOLD:
            # High throughput: increase batch size for efficiency
            new_size = min(
                self._max_batch_size_limit,
                int(self.max_batch_size * 1.5)
            )
        elif avg_rate < self.LOW_THROUGHPUT_THRESHOLD:
            # Low throughput: decrease batch size for lower latency
            new_size = max(
                self.min_batch_size,
                int(self.max_batch_size * 0.75)
            )
        else:
            # Medium throughput: maintain current size
            return

        self.max_batch_size = new_size

    def get_current_rate(self) -> float:
        """
        Get current write rate.

        Returns:
            Current throughput in entries/second
        """
        with self._lock:
            return self._calculate_current_rate()

    def get_average_rate(self) -> float:
        """
        Get average write rate over recent window.

        Returns:
            Average throughput in entries/second
        """
        with self._lock:
            if not self._recent_rates:
                return 0.0
            return sum(self._recent_rates) / len(self._recent_rates)

    def get_adaptive_stats(self) -> dict:
        """
        Get adaptive-specific statistics.

        Returns:
            Dictionary with adaptive batch stats
        """
        with self._lock:
            base_stats = self._stats.to_dict()
            base_stats.update({
                "current_batch_size": self.max_batch_size,
                "min_batch_size": self.min_batch_size,
                "max_batch_size_limit": self._max_batch_size_limit,
                "current_rate": self._calculate_current_rate(),
                "average_rate": (
                    sum(self._recent_rates) / len(self._recent_rates)
                    if self._recent_rates
                    else 0.0
                ),
            })
            return base_stats
