"""Console writer with ANSI colors"""

import sys
from typing import Optional
from logger_module.core.log_entry import LogEntry


class ConsoleWriter:
    """Write logs to console with optional colors."""

    def __init__(self, colored: bool = True, stream=None, formatter=None):
        """
        Initialize console writer.

        Args:
            colored: Use ANSI color codes
            stream: Output stream (default: sys.stderr)
            formatter: Log formatter (default: uses entry's __str__)
        """
        self.colored = colored
        self.stream = stream or sys.stderr
        self.formatter = formatter

    def write(self, entry: LogEntry):
        """Write log entry to console."""
        # Format the entry
        if self.formatter:
            msg = self.formatter.format(entry)
        else:
            msg = str(entry)

        # Add colors if enabled
        if self.colored and not self.formatter:
            msg = f"{entry.level.color_code}{msg}{entry.level.reset_code}"

        self.stream.write(msg + "\n")
        self.stream.flush()

    def flush(self):
        """Flush stream."""
        self.stream.flush()
