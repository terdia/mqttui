"""Broker management REST API endpoints."""
from flask import Blueprint, request
from flask_login import login_required

from mqttui.helpers import api_success, api_error
from mqttui.extensions import sa
from mqttui.models import Broker
from mqttui.broker_manager import get_broker_manager

brokers_bp = Blueprint('brokers', __name__, url_prefix='/api/v1/brokers')


@brokers_bp.route('/', methods=['GET'])
@login_required
def list_brokers():
    """List all configured brokers with connection status."""
    brokers = Broker.query.order_by(Broker.created_at).all()
    mgr = get_broker_manager()

    result = []
    for b in brokers:
        d = b.to_dict()
        if mgr:
            conn = mgr.get_connection(b.id)
            d['connected'] = conn.connected if conn else False
            d['connection_error'] = conn.error if conn else None
        else:
            d['connected'] = False
            d['connection_error'] = None
        result.append(d)

    return api_success({'brokers': result})


@brokers_bp.route('/', methods=['POST'])
@login_required
def create_broker():
    """Add a new broker connection."""
    data = request.get_json()
    if not data or not data.get('name') or not data.get('host'):
        return api_error("name and host are required", "VALIDATION", 400)

    broker = Broker(
        name=data['name'],
        host=data['host'],
        port=data.get('port', 1883),
        username=data.get('username'),
        password=data.get('password'),
        mqtt_version=data.get('mqtt_version', '3.1.1'),
        topics=data.get('topics', '#'),
        tls_enabled=data.get('tls_enabled', False),
        tls_ca_certs=data.get('tls_ca_certs'),
        tls_insecure=data.get('tls_insecure', False),
        is_active=data.get('is_active', True),
    )
    sa.session.add(broker)
    sa.session.commit()

    # Start connection if active
    if broker.is_active:
        mgr = get_broker_manager()
        if mgr:
            mgr.add_connection(broker)

    return api_success({'broker': broker.to_dict()}), 201


@brokers_bp.route('/<int:broker_id>', methods=['GET'])
@login_required
def get_broker(broker_id):
    """Get a single broker's details and connection status."""
    broker = sa.session.get(Broker, broker_id)
    if not broker:
        return api_error("Broker not found", "NOT_FOUND", 404)

    d = broker.to_dict()
    mgr = get_broker_manager()
    if mgr:
        conn = mgr.get_connection(broker.id)
        d['connected'] = conn.connected if conn else False
        d['connection_error'] = conn.error if conn else None

    return api_success({'broker': d})


@brokers_bp.route('/<int:broker_id>', methods=['PUT'])
@login_required
def update_broker(broker_id):
    """Update broker configuration. Reconnects if active."""
    broker = sa.session.get(Broker, broker_id)
    if not broker:
        return api_error("Broker not found", "NOT_FOUND", 404)

    data = request.get_json()
    if not data:
        return api_error("No data provided", "VALIDATION", 400)

    for field in ['name', 'host', 'port', 'username', 'password', 'mqtt_version',
                  'topics', 'tls_enabled', 'tls_ca_certs', 'tls_insecure', 'is_active']:
        if field in data:
            setattr(broker, field, data[field])

    sa.session.commit()

    # Reconnect with new settings
    mgr = get_broker_manager()
    if mgr:
        if broker.is_active:
            mgr.add_connection(broker)  # Stops old, starts new
        else:
            mgr.remove_connection(broker.id)

    return api_success({'broker': broker.to_dict()})


@brokers_bp.route('/<int:broker_id>', methods=['DELETE'])
@login_required
def delete_broker(broker_id):
    """Delete a broker and disconnect."""
    broker = sa.session.get(Broker, broker_id)
    if not broker:
        return api_error("Broker not found", "NOT_FOUND", 404)

    mgr = get_broker_manager()
    if mgr:
        mgr.remove_connection(broker.id)

    sa.session.delete(broker)
    sa.session.commit()

    return api_success({'deleted': broker_id})


@brokers_bp.route('/<int:broker_id>/connect', methods=['POST'])
@login_required
def connect_broker(broker_id):
    """Start/restart connection to a broker."""
    broker = sa.session.get(Broker, broker_id)
    if not broker:
        return api_error("Broker not found", "NOT_FOUND", 404)

    broker.is_active = True
    sa.session.commit()

    mgr = get_broker_manager()
    if mgr:
        mgr.add_connection(broker)

    return api_success({'broker': broker.to_dict(), 'status': 'connecting'})


@brokers_bp.route('/<int:broker_id>/disconnect', methods=['POST'])
@login_required
def disconnect_broker(broker_id):
    """Disconnect from a broker."""
    broker = sa.session.get(Broker, broker_id)
    if not broker:
        return api_error("Broker not found", "NOT_FOUND", 404)

    broker.is_active = False
    sa.session.commit()

    mgr = get_broker_manager()
    if mgr:
        mgr.remove_connection(broker.id)

    return api_success({'broker': broker.to_dict(), 'status': 'disconnected'})


@brokers_bp.route('/status', methods=['GET'])
@login_required
def broker_status():
    """Get live connection status for all brokers."""
    mgr = get_broker_manager()
    statuses = mgr.all_statuses() if mgr else []
    return api_success({'connections': statuses})
