"""Tests for the condition evaluator pure function."""
import pytest
from mqttui.rules.evaluator import evaluate, ConditionError


def test_simple_gt_true():
    """Greater-than returns True when actual > value."""
    assert evaluate({"path": "temperature", "op": "gt", "value": 30}, {"temperature": 35}) is True


def test_simple_gt_false():
    """Greater-than returns False when actual < value."""
    assert evaluate({"path": "temperature", "op": "gt", "value": 30}, {"temperature": 25}) is False


def test_nested_path_eq():
    """Dot-notation path resolves nested dicts."""
    condition = {"path": "sensors.outdoor.temp", "op": "eq", "value": 22}
    payload = {"sensors": {"outdoor": {"temp": 22}}}
    assert evaluate(condition, payload) is True


def test_compound_all_true():
    """Compound 'all' returns True when all sub-conditions match."""
    condition = {"all": [
        {"path": "temp", "op": "gt", "value": 20},
        {"path": "temp", "op": "lt", "value": 40},
    ]}
    assert evaluate(condition, {"temp": 30}) is True


def test_compound_all_false():
    """Compound 'all' returns False when any sub-condition fails."""
    condition = {"all": [
        {"path": "temp", "op": "gt", "value": 20},
        {"path": "temp", "op": "lt", "value": 25},
    ]}
    assert evaluate(condition, {"temp": 30}) is False


def test_compound_any_true():
    """Compound 'any' returns True when at least one sub-condition matches."""
    condition = {"any": [
        {"path": "status", "op": "eq", "value": "on"},
        {"path": "status", "op": "eq", "value": "active"},
    ]}
    assert evaluate(condition, {"status": "active"}) is True


def test_compound_any_false():
    """Compound 'any' returns False when no sub-condition matches."""
    condition = {"any": [
        {"path": "status", "op": "eq", "value": "on"},
        {"path": "status", "op": "eq", "value": "active"},
    ]}
    assert evaluate(condition, {"status": "off"}) is False


def test_contains():
    """Contains checks substring in string value."""
    assert evaluate({"path": "name", "op": "contains", "value": "sensor"}, {"name": "temp_sensor_1"}) is True


def test_not_contains():
    """Not-contains checks absence of substring."""
    assert evaluate({"path": "name", "op": "not_contains", "value": "xyz"}, {"name": "abc"}) is True


def test_regex_match():
    """Regex operator matches patterns."""
    assert evaluate({"path": "topic", "op": "regex", "value": r"^sensor_\d+"}, {"topic": "sensor_42"}) is True


def test_regex_no_match():
    """Regex returns False when pattern doesn't match."""
    assert evaluate({"path": "topic", "op": "regex", "value": r"^sensor_\d+"}, {"topic": "device_42"}) is False


def test_exists_true():
    """Exists returns True when path is present (even if value is falsy)."""
    assert evaluate({"path": "temp", "op": "exists"}, {"temp": 0}) is True


def test_exists_false():
    """Exists returns False when path is missing."""
    assert evaluate({"path": "missing", "op": "exists"}, {"temp": 0}) is False


def test_not_exists_true():
    """Not-exists returns True when path is missing."""
    assert evaluate({"path": "missing", "op": "not_exists"}, {"temp": 0}) is True


def test_not_exists_false():
    """Not-exists returns False when path is present."""
    assert evaluate({"path": "temp", "op": "not_exists"}, {"temp": 0}) is False


def test_non_json_payload_returns_false():
    """Non-dict payload returns False for path-based conditions."""
    assert evaluate({"path": "temp", "op": "gt", "value": 30}, None) is False


def test_numeric_coercion():
    """String numbers are coerced for numeric comparisons."""
    assert evaluate({"path": "temp", "op": "gt", "value": 30}, {"temp": "35"}) is True


def test_numeric_coercion_lt():
    """String numbers coerced for less-than."""
    assert evaluate({"path": "temp", "op": "lt", "value": 30}, {"temp": "25"}) is True


def test_empty_condition_always_true():
    """Empty condition dict means always match."""
    assert evaluate({}, {"temp": 30}) is True


def test_none_condition_always_true():
    """None condition means always match."""
    assert evaluate(None, {"temp": 30}) is True


def test_unknown_operator_raises():
    """Unknown operator raises ConditionError."""
    with pytest.raises(ConditionError, match="Unknown operator"):
        evaluate({"path": "x", "op": "unknown_op", "value": 1}, {"x": 1})


def test_eq_operator():
    """Equality check."""
    assert evaluate({"path": "x", "op": "eq", "value": 5}, {"x": 5}) is True
    assert evaluate({"path": "x", "op": "eq", "value": 5}, {"x": 6}) is False


def test_ne_operator():
    """Not-equal check."""
    assert evaluate({"path": "x", "op": "ne", "value": 5}, {"x": 6}) is True
    assert evaluate({"path": "x", "op": "ne", "value": 5}, {"x": 5}) is False


def test_gte_operator():
    """Greater-than-or-equal check."""
    assert evaluate({"path": "x", "op": "gte", "value": 5}, {"x": 5}) is True
    assert evaluate({"path": "x", "op": "gte", "value": 5}, {"x": 4}) is False


def test_lte_operator():
    """Less-than-or-equal check."""
    assert evaluate({"path": "x", "op": "lte", "value": 5}, {"x": 5}) is True
    assert evaluate({"path": "x", "op": "lte", "value": 5}, {"x": 6}) is False


def test_missing_path_returns_false():
    """Missing path in payload returns False (not an error)."""
    assert evaluate({"path": "missing.deep.path", "op": "eq", "value": 1}, {"x": 1}) is False
