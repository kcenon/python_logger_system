"""Tests for crash-safe logging functionality"""

import pytest
import tempfile
import os
import signal
import time
from pathlib import Path

from logger_module import LoggerBuilder, LogLevel, Logger, LoggerConfig
from logger_module.core.log_entry import LogEntry
from logger_module.safety import (
    SignalManager,
    MMapLogBuffer,
    CrashSafeLoggerMixin,
    create_emergency_log_file,
    recover_from_mmap,
    recover_from_emergency_logs,
    find_crash_logs,
    cleanup_old_crash_logs,
    CriticalWriter,
    WALCriticalWriter,
)


class TestSignalManager:
    """Test signal manager functionality."""

    def setup_method(self):
        """Reset signal manager before each test."""
        SignalManager.reset()

    def teardown_method(self):
        """Reset signal manager after each test."""
        SignalManager.reset()

    def test_register_logger(self):
        """Test logger registration."""

        class MockLogger:
            def emergency_flush(self):
                pass

        logger = MockLogger()
        SignalManager.register_logger(logger)

        assert SignalManager.get_registered_count() == 1
        assert SignalManager.is_initialized()

    def test_unregister_logger(self):
        """Test logger unregistration."""

        class MockLogger:
            def emergency_flush(self):
                pass

        logger = MockLogger()
        SignalManager.register_logger(logger)
        SignalManager.unregister_logger(logger)

        assert SignalManager.get_registered_count() == 0

    def test_emergency_flush_called(self):
        """Test that emergency_flush is called on registered loggers."""
        flush_count = 0

        class MockLogger:
            def emergency_flush(self):
                nonlocal flush_count
                flush_count += 1

        logger = MockLogger()
        SignalManager.register_logger(logger)
        SignalManager._emergency_flush_all()

        assert flush_count == 1

    def test_exception_in_flush_doesnt_affect_others(self):
        """Test that exception in one logger doesn't affect others."""
        good_flush_count = 0

        class BadLogger:
            def emergency_flush(self):
                raise RuntimeError("Simulated error")

        class GoodLogger:
            def emergency_flush(self):
                nonlocal good_flush_count
                good_flush_count += 1

        bad = BadLogger()
        good1 = GoodLogger()
        good2 = GoodLogger()

        SignalManager.register_logger(bad)
        SignalManager.register_logger(good1)
        SignalManager.register_logger(good2)

        # Should not raise, and should flush both good loggers
        SignalManager._emergency_flush_all()

        assert good_flush_count == 2


class TestMMapLogBuffer:
    """Test memory-mapped log buffer."""

    def test_create_buffer(self):
        """Test buffer creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")
            with MMapLogBuffer(buffer_path, size=4096) as buffer:
                assert buffer.path.exists()
                stats = buffer.get_stats()
                assert stats['size'] == 4096
                assert stats['entry_count'] == 0

    def test_write_and_recover(self):
        """Test writing and recovering entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")

            # Write entries
            with MMapLogBuffer(buffer_path) as buffer:
                buffer.write(b"Entry 1")
                buffer.write(b"Entry 2")
                buffer.write(b"Entry 3")

                stats = buffer.get_stats()
                assert stats['entry_count'] == 3

            # Recover entries
            with MMapLogBuffer(buffer_path, create=False) as buffer:
                entries = buffer.recover()
                assert len(entries) == 3
                assert entries[0] == "Entry 1"
                assert entries[1] == "Entry 2"
                assert entries[2] == "Entry 3"

    def test_write_entry_with_timestamp(self):
        """Test writing entry with automatic timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")
            with MMapLogBuffer(buffer_path) as buffer:
                buffer.write_entry("Test message")

                entries = buffer.recover()
                assert len(entries) == 1
                assert "Test message" in entries[0]
                # Should contain timestamp
                assert "[" in entries[0]

    def test_clear_buffer(self):
        """Test buffer clearing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")
            with MMapLogBuffer(buffer_path) as buffer:
                buffer.write(b"Entry 1")
                buffer.write(b"Entry 2")

                buffer.clear()

                stats = buffer.get_stats()
                assert stats['entry_count'] == 0

    def test_needs_recovery(self):
        """Test dirty flag for recovery detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")

            # Create buffer and write (simulating crash by not closing)
            buffer = MMapLogBuffer(buffer_path)
            buffer.write(b"Entry 1")
            buffer._mmap.flush()
            # Don't close properly

            # Check if needs recovery
            buffer2 = MMapLogBuffer(buffer_path, create=False)
            assert buffer2.needs_recovery()
            buffer2.close()
            buffer.close()

    def test_clean_close(self):
        """Test that clean close clears dirty flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")

            # Create and close properly
            with MMapLogBuffer(buffer_path) as buffer:
                buffer.write(b"Entry 1")

            # Should not need recovery
            with MMapLogBuffer(buffer_path, create=False) as buffer:
                assert not buffer.needs_recovery()


