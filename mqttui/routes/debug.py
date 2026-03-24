from flask import Blueprint, request, jsonify
import logging

bp = Blueprint('debug', __name__)


@bp.before_app_request
def debug_bar_middleware():
    from debug_bar import debug_bar
    debug_bar.start_request()
    debug_bar.record('request', 'path', request.path)
    debug_bar.record('request', 'method', request.method)


@bp.after_app_request
def after_request(response):
    from debug_bar import debug_bar
    debug_bar.record('request', 'status_code', response.status_code)
    debug_bar.end_request()
    return response


@bp.route('/debug-bar')
def get_debug_bar_data():
    from debug_bar import debug_bar
    try:
        data = debug_bar.get_data()
        return jsonify(data)
    except Exception as e:
        logging.error(f"Error fetching debug bar data: {e}")
        return jsonify({"error": "Failed to fetch debug bar data"}), 500


@bp.route('/toggle-debug-bar', methods=['POST'])
def toggle_debug_bar():
    from debug_bar import debug_bar
    if debug_bar.enabled:
        debug_bar.disable()
    else:
        debug_bar.enable()
    return jsonify(enabled=debug_bar.enabled)


@bp.route('/record-client-performance', methods=['POST'])
def record_client_performance():
    from debug_bar import debug_bar
    data = request.json
    debug_bar.record('performance', 'page_load_time', f"{data['pageLoadTime']}ms")
    debug_bar.record('performance', 'dom_ready_time', f"{data['domReadyTime']}ms")
    return jsonify(success=True)
