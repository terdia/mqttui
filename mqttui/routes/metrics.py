"""Prometheus-compatible /metrics endpoint and metric definitions.

Exposes counters, gauges, and histograms for MQTT, rules, webhooks,
and WebSocket activity. Designed for unauthenticated Prometheus scraping.
"""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Blueprint, Response

metrics_bp = Blueprint('metrics', __name__)

# Counters
MQTT_MESSAGES = Counter('mqtt_messages_total', 'Total MQTT messages received', ['topic'])
RULE_FIRINGS = Counter('rule_firings_total', 'Total rule firings', ['rule_id'])
WEBHOOK_DELIVERIES = Counter('webhook_deliveries_total', 'Total webhook deliveries', ['status'])
ALERTS = Counter('alerts_total', 'Total alerts triggered')

# Gauges
MQTT_CONNECTED = Gauge('mqtt_connected', 'MQTT broker connection status (0/1)')
ACTIVE_RULES = Gauge('active_rules', 'Number of active rules')
WEBSOCKET_CLIENTS = Gauge('websocket_clients', 'Number of connected WebSocket clients')

# Histograms
WEBHOOK_DURATION = Histogram(
    'webhook_delivery_duration_seconds',
    'Webhook delivery duration',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


@metrics_bp.route('/metrics')
def prometheus_metrics():
    """Serve Prometheus metrics. No authentication required for scraping."""
    import mqttui.state as state
    MQTT_CONNECTED.set(1 if state.connection_count > 0 else 0)
    WEBSOCKET_CLIENTS.set(state.active_websockets)
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# Signal subscribers for incrementing counters

def _on_message_for_metrics(sender, **kwargs):
    """Increment mqtt_messages_total counter on MQTT message received."""
    MQTT_MESSAGES.labels(topic=kwargs.get('topic', 'unknown')).inc()


def _on_rule_fired_for_metrics(sender, **kwargs):
    """Increment rule_firings_total counter on rule fired."""
    RULE_FIRINGS.labels(rule_id=str(kwargs.get('rule_id', 'unknown'))).inc()


def _on_alert_for_metrics(sender, **kwargs):
    """Increment alerts_total counter on alert triggered."""
    ALERTS.inc()
