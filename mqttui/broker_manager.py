"""Multi-broker connection manager.

Manages multiple paho-mqtt client connections, each tied to a Broker model.
Replaces the single-client approach in mqtt_client.py.
"""
import os
import logging
import ssl
from datetime import datetime

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from mqttui.events import mqtt_message_received
import mqttui.state as state

logger = logging.getLogger(__name__)

MQTT_RC_CODES = {
    0: "Connection successful",
    1: "Incorrect protocol version",
    2: "Invalid client identifier",
    3: "Server unavailable",
    4: "Bad username or password",
    5: "Not authorised",
    128: "Unspecified error",
    134: "Bad user name or password",
    135: "Not authorized",
    136: "Server unavailable",
}

# Module-level singleton
_broker_manager = None


def get_broker_manager():
    return _broker_manager


class ManagedConnection:
    """A single broker connection with its paho-mqtt client."""

    def __init__(self, broker_id, name, host, port, username=None, password=None,
                 mqtt_version='3.1.1', topics='#', tls_enabled=False,
                 tls_ca_certs=None, tls_insecure=False):
        self.broker_id = broker_id
        self.name = name
        self.host = host
        self.port = port
        self.topics_str = topics
        self.connected = False
        self.error = None

        # Create paho-mqtt client
        protocol = mqtt.MQTTv5 if mqtt_version == '5' else mqtt.MQTTv311
        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=f"mqttui_{os.getpid()}_{broker_id}",
            protocol=protocol,
        )

        if username and password:
            self.client.username_pw_set(username, password)

        if tls_enabled:
            self.client.tls_set(
                ca_certs=tls_ca_certs if tls_ca_certs else None,
                cert_reqs=ssl.CERT_NONE if tls_insecure else ssl.CERT_REQUIRED,
            )
            if tls_insecure:
                self.client.tls_insecure_set(True)

        # Wire callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties=None):
        rc = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
        if rc == 0:
            self.connected = True
            self.error = None
            state.connection_count += 1
            for topic in [t.strip() for t in self.topics_str.split(',')]:
                client.subscribe(topic)
                logger.info(f"[{self.name}] Subscribed to: {topic}")
            logger.info(f"[{self.name}] Connected to {self.host}:{self.port}")
        else:
            self.connected = False
            self.error = MQTT_RC_CODES.get(rc, f"Unknown error (rc: {rc})")
            logger.error(f"[{self.name}] Connection failed: {self.error}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        rc = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
        self.connected = False
        state.connection_count = max(0, state.connection_count - 1)
        if rc != 0:
            self.error = MQTT_RC_CODES.get(rc, f"Unexpected disconnect (rc: {rc})")
            logger.warning(f"[{self.name}] Disconnected: {self.error}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
        except UnicodeDecodeError:
            payload = msg.payload.hex()

        timestamp = datetime.now()

        # Update shared in-memory state
        message = {
            'topic': msg.topic,
            'payload': payload,
            'timestamp': timestamp.isoformat(),
            'broker_id': self.broker_id,
            'broker_name': self.name,
        }
        state.messages.append(message)
        state.topics.add(msg.topic)
        if len(state.messages) > 100:
            state.messages.pop(0)

        # Debug bar
        try:
            from debug_bar import debug_bar
            debug_bar.record('mqtt', 'last_topic', msg.topic)
            debug_bar.record('mqtt', 'last_payload', payload[:200])
            debug_bar.record('mqtt', 'last_broker', f"{self.name} ({self.host}:{self.port})")
            debug_bar.record('mqtt', 'last_timestamp', timestamp.isoformat())
        except Exception:
            pass

        # Fire event bus signal with broker context
        mqtt_message_received.send(
            'broker_manager',
            topic=msg.topic,
            payload=payload,
            timestamp=timestamp,
            qos=msg.qos,
            retain=msg.retain,
            broker_id=self.broker_id,
            broker_name=self.name,
        )

    def start(self):
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()
            logger.info(f"[{self.name}] Connecting to {self.host}:{self.port}")
        except Exception as e:
            self.connected = False
            self.error = str(e)
            logger.error(f"[{self.name}] Failed to connect: {e}")

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False

    def publish(self, topic, payload, qos=0, retain=False):
        if self.client and self.connected:
            self.client.publish(topic, payload, qos=qos, retain=retain)

    def status_dict(self):
        return {
            'broker_id': self.broker_id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'connected': self.connected,
            'error': self.error,
        }


class BrokerManager:
    """Manages multiple MQTT broker connections."""

    def __init__(self, app=None):
        self.app = app
        self.connections = {}  # broker_id -> ManagedConnection

    def add_connection(self, broker):
        """Add and start a connection from a Broker model instance or dict."""
        if isinstance(broker, dict):
            broker_id = broker['id']
            conn = ManagedConnection(
                broker_id=broker_id,
                name=broker['name'],
                host=broker['host'],
                port=broker.get('port', 1883),
                username=broker.get('username'),
                password=broker.get('password'),
                mqtt_version=broker.get('mqtt_version', '3.1.1'),
                topics=broker.get('topics', '#'),
                tls_enabled=broker.get('tls_enabled', False),
                tls_ca_certs=broker.get('tls_ca_certs'),
                tls_insecure=broker.get('tls_insecure', False),
            )
        else:
            broker_id = broker.id
            conn = ManagedConnection(
                broker_id=broker.id,
                name=broker.name,
                host=broker.host,
                port=broker.port,
                username=broker.username,
                password=broker.password,
                mqtt_version=broker.mqtt_version,
                topics=broker.topics,
                tls_enabled=broker.tls_enabled,
                tls_ca_certs=broker.tls_ca_certs,
                tls_insecure=broker.tls_insecure,
            )

        # Stop existing connection if replacing
        if broker_id in self.connections:
            self.connections[broker_id].stop()

        self.connections[broker_id] = conn
        conn.start()
        return conn

    def remove_connection(self, broker_id):
        conn = self.connections.pop(broker_id, None)
        if conn:
            conn.stop()

    def get_connection(self, broker_id):
        return self.connections.get(broker_id)

    def get_default_connection(self):
        """Return the first connected broker, or first broker overall."""
        for conn in self.connections.values():
            if conn.connected:
                return conn
        # Fallback to first
        if self.connections:
            return next(iter(self.connections.values()))
        return None

    def publish(self, topic, payload, qos=0, retain=False, broker_id=None):
        """Publish to a specific broker or the default one."""
        if broker_id and broker_id in self.connections:
            self.connections[broker_id].publish(topic, payload, qos, retain)
        else:
            conn = self.get_default_connection()
            if conn:
                conn.publish(topic, payload, qos, retain)

    def all_statuses(self):
        return [conn.status_dict() for conn in self.connections.values()]

    def start_all(self, app):
        """Load active brokers from DB and start connections."""
        with app.app_context():
            from mqttui.models import Broker
            brokers = Broker.query.filter_by(is_active=True).all()
            for broker in brokers:
                self.add_connection(broker)
            logger.info(f"BrokerManager started {len(brokers)} connection(s)")

    def stop_all(self):
        for conn in self.connections.values():
            conn.stop()
        self.connections.clear()

    def load_env_broker(self, app):
        """Create a default broker from environment variables if no brokers in DB."""
        with app.app_context():
            from mqttui.models import Broker
            if Broker.query.count() > 0:
                return  # DB already has brokers

            # Seed from env vars (backward compatible with v1.x)
            broker = Broker(
                name='Default',
                host=app.config['MQTT_BROKER'],
                port=app.config['MQTT_PORT'],
                username=app.config.get('MQTT_USERNAME'),
                password=app.config.get('MQTT_PASSWORD'),
                mqtt_version=app.config['MQTT_VERSION'],
                topics=app.config['MQTT_TOPICS'],
                tls_enabled=app.config.get('MQTT_TLS', 'false').lower() in ('true', '1', 'yes'),
                tls_ca_certs=app.config.get('MQTT_TLS_CA_CERTS') or None,
                tls_insecure=app.config.get('MQTT_TLS_INSECURE', 'false').lower() in ('true', '1', 'yes'),
                is_active=True,
                is_default=True,
            )
            from mqttui.extensions import sa
            sa.session.add(broker)
            sa.session.commit()
            logger.info(f"Seeded default broker from env: {broker.host}:{broker.port}")


def init_broker_manager(app):
    """Initialize the global broker manager. Call from create_app()."""
    global _broker_manager
    _broker_manager = BrokerManager(app=app)
    _broker_manager.load_env_broker(app)
    _broker_manager.start_all(app)
    return _broker_manager
