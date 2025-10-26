"""
Callback-based filter

Filters log entries using custom callback functions
"""

from typing import Callable
from logger_module.core.log_entry import LogEntry
from logger_module.filters.base_filter import BaseFilter


class CallbackFilter(BaseFilter):
    """
    Filter log entries using a custom callback function.

    Provides maximum flexibility for filtering logic.
    """

    def __init__(self, callback: Callable[[LogEntry], bool]):
        """
        Initialize callback filter.

        Args:
            callback: Function that takes LogEntry and returns bool.
                     Should return True to log the entry, False to discard it.

        Example:
            # Filter based on thread name
            def only_main_thread(entry):
                return entry.thread_name == "MainThread"

            filter = CallbackFilter(only_main_thread)

            # Filter based on extra fields
            def has_user_id(entry):
                return "user_id" in entry.extra

            filter = CallbackFilter(has_user_id)

            # Complex condition
            def complex_filter(entry):
                return (entry.level >= LogLevel.WARN or
                        "critical" in entry.message.lower())

            filter = CallbackFilter(complex_filter)
        """
        if not callable(callback):
            raise TypeError("callback must be callable")

        self.callback = callback

    def should_log(self, entry: LogEntry) -> bool:
        """
        Use callback to determine if entry should be logged.

        Args:
            entry: Log entry to check

        Returns:
            Result of callback function

        Raises:
            Exception: If callback raises an exception, it's propagated
        """
        try:
            return self.callback(entry)
        except Exception as e:
            # Log the error and allow the entry through
            print(f"Filter callback error: {e}")
            return True

    def __repr__(self) -> str:
        """String representation."""
        callback_name = getattr(self.callback, '__name__', repr(self.callback))
        return f"CallbackFilter(callback={callback_name})"
