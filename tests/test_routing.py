"""Tests for log routing system"""

import pytest
from unittest.mock import Mock, MagicMock

from logger_module import LoggerBuilder, LogLevel
from logger_module.core.log_entry import LogEntry
from logger_module.routing import LogRouter, RouteConfig, RouteBuilder


class MockWriter:
    """Mock writer for testing."""

    def __init__(self):
        self.entries = []

    def write(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    def clear(self) -> None:
        self.entries.clear()


class TestRouteConfig:
    """Test RouteConfig dataclass."""

    def test_create_config(self):
        config = RouteConfig(
            name="test_route",
            writer_names=["console", "file"]
        )
        assert config.name == "test_route"
        assert config.writer_names == ["console", "file"]
        assert config.filter is None
        assert config.stop_propagation is False

    def test_matches_without_filter(self):
        config = RouteConfig(name="test", writer_names=["console"])
        entry = LogEntry(level=LogLevel.INFO, message="Test")
        assert config.matches(entry) is True

    def test_matches_with_filter(self):
        config = RouteConfig(
            name="test",
            writer_names=["console"],
            filter=lambda e: e.level >= LogLevel.ERROR
        )
        info_entry = LogEntry(level=LogLevel.INFO, message="Test")
        error_entry = LogEntry(level=LogLevel.ERROR, message="Test")

        assert config.matches(info_entry) is False
        assert config.matches(error_entry) is True

    def test_repr(self):
        config = RouteConfig(name="test", writer_names=["console"])
        repr_str = repr(config)
        assert "test" in repr_str
        assert "console" in repr_str


class TestLogRouter:
    """Test LogRouter class."""

    def test_create_router(self):
        router = LogRouter()
        assert router is not None
        assert len(router.get_routes()) == 0

    def test_register_writer(self):
        router = LogRouter()
        writer = MockWriter()
        router.register_writer("console", writer)

        assert router.get_writer("console") is writer
        assert "console" in router.get_writer_names()

    def test_register_duplicate_writer_raises(self):
        router = LogRouter()
        writer = MockWriter()
        router.register_writer("console", writer)

        with pytest.raises(ValueError):
            router.register_writer("console", MockWriter())

    def test_unregister_writer(self):
        router = LogRouter()
        writer = MockWriter()
        router.register_writer("console", writer)
        router.unregister_writer("console")

        assert router.get_writer("console") is None

    def test_add_route(self):
        router = LogRouter()
        config = RouteConfig(name="test", writer_names=["console"])
        router.add_route(config)

        assert len(router.get_routes()) == 1

    def test_remove_route(self):
        router = LogRouter()
        config = RouteConfig(name="test", writer_names=["console"])
        router.add_route(config)
        assert router.remove_route("test") is True
        assert len(router.get_routes()) == 0

    def test_remove_nonexistent_route(self):
        router = LogRouter()
        assert router.remove_route("nonexistent") is False

    def test_clear_routes(self):
        router = LogRouter()
        router.add_route(RouteConfig(name="route1", writer_names=["console"]))
        router.add_route(RouteConfig(name="route2", writer_names=["file"]))
        router.clear_routes()

        assert len(router.get_routes()) == 0

    def test_set_default_writers(self):
        router = LogRouter()
        router.set_default_writers("console", "file")

        assert router.get_default_writers() == ["console", "file"]

    def test_get_writers_for_entry_with_default(self):
        router = LogRouter()
        router.set_default_writers("console")

        entry = LogEntry(level=LogLevel.INFO, message="Test")
        writers = router.get_writers_for_entry(entry)

        assert writers == ["console"]

    def test_get_writers_for_entry_with_route(self):
        router = LogRouter()
        router.set_default_writers("console")
        router.add_route(RouteConfig(
            name="errors",
            writer_names=["errors"],
            filter=lambda e: e.level >= LogLevel.ERROR
        ))

        info_entry = LogEntry(level=LogLevel.INFO, message="Test")
        error_entry = LogEntry(level=LogLevel.ERROR, message="Test")

        assert router.get_writers_for_entry(info_entry) == ["console"]
        assert router.get_writers_for_entry(error_entry) == ["errors"]

    def test_stop_propagation(self):
        router = LogRouter()
        router.add_route(RouteConfig(
            name="security",
            writer_names=["security_log"],
            filter=lambda e: "security" in e.message.lower(),
            stop_propagation=True
        ))
        router.add_route(RouteConfig(
            name="all",
            writer_names=["all_log"]
        ))

        security_entry = LogEntry(level=LogLevel.INFO, message="Security event")
        normal_entry = LogEntry(level=LogLevel.INFO, message="Normal event")

        # Security entry stops after first route
        assert router.get_writers_for_entry(security_entry) == ["security_log"]
        # Normal entry continues to second route
        assert router.get_writers_for_entry(normal_entry) == ["all_log"]

    def test_dispatch(self):
        router = LogRouter()
        console_writer = MockWriter()
        error_writer = MockWriter()

        router.register_writer("console", console_writer)
        router.register_writer("errors", error_writer)

        router.add_route(RouteConfig(
            name="errors",
            writer_names=["errors"],
            filter=lambda e: e.level >= LogLevel.ERROR
        ))
        router.set_default_writers("console")

        info_entry = LogEntry(level=LogLevel.INFO, message="Info")
        error_entry = LogEntry(level=LogLevel.ERROR, message="Error")

        router.dispatch(info_entry)
        router.dispatch(error_entry)

        assert len(console_writer.entries) == 1
        assert console_writer.entries[0].message == "Info"
        assert len(error_writer.entries) == 1
        assert error_writer.entries[0].message == "Error"

    def test_deduplication(self):
        router = LogRouter()
        router.add_route(RouteConfig(
            name="route1",
            writer_names=["console", "file"]
        ))
        router.add_route(RouteConfig(
            name="route2",
            writer_names=["console", "archive"]
        ))

        entry = LogEntry(level=LogLevel.INFO, message="Test")
        writers = router.get_writers_for_entry(entry)

        # Should deduplicate "console"
        assert writers == ["console", "file", "archive"]


class TestRouteBuilder:
    """Test RouteBuilder fluent API."""

    def test_basic_route(self):
        router = LogRouter()
        config = (router.route()
            .named("test_route")
            .route_to("console")
            .build())

        assert config.name == "test_route"
        assert config.writer_names == ["console"]

    def test_when_level(self):
        router = LogRouter()
        router.route() \
            .when_level(LogLevel.ERROR, LogLevel.CRITICAL) \
            .route_to("errors") \
            .build()

        info_entry = LogEntry(level=LogLevel.INFO, message="Test")
        error_entry = LogEntry(level=LogLevel.ERROR, message="Test")
        critical_entry = LogEntry(level=LogLevel.CRITICAL, message="Test")

        router.set_default_writers("console")

        assert router.get_writers_for_entry(info_entry) == ["console"]
        assert router.get_writers_for_entry(error_entry) == ["errors"]
        assert router.get_writers_for_entry(critical_entry) == ["errors"]

    def test_when_level_at_least(self):
        router = LogRouter()
        router.route() \
            .when_level_at_least(LogLevel.WARN) \
            .route_to("warnings") \
            .build()

        router.set_default_writers("console")

        info_entry = LogEntry(level=LogLevel.INFO, message="Test")
        warn_entry = LogEntry(level=LogLevel.WARN, message="Test")
        error_entry = LogEntry(level=LogLevel.ERROR, message="Test")

        assert router.get_writers_for_entry(info_entry) == ["console"]
        assert router.get_writers_for_entry(warn_entry) == ["warnings"]
        assert router.get_writers_for_entry(error_entry) == ["warnings"]

    def test_when_level_between(self):
        router = LogRouter()
        router.route() \
            .when_level_between(LogLevel.DEBUG, LogLevel.INFO) \
            .route_to("debug_info") \
            .build()

        router.set_default_writers("console")

        trace_entry = LogEntry(level=LogLevel.TRACE, message="Test")
        debug_entry = LogEntry(level=LogLevel.DEBUG, message="Test")
        info_entry = LogEntry(level=LogLevel.INFO, message="Test")
        warn_entry = LogEntry(level=LogLevel.WARN, message="Test")

        assert router.get_writers_for_entry(trace_entry) == ["console"]
        assert router.get_writers_for_entry(debug_entry) == ["debug_info"]
        assert router.get_writers_for_entry(info_entry) == ["debug_info"]
        assert router.get_writers_for_entry(warn_entry) == ["console"]

    def test_when_matches(self):
        router = LogRouter()
        router.route() \
            .when_matches(r"(login|logout)") \
            .route_to("auth") \
            .build()

        router.set_default_writers("console")

        login_entry = LogEntry(level=LogLevel.INFO, message="User login successful")
        logout_entry = LogEntry(level=LogLevel.INFO, message="User logout")
        normal_entry = LogEntry(level=LogLevel.INFO, message="Processing request")

        assert router.get_writers_for_entry(login_entry) == ["auth"]
        assert router.get_writers_for_entry(logout_entry) == ["auth"]
        assert router.get_writers_for_entry(normal_entry) == ["console"]

    def test_when_matches_case_insensitive(self):
        router = LogRouter()
        router.route() \
            .when_matches(r"ERROR", case_sensitive=False) \
            .route_to("errors") \
            .build()

        router.set_default_writers("console")

        upper_entry = LogEntry(level=LogLevel.INFO, message="ERROR occurred")
        lower_entry = LogEntry(level=LogLevel.INFO, message="error occurred")
        mixed_entry = LogEntry(level=LogLevel.INFO, message="Error occurred")

        assert router.get_writers_for_entry(upper_entry) == ["errors"]
        assert router.get_writers_for_entry(lower_entry) == ["errors"]
        assert router.get_writers_for_entry(mixed_entry) == ["errors"]

    def test_when_logger_name(self):
        router = LogRouter()
        router.route() \
            .when_logger_name("security", "audit") \
            .route_to("audit_log") \
            .build()

        router.set_default_writers("console")

        security_entry = LogEntry(
            level=LogLevel.INFO,
            message="Test",
            logger_name="security"
        )
        audit_entry = LogEntry(
            level=LogLevel.INFO,
            message="Test",
            logger_name="audit"
        )
        app_entry = LogEntry(
            level=LogLevel.INFO,
            message="Test",
            logger_name="app"
        )

        assert router.get_writers_for_entry(security_entry) == ["audit_log"]
        assert router.get_writers_for_entry(audit_entry) == ["audit_log"]
        assert router.get_writers_for_entry(app_entry) == ["console"]

    def test_when_has_extra(self):
        router = LogRouter()
        router.route() \
            .when_has_extra("user_id") \
            .route_to("user_activity") \
            .build()

        router.set_default_writers("console")

        with_user = LogEntry(
            level=LogLevel.INFO,
            message="Test",
            extra={"user_id": 123}
        )
        without_user = LogEntry(level=LogLevel.INFO, message="Test")

        assert router.get_writers_for_entry(with_user) == ["user_activity"]
        assert router.get_writers_for_entry(without_user) == ["console"]

    def test_when_extra_equals(self):
        router = LogRouter()
        router.route() \
            .when_extra_equals("environment", "production") \
            .route_to("prod_logs") \
            .build()

        router.set_default_writers("console")

        prod_entry = LogEntry(
            level=LogLevel.INFO,
            message="Test",
            extra={"environment": "production"}
        )
        dev_entry = LogEntry(
            level=LogLevel.INFO,
            message="Test",
            extra={"environment": "development"}
        )

        assert router.get_writers_for_entry(prod_entry) == ["prod_logs"]
        assert router.get_writers_for_entry(dev_entry) == ["console"]

    def test_custom_predicate(self):
        router = LogRouter()
        router.route() \
            .when(lambda e: len(e.message) > 100) \
            .route_to("long_messages") \
            .build()

        router.set_default_writers("console")

        short_entry = LogEntry(level=LogLevel.INFO, message="Short")
        long_entry = LogEntry(
            level=LogLevel.INFO,
            message="A" * 150
        )

        assert router.get_writers_for_entry(short_entry) == ["console"]
        assert router.get_writers_for_entry(long_entry) == ["long_messages"]

    def test_combined_filters(self):
        router = LogRouter()
        router.route() \
            .when_level_at_least(LogLevel.ERROR) \
            .when_matches(r"[Dd]atabase") \
            .route_to("db_errors") \
            .build()

        router.set_default_writers("console")

        # Both conditions must match
        db_error = LogEntry(level=LogLevel.ERROR, message="Database connection failed")
        db_info = LogEntry(level=LogLevel.INFO, message="Database query successful")
        other_error = LogEntry(level=LogLevel.ERROR, message="File not found")

        assert router.get_writers_for_entry(db_error) == ["db_errors"]
        assert router.get_writers_for_entry(db_info) == ["console"]
        assert router.get_writers_for_entry(other_error) == ["console"]

    def test_stop_propagation(self):
        router = LogRouter()
        router.route() \
            .when_matches(r"secret") \
            .route_to("secure_log") \
            .stop() \
            .build()

        router.route() \
            .route_to("general_log") \
            .build()

        secret_entry = LogEntry(level=LogLevel.INFO, message="secret data")
        normal_entry = LogEntry(level=LogLevel.INFO, message="normal data")

        assert router.get_writers_for_entry(secret_entry) == ["secure_log"]
        assert router.get_writers_for_entry(normal_entry) == ["general_log"]

    def test_route_without_writers_raises(self):
        router = LogRouter()
        with pytest.raises(ValueError):
            router.route().build()


class TestLoggerRouting:
    """Test Logger integration with routing."""

    def test_logger_get_router(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .build())

        router = logger.get_router()
        assert router is not None
        assert isinstance(router, LogRouter)
        logger.shutdown()

    def test_logger_with_named_writers(self):
        console_writer = MockWriter()
        error_writer = MockWriter()

        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .add_writer(console_writer, name="console")
            .add_writer(error_writer, name="errors")
            .build())

        router = logger.get_router()
        assert "console" in router.get_writer_names()
        assert "errors" in router.get_writer_names()
        logger.shutdown()

    def test_logger_routing_dispatch(self):
        console_writer = MockWriter()
        error_writer = MockWriter()

        def configure_routes(router):
            router.route() \
                .when_level_at_least(LogLevel.ERROR) \
                .route_to("errors") \
                .build()
            router.set_default_writers("console")

        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .add_writer(console_writer, name="console")
            .add_writer(error_writer, name="errors")
            .with_route(configure_routes)
            .build())

        logger.info("Info message")
        logger.error("Error message")

        assert len(console_writer.entries) == 1
        assert console_writer.entries[0].message == "Info message"
        assert len(error_writer.entries) == 1
        assert error_writer.entries[0].message == "Error message"

        logger.shutdown()

    def test_logger_without_routing(self):
        """Logger without routing sends to all writers."""
        writer1 = MockWriter()
        writer2 = MockWriter()

        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .add_writer(writer1)
            .add_writer(writer2)
            .build())

        logger.info("Test message")

        assert len(writer1.entries) == 1
        assert len(writer2.entries) == 1

        logger.shutdown()

    def test_builder_with_routing(self):
        logger = (LoggerBuilder()
            .with_name("test")
            .with_async(False)
            .with_routing()
            .build())

        assert logger.has_routing() is False  # No routes configured yet

        router = logger.get_router()
        router.route().route_to("test").build()

        assert logger.has_routing() is True

        logger.shutdown()


class TestThreadSafety:
    """Test thread safety of routing components."""

    def test_concurrent_dispatch(self):
        import threading
        import time

        router = LogRouter()
        writer = MockWriter()
        router.register_writer("test", writer)
        router.set_default_writers("test")

        errors = []
        entry_count = 100

        def dispatch_entries():
            try:
                for i in range(entry_count):
                    entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
                    router.dispatch(entry)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=dispatch_entries) for _ in range(4)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(writer.entries) == entry_count * 4

    def test_concurrent_route_modification(self):
        import threading

        router = LogRouter()
        errors = []

        def add_routes():
            try:
                for i in range(50):
                    router.route() \
                        .named(f"route_{threading.get_ident()}_{i}") \
                        .route_to("test") \
                        .build()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_routes) for _ in range(4)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(router.get_routes()) == 200
