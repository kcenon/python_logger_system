"""
Critical Writer for crash-safe logging

Wraps any writer to ensure critical log messages (ERROR, CRITICAL)
are never lost, even during crashes or unexpected terminations.

Equivalent to C++ safety/critical_writer.h
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Set, Optional, Any

from logger_module.core.log_level import LogLevel
from logger_module.safety.signal_manager import SignalManager

if TYPE_CHECKING:
    from logger_module.core.log_entry import LogEntry


class CriticalWriter:
    """
    Writer that ensures critical logs are never lost.

    This wrapper provides:
    - Synchronous flush for critical log levels
    - Signal handler registration for emergency flush
    - OS-level disk sync to ensure data persistence

    Thread Safety:
        This class is thread-safe when the inner writer is thread-safe.
    """

    def __init__(
        self,
        inner_writer: Any,
        force_flush_levels: Optional[Set[LogLevel]] = None,
        enable_signal_handlers: bool = True,
        sync_on_critical: bool = True
    ):
        """
        Initialize critical writer.

        Args:
            inner_writer: Writer to wrap (must have write/flush methods)
            force_flush_levels: Log levels that trigger immediate flush
                               (default: ERROR, CRITICAL)
            enable_signal_handlers: Register signal handlers for crashes
            sync_on_critical: Force OS disk sync for critical logs
        """
        self.inner_writer = inner_writer
        self.force_flush_levels = force_flush_levels or {
            LogLevel.ERROR,
            LogLevel.CRITICAL
        }
        self.sync_on_critical = sync_on_critical
        self._closed = False

        if enable_signal_handlers:
            SignalManager.register_logger(self)

    def write(self, entry: "LogEntry") -> None:
        """
        Write log entry with critical protection.

        For critical log levels, immediately flush and optionally
        sync to disk.

        Args:
            entry: Log entry to write
        """
        if self._closed:
            return

        self.inner_writer.write(entry)

        if entry.level in self.force_flush_levels:
            self.flush()
            if self.sync_on_critical:
                self._sync_to_disk()

    def flush(self) -> None:
        """Flush buffered logs to inner writer."""
        if self._closed:
            return

        if hasattr(self.inner_writer, 'flush'):
            self.inner_writer.flush()

    def emergency_flush(self) -> None:
        """
        Emergency flush for crash situations.

        Called by SignalManager on termination signals.
        This method is designed to be as safe as possible.
        """
        try:
            self.flush()
            self._sync_to_disk()
        except Exception:
            pass  # Best effort - don't raise in emergency

    def _sync_to_disk(self) -> None:
        """
        Force OS to sync buffers to disk.

        Uses os.fsync() to ensure data is written to physical disk,
        not just OS buffers.
        """
        try:
            # Try to get file descriptor from inner writer
            if hasattr(self.inner_writer, '_file') and self.inner_writer._file:
                os.fsync(self.inner_writer._file.fileno())
            elif hasattr(self.inner_writer, 'file') and self.inner_writer.file:
                os.fsync(self.inner_writer.file.fileno())
        except (OSError, AttributeError, ValueError):
            pass  # Best effort - inner writer may not have file

    def close(self) -> None:
        """Close the writer and unregister from signal manager."""
        if self._closed:
            return

        self.flush()
        self._sync_to_disk()

        SignalManager.unregister_logger(self)

        if hasattr(self.inner_writer, 'close'):
            self.inner_writer.close()

        self._closed = True

    def __enter__(self) -> "CriticalWriter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
