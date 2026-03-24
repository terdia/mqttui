"""Plugin registry: discovers, loads, and manages mqttui plugins."""
from __future__ import annotations

import importlib.metadata
from importlib.metadata import entry_points

import pluggy
import structlog

from mqttui.plugins.hookspec import MQTTUIPlugin, PROJECT_NAME
from mqttui.plugins.models import PluginConfig
from mqttui.extensions import sa

logger = structlog.get_logger(__name__)


class PluginRegistry:
    """Discovers plugins via entry_points and manages their lifecycle."""

    def __init__(self, app=None):
        self.app = app
        self.pm = pluggy.PluginManager(PROJECT_NAME)
        self.pm.add_hookspecs(MQTTUIPlugin)

    def discover(self) -> list[dict]:
        """Scan importlib.metadata entry_points for 'mqttui.plugins' group.

        For each discovered entry point, upsert a PluginConfig row if not
        already present. Returns list of discovered plugin dicts.
        """
        discovered = []
        try:
            eps = entry_points(group='mqttui.plugins')
        except TypeError:
            # Python 3.9 compat: entry_points() returns a dict
            eps = entry_points().get('mqttui.plugins', [])

        for ep in eps:
            name = ep.name
            value = ep.value
            version = None
            description = None

            try:
                if ep.dist:
                    version = ep.dist.version
                    description = ep.dist.metadata.get('Summary', '')
            except Exception:
                pass

            existing = PluginConfig.query.filter_by(name=name).first()
            if not existing:
                pc = PluginConfig(
                    name=name,
                    entry_point=value,
                    enabled=False,
                    version=version,
                    description=description,
                )
                sa.session.add(pc)
                sa.session.commit()
                discovered.append(pc.to_dict())
                logger.info("Discovered new plugin", name=name, version=version)
            else:
                # Update version/entry_point if changed
                existing.version = version
                existing.entry_point = value
                sa.session.commit()
                discovered.append(existing.to_dict())

        return discovered

    def list_plugins(self) -> list[dict]:
        """Return all registered plugins as list of dicts."""
        return [pc.to_dict() for pc in PluginConfig.query.all()]

    def get_enabled_plugins(self) -> list[PluginConfig]:
        """Return only plugins with enabled=True."""
        return PluginConfig.query.filter_by(enabled=True).all()

    def enable(self, name: str) -> bool:
        """Enable a plugin by name. Returns False if not found."""
        pc = PluginConfig.query.filter_by(name=name).first()
        if not pc:
            return False
        pc.enabled = True
        sa.session.commit()
        logger.info("Plugin enabled", name=name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a plugin by name. Returns False if not found."""
        pc = PluginConfig.query.filter_by(name=name).first()
        if not pc:
            return False
        pc.enabled = False
        sa.session.commit()
        logger.info("Plugin disabled", name=name)
        return True


# Module-level singleton
_registry = None


def get_plugin_registry() -> PluginRegistry:
    """Return the singleton PluginRegistry instance."""
    return _registry


def init_plugin_registry(app) -> PluginRegistry:
    """Create and initialize the PluginRegistry singleton."""
    global _registry
    _registry = PluginRegistry(app)
    with app.app_context():
        _registry.discover()
    logger.info("Plugin registry initialized")
    return _registry
