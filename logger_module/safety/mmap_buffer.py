"""
Memory-mapped log buffer for crash-resistant logging

Provides a crash-resistant buffer using memory-mapped files.
Data written to this buffer survives application crashes.
"""

from __future__ import annotations

import mmap
import os
import struct
from pathlib import Path
from typing import Optional, List
from datetime import datetime


# Buffer header structure:
# - 4 bytes: magic number (0x4C4F4742 = "LOGB")
# - 4 bytes: version
# - 4 bytes: write offset
# - 4 bytes: entry count
# - 4 bytes: flags (1 = dirty, needs recovery)
# - 12 bytes: reserved
HEADER_SIZE = 32
MAGIC_NUMBER = 0x4C4F4742  # "LOGB" in hex
VERSION = 1
FLAG_DIRTY = 0x01
FLAG_RECOVERED = 0x02


class MMapLogBuffer:
    """
    Memory-mapped buffer for crash-resistant logging.

    This buffer uses memory-mapped files to ensure that log data
    survives application crashes. The OS kernel manages the sync
    to disk, providing durability guarantees.

    Attributes:
        path: Path to the memory-mapped file
        size: Size of the buffer in bytes
    """

    def __init__(
        self,
        path: str,
        size: int = 1024 * 1024,
        create: bool = True
    ):
        """
        Initialize memory-mapped log buffer.

        Args:
            path: Path to buffer file
            size: Buffer size in bytes (default: 1MB)
            create: Create file if it doesn't exist
        """
        self.path = Path(path)
        self.size = size
        self._mmap: Optional[mmap.mmap] = None
        self._file = None
        self._closed = False

        if create:
            self._create_or_open()
        else:
            self._open_existing()

    def _create_or_open(self) -> None:
        """Create new buffer file or open existing one."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = self.path.exists() and self.path.stat().st_size >= HEADER_SIZE

        if file_exists:
            self._open_existing()
        else:
            self._create_new()

    def _create_new(self) -> None:
        """Create a new buffer file."""
        # Create file with proper size
        with open(self.path, 'wb') as f:
            f.write(b'\x00' * self.size)

        self._file = open(self.path, 'r+b')
        self._mmap = mmap.mmap(self._file.fileno(), self.size)

        # Write header
        self._write_header(
            write_offset=HEADER_SIZE,
            entry_count=0,
            flags=FLAG_DIRTY
        )

    def _open_existing(self) -> None:
        """Open existing buffer file."""
        if not self.path.exists():
            raise FileNotFoundError(f"Buffer file not found: {self.path}")

        file_size = self.path.stat().st_size
        self._file = open(self.path, 'r+b')
        self._mmap = mmap.mmap(self._file.fileno(), file_size)

        # Validate header
        magic = struct.unpack('<I', self._mmap[0:4])[0]
        if magic != MAGIC_NUMBER:
            raise ValueError(f"Invalid buffer file: {self.path}")

        # Update size from actual file
        self.size = file_size

    def _write_header(
        self,
        write_offset: int,
        entry_count: int,
        flags: int
    ) -> None:
        """Write buffer header."""
        header = struct.pack(
            '<IIIII12x',  # 5 uints + 12 reserved bytes
            MAGIC_NUMBER,
            VERSION,
            write_offset,
            entry_count,
            flags
        )
        self._mmap[0:HEADER_SIZE] = header
        self._mmap.flush()

    def _read_header(self) -> tuple:
        """Read buffer header."""
        data = self._mmap[0:HEADER_SIZE]
        magic, version, write_offset, entry_count, flags = struct.unpack(
            '<IIIII12x', data
        )
        return magic, version, write_offset, entry_count, flags

    def write(self, data: bytes) -> bool:
        """
        Write data to buffer.

        Args:
            data: Bytes to write

        Returns:
            True if write succeeded, False if buffer full
        """
        if self._closed or self._mmap is None:
            return False

        _, _, write_offset, entry_count, flags = self._read_header()

        # Each entry: 4 bytes length + data + newline
        entry_size = 4 + len(data) + 1

        # Check if we have space
        if write_offset + entry_size > self.size:
            # Wrap around (circular buffer)
            write_offset = HEADER_SIZE

        # Write entry length
        self._mmap[write_offset:write_offset + 4] = struct.pack('<I', len(data))
        write_offset += 4

        # Write data
        self._mmap[write_offset:write_offset + len(data)] = data
        write_offset += len(data)

        # Write newline marker
        self._mmap[write_offset:write_offset + 1] = b'\n'
        write_offset += 1

        # Update header
        self._write_header(
            write_offset=write_offset,
            entry_count=entry_count + 1,
            flags=FLAG_DIRTY
        )

        return True

    def write_entry(self, message: str) -> bool:
        """
        Write a log entry with timestamp.

        Args:
            message: Log message

        Returns:
            True if write succeeded
        """
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] {message}"
        return self.write(entry.encode('utf-8', errors='replace'))

    def flush(self) -> None:
        """Flush buffer to disk."""
        if self._mmap is not None:
            self._mmap.flush()

    def recover(self) -> List[str]:
        """
        Recover entries from buffer after crash.

        Returns:
            List of recovered log entries
        """
        if self._mmap is None:
            return []

        _, _, write_offset, entry_count, flags = self._read_header()

        entries = []
        offset = HEADER_SIZE

        while offset < write_offset and offset < self.size - 4:
            try:
                # Read entry length
                entry_len = struct.unpack('<I', self._mmap[offset:offset + 4])[0]

                if entry_len == 0 or entry_len > self.size:
                    break

                offset += 4

                # Read entry data
                if offset + entry_len > self.size:
                    break

                data = self._mmap[offset:offset + entry_len]
                entries.append(data.decode('utf-8', errors='replace'))
                offset += entry_len + 1  # +1 for newline

            except Exception:
                break

        return entries

    def clear(self) -> None:
        """Clear buffer contents."""
        if self._mmap is not None:
            self._write_header(
                write_offset=HEADER_SIZE,
                entry_count=0,
                flags=0
            )
            # Zero out data area
            self._mmap[HEADER_SIZE:] = b'\x00' * (self.size - HEADER_SIZE)
            self._mmap.flush()

    def mark_recovered(self) -> None:
        """Mark buffer as recovered."""
        if self._mmap is not None:
            _, _, write_offset, entry_count, _ = self._read_header()
            self._write_header(
                write_offset=write_offset,
                entry_count=entry_count,
                flags=FLAG_RECOVERED
            )

    def needs_recovery(self) -> bool:
        """
        Check if buffer needs recovery.

        Returns:
            True if buffer was not cleanly closed
        """
        if self._mmap is None:
            return False

        _, _, _, _, flags = self._read_header()
        return bool(flags & FLAG_DIRTY) and not bool(flags & FLAG_RECOVERED)

    def get_stats(self) -> dict:
        """
        Get buffer statistics.

        Returns:
            Dictionary with buffer stats
        """
        if self._mmap is None:
            return {}

        _, version, write_offset, entry_count, flags = self._read_header()

        return {
            'version': version,
            'size': self.size,
            'used': write_offset - HEADER_SIZE,
            'available': self.size - write_offset,
            'entry_count': entry_count,
            'dirty': bool(flags & FLAG_DIRTY),
            'recovered': bool(flags & FLAG_RECOVERED),
        }

    def close(self) -> None:
        """Close buffer and mark as clean."""
        if self._closed:
            return

        if self._mmap is not None:
            # Mark as cleanly closed
            _, _, write_offset, entry_count, _ = self._read_header()
            self._write_header(
                write_offset=write_offset,
                entry_count=entry_count,
                flags=0  # Clear dirty flag
            )
            self._mmap.close()
            self._mmap = None

        if self._file is not None:
            self._file.close()
            self._file = None

        self._closed = True

    def __enter__(self) -> 'MMapLogBuffer':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