class TestCrashSafeLogger:
    """Test crash-safe logger integration."""

    def test_create_crash_safe_logger(self):
        """Test creating logger with crash safety enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mmap_path = os.path.join(tmpdir, "test.mmap")

            logger = (LoggerBuilder()
                .with_name("test")
                .with_async(False)
                .with_crash_safety(True, mmap_path=mmap_path)
                .build())

            assert logger._crash_safety_enabled
            assert logger._mmap_buffer is not None

            logger.shutdown()

    def test_crash_safe_logger_buffers_entries(self):
        """Test that crash-safe logger buffers entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mmap_path = os.path.join(tmpdir, "test.mmap")

            logger = (LoggerBuilder()
                .with_name("test")
                .with_async(False)
                .with_crash_safety(True, mmap_path=mmap_path)
                .build())

            logger.info("Test message 1")
            logger.warn("Test message 2")

            # Check emergency buffer
            buffer = logger.get_emergency_buffer()
            assert len(buffer) == 2

            # Check mmap buffer
            mmap_buffer = logger.get_mmap_buffer()
            entries = mmap_buffer.recover()
            assert len(entries) == 2

            logger.shutdown()

    def test_logger_without_crash_safety(self):
        """Test that logger works without crash safety."""
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .build())

        assert not logger._crash_safety_enabled

        logger.info("Test message")
        metrics = logger.get_metrics()
        assert metrics["logged"] == 1

        logger.shutdown()


class TestRecovery:
    """Test log recovery utilities."""

    def test_recover_from_mmap(self):
        """Test recovering from mmap file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer_path = os.path.join(tmpdir, "test.mmap")

            # Create and populate buffer
            with MMapLogBuffer(buffer_path) as buffer:
                buffer.write(b"Entry 1")
                buffer.write(b"Entry 2")

            # Recover
            entries = recover_from_mmap(buffer_path)
            assert len(entries) == 2

    def test_recover_from_emergency_logs(self):
        """Test recovering from emergency log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create emergency log file
            log_path = os.path.join(tmpdir, "emergency_log_12345.log")
            with open(log_path, 'w') as f:
                f.write("Entry 1\n")
                f.write("Entry 2\n")

            results = recover_from_emergency_logs(tmpdir)
            assert log_path in results
            assert len(results[log_path]) == 2

    def test_find_crash_logs(self):
        """Test finding crash log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mmap file
            mmap_path = os.path.join(tmpdir, "test.mmap")
            with MMapLogBuffer(mmap_path) as buffer:
                buffer.write(b"Test")

            # Create emergency log
            log_path = os.path.join(tmpdir, "emergency_log_12345.log")
            with open(log_path, 'w') as f:
                f.write("Test\n")

            results = find_crash_logs(tmpdir)
            assert len(results) == 2

    def test_cleanup_old_crash_logs(self):
        """Test cleanup of old crash log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with old modification time
            old_file = os.path.join(tmpdir, "emergency_log_old.log")
            with open(old_file, 'w') as f:
                f.write("Old entry\n")

            # Set modification time to 2 days ago
            old_time = time.time() - (48 * 3600)
            os.utime(old_file, (old_time, old_time))

            # Create recent file
            new_file = os.path.join(tmpdir, "emergency_log_new.log")
            with open(new_file, 'w') as f:
                f.write("New entry\n")

            # Cleanup files older than 1 day
            deleted = cleanup_old_crash_logs(tmpdir, max_age_hours=24)

            assert old_file in deleted
            assert new_file not in deleted
            assert not os.path.exists(old_file)
            assert os.path.exists(new_file)


