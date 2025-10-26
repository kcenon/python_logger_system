"""
Logger configuration management

Equivalent to C++ logger_config.h
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from logger_module.core.log_level import LogLevel


@dataclass
class LoggerConfig:
    """
    Logger configuration.

    Equivalent to C++ logger_config class.
    """

    # Basic settings
    name: str = "logger"
    min_level: LogLevel = LogLevel.INFO
    async_mode: bool = True

    # Queue settings (for async mode)
    queue_size: int = 10000
    batch_size: int = 100
    flush_interval_ms: int = 100

    # File settings
    log_directory: Optional[Path] = None
    log_filename: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10 MB
    max_backup_files: int = 5

    # Console settings
    console_output: bool = True
    colored_output: bool = True

    # Performance settings
    enable_metrics: bool = False
    thread_safe: bool = True

    # Format settings
    timestamp_format: str = "%Y-%m-%d %H:%M:%S.%f"
    message_format: str = "[{timestamp}] [{level:8}] [{thread}] {message}"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.queue_size <= 0:
            raise ValueError("queue_size must be positive")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.batch_size > self.queue_size:
            raise ValueError("batch_size cannot exceed queue_size")
        if self.flush_interval_ms < 0:
            raise ValueError("flush_interval_ms cannot be negative")
        if self.max_file_size <= 0:
            raise ValueError("max_file_size must be positive")
        if self.max_backup_files < 0:
            raise ValueError("max_backup_files cannot be negative")

        # Convert log_directory to Path if it's a string
        if isinstance(self.log_directory, str):
            self.log_directory = Path(self.log_directory)

    @classmethod
    def default(cls) -> "LoggerConfig":
        """Create default configuration."""
        return cls()

    @classmethod
    def debug_config(cls) -> "LoggerConfig":
        """Create configuration for debugging."""
        return cls(
            min_level=LogLevel.DEBUG,
            console_output=True,
            colored_output=True,
            async_mode=False,  # Synchronous for debugging
        )

    @classmethod
    def performance_config(cls) -> "LoggerConfig":
        """Create configuration optimized for performance."""
        return cls(
            min_level=LogLevel.INFO,
            async_mode=True,
            queue_size=50000,
            batch_size=500,
            flush_interval_ms=50,
            enable_metrics=True,
        )

    @classmethod
    def production_config(cls) -> "LoggerConfig":
        """Create configuration for production."""
        return cls(
            min_level=LogLevel.WARN,
            console_output=False,
            async_mode=True,
            queue_size=20000,
            batch_size=200,
            enable_metrics=True,
        )
