__version__ = "1.3.0"

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from datetime import datetime
import os
from debug_bar import debug_bar, debug_bar_middleware
import logging
import time
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from werkzeug.serving import run_simple

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

# Set up logging
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(level=log_level)
if not DEBUG:
    handler = RotatingFileHandler('mqttui.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.INFO)
    logging.getLogger('').addHandler(handler)

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, async_mode='threading')

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

def on_connect(client, userdata, flags, rc):
    global connection_count
    error_message = MQTT_RC_CODES.get(rc, f"Unknown error (rc: {rc})")
    connection_status = 'Connected' if rc == 0 else f'Failed: {error_message}'
    debug_bar.record('mqtt', 'connection_status', connection_status)
    
    logging.info(f"MQTT Connection attempt - Result: {connection_status}")
    logging.info(f"MQTT Connection details - Broker: {mqtt_broker}, Port: {mqtt_port}, Username: {'Set' if mqtt_username else 'Not set'}, Password: {'Set' if mqtt_password else 'Not set'}, Protocol: MQTT v{mqtt_version}")
    
    if rc == 0:
        connection_count += 1
        client.subscribe("#")  # Subscribe to all topics
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

    message = {
        'topic': msg.topic,
        'payload': payload,
        'timestamp': datetime.now().isoformat()
    }
    messages.append(message)
    topics.add(msg.topic)
    if len(messages) > 100:
        messages.pop(0)
    socketio.emit('mqtt_message', message)
    debug_bar.record('mqtt', 'last_message', message)
    logging.debug(f"MQTT message received: {message}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.on_disconnect = on_disconnect

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