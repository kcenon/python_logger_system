"""
Route builder with fluent API

Provides a fluent interface for constructing route configurations
"""

from __future__ import annotations
import re
from typing import Callable, Optional, Pattern, Set, Union, TYPE_CHECKING

from logger_module.core.log_entry import LogEntry
from logger_module.core.log_level import LogLevel
from logger_module.routing.route_config import RouteConfig

if TYPE_CHECKING:
    from logger_module.routing.log_router import LogRouter


class RouteBuilder:
    """
    Fluent builder for route configuration.

    Allows building complex routing rules with a readable, chainable API.

    Example:
        router.route() \\
            .when_level(LogLevel.ERROR, LogLevel.CRITICAL) \\
            .route_to("errors", "console") \\
            .build()
    """

    def __init__(self, router: "LogRouter", name: Optional[str] = None):
        """
        Initialize route builder.

        Args:
            router: Parent router to register route with
            name: Optional route name (auto-generated if not provided)
        """
        self._router = router
        self._name = name or f"route_{id(self)}"
        self._writer_names: list[str] = []
        self._filter: Optional[Callable[[LogEntry], bool]] = None
        self._stop_propagation = False
        self._filters: list[Callable[[LogEntry], bool]] = []

    def named(self, name: str) -> "RouteBuilder":
        """
        Set route name for debugging.

        Args:
            name: Human-readable route name

        Returns:
            Self for method chaining
        """
        self._name = name
        return self

    def when_level(self, *levels: LogLevel) -> "RouteBuilder":
        """
        Route when log level is one of the specified levels.

        Args:
            levels: Log levels to match

        Returns:
            Self for method chaining

        Example:
            router.route().when_level(LogLevel.ERROR, LogLevel.CRITICAL)
        """
        level_set: Set[LogLevel] = set(levels)
        self._filters.append(lambda e: e.level in level_set)
        return self

    def when_level_at_least(self, min_level: LogLevel) -> "RouteBuilder":
        """
        Route when log level is at or above the specified minimum.

        Args:
            min_level: Minimum log level (inclusive)

        Returns:
            Self for method chaining

        Example:
            router.route().when_level_at_least(LogLevel.WARN)
        """
        self._filters.append(lambda e: e.level >= min_level)
        return self

    def when_level_at_most(self, max_level: LogLevel) -> "RouteBuilder":
        """
        Route when log level is at or below the specified maximum.

        Args:
            max_level: Maximum log level (inclusive)

        Returns:
            Self for method chaining

        Example:
            router.route().when_level_at_most(LogLevel.INFO)
        """
        self._filters.append(lambda e: e.level <= max_level)
        return self

    def when_level_between(
        self,
        min_level: LogLevel,
        max_level: LogLevel
    ) -> "RouteBuilder":
        """
        Route when log level is within the specified range.

        Args:
            min_level: Minimum log level (inclusive)
            max_level: Maximum log level (inclusive)

        Returns:
            Self for method chaining

        Example:
            router.route().when_level_between(LogLevel.DEBUG, LogLevel.INFO)
        """
        self._filters.append(lambda e: min_level <= e.level <= max_level)
        return self

    def when_matches(
        self,
        pattern: Union[str, Pattern],
        case_sensitive: bool = True
    ) -> "RouteBuilder":
        """
        Route when message matches the regex pattern.

        Args:
            pattern: Regular expression pattern (string or compiled)
            case_sensitive: Whether matching is case-sensitive

        Returns:
            Self for method chaining

        Example:
            router.route().when_matches(r"(login|logout|permission)")
        """
        if isinstance(pattern, str):
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
        else:
            compiled = pattern

        self._filters.append(lambda e: compiled.search(e.message) is not None)
        return self

    def when_logger_name(self, *names: str) -> "RouteBuilder":
        """
        Route when logger name matches one of the specified names.

        Args:
            names: Logger names to match

        Returns:
            Self for method chaining

        Example:
            router.route().when_logger_name("security", "audit")
        """
        name_set = set(names)
        self._filters.append(lambda e: e.logger_name in name_set)
        return self

    def when_logger_name_starts_with(self, prefix: str) -> "RouteBuilder":
        """
        Route when logger name starts with the specified prefix.

        Args:
            prefix: Logger name prefix

        Returns:
            Self for method chaining

        Example:
            router.route().when_logger_name_starts_with("com.myapp.")
        """
        self._filters.append(lambda e: e.logger_name.startswith(prefix))
        return self

    def when_has_extra(self, key: str) -> "RouteBuilder":
        """
        Route when log entry has the specified extra field.

        Args:
            key: Extra field key to check

        Returns:
            Self for method chaining

        Example:
            router.route().when_has_extra("user_id")
        """
        self._filters.append(lambda e: key in e.extra)
        return self

    def when_extra_equals(self, key: str, value) -> "RouteBuilder":
        """
        Route when extra field equals the specified value.

        Args:
            key: Extra field key
            value: Expected value

        Returns:
            Self for method chaining

        Example:
            router.route().when_extra_equals("environment", "production")
        """
        self._filters.append(lambda e: e.extra.get(key) == value)
        return self

    def when(self, predicate: Callable[[LogEntry], bool]) -> "RouteBuilder":
        """
        Route when custom predicate returns True.

        Args:
            predicate: Function that takes LogEntry and returns bool

        Returns:
            Self for method chaining

        Example:
            router.route().when(lambda e: e.message.startswith("AUDIT:"))
        """
        self._filters.append(predicate)
        return self

    def route_to(self, *writer_names: str) -> "RouteBuilder":
        """
        Specify destination writers for this route.

        Args:
            writer_names: Names of writers to route to

        Returns:
            Self for method chaining

        Example:
            router.route().when_level(LogLevel.ERROR).route_to("errors", "alerts")
        """
        self._writer_names = list(writer_names)
        return self

    def stop(self) -> "RouteBuilder":
        """
        Stop propagation to subsequent routes on match.

        When a log entry matches this route, subsequent routes
        will not be evaluated.

        Returns:
            Self for method chaining

        Example:
            router.route() \\
                .when_matches(r"security") \\
                .route_to("security_log") \\
                .stop()
        """
        self._stop_propagation = True
        return self

    def build(self) -> RouteConfig:
        """
        Build and register the route configuration.

        Returns:
            The created RouteConfig

        Raises:
            ValueError: If no writers are specified
        """
        if not self._writer_names:
            raise ValueError("Route must have at least one destination writer")

        # Combine all filters with AND logic
        combined_filter: Optional[Callable[[LogEntry], bool]] = None
        if self._filters:
            if len(self._filters) == 1:
                combined_filter = self._filters[0]
            else:
                # Use default argument to capture filter list at definition time
                filters = self._filters.copy()
                combined_filter = lambda e, fs=filters: all(f(e) for f in fs)

        config = RouteConfig(
            name=self._name,
            writer_names=self._writer_names,
            filter=combined_filter,
            stop_propagation=self._stop_propagation
        )

        self._router.add_route(config)
        return config
