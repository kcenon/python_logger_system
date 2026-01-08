"""Tests for batch writer functionality"""

import pytest
import threading
import time
from datetime import timedelta
from unittest.mock import Mock, MagicMock, patch

from logger_module import LoggerBuilder, LogLevel
from logger_module.core.log_entry import LogEntry
from logger_module.writers.batch_writer import (
    BatchStats,
    BatchWriter,
    AdaptiveBatchWriter,
)
from logger_module.writers.file_writer import FileWriter


class TestBatchStats:
    """Test batch statistics functionality."""

    def test_initial_stats(self):
        """Test default values for batch stats."""
        stats = BatchStats()
        assert stats.entries_written == 0
        assert stats.entries_dropped == 0
        assert stats.batches_flushed == 0
        assert stats.total_flush_time_ms == 0.0
        assert stats.buffer_overflows == 0
        assert stats.current_buffer_size == 0
        assert stats.max_buffer_size_reached == 0

    def test_record_write(self):
        """Test recording writes."""
        stats = BatchStats()
        stats.record_write()
        stats.record_write()

        assert stats.entries_written == 2

    def test_record_drop(self):
        """Test recording dropped entries."""
        stats = BatchStats()
        stats.record_drop()

        assert stats.entries_dropped == 1
        assert stats.buffer_overflows == 1

    def test_record_flush(self):
        """Test recording flush operations."""
        stats = BatchStats()
        stats.record_flush(10, 5.5)
        stats.record_flush(20, 3.5)

        assert stats.batches_flushed == 2
        assert stats.total_flush_time_ms == 9.0
        assert stats.last_flush_time is not None

    def test_update_buffer_size(self):
        """Test buffer size tracking."""
        stats = BatchStats()
        stats.update_buffer_size(50)
        stats.update_buffer_size(100)
        stats.update_buffer_size(75)

        assert stats.current_buffer_size == 75
        assert stats.max_buffer_size_reached == 100

    def test_to_dict(self):
        """Test serialization to dictionary."""
        stats = BatchStats()
        stats.record_write()
        stats.record_flush(10, 5.0)

        data = stats.to_dict()

        assert data["entries_written"] == 1
        assert data["batches_flushed"] == 1
        assert data["average_flush_time_ms"] == 5.0
        assert "last_flush_time" in data


