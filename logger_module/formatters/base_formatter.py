"""
Base formatter interface

Equivalent to C++ formatter_interface.h
"""

from abc import ABC, abstractmethod
from logger_module.core.log_entry import LogEntry


class BaseFormatter(ABC):
    """
    Abstract base class for log formatters.

    Formatters convert LogEntry objects into formatted strings.
    """

    @abstractmethod
    def format(self, entry: LogEntry) -> str:
        """
        Format a log entry into a string.

        Args:
            entry: The log entry to format

        Returns:
            Formatted string representation of the log entry
        """
        pass

    def __call__(self, entry: LogEntry) -> str:
        """Allow formatters to be callable."""
        return self.format(entry)
