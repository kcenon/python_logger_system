"""
Main Logger class - Asynchronous high-performance logger

Equivalent to C++ logger.h
"""

from __future__ import annotations
from typing import Optional, List, Any
import threading
import queue
import time
import atexit

from logger_module.core.log_level import LogLevel
from logger_module.core.log_entry import LogEntry
from logger_module.core.logger_config import LoggerConfig


class Logger:
    """Main logger class with async support."""

    def __init__(self, config: Optional[LoggerConfig] = None):
        self._config = config or LoggerConfig.default()
        self._writers: List[Any] = []
        self._filters: List[Any] = []
        self._running = False
        self._log_queue: Optional[queue.Queue] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._metrics = {"logged": 0, "dropped": 0, "processed": 0}
        
        if self._config.async_mode:
            self._start_async_worker()
        
        atexit.register(self.shutdown)

    def _start_async_worker(self):
        """Start async worker thread."""
        self._log_queue = queue.Queue(maxsize=self._config.queue_size)
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name=f"{self._config.name}-worker",
            daemon=True
        )
        self._worker_thread.start()

    def _process_queue(self):
        """Process log entries from queue (worker thread)."""
        batch = []
        last_flush = time.time()

        while self._running or not self._log_queue.empty():
            try:
                timeout = self._config.flush_interval_ms / 1000.0
                entry = self._log_queue.get(timeout=timeout)

                try:
                    batch.append(entry)

                    should_flush = (
                        len(batch) >= self._config.batch_size or
                        (time.time() - last_flush) >= timeout
                    )

                    if should_flush:
                        self._write_batch(batch)
                        batch.clear()
                        last_flush = time.time()
                finally:
                    # Always mark task as done to prevent queue.join() deadlock
                    self._log_queue.task_done()

            except queue.Empty:
                if batch:
                    self._write_batch(batch)
                    batch.clear()
                    last_flush = time.time()

    def _write_batch(self, batch: List[LogEntry]):
        """Write batch of log entries to all writers."""
        for entry in batch:
            for writer in self._writers:
                try:
                    writer.write(entry)
                except Exception as e:
                    print(f"Writer error: {e}")
            self._metrics["processed"] += 1

    def add_writer(self, writer: Any) -> None:
        """Add a log writer."""
        self._writers.append(writer)

    def add_filter(self, log_filter: Any) -> None:
        """
        Add a log filter.

        Args:
            log_filter: Filter instance with should_log(entry) method
        """
        self._filters.append(log_filter)

    def log(self, level: LogLevel, message: str, **kwargs) -> None:
        """Log a message."""
        if level < self._config.min_level:
            return
        
        entry = LogEntry(
            level=level,
            message=message,
            logger_name=self._config.name,
            **kwargs
        )
        
        # Apply filters
        for f in self._filters:
            if not f.should_log(entry):
                return
        
        if self._config.async_mode:
            try:
                self._log_queue.put_nowait(entry)
                self._metrics["logged"] += 1
            except queue.Full:
                self._metrics["dropped"] += 1
        else:
            self._write_batch([entry])
            self._metrics["logged"] += 1

    def trace(self, message: str, **kwargs) -> None:
        """Log trace message."""
        self.log(LogLevel.TRACE, message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warn(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.log(LogLevel.WARN, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def flush(self):
        """Flush all pending log entries."""
        if self._config.async_mode and self._log_queue:
            # Wait for queue to empty
            self._log_queue.join()

            # Wait for all entries to be processed (not just dequeued)
            max_wait = 1.0  # Maximum 1 second wait
            start_time = time.time()
            while (time.time() - start_time) < max_wait:
                if self._metrics["processed"] >= self._metrics["logged"]:
                    break
                time.sleep(0.01)  # 10ms polling interval

        for writer in self._writers:
            if hasattr(writer, 'flush'):
                writer.flush()

    def shutdown(self):
        """Shutdown logger gracefully."""
        if not self._running:
            return
        
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        
        for writer in self._writers:
            if hasattr(writer, 'close'):
                writer.close()

    def get_metrics(self) -> dict:
        """Get logging metrics."""
        return self._metrics.copy()
