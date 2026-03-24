"""Tests for PluginRunner subprocess isolation and JSON protocol."""
import json
import subprocess
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from mqttui.plugins.runner import PluginRunner, PLUGIN_TIMEOUT


@pytest.fixture
def runner():
    """Create a PluginRunner instance without app context."""
    return PluginRunner(app=None)


@pytest.fixture
def mock_plugin():
    """Create a mock PluginConfig."""
    plugin = MagicMock()
    plugin.name = "test-plugin"
    plugin.entry_point = "test_plugin.main"
    plugin.enabled = True
    plugin.config_json = "{}"
    return plugin


class TestCallPlugin:
    """Tests for call_plugin subprocess execution."""

    def test_spawns_subprocess_with_correct_args(self, runner, mock_plugin):
        """call_plugin spawns subprocess with python -m entry_point."""
        with patch("mqttui.plugins.runner.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ('{"actions": []}', "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            runner.call_plugin(mock_plugin, "on_message", {"topic": "t", "payload": "p"})

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            import sys
            assert call_args[0][0] == [sys.executable, "-m", "test_plugin.main"]

    def test_sends_json_on_stdin(self, runner, mock_plugin):
        """Subprocess receives JSON with event type and data on stdin."""
        with patch("mqttui.plugins.runner.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ('{"actions": []}', "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            data = {"topic": "home/temp", "payload": "22.5"}
            runner.call_plugin(mock_plugin, "on_message", data)

            input_json = mock_proc.communicate.call_args[1].get("input") or mock_proc.communicate.call_args[0][0]
            parsed = json.loads(input_json)
            assert parsed["event"] == "on_message"
            assert parsed["data"] == data

    def test_parses_valid_json_response(self, runner, mock_plugin):
        """Subprocess response with actions list is parsed and returned."""
        actions = [{"type": "publish", "topic": "out/t", "payload": "hello"}]
        with patch("mqttui.plugins.runner.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (json.dumps({"actions": actions}), "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            result = runner.call_plugin(mock_plugin, "on_message", {"topic": "t", "payload": "p"})
            assert result == actions

    def test_timeout_kills_subprocess(self, runner, mock_plugin):
        """Subprocess exceeding timeout is killed and returns empty actions."""
        with patch("mqttui.plugins.runner.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)
            mock_popen.return_value = mock_proc

            result = runner.call_plugin(mock_plugin, "on_message", {"topic": "t", "payload": "p"})

            mock_proc.kill.assert_called_once()
            assert result == []

    def test_invalid_json_returns_empty(self, runner, mock_plugin):
        """Invalid JSON from subprocess is handled gracefully."""
        with patch("mqttui.plugins.runner.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("not valid json!", "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            result = runner.call_plugin(mock_plugin, "on_message", {"topic": "t", "payload": "p"})
            assert result == []

    def test_empty_env_for_security_isolation(self, runner, mock_plugin):
        """Subprocess is spawned with empty env dict for isolation."""
        with patch("mqttui.plugins.runner.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ('{"actions": []}', "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            runner.call_plugin(mock_plugin, "on_message", {"topic": "t", "payload": "p"})

            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["env"] == {}


class TestDispatchMessage:
    """Tests for dispatch_message calling all enabled plugins."""

    def test_calls_all_enabled_plugins(self, runner):
        """dispatch_message calls call_plugin for each enabled plugin."""
        plugin1 = MagicMock(name="p1", entry_point="p1.main", enabled=True)
        plugin2 = MagicMock(name="p2", entry_point="p2.main", enabled=True)

        mock_registry = MagicMock()
        mock_registry.get_enabled_plugins.return_value = [plugin1, plugin2]

        with patch("mqttui.plugins.runner.get_plugin_registry", return_value=mock_registry):
            with patch.object(runner, "call_plugin", return_value=[]) as mock_call:
                runner.dispatch_message("test/topic", "payload")

                assert mock_call.call_count == 2
                mock_call.assert_any_call(plugin1, "on_message", {"topic": "test/topic", "payload": "payload"})
                mock_call.assert_any_call(plugin2, "on_message", {"topic": "test/topic", "payload": "payload"})

    def test_collects_all_actions(self, runner):
        """dispatch_message aggregates actions from all plugins."""
        plugin1 = MagicMock()
        plugin2 = MagicMock()

        mock_registry = MagicMock()
        mock_registry.get_enabled_plugins.return_value = [plugin1, plugin2]

        actions1 = [{"type": "publish", "topic": "a", "payload": "1"}]
        actions2 = [{"type": "log", "message": "hello"}]

        with patch("mqttui.plugins.runner.get_plugin_registry", return_value=mock_registry):
            with patch.object(runner, "call_plugin", side_effect=[actions1, actions2]):
                result = runner.dispatch_message("t", "p")

                assert len(result) == 2
                assert actions1[0] in result
                assert actions2[0] in result


class TestDispatchActions:
    """Tests for dispatch_actions handling different action types."""

    def test_publish_action(self, runner):
        """Publish actions call mqtt_client.publish."""
        actions = [{"type": "publish", "topic": "out/topic", "payload": "hello"}]

        with patch("mqttui.plugins.runner.mqttui.mqtt_client") as mock_mqtt:
            runner.dispatch_actions(actions)
            mock_mqtt.publish.assert_called_once_with("out/topic", "hello")

    def test_log_action(self, runner):
        """Log actions are logged without errors."""
        actions = [{"type": "log", "message": "test log message"}]
        # Should not raise
        runner.dispatch_actions(actions)

    def test_unknown_action_type(self, runner):
        """Unknown action types are logged and skipped without crash."""
        actions = [{"type": "unknown_action", "data": "something"}]
        # Should not raise
        runner.dispatch_actions(actions)


class TestPluginTimeout:
    """Tests for timeout configuration."""

    def test_timeout_is_5_seconds(self):
        """PLUGIN_TIMEOUT constant is 5 seconds."""
        assert PLUGIN_TIMEOUT == 5
