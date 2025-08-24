__version__ = "1.3.0"

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import os
from debug_bar import debug_bar, debug_bar_middleware
import logging
import time
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from werkzeug.serving import run_simple
from database import MessageDatabase

# Load environment variables
load_dotenv()

# Configuration
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', 60))
MQTT_VERSION = os.getenv('MQTT_VERSION', '3.1.1')
# Support for topic filtering (issue #6)
MQTT_TOPICS = os.getenv('MQTT_TOPICS', '#')  # Comma-separated list of topics to subscribe to

# Database configuration for message persistence
DB_ENABLED = os.getenv('DB_ENABLED', 'True').lower() in ('true', '1', 't')
DB_PATH = os.getenv('DB_PATH', 'mqtt_messages.db')
DB_MAX_MESSAGES = int(os.getenv('DB_MAX_MESSAGES', 10000))
DB_CLEANUP_DAYS = int(os.getenv('DB_CLEANUP_DAYS', 30))

# Set up logging with LOG_LEVEL environment variable support (fixes issue #9)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO').upper()
log_levels = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'WARN': logging.WARNING,  # Support both WARN and WARNING
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
log_level = log_levels.get(LOG_LEVEL, logging.INFO)
if LOG_LEVEL not in log_levels:
    print(f"Invalid LOG_LEVEL: {LOG_LEVEL}. Using INFO level.")
    
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
if not DEBUG:
    handler = RotatingFileHandler('mqttui.log', maxBytes=10000, backupCount=1)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger('').addHandler(handler)

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, async_mode='threading')

# Initialize database for message persistence
db = None
if DB_ENABLED:
    try:
        db = MessageDatabase(DB_PATH, DB_MAX_MESSAGES)
        logging.info(f"Database initialized: {DB_PATH}")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        db = None

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
    149: "Connection refused - connection rate exceeded"
}

app.before_request(debug_bar_middleware)

@app.after_request
def after_request(response):
    debug_bar.record('request', 'status_code', response.status_code)
    debug_bar.end_request()
    return response

# MQTT setup
mqtt_version = os.getenv('MQTT_VERSION', '3.1.1')
if mqtt_version == '5':
    mqtt_client = mqtt.Client(client_id=f"mqttui_{os.getpid()}", protocol=mqtt.MQTTv5)
    logging.info("Using MQTT v5")
else:
    mqtt_client = mqtt.Client(client_id=f"mqttui_{os.getpid()}", clean_session=True, protocol=mqtt.MQTTv311)
    logging.info("Using MQTT v3.1.1")

mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
mqtt_port = int(os.getenv('MQTT_PORT', 1883))
mqtt_username = os.getenv('MQTT_USERNAME')
mqtt_password = os.getenv('MQTT_PASSWORD')
mqtt_keepalive = int(os.getenv('MQTT_KEEPALIVE', 60))

logging.info(f"MQTT Setup - Broker: {mqtt_broker}, Port: {mqtt_port}, Username: {'Set' if mqtt_username else 'Not set'}, Password: {'Set' if mqtt_password else 'Not set'}, Version: {mqtt_version}")

messages = []
topics = set()
connection_count = 0
active_websockets = 0
error_log = []

@socketio.on('connect')
def handle_connect():
    global active_websockets
    active_websockets += 1
    debug_bar.record('performance', 'active_websockets', active_websockets)
    logging.info(f"WebSocket connected. Total active: {active_websockets}")

@socketio.on('disconnect')
def handle_disconnect():
    global active_websockets
    active_websockets -= 1
    debug_bar.record('performance', 'active_websockets', active_websockets)
    logging.info(f"WebSocket disconnected. Total active: {active_websockets}")

