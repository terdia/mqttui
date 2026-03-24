"""Rules CRUD REST API blueprint.

All endpoints return JSON envelope: {"status": "success"|"error", "data": ..., "error": ...}
All endpoints require @login_required authentication.
"""

from flask import Blueprint, request
from flask_login import login_required
import json
import logging

from mqttui.extensions import sa
from mqttui.helpers import api_success, api_error
from mqttui.rules.models import Rule
from mqttui.rules.evaluator import evaluate, ConditionError
from mqttui.rules.ssrf import is_ssrf_safe
from mqttui.events import rule_changed

rules_bp = Blueprint('rules', __name__, url_prefix='/api/v1/rules')
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# List / Create
# ---------------------------------------------------------------------------

@rules_bp.route('/')
@login_required
def list_rules():
    """List all rules ordered by creation date (newest first)."""
    rules = Rule.query.order_by(Rule.created_at.desc()).all()
    return api_success({"rules": [r.to_dict() for r in rules]})


@rules_bp.route('/', methods=['POST'])
@login_required
def create_rule():
    """Create a new rule.

    Required fields: name, trigger_topic, action (dict with 'type' key).
    Optional: description, condition, rate_limit_per_min, schedule_cron, enabled.
    """
    data = request.get_json(silent=True)
    if not data:
        return api_error("JSON body required", "VALIDATION_ERROR", 400)

    # Validate required fields
    name = data.get('name')
    if not name or not isinstance(name, str) or not name.strip():
        return api_error("name is required", "VALIDATION_ERROR", 400)

    trigger_topic = data.get('trigger_topic')
    if not trigger_topic or not isinstance(trigger_topic, str) or not trigger_topic.strip():
        return api_error("trigger_topic is required", "VALIDATION_ERROR", 400)

    action = data.get('action')
    if not action or not isinstance(action, dict) or 'type' not in action:
        return api_error("action is required and must have a 'type' key", "VALIDATION_ERROR", 400)

    # SSRF validation for webhook actions
    if action.get('type') == 'webhook':
        webhook_url = action.get('url', '')
        safe, reason = is_ssrf_safe(webhook_url)
        if not safe:
            return api_error(f"Webhook URL rejected: {reason}", "SSRF_BLOCKED", 400)

    # Build rule
    rule = Rule(
        name=name.strip(),
        description=data.get('description', ''),
        trigger_topic=trigger_topic.strip(),
        condition_json=json.dumps(data.get('condition', {})),
        action_json=json.dumps(action),
        enabled=data.get('enabled', True),
        rate_limit_per_min=data.get('rate_limit_per_min', 10),
        schedule_cron=data.get('schedule_cron'),
    )

    sa.session.add(rule)
    sa.session.commit()

    rule_changed.send('api', action='created', rule_id=rule.id)
    logger.info(f"Rule created: id={rule.id} name={rule.name}")

    return api_success(rule.to_dict(), 201)


# ---------------------------------------------------------------------------
# Single rule CRUD
# ---------------------------------------------------------------------------

def _get_rule_or_404(rule_id):
    """Helper to fetch a rule by ID or return a 404 error response."""
    rule = sa.session.get(Rule, rule_id)
    if not rule:
        return None, api_error("Rule not found", "NOT_FOUND", 404)
    return rule, None


@rules_bp.route('/<int:rule_id>')
@login_required
def get_rule(rule_id):
    """Get a single rule by ID."""
    rule, err = _get_rule_or_404(rule_id)
    if err:
        return err
    return api_success(rule.to_dict())


@rules_bp.route('/<int:rule_id>', methods=['PUT'])
@login_required
def update_rule(rule_id):
    """Update a rule. Only updates fields present in the request body."""
    rule, err = _get_rule_or_404(rule_id)
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return api_error("JSON body required", "VALIDATION_ERROR", 400)

    # SSRF validation for webhook actions
    if 'action' in data and isinstance(data['action'], dict) and data['action'].get('type') == 'webhook':
        webhook_url = data['action'].get('url', '')
        safe, reason = is_ssrf_safe(webhook_url)
        if not safe:
            return api_error(f"Webhook URL rejected: {reason}", "SSRF_BLOCKED", 400)

    # Update only fields present in request
    if 'name' in data:
        rule.name = data['name']
    if 'description' in data:
        rule.description = data['description']
    if 'trigger_topic' in data:
        rule.trigger_topic = data['trigger_topic']
    if 'condition' in data:
        rule.condition_json = json.dumps(data['condition'])
    if 'action' in data:
        rule.action_json = json.dumps(data['action'])
    if 'enabled' in data:
        rule.enabled = data['enabled']
    if 'rate_limit_per_min' in data:
        rule.rate_limit_per_min = data['rate_limit_per_min']
    if 'schedule_cron' in data:
        rule.schedule_cron = data['schedule_cron']

    sa.session.commit()

    rule_changed.send('api', action='updated', rule_id=rule.id)
    logger.info(f"Rule updated: id={rule.id}")

    return api_success(rule.to_dict())


