"""
Write-Ahead Logging (WAL) Critical Writer

Provides crash recovery capability by writing logs to a WAL file
before passing to the inner writer. On crash, logs can be recovered
from the WAL file.

Equivalent to C++ safety/critical_writer.h WAL feature
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Set, Optional, Any, List

from logger_module.core.log_level import LogLevel
from logger_module.core.log_entry import LogEntry
from logger_module.safety.critical_writer import CriticalWriter

if TYPE_CHECKING:
    pass


class WALCriticalWriter(CriticalWriter):
    """
    CriticalWriter with write-ahead logging for crash recovery.

    Writes logs to a WAL file before passing to the inner writer.
    If the application crashes, logs can be recovered from the WAL.

    WAL Format:
        Each line is a JSON-encoded log entry with a sequence number.
        After successful write to inner writer, entries are marked as committed.
    """

    def __init__(
        self,
        inner_writer: Any,
        wal_path: str,
        force_flush_levels: Optional[Set[LogLevel]] = None,
        enable_signal_handlers: bool = True,
        sync_on_critical: bool = True,
        auto_cleanup: bool = True
    ):
        """
        Initialize WAL critical writer.

        Args:
            inner_writer: Writer to wrap
            wal_path: Path to WAL file for crash recovery
            force_flush_levels: Log levels that trigger immediate flush
            enable_signal_handlers: Register signal handlers for crashes
            sync_on_critical: Force OS disk sync for critical logs
            auto_cleanup: Automatically clean up WAL after successful commit
        """
        super().__init__(
            inner_writer,
            force_flush_levels,
            enable_signal_handlers,
            sync_on_critical
        )

        self.wal_path = Path(wal_path)
        self.auto_cleanup = auto_cleanup
        self._sequence = 0
        self._wal_file = None
        self._committed_sequence = 0

        self._open_wal()

    def _open_wal(self) -> None:
        """Open WAL file for writing."""
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        self._wal_file = open(
            self.wal_path,
            'a',
            encoding='utf-8',
            buffering=1  # Line buffered
        )

        # Recover sequence number from existing WAL
        if self.wal_path.exists():
            self._recover_sequence()

    def _recover_sequence(self) -> None:
        """Recover sequence number from existing WAL file."""
        try:
            with open(self.wal_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        seq = data.get('_wal_seq', 0)
                        if seq > self._sequence:
                            self._sequence = seq
                        if data.get('_wal_committed'):
                            self._committed_sequence = max(
                                self._committed_sequence,
                                seq
                            )
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass

    def write(self, entry: "LogEntry") -> None:
        """
        Write log entry with WAL protection.

        Writes to WAL first, then to inner writer, then marks as committed.

        Args:
            entry: Log entry to write
        """
        if self._closed:
            return

        # Increment sequence
        self._sequence += 1

        # Write to WAL first
        self._write_to_wal(entry, committed=False)

        # Write to inner writer
        super().write(entry)

        # Mark as committed
        self._mark_committed(self._sequence)

        # Auto cleanup if enabled
        if self.auto_cleanup and self._sequence % 100 == 0:
            self._cleanup_committed()

    def _write_to_wal(self, entry: "LogEntry", committed: bool) -> None:
        """
        Write entry to WAL file.

        Args:
            entry: Log entry to write
            committed: Whether entry has been committed
        """
        if not self._wal_file:
            return

        try:
            wal_entry = {
                '_wal_seq': self._sequence,
                '_wal_committed': committed,
                'timestamp': entry.timestamp.isoformat(),
                'level': entry.level.name,
                'message': entry.message,
                'logger_name': entry.logger_name,
                'source_file': entry.source_file,
                'source_line': entry.source_line,
                'context': entry.context
            }

            self._wal_file.write(json.dumps(wal_entry) + '\n')
            self._wal_file.flush()
            os.fsync(self._wal_file.fileno())
        except (OSError, IOError):
            pass  # Best effort

    def _mark_committed(self, sequence: int) -> None:
        """
        Mark entry as committed in WAL.

        Args:
            sequence: Sequence number to mark as committed
        """
        if not self._wal_file:
            return

        try:
            commit_marker = {
                '_wal_seq': sequence,
                '_wal_committed': True
            }
            self._wal_file.write(json.dumps(commit_marker) + '\n')
            self._wal_file.flush()
            os.fsync(self._wal_file.fileno())
            self._committed_sequence = sequence
        except (OSError, IOError):
            pass

    def _cleanup_committed(self) -> None:
        """Remove committed entries from WAL to prevent unbounded growth."""
        if not self.wal_path.exists():
            return

        try:
            # Read uncommitted entries
            uncommitted = []
            with open(self.wal_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        seq = data.get('_wal_seq', 0)
                        if seq > self._committed_sequence:
                            uncommitted.append(line)
                    except json.JSONDecodeError:
                        continue

            # Rewrite WAL with only uncommitted entries
            self._wal_file.close()
            with open(self.wal_path, 'w', encoding='utf-8') as f:
                for line in uncommitted:
                    f.write(line)
            self._wal_file = open(
                self.wal_path,
                'a',
                encoding='utf-8',
                buffering=1
            )
        except (OSError, IOError):
            pass

    def recover(self) -> List[LogEntry]:
        """
        Recover uncommitted entries from WAL after crash.

        Returns:
            List of LogEntry objects that were not committed
        """
        entries = []

        if not self.wal_path.exists():
            return entries

        try:
            committed_seqs = set()
            pending_entries = {}

            # First pass: collect all entries and committed markers
            with open(self.wal_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        seq = data.get('_wal_seq', 0)

                        if data.get('_wal_committed') and 'message' not in data:
                            committed_seqs.add(seq)
                        elif 'message' in data:
                            pending_entries[seq] = data
                    except json.JSONDecodeError:
                        continue

            # Find uncommitted entries
            for seq in sorted(pending_entries.keys()):
                if seq not in committed_seqs:
                    data = pending_entries[seq]
                    entry = LogEntry(
                        message=data['message'],
                        level=LogLevel.from_string(data['level']),
                        logger_name=data.get('logger_name', 'recovered'),
                        source_file=data.get('source_file'),
                        source_line=data.get('source_line'),
                        context=data.get('context', {})
                    )
                    entries.append(entry)

        except (OSError, IOError):
            pass

        return entries

    def close(self) -> None:
        """Close the writer and WAL file."""
        if self._closed:
            return

        # Cleanup before closing
        if self.auto_cleanup:
            self._cleanup_committed()

        if self._wal_file:
            try:
                self._wal_file.flush()
                os.fsync(self._wal_file.fileno())
                self._wal_file.close()
            except (OSError, IOError):
                pass
            self._wal_file = None

        super().close()

    def clear_wal(self) -> None:
        """Clear the WAL file (use after manual recovery)."""
        if self._wal_file:
            self._wal_file.close()

        try:
            self.wal_path.unlink(missing_ok=True)
        except (OSError, IOError):
            pass

        self._sequence = 0
        self._committed_sequence = 0
        self._open_wal()
