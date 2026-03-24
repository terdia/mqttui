"""Tests for Phase 5 frontend: partials, Alpine.js, htmx, batch emitter."""
import pytest
from unittest.mock import MagicMock, patch


class TestPartialRoutes:
    """Test htmx partial template routes."""

    def test_rules_list_partial_returns_html(self, auth_client):
        resp = auth_client.get('/partials/rules')
        assert resp.status_code == 200
        assert b'rules-list' in resp.data

    def test_alerts_list_partial_returns_html(self, auth_client):
        resp = auth_client.get('/partials/alerts')
        assert resp.status_code == 200
        assert b'alerts-list' in resp.data

    def test_rule_form_partial_returns_html(self, auth_client):
        resp = auth_client.get('/partials/rules/form')
        assert resp.status_code == 200
        assert b'name' in resp.data

    def test_partials_require_auth(self, client):
        """Unauthenticated requests should redirect to login."""
        for url in ['/partials/rules', '/partials/alerts', '/partials/rules/form']:
            resp = client.get(url)
            assert resp.status_code in (302, 401), f"{url} should require auth"


class TestIndexTemplate:
    """Test main index template includes Alpine.js, htmx, and tabs."""

    def test_index_contains_alpine(self, auth_client):
        resp = auth_client.get('/')
        assert resp.status_code == 200
        assert b'alpinejs' in resp.data or b'alpine' in resp.data.lower()

    def test_index_contains_htmx(self, auth_client):
        resp = auth_client.get('/')
        assert b'htmx' in resp.data

    def test_index_contains_tabs(self, auth_client):
        resp = auth_client.get('/')
        html = resp.data.decode()
        assert 'Messages' in html
        assert 'Rules' in html
        assert 'Alerts' in html

    def test_index_contains_alpine_xdata(self, auth_client):
        resp = auth_client.get('/')
        assert b'x-data' in resp.data


class TestBatchEmitter:
    """Test server-side Socket.IO batch emitter."""

    def test_enqueue_adds_to_buffer(self):
        from mqttui.socketio_batch import BatchEmitter
        mock_sio = MagicMock()
        emitter = BatchEmitter(mock_sio, interval_ms=100)
        emitter.enqueue({'topic': 'test', 'payload': 'hello'})
        assert len(emitter._buffer) == 1

    def test_flush_emits_batch_and_clears(self):
        from mqttui.socketio_batch import BatchEmitter
        mock_sio = MagicMock()
        emitter = BatchEmitter(mock_sio, interval_ms=100)
        emitter.enqueue({'topic': 't1', 'payload': 'p1'})
        emitter.enqueue({'topic': 't2', 'payload': 'p2'})
        emitter._flush()
        mock_sio.emit.assert_called_once_with('mqtt_messages_batch', [
            {'topic': 't1', 'payload': 'p1'},
            {'topic': 't2', 'payload': 'p2'},
        ])
        assert len(emitter._buffer) == 0

    def test_flush_noop_when_empty(self):
        from mqttui.socketio_batch import BatchEmitter
        mock_sio = MagicMock()
        emitter = BatchEmitter(mock_sio, interval_ms=100)
        emitter._flush()
        mock_sio.emit.assert_not_called()
