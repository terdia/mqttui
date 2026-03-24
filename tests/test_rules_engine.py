"""Tests for the RuleEngine class -- cache, matcher, rate limiter, loop prevention."""
import json
import time
from collections import deque
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest

from mqttui.events import mqtt_message_received, rule_fired, rule_changed


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


@pytest.fixture
def engine(app):
    """Create a RuleEngine with mocked scheduler, disconnect after test."""
    from mqttui.rules.engine import RuleEngine
    eng = RuleEngine(app)
    # Prevent real GeventScheduler from starting in tests
    eng._scheduler = MagicMock()
    eng._scheduler.get_jobs.return_value = []
    yield eng
    eng.disconnect()


@pytest.fixture
def fire_log():
    """Collect rule_fired signals. Auto-disconnects after test."""
    fired = []

    def _handler(sender, **kw):
        fired.append(kw)

    rule_fired.connect(_handler)
    yield fired
    rule_fired.disconnect(_handler)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoopPrevention:
    """Messages with __source: mqttui-automation must be skipped."""

    def test_loop_prevention_skips_automation_messages(self, app, engine, fire_log):
        _create_rule(app, trigger_topic='sensors/#')
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {
                '__source': 'mqttui-automation',
                'temp': 35,
            })

        assert len(fire_log) == 0, "Rule must not fire on automation messages"


class TestTopicMatching:
    """Rules should match based on MQTT wildcard patterns."""

    def test_wildcard_topic_matching(self, app, engine, fire_log):
        _create_rule(app, trigger_topic='sensors/+/temp',
                     action_json=json.dumps({'type': 'log'}))
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 25})

        assert len(fire_log) == 1
        assert fire_log[0]['topic'] == 'sensors/outdoor/temp'

    def test_non_matching_topic(self, app, engine, fire_log):
        _create_rule(app, trigger_topic='sensors/+/temp')
        engine.connect()

        with app.app_context():
            _send_message('actuators/fan/speed', {'speed': 50})

        assert len(fire_log) == 0


class TestConditionEvaluation:
    """Rules should evaluate conditions before firing."""

    def test_matching_condition_fires(self, app, engine, fire_log):
        _create_rule(
            app,
            trigger_topic='sensors/+/temp',
            condition_json=json.dumps({'path': 'temp', 'op': 'gt', 'value': 30}),
            action_json=json.dumps({'type': 'log'}),
        )
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 35})

        assert len(fire_log) == 1

    def test_non_matching_condition_does_not_fire(self, app, engine, fire_log):
        _create_rule(
            app,
            trigger_topic='sensors/+/temp',
            condition_json=json.dumps({'path': 'temp', 'op': 'gt', 'value': 30}),
        )
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 20})

        assert len(fire_log) == 0


class TestDisabledRule:
    """Disabled rules must not be in cache and never fire."""

    def test_disabled_rule_not_in_cache(self, app, engine, fire_log):
        _create_rule(app, trigger_topic='sensors/#', enabled=False)
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 35})

        assert len(fire_log) == 0


class TestPerRuleRateLimit:
    """Per-rule rate limit blocks excessive firings within the window."""

    def test_rate_limit_blocks_excess(self, app, engine, fire_log):
        _create_rule(
            app,
            trigger_topic='sensors/#',
            rate_limit_per_min=2,
            action_json=json.dumps({'type': 'log'}),
        )
        engine.connect()

        with app.app_context():
            for _ in range(3):
                _send_message('sensors/outdoor/temp', {'temp': 35})

        assert len(fire_log) == 2, "Third firing should be rate-limited"


