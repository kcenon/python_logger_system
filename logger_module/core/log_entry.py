"""
Log entry data structure

Equivalent to C++ log_entry.h
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import threading

from logger_module.core.log_level import LogLevel


@dataclass
class LogEntry:
    """
    Log entry data structure.

    Equivalent to C++ log_entry struct.
    Contains all information about a single log message.
    """

    level: LogLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    thread_id: int = field(default_factory=threading.get_ident)
    thread_name: str = field(default_factory=lambda: threading.current_thread().name)
    logger_name: str = ""
    file_name: str = ""
    line_number: int = 0
    function_name: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate log entry after initialization."""
        if not isinstance(self.level, LogLevel):
            raise TypeError("level must be LogLevel enum")
        if not isinstance(self.message, str):
            self.message = str(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert log entry to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "level": self.level.name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
            "logger_name": self.logger_name,
            "file_name": self.file_name,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """
        Create log entry from dictionary.

        Args:
            data: Dictionary with log entry data

        Returns:
            New LogEntry instance
        """
        return cls(
            level=LogLevel[data["level"]],
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            thread_id=data.get("thread_id", 0),
            thread_name=data.get("thread_name", ""),
            logger_name=data.get("logger_name", ""),
            file_name=data.get("file_name", ""),
            line_number=data.get("line_number", 0),
            function_name=data.get("function_name", ""),
            extra=data.get("extra", {}),
        )

    def __str__(self) -> str:
        """String representation."""
        return (
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] "
            f"[{self.level.name:8}] "
            f"[{self.thread_name}] "
            f"{self.message}"
        )
