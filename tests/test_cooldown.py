"""Tests for CooldownTracker and webhook cooldown integration."""
import time
from unittest.mock import patch, MagicMock

import pytest

from mqttui.rules.cooldown import CooldownTracker, cooldown_tracker


# ---------------------------------------------------------------------------
# CooldownTracker unit tests
# ---------------------------------------------------------------------------

class TestCooldownTracker:
    """Tests for the per-rule in-memory cooldown tracker."""

    def test_cooldown_allows_first_alert(self):
        """First call for a rule_id should always be allowed."""
        tracker = CooldownTracker()
        assert tracker.check(rule_id=1) is True

    def test_cooldown_blocks_during_window(self):
        """Subsequent calls within the cooldown window should be blocked."""
        tracker = CooldownTracker()
        assert tracker.check(rule_id=1) is True
        assert tracker.check(rule_id=1) is False

    def test_cooldown_allows_after_expiry(self):
        """After cooldown expires, alert should be allowed again."""
        tracker = CooldownTracker(default_seconds=1)
        assert tracker.check(rule_id=1) is True

        # Mock time to advance past cooldown window
        with patch('mqttui.rules.cooldown.time') as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2
            assert tracker.check(rule_id=1) is True

    def test_cooldown_different_rules_independent(self):
        """Cooldown for one rule should not affect another."""
        tracker = CooldownTracker()
        assert tracker.check(rule_id=1) is True
        assert tracker.check(rule_id=2) is True
        # rule_id=1 still blocked
        assert tracker.check(rule_id=1) is False
        # rule_id=2 also blocked
        assert tracker.check(rule_id=2) is False

    def test_cooldown_custom_window(self):
        """CooldownTracker should respect custom default_seconds."""
        tracker = CooldownTracker(default_seconds=60)
        assert tracker.check(rule_id=1) is True

        # Even 50 seconds later, still blocked (60s window)
        with patch('mqttui.rules.cooldown.time') as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 50
            assert tracker.check(rule_id=1) is False

        # After 61 seconds, allowed again
        with patch('mqttui.rules.cooldown.time') as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 61
            assert tracker.check(rule_id=1) is True

    def test_cooldown_suppressed_count(self):
        """Suppressed count should track how many alerts were blocked."""
        tracker = CooldownTracker()
        assert tracker.check(rule_id=1) is True
        assert tracker.get_suppressed_count(rule_id=1) == 0

        # Suppress 3 alerts
        tracker.check(rule_id=1)
        tracker.check(rule_id=1)
        tracker.check(rule_id=1)
        assert tracker.get_suppressed_count(rule_id=1) == 3

    def test_cooldown_suppressed_count_resets_on_new_fire(self):
        """Suppressed count resets when a new alert is allowed."""
        tracker = CooldownTracker(default_seconds=1)
        assert tracker.check(rule_id=1) is True
        tracker.check(rule_id=1)  # suppressed
        tracker.check(rule_id=1)  # suppressed
        assert tracker.get_suppressed_count(rule_id=1) == 2

        # After cooldown expires, count resets
        with patch('mqttui.rules.cooldown.time') as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2
            assert tracker.check(rule_id=1) is True
        assert tracker.get_suppressed_count(rule_id=1) == 0


# ---------------------------------------------------------------------------
# Webhook cooldown integration test
# ---------------------------------------------------------------------------

class TestWebhookCooldownIntegration:
    """Test that _execute_webhook respects cooldown."""

    def test_webhook_skipped_during_cooldown(self, app):
        """Webhook should return cooldown detail when blocked."""
        from mqttui.rules.cooldown import cooldown_tracker as ct
        from mqttui.rules.actions import _execute_webhook

        with app.app_context():
            context = {
                'rule_id': 99,
                'rule_name': 'test-rule',
                'topic': 'sensors/temp',
                'payload': '{"temp": 42}',
            }
            action = {'type': 'webhook', 'url': 'https://example.com/hook'}

            # Reset the module-level tracker for clean test
            ct._last_fired.clear()
            ct._suppressed.clear()

            # First call -- allowed (submitted to thread pool)
            result1 = _execute_webhook(action, context)
            assert result1['success'] is True
            assert 'cooldown' not in result1['detail'].lower()

            # Second call -- blocked by cooldown
            result2 = _execute_webhook(action, context)
            assert result2['success'] is True
            assert 'cooldown' in result2['detail'].lower() or 'suppressed' in result2['detail'].lower()
