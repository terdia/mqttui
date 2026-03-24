from mqttui.extensions import sa
from datetime import datetime
import json


class Rule(sa.Model):
    __tablename__ = 'rules'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(200), nullable=False)
    description = sa.Column(sa.Text, default='')
    trigger_topic = sa.Column(sa.String(500), nullable=False)
    condition_json = sa.Column(sa.Text, nullable=False, default='{}')
    action_json = sa.Column(sa.Text, nullable=False)
    enabled = sa.Column(sa.Boolean, default=True)
    rate_limit_per_min = sa.Column(sa.Integer, default=10)
    schedule_cron = sa.Column(sa.String(100), nullable=True)
    last_fired = sa.Column(sa.DateTime, nullable=True)
    fire_count = sa.Column(sa.Integer, default=0)
    created_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime, server_default=sa.func.now(), onupdate=datetime.utcnow)

    @property
    def action(self):
        try:
            return json.loads(self.action_json) if self.action_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def condition(self):
        try:
            return json.loads(self.condition_json) if self.condition_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'trigger_topic': self.trigger_topic,
            'condition': self.condition,
            'action': self.action,
            'enabled': self.enabled,
            'rate_limit_per_min': self.rate_limit_per_min,
            'schedule_cron': self.schedule_cron,
            'last_fired': self.last_fired.isoformat() if self.last_fired else None,
            'fire_count': self.fire_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class AlertHistory(sa.Model):
    __tablename__ = 'alert_history'

    id = sa.Column(sa.Integer, primary_key=True)
    rule_id = sa.Column(sa.Integer, nullable=True)
    rule_name = sa.Column(sa.String(200))
    topic = sa.Column(sa.String(500))
    severity = sa.Column(sa.String(20), default='info')
    message = sa.Column(sa.Text)
    fired_at = sa.Column(sa.DateTime, server_default=sa.func.now())
    # Webhook delivery fields (Phase 4)
    webhook_url = sa.Column(sa.String(1000), nullable=True)
    http_status = sa.Column(sa.Integer, nullable=True)
    retry_count = sa.Column(sa.Integer, default=0)
    error_detail = sa.Column(sa.Text, nullable=True)
    suppressed_count = sa.Column(sa.Integer, default=0)
    cooldown_until = sa.Column(sa.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'topic': self.topic,
            'severity': self.severity,
            'message': self.message,
            'fired_at': self.fired_at.isoformat() if self.fired_at else None,
            'webhook_url': self.webhook_url,
            'http_status': self.http_status,
            'retry_count': self.retry_count,
            'error_detail': self.error_detail,
            'suppressed_count': self.suppressed_count,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
        }