def on_connect(client, userdata, flags, rc, properties=None):
    # MQTT v5 includes 'properties' parameter, v3.1.1 doesn't (fixes issue #8)
    global connection_count
    error_message = MQTT_RC_CODES.get(rc, f"Unknown error (rc: {rc})")
    connection_status = 'Connected' if rc == 0 else f'Failed: {error_message}'
    debug_bar.record('mqtt', 'connection_status', connection_status)
    
    logging.info(f"MQTT Connection attempt - Result: {connection_status}")
    logging.info(f"MQTT Connection details - Broker: {mqtt_broker}, Port: {mqtt_port}, Username: {'Set' if mqtt_username else 'Not set'}, Password: {'Set' if mqtt_password else 'Not set'}, Protocol: MQTT v{mqtt_version}")
    
    if rc == 0:
        connection_count += 1
        # Subscribe to specified topics (supports filtering - issue #6)
        topics_to_subscribe = [topic.strip() for topic in MQTT_TOPICS.split(',')]
        for topic in topics_to_subscribe:
            client.subscribe(topic)
            logging.info(f"Subscribed to topic: {topic}")
        logging.info(f"Connected to MQTT broker at {mqtt_broker}:{mqtt_port}. Total connections: {connection_count}")
        debug_bar.remove('mqtt', 'connection_attempt')  # Remove connection attempt entry
    else:
        error_log.append(error_message)
        debug_bar.record('mqtt', 'last_error', error_message)
        logging.error(f"Connection failed: {error_message}")
        time.sleep(5)
        connect_mqtt()  # Retry connection

