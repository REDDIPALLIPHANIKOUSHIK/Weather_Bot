import pytest
from app.policy import evaluate_condition, evaluate_policies, load_sops


def test_evaluate_condition_operators():
    facts = {
        "temperature_2m": 35.5,
        "wind_speed_10m": 42.0,
        "precipitation": 3.0,
        "weather_code": 65,
        "tags": ["outdoor", "summer"],
    }

    # gte
    res, _ = evaluate_condition({"field": "wind_speed_10m", "operator": "gte", "value": 40}, facts)
    assert res is True

    # lt
    res, _ = evaluate_condition({"field": "wind_speed_10m", "operator": "lt", "value": 40}, facts)
    assert res is False

    # in
    res, _ = evaluate_condition({"field": "weather_code", "operator": "in", "value": [61, 63, 65]}, facts)
    assert res is True

    # all
    all_cond = {
        "all": [
            {"field": "temperature_2m", "operator": "gt", "value": 30},
            {"field": "wind_speed_10m", "operator": "gte", "value": 40},
        ]
    }
    res, _ = evaluate_condition(all_cond, facts)
    assert res is True

    # not
    not_cond = {"not": {"field": "precipitation", "operator": "gt", "value": 5}}
    res, _ = evaluate_condition(not_cond, facts)
    assert res is True


def test_sop_match_and_priority(loaded_sops):
    # WB-001: wind_speed_10m >= 40 for cycling -> HIGH
    facts_high_wind = {
        "temperature_2m": 25.0,
        "wind_speed_10m": 45.0,
        "precipitation": 0.0,
        "precipitation_probability": 10.0,
        "uv_index": 4.0,
    }
    result = evaluate_policies(loaded_sops, "cycling", facts_high_wind)
    assert result.outcome == "matched"
    assert result.sop_id == "WB-001"
    assert result.severity == "HIGH"
    assert len(result.guidance) > 0

    # For running: WB-005 (CRITICAL, temp >= 40, priority 100) vs WB-002 (MODERATE, precip >= 2, priority 55)
    # Both triggers are present, CRITICAL WB-005 must win!
    facts_running_extreme = {
        "temperature_2m": 42.0,
        "wind_speed_10m": 15.0,
        "precipitation": 4.0,
        "precipitation_probability": 80.0,
        "uv_index": 5.0,
    }
    result2 = evaluate_policies(loaded_sops, "running", facts_running_extreme)
    assert result2.outcome == "matched"
    assert result2.sop_id == "WB-005"
    assert result2.severity == "CRITICAL"
    assert result2.priority == 100


def test_no_sop_match(loaded_sops):
    facts_benign = {
        "temperature_2m": 22.0,
        "wind_speed_10m": 10.0,
        "precipitation": 0.0,
        "precipitation_probability": 10.0,
        "uv_index": 3.0,
        "weather_code": 1,
    }
    # Cycling has no active restriction policy under calm 22C conditions
    result = evaluate_policies(loaded_sops, "cycling", facts_benign)
    assert result.outcome == "no_match"
    assert result.sop_id is None


def test_insufficient_weather_data(loaded_sops):
    # Missing wind_speed_10m needed for WB-001
    facts_missing = {
        "temperature_2m": 22.0,
        "precipitation": 0.0,
    }
    result = evaluate_policies(loaded_sops, "cycling", facts_missing)
    assert result.outcome == "insufficient_data"


def test_unsupported_activity_in_policy_engine(loaded_sops):
    facts = {"temperature_2m": 25.0, "wind_speed_10m": 15.0}
    result = evaluate_policies(loaded_sops, "stargazing", facts)
    assert result.outcome == "no_match"
