"""Logger builder pattern"""

from typing import Any, Callable, Optional, Set, TYPE_CHECKING
from pathlib import Path

from logger_module.core.logger import Logger
from logger_module.core.logger_config import LoggerConfig
from logger_module.core.log_level import LogLevel
from logger_module.writers.console_writer import ConsoleWriter
from logger_module.writers.file_writer import FileWriter
from logger_module.writers.rotating_file_writer import RotatingFileWriter
from logger_module.writers.network_writer import TCPWriter, UDPWriter
from logger_module.writers.batch_writer import BatchWriter, AdaptiveBatchWriter

if TYPE_CHECKING:
    from logger_module.security.encryption_config import EncryptionConfig
    from logger_module.routing.log_router import LogRouter
    from logger_module.monitoring.monitor import Monitor


class LoggerBuilder:
    """Builder pattern for logger construction."""

    def __init__(self):
        self._config = LoggerConfig()
        self._console_enabled = False
        self._console_name: Optional[str] = None
        self._file_path: Optional[Path] = None
        self._file_name: Optional[str] = None
        self._rotating_file = False
        self._custom_writers: list[tuple[Any, Optional[str]]] = []
        self._custom_filters = []
        self._encryption_config: Optional["EncryptionConfig"] = None
        self._critical_writer_enabled = False
        self._critical_force_flush_levels: Optional[Set[LogLevel]] = None
        self._critical_sync_on_critical = True
        self._wal_path: Optional[str] = None
        self._router: Optional["LogRouter"] = None
        self._route_configs: list[Callable[["LogRouter"], None]] = []
        self._monitor: Optional["Monitor"] = None
        self._metrics_enabled = False
        self._batching_enabled = False
        self._batching_max_batch_size = 100
        self._batching_flush_interval_ms = 1000
        self._batching_max_buffer_size = 10000
        self._batching_adaptive = False
        self._batching_min_batch_size = 10
        self._batching_max_batch_size_limit = 500

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

    def with_console(
        self,
        colored: bool = True,
        name: Optional[str] = None
    ) -> "LoggerBuilder":
        """
        Enable console output.

        Args:
            colored: Enable colored output
            name: Optional name for routing

        Returns:
            Self for method chaining
        """
        self._console_enabled = True
        self._console_name = name
        self._config.colored_output = colored
        return self

    def with_file(
        self,
        filepath: str,
        rotating: bool = False,
        name: Optional[str] = None
    ) -> "LoggerBuilder":
        """
        Enable file output.

        Args:
            filepath: Path to log file
            rotating: Enable log rotation
            name: Optional name for routing

        Returns:
            Self for method chaining
        """
        self._file_path = Path(filepath)
        self._file_name = name
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

    def add_writer(
        self,
        writer: Any,
        name: Optional[str] = None
    ) -> "LoggerBuilder":
        """
        Add a custom writer.

        Args:
            writer: Writer instance
            name: Optional name for routing

        Returns:
            Self for method chaining
        """
        self._custom_writers.append((writer, name))
        return self

    def with_tcp(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
        reconnect_attempts: int = 3,
        use_ssl: bool = False,
    ) -> "LoggerBuilder":
        """
        Add TCP network writer for remote logging.

        TCP provides reliable, ordered delivery with automatic
        reconnection on connection failures.

        Args:
            host: Remote host address
            port: Remote port number
            timeout: Socket timeout in seconds
            reconnect_attempts: Maximum reconnection attempts
            use_ssl: Enable SSL/TLS encryption

        Returns:
            Self for method chaining

        Example:
            logger = (LoggerBuilder()
                .with_tcp("log-server.example.com", 5140)
                .build())
        """
        writer = TCPWriter(
            host=host,
            port=port,
            timeout=timeout,
            reconnect_attempts=reconnect_attempts,
            use_ssl=use_ssl,
        )
        self._custom_writers.append((writer, None))
        return self

    def with_udp(
        self,
        host: str,
        port: int,
        timeout: float = 5.0,
    ) -> "LoggerBuilder":
        """
        Add UDP network writer for high-throughput logging.

        UDP provides fire-and-forget delivery with low latency.
        Best for high-volume logging where some loss is acceptable.

        Args:
            host: Remote host address
            port: Remote port number
            timeout: Socket timeout in seconds

        Returns:
            Self for method chaining

        Example:
            logger = (LoggerBuilder()
                .with_udp("syslog.example.com", 514)
                .build())
        """
        writer = UDPWriter(
            host=host,
            port=port,
            timeout=timeout,
        )
        self._custom_writers.append((writer, None))
        return self

    def with_routing(
        self,
        router: Optional["LogRouter"] = None
    ) -> "LoggerBuilder":
        """
        Enable log routing.

        When routing is enabled, log entries are directed to specific
        writers based on configurable rules instead of being sent to
        all writers.

        Args:
            router: Optional pre-configured LogRouter instance

        Returns:
            Self for method chaining

        Example:
            from logger_module.routing import LogRouter

            router = LogRouter()
            router.set_default_writers("console")

            logger = (LoggerBuilder()
                .with_console(name="console")
                .with_file("errors.log", name="errors")
                .with_routing(router)
                .build())

            # Configure routes after build
            logger.get_router().route() \\
                .when_level(LogLevel.ERROR) \\
                .route_to("errors", "console") \\
                .build()
        """
        if router is None:
            from logger_module.routing.log_router import LogRouter
            router = LogRouter()
        self._router = router
        return self

    def with_route(
        self,
        config_func: Callable[["LogRouter"], None]
    ) -> "LoggerBuilder":
        """
        Add a route configuration function.

        The function will be called with the router during build.

        Args:
            config_func: Function that configures routes on the router

        Returns:
            Self for method chaining

        Example:
            def configure_routes(router):
                router.route() \\
                    .when_level(LogLevel.ERROR) \\
                    .route_to("errors") \\
                    .build()
                router.set_default_writers("console")

            logger = (LoggerBuilder()
                .with_console(name="console")
                .with_file("errors.log", name="errors")
                .with_route(configure_routes)
                .build())
        """
        self._route_configs.append(config_func)
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

    def with_monitoring(
        self,
        monitor: Optional["Monitor"] = None,
        metrics_enabled: bool = True
    ) -> "LoggerBuilder":
        """
        Enable monitoring and metrics collection.

        Enables detailed metrics collection and optionally exports
        metrics to an external monitoring system.

        Args:
            monitor: Optional Monitor instance for exporting metrics
                    (Prometheus, StatsD, etc.)
            metrics_enabled: Whether to enable detailed metrics collection

        Returns:
            Self for method chaining

        Example:
            from logger_module.monitoring import PrometheusMonitor

            monitor = PrometheusMonitor(prefix="myapp_logger")

            logger = (LoggerBuilder()
                .with_console()
                .with_monitoring(monitor, metrics_enabled=True)
                .build())

            # Get detailed metrics
            metrics = logger.get_detailed_metrics()
            print(f"Total messages: {metrics.total_messages}")
        """
        self._monitor = monitor
        self._metrics_enabled = metrics_enabled
        return self

    def with_metrics(self, enabled: bool = True) -> "LoggerBuilder":
        """
        Enable detailed metrics collection.

        Enables comprehensive metrics tracking without requiring
        an external monitoring backend.

        Args:
            enabled: Whether to enable metrics collection

        Returns:
            Self for method chaining

        Example:
            logger = (LoggerBuilder()
                .with_console()
                .with_metrics(True)
                .build())

            # Log some messages
            logger.info("Test message")

            # Check metrics
            metrics = logger.get_detailed_metrics()
            print(f"Messages per second: {metrics.messages_per_second}")
        """
        self._metrics_enabled = enabled
        return self

    def with_batching(
        self,
        max_batch_size: int = 100,
        flush_interval_ms: int = 1000,
        max_buffer_size: int = 10000,
        adaptive: bool = False,
        min_batch_size: int = 10,
        max_batch_size_limit: int = 500,
    ) -> "LoggerBuilder":
        """
        Enable batch writing for improved I/O performance.

        When enabled, all writers are wrapped with BatchWriter (or
        AdaptiveBatchWriter if adaptive=True) to buffer log entries
        and write them in batches, reducing syscall overhead.

        Args:
            max_batch_size: Maximum entries before triggering batch flush
            flush_interval_ms: Time interval for periodic flush in milliseconds
            max_buffer_size: Maximum buffer capacity before dropping entries
            adaptive: Use AdaptiveBatchWriter for dynamic batch sizing
            min_batch_size: Minimum batch size for adaptive mode
            max_batch_size_limit: Maximum batch size limit for adaptive mode

        Returns:
            Self for method chaining

        Example:
            # Basic batching
            logger = (LoggerBuilder()
                .with_file("app.log")
                .with_batching(max_batch_size=100, flush_interval_ms=1000)
                .build())

            # Adaptive batching for variable throughput
            logger = (LoggerBuilder()
                .with_file("app.log")
                .with_batching(adaptive=True, min_batch_size=10, max_batch_size_limit=500)
                .build())
        """
        self._batching_enabled = True
        self._batching_max_batch_size = max_batch_size
        self._batching_flush_interval_ms = flush_interval_ms
        self._batching_max_buffer_size = max_buffer_size
        self._batching_adaptive = adaptive
        self._batching_min_batch_size = min_batch_size
        self._batching_max_batch_size_limit = max_batch_size_limit
        return self

    def build(self) -> Logger:
        """Build and return configured logger."""
        logger = Logger(self._config)

        # Set up router if routing is enabled
        if self._router is not None or self._route_configs:
            if self._router is None:
                from logger_module.routing.log_router import LogRouter
                self._router = LogRouter()
            logger.set_router(self._router)

        # Add console writer
        if self._console_enabled:
            logger.add_writer(
                ConsoleWriter(colored=self._config.colored_output),
                name=self._console_name
            )

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

            # Wrap with batch writer if configured
            if self._batching_enabled:
                writer = self._wrap_with_batch_writer(writer)

            logger.add_writer(writer, name=self._file_name)

        # Add custom writers
        for writer, name in self._custom_writers:
            # Wrap with batch writer if configured
            if self._batching_enabled:
                writer = self._wrap_with_batch_writer(writer)
            logger.add_writer(writer, name=name)

        # Add custom filters
        for log_filter in self._custom_filters:
            logger.add_filter(log_filter)

        # Apply route configurations
        if self._route_configs and self._router:
            for config_func in self._route_configs:
                config_func(self._router)

        # Enable monitoring if configured
        if self._metrics_enabled:
            logger.enable_metrics(True)
        if self._monitor:
            logger.set_monitor(self._monitor)

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

    def _wrap_with_batch_writer(self, writer):
        """Wrap a writer with BatchWriter or AdaptiveBatchWriter."""
        from datetime import timedelta

        flush_interval = timedelta(milliseconds=self._batching_flush_interval_ms)

        if self._batching_adaptive:
            return AdaptiveBatchWriter(
                inner_writer=writer,
                min_batch_size=self._batching_min_batch_size,
                max_batch_size=self._batching_max_batch_size_limit,
                initial_batch_size=self._batching_max_batch_size,
                flush_interval=flush_interval,
                max_buffer_size=self._batching_max_buffer_size,
            )
        else:
            return BatchWriter(
                inner_writer=writer,
                max_batch_size=self._batching_max_batch_size,
                flush_interval=flush_interval,
                max_buffer_size=self._batching_max_buffer_size,
            )
