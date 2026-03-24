"""Alert history REST API blueprint.

Provides paginated, filterable listing of AlertHistory records.
All endpoints require authentication via @login_required.
"""
from flask import Blueprint, request
from flask_login import login_required

from mqttui.extensions import sa
from mqttui.helpers import api_success, api_error
from mqttui.rules.models import AlertHistory

alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/v1/alerts')


@alerts_bp.route('/')
@login_required
def list_alerts():
    """List alert history with pagination and optional filters.

    Query params:
        page (int): Page number, default 1.
        per_page (int): Items per page, default 20, max 100.
        rule_id (int): Filter by rule ID.
        severity (str): Filter by severity level.

    Returns:
        JSON envelope with alerts list, total count, page, and per_page.
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    rule_id = request.args.get('rule_id', type=int)
    severity = request.args.get('severity', type=str)

    query = AlertHistory.query.order_by(AlertHistory.fired_at.desc())

    if rule_id is not None:
        query = query.filter(AlertHistory.rule_id == rule_id)
    if severity:
        query = query.filter(AlertHistory.severity == severity)

    total = query.count()
    alerts = query.offset((page - 1) * per_page).limit(per_page).all()

    return api_success({
        "alerts": [a.to_dict() for a in alerts],
        "total": total,
        "page": page,
        "per_page": per_page,
    })