class TestGlobalCircuitBreaker:
    """Global circuit breaker blocks all firings after threshold."""

    def test_global_limit_blocks_excess(self, app, engine, fire_log):
        # Create rules that will all fire
        for i in range(5):
            _create_rule(
                app,
                name=f'Rule {i}',
                trigger_topic='sensors/#',
                rate_limit_per_min=100,
                action_json=json.dumps({'type': 'log'}),
            )

        engine._GLOBAL_LIMIT = 3  # Low limit for testing
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 35})

        # 5 rules match but global limit is 3
        assert len(fire_log) == 3, "Global circuit breaker should limit to 3 firings"


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

    def test_signal_emitted_on_fire(self, app, engine, fire_log):
        rule_id = _create_rule(
            app,
            name='Signal Test Rule',
            trigger_topic='sensors/#',
            action_json=json.dumps({'type': 'log'}),
        )
        engine.connect()

        with app.app_context():
            _send_message('sensors/outdoor/temp', {'temp': 25})

        assert len(fire_log) == 1
        sig = fire_log[0]
        assert sig['rule_id'] == rule_id
        assert sig['rule_name'] == 'Signal Test Rule'
        assert sig['topic'] == 'sensors/outdoor/temp'


# ---------------------------------------------------------------------------
# Scheduler & Hot-Reload Tests (Plan 03-04)
# ---------------------------------------------------------------------------

class TestHotReload:
    """rule_changed signal should trigger cache reload."""

    def test_hot_reload_on_rule_changed(self, app, engine):
        """Cache updates when rule_changed signal fires."""
        rule_id = _create_rule(app, trigger_topic='sensors/#')
        engine.connect()

        # Rule should be in cache
        assert rule_id in engine._rules

        # Delete the rule from DB
        with app.app_context():
            from mqttui.rules.models import Rule
            from mqttui.extensions import sa
            rule = sa.session.get(Rule, rule_id)
            sa.session.delete(rule)
            sa.session.commit()

        # Fire rule_changed signal -- should trigger cache reload
        rule_changed.send('test', action='deleted', rule_id=rule_id)

        # Rule should no longer be in cache
        assert rule_id not in engine._rules


class TestCronScheduleSync:
    """sync_scheduled_jobs should manage APScheduler jobs for cron rules."""

    def test_cron_schedule_sync(self, app, engine):
        """A rule with schedule_cron gets a scheduler job with replace_existing."""
        rule_id = _create_rule(
            app,
            trigger_topic='sensors/#',
            schedule_cron='*/5 * * * *',
        )
        engine.connect()

        # Verify add_job was called with correct arguments
        engine._scheduler.add_job.assert_called()
        call_kwargs = engine._scheduler.add_job.call_args
        assert call_kwargs[1]['replace_existing'] is True
        assert call_kwargs[1]['id'] == f'rule_{rule_id}'

    def test_removed_rule_job_cleaned_up(self, app, engine):
        """Jobs for deleted rules are removed from scheduler."""
        # Simulate a stale job from a previously deleted rule
        stale_job = MagicMock()
        stale_job.id = 'rule_999'
        engine._scheduler.get_jobs.return_value = [stale_job]

        # Create a rule without cron (no new job expected)
        _create_rule(app, trigger_topic='sensors/#')
        engine.connect()

        # Stale job should be removed
        engine._scheduler.remove_job.assert_any_call('rule_999')


class TestFireScheduledRule:
    """fire_scheduled_rule should execute the action and log to AlertHistory."""

    def test_fire_scheduled_rule(self, app, engine):
        """Calling fire_scheduled_rule creates an AlertHistory record."""
        from mqttui.rules.models import AlertHistory

        rule_id = _create_rule(
            app,
            name='Heartbeat Rule',
            trigger_topic='__scheduled__',
            action_json=json.dumps({'type': 'log', 'message': 'heartbeat'}),
        )
        engine.connect()

        with app.app_context():
            engine.fire_scheduled_rule(rule_id)

            alerts = AlertHistory.query.all()
            assert len(alerts) == 1
            assert alerts[0].message == 'heartbeat'
            assert alerts[0].rule_name == 'Heartbeat Rule'

    def test_fire_scheduled_rule_missing_id(self, app, engine):
        """fire_scheduled_rule silently returns for non-existent rule."""
        engine.connect()
        with app.app_context():
            # Should not raise
            engine.fire_scheduled_rule(99999)


class TestAppCreatesRuleEngine:
    """create_app should register the rules blueprint."""

    def test_rules_blueprint_registered(self, app):
        """The rules blueprint should be in app.blueprints."""
        assert 'rules' in app.blueprints
