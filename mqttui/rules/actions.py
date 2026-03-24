"""Action executor for the rules engine.

Handles publish, log, and webhook action types.
Webhook delivery uses httpx in a thread pool for non-blocking HTTP POST.
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Module-level thread pool for webhook delivery (non-blocking)
_webhook_executor = ThreadPoolExecutor(max_workers=4)


def execute_action(action_dict, context):
    """Execute a rule action.

    Args:
        action_dict: parsed action JSON with 'type' key.
            - type 'publish': publishes MQTT message with __source marker
            - type 'log': creates AlertHistory record in database
            - type 'webhook': HTTP POST with retry in thread pool
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
    elif action_type == 'telegram':
        return _execute_telegram(action_dict, context)
    elif action_type == 'slack':
        return _execute_slack(action_dict, context)
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
    """Submit webhook delivery to thread pool for async execution.

    Checks per-rule cooldown before submitting. If the rule is within its
    cooldown window the webhook is suppressed and an AlertHistory record
    is created with the incremented suppressed_count.

    Returns immediately with submission confirmation. Actual HTTP delivery
    happens in background thread with retry logic.
    """
    from mqttui.rules.cooldown import cooldown_tracker

    rule_id = context['rule_id']

    # Check cooldown before submitting
    if not cooldown_tracker.check(rule_id):
        suppressed_count = cooldown_tracker.get_suppressed_count(rule_id)
        cooldown_until = cooldown_tracker.get_cooldown_until(rule_id)

        # Log suppressed alert to history
        _log_suppressed_alert(
            rule_id=rule_id,
            rule_name=context['rule_name'],
            topic=context['topic'],
            url=action_dict.get('url', ''),
            suppressed_count=suppressed_count,
            cooldown_until=cooldown_until,
        )

        return {"success": True, "detail": f"Alert suppressed (cooldown), {suppressed_count} suppressed"}

    url = action_dict.get('url', '')
    payload_template = action_dict.get('payload_template')

    # Build payload
    if payload_template:
        payload_json = _build_webhook_payload(payload_template, context)
    else:
        payload_json = _build_default_payload(context)

    # Get Flask app for thread pool context
    try:
        from flask import current_app
        app = current_app._get_current_object()
    except RuntimeError:
        app = None

    # Submit to thread pool -- non-blocking
    _webhook_executor.submit(
        _deliver_webhook,
        url=url,
        payload_json=payload_json,
        rule_id=context['rule_id'],
        rule_name=context['rule_name'],
        topic=context['topic'],
        app=app,
    )

    return {"success": True, "detail": "Webhook delivery submitted"}


def _build_default_payload(context):
    """Build the default webhook JSON payload."""
    return {
        "topic": context.get('topic', ''),
        "payload": context.get('payload', ''),
        "rule_name": context.get('rule_name', ''),
        "timestamp": datetime.utcnow().isoformat(),
        "mqttui_source": True,
    }


def _build_webhook_payload(template, context):
    """Build webhook payload from a template string with {{variable}} substitution.

    Supports: {{topic}}, {{payload}}, {{rule_name}}, {{timestamp}}

    Args:
        template: JSON string with {{variable}} placeholders.
        context: dict with rule_id, rule_name, topic, payload.

    Returns:
        Parsed dict from the substituted template.
    """
    substitutions = {
        '{{topic}}': str(context.get('topic', '')),
        '{{payload}}': str(context.get('payload', '')),
        '{{rule_name}}': str(context.get('rule_name', '')),
        '{{timestamp}}': datetime.utcnow().isoformat(),
    }

    result = template
    for placeholder, value in substitutions.items():
        result = result.replace(placeholder, value)

    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"raw": result}


def _deliver_webhook(url, payload_json, rule_id, rule_name, topic,
                     max_retries=3, _sleep_fn=None, app=None):
    """Deliver webhook HTTP POST with retry logic.

    Args:
        url: Destination URL for the POST request.
        payload_json: Dict payload to send as JSON.
        rule_id: Rule ID for AlertHistory logging.
        rule_name: Rule name for AlertHistory logging.
        topic: MQTT topic that triggered the rule.
        max_retries: Maximum retry attempts on 5xx/connection errors.
        _sleep_fn: Override sleep function for testing (default: time.sleep).
        app: Flask app instance for creating app context in thread pool.

    Returns:
        dict with 'success' bool and 'detail' string.
    """
    from mqttui.rules.models import AlertHistory
    from mqttui.extensions import sa
    from mqttui.events import alert_triggered

    # Push app context for this thread (thread pool workers have none)
    ctx = None
    if app is not None:
        ctx = app.app_context()
        ctx.push()

    sleep_fn = _sleep_fn or time.sleep
    last_status = None
    last_error = None
    retries = 0

    for attempt in range(1 + max_retries):
        try:
            response = httpx.post(url, json=payload_json, timeout=10.0)
            last_status = response.status_code

            if 200 <= response.status_code < 300:
                # Success
                _log_webhook_history(
                    sa, rule_id, rule_name, topic, url,
                    http_status=response.status_code,
                    retry_count=attempt,
                )
                alert_triggered.send(
                    'webhook',
                    alert_id=None,
                    rule_id=rule_id,
                    message=f"Webhook delivered to {url}",
                )
                try:
                    from mqttui.routes.metrics import WEBHOOK_DELIVERIES
                    WEBHOOK_DELIVERIES.labels(status='success').inc()
                except Exception:
                    pass
                logger.info(f"Webhook delivered: rule={rule_name} url={url} status={response.status_code}")
                if ctx is not None:
                    ctx.pop()
                return {"success": True, "detail": f"Webhook delivered (HTTP {response.status_code})"}

            elif 400 <= response.status_code < 500:
                # Client error -- no retry
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"Webhook client error: rule={rule_name} url={url} status={response.status_code}")
                _log_webhook_history(
                    sa, rule_id, rule_name, topic, url,
                    http_status=response.status_code,
                    retry_count=0,
                    error_detail=last_error,
                )
                if ctx is not None:
                    ctx.pop()
                return {"success": False, "detail": last_error}

            else:
                # 5xx or other -- retry
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                retries = attempt
                if attempt < max_retries:
                    backoff = 5 ** attempt  # 1s, 5s, 25s
                    logger.info(f"Webhook retry {attempt + 1}/{max_retries}: rule={rule_name} backoff={backoff}s")
                    sleep_fn(backoff)

        except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
            last_error = str(e)
            retries = attempt
            if attempt < max_retries:
                backoff = 5 ** attempt
                logger.info(f"Webhook retry {attempt + 1}/{max_retries}: rule={rule_name} error={e}")
                sleep_fn(backoff)

    # Exhausted retries
    _log_webhook_history(
        sa, rule_id, rule_name, topic, url,
        http_status=last_status,
        retry_count=retries,
        error_detail=last_error,
    )
    try:
        from mqttui.routes.metrics import WEBHOOK_DELIVERIES
        WEBHOOK_DELIVERIES.labels(status='failure').inc()
    except Exception:
        pass
    logger.error(f"Webhook failed after {retries} retries: rule={rule_name} url={url}")
    if ctx is not None:
        ctx.pop()
    return {"success": False, "detail": f"Webhook failed after {retries} retries: {last_error}"}


