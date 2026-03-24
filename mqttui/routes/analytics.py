"""Analytics REST API blueprint.

Provides per-topic message rate and numeric payload histogram data.
All endpoints return JSON envelope: {"status": "success"|"error", "data": ..., "error": ...}
"""

from flask import Blueprint, request
from flask_login import login_required
import logging

from mqttui.helpers import api_success, api_error
from mqttui.analytics import get_analytics

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/v1/analytics')
logger = logging.getLogger(__name__)


@analytics_bp.route('/topics')
@login_required
def get_topics():
    """Get top-N topic analytics sorted by message rate.

    Query params:
        limit (int): Maximum topics to return (default 20)
        window (int): Rate window in seconds (default 60)

    Returns:
        JSON envelope with topics array and window_seconds.
    """
    limit = request.args.get('limit', 20, type=int)
    window = request.args.get('window', 60, type=int)

    analytics = get_analytics()
    topics = analytics.get_all_stats(limit=limit)

    return api_success({
        "topics": topics,
        "window_seconds": window,
    })


@analytics_bp.route('/topics/<path:topic>')
@login_required
def get_topic(topic):
    """Get analytics for a single topic.

    Uses path converter to support MQTT topics with slashes (e.g., home/sensor/temp).

    Returns:
        JSON envelope with topic stats or 404 if no data.
    """
    analytics = get_analytics()
    stats = analytics.get_topic_stats(topic)

    if stats["message_count"] == 0:
        return api_error("Topic not found", "NOT_FOUND", 404)

    return api_success(stats)
