"""
Compact formatter for minimal log output

Produces concise single-line log entries
"""

from logger_module.core.log_entry import LogEntry
from logger_module.formatters.base_formatter import BaseFormatter


class CompactFormatter(BaseFormatter):
    """
    Format log entries in a compact single-line format.

    Optimized for production environments with high log volume.
    """

    def __init__(self, include_timestamp: bool = True, include_logger: bool = False):
        """
        Initialize compact formatter.

        Args:
            include_timestamp: Include timestamp in output
            include_logger: Include logger name in output

        Example:
            # Minimal format: "LEVEL: message"
            formatter = CompactFormatter(include_timestamp=False)

            # With timestamp: "12:34:56 LEVEL: message"
            formatter = CompactFormatter()

            # With logger: "12:34:56 [myapp] LEVEL: message"
            formatter = CompactFormatter(include_logger=True)
        """
        self.include_timestamp = include_timestamp
        self.include_logger = include_logger

    def format(self, entry: LogEntry) -> str:
        """
        Format log entry in compact format.

        Args:
            entry: Log entry to format

        Returns:
            Compact formatted string
        """
        parts = []

        # Add timestamp (HH:MM:SS format)
        if self.include_timestamp:
            time_str = entry.timestamp.strftime("%H:%M:%S")
            parts.append(time_str)

        # Add logger name
        if self.include_logger and entry.logger_name:
            parts.append(f"[{entry.logger_name}]")

        # Add level (abbreviated)
        level_abbrev = {
            "TRACE": "TRC",
            "DEBUG": "DBG",
            "INFO": "INF",
            "WARN": "WRN",
            "ERROR": "ERR",
            "CRITICAL": "CRT"
        }.get(entry.level.name, entry.level.name[:3])

        parts.append(f"{level_abbrev}:")

        # Add message
        parts.append(entry.message)

        return " ".join(parts)

    def __repr__(self) -> str:
        """String representation."""
        return f"CompactFormatter(timestamp={self.include_timestamp}, logger={self.include_logger})"
