"""Action executor for the rules engine.

Handles publish, log, and webhook action types.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def execute_action(action_dict, context):
    """Execute a rule action.

    Args:
        action_dict: parsed action JSON with 'type' key.
            - type 'publish': publishes MQTT message with __source marker
            - type 'log': creates AlertHistory record in database
            - type 'webhook': stub that logs intent (Phase 4)
        context: dict with 'rule_id', 'rule_name', 'topic', 'payload' keys.

    Returns:
        dict with 'success' bool and 'detail' string.
    """
    action_type = action_dict.get('type')

    if action_type == 'publish':
        return _execute_publish(action_dict, context)
    elif action_type == 'log':
        return _execute_log(action_dict, context)
    elif action_type == 'webhook':
        return _execute_webhook(action_dict, context)
    else:
        return {"success": False, "detail": f"Unknown action type: {action_type}"}


def _execute_publish(action_dict, context):
    """Publish an MQTT message with __source marker for loop prevention."""
    from mqttui.mqtt_client import publish as mqtt_publish

    # Use action payload if specified, otherwise use original context payload
    outgoing = action_dict.get('payload', context.get('payload'))

    # Parse as JSON if possible, inject __source marker
    if isinstance(outgoing, str):
        try:
            outgoing_dict = json.loads(outgoing)
        except (json.JSONDecodeError, TypeError):
            # Raw string -- wrap in JSON envelope
            outgoing_dict = {"payload": outgoing}
    elif isinstance(outgoing, dict):
        outgoing_dict = outgoing
    else:
        outgoing_dict = {"payload": str(outgoing)}

    outgoing_dict["__source"] = "mqttui-automation"

    mqtt_publish(
        action_dict['topic'],
        json.dumps(outgoing_dict),
        qos=action_dict.get('qos', 0),
        retain=action_dict.get('retain', False),
    )
    return {"success": True, "detail": f"Published to {action_dict['topic']}"}


def _execute_log(action_dict, context):
    """Create an AlertHistory record in the database."""
    from mqttui.rules.models import AlertHistory
    from mqttui.extensions import sa

    message = action_dict.get(
        'message',
        f"Rule {context['rule_name']} fired on {context['topic']}",
    )

    record = AlertHistory(
        rule_id=context['rule_id'],
        rule_name=context['rule_name'],
        topic=context['topic'],
        severity=action_dict.get('severity', 'info'),
        message=message,
        fired_at=datetime.utcnow(),
    )
    sa.session.add(record)
    sa.session.commit()
    return {"success": True, "detail": "Alert logged"}


def _execute_webhook(action_dict, context):
    """Webhook stub -- logs intent without making HTTP call."""
    logger.info(f"Webhook stub: would POST to {action_dict.get('url', 'unknown')}")
    return {"success": True, "detail": "Webhook stub (Phase 4)"}
