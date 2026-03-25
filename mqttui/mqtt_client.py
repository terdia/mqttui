"""MQTT client compatibility layer.

Delegates to BrokerManager for multi-broker support while keeping the
same publish() API that rules engine and other modules use.
"""
import logging

logger = logging.getLogger(__name__)


def init_mqtt(app):
    """Initialize MQTT connections via BrokerManager. Call inside create_app()."""
    from mqttui.broker_manager import init_broker_manager
    init_broker_manager(app)
    logger.info("MQTT client initialized via BrokerManager")


def get_client():
    """Get the default MQTT client instance (backward compat)."""
    from mqttui.broker_manager import get_broker_manager
    mgr = get_broker_manager()
    if mgr:
        conn = mgr.get_default_connection()
        if conn:
            return conn.client
    return None


def publish(topic, payload, qos=0, retain=False, broker_id=None):
    """Publish a message. Routes to specific broker or default."""
    from mqttui.broker_manager import get_broker_manager
    mgr = get_broker_manager()
    if mgr:
        mgr.publish(topic, payload, qos=qos, retain=retain, broker_id=broker_id)
