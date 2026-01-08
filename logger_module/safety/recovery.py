"""
Log recovery utilities

Provides utilities to recover logs from memory-mapped buffers
and emergency log files after application crashes.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from logger_module.safety.mmap_buffer import MMapLogBuffer


def recover_from_mmap(path: str) -> List[str]:
    """
    Recover log entries from a memory-mapped buffer file.

    Args:
        path: Path to the mmap buffer file

    Returns:
        List of recovered log entries

    Raises:
        FileNotFoundError: If buffer file doesn't exist
        ValueError: If buffer file is invalid
    """
    with MMapLogBuffer(path, create=False) as buffer:
        entries = buffer.recover()
        buffer.mark_recovered()
        return entries


def recover_from_emergency_logs(
    directory: Optional[str] = None,
    pattern: str = "emergency_log_*.log"
) -> Dict[str, List[str]]:
    """
    Recover entries from emergency log files.

    Args:
        directory: Directory to search (uses temp dir if None)
        pattern: Glob pattern for emergency log files

    Returns:
        Dictionary mapping file paths to their log entries
    """
    import tempfile

    if directory is None:
        directory = tempfile.gettempdir()

    search_path = Path(directory) / pattern
    results = {}

    for filepath in glob.glob(str(search_path)):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                entries = [line.strip() for line in f if line.strip()]
                if entries:
                    results[filepath] = entries
        except Exception:
            pass

    return results


def find_crash_logs(
    base_directory: str,
    mmap_pattern: str = "*.mmap",
    emergency_pattern: str = "emergency_log_*.log"
) -> Dict[str, dict]:
    """
    Find all potential crash log files.

    Args:
        base_directory: Base directory to search
        mmap_pattern: Pattern for mmap files
        emergency_pattern: Pattern for emergency log files

    Returns:
        Dictionary with file info and recovery status
    """
    results = {}
    base_path = Path(base_directory)

    # Find mmap files
    for mmap_file in base_path.glob(mmap_pattern):
        try:
            with MMapLogBuffer(str(mmap_file), create=False) as buffer:
                stats = buffer.get_stats()
                results[str(mmap_file)] = {
                    'type': 'mmap',
                    'needs_recovery': buffer.needs_recovery(),
                    'entry_count': stats.get('entry_count', 0),
                    'size': stats.get('size', 0),
                    'modified': datetime.fromtimestamp(
                        mmap_file.stat().st_mtime
                    ).isoformat()
                }
        except Exception as e:
            results[str(mmap_file)] = {
                'type': 'mmap',
                'error': str(e)
            }

    # Find emergency log files
    for emergency_file in base_path.glob(emergency_pattern):
        try:
            stat = emergency_file.stat()
            with open(emergency_file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)

            results[str(emergency_file)] = {
                'type': 'emergency',
                'entry_count': line_count,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        except Exception as e:
            results[str(emergency_file)] = {
                'type': 'emergency',
                'error': str(e)
            }

    return results


def recover_all(
    base_directory: str,
    output_file: Optional[str] = None,
    cleanup: bool = False
) -> Dict[str, int]:
    """
    Recover all crash logs from a directory.

    Args:
        base_directory: Directory containing crash logs
        output_file: Optional file to write recovered logs
        cleanup: Whether to remove processed files after recovery

    Returns:
        Dictionary with recovery statistics
    """
    stats = {
        'mmap_files': 0,
        'emergency_files': 0,
        'total_entries': 0,
        'errors': 0
    }

    all_entries = []
    base_path = Path(base_directory)

    # Recover from mmap files
    for mmap_file in base_path.glob("*.mmap"):
        try:
            entries = recover_from_mmap(str(mmap_file))
            all_entries.extend(entries)
            stats['mmap_files'] += 1
            stats['total_entries'] += len(entries)

            if cleanup:
                mmap_file.unlink()
        except Exception:
            stats['errors'] += 1

    # Recover from emergency logs
    emergency_results = recover_from_emergency_logs(str(base_path))
    for filepath, entries in emergency_results.items():
        all_entries.extend(entries)
        stats['emergency_files'] += 1
        stats['total_entries'] += len(entries)

        if cleanup:
            try:
                Path(filepath).unlink()
            except Exception:
                stats['errors'] += 1

    # Write to output file if specified
    if output_file and all_entries:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in all_entries:
                f.write(entry + '\n')

    return stats


def cleanup_old_crash_logs(
    directory: str,
    max_age_hours: int = 24,
    dry_run: bool = False
) -> List[str]:
    """
    Clean up old crash log files.

    Args:
        directory: Directory to clean
        max_age_hours: Maximum age of files to keep
        dry_run: If True, only list files that would be deleted

    Returns:
        List of deleted (or would-be deleted) file paths
    """
    import time

    deleted = []
    base_path = Path(directory)
    cutoff_time = time.time() - (max_age_hours * 3600)

    patterns = ["*.mmap", "emergency_log_*.log"]

    for pattern in patterns:
        for filepath in base_path.glob(pattern):
            try:
                if filepath.stat().st_mtime < cutoff_time:
                    deleted.append(str(filepath))
                    if not dry_run:
                        filepath.unlink()
            except Exception:
                pass

    return deleted
