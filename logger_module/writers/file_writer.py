"""File writer"""

from pathlib import Path
from logger_module.core.log_entry import LogEntry


class FileWriter:
    """Write logs to file."""

    def __init__(self, filepath: str, mode: str = "a", encoding: str = "utf-8"):
        self.filepath = Path(filepath)
        self.mode = mode
        self.encoding = encoding
        self._file = None
        self._open()

    def _open(self):
        """Open log file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filepath, self.mode, encoding=self.encoding)

    def write(self, entry: LogEntry):
        """Write log entry to file."""
        if self._file:
            self._file.write(f"{entry}\n")

    def flush(self):
        """Flush file buffer."""
        if self._file:
            self._file.flush()

    def close(self):
        """Close file."""
        if self._file:
            self._file.close()
            self._file = None
