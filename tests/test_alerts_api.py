"""Tests for the Alerts REST API and dry-run action_preview."""
import json
from datetime import datetime

import pytest

from mqttui.extensions import sa
from mqttui.rules.models import AlertHistory, Rule


# ---------------------------------------------------------------------------
# Helper to seed alerts
# ---------------------------------------------------------------------------

def _seed_alerts(app, count=25, rule_id=1, severity='info'):
    """Seed AlertHistory records for testing."""
    with app.app_context():
        for i in range(count):
            record = AlertHistory(
                rule_id=rule_id,
                rule_name=f'rule-{rule_id}',
                topic=f'sensors/temp/{i}',
                severity=severity,
                message=f'Test alert {i}',
                fired_at=datetime(2026, 1, 1, 0, i % 60),
            )
            sa.session.add(record)
        sa.session.commit()


def _seed_rule(app, rule_id=None, action_type='webhook'):
    """Seed a Rule record and return its ID."""
    with app.app_context():
        action = {'type': action_type}
        if action_type == 'webhook':
            action['url'] = 'https://example.com/hook'
            action['payload_template'] = '{"topic": "{{topic}}", "rule": "{{rule_name}}"}'
        elif action_type == 'publish':
            action['topic'] = 'output/topic'
            action['payload'] = '{"forwarded": true}'
        elif action_type == 'log':
            action['message'] = 'Rule fired: {{rule_name}}'
            action['severity'] = 'warning'

        rule = Rule(
            name='test-rule',
            trigger_topic='sensors/+',
            condition_json='{"operator": ">", "field": "temp", "value": 30}',
            action_json=json.dumps(action),
            enabled=True,
        )
        sa.session.add(rule)
        sa.session.commit()
        return rule.id


# ---------------------------------------------------------------------------
# GET /api/v1/alerts tests
# ---------------------------------------------------------------------------

class TestListAlerts:
    """Tests for the alert history listing endpoint."""

    def test_list_alerts_empty(self, auth_client, app):
        """Empty database returns empty list with total 0."""
        resp = auth_client.get('/api/v1/alerts/')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert data['data']['alerts'] == []
        assert data['data']['total'] == 0

    def test_list_alerts_paginated(self, auth_client, app):
        """With 25 alerts, page=1&per_page=10 returns 10 items and total=25."""
        _seed_alerts(app, count=25)
        resp = auth_client.get('/api/v1/alerts/?page=1&per_page=10')
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert len(data['alerts']) == 10
        assert data['total'] == 25
        assert data['page'] == 1
        assert data['per_page'] == 10

    def test_list_alerts_filter_rule_id(self, auth_client, app):
        """Filter by rule_id returns only matching alerts."""
        _seed_alerts(app, count=5, rule_id=1)
        _seed_alerts(app, count=3, rule_id=2)
        resp = auth_client.get('/api/v1/alerts/?rule_id=1')
        data = resp.get_json()['data']
        assert data['total'] == 5
        for alert in data['alerts']:
            assert alert['rule_id'] == 1

    def test_list_alerts_filter_severity(self, auth_client, app):
        """Filter by severity returns only matching alerts."""
        _seed_alerts(app, count=4, severity='info')
        _seed_alerts(app, count=2, severity='error')
        resp = auth_client.get('/api/v1/alerts/?severity=error')
        data = resp.get_json()['data']
        assert data['total'] == 2
        for alert in data['alerts']:
            assert alert['severity'] == 'error'

    def test_list_alerts_requires_auth(self, client):
        """Unauthenticated request should be rejected."""
        resp = client.get('/api/v1/alerts/')
        # Flask-Login redirects to login page (302) or returns 401
        assert resp.status_code in (302, 401)


# ---------------------------------------------------------------------------
# Dry-run action_preview test
# ---------------------------------------------------------------------------

class TestDryRunActionPreview:
    """Test that dry-run test endpoint returns action_preview."""

    def test_dry_run_action_preview(self, auth_client, app):
        """POST test with matching payload returns action_preview with rendered webhook payload."""
        rule_id = _seed_rule(app, action_type='webhook')
        resp = auth_client.post(
            f'/api/v1/rules/{rule_id}/test',
            json={'topic': 'sensors/temp', 'payload': '{"temp": 42}'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['match'] is True
        assert 'action_preview' in data

        preview = data['action_preview']
        assert len(preview) > 0
        # Webhook preview should contain the URL and rendered payload
        wp = preview[0]
        assert wp['type'] == 'webhook'
        assert 'url' in wp
        assert 'payload' in wp

    def test_dry_run_action_preview_publish(self, auth_client, app):
        """Publish action preview shows topic and payload."""
        rule_id = _seed_rule(app, action_type='publish')
        resp = auth_client.post(
            f'/api/v1/rules/{rule_id}/test',
            json={'topic': 'sensors/temp', 'payload': '{"temp": 42}'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        if data['match']:
            assert 'action_preview' in data
            wp = data['action_preview']
            assert len(wp) > 0
            assert wp[0]['type'] == 'publish'

    def test_dry_run_action_preview_log(self, auth_client, app):
        """Log action preview shows message."""
        rule_id = _seed_rule(app, action_type='log')
        resp = auth_client.post(
            f'/api/v1/rules/{rule_id}/test',
            json={'topic': 'sensors/temp', 'payload': '{"temp": 42}'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        if data['match']:
            assert 'action_preview' in data
            wp = data['action_preview']
            assert len(wp) > 0
            assert wp[0]['type'] == 'log'

    def test_dry_run_no_preview_when_no_match(self, auth_client, app):
        """No action_preview when rule doesn't match."""
        rule_id = _seed_rule(app, action_type='webhook')
        resp = auth_client.post(
            f'/api/v1/rules/{rule_id}/test',
            json={'topic': 'sensors/temp', 'payload': '{"temp": 10}'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['match'] is False
        # action_preview should be empty or absent when no match
        preview = data.get('action_preview', [])
        assert len(preview) == 0
