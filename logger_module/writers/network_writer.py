"""
Network writer for distributed logging

Send logs to remote log aggregation systems via TCP/UDP.
Essential for distributed systems, microservices, and centralized logging.

Equivalent to C++ network_writer.h
"""

from __future__ import annotations

import socket
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from logger_module.core.log_entry import LogEntry


@dataclass
class ConnectionStats:
    """
    Statistics for network connection monitoring.

    Tracks message counts, errors, and connection health metrics.
    """

    messages_sent: int = 0
    messages_failed: int = 0
    bytes_sent: int = 0
    reconnect_count: int = 0
    errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    is_connected: bool = False

    def record_success(self, bytes_count: int) -> None:
        """Record a successful message send."""
        self.messages_sent += 1
        self.bytes_sent += bytes_count

    def record_failure(self, error: str) -> None:
        """Record a failed message send."""
        self.messages_failed += 1
        self.errors += 1
        self.last_error = error
        self.last_error_time = datetime.now()

    def record_reconnect(self) -> None:
        """Record a reconnection attempt."""
        self.reconnect_count += 1

    def to_dict(self) -> dict:
        """Convert stats to dictionary for serialization."""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "bytes_sent": self.bytes_sent,
            "reconnect_count": self.reconnect_count,
            "errors": self.errors,
            "last_error": self.last_error,
            "last_error_time": (
                self.last_error_time.isoformat()
                if self.last_error_time
                else None
            ),
            "connected_at": (
                self.connected_at.isoformat() if self.connected_at else None
            ),
            "is_connected": self.is_connected,
        }


