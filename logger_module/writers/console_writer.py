"""Console writer with ANSI colors"""

import sys
from logger_module.core.log_entry import LogEntry


class ConsoleWriter:
    """Write logs to console with optional colors."""

    def __init__(self, colored: bool = True, stream=None):
        self.colored = colored
        self.stream = stream or sys.stderr

    def write(self, entry: LogEntry):
        """Write log entry to console."""
        if self.colored:
            msg = f"{entry.level.color_code}{entry}{entry.level.reset_code}\n"
        else:
            msg = f"{entry}\n"
        self.stream.write(msg)
        self.stream.flush()

    def flush(self):
        """Flush stream."""
        self.stream.flush()
