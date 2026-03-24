"""Plugin hook specifications for mqttui."""
from __future__ import annotations

import pluggy

PROJECT_NAME = "mqttui"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class MQTTUIPlugin:
    """Hook specifications for mqttui plugins.

    Plugin authors implement these hooks using the @hookimpl decorator.
    """

    @hookspec
    def on_message(self, topic: str, payload: str) -> dict | None:
        """Called when an MQTT message is received.

        Args:
            topic: The MQTT topic string.
            payload: The message payload as a string.

        Returns:
            Optional dict with transformed/enriched data, or None.
        """

    @hookspec
    def on_connect(self) -> None:
        """Called when the MQTT client connects to the broker."""

    @hookspec
    def on_rule_trigger(self, rule_name: str, topic: str, payload: str) -> dict | None:
        """Called when an automation rule fires.

        Args:
            rule_name: Name of the triggered rule.
            topic: The MQTT topic that triggered the rule.
            payload: The message payload.

        Returns:
            Optional dict with additional context or modifications.
        """
