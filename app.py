__version__ = "1.0.0"

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from datetime import datetime
import os

app = Flask(__name__, static_url_path='/static')
socketio = SocketIO(app)

# MQTT setup
mqtt_client = mqtt.Client()
mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
mqtt_port = int(os.getenv('MQTT_PORT', 1883))
mqtt_username = os.getenv('MQTT_USERNAME')
mqtt_password = os.getenv('MQTT_PASSWORD')

messages = []
topics = set()
connection_count = 0
error_log = []

def on_connect(client, userdata, flags, rc):
    global connection_count
    if rc == 0:
        print("Connected to MQTT broker")
        connection_count += 1
        client.subscribe("#")  # Subscribe to all topics
    else:
        print(f"Failed to connect to MQTT broker with code {rc}")
        error_log.append(f"Failed to connect to MQTT broker with code {rc}")

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

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

@app.route('/')
def index():
    return render_template('index.html', messages=messages, topics=list(topics))

@app.route('/publish', methods=['POST'])
def publish_message():
    topic = request.form['topic']
    message = request.form['message']
    mqtt_client.publish(topic, message)
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
        print(f"Failed to connect to MQTT broker: {str(e)}")
        error_log.append(f"Failed to connect to MQTT broker: {str(e)}")
    
    print(f"Starting MQTT Web Interface v{__version__}")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)