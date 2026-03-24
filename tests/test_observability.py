"""Tests for structured logging (structlog) and Prometheus metrics endpoint."""
import pytest
from unittest.mock import patch


class TestStructlogConfiguration:
    """Tests for mqttui.logging_config.configure_logging."""

    def test_configure_logging_debug_uses_console_renderer(self):
        """configure_logging(debug=True) sets up colored console renderer."""
        import structlog
        from mqttui.logging_config import configure_logging

        configure_logging(debug=True)

        # structlog should be configured -- get a logger and verify it works
        logger = structlog.get_logger("test")
        assert logger is not None
        # In debug mode, the formatter should use ConsoleRenderer (not JSON)
        import logging
        root = logging.getLogger()
        assert len(root.handlers) > 0
        formatter = root.handlers[0].formatter
        # ProcessorFormatter stores processors list
        assert hasattr(formatter, '_processors')
        processor_names = [type(p).__name__ for p in formatter._processors]
        assert 'ConsoleRenderer' in processor_names

    def test_configure_logging_production_uses_json_renderer(self):
        """configure_logging(debug=False) sets up JSON renderer."""
        import structlog
        from mqttui.logging_config import configure_logging

        configure_logging(debug=False)

        import logging
        root = logging.getLogger()
        assert len(root.handlers) > 0
        formatter = root.handlers[0].formatter
        assert hasattr(formatter, '_processors')
        processor_names = [type(p).__name__ for p in formatter._processors]
        assert 'JSONRenderer' in processor_names

    def test_structlog_get_logger_returns_bound_logger(self):
        """structlog.get_logger() returns a logger with .info() and .error()."""
        import structlog
        from mqttui.logging_config import configure_logging

        configure_logging(debug=True)
        logger = structlog.get_logger("test.bound")

        assert callable(getattr(logger, 'info', None))
        assert callable(getattr(logger, 'error', None))


class TestPrometheusMetricsEndpoint:
    """Tests for the /metrics Prometheus scrape endpoint."""

    def test_metrics_returns_200(self, client):
        """GET /metrics returns 200 with text/plain content type."""
        response = client.get('/metrics')
        assert response.status_code == 200
        assert 'text/plain' in response.content_type

    def test_metrics_contains_mqtt_messages_total(self, client):
        """The /metrics response contains mqtt_messages_total counter."""
        response = client.get('/metrics')
        assert b'mqtt_messages_total' in response.data

    def test_metrics_contains_mqtt_connected_gauge(self, client):
        """The /metrics response contains mqtt_connected gauge."""
        response = client.get('/metrics')
        assert b'mqtt_connected' in response.data

    def test_metrics_contains_rule_firings_total(self, client):
        """The /metrics response contains rule_firings_total counter."""
        response = client.get('/metrics')
        assert b'rule_firings_total' in response.data

    def test_metrics_no_auth_required(self, client):
        """The /metrics endpoint does NOT require authentication."""
        # client is unauthenticated -- should still get 200, not 302/401
        response = client.get('/metrics')
        assert response.status_code == 200
