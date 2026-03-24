# TODO: Remove legacy /api/ routes in Phase 5 after frontend migrates to /api/v1/
# All new API development should use mqttui/routes/api_v1.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import logging

from mqttui import state
from mqttui import extensions as ext

bp = Blueprint('api', __name__)


@bp.route('/api/messages')
def get_message_history():
    """Get paginated message history with enhanced filtering"""
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
                json_value=json_value
            )
            total_count = ext.db.get_message_count(topic_filter=topic_filter, since=since)
        else:
            messages_list = list(reversed(state.messages))
            if topic_filter:
                messages_list = [m for m in messages_list if m['topic'] == topic_filter]
            if content_search:
                messages_list = [m for m in messages_list if content_search.lower() in m['payload'].lower()]

            total_count = len(messages_list)
            messages_list = messages_list[offset:offset + limit]

        return jsonify({
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
                'hours': hours
            }
        })

    except Exception as e:
        logging.error(f"Error getting message history: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/topics')
def get_topic_list():
    """Get list of all topics with statistics"""
    try:
        if ext.db:
            topics_list = ext.db.get_topics()
        else:
            topics_list = [{'topic': topic} for topic in sorted(state.topics)]

        return jsonify({'topics': topics_list})

    except Exception as e:
        logging.error(f"Error getting topics: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/database/stats')
def get_database_stats():
    """Get database size and statistics"""
    try:
        if ext.db:
            stats = ext.db.get_database_size()
            stats['enabled'] = True
        else:
            stats = {
                'enabled': False,
                'message_count': len(state.messages),
                'topic_count': len(state.topics)
            }

        return jsonify(stats)

    except Exception as e:
        logging.error(f"Error getting database stats: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/database/cleanup', methods=['POST'])
def cleanup_database():
    """Clean up old database records"""
    try:
        if not ext.db:
            return jsonify({'error': 'Database not enabled'}), 400

        from flask import current_app
        days = int(request.json.get('days', current_app.config['DB_CLEANUP_DAYS']))
        deleted = ext.db.cleanup_old_data(days)

        return jsonify({
            'success': True,
            'deleted_messages': deleted,
            'days': days
        })

    except Exception as e:
        logging.error(f"Error cleaning database: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/filter-presets')
def get_filter_presets():
    """Get all saved filter presets"""
    try:
        if not ext.db:
            return jsonify({'error': 'Database not enabled'}), 400

        presets = ext.db.get_filter_presets()
        return jsonify({'presets': presets})

    except Exception as e:
        logging.error(f"Error getting filter presets: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/filter-presets', methods=['POST'])
def save_filter_preset():
    """Save a new filter preset"""
    try:
        if not ext.db:
            return jsonify({'error': 'Database not enabled'}), 400

        data = request.json
        name = data.get('name')
        description = data.get('description', '')
        filters = data.get('filters', {})

        if not name or not filters:
            return jsonify({'error': 'Name and filters are required'}), 400

        success = ext.db.save_filter_preset(name, filters, description)

        if success:
            return jsonify({'success': True, 'message': f'Saved preset: {name}'})
        else:
            return jsonify({'error': 'Failed to save preset'}), 500

    except Exception as e:
        logging.error(f"Error saving filter preset: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/filter-presets/<name>', methods=['DELETE'])
def delete_filter_preset(name):
    """Delete a filter preset"""
    try:
        if not ext.db:
            return jsonify({'error': 'Database not enabled'}), 400

        success = ext.db.delete_filter_preset(name)

        if success:
            return jsonify({'success': True, 'message': f'Deleted preset: {name}'})
        else:
            return jsonify({'error': 'Preset not found'}), 404

    except Exception as e:
        logging.error(f"Error deleting filter preset: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/filter-presets/<name>/use', methods=['POST'])
def use_filter_preset(name):
    """Load and use a filter preset"""
    try:
        if not ext.db:
            return jsonify({'error': 'Database not enabled'}), 400

        filters = ext.db.use_filter_preset(name)

        if filters:
            return jsonify({'success': True, 'filters': filters})
        else:
            return jsonify({'error': 'Preset not found'}), 404

    except Exception as e:
        logging.error(f"Error using filter preset: {e}")
        return jsonify({'error': str(e)}), 500
