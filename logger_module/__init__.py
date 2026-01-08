"""
BSD 3-Clause License

Copyright (c) 2021, 🍀☀🌕🌥 🌊
All rights reserved.

Python Logger System - A high-performance asynchronous logging framework
Equivalent to the C++ logger_system implementation
"""

__version__ = "1.0.0"
__author__ = "kcenon"
__email__ = "kcenon@naver.com"

from logger_module.core.logger import Logger
from logger_module.core.logger_builder import LoggerBuilder
from logger_module.core.log_entry import LogEntry
from logger_module.core.log_level import LogLevel
from logger_module.core.logger_config import LoggerConfig

# Import submodules (not all classes by default)
from logger_module import filters
from logger_module import formatters
from logger_module import monitoring
from logger_module import routing
from logger_module import safety
from logger_module import security

__all__ = [
    "Logger",
    "LoggerBuilder",
    "LogEntry",
    "LogLevel",
    "LoggerConfig",
    "filters",
    "formatters",
    "monitoring",
    "routing",
    "safety",
    "security",
]
