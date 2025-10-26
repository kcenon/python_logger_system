"""
Core module for logger system

This module contains the fundamental classes:
- Logger: Main logger class
- LoggerBuilder: Builder pattern for logger construction
- LogEntry: Log entry data structure
- LogLevel: Log level enumeration
- LoggerConfig: Configuration management
"""

from logger_module.core.logger import Logger
from logger_module.core.logger_builder import LoggerBuilder
from logger_module.core.log_entry import LogEntry
from logger_module.core.log_level import LogLevel
from logger_module.core.logger_config import LoggerConfig

__all__ = ["Logger", "LoggerBuilder", "LogEntry", "LogLevel", "LoggerConfig"]
