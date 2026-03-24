"""Tests for the RuleEngine class -- cache, matcher, rate limiter, loop prevention."""
import json
import time
from collections import deque
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest

from mqttui.events import mqtt_message_received, rule_fired


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_rule(app, **overrides):
    """Create a Rule record inside app context and return its id."""
    with app.app_context():
        from mqttui.rules.models import Rule
        from mqttui.extensions import sa

        defaults = {
            'name': 'Test Rule',
            'trigger_topic': 'sensors/+/temp',
            'condition_json': '{}',
            'action_json': json.dumps({'type': 'log'}),
            'enabled': True,
            'rate_limit_per_min': 10,
        }
        defaults.update(overrides)
        rule = Rule(**defaults)
        sa.session.add(rule)
        sa.session.commit()
        return rule.id


def _send_message(topic, payload_dict):
    """Fire mqtt_message_received signal with given topic and JSON payload."""
    mqtt_message_received.send(
        'mqtt_client',
        topic=topic,
        payload=json.dumps(payload_dict),
        timestamp=datetime.utcnow(),
        qos=0,
        retain=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoopPrevention:
    """Messages with __source: mqttui-automation must be skipped."""

    def test_loop_prevention_skips_automation_messages(self, app):
        from mqttui.rules.engine import RuleEngine

        _create_rule(app, trigger_topic='sensors/#')
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {
                '__source': 'mqttui-automation',
                'temp': 35,
            })

        assert len(fired) == 0, "Rule must not fire on automation messages"


class TestTopicMatching:
    """Rules should match based on MQTT wildcard patterns."""

    def test_wildcard_topic_matching(self, app):
        from mqttui.rules.engine import RuleEngine

        _create_rule(app, trigger_topic='sensors/+/temp',
                     action_json=json.dumps({'type': 'log'}))
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 25})

        assert len(fired) == 1
        assert fired[0]['topic'] == 'sensors/outdoor/temp'

    def test_non_matching_topic(self, app):
        from mqttui.rules.engine import RuleEngine

        _create_rule(app, trigger_topic='sensors/+/temp')
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('actuators/fan/speed', {'speed': 50})

        assert len(fired) == 0


class TestConditionEvaluation:
    """Rules should evaluate conditions before firing."""

    def test_matching_condition_fires(self, app):
        from mqttui.rules.engine import RuleEngine

        _create_rule(
            app,
            trigger_topic='sensors/+/temp',
            condition_json=json.dumps({'path': 'temp', 'op': 'gt', 'value': 30}),
            action_json=json.dumps({'type': 'log'}),
        )
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 35})

        assert len(fired) == 1

    def test_non_matching_condition_does_not_fire(self, app):
        from mqttui.rules.engine import RuleEngine

        _create_rule(
            app,
            trigger_topic='sensors/+/temp',
            condition_json=json.dumps({'path': 'temp', 'op': 'gt', 'value': 30}),
        )
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 20})

        assert len(fired) == 0


class TestDisabledRule:
    """Disabled rules must not be in cache and never fire."""

    def test_disabled_rule_not_in_cache(self, app):
        from mqttui.rules.engine import RuleEngine

        _create_rule(app, trigger_topic='sensors/#', enabled=False)
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 35})

        assert len(fired) == 0


class TestPerRuleRateLimit:
    """Per-rule rate limit blocks excessive firings within the window."""

    def test_rate_limit_blocks_excess(self, app):
        from mqttui.rules.engine import RuleEngine

        rule_id = _create_rule(
            app,
            trigger_topic='sensors/#',
            rate_limit_per_min=2,
            action_json=json.dumps({'type': 'log'}),
        )
        engine = RuleEngine(app)
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            for _ in range(3):
                _send_message('sensors/outdoor/temp', {'temp': 35})

        assert len(fired) == 2, "Third firing should be rate-limited"


class TestGlobalCircuitBreaker:
    """Global circuit breaker blocks all firings after threshold."""

    def test_global_limit_blocks_excess(self, app):
        from mqttui.rules.engine import RuleEngine

        # Create rules that will all fire
        for i in range(5):
            _create_rule(
                app,
                name=f'Rule {i}',
                trigger_topic='sensors/#',
                rate_limit_per_min=100,
                action_json=json.dumps({'type': 'log'}),
            )

        engine = RuleEngine(app)
        engine._GLOBAL_LIMIT = 3  # Low limit for testing
        engine.connect()

        fired = []
        rule_fired.connect(lambda sender, **kw: fired.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 35})

        # 5 rules match but global limit is 3
        assert len(fired) == 3, "Global circuit breaker should limit to 3 firings"


class TestPublishActionSourceMarker:
    """Publish action must inject __source marker."""

    def test_publish_injects_source_marker(self, app):
        from mqttui.rules.actions import execute_action

        with app.app_context():
            with patch('mqttui.mqtt_client.publish') as mock_pub:
                result = execute_action(
                    {'type': 'publish', 'topic': 'output/fan', 'payload': '{"speed": 100}'},
                    {'rule_id': 1, 'rule_name': 'Test', 'topic': 'sensors/temp', 'payload': '{}'},
                )

                assert result['success'] is True
                call_args = mock_pub.call_args
                published_payload = json.loads(call_args[0][1])
                assert published_payload['__source'] == 'mqttui-automation'
                assert published_payload['speed'] == 100


class TestLogActionCreatesAlert:
    """Log action must create an AlertHistory record."""

    def test_log_creates_alert_history(self, app):
        from mqttui.rules.actions import execute_action
        from mqttui.rules.models import AlertHistory

        with app.app_context():
            result = execute_action(
                {'type': 'log', 'severity': 'warning', 'message': 'Temperature high'},
                {'rule_id': 1, 'rule_name': 'Temp Alert', 'topic': 'sensors/temp', 'payload': '{}'},
            )

            assert result['success'] is True
            alerts = AlertHistory.query.all()
            assert len(alerts) == 1
            assert alerts[0].severity == 'warning'
            assert alerts[0].rule_name == 'Temp Alert'


class TestRuleFiredSignal:
    """rule_fired signal must be emitted with correct kwargs."""

    def test_signal_emitted_on_fire(self, app):
        from mqttui.rules.engine import RuleEngine

        rule_id = _create_rule(
            app,
            name='Signal Test Rule',
            trigger_topic='sensors/#',
            action_json=json.dumps({'type': 'log'}),
        )
        engine = RuleEngine(app)
        engine.connect()

        signals_received = []
        rule_fired.connect(lambda sender, **kw: signals_received.append(kw))

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 25})

        assert len(signals_received) == 1
        sig = signals_received[0]
        assert sig['rule_id'] == rule_id
        assert sig['rule_name'] == 'Signal Test Rule'
        assert sig['topic'] == 'sensors/outdoor/temp'
