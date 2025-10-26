"""
Pattern-based filter using regular expressions

Filters log entries based on message content matching
"""

import re
from typing import Union, Pattern
from logger_module.core.log_entry import LogEntry
from logger_module.filters.base_filter import BaseFilter


class PatternFilter(BaseFilter):
    """
    Filter log entries based on regex pattern matching.

    Can be configured to include or exclude matching messages.
    """

    def __init__(
        self,
        pattern: Union[str, Pattern],
        exclude: bool = False,
        case_sensitive: bool = True
    ):
        """
        Initialize pattern filter.

        Args:
            pattern: Regular expression pattern (string or compiled Pattern)
            exclude: If True, exclude matching messages. If False, include only matching messages.
            case_sensitive: Whether pattern matching is case-sensitive

        Example:
            # Only log messages containing "error"
            filter = PatternFilter(r".*error.*", exclude=False)

            # Exclude debug messages
            filter = PatternFilter(r"^DEBUG:", exclude=True)

            # Case-insensitive matching
            filter = PatternFilter(r"warning", case_sensitive=False)
        """
        if isinstance(pattern, str):
            flags = 0 if case_sensitive else re.IGNORECASE
            self.pattern = re.compile(pattern, flags)
        else:
            self.pattern = pattern

        self.exclude = exclude

    def should_log(self, entry: LogEntry) -> bool:
        """
        Check if entry message matches the pattern.

        Args:
            entry: Log entry to check

        Returns:
            True if entry should be logged based on pattern match, False otherwise
        """
        matches = self.pattern.search(entry.message) is not None

        # If exclude=True, return False when matches (exclude matching entries)
        # If exclude=False, return True when matches (include only matching entries)
        return not matches if self.exclude else matches

    def __repr__(self) -> str:
        """String representation."""
        mode = "exclude" if self.exclude else "include"
        return f"PatternFilter(pattern='{self.pattern.pattern}', mode={mode})"
