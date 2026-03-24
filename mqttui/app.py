import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

from mqttui.extensions import socketio
from mqttui.events import mqtt_message_received


def _on_mqtt_message(sender, **kwargs):
    """Forward MQTT messages to WebSocket clients and persist to database."""
    topic = kwargs['topic']
    payload = kwargs['payload']
    timestamp = kwargs['timestamp']
    qos = kwargs.get('qos', 0)
    retain = kwargs.get('retain', False)

    # Emit to connected browsers
    socketio.emit('mqtt_message', {
        'topic': topic,
        'payload': payload,
        'timestamp': timestamp.isoformat(),
    })

    # Persist to database
    import mqttui.extensions as ext
    if ext.db:
        try:
            ext.db.store_message(
                topic=topic, payload=payload,
                timestamp=timestamp, qos=qos, retain=retain,
            )
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to store message: {e}")


def create_app(config=None):
    """Application factory for mqttui."""
    app = Flask(
        __name__,
        static_folder='../static',
        template_folder='../templates'
    )

    # Load config from environment variables
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
    app.config['DEBUG'] = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    app.config['HOST'] = os.getenv('HOST', '0.0.0.0')
    app.config['PORT'] = int(os.getenv('PORT', 5000))
    app.config['MQTT_BROKER'] = os.getenv('MQTT_BROKER', 'localhost')
    app.config['MQTT_PORT'] = int(os.getenv('MQTT_PORT', 1883))
    app.config['MQTT_USERNAME'] = os.getenv('MQTT_USERNAME')
    app.config['MQTT_PASSWORD'] = os.getenv('MQTT_PASSWORD')
    app.config['MQTT_KEEPALIVE'] = int(os.getenv('MQTT_KEEPALIVE', 60))
    app.config['MQTT_VERSION'] = os.getenv('MQTT_VERSION', '3.1.1')
    app.config['MQTT_TOPICS'] = os.getenv('MQTT_TOPICS', '#')
    app.config['DB_ENABLED'] = os.getenv('DB_ENABLED', 'True').lower() in ('true', '1', 't')
    app.config['DB_PATH'] = os.getenv('DB_PATH', 'mqtt_messages.db')
    app.config['DB_MAX_MESSAGES'] = int(os.getenv('DB_MAX_MESSAGES', 10000))
    app.config['DB_CLEANUP_DAYS'] = int(os.getenv('DB_CLEANUP_DAYS', 30))

    # Override with passed config dict
    if config:
        app.config.update(config)

    # Set up logging
    log_level_name = os.getenv('LOG_LEVEL', 'DEBUG' if app.config['DEBUG'] else 'INFO').upper()
    log_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'WARN': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = log_levels.get(log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    if not app.config['DEBUG']:
        handler = RotatingFileHandler('mqttui.log', maxBytes=10000, backupCount=1)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logging.getLogger('').addHandler(handler)

    # Initialize SocketIO with gevent async mode
    socketio.init_app(app, async_mode='gevent')

    # Initialize database if enabled
    if app.config['DB_ENABLED']:
        try:
            from mqttui.database import MessageDatabase
            import mqttui.extensions as ext
            db_instance = MessageDatabase(
                app.config['DB_PATH'],
                app.config['DB_MAX_MESSAGES']
            )
            ext.db = db_instance
            logging.info(f"Database initialized: {app.config['DB_PATH']}")
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")

    # Register blueprints
    from mqttui.routes.main import bp as main_bp
    from mqttui.routes.api import bp as api_bp
    from mqttui.routes.debug import bp as debug_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(debug_bp)

    # Initialize MQTT client (paho-mqtt 2.x with event bus)
    from mqttui.mqtt_client import init_mqtt
    init_mqtt(app)

    # Wire event bus: forward MQTT messages to SocketIO and database
    mqtt_message_received.connect(_on_mqtt_message)

    return app
