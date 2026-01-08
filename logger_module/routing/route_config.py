"""
Route configuration data structure

Equivalent to C++ log_router.h route configuration
"""

from dataclasses import dataclass, field
from typing import List, Callable, Optional

from logger_module.core.log_entry import LogEntry


@dataclass
class RouteConfig:
    """
    Configuration for a single log route.

    Defines how log entries should be filtered and which writers
    should receive matching entries.

    Attributes:
        name: Unique name for this route (for debugging/logging)
        writer_names: List of writer names to route matching entries to
        filter: Optional predicate function to filter entries
        stop_propagation: If True, stop processing subsequent routes on match
    """

    name: str
    writer_names: List[str] = field(default_factory=list)
    filter: Optional[Callable[[LogEntry], bool]] = None
    stop_propagation: bool = False

    def matches(self, entry: LogEntry) -> bool:
        """
        Check if this route matches the given entry.

        Args:
            entry: Log entry to check

        Returns:
            True if entry matches this route's filter (or no filter defined)
        """
        if self.filter is None:
            return True
        return self.filter(entry)

    def __repr__(self) -> str:
        """String representation."""
        filter_str = "custom" if self.filter else "none"
        return (
            f"RouteConfig(name={self.name!r}, "
            f"writers={self.writer_names}, "
            f"filter={filter_str}, "
            f"stop={self.stop_propagation})"
        )