class TestEmergencyLogFile:
    """Test emergency log file creation."""

    def test_create_emergency_log_file(self):
        """Test creating emergency log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path, fd = create_emergency_log_file(tmpdir)

            assert os.path.exists(path)
            assert fd is not None
            assert fd >= 0

            # Write to file descriptor
            os.write(fd, b"Test message\n")
            os.fsync(fd)
            os.close(fd)

            # Verify content
            with open(path, 'r') as f:
                content = f.read()
                assert "Test message" in content


class TestCriticalWriter:
    """Test CriticalWriter functionality."""

    def setup_method(self):
        """Reset signal manager before each test."""
        SignalManager.reset()

    def teardown_method(self):
        """Reset signal manager after each test."""
        SignalManager.reset()

    def test_write_normal_level(self):
        """Test writing normal level logs."""
        written = []

        class MockWriter:
            def write(self, entry):
                written.append(entry)

            def flush(self):
                pass

        mock = MockWriter()
        writer = CriticalWriter(mock, enable_signal_handlers=False)

        entry = LogEntry(message="Test", level=LogLevel.INFO)
        writer.write(entry)

        assert len(written) == 1
        writer.close()

    def test_flush_on_error_level(self):
        """Test immediate flush on ERROR level."""
        flush_count = 0

        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                nonlocal flush_count
                flush_count += 1

        mock = MockWriter()
        writer = CriticalWriter(mock, enable_signal_handlers=False)

        entry = LogEntry(message="Error occurred", level=LogLevel.ERROR)
        writer.write(entry)

        assert flush_count == 1
        writer.close()

    def test_flush_on_critical_level(self):
        """Test immediate flush on CRITICAL level."""
        flush_count = 0

        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                nonlocal flush_count
                flush_count += 1

        mock = MockWriter()
        writer = CriticalWriter(mock, enable_signal_handlers=False)

        entry = LogEntry(message="Critical failure", level=LogLevel.CRITICAL)
        writer.write(entry)

        assert flush_count == 1
        writer.close()

    def test_no_flush_on_info_level(self):
        """Test no immediate flush on INFO level."""
        flush_count = 0

        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                nonlocal flush_count
                flush_count += 1

        mock = MockWriter()
        writer = CriticalWriter(mock, enable_signal_handlers=False)

        entry = LogEntry(message="Info message", level=LogLevel.INFO)
        writer.write(entry)

        # Should not trigger flush for INFO level
        assert flush_count == 0
        writer.close()

    def test_custom_force_flush_levels(self):
        """Test custom force flush levels."""
        flush_count = 0

        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                nonlocal flush_count
                flush_count += 1

        mock = MockWriter()
        writer = CriticalWriter(
            mock,
            force_flush_levels={LogLevel.WARN, LogLevel.ERROR, LogLevel.CRITICAL},
            enable_signal_handlers=False
        )

        entry = LogEntry(message="Warning", level=LogLevel.WARN)
        writer.write(entry)

        assert flush_count == 1
        writer.close()

    def test_signal_manager_registration(self):
        """Test automatic registration with SignalManager."""
        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                pass

        mock = MockWriter()
        writer = CriticalWriter(mock, enable_signal_handlers=True)

        assert SignalManager.get_registered_count() == 1

        writer.close()
        assert SignalManager.get_registered_count() == 0

    def test_emergency_flush(self):
        """Test emergency flush method."""
        flush_count = 0

        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                nonlocal flush_count
                flush_count += 1

        mock = MockWriter()
        writer = CriticalWriter(mock, enable_signal_handlers=False)

        writer.emergency_flush()

        assert flush_count == 1
        writer.close()

    def test_context_manager(self):
        """Test context manager usage."""
        closed = False

        class MockWriter:
            def write(self, entry):
                pass

            def flush(self):
                pass

            def close(self):
                nonlocal closed
                closed = True

        mock = MockWriter()
        with CriticalWriter(mock, enable_signal_handlers=False) as writer:
            entry = LogEntry(message="Test", level=LogLevel.INFO)
            writer.write(entry)

        assert closed

    def test_sync_to_disk_with_file_writer(self):
        """Test disk sync with actual file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.log")

            from logger_module.writers.file_writer import FileWriter
            file_writer = FileWriter(file_path)
            writer = CriticalWriter(
                file_writer,
                sync_on_critical=True,
                enable_signal_handlers=False
            )

            entry = LogEntry(message="Critical error", level=LogLevel.CRITICAL)
            writer.write(entry)
            writer.close()

            # Verify file exists and contains content
            with open(file_path, 'r') as f:
                content = f.read()
                assert "Critical error" in content


