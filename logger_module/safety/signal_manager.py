"""
Signal Manager for crash-safe logging

Manages signal handlers to ensure logs are flushed on crashes,
unexpected terminations, and system failures.

Equivalent to C++ safety/crash_safe_logger.h
"""

from __future__ import annotations

import signal
import sys
import atexit
import os
from typing import TYPE_CHECKING, Set, Dict, Callable, Optional, Any
from weakref import WeakSet

if TYPE_CHECKING:
    from types import FrameType


class SignalManager:
    """
    Manages signal handlers for crash-safe logging.

    This class provides a centralized mechanism to register loggers
    for emergency flush when the application receives termination signals.

    Thread Safety:
        This class uses WeakSet for thread-safe logger registration
        and properly chains signal handlers.
    """

    _loggers: WeakSet = WeakSet()
    _original_handlers: Dict[int, Any] = {}
    _initialized: bool = False

    # Standard crash/termination signals
    CRASH_SIGNALS = [
        signal.SIGTERM,
        signal.SIGINT,
        signal.SIGABRT,
    ]

    # Unix-specific signals (not available on Windows)
    if hasattr(signal, 'SIGHUP'):
        CRASH_SIGNALS.append(signal.SIGHUP)
    if hasattr(signal, 'SIGQUIT'):
        CRASH_SIGNALS.append(signal.SIGQUIT)

    @classmethod
    def register_logger(cls, logger: Any) -> None:
        """
        Register a logger for emergency flush.

        Args:
            logger: Logger instance with emergency_flush() method
        """
        cls._loggers.add(logger)
        if not cls._initialized:
            cls._initialize()

    @classmethod
    def unregister_logger(cls, logger: Any) -> None:
        """
        Unregister a logger from emergency flush.

        Args:
            logger: Logger instance to unregister
        """
        cls._loggers.discard(logger)

    @classmethod
    def _initialize(cls) -> None:
        """Set up signal handlers and atexit."""
        for sig in cls.CRASH_SIGNALS:
            try:
                cls._original_handlers[sig] = signal.signal(
                    sig, cls._signal_handler
                )
            except (OSError, ValueError):
                # Signal may not be settable in some contexts
                pass

        atexit.register(cls._atexit_handler)
        sys.excepthook = cls._exception_hook
        cls._initialized = True

    @classmethod
    def _signal_handler(
        cls,
        signum: int,
        frame: Optional[FrameType]
    ) -> None:
        """
        Emergency flush on signal.

        Args:
            signum: Signal number received
            frame: Current stack frame
        """
        cls._emergency_flush_all()

        # Call original handler if it exists and is callable
        original = cls._original_handlers.get(signum)
        if original and callable(original):
            original(signum, frame)
        elif original is not signal.SIG_IGN:
            # Restore default behavior and re-raise
            signal.signal(signum, signal.SIG_DFL)
            if hasattr(signal, 'raise_signal'):
                signal.raise_signal(signum)
            else:
                # Python < 3.8 fallback
                os.kill(os.getpid(), signum)

    @classmethod
    def _exception_hook(
        cls,
        exc_type: type,
        exc_value: BaseException,
        exc_tb: Any
    ) -> None:
        """
        Flush on unhandled exception.

        Args:
            exc_type: Exception type
            exc_value: Exception instance
            exc_tb: Traceback object
        """
        cls._emergency_flush_all()
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    @classmethod
    def _atexit_handler(cls) -> None:
        """Flush on normal exit."""
        cls._emergency_flush_all()

    @classmethod
    def _emergency_flush_all(cls) -> None:
        """
        Flush all registered loggers.

        This method is designed to be as safe as possible,
        catching any exceptions to ensure all loggers get a chance to flush.
        """
        for logger in list(cls._loggers):
            try:
                if hasattr(logger, 'emergency_flush'):
                    logger.emergency_flush()
                elif hasattr(logger, 'flush'):
                    logger.flush()
            except Exception:
                pass  # Best effort - don't let one logger failure affect others

    @classmethod
    def reset(cls) -> None:
        """
        Reset signal manager state.

        Useful for testing. Restores original signal handlers.
        """
        for sig, handler in cls._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (OSError, ValueError):
                pass

        cls._original_handlers.clear()
        cls._loggers.clear()
        cls._initialized = False

    @classmethod
    def get_registered_count(cls) -> int:
        """
        Get number of registered loggers.

        Returns:
            Number of currently registered loggers
        """
        return len(cls._loggers)

    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if signal manager is initialized.

        Returns:
            True if signal handlers are installed
        """
        return cls._initialized
