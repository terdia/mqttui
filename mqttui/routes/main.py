from flask import Blueprint, render_template, request, jsonify, send_from_directory
from flask_login import login_required
import logging

from mqttui import __version__
from mqttui.extensions import limiter
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
@limiter.exempt
def get_stats():
    return jsonify({
        'connection_count': state.connection_count,
        'topic_count': len(state.topics),
        'message_count': len(state.messages),
        'errors': state.error_log
    })


@bp.route('/version')
@limiter.exempt
def get_version():
    return jsonify({'version': __version__})


@bp.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


# ---------------------------------------------------------------------------
# Partial routes for htmx (Alerts History UI)
# ---------------------------------------------------------------------------

@bp.route('/partials/alerts')
@login_required
def alerts_list_partial():
    """Return HTML partial of alert history with pagination and filters."""
    from mqttui.rules.models import AlertHistory, Rule

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    rule_id = request.args.get('rule_id', type=int)
    severity = request.args.get('severity', type=str)

    query = AlertHistory.query.order_by(AlertHistory.fired_at.desc())
    if rule_id:
        query = query.filter(AlertHistory.rule_id == rule_id)
    if severity:
        query = query.filter(AlertHistory.severity == severity)

    total = query.count()
    alerts = query.offset((page - 1) * per_page).limit(per_page).all()
    has_next = (page * per_page) < total

    # Get all rules for filter dropdown
    rules = Rule.query.order_by(Rule.name).all()

    return render_template('partials/alerts_list.html',
                           alerts=alerts, rules=rules,
                           page=page, per_page=per_page,
                           total=total, has_next=has_next,
                           current_rule_id=rule_id,
                           current_severity=severity)


# ---------------------------------------------------------------------------
# Partial routes for htmx (Rules Editor UI)
# ---------------------------------------------------------------------------

@bp.route('/partials/rules')
@login_required
def rules_list_partial():
    """Return HTML partial of all rules for htmx swap."""
    from mqttui.rules.models import Rule
    rules = Rule.query.order_by(Rule.created_at.desc()).all()
    return render_template('partials/rules_list.html', rules=rules)


@bp.route('/partials/rules/<int:rule_id>/row')
@login_required
def rule_row_partial(rule_id):
    """Return single rule row partial after update."""
    from mqttui.rules.models import Rule
    from mqttui.extensions import sa
    rule = sa.session.get(Rule, rule_id)
    if not rule:
        return '', 404
    return render_template('partials/rule_row.html', rule=rule)


@bp.route('/partials/rules/form')
@login_required
def rule_form_partial():
    """Return empty rule creation form partial."""
    return render_template('partials/rule_form.html', rule=None)


@bp.route('/partials/rules/<int:rule_id>/form')
@login_required
def rule_edit_form_partial(rule_id):
    """Return pre-filled rule edit form partial."""
    from mqttui.rules.models import Rule
    from mqttui.extensions import sa
    rule = sa.session.get(Rule, rule_id)
    if not rule:
        return '', 404
    return render_template('partials/rule_form.html', rule=rule)


@bp.route('/partials/rules/<int:rule_id>/dry-run')
@login_required
def dry_run_form_partial(rule_id):
    """Return dry-run test form for a rule."""
    return render_template('partials/dry_run_result.html', rule_id=rule_id, result=None)


@bp.route('/partials/rules/<int:rule_id>/toggle', methods=['POST'])
@login_required
def rule_toggle_partial(rule_id):
    """Toggle rule enabled/disabled and return updated row partial."""
    from mqttui.rules.models import Rule
    from mqttui.extensions import sa
    from mqttui.events import rule_changed
    rule = sa.session.get(Rule, rule_id)
    if not rule:
        return '', 404
    rule.enabled = not rule.enabled
    sa.session.commit()
    rule_changed.send('ui', action='updated', rule_id=rule.id)
    return render_template('partials/rule_row.html', rule=rule)


@bp.route('/partials/analytics')
@login_required
def analytics_partial():
    """Return HTML partial for analytics dashboard widget."""
    return render_template('partials/analytics.html')


@bp.route('/partials/rules/<int:rule_id>/delete', methods=['DELETE'])
@login_required
def rule_delete_partial(rule_id):
    """Delete a rule and return empty response to remove DOM element."""
    from mqttui.rules.models import Rule
    from mqttui.extensions import sa
    from mqttui.events import rule_changed
    rule = sa.session.get(Rule, rule_id)
    if not rule:
        return '', 404
    sa.session.delete(rule)
    sa.session.commit()
    rule_changed.send('ui', action='deleted', rule_id=rule_id)
    return ''  # Empty response removes the element
