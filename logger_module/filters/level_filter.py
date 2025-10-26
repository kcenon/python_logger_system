"""
Level-based filter

Filters log entries based on log level range
"""

from typing import Optional
from logger_module.core.log_entry import LogEntry
from logger_module.core.log_level import LogLevel
from logger_module.filters.base_filter import BaseFilter


class LevelFilter(BaseFilter):
    """
    Filter log entries based on log level.

    Allows filtering by minimum and/or maximum log level.
    """

    def __init__(
        self,
        min_level: Optional[LogLevel] = None,
        max_level: Optional[LogLevel] = None
    ):
        """
        Initialize level filter.

        Args:
            min_level: Minimum log level (inclusive). If None, no minimum.
            max_level: Maximum log level (inclusive). If None, no maximum.

        Example:
            # Only log WARN and above
            filter = LevelFilter(min_level=LogLevel.WARN)

            # Only log DEBUG to INFO
            filter = LevelFilter(min_level=LogLevel.DEBUG, max_level=LogLevel.INFO)
        """
        self.min_level = min_level
        self.max_level = max_level

    def should_log(self, entry: LogEntry) -> bool:
        """
        Check if entry's level is within the specified range.

        Args:
            entry: Log entry to check

        Returns:
            True if entry level is within range, False otherwise
        """
        if self.min_level is not None and entry.level < self.min_level:
            return False

        if self.max_level is not None and entry.level > self.max_level:
            return False

        return True

    def __repr__(self) -> str:
        """String representation."""
        return f"LevelFilter(min={self.min_level}, max={self.max_level})"