def _execute_telegram(action_dict, context):
    """Send a Telegram message via Bot API.

    Converts to a webhook action targeting the Telegram Bot API, then delegates
    to _execute_webhook for cooldown, retry, alert history, and metrics.
    """
    bot_token = action_dict.get('bot_token', '')
    chat_id = action_dict.get('chat_id', '')
    template = action_dict.get('message_template',
                               '🔔 *MQTT Alert*\n*Rule:* {{rule_name}}\n*Topic:* `{{topic}}`\n*Payload:* `{{payload}}`')

    if not bot_token or not chat_id:
        return {"success": False, "detail": "Telegram requires bot_token and chat_id"}

    # Substitute placeholders
    message = _substitute_template(template, context)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload_template = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

    # Delegate to webhook with full cooldown + retry + alert logging
    return _execute_webhook({'url': url, 'payload_template': payload_template}, context)


def _execute_slack(action_dict, context):
    """Send a Slack message via incoming webhook URL.

    Converts to a webhook action, then delegates to _execute_webhook for
    cooldown, retry, alert history, and metrics.
    """
    webhook_url = action_dict.get('webhook_url', '')
    template = action_dict.get('message_template',
                               '🔔 *MQTT Alert*\n>*Rule:* {{rule_name}}\n>*Topic:* `{{topic}}`\n>*Payload:* `{{payload}}`')

    if not webhook_url:
        return {"success": False, "detail": "Slack requires webhook_url"}

    message = _substitute_template(template, context)
    payload_template = json.dumps({"text": message})

    return _execute_webhook({'url': webhook_url, 'payload_template': payload_template}, context)


def _substitute_template(template, context):
    """Replace {{variable}} placeholders in a template string."""
    result = template
    for placeholder, value in {
        '{{topic}}': str(context.get('topic', '')),
        '{{payload}}': str(context.get('payload', '')),
        '{{rule_name}}': str(context.get('rule_name', '')),
        '{{timestamp}}': datetime.utcnow().isoformat(),
    }.items():
        result = result.replace(placeholder, value)
    return result


def _log_suppressed_alert(rule_id, rule_name, topic, url,
                          suppressed_count, cooldown_until):
    """Create an AlertHistory record for a suppressed (cooldown) alert."""
    from mqttui.rules.models import AlertHistory
    from mqttui.extensions import sa

    try:
        record = AlertHistory(
            rule_id=rule_id,
            rule_name=rule_name,
            topic=topic,
            severity='info',
            message=f"Webhook to {url} suppressed (cooldown)",
            fired_at=datetime.utcnow(),
            webhook_url=url,
            suppressed_count=suppressed_count,
            cooldown_until=cooldown_until,
        )
        sa.session.add(record)
        sa.session.commit()
    except Exception as e:
        logger.error(f"Failed to log suppressed alert: {e}")
        try:
            sa.session.rollback()
        except Exception:
            pass


def _log_webhook_history(sa, rule_id, rule_name, topic, url,
                         http_status=None, retry_count=0, error_detail=None):
    """Create an AlertHistory record for webhook delivery."""
    from mqttui.rules.models import AlertHistory

    try:
        record = AlertHistory(
            rule_id=rule_id,
            rule_name=rule_name,
            topic=topic,
            severity='info' if http_status and http_status < 400 else 'error',
            message=f"Webhook to {url}",
            fired_at=datetime.utcnow(),
            webhook_url=url,
            http_status=http_status,
            retry_count=retry_count,
            error_detail=error_detail,
        )
        sa.session.add(record)
        sa.session.commit()
    except Exception as e:
        logger.error(f"Failed to log webhook history: {e}")
        try:
            sa.session.rollback()
        except Exception:
            pass
