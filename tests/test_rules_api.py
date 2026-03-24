"""Integration tests for rules REST API endpoints."""
import json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_rule(auth_client, **overrides):
    """POST a new rule with sensible defaults. Returns response object."""
    data = {
        "name": "Test Rule",
        "trigger_topic": "sensors/+/temp",
        "condition": {"path": "temp", "op": "gt", "value": 30},
        "action": {"type": "publish", "topic": "alerts/temp", "payload": '{"alert": true}'},
    }
    data.update(overrides)
    return auth_client.post('/api/v1/rules/', json=data)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_rules_empty(auth_client):
    """GET /api/v1/rules/ returns empty list when no rules exist."""
    r = auth_client.get('/api/v1/rules/')
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'success'
    assert body['data']['rules'] == []


def test_list_rules_with_data(auth_client):
    """GET /api/v1/rules/ returns created rules."""
    _create_rule(auth_client, name="Rule A")
    _create_rule(auth_client, name="Rule B")
    r = auth_client.get('/api/v1/rules/')
    assert r.status_code == 200
    rules = r.get_json()['data']['rules']
    assert len(rules) == 2


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_rule(auth_client):
    """POST /api/v1/rules/ with valid data returns 201 with rule data."""
    r = _create_rule(auth_client)
    assert r.status_code == 201
    body = r.get_json()
    assert body['status'] == 'success'
    rule = body['data']
    assert rule['name'] == 'Test Rule'
    assert rule['trigger_topic'] == 'sensors/+/temp'
    assert rule['enabled'] is True
    assert rule['id'] is not None
    assert rule['condition'] == {"path": "temp", "op": "gt", "value": 30}
    assert rule['action']['type'] == 'publish'


def test_create_rule_missing_name(auth_client):
    """POST without name returns 400 VALIDATION_ERROR."""
    r = auth_client.post('/api/v1/rules/', json={
        "trigger_topic": "test/+",
        "action": {"type": "publish", "topic": "out", "payload": "x"},
    })
    assert r.status_code == 400
    body = r.get_json()
    assert body['status'] == 'error'
    assert body['error']['code'] == 'VALIDATION_ERROR'


def test_create_rule_missing_action(auth_client):
    """POST without action returns 400 VALIDATION_ERROR."""
    r = auth_client.post('/api/v1/rules/', json={
        "name": "No Action",
        "trigger_topic": "test/+",
    })
    assert r.status_code == 400
    body = r.get_json()
    assert body['status'] == 'error'
    assert body['error']['code'] == 'VALIDATION_ERROR'


def test_create_rule_missing_trigger_topic(auth_client):
    """POST without trigger_topic returns 400 VALIDATION_ERROR."""
    r = auth_client.post('/api/v1/rules/', json={
        "name": "No Topic",
        "action": {"type": "publish", "topic": "out", "payload": "x"},
    })
    assert r.status_code == 400
    body = r.get_json()
    assert body['error']['code'] == 'VALIDATION_ERROR'


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

def test_get_rule(auth_client):
    """GET /api/v1/rules/<id> returns rule."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']
    r = auth_client.get(f'/api/v1/rules/{rule_id}')
    assert r.status_code == 200
    assert r.get_json()['data']['id'] == rule_id


def test_get_rule_not_found(auth_client):
    """GET /api/v1/rules/999 returns 404 NOT_FOUND."""
    r = auth_client.get('/api/v1/rules/999')
    assert r.status_code == 404
    body = r.get_json()
    assert body['error']['code'] == 'NOT_FOUND'


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_rule(auth_client):
    """PUT /api/v1/rules/<id> updates specified fields only."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.put(f'/api/v1/rules/{rule_id}', json={
        "name": "Updated Rule",
        "description": "Now with description",
    })
    assert r.status_code == 200
    rule = r.get_json()['data']
    assert rule['name'] == 'Updated Rule'
    assert rule['description'] == 'Now with description'
    # Unchanged fields preserved
    assert rule['trigger_topic'] == 'sensors/+/temp'


def test_update_rule_not_found(auth_client):
    """PUT /api/v1/rules/999 returns 404."""
    r = auth_client.put('/api/v1/rules/999', json={"name": "x"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_rule(auth_client):
    """DELETE /api/v1/rules/<id> returns 200, subsequent GET returns 404."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.delete(f'/api/v1/rules/{rule_id}')
    assert r.status_code == 200
    assert r.get_json()['status'] == 'success'

    # Verify deleted
    r2 = auth_client.get(f'/api/v1/rules/{rule_id}')
    assert r2.status_code == 404


def test_delete_rule_not_found(auth_client):
    """DELETE /api/v1/rules/999 returns 404."""
    r = auth_client.delete('/api/v1/rules/999')
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------

def test_enable_disable(auth_client):
    """POST enable sets enabled=True, POST disable sets enabled=False."""
    cr = _create_rule(auth_client, enabled=True)
    rule_id = cr.get_json()['data']['id']

    # Disable
    r = auth_client.post(f'/api/v1/rules/{rule_id}/disable')
    assert r.status_code == 200
    assert r.get_json()['data']['enabled'] is False

    # Enable
    r = auth_client.post(f'/api/v1/rules/{rule_id}/enable')
    assert r.status_code == 200
    assert r.get_json()['data']['enabled'] is True


def test_enable_not_found(auth_client):
    """POST /api/v1/rules/999/enable returns 404."""
    r = auth_client.post('/api/v1/rules/999/enable')
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Dry-run / Test
# ---------------------------------------------------------------------------

def test_dry_run_match(auth_client):
    """POST /api/v1/rules/<id>/test with matching topic+payload returns match=True."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.post(f'/api/v1/rules/{rule_id}/test', json={
        "topic": "sensors/living-room/temp",
        "payload": '{"temp": 35}',
    })
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['match'] is True
    assert body['topic_match'] is True
    assert body['condition_match'] is True
    assert len(body['actions']) == 1
    assert body['actions'][0]['type'] == 'publish'


def test_dry_run_no_match_condition(auth_client):
    """POST /test with non-matching payload returns match=False."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.post(f'/api/v1/rules/{rule_id}/test', json={
        "topic": "sensors/living-room/temp",
        "payload": '{"temp": 20}',
    })
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['match'] is False
    assert body['topic_match'] is True
    assert body['condition_match'] is False
    assert body['actions'] == []


def test_dry_run_no_match_topic(auth_client):
    """POST /test with non-matching topic returns match=False."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.post(f'/api/v1/rules/{rule_id}/test', json={
        "topic": "other/topic",
        "payload": '{"temp": 35}',
    })
    assert r.status_code == 200
    body = r.get_json()['data']
    assert body['match'] is False
    assert body['topic_match'] is False


def test_dry_run_dict_payload(auth_client):
    """POST /test with dict payload (not string) also works."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.post(f'/api/v1/rules/{rule_id}/test', json={
        "topic": "sensors/bedroom/temp",
        "payload": {"temp": 40},
    })
    assert r.status_code == 200
    assert r.get_json()['data']['match'] is True


def test_dry_run_missing_topic(auth_client):
    """POST /test without topic returns 400."""
    cr = _create_rule(auth_client)
    rule_id = cr.get_json()['data']['id']

    r = auth_client.post(f'/api/v1/rules/{rule_id}/test', json={
        "payload": '{"temp": 35}',
    })
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_unauthenticated_access(client):
    """GET /api/v1/rules/ without auth returns 401 or redirect to login."""
    r = client.get('/api/v1/rules/')
    # Flask-Login redirects to /login (302) or returns 401
    assert r.status_code in (302, 401)
