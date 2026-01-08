"""
Crash-safe logger mixin

Provides crash-safe capabilities to logger classes via mixin pattern.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional, List, Any
from collections import deque

from logger_module.safety.signal_manager import SignalManager
from logger_module.safety.mmap_buffer import MMapLogBuffer


class CrashSafeLoggerMixin:
    """
    Mixin to add crash-safe capabilities to logger.

    This mixin provides:
    - Emergency flush on signals and crashes
    - Optional memory-mapped buffer for durability
    - Recent entries buffer for emergency recovery

    Usage:
        class CrashSafeLogger(CrashSafeLoggerMixin, Logger):
            pass
    """

    # Max entries to keep in emergency buffer
    EMERGENCY_BUFFER_SIZE = 100

    def _init_crash_safety(
        self,
        mmap_path: Optional[str] = None,
        mmap_size: int = 1024 * 1024,
        emergency_fd: Optional[int] = None
    ) -> None:
        """
        Initialize crash-safe features.

        Args:
            mmap_path: Path for memory-mapped buffer (optional)
            mmap_size: Size of memory-mapped buffer
            emergency_fd: File descriptor for emergency writes
        """
        self._emergency_buffer: deque = deque(maxlen=self.EMERGENCY_BUFFER_SIZE)
        self._mmap_buffer: Optional[MMapLogBuffer] = None
        self._emergency_fd: Optional[int] = emergency_fd
        self._crash_safety_enabled = True

        # Initialize memory-mapped buffer if path provided
        if mmap_path:
            try:
                self._mmap_buffer = MMapLogBuffer(mmap_path, mmap_size)
            except Exception:
                pass  # Best effort - continue without mmap

        # Register with signal manager
        SignalManager.register_logger(self)

    def _buffer_for_emergency(self, formatted_entry: str) -> None:
        """
        Buffer an entry for potential emergency flush.

        Args:
            formatted_entry: Formatted log entry string
        """
        if not self._crash_safety_enabled:
            return

        self._emergency_buffer.append(formatted_entry)

        # Also write to mmap buffer if available
        if self._mmap_buffer is not None:
            try:
                self._mmap_buffer.write(formatted_entry.encode('utf-8'))
            except Exception:
                pass  # Best effort

    def emergency_flush(self) -> None:
        """
        Signal-safe emergency flush.

        This method is called by SignalManager on crashes/signals.
        It bypasses normal queue processing and writes directly.
        """
        # Write buffered entries to emergency file descriptor
        if self._emergency_fd is not None:
            for entry in self._emergency_buffer:
                try:
                    os.write(self._emergency_fd, (entry + '\n').encode('utf-8'))
                    os.fsync(self._emergency_fd)
                except OSError:
                    pass

        # Flush mmap buffer
        if self._mmap_buffer is not None:
            try:
                self._mmap_buffer.flush()
            except Exception:
                pass

        # Try to flush normal writers
        if hasattr(self, '_writers'):
            for writer in getattr(self, '_writers', []):
                try:
                    if hasattr(writer, 'flush'):
                        writer.flush()
                except Exception:
                    pass

    def _cleanup_crash_safety(self) -> None:
        """Cleanup crash-safe resources."""
        # Unregister from signal manager
        SignalManager.unregister_logger(self)

        # Close mmap buffer
        if self._mmap_buffer is not None:
            try:
                self._mmap_buffer.close()
            except Exception:
                pass
            self._mmap_buffer = None

        # Close emergency fd
        if self._emergency_fd is not None:
            try:
                os.close(self._emergency_fd)
            except OSError:
                pass
            self._emergency_fd = None

    def get_mmap_buffer(self) -> Optional[MMapLogBuffer]:
        """
        Get the memory-mapped buffer.

        Returns:
            MMapLogBuffer instance or None if not configured
        """
        return self._mmap_buffer

    def recover_buffered_entries(self) -> List[str]:
        """
        Recover entries from memory-mapped buffer.

        Returns:
            List of recovered log entries
        """
        if self._mmap_buffer is None:
            return []

        return self._mmap_buffer.recover()

    def get_emergency_buffer(self) -> List[str]:
        """
        Get current emergency buffer contents.

        Returns:
            List of recent log entries
        """
        return list(self._emergency_buffer)

    def set_crash_safety_enabled(self, enabled: bool) -> None:
        """
        Enable or disable crash safety features.

        Args:
            enabled: Whether to enable crash safety
        """
        self._crash_safety_enabled = enabled

    def is_crash_safety_enabled(self) -> bool:
        """
        Check if crash safety is enabled.

        Returns:
            True if crash safety is enabled
        """
        return self._crash_safety_enabled


def create_emergency_log_file(
    base_path: Optional[str] = None
) -> tuple:
    """
    Create an emergency log file and return path and file descriptor.

    Args:
        base_path: Base directory for emergency log (uses temp if None)

    Returns:
        Tuple of (path, file_descriptor)
    """
    if base_path:
        directory = Path(base_path)
    else:
        directory = Path(tempfile.gettempdir())

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"emergency_log_{os.getpid()}.log"

    # Open with O_WRONLY | O_CREAT | O_APPEND for signal-safe writes
    fd = os.open(
        str(path),
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o644
    )

    return str(path), fd
