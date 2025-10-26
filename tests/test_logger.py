"""Basic tests for logger system"""

import pytest
import time
from pathlib import Path

from logger_module import LoggerBuilder, LogLevel, Logger, LoggerConfig
from logger_module.core.log_entry import LogEntry


class TestLogLevel:
    """Test log level functionality."""

    def test_log_levels(self):
        assert LogLevel.TRACE < LogLevel.DEBUG
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARN
        assert LogLevel.WARN < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.CRITICAL

    def test_from_string(self):
        assert LogLevel.from_string("DEBUG") == LogLevel.DEBUG
        assert LogLevel.from_string("info") == LogLevel.INFO


class TestLogEntry:
    """Test log entry structure."""

    def test_create_entry(self):
        entry = LogEntry(level=LogLevel.INFO, message="Test message")
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.logger_name == ""

    def test_to_dict(self):
        entry = LogEntry(level=LogLevel.DEBUG, message="Test")
        data = entry.to_dict()
        assert data["level"] == "DEBUG"
        assert data["message"] == "Test"


class TestLoggerConfig:
    """Test logger configuration."""

    def test_default_config(self):
        config = LoggerConfig.default()
        assert config.name == "logger"
        assert config.min_level == LogLevel.INFO
        assert config.async_mode is True

    def test_debug_config(self):
        config = LoggerConfig.debug_config()
        assert config.min_level == LogLevel.DEBUG
        assert config.async_mode is False


class TestLogger:
    """Test main logger functionality."""

    def test_create_logger(self):
        config = LoggerConfig(async_mode=False)
        logger = Logger(config)
        assert logger is not None
        logger.shutdown()

    def test_log_messages(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_level(LogLevel.DEBUG)
            .with_async(False)
            .build())
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warn("Warning message")
        
        metrics = logger.get_metrics()
        assert metrics["logged"] == 3
        logger.shutdown()

    def test_builder_pattern(self):
        logger = (LoggerBuilder()
            .with_name("builder_test")
            .with_level(LogLevel.INFO)
            .with_console(colored=False)
            .build())
        
        assert logger._config.name == "builder_test"
        assert logger._config.min_level == LogLevel.INFO
        logger.shutdown()
