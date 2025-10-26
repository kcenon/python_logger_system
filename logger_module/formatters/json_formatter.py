"""
JSON formatter for structured logging

Formats log entries as JSON objects
"""

import json
from logger_module.core.log_entry import LogEntry
from logger_module.formatters.base_formatter import BaseFormatter


class JSONFormatter(BaseFormatter):
    """
    Format log entries as JSON objects.

    Produces structured log output suitable for log aggregation systems.
    """

    def __init__(
        self,
        include_extra: bool = True,
        include_thread_info: bool = True,
        include_source_info: bool = False,
        indent: int = None,
        ensure_ascii: bool = False
    ):
        """
        Initialize JSON formatter.

        Args:
            include_extra: Include extra fields in output
            include_thread_info: Include thread_id and thread_name
            include_source_info: Include file_name, line_number, function_name
            indent: JSON indentation (None for compact, 2 for readable)
            ensure_ascii: Escape non-ASCII characters

        Example:
            # Compact JSON (one line per entry)
            formatter = JSONFormatter()

            # Pretty-printed JSON
            formatter = JSONFormatter(indent=2)

            # Minimal JSON
            formatter = JSONFormatter(
                include_extra=False,
                include_thread_info=False
            )
        """
        self.include_extra = include_extra
        self.include_thread_info = include_thread_info
        self.include_source_info = include_source_info
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def format(self, entry: LogEntry) -> str:
        """
        Format log entry as JSON.

        Args:
            entry: Log entry to format

        Returns:
            JSON string
        """
        # Build base dictionary
        log_dict = {
            "timestamp": entry.timestamp.isoformat(),
            "level": entry.level.name,
            "message": entry.message,
        }

        # Add logger name if set
        if entry.logger_name:
            log_dict["logger"] = entry.logger_name

        # Add thread info
        if self.include_thread_info:
            log_dict["thread_id"] = entry.thread_id
            log_dict["thread_name"] = entry.thread_name

        # Add source info
        if self.include_source_info and (entry.file_name or entry.function_name):
            source_info = {}
            if entry.file_name:
                source_info["file"] = entry.file_name
            if entry.line_number:
                source_info["line"] = entry.line_number
            if entry.function_name:
                source_info["function"] = entry.function_name
            if source_info:
                log_dict["source"] = source_info

        # Add extra fields
        if self.include_extra and entry.extra:
            log_dict["extra"] = entry.extra

        return json.dumps(
            log_dict,
            indent=self.indent,
            ensure_ascii=self.ensure_ascii
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"JSONFormatter(indent={self.indent})"
