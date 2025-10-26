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
        
        return logger