def on_disconnect(client, userdata, rc):
    global connection_count
    connection_count = max(0, connection_count - 1)
    error_message = MQTT_RC_CODES.get(rc, f"Unknown error (rc: {rc})")
    disconnect_reason = 'Clean disconnect' if rc == 0 else f'Unexpected disconnect: {error_message}'
    debug_bar.record('mqtt', 'last_disconnect', disconnect_reason)
    error_log.append(f"Disconnected: {disconnect_reason}")
    logging.warning(f"Disconnected from MQTT broker: {disconnect_reason}")
    
    if rc != 0:
        logging.info("Attempting to reconnect...")
        client.connect_async(mqtt_broker, mqtt_port, mqtt_keepalive)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
    except UnicodeDecodeError:
        payload = msg.payload.hex()

    timestamp = datetime.now()
    message = {
        'topic': msg.topic,
        'payload': payload,
        'timestamp': timestamp.isoformat()
    }
    
    # Store in memory for backward compatibility
    messages.append(message)
    topics.add(msg.topic)
    if len(messages) > 100:
        messages.pop(0)
    
    # Store in database if enabled
    if db:
        try:
            db.store_message(
                topic=msg.topic,
                payload=payload,
                timestamp=timestamp,
                qos=msg.qos,
                retain=msg.retain
            )
        except Exception as e:
            logging.error(f"Failed to store message in database: {e}")
    
    # Emit to connected clients
    socketio.emit('mqtt_message', message)
    debug_bar.record('mqtt', 'last_message', message)
    logging.debug(f"MQTT message received: {message}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.on_disconnect = on_disconnect

# API endpoints for message history
@app.route('/api/messages')
def get_message_history():
    """Get paginated message history with optional filtering"""
    try:
        # Get query parameters
        limit = min(int(request.args.get('limit', 100)), 1000)  # Max 1000 messages
        offset = int(request.args.get('offset', 0))
        topic_filter = request.args.get('topic')
        hours = request.args.get('hours')  # Messages from last N hours
        
        since = None
        if hours:
            since = datetime.now() - timedelta(hours=int(hours))
        
        if db:
            # Get from database
            messages_list = db.get_messages(
                limit=limit,
                offset=offset, 
                topic_filter=topic_filter,
                since=since
            )
            total_count = db.get_message_count(topic_filter=topic_filter, since=since)
        else:
            # Fallback to in-memory messages
            messages_list = list(reversed(messages))  # Most recent first
            if topic_filter:
                messages_list = [m for m in messages_list if m['topic'] == topic_filter]
            
            total_count = len(messages_list)
            messages_list = messages_list[offset:offset+limit]
        
        return jsonify({
            'messages': messages_list,
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + len(messages_list) < total_count
        })
        
    except Exception as e:
        logging.error(f"Error getting message history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/topics')
def get_topic_list():
    """Get list of all topics with statistics"""
    try:
        if db:
            topics_list = db.get_topics()
        else:
            # Fallback to in-memory topics
            topics_list = [{'topic': topic} for topic in sorted(topics)]
        
        return jsonify({'topics': topics_list})
        
    except Exception as e:
        logging.error(f"Error getting topics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/stats')
def get_database_stats():
    """Get database size and statistics"""
    try:
        if db:
            stats = db.get_database_size()
            stats['enabled'] = True
        else:
            stats = {
                'enabled': False,
                'message_count': len(messages),
                'topic_count': len(topics)
            }
        
        return jsonify(stats)
        
    except Exception as e:
        logging.error(f"Error getting database stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/cleanup', methods=['POST'])
def cleanup_database():
    """Clean up old database records"""
    try:
        if not db:
            return jsonify({'error': 'Database not enabled'}), 400
            
        days = int(request.json.get('days', DB_CLEANUP_DAYS))
        deleted = db.cleanup_old_data(days)
        
        return jsonify({
            'success': True,
            'deleted_messages': deleted,
            'days': days
        })
        
    except Exception as e:
        logging.error(f"Error cleaning database: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html', messages=messages, topics=list(topics))

@app.route('/publish', methods=['POST'])
def publish_message():
    topic = request.form['topic']
    message = request.form['message']
    mqtt_client.publish(topic, message)
    debug_bar.record('mqtt', 'last_publish', {'topic': topic, 'message': message})
    return jsonify(success=True)

@app.route('/stats')
def get_stats():
    return jsonify({
        'connection_count': connection_count,
        'topic_count': len(topics),
        'message_count': len(messages),
        'errors': error_log
    })

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/debug-bar')
def get_debug_bar_data():
    try:
        data = debug_bar.get_data()
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error fetching debug bar data: {e}")
        return jsonify({"error": "Failed to fetch debug bar data"}), 500

@app.route('/toggle-debug-bar', methods=['POST'])
def toggle_debug_bar():
    if debug_bar.enabled:
        debug_bar.disable()
    else:
        debug_bar.enable()
    return jsonify(enabled=debug_bar.enabled)

@app.route('/record-client-performance', methods=['POST'])
def record_client_performance():
    data = request.json
    debug_bar.record('performance', 'page_load_time', f"{data['pageLoadTime']}ms")
    debug_bar.record('performance', 'dom_ready_time', f"{data['domReadyTime']}ms")
    return jsonify(success=True)

@app.route('/version')
def get_version():
    return jsonify({'version': __version__})

if __name__ == '__main__' or __name__ == 'app':
    if mqtt_username and mqtt_password:
        mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    
    def connect_mqtt():
        if mqtt_username and mqtt_password:
            mqtt_client.username_pw_set(mqtt_username, mqtt_password)
            logging.info("MQTT credentials set")
        else:
            logging.info("No MQTT credentials provided")
        
        debug_bar.record('mqtt', 'connection_attempt', f"Connecting to {mqtt_broker}:{mqtt_port}")
        debug_bar.record('mqtt', 'broker', mqtt_broker)
        debug_bar.record('mqtt', 'port', mqtt_port)
        debug_bar.record('mqtt', 'username', mqtt_username if mqtt_username else 'Not set')
        debug_bar.record('mqtt', 'password', 'Set' if mqtt_password else 'Not set')
        debug_bar.record('mqtt', 'protocol', f'MQTT v{mqtt_version}')
        debug_bar.record('mqtt', 'subscribed_topics', MQTT_TOPICS)
        
        logging.info(f"Attempting to connect to MQTT broker at {mqtt_broker}:{mqtt_port}")
        
        try:
            mqtt_client.connect(mqtt_broker, mqtt_port, mqtt_keepalive)
            mqtt_client.loop_start()
        except Exception as e:
            error_message = f"Failed to connect to MQTT broker: {str(e)}"
            debug_bar.record('mqtt', 'connection_error', error_message)
            debug_bar.record('mqtt', 'connection_status', 'Failed')
            error_log.append(error_message)
            logging.error(error_message)
            time.sleep(5)
            connect_mqtt()  # Retry connection
            debug_bar.record('mqtt', 'connection_status', 'Failed')
    
    connect_mqtt()
    
    # Start the Flask-SocketIO server when running directly
    # This prevents the app from exiting prematurely (fixes issue #12)
    if __name__ == '__main__':
        socketio.run(app, host=HOST, port=PORT, debug=DEBUG)