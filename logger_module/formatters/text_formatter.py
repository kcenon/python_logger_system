"""
Text formatter with customizable template

Formats log entries using a template string with placeholders
"""

from logger_module.core.log_entry import LogEntry
from logger_module.formatters.base_formatter import BaseFormatter


class TextFormatter(BaseFormatter):
    """
    Format log entries using a customizable template.

    Supports placeholders for all LogEntry fields.
    """

    DEFAULT_TEMPLATE = "[{timestamp}] [{level:8}] [{thread}] {message}"

    def __init__(self, template: str = None, timestamp_format: str = "%Y-%m-%d %H:%M:%S.%f"):
        """
        Initialize text formatter.

        Args:
            template: Format template with placeholders.
                     Available placeholders:
                     - {timestamp}: Timestamp
                     - {level}: Log level name
                     - {level:8}: Log level with padding
                     - {message}: Log message
                     - {thread}: Thread name
                     - {thread_id}: Thread ID
                     - {logger}: Logger name
                     - {file}: File name
                     - {line}: Line number
                     - {function}: Function name
            timestamp_format: strftime format for timestamps

        Example:
            # Default format
            formatter = TextFormatter()

            # Custom format
            formatter = TextFormatter("{level} - {message}")

            # Detailed format
            formatter = TextFormatter(
                "{timestamp} [{level}] {logger}:{function} - {message}"
            )
        """
        self.template = template or self.DEFAULT_TEMPLATE
        self.timestamp_format = timestamp_format

    def format(self, entry: LogEntry) -> str:
        """
        Format log entry using the template.

        Args:
            entry: Log entry to format

        Returns:
            Formatted string
        """
        # Format timestamp
        timestamp_str = entry.timestamp.strftime(self.timestamp_format)[:-3]  # Remove last 3 digits

        # Build format dictionary
        format_dict = {
            "timestamp": timestamp_str,
            "level": entry.level.name,
            "message": entry.message,
            "thread": entry.thread_name,
            "thread_id": entry.thread_id,
            "logger": entry.logger_name,
            "file": entry.file_name,
            "line": entry.line_number,
            "function": entry.function_name,
        }

        try:
            return self.template.format(**format_dict)
        except KeyError as e:
            # Fallback if template has unknown placeholder
            return f"[FORMAT ERROR: {e}] {entry.message}"

    def __repr__(self) -> str:
        """String representation."""
        return f"TextFormatter(template='{self.template}')"
