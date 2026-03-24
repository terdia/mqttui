"""Pure-function condition evaluator for the rules engine.

Evaluates structured JSON conditions against message payloads.
No side effects, no database access -- purely functional.
"""
import re


class ConditionError(Exception):
    """Raised when a condition is malformed or uses an unknown operator."""
    pass


def _get_path(data, path):
    """Resolve a dot-notation path in a nested dict.

    Args:
        data: dict to traverse
        path: dot-separated path string (e.g. "sensors.outdoor.temp")

    Returns:
        The value at the path.

    Raises:
        KeyError: if any segment is missing
        TypeError: if a non-dict is encountered mid-path
    """
    segments = path.split('.')
    current = data
    for segment in segments:
        current = current[segment]
    return current


def _coerce_numeric(actual, expected):
    """Coerce actual to numeric type if expected is numeric and actual is a string.

    Handles sensor payloads like {"temp": "28"} where values arrive as strings.
    """
    if isinstance(expected, (int, float)) and isinstance(actual, str):
        try:
            return float(actual)
        except (ValueError, TypeError):
            return actual
    return actual


def evaluate(condition, payload):
    """Evaluate a condition dict against a payload dict.

    Args:
        condition: dict describing the condition. Supports:
            - Simple: {"path": "temp", "op": "gt", "value": 30}
            - Compound: {"all": [...conditions]} or {"any": [...conditions]}
            - Empty/None: always matches (returns True)
        payload: dict of the parsed message payload, or None for non-JSON.

    Returns:
        bool: True if condition matches, False otherwise.

    Raises:
        ConditionError: if an unknown operator is used.
    """
    # Empty or None condition = always match
    if not condition:
        return True

    # Compound conditions
    if 'all' in condition:
        return all(evaluate(c, payload) for c in condition['all'])
    if 'any' in condition:
        return any(evaluate(c, payload) for c in condition['any'])

    path = condition.get('path')
    op = condition.get('op')
    value = condition.get('value')

    # Existence checks don't need the actual value resolved first
    if op == 'exists':
        if not isinstance(payload, dict):
            return False
        try:
            _get_path(payload, path)
            return True
        except (KeyError, TypeError):
            return False

    if op == 'not_exists':
        if not isinstance(payload, dict):
            return True
        try:
            _get_path(payload, path)
            return False
        except (KeyError, TypeError):
            return True

    # All other ops require resolving the path value
    if not isinstance(payload, dict):
        return False

    try:
        actual = _get_path(payload, path)
    except (KeyError, TypeError):
        return False

    # Numeric coercion for comparison operators
    if op in ('gt', 'lt', 'gte', 'lte'):
        actual = _coerce_numeric(actual, value)

    if op == 'eq':
        return actual == value
    elif op == 'ne':
        return actual != value
    elif op == 'gt':
        return actual > value
    elif op == 'lt':
        return actual < value
    elif op == 'gte':
        return actual >= value
    elif op == 'lte':
        return actual <= value
    elif op == 'contains':
        return str(value) in str(actual)
    elif op == 'not_contains':
        return str(value) not in str(actual)
    elif op == 'regex':
        return bool(re.search(str(value), str(actual)))
    else:
        raise ConditionError(f"Unknown operator: {op}")
