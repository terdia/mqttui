import os
import logging
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from mqttui.events import mqtt_message_received
import mqttui.state as state

logger = logging.getLogger(__name__)

_mqtt_client = None

MQTT_RC_CODES = {
    0: "Connection successful",
    1: "Connection refused - incorrect protocol version",
    2: "Connection refused - invalid client identifier",
    3: "Connection refused - server unavailable",
    4: "Connection refused - bad username or password",
    5: "Connection refused - not authorised",
    # MQTT v5 specific codes
    16: "Connection refused - no matching subscribers",
    17: "Connection refused - no subscription existed",
    128: "Connection refused - unspecified error",
    129: "Connection refused - malformed packet",
    130: "Connection refused - protocol error",
    131: "Connection refused - implementation specific error",
    132: "Connection refused - unsupported protocol version",
    133: "Connection refused - client identifier not valid",
    134: "Connection refused - bad user name or password",
    135: "Connection refused - not authorized",
    136: "Connection refused - server unavailable",
    137: "Connection refused - server busy",
    138: "Connection refused - banned",
    139: "Connection refused - server shutting down",
    140: "Connection refused - bad authentication method",
    141: "Connection refused - topic name invalid",
    142: "Connection refused - packet too large",
    143: "Connection refused - quota exceeded",
    144: "Connection refused - payload format invalid",
    145: "Connection refused - retain not supported",
    146: "Connection refused - QoS not supported",
    147: "Connection refused - use another server",
    148: "Connection refused - server moved",
    149: "Connection refused - connection rate exceeded",
}


def init_mqtt(app):
    """Initialize MQTT client with app config. Call inside create_app()."""
    global _mqtt_client

    broker = app.config['MQTT_BROKER']
    port = app.config['MQTT_PORT']
    username = app.config.get('MQTT_USERNAME')
    password = app.config.get('MQTT_PASSWORD')
    keepalive = app.config['MQTT_KEEPALIVE']
    version = app.config['MQTT_VERSION']
    topics_str = app.config['MQTT_TOPICS']

    # paho-mqtt 2.x: must specify CallbackAPIVersion
    if version == '5':
        _mqtt_client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"mqttui_{os.getpid()}",
            protocol=mqtt.MQTTv5,
        )
    else:
        _mqtt_client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"mqttui_{os.getpid()}",
            protocol=mqtt.MQTTv311,
        )

    if username and password:
        _mqtt_client.username_pw_set(username, password)

    # paho-mqtt 2.x callback signatures:
    # on_connect(client, userdata, connect_flags, reason_code, properties)
    # on_disconnect(client, userdata, disconnect_flags, reason_code, properties)
    # on_message(client, userdata, message)

    def on_connect(client, userdata, connect_flags, reason_code, properties=None):
        rc = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
        if rc == 0:
            state.connection_count += 1
            topics_to_subscribe = [t.strip() for t in topics_str.split(',')]
            for topic in topics_to_subscribe:
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
            logger.info(f"Connected to MQTT broker at {broker}:{port}")
        else:
            error_message = MQTT_RC_CODES.get(rc, f"Unknown error (rc: {rc})")
            state.error_log.append(error_message)
            logger.error(f"Connection failed: {error_message}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
        rc = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
        state.connection_count = max(0, state.connection_count - 1)
        error_message = MQTT_RC_CODES.get(rc, f"Unknown error (rc: {rc})")
        disconnect_reason = 'Clean disconnect' if rc == 0 else f'Unexpected disconnect: {error_message}'
        state.error_log.append(f"Disconnected: {disconnect_reason}")
        logger.warning(f"Disconnected from MQTT broker: {disconnect_reason}")
        if rc != 0:
            logger.info("Attempting to reconnect...")

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode()
        except UnicodeDecodeError:
            payload = msg.payload.hex()

        timestamp = datetime.now()

        # Update in-memory state
        message = {
            'topic': msg.topic,
            'payload': payload,
            'timestamp': timestamp.isoformat(),
        }
        state.messages.append(message)
        state.topics.add(msg.topic)
        if len(state.messages) > 100:
            state.messages.pop(0)

        # Record to debug bar
        try:
            from debug_bar import debug_bar
            debug_bar.record('mqtt', 'last_topic', msg.topic)
            debug_bar.record('mqtt', 'last_payload', payload[:200])
            debug_bar.record('mqtt', 'last_qos', msg.qos)
            debug_bar.record('mqtt', 'last_retain', msg.retain)
            debug_bar.record('mqtt', 'last_timestamp', timestamp.isoformat())
            debug_bar.record('mqtt', 'connection_status', 'Connected')
            debug_bar.record('mqtt', 'broker', f"{broker}:{port}")
        except Exception:
            pass

        # Fire the event bus signal -- all consumers subscribe to this
        mqtt_message_received.send(
            'mqtt_client',
            topic=msg.topic,
            payload=payload,
            timestamp=timestamp,
            qos=msg.qos,
            retain=msg.retain,
        )

    _mqtt_client.on_connect = on_connect
    _mqtt_client.on_disconnect = on_disconnect
    _mqtt_client.on_message = on_message

    try:
        _mqtt_client.connect(broker, port, keepalive)
        _mqtt_client.loop_start()
        logger.info(f"MQTT client connecting to {broker}:{port}")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        state.error_log.append(f"Failed to connect: {e}")


def get_client():
    """Get the MQTT client instance for publishing."""
    return _mqtt_client


def publish(topic, payload, qos=0, retain=False):
    """Publish a message via MQTT."""
    if _mqtt_client:
        _mqtt_client.publish(topic, payload, qos=qos, retain=retain)
