"""Tests for webhook delivery system: SSRF validation, webhook execution, retry logic."""

import pytest
import socket
from unittest.mock import patch, MagicMock, call
from datetime import datetime


# ---------------------------------------------------------------------------
# SSRF Validator Tests
# ---------------------------------------------------------------------------

class TestSSRFValidator:
    """Test SSRF URL validation blocks private/reserved IPs."""

    def test_ssrf_blocks_private_10(self):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("http://10.0.0.1/hook")
        assert safe is False
        assert "private" in reason.lower() or "blocked" in reason.lower()

    def test_ssrf_blocks_private_172(self):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("http://172.16.0.1/hook")
        assert safe is False

    def test_ssrf_blocks_private_192(self):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("http://192.168.1.1/hook")
        assert safe is False

    def test_ssrf_blocks_localhost(self):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("http://127.0.0.1/hook")
        assert safe is False

    def test_ssrf_blocks_link_local(self):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("http://169.254.1.1/hook")
        assert safe is False

    @patch('socket.getaddrinfo', return_value=[
        (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('93.184.216.34', 443))
    ])
    def test_ssrf_allows_public(self, mock_dns):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("https://hooks.example.com/hook")
        assert safe is True

    def test_ssrf_blocks_ipv6_localhost(self):
        from mqttui.rules.ssrf import is_ssrf_safe
        safe, reason = is_ssrf_safe("http://[::1]/hook")
        assert safe is False


# ---------------------------------------------------------------------------
# Webhook Delivery Tests
# ---------------------------------------------------------------------------

class TestWebhookDelivery:
    """Test webhook HTTP delivery, retry logic, and AlertHistory integration."""

    @patch('httpx.post')
    def test_webhook_success(self, mock_post, app):
        """Successful webhook creates AlertHistory record with http_status=200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        from mqttui.rules.actions import _deliver_webhook

        with app.app_context():
            from mqttui.rules.models import AlertHistory
            from mqttui.extensions import sa

            result = _deliver_webhook(
                url="https://hooks.example.com/hook",
                payload_json={"topic": "test/topic", "payload": "hello"},
                rule_id=1,
                rule_name="Test Rule",
                topic="test/topic",
            )
            assert result["success"] is True

            record = AlertHistory.query.filter_by(rule_id=1).order_by(AlertHistory.id.desc()).first()
            assert record is not None
            assert record.http_status == 200
            assert record.webhook_url == "https://hooks.example.com/hook"

    @patch('httpx.post')
    def test_webhook_retry_on_5xx(self, mock_post, app):
        """5xx responses trigger up to 3 retries."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        from mqttui.rules.actions import _deliver_webhook

        with app.app_context():
            from mqttui.rules.models import AlertHistory

            result = _deliver_webhook(
                url="https://hooks.example.com/hook",
                payload_json={"topic": "test/topic"},
                rule_id=2,
                rule_name="Retry Rule",
                topic="test/topic",
                _sleep_fn=lambda x: None,  # Skip actual sleep in tests
            )
            assert result["success"] is False
            # 1 initial + 3 retries = 4 total calls
            assert mock_post.call_count == 4

            record = AlertHistory.query.filter_by(rule_id=2).order_by(AlertHistory.id.desc()).first()
            assert record is not None
            assert record.retry_count == 3
            assert record.http_status == 500

    @patch('httpx.post')
    def test_webhook_no_retry_on_4xx(self, mock_post, app):
        """4xx responses fail immediately without retry."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        from mqttui.rules.actions import _deliver_webhook

        with app.app_context():
            from mqttui.rules.models import AlertHistory

            result = _deliver_webhook(
                url="https://hooks.example.com/hook",
                payload_json={"topic": "test/topic"},
                rule_id=3,
                rule_name="NoRetry Rule",
                topic="test/topic",
            )
            assert result["success"] is False
            assert mock_post.call_count == 1

            record = AlertHistory.query.filter_by(rule_id=3).order_by(AlertHistory.id.desc()).first()
            assert record is not None
            assert record.retry_count == 0
            assert record.http_status == 400

    def test_webhook_payload_template(self, app):
        """Webhook with template substitutes {{topic}}, {{rule_name}} context values."""
        from mqttui.rules.actions import _build_webhook_payload

        context = {
            'rule_id': 1,
            'rule_name': 'Temp Alert',
            'topic': 'sensors/temp',
            'payload': '{"temp": 42}',
        }
        template = '{"alert": "{{rule_name}}", "on": "{{topic}}"}'
        result = _build_webhook_payload(template, context)
        assert result["alert"] == "Temp Alert"
        assert result["on"] == "sensors/temp"

    @patch('httpx.post')
    def test_webhook_runs_in_thread(self, mock_post, app):
        """Webhook delivery via execute_action returns immediately (async via thread pool)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        from mqttui.rules.actions import execute_action

        with app.app_context():
            action = {"type": "webhook", "url": "https://hooks.example.com/hook"}
            context = {
                "rule_id": 1,
                "rule_name": "Thread Rule",
                "topic": "test/topic",
                "payload": "hello",
            }
            result = execute_action(action, context)
            # Should return immediately with submission confirmation
            assert result["success"] is True
            assert "submitted" in result["detail"].lower() or "delivery" in result["detail"].lower()
