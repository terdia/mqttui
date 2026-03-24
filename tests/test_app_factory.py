def test_create_app(app):
    assert app is not None
    assert app.testing is True


def test_create_app_has_blueprints(app):
    blueprint_names = list(app.blueprints.keys())
    assert 'main' in blueprint_names
    assert 'api' in blueprint_names
    assert 'debug' in blueprint_names


def test_create_app_custom_config(tmp_path):
    from unittest.mock import patch
    with patch('mqttui.mqtt_client.init_mqtt'):
        from mqttui.app import create_app
        app = create_app({
            'SECRET_KEY': 'custom-key',
            'DB_ENABLED': False,
            'MQTT_BROKER': '127.0.0.1',
            'MQTT_PORT': 1883,
            'MQTT_VERSION': '3.1.1',
            'MQTT_TOPICS': '#',
            'MQTT_USERNAME': None,
            'MQTT_PASSWORD': None,
            'MQTT_KEEPALIVE': 60,
        })
    assert app.config['SECRET_KEY'] == 'custom-key'


def test_socketio_async_mode(app):
    from mqttui.extensions import socketio
    assert socketio.async_mode == 'gevent'
