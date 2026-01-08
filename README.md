# Python Logger System

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)

> **Language:** **English** | [한국어](README_KO.md)

## Overview

Python Logger System is a high-performance asynchronous logging framework for Python, providing the same functionality as the C++ [logger_system](https://github.com/kcenon/logger_system). Designed for multithreaded applications requiring efficient, non-blocking logging with minimal overhead.

**Key Features:**
- **Asynchronous Processing**: Non-blocking log operations with queue-based batching
- **Multiple Writers**: Console, file, rotating file, network (TCP/UDP), batch writers
- **Batch Writing**: High-performance batched I/O with adaptive sizing
- **Log Routing**: Direct log entries to specific writers based on level, pattern, or custom rules
- **Monitoring & Metrics**: Comprehensive metrics collection with Prometheus/StatsD integration
- **Health Checks**: Kubernetes-ready liveness and readiness probes
- **Thread-Safe**: Concurrent logging from multiple threads
- **Builder Pattern**: Fluent API for logger construction
- **Colored Output**: ANSI-colored console output
- **Crash-Safe Logging**: Signal handlers and memory-mapped buffers for durability
- **Encrypted Logging**: AES-256-GCM, AES-256-CBC, ChaCha20-Poly1305 encryption
- **Zero External Dependencies**: Uses only Python standard library (encryption requires `cryptography`)

## Quick Start

### Installation

```bash
pip install -e /Users/dongcheolshin/Sources/python_logger_system
```

### Basic Usage

```python
from logger_module import LoggerBuilder, LogLevel

# Create logger
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_level(LogLevel.INFO)
    .with_console(colored=True)
    .with_file("app.log", rotating=True)
    .build())

# Log messages
logger.info("Application started")
logger.warn("Warning message")
logger.error("Error occurred")

# Cleanup
logger.shutdown()
```

## Features

### Log Levels

- `TRACE` (5) - Most verbose
- `DEBUG` (10) - Debug information
- `INFO` (20) - Informational
- `WARN` (30) - Warnings
- `ERROR` (40) - Errors
- `CRITICAL` (50) - Critical errors
- `OFF` (100) - Disabled

### Writers

**ConsoleWriter**: Output to console with optional ANSI colors
```python
logger.add_writer(ConsoleWriter(colored=True))
```

**FileWriter**: Basic file output
```python
logger.add_writer(FileWriter("app.log"))
```

**RotatingFileWriter**: Size-based log rotation
```python
logger.add_writer(RotatingFileWriter(
    "app.log",
    max_bytes=10*1024*1024,  # 10 MB
    backup_count=5
))
```

**TCPWriter**: Reliable network logging with auto-reconnect
```python
from logger_module.writers import TCPWriter

# Via builder
logger = (LoggerBuilder()
    .with_tcp("log-server.example.com", 5140)
    .build())

# Or manually
tcp_writer = TCPWriter(
    host="log-server.example.com",
    port=5140,
    timeout=5.0,
    reconnect_attempts=3,
    use_ssl=True  # Enable TLS encryption
)
logger.add_writer(tcp_writer)
```

**UDPWriter**: High-throughput fire-and-forget logging
```python
from logger_module.writers import UDPWriter

# Via builder
logger = (LoggerBuilder()
    .with_udp("syslog.example.com", 514)
    .build())

# Or manually
udp_writer = UDPWriter(
    host="syslog.example.com",
    port=514
)
logger.add_writer(udp_writer)
```

**BatchWriter**: Buffered I/O for improved performance
```python
from logger_module.writers import BatchWriter, FileWriter

# Via builder (recommended)
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_file("app.log")
    .with_batching(
        max_batch_size=100,      # Flush after 100 entries
        flush_interval_ms=1000   # Or every 1 second
    )
    .build())

# Manual batching
file_writer = FileWriter("app.log")
batch_writer = BatchWriter(
    file_writer,
    max_batch_size=100,
    flush_interval=timedelta(seconds=1),
    max_buffer_size=10000  # Drop entries if buffer exceeds this
)
logger.add_writer(batch_writer)
```

**AdaptiveBatchWriter**: Dynamic batch sizing based on throughput
```python
from logger_module.writers import AdaptiveBatchWriter, FileWriter

# Via builder (recommended)
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_file("app.log")
    .with_batching(
        adaptive=True,
        min_batch_size=10,
        max_batch_size_limit=500
    )
    .build())

# Manual adaptive batching
file_writer = FileWriter("app.log")
adaptive_writer = AdaptiveBatchWriter(
    file_writer,
    min_batch_size=10,
    max_batch_size=500,
    initial_batch_size=100
)

# Monitor batch statistics
stats = adaptive_writer.get_adaptive_stats()
print(f"Current batch size: {stats['current_batch_size']}")
print(f"Write rate: {stats['current_rate']} entries/sec")
```

### Log Routing

Direct log entries to specific writers based on configurable rules:

```python
from logger_module import LoggerBuilder, LogLevel
from logger_module.routing import LogRouter

# Create logger with named writers
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_console(name="console")
    .with_file("errors.log", name="errors")
    .with_file("security.log", name="security")
    .with_routing()
    .build())

# Configure routing rules
router = logger.get_router()

# Route ERROR and CRITICAL to dedicated error file
router.route() \
    .when_level(LogLevel.ERROR, LogLevel.CRITICAL) \
    .route_to("errors", "console") \
    .build()

# Route security-related logs (stop further processing)
router.route() \
    .when_matches(r"(login|logout|permission|access)") \
    .route_to("security") \
    .stop() \
    .build()

# Set default for unmatched entries
router.set_default_writers("console")

# Now logs are routed automatically
logger.error("Database error")           # -> errors, console
logger.info("User login successful")     # -> security (stops)
logger.info("Processing request")        # -> console (default)

logger.shutdown()
```

**Available routing filters:**
- `when_level(*levels)` - Match specific log levels
- `when_level_at_least(min_level)` - Match levels >= minimum
- `when_level_between(min, max)` - Match level range
- `when_matches(pattern)` - Match message regex pattern
- `when_logger_name(*names)` - Match logger names
- `when_has_extra(key)` - Match entries with extra field
- `when_extra_equals(key, value)` - Match extra field value
- `when(predicate)` - Custom predicate function
- `stop()` - Stop propagation on match

### Configuration

```python
from logger_module import LoggerConfig, LogLevel

# Custom configuration
config = LoggerConfig(
    name="myapp",
    min_level=LogLevel.DEBUG,
    async_mode=True,
    queue_size=10000,
    batch_size=100,
    console_output=True,
    colored_output=True
)

logger = Logger(config)
```

### Builder Pattern

```python
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_level(LogLevel.DEBUG)
    .with_console(colored=True)
    .with_file("logs/app.log", rotating=True)
    .with_async(True)
    .with_queue_size(20000)
    .with_batch_size(200)
    .build())
```

### Crash-Safe Logging

Enable crash-safe mode for durability:

```python
from logger_module import LoggerBuilder

# Enable crash safety with memory-mapped buffer
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_crash_safety(
        enabled=True,
        mmap_path="/tmp/myapp.mmap",
        mmap_size=1024*1024  # 1 MB
    )
    .build())

logger.info("This will survive crashes")
```

Recover logs after a crash:

```python
from logger_module.safety import recover_from_mmap, recover_all

# Recover from specific mmap file
entries = recover_from_mmap("/tmp/myapp.mmap")
for entry in entries:
    print(entry)

# Recover all crash logs from directory
stats = recover_all("/tmp", output_file="recovered.log", cleanup=True)
print(f"Recovered {stats['total_entries']} entries")
```

### Critical Writer

Ensure critical logs (ERROR, CRITICAL) are never lost, even during crashes:

```python
from logger_module import LoggerBuilder, LogLevel
from logger_module.safety import CriticalWriter
from logger_module.writers import FileWriter

# Using LoggerBuilder (recommended)
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_file("app.log")
    .with_critical_writer(
        enabled=True,
        force_flush_levels={LogLevel.ERROR, LogLevel.CRITICAL},
        sync_on_critical=True
    )
    .build())

logger.error("This is immediately flushed and synced to disk")
logger.shutdown()
```

With Write-Ahead Logging (WAL) for crash recovery:

```python
from logger_module import LoggerBuilder

# Enable WAL for crash recovery
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_file("app.log")
    .with_critical_writer(
        enabled=True,
        wal_path="/tmp/app.wal"
    )
    .build())

logger.critical("Critical error - recoverable from WAL on crash")
logger.shutdown()
```

Recover uncommitted entries after crash:

```python
from logger_module.safety import WALCriticalWriter
from logger_module.writers import FileWriter

writer = FileWriter("app.log")
wal_writer = WALCriticalWriter(writer, wal_path="/tmp/app.wal")

# Recover any uncommitted entries
recovered = wal_writer.recover()
for entry in recovered:
    print(f"Recovered: {entry.message}")

wal_writer.close()
```

### Encrypted Logging

Encrypt log files for compliance (GDPR, HIPAA, PCI DSS):

```bash
# Install cryptography dependency
pip install python-logger-system[security]
```

```python
from logger_module import LoggerBuilder
from logger_module.security import (
    EncryptionConfig,
    EncryptionAlgorithm,
    generate_key,
    save_key_to_file,
    LogDecryptor,
)

# Generate and save encryption key
key = generate_key()
save_key_to_file(key, "secret.key")

# Create encrypted logger
config = EncryptionConfig(
    key=key,
    algorithm=EncryptionAlgorithm.AES_256_GCM
)

logger = (LoggerBuilder()
    .with_name("secure-app")
    .with_file("secure.log.enc")
    .with_encryption(config)
    .build())

logger.info("This message is encrypted at rest")
logger.shutdown()
```

Decrypt logs for analysis:

```python
from logger_module.security import LogDecryptor, load_key_from_file

key = load_key_from_file("secret.key")
decryptor = LogDecryptor(key)

# Decrypt file
logs = decryptor.decrypt_file("secure.log.enc")
for log in logs:
    print(log)

# Or decrypt to output file
decryptor.decrypt_to_file("secure.log.enc", "decrypted.log")
```

Supported algorithms:
- **AES-256-GCM** (default): Authenticated encryption, recommended
- **AES-256-CBC**: Classic block cipher
- **ChaCha20-Poly1305**: Modern stream cipher

### Monitoring and Metrics

Enable comprehensive monitoring for observability:

```python
from logger_module import LoggerBuilder
from logger_module.monitoring import (
    InMemoryMonitor,
    HealthChecker,
    HealthStatus,
)

# Enable metrics collection
logger = (LoggerBuilder()
    .with_name("myapp")
    .with_console()
    .with_metrics(True)
    .build())

# Log messages
logger.info("Application started")
logger.error("An error occurred")

# Get detailed metrics
metrics = logger.get_detailed_metrics()
print(f"Total messages: {metrics.total_messages}")
print(f"Messages per second: {metrics.messages_per_second}")
print(f"Avg latency: {metrics.avg_write_latency_ms}ms")

logger.shutdown()
```

**With external monitoring (Prometheus):**

```bash
# Install prometheus-client
pip install prometheus-client
```

```python
from logger_module import LoggerBuilder
from logger_module.monitoring import PrometheusMonitor

# Create Prometheus monitor
monitor = PrometheusMonitor(prefix="myapp_logger")

logger = (LoggerBuilder()
    .with_name("myapp")
    .with_console()
    .with_monitoring(monitor, metrics_enabled=True)
    .build())

# Metrics are automatically exported to Prometheus
# Available metrics:
#   myapp_logger_messages_total{level="INFO"}
#   myapp_logger_queue_depth
#   myapp_logger_dropped_total
#   myapp_logger_write_latency_seconds

logger.info("This is tracked")
logger.shutdown()
```

**Health Checks (for Kubernetes/containers):**

```python
from logger_module.monitoring import (
    HealthChecker,
    LivenessChecker,
    ReadinessChecker,
)

# Comprehensive health check
health = HealthChecker(logger)
result = health.check()
print(f"Status: {result.status.value}")  # healthy/degraded/unhealthy
print(f"Issues: {result.issues}")

# Kubernetes-style probes
liveness = LivenessChecker(logger)
alive, reason = liveness.check()

readiness = ReadinessChecker(logger)
ready, reason = readiness.check()
```

**Available metrics:**
- `total_messages` - Total logged messages
- `messages_by_level` - Messages per log level
- `queue_depth` / `queue_max_depth` - Async queue metrics
- `dropped_messages` - Messages dropped due to full queue
- `messages_per_second` - Current throughput rate
- `avg_write_latency_ms` / `max_write_latency_ms` - Write latencies
- `writer_errors` / `writer_retries` - Error tracking
- `bytes_written` - Total output size

## Architecture

```
python_logger_system/
├── logger_module/
│   ├── core/
│   │   ├── logger.py           # Main logger
│   │   ├── logger_builder.py   # Builder pattern
│   │   ├── logger_config.py    # Configuration
│   │   ├── log_entry.py        # Log entry structure
│   │   └── log_level.py        # Log levels
│   ├── writers/
│   │   ├── console_writer.py   # Console output
│   │   ├── file_writer.py      # File output
│   │   ├── rotating_file_writer.py  # Rotating files
│   │   ├── network_writer.py   # TCP/UDP network logging
│   │   └── batch_writer.py     # Batched I/O for performance
│   ├── routing/
│   │   ├── log_router.py       # Main router
│   │   ├── route_builder.py    # Fluent route configuration
│   │   └── route_config.py     # Route configuration
│   ├── monitoring/
│   │   ├── metrics.py          # Metrics collection
│   │   ├── monitor.py          # Monitor interfaces
│   │   ├── prometheus_monitor.py # Prometheus/StatsD export
│   │   └── health_checker.py   # Health checks
│   ├── safety/
│   │   ├── signal_manager.py   # Signal handlers
│   │   ├── mmap_buffer.py      # Memory-mapped buffer
│   │   ├── crash_safe_mixin.py # Crash-safe mixin
│   │   ├── critical_writer.py  # Critical log protection
│   │   ├── wal_critical_writer.py # WAL-based crash recovery
│   │   └── recovery.py         # Log recovery utilities
│   └── security/
│       ├── encrypted_writer.py # Encryption writer
│       ├── encryption_config.py # Encryption configuration
│       ├── key_management.py   # Key utilities
│       └── decryptor.py        # Log decryption
├── tests/                      # Unit tests
├── examples/                   # Examples
└── docs/                       # Documentation
```

## Performance

**Async Mode** (Recommended):
- Non-blocking log operations
- Batched queue processing
- ~100K+ messages/sec

**Sync Mode** (Debugging):
- Immediate write
- Simpler debugging
- ~10K messages/sec

**Batched I/O Mode** (High-throughput):
- Reduces syscall overhead by 90-99%
- Configurable batch size and flush interval
- Adaptive mode adjusts batch size based on throughput
- Ideal for high-volume logging scenarios

| Scenario | Without Batching | With Batching |
|----------|-----------------|---------------|
| 10K logs/sec | 10K syscalls/sec | ~100 syscalls/sec |
| Disk I/O | High seek overhead | Sequential writes |
| Network | Many small packets | Fewer large packets |

## Comparison with C++ Version

| Feature | C++ logger_system | Python logger_system |
|---------|------------------|---------------------|
| **Language** | C++20 | Python 3.8+ |
| **Async** | Lock-free queue | queue.Queue |
| **Performance** | ~1M msg/sec | ~100K msg/sec |
| **Writers** | 10+ types | 7 core types |
| **Dependencies** | fmt, spdlog | None (stdlib) |
| **Use Case** | High-perf C++ | Python apps |

## Examples

### Structured Logging

```python
logger.info("User login", extra={
    "user_id": 12345,
    "ip_address": "192.168.1.1",
    "session_id": "abc-123"
})
```

### Performance Configuration

```python
config = LoggerConfig.performance_config()
logger = Logger(config)
```

### Debug Configuration

```python
config = LoggerConfig.debug_config()
logger = Logger(config)
```

## License

BSD 3-Clause License - See [LICENSE](LICENSE)

## Acknowledgments

- Based on C++ [logger_system](https://github.com/kcenon/logger_system)
- Maintainer: kcenon@naver.com

---

<p align="center">Made with ❤️ by 🍀☀🌕🌥 🌊</p>