@rules_bp.route('/<int:rule_id>', methods=['DELETE'])
@login_required
def delete_rule(rule_id):
    """Delete a rule by ID."""
    rule, err = _get_rule_or_404(rule_id)
    if err:
        return err

    sa.session.delete(rule)
    sa.session.commit()

    rule_changed.send('api', action='deleted', rule_id=rule_id)
    logger.info(f"Rule deleted: id={rule_id}")

    return api_success({"message": f"Rule {rule_id} deleted"})


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------

@rules_bp.route('/<int:rule_id>/enable', methods=['POST'])
@login_required
def enable_rule(rule_id):
    """Enable a rule."""
    rule, err = _get_rule_or_404(rule_id)
    if err:
        return err

    rule.enabled = True
    sa.session.commit()

    rule_changed.send('api', action='updated', rule_id=rule.id)
    return api_success(rule.to_dict())


@rules_bp.route('/<int:rule_id>/disable', methods=['POST'])
@login_required
def disable_rule(rule_id):
    """Disable a rule."""
    rule, err = _get_rule_or_404(rule_id)
    if err:
        return err

    rule.enabled = False
    sa.session.commit()

    rule_changed.send('api', action='updated', rule_id=rule.id)
    return api_success(rule.to_dict())


# ---------------------------------------------------------------------------
# Dry-run / Test
# ---------------------------------------------------------------------------

@rules_bp.route('/<int:rule_id>/test', methods=['POST'])
@login_required
def test_rule(rule_id):
    """Dry-run a rule against a sample topic + payload.

    Checks topic matching (MQTT wildcard) and condition evaluation.
    Does NOT fire the rule's action -- purely for testing.
    """
    rule, err = _get_rule_or_404(rule_id)
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return api_error("JSON body required", "VALIDATION_ERROR", 400)

    topic = data.get('topic')
    payload_str = data.get('payload')

    if not topic:
        return api_error("topic is required", "VALIDATION_ERROR", 400)
    if payload_str is None:
        return api_error("payload is required", "VALIDATION_ERROR", 400)

    # Parse payload as JSON if possible
    payload_dict = None
    if isinstance(payload_str, dict):
        payload_dict = payload_str
    elif isinstance(payload_str, str):
        try:
            payload_dict = json.loads(payload_str)
        except (json.JSONDecodeError, ValueError):
            payload_dict = None

    # Check MQTT topic matching (supports wildcards + and #)
    topic_matches = _topic_matches(rule.trigger_topic, topic)

    # Check condition evaluation
    condition = json.loads(rule.condition_json) if rule.condition_json else {}
    condition_matches = False
    try:
        condition_matches = evaluate(condition, payload_dict)
    except ConditionError as e:
        return api_error(f"Condition error: {e}", "CONDITION_ERROR", 400)

    matched = topic_matches and condition_matches
    actions = [json.loads(rule.action_json)] if matched else []

    return api_success({
        "match": matched,
        "topic_match": topic_matches,
        "condition_match": condition_matches,
        "actions": actions,
    })


def _topic_matches(pattern, topic):
    """Check if an MQTT topic matches a subscription pattern.

    Supports MQTT wildcards:
    - '+' matches a single level
    - '#' matches any remaining levels (must be last)
    """
    pattern_parts = pattern.split('/')
    topic_parts = topic.split('/')

    for i, p in enumerate(pattern_parts):
        if p == '#':
            return True  # '#' matches everything from here
        if i >= len(topic_parts):
            return False
        if p != '+' and p != topic_parts[i]:
            return False

    return len(pattern_parts) == len(topic_parts)
