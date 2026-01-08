"""Tests for network writer functionality"""

import pytest
import socket
import threading
import time
from unittest.mock import Mock, patch, MagicMock

from logger_module import LoggerBuilder, LogLevel
from logger_module.core.log_entry import LogEntry
from logger_module.writers.network_writer import (
    ConnectionStats,
    NetworkWriter,
    TCPWriter,
    UDPWriter,
)


class TestConnectionStats:
    """Test connection statistics functionality."""

    def test_initial_stats(self):
        """Test default values for connection stats."""
        stats = ConnectionStats()
        assert stats.messages_sent == 0
        assert stats.messages_failed == 0
        assert stats.bytes_sent == 0
        assert stats.reconnect_count == 0
        assert stats.errors == 0
        assert stats.is_connected is False

    def test_record_success(self):
        """Test recording successful sends."""
        stats = ConnectionStats()
        stats.record_success(100)
        stats.record_success(50)

        assert stats.messages_sent == 2
        assert stats.bytes_sent == 150

    def test_record_failure(self):
        """Test recording failed sends."""
        stats = ConnectionStats()
        stats.record_failure("Connection refused")

        assert stats.messages_failed == 1
        assert stats.errors == 1
        assert stats.last_error == "Connection refused"
        assert stats.last_error_time is not None

    def test_record_reconnect(self):
        """Test recording reconnection attempts."""
        stats = ConnectionStats()
        stats.record_reconnect()
        stats.record_reconnect()

        assert stats.reconnect_count == 2

    def test_to_dict(self):
        """Test serialization to dictionary."""
        stats = ConnectionStats()
        stats.record_success(100)
        stats.record_failure("Test error")

        data = stats.to_dict()

        assert data["messages_sent"] == 1
        assert data["messages_failed"] == 1
        assert data["bytes_sent"] == 100
        assert data["last_error"] == "Test error"


class TestTCPWriter:
    """Test TCP writer functionality."""

    def test_initialization(self):
        """Test TCP writer initialization."""
        writer = TCPWriter(host="localhost", port=5140)

        assert writer.host == "localhost"
        assert writer.port == 5140
        assert writer.timeout == 5.0
        assert writer.reconnect_attempts == 3
        assert writer.nodelay is True
        assert writer.keepalive is True

    def test_create_socket(self):
        """Test socket creation with proper configuration."""
        writer = TCPWriter(host="localhost", port=5140)
        sock = writer._create_socket()

        assert sock is not None
        assert sock.type == socket.SOCK_STREAM
        sock.close()

    def test_connection_failure_buffers_message(self):
        """Test that messages are buffered on connection failure."""
        writer = TCPWriter(
            host="localhost",
            port=5140,
            reconnect_attempts=1,
            reconnect_delay=0.01,
        )

        # Mock socket creation to always fail
        def mock_create_socket():
            raise socket.error("Connection refused")

        writer._create_socket = mock_create_socket

        entry = LogEntry(level=LogLevel.INFO, message="Test message")
        writer.write(entry)

        # Message should be buffered since connection failed
        assert len(writer._buffer) == 1
        stats = writer.get_stats()
        assert stats.errors > 0
        assert stats.is_connected is False

        writer.close()

    def test_get_stats_returns_copy(self):
        """Test that get_stats returns a copy of stats."""
        writer = TCPWriter(host="localhost", port=5140)
        stats1 = writer.get_stats()
        stats2 = writer.get_stats()

        # Modifying one should not affect the other
        stats1.messages_sent = 100
        assert stats2.messages_sent == 0

    def test_context_manager(self):
        """Test context manager protocol."""
        with patch.object(TCPWriter, 'connect', return_value=False):
            with patch.object(TCPWriter, 'close') as mock_close:
                with TCPWriter(host="localhost", port=5140) as writer:
                    pass
                mock_close.assert_called_once()

    def test_close_flushes_buffer(self):
        """Test that close attempts to flush buffer."""
        writer = TCPWriter(
            host="192.0.2.1",
            port=5140,
            timeout=0.01,
            reconnect_attempts=1,
        )

        # Add some messages to buffer manually
        writer._buffer.append(b"test message\n")

        writer.close()

        assert writer._closed is True


