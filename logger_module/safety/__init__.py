"""
Safety module - Crash-safe logging infrastructure

Provides crash-safe logging capabilities including:
- Signal handlers for emergency flush
- Memory-mapped buffers for durability
- Log recovery utilities
- Critical writers for guaranteed log persistence
"""

from logger_module.safety.signal_manager import SignalManager
from logger_module.safety.mmap_buffer import MMapLogBuffer
from logger_module.safety.crash_safe_mixin import (
    CrashSafeLoggerMixin,
    create_emergency_log_file,
)
from logger_module.safety.recovery import (
    recover_from_mmap,
    recover_from_emergency_logs,
    find_crash_logs,
    recover_all,
    cleanup_old_crash_logs,
)
from logger_module.safety.critical_writer import CriticalWriter
from logger_module.safety.wal_critical_writer import WALCriticalWriter

__all__ = [
    "SignalManager",
    "MMapLogBuffer",
    "CrashSafeLoggerMixin",
    "create_emergency_log_file",
    "recover_from_mmap",
    "recover_from_emergency_logs",
    "find_crash_logs",
    "recover_all",
    "cleanup_old_crash_logs",
    "CriticalWriter",
    "WALCriticalWriter",
]