class TestWALCriticalWriter:
    """Test WALCriticalWriter functionality."""

    def setup_method(self):
        """Reset signal manager before each test."""
        SignalManager.reset()

    def teardown_method(self):
        """Reset signal manager after each test."""
        SignalManager.reset()

    def test_write_to_wal(self):
        """Test writing to WAL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_path = os.path.join(tmpdir, "test.wal")

            class MockWriter:
                def write(self, entry):
                    pass

                def flush(self):
                    pass

            mock = MockWriter()
            writer = WALCriticalWriter(
                mock,
                wal_path=wal_path,
                enable_signal_handlers=False
            )

            entry = LogEntry(message="Test message", level=LogLevel.INFO)
            writer.write(entry)
            writer.close()

            # Verify WAL file exists
            assert os.path.exists(wal_path)

    def test_wal_recovery(self):
        """Test recovering uncommitted entries from WAL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_path = os.path.join(tmpdir, "test.wal")

            class FailingWriter:
                def write(self, entry):
                    raise RuntimeError("Simulated failure")

                def flush(self):
                    pass

            mock = FailingWriter()
            writer = WALCriticalWriter(
                mock,
                wal_path=wal_path,
                auto_cleanup=False,
                enable_signal_handlers=False
            )

            entry = LogEntry(message="Should be recovered", level=LogLevel.ERROR)
            try:
                writer.write(entry)
            except RuntimeError:
                pass

            writer._wal_file.close()

            # Create new writer to recover
            class MockWriter2:
                def write(self, entry):
                    pass

                def flush(self):
                    pass

            mock2 = MockWriter2()
            writer2 = WALCriticalWriter(
                mock2,
                wal_path=wal_path,
                auto_cleanup=False,
                enable_signal_handlers=False
            )

            recovered = writer2.recover()
            assert len(recovered) >= 1

            writer2.close()

    def test_wal_commit_marker(self):
        """Test that committed entries are marked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_path = os.path.join(tmpdir, "test.wal")

            written = []

            class MockWriter:
                def write(self, entry):
                    written.append(entry)

                def flush(self):
                    pass

            mock = MockWriter()
            writer = WALCriticalWriter(
                mock,
                wal_path=wal_path,
                auto_cleanup=False,
                enable_signal_handlers=False
            )

            entry = LogEntry(message="Committed entry", level=LogLevel.INFO)
            writer.write(entry)
            writer.close()

            # Create new writer to check recovery
            mock2 = MockWriter()
            writer2 = WALCriticalWriter(
                mock2,
                wal_path=wal_path,
                auto_cleanup=False,
                enable_signal_handlers=False
            )

            # Should find no uncommitted entries
            recovered = writer2.recover()
            assert len(recovered) == 0

            writer2.close()

    def test_clear_wal(self):
        """Test clearing WAL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wal_path = os.path.join(tmpdir, "test.wal")

            class MockWriter:
                def write(self, entry):
                    pass

                def flush(self):
                    pass

            mock = MockWriter()
            writer = WALCriticalWriter(
                mock,
                wal_path=wal_path,
                enable_signal_handlers=False
            )

            entry = LogEntry(message="Test", level=LogLevel.INFO)
            writer.write(entry)

            writer.clear_wal()

            # After clear, WAL should be empty or contain no entries
            with open(wal_path, 'r') as f:
                content = f.read()
                assert content == ""

            writer.close()

    def test_builder_integration(self):
        """Test CriticalWriter with LoggerBuilder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.log")

            SignalManager.reset()

            logger = (LoggerBuilder()
                .with_name("test")
                .with_async(False)
                .with_file(log_path)
                .with_critical_writer(
                    enabled=True,
                    force_flush_levels={LogLevel.ERROR, LogLevel.CRITICAL}
                )
                .build())

            logger.error("Error message")
            logger.shutdown()

            with open(log_path, 'r') as f:
                content = f.read()
                assert "Error message" in content

    def test_builder_with_wal(self):
        """Test WALCriticalWriter with LoggerBuilder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "test.log")
            wal_path = os.path.join(tmpdir, "test.wal")

            SignalManager.reset()

            logger = (LoggerBuilder()
                .with_name("test")
                .with_async(False)
                .with_file(log_path)
                .with_critical_writer(
                    enabled=True,
                    wal_path=wal_path
                )
                .build())

            logger.critical("Critical message")
            logger.shutdown()

            # Verify both log and WAL exist
            assert os.path.exists(log_path)
            assert os.path.exists(wal_path)

            with open(log_path, 'r') as f:
                content = f.read()
                assert "Critical message" in content