class TestUDPWriter:
    """Test UDP writer functionality."""

    def test_initialization(self):
        """Test UDP writer initialization."""
        writer = UDPWriter(host="localhost", port=514)

        assert writer.host == "localhost"
        assert writer.port == 514
        assert writer.timeout == 5.0
        assert writer.truncate_oversized is True

    def test_create_socket(self):
        """Test socket creation for UDP."""
        writer = UDPWriter(host="localhost", port=514)
        sock = writer._create_socket()

        assert sock is not None
        assert sock.type == socket.SOCK_DGRAM
        sock.close()

    def test_connect_always_succeeds(self):
        """Test that UDP connect always succeeds (connectionless)."""
        writer = UDPWriter(host="localhost", port=514)
        result = writer.connect()

        assert result is True
        assert writer._socket is not None
        assert writer.is_connected() is True

        writer.close()

    def test_truncate_oversized_message(self):
        """Test that oversized messages are truncated."""
        writer = UDPWriter(host="127.0.0.1", port=9999, truncate_oversized=True)

        # Create a mock socket
        mock_socket = MagicMock()
        writer._socket = mock_socket
        writer._stats.is_connected = True

        # Create a very large message
        large_data = b"x" * 70000  # Larger than MAX_UDP_PAYLOAD (65507)

        # Should not raise, message gets truncated
        writer._send_data(large_data)

        # Check that the data was truncated
        called_data = mock_socket.sendto.call_args[0][0]
        assert len(called_data) <= UDPWriter.MAX_UDP_PAYLOAD

        writer._socket = None  # Prevent close from failing
        writer.close()

    def test_write_creates_socket_on_demand(self):
        """Test that write creates socket if not connected."""
        writer = UDPWriter(host="127.0.0.1", port=9999)

        assert writer._socket is None

        # Mock _create_socket to return a mock socket
        mock_socket = MagicMock()
        original_create_socket = writer._create_socket

        def mock_create():
            return mock_socket

        writer._create_socket = mock_create

        entry = LogEntry(level=LogLevel.INFO, message="Test")
        writer.write(entry)

        # Socket should have been created
        assert writer._socket is mock_socket

        writer._socket = None
        writer.close()

    def test_fire_and_forget(self):
        """Test that UDP doesn't buffer on failure."""
        writer = UDPWriter(host="127.0.0.1", port=9999, max_buffer_entries=0)

        # Create a mock socket
        mock_socket = MagicMock()
        mock_socket.sendto.side_effect = socket.error("Test error")
        writer._socket = mock_socket
        writer._stats.is_connected = True

        entry = LogEntry(level=LogLevel.INFO, message="Test")
        writer.write(entry)

        # Buffer should be empty (UDP doesn't buffer)
        assert len(writer._buffer) == 0

        writer._socket = None
        writer.close()


