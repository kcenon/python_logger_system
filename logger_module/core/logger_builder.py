"""Logger builder pattern"""

from typing import Optional, Set, TYPE_CHECKING
from pathlib import Path

from logger_module.core.logger import Logger
from logger_module.core.logger_config import LoggerConfig
from logger_module.core.log_level import LogLevel
from logger_module.writers.console_writer import ConsoleWriter
from logger_module.writers.file_writer import FileWriter
from logger_module.writers.rotating_file_writer import RotatingFileWriter

if TYPE_CHECKING:
    from logger_module.security.encryption_config import EncryptionConfig


class LoggerBuilder:
    """Builder pattern for logger construction."""

    def __init__(self):
        self._config = LoggerConfig()
        self._console_enabled = False
        self._file_path: Optional[Path] = None
        self._rotating_file = False
        self._custom_writers = []
        self._custom_filters = []
        self._encryption_config: Optional["EncryptionConfig"] = None
        self._critical_writer_enabled = False
        self._critical_force_flush_levels: Optional[Set[LogLevel]] = None
        self._critical_sync_on_critical = True
        self._wal_path: Optional[str] = None

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

    def with_encryption(
        self,
        config: "EncryptionConfig",
    ) -> "LoggerBuilder":
        """
        Enable encryption for file writers.

        When enabled, file output will be encrypted using the specified
        configuration. Console output is not encrypted.

        Args:
            config: Encryption configuration with key and algorithm

        Returns:
            Self for method chaining

        Example:
            from logger_module.security import EncryptionConfig, generate_key

            key = generate_key()
            config = EncryptionConfig(key=key)

            logger = (LoggerBuilder()
                .with_file("secure.log.enc")
                .with_encryption(config)
                .build())
        """
        self._encryption_config = config
        return self

    def add_writer(self, writer) -> "LoggerBuilder":
        """
        Add a custom writer.

        Args:
            writer: Writer instance

        Returns:
            Self for method chaining
        """
        self._custom_writers.append(writer)
        return self

    def with_critical_writer(
        self,
        enabled: bool = True,
        force_flush_levels: Optional[Set[LogLevel]] = None,
        sync_on_critical: bool = True,
        wal_path: Optional[str] = None
    ) -> "LoggerBuilder":
        """
        Enable CriticalWriter for crash-safe file logging.

        When enabled, file writers are wrapped with CriticalWriter
        to ensure ERROR and CRITICAL logs are never lost.

        Args:
            enabled: Whether to enable critical writer
            force_flush_levels: Log levels that trigger immediate flush
                               (default: ERROR, CRITICAL)
            sync_on_critical: Force OS disk sync for critical logs
            wal_path: Optional WAL path for crash recovery support

        Returns:
            Self for method chaining

        Example:
            logger = (LoggerBuilder()
                .with_file("app.log")
                .with_critical_writer(
                    force_flush_levels={LogLevel.ERROR, LogLevel.CRITICAL},
                    wal_path="/tmp/app.wal"
                )
                .build())
        """
        self._critical_writer_enabled = enabled
        self._critical_force_flush_levels = force_flush_levels
        self._critical_sync_on_critical = sync_on_critical
        self._wal_path = wal_path
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

            # Wrap with encryption if configured
            if self._encryption_config:
                from logger_module.security.encrypted_writer import EncryptedWriter
                writer = EncryptedWriter(writer, self._encryption_config)

            # Wrap with critical writer if configured
            if self._critical_writer_enabled:
                writer = self._wrap_with_critical_writer(writer)

            logger.add_writer(writer)

        # Add custom writers
        for writer in self._custom_writers:
            logger.add_writer(writer)

        # Add custom filters
        for log_filter in self._custom_filters:
            logger.add_filter(log_filter)

        return logger

    def _wrap_with_critical_writer(self, writer):
        """Wrap a writer with CriticalWriter or WALCriticalWriter."""
        if self._wal_path:
            from logger_module.safety.wal_critical_writer import WALCriticalWriter
            return WALCriticalWriter(
                writer,
                wal_path=self._wal_path,
                force_flush_levels=self._critical_force_flush_levels,
                sync_on_critical=self._critical_sync_on_critical
            )
        else:
            from logger_module.safety.critical_writer import CriticalWriter
            return CriticalWriter(
                writer,
                force_flush_levels=self._critical_force_flush_levels,
                sync_on_critical=self._critical_sync_on_critical
            )
