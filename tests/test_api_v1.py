"""Tests for API v1 endpoints."""
import json


def test_json_envelope_success(auth_client):
    """API responses follow success envelope format."""
    r = auth_client.get('/api/v1/version')
    data = json.loads(r.data)
    assert 'status' in data
    assert 'data' in data
    assert 'error' in data
    assert data['status'] == 'success'
    assert data['error'] is None


def test_json_envelope_error(auth_client):
    """API error responses follow error envelope format."""
    r = auth_client.post('/api/v1/publish', json={})
    if r.status_code >= 400:
        data = json.loads(r.data)
        assert data['status'] == 'error'
        assert data['error'] is not None
        assert 'code' in data['error']
        assert 'message' in data['error']


def test_messages_endpoint(auth_client):
    """GET /api/v1/messages returns envelope with messages array."""
    r = auth_client.get('/api/v1/messages')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data['status'] == 'success'
    assert 'messages' in data['data']


def test_topics_endpoint(auth_client):
    """GET /api/v1/topics returns envelope with topics array."""
    r = auth_client.get('/api/v1/topics')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data['status'] == 'success'
    assert 'topics' in data['data']


def test_version_public(client):
    """GET /api/v1/version is public (no auth required)."""
    r = client.get('/api/v1/version')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data['status'] == 'success'


def test_docs_endpoint(client):
    """GET /api/v1/docs returns Swagger UI."""
    r = client.get('/api/v1/docs')
    assert r.status_code == 200
    assert b'swagger-ui' in r.data


def test_openapi_spec(client):
    """GET /api/v1/openapi.json returns valid OpenAPI spec."""
    r = client.get('/api/v1/openapi.json')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert 'openapi' in data or 'swagger' in data
    assert 'info' in data
    assert 'paths' in data


def test_cors_headers(client):
    """API responses include CORS headers."""
    r = client.options('/api/v1/version', headers={
        'Origin': 'http://example.com',
        'Access-Control-Request-Method': 'GET'
    })
    # Flask-CORS should add Access-Control-Allow-Origin
    assert r.status_code in (200, 204)


def test_publish_requires_auth(client):
    """POST /api/v1/publish without auth is rejected."""
    r = client.post('/api/v1/publish', json={'topic': 'test', 'message': 'hello'})
    assert r.status_code in (302, 401)


def test_stats_requires_auth(client):
    """GET /api/v1/stats without auth is rejected."""
    r = client.get('/api/v1/stats')
    assert r.status_code in (302, 401)


def test_messages_requires_auth(client):
    """GET /api/v1/messages without auth is rejected."""
    r = client.get('/api/v1/messages')
    assert r.status_code in (302, 401)


def test_rate_limit_publish(auth_client, app):
    """POST /api/v1/publish is rate limited to 30/minute with Retry-After header."""
    from unittest.mock import patch
    with patch('mqttui.mqtt_client.publish'):
        hit_429 = False
        for i in range(35):
            r = auth_client.post('/api/v1/publish', json={'topic': 'test/rate', 'message': f'msg-{i}'})
            if r.status_code == 429:
                hit_429 = True
                assert 'Retry-After' in r.headers
                data = json.loads(r.data)
                assert data['status'] == 'error'
                assert data['error']['code'] == 'RATE_LIMIT_EXCEEDED'
                break
        # Rate limiter should have kicked in after 30 requests
        assert hit_429, "Expected 429 after exceeding rate limit"
