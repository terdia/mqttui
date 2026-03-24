"""Plugin management REST API and partials blueprint.

Provides endpoints to list, enable, and disable plugins,
plus an HTML partial for the plugins management tab.
"""
from flask import Blueprint, render_template
from flask_login import login_required

from mqttui.helpers import api_success, api_error
from mqttui.plugins.registry import get_plugin_registry

plugins_bp = Blueprint('plugins', __name__)


@plugins_bp.route('/api/v1/plugins')
@login_required
def list_plugins():
    """List all installed plugins.

    Returns:
        JSON envelope with plugins list.
    """
    registry = get_plugin_registry()
    plugins = registry.list_plugins() if registry else []
    return api_success({"plugins": plugins})


@plugins_bp.route('/api/v1/plugins/<name>/enable', methods=['POST'])
@login_required
def enable_plugin(name):
    """Enable a plugin by name.

    Returns:
        JSON success or 404 if plugin not found.
    """
    registry = get_plugin_registry()
    if not registry or not registry.enable(name):
        return api_error("Plugin not found", "NOT_FOUND", 404)
    return api_success({"name": name, "enabled": True})


@plugins_bp.route('/api/v1/plugins/<name>/disable', methods=['POST'])
@login_required
def disable_plugin(name):
    """Disable a plugin by name.

    Returns:
        JSON success or 404 if plugin not found.
    """
    registry = get_plugin_registry()
    if not registry or not registry.disable(name):
        return api_error("Plugin not found", "NOT_FOUND", 404)
    return api_success({"name": name, "enabled": False})


@plugins_bp.route('/partials/plugins')
@login_required
def plugins_partial():
    """Render plugins management HTML partial.

    Returns:
        HTML partial with plugin list and enable/disable controls.
    """
    registry = get_plugin_registry()
    plugins = registry.list_plugins() if registry else []
    return render_template('partials/plugins.html', plugins=plugins)
