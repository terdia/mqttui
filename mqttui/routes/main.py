from flask import Blueprint, render_template, request, jsonify, send_from_directory
from flask_login import login_required
import logging

from mqttui import __version__
from mqttui import state

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def index():
    return render_template('index.html', messages=state.messages, topics=list(state.topics))


@bp.route('/publish', methods=['POST'])
@login_required
def publish_message():
    from mqttui.mqtt_client import publish as mqtt_publish
    topic = request.form['topic']
    message = request.form['message']
    mqtt_publish(topic, message)
    return jsonify(success=True)


@bp.route('/stats')
def get_stats():
    return jsonify({
        'connection_count': state.connection_count,
        'topic_count': len(state.topics),
        'message_count': len(state.messages),
        'errors': state.error_log
    })


@bp.route('/version')
def get_version():
    return jsonify({'version': __version__})


@bp.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)
