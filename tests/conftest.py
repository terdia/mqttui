import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock


@pytest.fixture
def app(tmp_path):
    """Create application for testing with mocked MQTT."""
    db_path = str(tmp_path / "test.db")

    # Patch init_mqtt to prevent real MQTT broker connection
    with patch('mqttui.mqtt_client.init_mqtt') as mock_init:
        from mqttui.app import create_app
        app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-secret-key',
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path}/test_users.db',
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'DB_ENABLED': True,
            'DB_PATH': db_path,
            'DB_MAX_MESSAGES': 1000,
            'MQTT_BROKER': '127.0.0.1',
            'MQTT_PORT': 1883,
            'MQTT_VERSION': '3.1.1',
            'MQTT_TOPICS': '#',
            'MQTT_USERNAME': None,
            'MQTT_PASSWORD': None,
            'MQTT_KEEPALIVE': 60,
        })
    yield app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def test_db(tmp_path):
    """Isolated MessageDatabase for testing."""
    db_path = str(tmp_path / "test_messages.db")
    from mqttui.database import MessageDatabase
    db = MessageDatabase(db_path, max_messages=100)
    yield db
    db.close()


@pytest.fixture
def auth_client(app):
    """Flask test client with authenticated session."""
    client = app.test_client()
    with app.app_context():
        from mqttui.models import User
        from mqttui.extensions import sa
        user = User.query.filter_by(username='admin').first()
        if not user:
            user = User(username='admin')
            user.set_password('admin')
            user.generate_api_token()
            sa.session.add(user)
            sa.session.commit()
    # Log in via test client
    client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=False)
    return client


@pytest.fixture
def api_token(app):
    """Return a valid API token for testing."""
    with app.app_context():
        from mqttui.models import User
        user = User.query.filter_by(username='admin').first()
        return user.api_token


@pytest.fixture
def mock_mqtt():
    """Mock MQTT client to prevent broker connections."""
    with patch('mqttui.mqtt_client._mqtt_client') as mock_client:
        mock_client.publish = MagicMock()
        mock_client.connect = MagicMock()
        mock_client.subscribe = MagicMock()
        yield mock_client
