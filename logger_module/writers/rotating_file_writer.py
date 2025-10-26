"""Rotating file writer"""

from pathlib import Path
import os
from typing import Optional
from logger_module.core.log_entry import LogEntry


class RotatingFileWriter:
    """Write logs with size-based rotation."""

    def __init__(
        self,
        filepath: str,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        encoding: str = "utf-8",
        formatter=None
    ):
        """
        Initialize rotating file writer.

        Args:
            filepath: Path to log file
            max_bytes: Maximum file size before rotation
            backup_count: Number of backup files to keep
            encoding: File encoding (default: 'utf-8')
            formatter: Log formatter (default: uses entry's __str__)
        """
        self.filepath = Path(filepath)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        self.formatter = formatter
        self._file = None
        self._open()

    def _open(self):
        """Open log file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filepath, "a", encoding=self.encoding)

    def _should_rotate(self) -> bool:
        """Check if file should be rotated."""
        if not self._file:
            return False
        return self._file.tell() >= self.max_bytes

    def _do_rotate(self):
        """Perform file rotation."""
        if self._file:
            self._file.close()
        
        # Rotate existing files
        for i in range(self.backup_count - 1, 0, -1):
            src = self.filepath.with_suffix(f".{i}")
            dst = self.filepath.with_suffix(f".{i+1}")
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)
        
        # Move current to .1
        if self.filepath.exists():
            self.filepath.rename(self.filepath.with_suffix(".1"))
        
        self._open()

    def write(self, entry: LogEntry):
        """Write log entry with rotation."""
        if self._should_rotate():
            self._do_rotate()
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