class NetworkWriter(ABC):
    """
    Base class for network-based log writers.

    Provides common functionality for TCP and UDP writers including:
    - Connection management with retry logic
    - Internal buffering for network failures
    - Connection statistics tracking
    - Thread-safe operations

    Thread Safety:
        This class is thread-safe. All public methods use internal locking.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        buffer_size: int = 8192,
        reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
        reconnect_backoff: float = 2.0,
        max_buffer_entries: int = 1000,
        formatter=None,
    ):
        """
        Initialize network writer.

        Args:
            host: Remote host address
            port: Remote port number
            timeout: Socket timeout in seconds
            buffer_size: Socket buffer size in bytes
            reconnect_attempts: Maximum reconnection attempts before giving up
            reconnect_delay: Initial delay between reconnection attempts
            reconnect_backoff: Multiplier for exponential backoff
            max_buffer_entries: Maximum buffered entries during disconnect
            formatter: Log formatter (default: uses entry's __str__)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.buffer_size = buffer_size
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.reconnect_backoff = reconnect_backoff
        self.max_buffer_entries = max_buffer_entries
        self.formatter = formatter

        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._stats = ConnectionStats()
        self._buffer: List[bytes] = []
        self._closed = False

    @abstractmethod
    def _create_socket(self) -> socket.socket:
        """
        Create and configure socket for specific protocol.

        Returns:
            Configured socket instance
        """
        pass

    @abstractmethod
    def _send_data(self, data: bytes) -> bool:
        """
        Send data using protocol-specific method.

        Args:
            data: Bytes to send

        Returns:
            True if send was successful
        """
        pass

    def connect(self) -> bool:
        """
        Establish connection with retry logic.

        Uses exponential backoff for reconnection attempts.

        Returns:
            True if connection was established
        """
        with self._lock:
            return self._connect_internal()

    def _connect_internal(self) -> bool:
        """Internal connect without lock (caller must hold lock)."""
        if self._socket is not None:
            return True

        delay = self.reconnect_delay

        for attempt in range(self.reconnect_attempts):
            try:
                self._socket = self._create_socket()
                self._socket.settimeout(self.timeout)
                self._do_connect()
                self._stats.connected_at = datetime.now()
                self._stats.is_connected = True
                self._flush_buffer()
                return True
            except socket.error as e:
                self._stats.record_failure(str(e))
                self._socket = None

                if attempt < self.reconnect_attempts - 1:
                    self._stats.record_reconnect()
                    time.sleep(delay)
                    delay *= self.reconnect_backoff

        return False

    def _do_connect(self) -> None:
        """
        Perform actual connection (protocol-specific).

        Override in subclasses that need connection (TCP).
        Default does nothing (UDP doesn't need explicit connect).
        """
        pass

    def _flush_buffer(self) -> None:
        """Send buffered messages after reconnection."""
        while self._buffer:
            data = self._buffer[0]
            if self._send_data(data):
                self._buffer.pop(0)
                self._stats.record_success(len(data))
            else:
                break

    def write(self, entry: "LogEntry") -> None:
        """
        Write log entry to network.

        If connection fails, buffers the message for later retry.

        Args:
            entry: Log entry to write
        """
        if self._closed:
            return

        if self.formatter:
            msg = self.formatter.format(entry)
        else:
            msg = str(entry)

        data = (msg + "\n").encode("utf-8")

        with self._lock:
            if not self._stats.is_connected:
                self._connect_internal()

            if self._stats.is_connected and self._send_data(data):
                self._stats.record_success(len(data))
            else:
                self._add_to_buffer(data)

    def _add_to_buffer(self, data: bytes) -> None:
        """Add data to internal buffer (caller must hold lock)."""
        if len(self._buffer) < self.max_buffer_entries:
            self._buffer.append(data)
        else:
            self._stats.record_failure("buffer_overflow")

    def _handle_send_error(self, error: Exception) -> None:
        """Handle send error and mark connection as failed."""
        self._stats.record_failure(str(error))
        self._stats.is_connected = False
        self._close_socket()

    def _close_socket(self) -> None:
        """Close current socket (caller must hold lock)."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def flush(self) -> None:
        """
        Flush buffered messages.

        Attempts to reconnect and send buffered messages.
        """
        if self._closed:
            return

        with self._lock:
            if self._buffer:
                if not self._stats.is_connected:
                    self._connect_internal()
                if self._stats.is_connected:
                    self._flush_buffer()

    def close(self) -> None:
        """Close connection and release resources."""
        if self._closed:
            return

        with self._lock:
            self._closed = True
            self._flush_buffer()
            self._close_socket()
            self._stats.is_connected = False

    def get_stats(self) -> ConnectionStats:
        """
        Get connection statistics.

        Returns:
            Copy of current connection statistics
        """
        with self._lock:
            return ConnectionStats(
                messages_sent=self._stats.messages_sent,
                messages_failed=self._stats.messages_failed,
                bytes_sent=self._stats.bytes_sent,
                reconnect_count=self._stats.reconnect_count,
                errors=self._stats.errors,
                last_error=self._stats.last_error,
                last_error_time=self._stats.last_error_time,
                connected_at=self._stats.connected_at,
                is_connected=self._stats.is_connected,
            )

    def is_connected(self) -> bool:
        """
        Check if currently connected.

        Returns:
            True if connection is active
        """
        with self._lock:
            return self._stats.is_connected

    def __enter__(self) -> "NetworkWriter":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


class TCPWriter(NetworkWriter):
    """
    TCP-based log writer with reliable delivery.

    Features:
    - Reliable, ordered delivery
    - Automatic reconnection with exponential backoff
    - Internal buffering during connection failures
    - Connection keep-alive support
    - Optional TLS/SSL encryption

    Thread Safety:
        This class is thread-safe. All public methods use internal locking.

    Example:
        tcp_writer = TCPWriter(
            host="log-aggregator.example.com",
            port=5140,
            timeout=5.0
        )
        logger = LoggerBuilder().add_writer(tcp_writer).build()
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        buffer_size: int = 8192,
        reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
        reconnect_backoff: float = 2.0,
        max_buffer_entries: int = 1000,
        formatter=None,
        keepalive: bool = True,
        keepalive_time: int = 60,
        nodelay: bool = True,
        use_ssl: bool = False,
        ssl_context=None,
    ):
        """
        Initialize TCP writer.

        Args:
            host: Remote host address
            port: Remote port number
            timeout: Socket timeout in seconds
            buffer_size: Socket buffer size in bytes
            reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Initial reconnection delay
            reconnect_backoff: Backoff multiplier
            max_buffer_entries: Maximum buffered entries
            formatter: Log formatter
            keepalive: Enable TCP keep-alive
            keepalive_time: Keep-alive interval in seconds
            nodelay: Enable TCP_NODELAY (disable Nagle's algorithm)
            use_ssl: Enable SSL/TLS encryption
            ssl_context: Custom SSL context (optional)
        """
        super().__init__(
            host=host,
            port=port,
            timeout=timeout,
            buffer_size=buffer_size,
            reconnect_attempts=reconnect_attempts,
            reconnect_delay=reconnect_delay,
            reconnect_backoff=reconnect_backoff,
            max_buffer_entries=max_buffer_entries,
            formatter=formatter,
        )
        self.keepalive = keepalive
        self.keepalive_time = keepalive_time
        self.nodelay = nodelay
        self.use_ssl = use_ssl
        self.ssl_context = ssl_context

    def _create_socket(self) -> socket.socket:
        """Create and configure TCP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.buffer_size)

        if self.nodelay:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        if self.keepalive:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        return sock

    def _do_connect(self) -> None:
        """Establish TCP connection."""
        self._socket.connect((self.host, self.port))

        if self.use_ssl:
            self._wrap_ssl()

    def _wrap_ssl(self) -> None:
        """Wrap socket with SSL/TLS."""
        import ssl

        if self.ssl_context:
            context = self.ssl_context
        else:
            context = ssl.create_default_context()

        self._socket = context.wrap_socket(
            self._socket, server_hostname=self.host
        )

    def _send_data(self, data: bytes) -> bool:
        """Send data over TCP connection."""
        if not self._socket:
            return False

        try:
            self._socket.sendall(data)
            return True
        except socket.error as e:
            self._handle_send_error(e)
            return False


class UDPWriter(NetworkWriter):
    """
    UDP-based log writer for high-throughput logging.

    Features:
    - Fire-and-forget delivery (no connection overhead)
    - Low latency for high-volume logging
    - Automatic message truncation for oversized payloads
    - No buffering needed (connectionless)

    Note:
        UDP does not guarantee delivery or ordering. Use TCPWriter
        for critical logs that must not be lost.

    Thread Safety:
        This class is thread-safe. All public methods use internal locking.

    Example:
        udp_writer = UDPWriter(
            host="syslog.example.com",
            port=514
        )
        logger = LoggerBuilder().add_writer(udp_writer).build()
    """

    MAX_UDP_PAYLOAD = 65507

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        buffer_size: int = 8192,
        max_buffer_entries: int = 0,
        formatter=None,
        truncate_oversized: bool = True,
    ):
        """
        Initialize UDP writer.

        Args:
            host: Remote host address
            port: Remote port number
            timeout: Socket timeout in seconds
            buffer_size: Socket buffer size in bytes
            max_buffer_entries: Not used for UDP (connectionless)
            formatter: Log formatter
            truncate_oversized: Truncate messages exceeding UDP limit
        """
        super().__init__(
            host=host,
            port=port,
            timeout=timeout,
            buffer_size=buffer_size,
            reconnect_attempts=1,
            reconnect_delay=0,
            reconnect_backoff=1,
            max_buffer_entries=max_buffer_entries,
            formatter=formatter,
        )
        self.truncate_oversized = truncate_oversized
        self._target = (host, port)

    def _create_socket(self) -> socket.socket:
        """Create and configure UDP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.buffer_size)
        return sock

    def _do_connect(self) -> None:
        """UDP is connectionless, mark as connected immediately."""
        pass

    def connect(self) -> bool:
        """
        Initialize UDP socket.

        UDP is connectionless, so this just creates the socket.

        Returns:
            True (always succeeds for UDP)
        """
        with self._lock:
            if self._socket is None:
                try:
                    self._socket = self._create_socket()
                    self._socket.settimeout(self.timeout)
                    self._stats.connected_at = datetime.now()
                    self._stats.is_connected = True
                    return True
                except socket.error as e:
                    self._stats.record_failure(str(e))
                    return False
            return True

    def _send_data(self, data: bytes) -> bool:
        """Send data over UDP."""
        if not self._socket:
            return False

        if self.truncate_oversized and len(data) > self.MAX_UDP_PAYLOAD:
            data = data[: self.MAX_UDP_PAYLOAD]

        try:
            self._socket.sendto(data, self._target)
            return True
        except socket.error as e:
            self._stats.record_failure(str(e))
            return False

    def write(self, entry: "LogEntry") -> None:
        """
        Write log entry via UDP.

        UDP is fire-and-forget, no buffering for failed sends.

        Args:
            entry: Log entry to write
        """
        if self._closed:
            return

        if self.formatter:
            msg = self.formatter.format(entry)
        else:
            msg = str(entry)

        data = (msg + "\n").encode("utf-8")

        with self._lock:
            if self._socket is None:
                self._init_socket()

            if self._socket and self._send_data(data):
                self._stats.record_success(len(data))

    def _init_socket(self) -> bool:
        """Initialize UDP socket (caller must hold lock)."""
        try:
            self._socket = self._create_socket()
            self._socket.settimeout(self.timeout)
            self._stats.connected_at = datetime.now()
            self._stats.is_connected = True
            return True
        except socket.error as e:
            self._stats.record_failure(str(e))
            return False
