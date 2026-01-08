"""
Log router for directing entries to specific writers

Equivalent to C++ log_router.h
"""

from __future__ import annotations
import threading
from typing import Any, Dict, List, Optional, Set

from logger_module.core.log_entry import LogEntry
from logger_module.routing.route_config import RouteConfig
from logger_module.routing.route_builder import RouteBuilder


class LogRouter:
    """
    Routes log entries to appropriate writers based on configurable rules.

    The router evaluates entries against registered routes in order.
    Each route can specify filters and destination writers.

    Thread Safety:
        All methods are thread-safe for concurrent access.

    Example:
        router = LogRouter()
        router.register_writer("console", console_writer)
        router.register_writer("errors", error_file_writer)

        router.route() \\
            .when_level(LogLevel.ERROR, LogLevel.CRITICAL) \\
            .route_to("errors", "console") \\
            .build()

        router.set_default_writers("console")
    """

    def __init__(self):
        """Initialize log router."""
        self._routes: List[RouteConfig] = []
        self._default_writers: List[str] = []
        self._writers: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def register_writer(self, name: str, writer: Any) -> None:
        """
        Register a writer with a name.

        Args:
            name: Unique name for the writer
            writer: Writer instance with write(entry) method

        Raises:
            ValueError: If name is already registered
        """
        with self._lock:
            if name in self._writers:
                raise ValueError(f"Writer '{name}' is already registered")
            self._writers[name] = writer

    def unregister_writer(self, name: str) -> None:
        """
        Unregister a writer by name.

        Args:
            name: Name of writer to unregister

        Note:
            Does nothing if writer is not registered.
        """
        with self._lock:
            self._writers.pop(name, None)

    def get_writer(self, name: str) -> Optional[Any]:
        """
        Get a registered writer by name.

        Args:
            name: Writer name

        Returns:
            Writer instance or None if not found
        """
        with self._lock:
            return self._writers.get(name)

    def get_writer_names(self) -> List[str]:
        """
        Get all registered writer names.

        Returns:
            List of writer names
        """
        with self._lock:
            return list(self._writers.keys())

    def add_route(self, config: RouteConfig) -> None:
        """
        Add a routing rule.

        Args:
            config: Route configuration
        """
        with self._lock:
            self._routes.append(config)

    def remove_route(self, name: str) -> bool:
        """
        Remove a route by name.

        Args:
            name: Route name

        Returns:
            True if route was removed, False if not found
        """
        with self._lock:
            for i, route in enumerate(self._routes):
                if route.name == name:
                    self._routes.pop(i)
                    return True
            return False

    def clear_routes(self) -> None:
        """Remove all routing rules."""
        with self._lock:
            self._routes.clear()

    def set_default_writers(self, *writer_names: str) -> None:
        """
        Set default writers for unmatched entries.

        When no routes match an entry, it will be sent to these writers.

        Args:
            writer_names: Names of default writers
        """
        with self._lock:
            self._default_writers = list(writer_names)

    def get_default_writers(self) -> List[str]:
        """
        Get default writer names.

        Returns:
            List of default writer names
        """
        with self._lock:
            return self._default_writers.copy()

    def route(self, name: Optional[str] = None) -> RouteBuilder:
        """
        Start building a new route.

        Args:
            name: Optional route name

        Returns:
            RouteBuilder for fluent configuration

        Example:
            router.route("error_route") \\
                .when_level(LogLevel.ERROR) \\
                .route_to("errors") \\
                .build()
        """
        return RouteBuilder(self, name)

    def get_writers_for_entry(self, entry: LogEntry) -> List[str]:
        """
        Determine which writers should receive this entry.

        Evaluates routes in order. Returns default writers if no match.

        Args:
            entry: Log entry to route

        Returns:
            List of writer names (deduplicated)
        """
        with self._lock:
            matched_writers: List[str] = []

            for route in self._routes:
                if route.matches(entry):
                    matched_writers.extend(route.writer_names)
                    if route.stop_propagation:
                        break

            # Use defaults if no routes matched
            if not matched_writers:
                return self._default_writers.copy()

            # Deduplicate while preserving order
            seen: Set[str] = set()
            result: List[str] = []
            for name in matched_writers:
                if name not in seen:
                    seen.add(name)
                    result.append(name)

            return result

    def dispatch(self, entry: LogEntry) -> int:
        """
        Dispatch a log entry to appropriate writers.

        This method determines the target writers and writes the entry.

        Args:
            entry: Log entry to dispatch

        Returns:
            Number of writers the entry was sent to
        """
        writer_names = self.get_writers_for_entry(entry)
        count = 0

        with self._lock:
            for name in writer_names:
                writer = self._writers.get(name)
                if writer is not None:
                    try:
                        writer.write(entry)
                        count += 1
                    except Exception:
                        # Log errors are handled by individual writers
                        pass

        return count

    def get_routes(self) -> List[RouteConfig]:
        """
        Get all registered routes.

        Returns:
            Copy of routes list
        """
        with self._lock:
            return self._routes.copy()

    def __repr__(self) -> str:
        """String representation."""
        with self._lock:
            return (
                f"LogRouter(routes={len(self._routes)}, "
                f"writers={list(self._writers.keys())}, "
                f"defaults={self._default_writers})"
            )