class TestBatchWriter:
    """Test BatchWriter functionality."""

    def test_initialization(self):
        """Test batch writer initialization."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=50,
            flush_interval=timedelta(seconds=2),
            max_buffer_size=5000,
        )

        assert batch_writer.max_batch_size == 50
        assert batch_writer.flush_interval == timedelta(seconds=2)
        assert batch_writer.max_buffer_size == 5000

        batch_writer.close()

    def test_default_values(self):
        """Test default configuration values."""
        mock_writer = Mock()
        batch_writer = BatchWriter(mock_writer)

        assert batch_writer.max_batch_size == 100
        assert batch_writer.flush_interval == timedelta(seconds=1)
        assert batch_writer.max_buffer_size == 10000

        batch_writer.close()

    def test_write_buffers_entries(self):
        """Test that write buffers entries."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=100,
            flush_interval=timedelta(seconds=10),  # Long interval to prevent auto-flush
        )

        entry = LogEntry(level=LogLevel.INFO, message="Test message")
        batch_writer.write(entry)

        assert batch_writer.get_buffer_size() == 1
        mock_writer.write.assert_not_called()

        batch_writer.close()

    def test_flush_on_batch_size(self):
        """Test that flush occurs when batch size is reached."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        # All entries should have been flushed
        assert mock_writer.write.call_count == 5
        assert batch_writer.get_buffer_size() == 0

        batch_writer.close()

    def test_manual_flush(self):
        """Test manual flush."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=100,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(3):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        assert batch_writer.get_buffer_size() == 3
        batch_writer.flush()

        assert batch_writer.get_buffer_size() == 0
        assert mock_writer.write.call_count == 3

        batch_writer.close()

    def test_periodic_flush(self):
        """Test periodic flush timer."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=100,
            flush_interval=timedelta(milliseconds=100),
        )

        entry = LogEntry(level=LogLevel.INFO, message="Test message")
        batch_writer.write(entry)

        # Wait for periodic flush
        time.sleep(0.2)

        # Entry should have been flushed
        assert mock_writer.write.call_count >= 1

        batch_writer.close()

    def test_buffer_overflow_drops_entries(self):
        """Test that buffer overflow drops entries."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=100,
            flush_interval=timedelta(seconds=10),
            max_buffer_size=5,
        )

        # Write more entries than buffer can hold
        for i in range(10):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        stats = batch_writer.get_stats()
        assert stats.entries_dropped > 0
        assert stats.buffer_overflows > 0

        batch_writer.close()

    def test_close_flushes_remaining(self):
        """Test that close flushes remaining entries."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=100,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(3):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        batch_writer.close()

        # All entries should have been flushed on close
        assert mock_writer.write.call_count == 3
        mock_writer.close.assert_called_once()

    def test_write_after_close_ignored(self):
        """Test that writes after close are ignored."""
        mock_writer = Mock()
        batch_writer = BatchWriter(mock_writer)
        batch_writer.close()

        entry = LogEntry(level=LogLevel.INFO, message="Test message")
        batch_writer.write(entry)

        # No write should have occurred
        mock_writer.write.assert_not_called()

    def test_get_stats_returns_copy(self):
        """Test that get_stats returns a copy."""
        mock_writer = Mock()
        batch_writer = BatchWriter(mock_writer)

        stats1 = batch_writer.get_stats()
        stats2 = batch_writer.get_stats()

        stats1.entries_written = 100
        assert stats2.entries_written == 0

        batch_writer.close()

    def test_context_manager(self):
        """Test context manager protocol."""
        mock_writer = Mock()

        with BatchWriter(mock_writer) as batch_writer:
            entry = LogEntry(level=LogLevel.INFO, message="Test message")
            batch_writer.write(entry)

        # Should be closed and flushed
        mock_writer.write.assert_called_once()
        mock_writer.close.assert_called_once()

    def test_inner_writer_flush_called(self):
        """Test that inner writer flush is called after batch flush."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        mock_writer.flush.assert_called()

        batch_writer.close()

    def test_stats_tracking(self):
        """Test comprehensive stats tracking."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(12):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        stats = batch_writer.get_stats()

        assert stats.entries_written == 12
        assert stats.batches_flushed == 2  # 5 + 5, remaining 2 not flushed yet
        assert stats.total_flush_time_ms > 0

        batch_writer.close()


class TestAdaptiveBatchWriter:
    """Test AdaptiveBatchWriter functionality."""

    def test_initialization(self):
        """Test adaptive batch writer initialization."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            min_batch_size=10,
            max_batch_size=500,
            initial_batch_size=100,
        )

        assert adaptive_writer.min_batch_size == 10
        assert adaptive_writer._max_batch_size_limit == 500
        assert adaptive_writer.max_batch_size == 100

        adaptive_writer.close()

    def test_default_values(self):
        """Test default configuration values."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(mock_writer)

        assert adaptive_writer.min_batch_size == 10
        assert adaptive_writer._max_batch_size_limit == 500
        assert adaptive_writer.max_batch_size == 100
        assert adaptive_writer.rate_window_seconds == 60

        adaptive_writer.close()

    def test_write_tracks_rate(self):
        """Test that writes track throughput rate."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            max_batch_size=1000,  # High to avoid auto-flush
            flush_interval=timedelta(seconds=10),
        )

        for i in range(10):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            adaptive_writer.write(entry)

        # Should have rate tracking
        rate = adaptive_writer.get_current_rate()
        assert rate >= 0  # Rate can be calculated

        adaptive_writer.close()

    def test_batch_size_increases_high_throughput(self):
        """Test that batch size increases with high throughput."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            min_batch_size=10,
            max_batch_size=500,
            initial_batch_size=50,
            flush_interval=timedelta(seconds=10),
        )

        # Simulate high throughput
        adaptive_writer._recent_rates = [2000, 2000, 2000]
        adaptive_writer._update_batch_size()

        # Batch size should have increased
        assert adaptive_writer.max_batch_size > 50

        adaptive_writer.close()

    def test_batch_size_decreases_low_throughput(self):
        """Test that batch size decreases with low throughput."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            min_batch_size=10,
            max_batch_size=500,
            initial_batch_size=100,
            flush_interval=timedelta(seconds=10),
        )

        # Simulate low throughput
        adaptive_writer._recent_rates = [50, 50, 50]
        adaptive_writer._update_batch_size()

        # Batch size should have decreased
        assert adaptive_writer.max_batch_size < 100

        adaptive_writer.close()

    def test_batch_size_bounded_by_limits(self):
        """Test that batch size respects min/max limits."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            min_batch_size=10,
            max_batch_size=500,
            initial_batch_size=100,
            flush_interval=timedelta(seconds=10),
        )

        # Simulate very high throughput
        adaptive_writer._recent_rates = [10000] * 20
        for _ in range(10):
            adaptive_writer._update_batch_size()

        # Should not exceed max
        assert adaptive_writer.max_batch_size <= 500

        # Simulate very low throughput
        adaptive_writer._recent_rates = [1] * 20
        for _ in range(10):
            adaptive_writer._update_batch_size()

        # Should not go below min
        assert adaptive_writer.max_batch_size >= 10

        adaptive_writer.close()

    def test_get_adaptive_stats(self):
        """Test getting adaptive-specific stats."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            min_batch_size=10,
            max_batch_size=500,
            initial_batch_size=100,
        )

        stats = adaptive_writer.get_adaptive_stats()

        assert "current_batch_size" in stats
        assert "min_batch_size" in stats
        assert "max_batch_size_limit" in stats
        assert "current_rate" in stats
        assert "average_rate" in stats

        adaptive_writer.close()

    def test_inherits_batch_writer_behavior(self):
        """Test that AdaptiveBatchWriter inherits BatchWriter behavior."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            max_batch_size=500,
            initial_batch_size=5,  # Small batch for quick flush
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            adaptive_writer.write(entry)

        # Should have flushed like BatchWriter
        assert mock_writer.write.call_count == 5

        adaptive_writer.close()


class TestLoggerBuilderIntegration:
    """Test LoggerBuilder integration with batch writers."""

    def test_with_batching_basic(self):
        """Test basic batching via builder."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            logger = (LoggerBuilder()
                .with_name("batch_test")
                .with_level(LogLevel.DEBUG)
                .with_async(False)
                .with_file(log_file)
                .with_batching(max_batch_size=50, flush_interval_ms=500)
                .build())

            # Verify BatchWriter was added
            batch_writers = [
                w for w in logger._writers
                if isinstance(w, BatchWriter) and not isinstance(w, AdaptiveBatchWriter)
            ]
            assert len(batch_writers) == 1
            assert batch_writers[0].max_batch_size == 50

            logger.shutdown()

    def test_with_batching_adaptive(self):
        """Test adaptive batching via builder."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            logger = (LoggerBuilder()
                .with_name("adaptive_test")
                .with_level(LogLevel.DEBUG)
                .with_async(False)
                .with_file(log_file)
                .with_batching(
                    adaptive=True,
                    min_batch_size=10,
                    max_batch_size_limit=500,
                )
                .build())

            # Verify AdaptiveBatchWriter was added
            adaptive_writers = [
                w for w in logger._writers
                if isinstance(w, AdaptiveBatchWriter)
            ]
            assert len(adaptive_writers) == 1
            assert adaptive_writers[0].min_batch_size == 10

            logger.shutdown()

    def test_batching_with_custom_writer(self):
        """Test batching with custom writer."""
        mock_writer = Mock()

        logger = (LoggerBuilder()
            .with_name("custom_test")
            .with_level(LogLevel.DEBUG)
            .with_async(False)
            .add_writer(mock_writer)
            .with_batching(max_batch_size=10)
            .build())

        # Custom writer should be wrapped
        batch_writers = [
            w for w in logger._writers
            if isinstance(w, BatchWriter)
        ]
        assert len(batch_writers) == 1

        logger.shutdown()

    def test_batching_not_applied_to_console(self):
        """Test that batching is not applied to console writer."""
        from logger_module.writers.console_writer import ConsoleWriter

        logger = (LoggerBuilder()
            .with_name("console_test")
            .with_level(LogLevel.DEBUG)
            .with_async(False)
            .with_console()
            .with_batching(max_batch_size=10)
            .build())

        # Console writer should NOT be wrapped
        console_writers = [
            w for w in logger._writers
            if isinstance(w, ConsoleWriter)
        ]
        assert len(console_writers) == 1

        # And no BatchWriter wrapping ConsoleWriter
        batch_writers = [
            w for w in logger._writers
            if isinstance(w, BatchWriter)
        ]
        assert len(batch_writers) == 0

        logger.shutdown()


class TestThreadSafety:
    """Test thread safety of batch writers."""

    def test_concurrent_writes(self):
        """Test that concurrent writes are thread-safe."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=1000,
            flush_interval=timedelta(seconds=10),
        )

        def write_messages():
            for i in range(100):
                entry = LogEntry(level=LogLevel.INFO, message=f"Thread message {i}")
                batch_writer.write(entry)

        threads = [threading.Thread(target=write_messages) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise any exception
        stats = batch_writer.get_stats()
        assert stats.entries_written == 500

        batch_writer.close()

    def test_concurrent_writes_and_flush(self):
        """Test concurrent writes and flush operations."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=1000,
            flush_interval=timedelta(seconds=10),
        )

        def write_messages():
            for i in range(50):
                entry = LogEntry(level=LogLevel.INFO, message=f"Thread message {i}")
                batch_writer.write(entry)
                if i % 10 == 0:
                    batch_writer.flush()

        threads = [threading.Thread(target=write_messages) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise any exception
        stats = batch_writer.get_stats()
        assert stats.entries_written == 150

        batch_writer.close()

    def test_concurrent_adaptive_writes(self):
        """Test concurrent writes with adaptive batch writer."""
        mock_writer = Mock()
        adaptive_writer = AdaptiveBatchWriter(
            mock_writer,
            max_batch_size=1000,
            initial_batch_size=100,
            flush_interval=timedelta(seconds=10),
        )

        def write_messages():
            for i in range(100):
                entry = LogEntry(level=LogLevel.INFO, message=f"Thread message {i}")
                adaptive_writer.write(entry)

        threads = [threading.Thread(target=write_messages) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise any exception
        stats = adaptive_writer.get_stats()
        assert stats.entries_written == 500

        adaptive_writer.close()


class TestErrorHandling:
    """Test error handling in batch writers."""

    def test_inner_writer_exception_continues(self):
        """Test that inner writer exception doesn't stop batch processing."""
        mock_writer = Mock()
        # Make write fail for first few calls, then succeed
        call_count = [0]

        def side_effect(entry):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Write failed")

        mock_writer.write.side_effect = side_effect

        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        # All writes should have been attempted
        assert mock_writer.write.call_count == 5

        batch_writer.close()

    def test_inner_writer_flush_exception_ignored(self):
        """Test that inner writer flush exception is handled gracefully."""
        mock_writer = Mock()
        mock_writer.flush.side_effect = Exception("Flush failed")

        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        # Should not raise
        batch_writer.close()

    def test_inner_writer_without_flush(self):
        """Test batch writer with inner writer that has no flush method."""
        mock_writer = Mock(spec=['write', 'close'])

        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        # Should not raise
        batch_writer.close()


class TestPerformanceCharacteristics:
    """Test performance characteristics of batch writers."""

    def test_stats_track_flush_time(self):
        """Test that flush time is tracked."""
        mock_writer = Mock()

        def slow_write(entry):
            time.sleep(0.001)  # 1ms delay

        mock_writer.write.side_effect = slow_write

        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=5,
            flush_interval=timedelta(seconds=10),
        )

        for i in range(5):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        stats = batch_writer.get_stats()

        # Flush time should be at least 5ms (5 writes × 1ms)
        assert stats.total_flush_time_ms >= 5.0
        assert stats.batches_flushed == 1

        batch_writer.close()

    def test_buffer_size_tracking(self):
        """Test buffer size tracking over time."""
        mock_writer = Mock()
        batch_writer = BatchWriter(
            mock_writer,
            max_batch_size=10,
            flush_interval=timedelta(seconds=10),
        )

        # Write 7 entries
        for i in range(7):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        stats = batch_writer.get_stats()
        assert stats.current_buffer_size == 7
        assert stats.max_buffer_size_reached == 7

        # Write 3 more to trigger flush
        for i in range(3):
            entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
            batch_writer.write(entry)

        stats = batch_writer.get_stats()
        assert stats.current_buffer_size == 0
        assert stats.max_buffer_size_reached == 10

        batch_writer.close()
