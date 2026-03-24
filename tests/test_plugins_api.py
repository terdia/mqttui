"""Tests for plugin management REST API and example plugins."""
import json
import subprocess
import sys

import pytest


# ── API Tests ──────────────────────────────────────────────────────


class TestPluginsAPI:
    """Test plugin management REST API endpoints."""

    @pytest.fixture(autouse=True)
    def seed_plugin(self, app):
        """Seed a test plugin into the database."""
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.extensions import sa

            pc = PluginConfig(
                name="test-plugin",
                entry_point="mqttui.plugins.examples.json_formatter",
                enabled=False,
                version="1.0.0",
                description="A test plugin",
            )
            sa.session.add(pc)
            sa.session.commit()

    def test_list_plugins(self, auth_client):
        """GET /api/v1/plugins returns JSON list of plugins."""
        resp = auth_client.get("/api/v1/plugins")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        plugins = data["data"]["plugins"]
        assert isinstance(plugins, list)
        assert any(p["name"] == "test-plugin" for p in plugins)

    def test_enable_plugin(self, auth_client, app):
        """POST /api/v1/plugins/test-plugin/enable enables the plugin."""
        resp = auth_client.post("/api/v1/plugins/test-plugin/enable")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"

        # Verify plugin is now enabled
        with app.app_context():
            from mqttui.plugins.models import PluginConfig

            pc = PluginConfig.query.filter_by(name="test-plugin").first()
            assert pc.enabled is True

    def test_disable_plugin(self, auth_client, app):
        """POST /api/v1/plugins/test-plugin/disable disables the plugin."""
        # Enable first
        auth_client.post("/api/v1/plugins/test-plugin/enable")
        # Then disable
        resp = auth_client.post("/api/v1/plugins/test-plugin/disable")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"

        with app.app_context():
            from mqttui.plugins.models import PluginConfig

            pc = PluginConfig.query.filter_by(name="test-plugin").first()
            assert pc.enabled is False

    def test_enable_nonexistent_returns_404(self, auth_client):
        """POST /api/v1/plugins/nonexistent/enable returns 404."""
        resp = auth_client.post("/api/v1/plugins/nonexistent/enable")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["status"] == "error"

    def test_disable_nonexistent_returns_404(self, auth_client):
        """POST /api/v1/plugins/nonexistent/disable returns 404."""
        resp = auth_client.post("/api/v1/plugins/nonexistent/disable")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["status"] == "error"

    def test_partials_plugins_returns_html(self, auth_client):
        """GET /partials/plugins returns HTML partial."""
        resp = auth_client.get("/partials/plugins")
        assert resp.status_code == 200
        assert b"test-plugin" in resp.data


# ── Example Plugin Tests ───────────────────────────────────────────


class TestJsonFormatterPlugin:
    """Test the json_formatter example plugin via subprocess."""

    def test_formats_json_payload(self):
        """JSON payload is pretty-printed."""
        input_data = {
            "event": "on_message",
            "data": {"topic": "test/topic", "payload": '{"a": 1, "b": 2}'},
        }
        result = subprocess.run(
            [sys.executable, "-m", "mqttui.plugins.examples.json_formatter"],
            input=json.dumps(input_data) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = json.loads(result.stdout)
        assert "actions" in output
        assert len(output["actions"]) == 1
        assert output["actions"][0]["type"] == "transform"
        # Verify it's pretty-printed (has newlines)
        assert "\n" in output["actions"][0]["result"]

    def test_non_json_payload_returns_empty_actions(self):
        """Non-JSON payload returns empty actions list."""
        input_data = {
            "event": "on_message",
            "data": {"topic": "test/topic", "payload": "not json"},
        }
        result = subprocess.run(
            [sys.executable, "-m", "mqttui.plugins.examples.json_formatter"],
            input=json.dumps(input_data) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = json.loads(result.stdout)
        assert output["actions"] == []

    def test_non_message_event_returns_empty_actions(self):
        """Non on_message events return empty actions."""
        input_data = {
            "event": "on_rule_trigger",
            "data": {"rule_name": "test"},
        }
        result = subprocess.run(
            [sys.executable, "-m", "mqttui.plugins.examples.json_formatter"],
            input=json.dumps(input_data) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = json.loads(result.stdout)
        assert output["actions"] == []


class TestTopicLoggerPlugin:
    """Test the topic_logger example plugin via subprocess."""

    def test_logs_message(self):
        """on_message event produces a log action."""
        input_data = {
            "event": "on_message",
            "data": {"topic": "home/sensor/temp", "payload": "22.5"},
        }
        result = subprocess.run(
            [sys.executable, "-m", "mqttui.plugins.examples.topic_logger"],
            input=json.dumps(input_data) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = json.loads(result.stdout)
        assert len(output["actions"]) == 1
        assert output["actions"][0]["type"] == "log"
        assert "home/sensor/temp" in output["actions"][0]["message"]
        assert "22.5" in output["actions"][0]["message"]

    def test_logs_to_stderr(self):
        """Plugin logs to stderr (not stdout which is protocol)."""
        input_data = {
            "event": "on_message",
            "data": {"topic": "home/sensor/temp", "payload": "22.5"},
        }
        result = subprocess.run(
            [sys.executable, "-m", "mqttui.plugins.examples.topic_logger"],
            input=json.dumps(input_data) + "\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert "home/sensor/temp" in result.stderr
