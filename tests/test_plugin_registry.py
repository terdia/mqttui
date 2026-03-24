"""Tests for plugin hookspec, model, and registry."""
import pytest
from unittest.mock import patch, MagicMock


class TestMQTTUIPluginHookspec:
    """Test that MQTTUIPlugin defines the expected hookspec methods."""

    def test_has_on_message_hookspec(self):
        from mqttui.plugins.hookspec import MQTTUIPlugin
        assert hasattr(MQTTUIPlugin, 'on_message')

    def test_has_on_connect_hookspec(self):
        from mqttui.plugins.hookspec import MQTTUIPlugin
        assert hasattr(MQTTUIPlugin, 'on_connect')

    def test_has_on_rule_trigger_hookspec(self):
        from mqttui.plugins.hookspec import MQTTUIPlugin
        assert hasattr(MQTTUIPlugin, 'on_rule_trigger')

    def test_hookspec_markers_applied(self):
        from mqttui.plugins.hookspec import MQTTUIPlugin
        # pluggy marks hookspec methods with a special attribute
        assert hasattr(MQTTUIPlugin.on_message, 'mqttui_spec')
        assert hasattr(MQTTUIPlugin.on_connect, 'mqttui_spec')
        assert hasattr(MQTTUIPlugin.on_rule_trigger, 'mqttui_spec')

    def test_hookimpl_marker_exported(self):
        from mqttui.plugins.hookspec import hookimpl
        assert hookimpl is not None


class TestPluginConfigModel:
    """Test PluginConfig SQLAlchemy model CRUD."""

    def test_create_plugin_config(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.extensions import sa

            pc = PluginConfig(
                name='test-plugin',
                entry_point='test_plugin:TestPlugin',
                enabled=False,
                config_json='{"key": "value"}',
            )
            sa.session.add(pc)
            sa.session.commit()

            found = PluginConfig.query.filter_by(name='test-plugin').first()
            assert found is not None
            assert found.name == 'test-plugin'
            assert found.entry_point == 'test_plugin:TestPlugin'
            assert found.enabled is False
            assert found.config_json == '{"key": "value"}'

    def test_update_enabled_state(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.extensions import sa

            pc = PluginConfig(
                name='toggle-plugin',
                entry_point='toggle:Plugin',
                enabled=False,
            )
            sa.session.add(pc)
            sa.session.commit()

            pc.enabled = True
            sa.session.commit()

            found = PluginConfig.query.filter_by(name='toggle-plugin').first()
            assert found.enabled is True

    def test_to_dict(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.extensions import sa

            pc = PluginConfig(
                name='dict-plugin',
                entry_point='dict:Plugin',
                enabled=True,
                config_json='{}',
                version='1.0.0',
                description='A test plugin',
            )
            sa.session.add(pc)
            sa.session.commit()

            d = pc.to_dict()
            assert d['name'] == 'dict-plugin'
            assert d['entry_point'] == 'dict:Plugin'
            assert d['enabled'] is True
            assert d['version'] == '1.0.0'
            assert d['description'] == 'A test plugin'
            assert 'installed_at' in d


class TestPluginRegistry:
    """Test PluginRegistry discover, list, enable, disable."""

    def test_discover_with_no_entry_points(self, app):
        with app.app_context():
            from mqttui.plugins.registry import PluginRegistry
            registry = PluginRegistry(app)

            with patch('mqttui.plugins.registry.entry_points', return_value=[]):
                result = registry.discover()
            assert result == []

    def test_discover_with_mock_entry_point(self, app):
        with app.app_context():
            from mqttui.plugins.registry import PluginRegistry
            from mqttui.extensions import sa

            registry = PluginRegistry(app)

            mock_ep = MagicMock()
            mock_ep.name = 'sample-plugin'
            mock_ep.value = 'sample_plugin:SamplePlugin'
            mock_ep.dist = MagicMock()
            mock_ep.dist.version = '0.1.0'
            mock_ep.dist.metadata = {'Summary': 'A sample plugin'}

            with patch('mqttui.plugins.registry.entry_points', return_value=[mock_ep]):
                result = registry.discover()

            assert len(result) == 1
            assert result[0]['name'] == 'sample-plugin'

    def test_list_plugins(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.plugins.registry import PluginRegistry
            from mqttui.extensions import sa

            pc = PluginConfig(
                name='list-plugin',
                entry_point='list:Plugin',
                enabled=True,
            )
            sa.session.add(pc)
            sa.session.commit()

            registry = PluginRegistry(app)
            plugins = registry.list_plugins()
            names = [p['name'] for p in plugins]
            assert 'list-plugin' in names

    def test_enable_plugin(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.plugins.registry import PluginRegistry
            from mqttui.extensions import sa

            pc = PluginConfig(
                name='enable-me',
                entry_point='enable:Plugin',
                enabled=False,
            )
            sa.session.add(pc)
            sa.session.commit()

            registry = PluginRegistry(app)
            result = registry.enable('enable-me')
            assert result is True

            found = PluginConfig.query.filter_by(name='enable-me').first()
            assert found.enabled is True

    def test_disable_plugin(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.plugins.registry import PluginRegistry
            from mqttui.extensions import sa

            pc = PluginConfig(
                name='disable-me',
                entry_point='disable:Plugin',
                enabled=True,
            )
            sa.session.add(pc)
            sa.session.commit()

            registry = PluginRegistry(app)
            result = registry.disable('disable-me')
            assert result is True

            found = PluginConfig.query.filter_by(name='disable-me').first()
            assert found.enabled is False

    def test_enable_nonexistent_returns_false(self, app):
        with app.app_context():
            from mqttui.plugins.registry import PluginRegistry
            registry = PluginRegistry(app)
            assert registry.enable('no-such-plugin') is False

    def test_disable_nonexistent_returns_false(self, app):
        with app.app_context():
            from mqttui.plugins.registry import PluginRegistry
            registry = PluginRegistry(app)
            assert registry.disable('no-such-plugin') is False

    def test_get_enabled_plugins(self, app):
        with app.app_context():
            from mqttui.plugins.models import PluginConfig
            from mqttui.plugins.registry import PluginRegistry
            from mqttui.extensions import sa

            sa.session.add(PluginConfig(name='on-plugin', entry_point='on:P', enabled=True))
            sa.session.add(PluginConfig(name='off-plugin', entry_point='off:P', enabled=False))
            sa.session.commit()

            registry = PluginRegistry(app)
            enabled = registry.get_enabled_plugins()
            names = [p.name for p in enabled]
            assert 'on-plugin' in names
            assert 'off-plugin' not in names
