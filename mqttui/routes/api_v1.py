"""Versioned API v1 endpoints for MQTTUI.

All endpoints return JSON envelope: {"status": "success"|"error", "data": ..., "error": ...}
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging

from mqttui import __version__
from mqttui import state
from mqttui import extensions as ext
from mqttui.extensions import sa, limiter
from mqttui.helpers import api_success, api_error

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@api_v1_bp.route('/messages')
@login_required
def get_messages():
    """Get paginated message history with filtering.
    ---
    get:
      summary: Retrieve MQTT messages
      parameters:
        - name: limit
          in: query
          schema: {type: integer, default: 100}
        - name: offset
          in: query
          schema: {type: integer, default: 0}
        - name: topic
          in: query
          schema: {type: string}
        - name: hours
          in: query
          schema: {type: integer}
        - name: content
          in: query
          schema: {type: string}
        - name: regex_topic
          in: query
          schema: {type: string}
        - name: json_path
          in: query
          schema: {type: string}
        - name: json_value
          in: query
          schema: {type: string}
      responses:
        200:
          description: Paginated message list
    """
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))

        topic_filter = request.args.get('topic')
        hours = request.args.get('hours')
        content_search = request.args.get('content')
        regex_topic = request.args.get('regex_topic')
        json_path = request.args.get('json_path')
        json_value = request.args.get('json_value')

        since = None
        if hours:
            since = datetime.now() - timedelta(hours=int(hours))

        if ext.db:
            messages_list = ext.db.get_messages(
                limit=limit,
                offset=offset,
                topic_filter=topic_filter,
                since=since,
                content_search=content_search,
                regex_topic=regex_topic,
                json_path=json_path,
                json_value=json_value,
            )
            total_count = ext.db.get_message_count(
                topic_filter=topic_filter, since=since
            )
        else:
            messages_list = list(reversed(state.messages))
            if topic_filter:
                messages_list = [m for m in messages_list if m['topic'] == topic_filter]
            if content_search:
                messages_list = [
                    m for m in messages_list
                    if content_search.lower() in m['payload'].lower()
                ]
            total_count = len(messages_list)
            messages_list = messages_list[offset:offset + limit]

        return api_success({
            'messages': messages_list,
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + len(messages_list) < total_count,
            'filters_applied': {
                'topic': topic_filter,
                'content': content_search,
                'regex_topic': regex_topic,
                'json_path': json_path,
                'json_value': json_value,
                'hours': hours,
            }
        })
    except Exception as e:
        logger.error(f"Error getting message history: {e}")
        return api_error(str(e), "MESSAGES_ERROR", 500)


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

@api_v1_bp.route('/topics')
@login_required
def get_topics():
    """Get list of all topics with statistics.
    ---
    get:
      summary: List MQTT topics
      responses:
        200:
          description: Topic list
    """
    try:
        if ext.db:
            topics_list = ext.db.get_topics()
        else:
            topics_list = [{'topic': topic} for topic in sorted(state.topics)]

        return api_success({'topics': topics_list})
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        return api_error(str(e), "TOPICS_ERROR", 500)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@api_v1_bp.route('/database/stats')
@login_required
def get_database_stats():
    """Get database size and statistics.
    ---
    get:
      summary: Database statistics
      responses:
        200:
          description: Database stats
    """
    try:
        if ext.db:
            stats = ext.db.get_database_size()
            stats['enabled'] = True
        else:
            stats = {
                'enabled': False,
                'message_count': len(state.messages),
                'topic_count': len(state.topics),
            }
        return api_success(stats)
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return api_error(str(e), "DB_STATS_ERROR", 500)


@api_v1_bp.route('/database/cleanup', methods=['POST'])
@login_required
def cleanup_database():
    """Clean up old database records.
    ---
    post:
      summary: Cleanup old messages
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                days:
                  type: integer
                  default: 30
      responses:
        200:
          description: Cleanup result
    """
    try:
        if not ext.db:
            return api_error("Database not enabled", "DB_DISABLED", 400)

        days = int(request.json.get('days', current_app.config['DB_CLEANUP_DAYS']))
        deleted = ext.db.cleanup_old_data(days)

        return api_success({'deleted_messages': deleted, 'days': days})
    except Exception as e:
        logger.error(f"Error cleaning database: {e}")
        return api_error(str(e), "DB_CLEANUP_ERROR", 500)


# ---------------------------------------------------------------------------
# Filter Presets
# ---------------------------------------------------------------------------

@api_v1_bp.route('/filter-presets')
@login_required
def get_filter_presets():
    """Get all saved filter presets.
    ---
    get:
      summary: List filter presets
      responses:
        200:
          description: Preset list
    """
    try:
        if not ext.db:
            return api_error("Database not enabled", "DB_DISABLED", 400)

        presets = ext.db.get_filter_presets()
        return api_success({'presets': presets})
    except Exception as e:
        logger.error(f"Error getting filter presets: {e}")
        return api_error(str(e), "PRESETS_ERROR", 500)


@api_v1_bp.route('/filter-presets', methods=['POST'])
@login_required
def save_filter_preset():
    """Save a new filter preset.
    ---
    post:
      summary: Create filter preset
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                description:
                  type: string
                filters:
                  type: object
      responses:
        201:
          description: Preset saved
    """
    try:
        if not ext.db:
            return api_error("Database not enabled", "DB_DISABLED", 400)

        data = request.json
        name = data.get('name')
        description = data.get('description', '')
        filters = data.get('filters', {})

        if not name or not filters:
            return api_error("Name and filters are required", "VALIDATION_ERROR", 400)

        success = ext.db.save_filter_preset(name, filters, description)

        if success:
            return api_success({'message': f'Saved preset: {name}'}, 201)
        else:
            return api_error("Failed to save preset", "PRESET_SAVE_FAILED", 500)
    except Exception as e:
        logger.error(f"Error saving filter preset: {e}")
        return api_error(str(e), "PRESETS_ERROR", 500)


@api_v1_bp.route('/filter-presets/<name>', methods=['DELETE'])
@login_required
def delete_filter_preset(name):
    """Delete a filter preset.
    ---
    delete:
      summary: Delete a filter preset
      parameters:
        - name: name
          in: path
          required: true
          schema: {type: string}
      responses:
        200:
          description: Preset deleted
        404:
          description: Preset not found
    """
    try:
        if not ext.db:
            return api_error("Database not enabled", "DB_DISABLED", 400)

        success = ext.db.delete_filter_preset(name)

        if success:
            return api_success({'message': f'Deleted preset: {name}'})
        else:
            return api_error("Preset not found", "NOT_FOUND", 404)
    except Exception as e:
        logger.error(f"Error deleting filter preset: {e}")
        return api_error(str(e), "PRESETS_ERROR", 500)


@api_v1_bp.route('/filter-presets/<name>/use', methods=['POST'])
@login_required
def use_filter_preset(name):
    """Load and use a filter preset.
    ---
    post:
      summary: Use a filter preset
      parameters:
        - name: name
          in: path
          required: true
          schema: {type: string}
      responses:
        200:
          description: Preset filters
        404:
          description: Preset not found
    """
    try:
        if not ext.db:
            return api_error("Database not enabled", "DB_DISABLED", 400)

        filters = ext.db.use_filter_preset(name)

        if filters:
            return api_success({'filters': filters})
        else:
            return api_error("Preset not found", "NOT_FOUND", 404)
    except Exception as e:
        logger.error(f"Error using filter preset: {e}")
        return api_error(str(e), "PRESETS_ERROR", 500)


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

@api_v1_bp.route('/publish', methods=['POST'])
@login_required
@limiter.limit("30/minute")
def publish_message():
    """Publish an MQTT message (JSON API).
    ---
    post:
      summary: Publish MQTT message
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [topic, message]
              properties:
                topic:
                  type: string
                message:
                  type: string
      responses:
        200:
          description: Message published
    """
    try:
        data = request.json
        if not data:
            return api_error("JSON body required", "VALIDATION_ERROR", 400)

        topic = data.get('topic')
        message = data.get('message')

        if not topic or message is None:
            return api_error("topic and message are required", "VALIDATION_ERROR", 400)

        from mqttui.mqtt_client import publish as mqtt_publish
        mqtt_publish(topic, message)

        return api_success({'published': True})
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return api_error(str(e), "PUBLISH_ERROR", 500)


# ---------------------------------------------------------------------------
# Stats & Version
# ---------------------------------------------------------------------------

@api_v1_bp.route('/stats')
@login_required
def get_stats():
    """Get application statistics.
    ---
    get:
      summary: Application statistics
      responses:
        200:
          description: Stats
    """
    try:
        return api_success({
            'connection_count': state.connection_count,
            'topic_count': len(state.topics),
            'message_count': len(state.messages),
            'errors': state.error_log,
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return api_error(str(e), "STATS_ERROR", 500)


@api_v1_bp.route('/version')
def get_version():
    """Get application version.
    ---
    get:
      summary: App version
      responses:
        200:
          description: Version info
    """
    return api_success({'version': __version__})


# ---------------------------------------------------------------------------
# OpenAPI Documentation
# ---------------------------------------------------------------------------

@api_v1_bp.route('/docs')
def api_docs():
    """Serve Swagger UI for API documentation."""
    html = """<!DOCTYPE html>
