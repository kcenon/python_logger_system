"""
Log level enumeration

Equivalent to C++ logger_types.h
"""

from enum import IntEnum
from typing import Dict


class LogLevel(IntEnum):
    """
    Log level enumeration.

    Equivalent to C++ log_level enum.
    Values are compatible with Python's logging module.
    """

    TRACE = 5       # Most verbose, detailed tracing
    DEBUG = 10      # Debug information
    INFO = 20       # Informational messages
    WARN = 30       # Warning messages
    ERROR = 40      # Error messages
    CRITICAL = 50   # Critical errors
    OFF = 100       # Logging disabled

    def __str__(self) -> str:
        """String representation of log level."""
        return self.name

    @classmethod
    def from_string(cls, level_str: str) -> "LogLevel":
        """
        Convert string to LogLevel.

        Args:
            level_str: Level name (case-insensitive)

        Returns:
            LogLevel enum value

        Raises:
            ValueError: If level_str is not valid
        """
        level_str = level_str.upper()
        if hasattr(cls, level_str):
            return cls[level_str]
        raise ValueError(f"Invalid log level: {level_str}")

    @property
    def color_code(self) -> str:
        """
        Get ANSI color code for this level.

        Returns:
            ANSI escape sequence
        """
        colors = {
            LogLevel.TRACE: "\033[37m",     # White
            LogLevel.DEBUG: "\033[36m",     # Cyan
            LogLevel.INFO: "\033[32m",      # Green
            LogLevel.WARN: "\033[33m",      # Yellow
            LogLevel.ERROR: "\033[31m",     # Red
            LogLevel.CRITICAL: "\033[35m",  # Magenta
        }
        return colors.get(self, "\033[0m")

    @property
    def reset_code(self) -> str:
        """ANSI reset code."""
        return "\033[0m"


# Mapping from log level to names
LEVEL_NAMES: Dict[LogLevel, str] = {
    LogLevel.TRACE: "TRACE",
    LogLevel.DEBUG: "DEBUG",
    LogLevel.INFO: "INFO",
    LogLevel.WARN: "WARN",
    LogLevel.ERROR: "ERROR",
    LogLevel.CRITICAL: "CRITICAL",
    LogLevel.OFF: "OFF",
}

# Reverse mapping
LEVEL_FROM_NAME: Dict[str, LogLevel] = {v: k for k, v in LEVEL_NAMES.items()}
