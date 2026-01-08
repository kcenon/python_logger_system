"""
Safety module - Crash-safe logging infrastructure

Provides crash-safe logging capabilities including:
- Signal handlers for emergency flush
- Memory-mapped buffers for durability
- Log recovery utilities
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
]
