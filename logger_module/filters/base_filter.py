"""
Base filter interface

Equivalent to C++ filter_interface.h
"""

from abc import ABC, abstractmethod
from logger_module.core.log_entry import LogEntry


class BaseFilter(ABC):
    """
    Abstract base class for log filters.

    Filters determine whether a log entry should be processed or discarded.
    """

    @abstractmethod
    def should_log(self, entry: LogEntry) -> bool:
        """
        Determine if a log entry should be logged.

        Args:
            entry: The log entry to filter

        Returns:
            True if the entry should be logged, False otherwise
        """
        pass

    def __call__(self, entry: LogEntry) -> bool:
        """Allow filters to be callable."""
        return self.should_log(entry)
