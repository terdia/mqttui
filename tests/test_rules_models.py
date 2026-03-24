"""Tests for Rule and AlertHistory models."""
import json
from datetime import datetime


def test_rule_model_columns(app):
    """Rule model has all required columns."""
    with app.app_context():
        from mqttui.rules.models import Rule
        cols = [c.name for c in Rule.__table__.columns]
        expected = [
            'id', 'name', 'description', 'trigger_topic',
            'condition_json', 'action_json', 'enabled',
            'rate_limit_per_min', 'schedule_cron', 'last_fired',
            'fire_count', 'created_at', 'updated_at',
        ]
        for col in expected:
            assert col in cols, f"Missing column: {col}"


def test_rule_tablename(app):
    """Rule model uses 'rules' table."""
    with app.app_context():
        from mqttui.rules.models import Rule
        assert Rule.__tablename__ == 'rules'


def test_rule_to_dict(app):
    """Rule.to_dict() returns dict with parsed JSON fields."""
    with app.app_context():
        from mqttui.rules.models import Rule
        from mqttui.extensions import sa

        rule = Rule(
            name='Test Rule',
            description='A test rule',
            trigger_topic='sensors/temp',
            condition_json=json.dumps({"path": "temp", "op": "gt", "value": 30}),
            action_json=json.dumps({"type": "log", "message": "Hot!"}),
            enabled=True,
            rate_limit_per_min=5,
        )
        sa.session.add(rule)
        sa.session.commit()

        d = rule.to_dict()
        assert d['name'] == 'Test Rule'
        assert d['trigger_topic'] == 'sensors/temp'
        assert d['condition'] == {"path": "temp", "op": "gt", "value": 30}
        assert d['action'] == {"type": "log", "message": "Hot!"}
        assert d['enabled'] is True
        assert d['rate_limit_per_min'] == 5
        assert d['fire_count'] == 0
        assert d['id'] is not None


def test_alert_history_model_columns(app):
    """AlertHistory model has all required columns."""
    with app.app_context():
        from mqttui.rules.models import AlertHistory
        cols = [c.name for c in AlertHistory.__table__.columns]
        expected = ['id', 'rule_id', 'rule_name', 'topic', 'severity', 'message', 'fired_at']
        for col in expected:
            assert col in cols, f"Missing column: {col}"


def test_alert_history_tablename(app):
    """AlertHistory model uses 'alert_history' table."""
    with app.app_context():
        from mqttui.rules.models import AlertHistory
        assert AlertHistory.__tablename__ == 'alert_history'


def test_alert_history_to_dict(app):
    """AlertHistory.to_dict() returns dict with ISO datetime."""
    with app.app_context():
        from mqttui.rules.models import AlertHistory
        from mqttui.extensions import sa

        ah = AlertHistory(
            rule_id=1,
            rule_name='Test Rule',
            topic='sensors/temp',
            severity='warning',
            message='Temperature too high',
        )
        sa.session.add(ah)
        sa.session.commit()

        d = ah.to_dict()
        assert d['rule_name'] == 'Test Rule'
        assert d['severity'] == 'warning'
        assert d['topic'] == 'sensors/temp'
        assert d['fired_at'] is not None
