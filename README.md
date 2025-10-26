# Python Logger System

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)

> **Language:** **English** | [한국어](README_KO.md)

## Overview

Python Logger System is a high-performance asynchronous logging framework for Python, providing the same functionality as the C++ [logger_system](https://github.com/kcenon/logger_system). Designed for multithreaded applications requiring efficient, non-blocking logging with minimal overhead.

**Key Features:**
- **Asynchronous Processing**: Non-blocking log operations with queue-based batching
- **Multiple Writers**: Console, file, rotating file support
- **Thread-Safe**: Concurrent logging from multiple threads
- **Builder Pattern**: Fluent API for logger construction
- **Colored Output**: ANSI-colored console output
- **Zero External Dependencies**: Uses only Python standard library

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
│   └── writers/
│       ├── console_writer.py   # Console output
│       ├── file_writer.py      # File output
│       └── rotating_file_writer.py  # Rotating files
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

## Comparison with C++ Version

| Feature | C++ logger_system | Python logger_system |
|---------|------------------|---------------------|
| **Language** | C++20 | Python 3.8+ |
| **Async** | Lock-free queue | queue.Queue |
| **Performance** | ~1M msg/sec | ~100K msg/sec |
| **Writers** | 10+ types | 3 core types |
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
