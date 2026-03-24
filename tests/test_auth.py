"""Tests for authentication flow."""


def test_login_page_loads(client):
    """GET /login returns 200 with login form."""
    r = client.get('/login')
    assert r.status_code == 200
    assert b'username' in r.data
    assert b'password' in r.data


def test_unauthenticated_redirect(client):
    """Unauthenticated GET / redirects to /login."""
    r = client.get('/')
    assert r.status_code == 302
    assert '/login' in r.headers['Location']


def test_login_valid_credentials(client, app):
    """POST /login with valid creds redirects to /."""
    with app.app_context():
        from mqttui.models import User
        from mqttui.extensions import sa
        user = User.query.filter_by(username='admin').first()
        if not user:
            user = User(username='admin')
            user.set_password('testpass')
            sa.session.add(user)
            sa.session.commit()
    r = client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers['Location'] in ('/', 'http://localhost/')


def test_login_invalid_credentials(client, app):
    """POST /login with bad creds returns login page with error."""
    r = client.post('/login', data={'username': 'admin', 'password': 'wrong'})
    assert r.status_code == 200
    assert b'Invalid' in r.data or b'invalid' in r.data


def test_logout(auth_client):
    """GET /logout clears session and redirects."""
    r = auth_client.get('/logout', follow_redirects=False)
    assert r.status_code == 302
    assert '/login' in r.headers['Location']


def test_api_token_auth(client, api_token):
    """X-API-Key header authenticates API requests."""
    r = client.get('/api/v1/stats', headers={'X-API-Key': api_token})
    assert r.status_code == 200
    import json
    data = json.loads(r.data)
    assert data['status'] == 'success'


def test_api_token_invalid(client):
    """Invalid X-API-Key returns 401/redirect."""
    r = client.get('/api/v1/stats', headers={'X-API-Key': 'bad-token'})
    # Should redirect to login or return 401
    assert r.status_code in (302, 401)


def test_secret_key_guard():
    """App refuses to start with insecure SECRET_KEY in production."""
    import os
    old_env = os.environ.get('FLASK_ENV')
    os.environ['FLASK_ENV'] = 'production'
    try:
        from unittest.mock import patch
        import pytest
        with patch('mqttui.mqtt_client.init_mqtt'):
            from mqttui.app import create_app
            with pytest.raises(RuntimeError, match="SECRET_KEY"):
                create_app({'SECRET_KEY': 'dev', 'DB_ENABLED': False, 'SQLALCHEMY_DATABASE_URI': 'sqlite://'})
    finally:
        if old_env is None:
            os.environ.pop('FLASK_ENV', None)
        else:
            os.environ['FLASK_ENV'] = old_env


def test_token_get(auth_client, app):
    """GET /api/v1/auth/token returns current token."""
    r = auth_client.get('/api/v1/auth/token')
    assert r.status_code == 200
    import json
    data = json.loads(r.data)
    assert data['status'] == 'success'
    assert 'api_token' in data['data']


def test_token_regenerate(auth_client, app):
    """POST /api/v1/auth/token regenerates token."""
    r = auth_client.post('/api/v1/auth/token')
    assert r.status_code == 200
    import json
    data = json.loads(r.data)
    assert data['status'] == 'success'
    assert data['data']['api_token'] is not None


def test_token_revoke(auth_client, app):
    """DELETE /api/v1/auth/token revokes token."""
    r = auth_client.delete('/api/v1/auth/token')
    assert r.status_code == 200
    import json
    data = json.loads(r.data)
    assert data['data']['message'] == 'API token revoked'