<html><head><title>MQTTUI API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: '/api/v1/openapi.json', dom_id: '#swagger-ui'})</script>
</body></html>"""
    return html


@api_v1_bp.route('/openapi.json')
def openapi_spec():
    """Return OpenAPI 3.0 specification."""
    from apispec import APISpec
    from apispec_webframeworks.flask import FlaskPlugin

    spec = APISpec(
        title="MQTTUI API",
        version="1.0.0",
        openapi_version="3.0.3",
        info={"description": "MQTT monitoring and automation API"},
        plugins=[FlaskPlugin()],
    )
    # Register paths from current app's url_map
    with current_app.test_request_context():
        for rule in current_app.url_map.iter_rules():
            if rule.rule.startswith('/api/v1/') and rule.endpoint != 'static':
                view = current_app.view_functions.get(rule.endpoint)
                if view:
                    spec.path(view=view, app=current_app)
    return jsonify(spec.to_dict())


# ---------------------------------------------------------------------------
# Token CRUD
# ---------------------------------------------------------------------------

@api_v1_bp.route('/auth/token', methods=['GET'])
@login_required
def get_token():
    """Get current user's API token.
    ---
    get:
      summary: Get API token
      security: [{session: []}, {apiKey: []}]
      responses:
        200: {description: Current token}
    """
    return api_success({"api_token": current_user.api_token})


@api_v1_bp.route('/auth/token', methods=['POST'])
@login_required
def regenerate_token():
    """Regenerate API token.
    ---
    post:
      summary: Regenerate API token
      responses:
        200: {description: New token generated}
    """
    token = current_user.generate_api_token()
    sa.session.commit()
    return api_success({"api_token": token})


@api_v1_bp.route('/auth/token', methods=['DELETE'])
@login_required
def revoke_token():
    """Revoke API token.
    ---
    delete:
      summary: Revoke API token
      responses:
        200: {description: Token revoked}
    """
    current_user.api_token = None
    sa.session.commit()
    return api_success({"message": "API token revoked"})


# ---------------------------------------------------------------------------
# Blueprint error handlers
# ---------------------------------------------------------------------------

@api_v1_bp.errorhandler(404)
def handle_404(e):
    return api_error("Resource not found", "NOT_FOUND", 404)


@api_v1_bp.errorhandler(500)
def handle_500(e):
    return api_error("Internal server error", "INTERNAL_ERROR", 500)
