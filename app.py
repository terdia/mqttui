__version__ = "1.0.0"

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from datetime import datetime
import os
from debug_bar import debug_bar, debug_bar_middleware
import logging

app = Flask(__name__, static_url_path='/static')
socketio = SocketIO(app, async_mode='threading')

logging.basicConfig(level=logging.DEBUG)

app.before_request(debug_bar_middleware)

@app.after_request
def after_request(response):
    debug_bar.record('request', 'status_code', response.status_code)
    debug_bar.end_request()
    return response

# MQTT setup
mqtt_client = mqtt.Client()
mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
mqtt_port = int(os.getenv('MQTT_PORT', 1883))
mqtt_username = os.getenv('MQTT_USERNAME')
mqtt_password = os.getenv('MQTT_PASSWORD')

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
    connection_status = 'Connected' if rc == 0 else f'Failed (rc: {rc})'
    debug_bar.record('mqtt', 'connection_status', connection_status)
    debug_bar.record('mqtt', 'broker', mqtt_broker)
    debug_bar.record('mqtt', 'port', mqtt_port)
    debug_bar.record('mqtt', 'username', mqtt_username if mqtt_username else 'Not set')
    debug_bar.record('mqtt', 'password', 'Set' if mqtt_password else 'Not set')
    
    if rc == 0:
        connection_count += 1
        client.subscribe("#")  # Subscribe to all topics
        logging.info(f"Connected to MQTT broker. Total connections: {connection_count}")
    else:
        error_message = f"Connection failed with code {rc}"
        error_log.append(error_message)
        debug_bar.record('mqtt', 'last_error', error_message)
        logging.error(error_message)

def on_disconnect(client, userdata, rc):
    disconnect_reason = 'Clean disconnect' if rc == 0 else f'Unexpected disconnect (rc: {rc})'
    debug_bar.record('mqtt', 'last_disconnect', disconnect_reason)
    error_log.append(f"Disconnected: {disconnect_reason}")
    logging.warning(f"Disconnected from MQTT broker: {disconnect_reason}")

def on_message(client, userdata, msg):
    message = {
        'topic': msg.topic,
        'payload': msg.payload.decode(),
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

if __name__ == '__main__':
    if mqtt_username and mqtt_password:
        mqtt_client.username_pw_set(mqtt_username, mqtt_password)
    try:
        mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        error_message = f"Failed to connect to MQTT broker: {str(e)}"
        debug_bar.record('mqtt', 'connection_error', error_message)
        error_log.append(error_message)
        logging.error(error_message)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)