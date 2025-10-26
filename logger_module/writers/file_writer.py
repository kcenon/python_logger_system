"""File writer"""

from pathlib import Path
from typing import Optional
from logger_module.core.log_entry import LogEntry


class FileWriter:
    """Write logs to file."""

    def __init__(
        self,
        filepath: str,
        mode: str = "a",
        encoding: str = "utf-8",
        formatter=None
    ):
        """
        Initialize file writer.

        Args:
            filepath: Path to log file
            mode: File open mode (default: 'a' for append)
            encoding: File encoding (default: 'utf-8')
            formatter: Log formatter (default: uses entry's __str__)
        """
        self.filepath = Path(filepath)
        self.mode = mode
        self.encoding = encoding
        self.formatter = formatter
        self._file = None
        self._open()

    def _open(self):
        """Open log file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filepath, self.mode, encoding=self.encoding)

    def write(self, entry: LogEntry):
        """Write log entry to file."""
        if self._file:
            if self.formatter:
                msg = self.formatter.format(entry)
            else:
                msg = str(entry)
            self._file.write(msg + "\n")

    def flush(self):
        """Flush file buffer."""
        if self._file:
            self._file.flush()

    def close(self):
        """Close file."""
        if self._file:
            self._file.close()
            self._file = None
