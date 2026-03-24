"""API response helpers for consistent JSON envelope format."""

from flask import jsonify


def api_success(data=None, status_code=200):
    """Standard success envelope."""
    return jsonify({"status": "success", "data": data, "error": None}), status_code


def api_error(message, code="UNKNOWN_ERROR", status_code=400):
    """Standard error envelope."""
    return jsonify({
        "status": "error",
        "data": None,
        "error": {"code": code, "message": message}
    }), status_code
