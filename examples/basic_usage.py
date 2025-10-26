#!/usr/bin/env python3
"""Basic usage example"""

from logger_module import LoggerBuilder, LogLevel

def main():
    # Create logger with builder pattern
    logger = (LoggerBuilder()
        .with_name("example")
        .with_level(LogLevel.DEBUG)
        .with_console(colored=True)
        .with_file("logs/example.log", rotating=True)
        .with_async(True)
        .build())

    # Log messages
    logger.trace("This is trace")
    logger.debug("This is debug")
    logger.info("Application started")
    logger.warn("This is warning")
    logger.error("This is error")
    logger.critical("This is critical")

    # Flush and shutdown
    logger.flush()
    logger.shutdown()

if __name__ == "__main__":
    main()
