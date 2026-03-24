"""Plugin runner: subprocess isolation layer for mqttui plugins.

Runs plugin code in separate processes communicating via newline-delimited
JSON on stdin/stdout. Plugins have no access to app internals (empty env).
"""
from __future__ import annotations

import json
import subprocess
import sys

import structlog

import mqttui.mqtt_client
from mqttui.plugins.registry import get_plugin_registry

logger = structlog.get_logger(__name__)

PLUGIN_TIMEOUT = 5  # seconds


class PluginRunner:
    """Executes plugins in isolated subprocesses with JSON protocol."""

    def __init__(self, app=None):
        self.app = app
        self.logger = structlog.get_logger(__name__)

    def call_plugin(self, plugin_config, event_type: str, data: dict) -> list[dict]:
        """Run a single plugin in a subprocess and return its actions.

        Args:
            plugin_config: PluginConfig model instance with entry_point.
            event_type: Hook name (e.g. 'on_message', 'on_rule_trigger').
            data: Event data dict to pass to the plugin.

        Returns:
            List of action dicts from the plugin, or empty list on error.
        """
        cmd = [sys.executable, "-m", plugin_config.entry_point]
        input_json = json.dumps({"event": event_type, "data": data}) + "\n"

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={},
            )
            stdout, stderr = proc.communicate(input=input_json, timeout=PLUGIN_TIMEOUT)

            if stderr:
                self.logger.debug(
                    "Plugin stderr output",
                    plugin=plugin_config.name,
                    stderr=stderr.strip(),
                )

            result = json.loads(stdout)
            return result.get("actions", [])

        except subprocess.TimeoutExpired:
            proc.kill()
            self.logger.warning(
                "Plugin timed out, killed",
                plugin=plugin_config.name,
                timeout=PLUGIN_TIMEOUT,
            )
            return []

        except json.JSONDecodeError:
            self.logger.warning(
                "Plugin returned invalid JSON",
                plugin=plugin_config.name,
                stdout=stdout[:200] if stdout else "",
            )
            return []

        except Exception as exc:
            self.logger.error(
                "Plugin execution error",
                plugin=plugin_config.name,
                error=str(exc),
            )
            return []

    def dispatch_message(self, topic: str, payload: str) -> list[dict]:
        """Run all enabled plugins for an MQTT message event.

        Returns:
            Aggregated list of action dicts from all plugins.
        """
        registry = get_plugin_registry()
        if registry is None:
            return []

        all_actions = []
        for plugin in registry.get_enabled_plugins():
            actions = self.call_plugin(
                plugin, "on_message", {"topic": topic, "payload": payload}
            )
            all_actions.extend(actions)
        return all_actions

    def dispatch_actions(self, actions: list[dict]):
        """Execute action dicts returned by plugins.

        Supported action types:
            - publish: Publish an MQTT message (topic, payload).
            - log: Log a message via structlog.
        """
        for action in actions:
            action_type = action.get("type")

            if action_type == "publish":
                mqttui.mqtt_client.publish(action["topic"], action["payload"])

            elif action_type == "log":
                self.logger.info(
                    "Plugin log action",
                    message=action.get("message", ""),
                )

            else:
                self.logger.warning(
                    "Unknown plugin action type",
                    action_type=action_type,
                    action=action,
                )

    def on_mqtt_message(self, sender, **kwargs):
        """Blinker signal handler for mqtt_message_received."""
        topic = kwargs.get("topic", "")
        payload = kwargs.get("payload", "")
        payload_str = payload if isinstance(payload, str) else str(payload)

        actions = self.dispatch_message(topic, payload_str)
        if actions:
            self.dispatch_actions(actions)

    def on_rule_trigger(self, sender, **kwargs):
        """Blinker signal handler for rule_fired."""
        rule_name = kwargs.get("rule_name", "")
        topic = kwargs.get("topic", "")
        payload = kwargs.get("payload", "")
        payload_str = payload if isinstance(payload, str) else str(payload)

        registry = get_plugin_registry()
        if registry is None:
            return

        all_actions = []
        for plugin in registry.get_enabled_plugins():
            actions = self.call_plugin(
                plugin,
                "on_rule_trigger",
                {"rule_name": rule_name, "topic": topic, "payload": payload_str},
            )
            all_actions.extend(actions)

        if all_actions:
            self.dispatch_actions(all_actions)


# Module-level singleton
_runner = None


def get_plugin_runner() -> PluginRunner | None:
    """Return the singleton PluginRunner instance."""
    return _runner


def init_plugin_runner(app) -> PluginRunner:
    """Create and initialize the PluginRunner singleton."""
    global _runner
    _runner = PluginRunner(app)
    logger.info("Plugin runner initialized")
    return _runner
