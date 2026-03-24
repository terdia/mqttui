import os

import structlog
from flask import Flask

from mqttui.extensions import socketio, sa, login_manager
from mqttui.events import mqtt_message_received, rule_fired, alert_triggered
from mqttui.logging_config import configure_logging


def _on_mqtt_message(sender, **kwargs):
    """Forward MQTT messages to WebSocket clients and persist to database."""
    topic = kwargs['topic']
    payload = kwargs['payload']
    timestamp = kwargs['timestamp']
    qos = kwargs.get('qos', 0)
    retain = kwargs.get('retain', False)

    # Emit to connected browsers via batch emitter (100ms batching)
    from mqttui.socketio_batch import get_batch_emitter
    emitter = get_batch_emitter()
    msg_data = {
        'topic': topic,
        'payload': payload,
        'timestamp': timestamp.isoformat(),
        'retain': retain,
    }
    if emitter:
        emitter.enqueue(msg_data)
    else:
        socketio.emit('mqtt_message', msg_data)

    # Persist to database
    import mqttui.extensions as ext
    if ext.db:
        try:
            ext.db.store_message(
                topic=topic, payload=payload,
                timestamp=timestamp, qos=qos, retain=retain,
            )
        except Exception as e:
            structlog.get_logger(__name__).error("Failed to store message", error=str(e))


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

    # Set up structured logging via structlog
    log_level_name = os.getenv('LOG_LEVEL', 'DEBUG' if app.config['DEBUG'] else 'INFO').upper()
    configure_logging(debug=app.config['DEBUG'], log_level=log_level_name)

    # SECRET_KEY production guard
    flask_env = os.getenv('FLASK_ENV', 'development')
    insecure_keys = {'dev', 'change-me', 'your-secret-key'}
    if flask_env == 'production' and app.config['SECRET_KEY'] in insecure_keys:
        raise RuntimeError(
            "SECRET_KEY is insecure. Set a strong SECRET_KEY environment variable for production."
        )

    # Initialize SocketIO with gevent async mode
    socketio.init_app(app, async_mode='gevent')

    # Initialize batch emitter for Socket.IO message batching (100ms windows)
    from mqttui.socketio_batch import init_batch_emitter
    init_batch_emitter(socketio, interval_ms=100)

    # Enable CORS for API endpoints
    from flask_cors import CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Configure and initialize SQLAlchemy for user database
    db_dir = os.path.dirname(os.path.abspath(app.config.get('DB_PATH', 'mqtt_messages.db')))
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', f"sqlite:///{os.path.join(db_dir, 'mqttui_users.db')}")
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    sa.init_app(app)
    login_manager.init_app(app)

    # Initialize rate limiter
    from mqttui.extensions import limiter
    rate_limit = os.getenv('MQTTUI_RATE_LIMIT', '30/minute')
    app.config['RATELIMIT_DEFAULT'] = rate_limit
    limiter.init_app(app)

    with app.app_context():
        from mqttui.models import User  # noqa: F811
        from mqttui.rules.models import Rule, AlertHistory  # noqa: F401
        sa.create_all()

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
            structlog.get_logger(__name__).info("Database initialized", path=app.config['DB_PATH'])
        except Exception as e:
            structlog.get_logger(__name__).error("Failed to initialize database", error=str(e))

    # Register blueprints
    from mqttui.routes.main import bp as main_bp
    from mqttui.routes.api import bp as api_bp  # TODO: Remove legacy /api/ routes in Phase 5 after frontend migrates to /api/v1/
    from mqttui.routes.debug import bp as debug_bp
    from mqttui.routes.api_v1 import api_v1_bp
    from mqttui.routes.rules import rules_bp
    from mqttui.routes.alerts import alerts_bp
    from mqttui.routes.metrics import metrics_bp
    from mqttui.routes.analytics import analytics_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(api_v1_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(analytics_bp)

    # Register auth blueprint and seed admin user
    from mqttui.auth import auth_bp, seed_admin_user
    app.register_blueprint(auth_bp)
    seed_admin_user(app)

    # Initialize MQTT client (paho-mqtt 2.x with event bus)
    from mqttui.mqtt_client import init_mqtt
    init_mqtt(app)

    # Wire event bus: forward MQTT messages to SocketIO and database
    mqtt_message_received.connect(_on_mqtt_message)

    # Wire analytics subscriber to track per-topic rates and histograms
    from mqttui.analytics import _on_mqtt_message as _on_analytics_message
    mqtt_message_received.connect(_on_analytics_message)

    # Wire Prometheus metric signal subscribers
    from mqttui.routes.metrics import (
        _on_message_for_metrics, _on_rule_fired_for_metrics, _on_alert_for_metrics
    )
    mqtt_message_received.connect(_on_message_for_metrics)
    rule_fired.connect(_on_rule_fired_for_metrics)
    alert_triggered.connect(_on_alert_for_metrics)

    # Initialize rules engine (Phase 3)
    from mqttui.rules.engine import RuleEngine
    rule_engine = RuleEngine(app=app)
    rule_engine.connect()

    return app
