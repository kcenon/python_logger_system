"""Logger builder pattern"""

from typing import Optional
from pathlib import Path

from logger_module.core.logger import Logger
from logger_module.core.logger_config import LoggerConfig
from logger_module.core.log_level import LogLevel
from logger_module.writers.console_writer import ConsoleWriter
from logger_module.writers.file_writer import FileWriter
from logger_module.writers.rotating_file_writer import RotatingFileWriter


class LoggerBuilder:
    """Builder pattern for logger construction."""

    def __init__(self):
        self._config = LoggerConfig()
        self._console_enabled = False
        self._file_path: Optional[Path] = None
        self._rotating_file = False
        self._custom_writers = []
        self._custom_filters = []

    def with_name(self, name: str) -> "LoggerBuilder":
        """Set logger name."""
        self._config.name = name
        return self

    def with_level(self, level: LogLevel) -> "LoggerBuilder":
        """Set minimum log level."""
        self._config.min_level = level
        return self

    def with_async(self, enabled: bool = True) -> "LoggerBuilder":
        """Enable/disable async mode."""
        self._config.async_mode = enabled
        return self

    def with_console(self, colored: bool = True) -> "LoggerBuilder":
        """Enable console output."""
        self._console_enabled = True
        self._config.colored_output = colored
        return self

    def with_file(self, filepath: str, rotating: bool = False) -> "LoggerBuilder":
        """Enable file output."""
        self._file_path = Path(filepath)
        self._rotating_file = rotating
        return self

    def with_queue_size(self, size: int) -> "LoggerBuilder":
        """Set async queue size."""
        self._config.queue_size = size
        return self

    def with_batch_size(self, size: int) -> "LoggerBuilder":
        """Set batch size."""
        self._config.batch_size = size
        return self

    def with_filter(self, log_filter) -> "LoggerBuilder":
        """
        Add a log filter.

        Args:
            log_filter: Filter instance (BaseFilter subclass)

        Returns:
            Self for method chaining

        Example:
            from logger_module.filters import LevelFilter, PatternFilter

            logger = (LoggerBuilder()
                .with_filter(LevelFilter(min_level=LogLevel.WARN))
                .with_filter(PatternFilter(r"error", exclude=False))
                .build())
        """
        self._custom_filters.append(log_filter)
        return self

    def with_crash_safety(
        self,
        enabled: bool = True,
        mmap_path: Optional[str] = None,
        mmap_size: int = 1024 * 1024
    ) -> "LoggerBuilder":
        """
        Enable crash-safe logging.

        When enabled, logs are buffered for emergency recovery on crashes
        and optionally stored in a memory-mapped file for durability.

        Args:
            enabled: Whether to enable crash safety
            mmap_path: Path for memory-mapped buffer (optional)
            mmap_size: Size of memory-mapped buffer in bytes

        Returns:
            Self for method chaining

        Example:
            logger = (LoggerBuilder()
                .with_crash_safety(True, mmap_path="/tmp/app.mmap")
                .build())
        """
        self._config.crash_safe = enabled
        if mmap_path:
            self._config.mmap_buffer_path = mmap_path
        self._config.mmap_buffer_size = mmap_size
        return self

    def build(self) -> Logger:
        """Build and return configured logger."""
        logger = Logger(self._config)

        # Add console writer
        if self._console_enabled:
            logger.add_writer(ConsoleWriter(colored=self._config.colored_output))

        # Add file writer
        if self._file_path:
            if self._rotating_file:
                writer = RotatingFileWriter(
                    str(self._file_path),
                    max_bytes=self._config.max_file_size,
                    backup_count=self._config.max_backup_files
                )
            else:
                writer = FileWriter(str(self._file_path))
            logger.add_writer(writer)

        # Add custom writers
        for writer in self._custom_writers:
            logger.add_writer(writer)

        # Add custom filters
        for log_filter in self._custom_filters:
            logger.add_filter(log_filter)

        return logger