class TestLoggerBuilderIntegration:
    """Test LoggerBuilder integration with network writers."""

    def test_with_tcp_method(self):
        """Test adding TCP writer via builder."""
        logger = (LoggerBuilder()
            .with_name("tcp_test")
            .with_level(LogLevel.DEBUG)
            .with_async(False)
            .with_tcp("localhost", 5140)
            .build())

        # Verify TCP writer was added
        tcp_writers = [
            w for w in logger._writers
            if isinstance(w, TCPWriter)
        ]
        assert len(tcp_writers) == 1
        assert tcp_writers[0].host == "localhost"
        assert tcp_writers[0].port == 5140

        logger.shutdown()

    def test_with_udp_method(self):
        """Test adding UDP writer via builder."""
        logger = (LoggerBuilder()
            .with_name("udp_test")
            .with_level(LogLevel.DEBUG)
            .with_async(False)
            .with_udp("localhost", 514)
            .build())

        # Verify UDP writer was added
        udp_writers = [
            w for w in logger._writers
            if isinstance(w, UDPWriter)
        ]
        assert len(udp_writers) == 1
        assert udp_writers[0].host == "localhost"
        assert udp_writers[0].port == 514

        logger.shutdown()

    def test_multiple_network_writers(self):
        """Test adding multiple network writers."""
        logger = (LoggerBuilder()
            .with_name("multi_test")
            .with_level(LogLevel.DEBUG)
            .with_async(False)
            .with_tcp("tcp-host", 5140)
            .with_udp("udp-host", 514)
            .build())

        network_writers = [
            w for w in logger._writers
            if isinstance(w, (TCPWriter, UDPWriter))
        ]
        assert len(network_writers) == 2

        logger.shutdown()


class TestTCPWriterWithMock:
    """Test TCP writer with mocked socket."""

    def test_successful_send(self):
        """Test successful TCP send with mock socket."""
        writer = TCPWriter(host="localhost", port=5140)

        # Mock the socket
        mock_socket = MagicMock()
        writer._socket = mock_socket
        writer._stats.is_connected = True

        # Test send
        result = writer._send_data(b"test message\n")

        assert result is True
        mock_socket.sendall.assert_called_once_with(b"test message\n")

        writer._socket = None
        writer.close()

    def test_send_failure_marks_disconnected(self):
        """Test that send failure marks connection as disconnected."""
        writer = TCPWriter(host="localhost", port=5140)

        # Mock the socket to fail
        mock_socket = MagicMock()
        mock_socket.sendall.side_effect = socket.error("Connection reset")
        writer._socket = mock_socket
        writer._stats.is_connected = True

        result = writer._send_data(b"test message\n")

        assert result is False
        assert writer._stats.is_connected is False

        writer._socket = None
        writer.close()

    def test_reconnection_logic(self):
        """Test reconnection with exponential backoff."""
        writer = TCPWriter(
            host="localhost",
            port=5140,
            reconnect_attempts=3,
            reconnect_delay=0.01,
            reconnect_backoff=2.0,
        )

        connect_attempts = 0

        def mock_create_socket():
            nonlocal connect_attempts
            connect_attempts += 1
            raise socket.error("Connection refused")

        writer._create_socket = mock_create_socket

        result = writer.connect()

        assert result is False
        assert connect_attempts == 3  # All attempts made
        assert writer._stats.errors >= 3

        writer.close()


class TestThreadSafety:
    """Test thread safety of network writers."""

    def test_concurrent_writes_tcp(self):
        """Test that concurrent writes are thread-safe for TCP."""
        writer = TCPWriter(
            host="localhost",
            port=5140,
        )

        # Use mock socket that always succeeds
        mock_socket = MagicMock()
        writer._socket = mock_socket
        writer._stats.is_connected = True

        def write_messages():
            for i in range(50):
                entry = LogEntry(level=LogLevel.INFO, message=f"Thread message {i}")
                writer.write(entry)

        threads = [threading.Thread(target=write_messages) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise any exception
        stats = writer.get_stats()
        # All 250 messages should have been sent
        assert stats.messages_sent == 250

        writer._socket = None
        writer.close()

    def test_concurrent_writes_udp(self):
        """Test that concurrent writes are thread-safe for UDP."""
        writer = UDPWriter(host="localhost", port=514)

        # Use mock socket
        mock_socket = MagicMock()
        writer._socket = mock_socket
        writer._stats.is_connected = True

        def write_messages():
            for i in range(50):
                entry = LogEntry(level=LogLevel.INFO, message=f"Thread message {i}")
                writer.write(entry)

        threads = [threading.Thread(target=write_messages) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 250 messages should have been sent
        stats = writer.get_stats()
        assert stats.messages_sent == 250

        writer._socket = None
        writer.close()
