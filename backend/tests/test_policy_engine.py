from pathlib import Path
from app.services import evaluate_policies, load_sops, evaluate_condition

def test_external_sops_cover_required_categories_and_count():
    sops = load_sops()
    assert len(sops) >= 12
    assert {s["category"] for s in sops} >= {"outdoor_exercise", "travel", "vulnerable_groups", "leisure"}
    assert all(s["version"] == 1 and s["required_weather_fields"] for s in sops)

def test_generic_engine_evaluates_boolean_conditions():
    condition = {"all": [{"field":"temperature_2m","operator":"gte","value":30},{"not":{"field":"weather_code","operator":"eq","value":0}}]}
    assert evaluate_condition(condition, {"temperature_2m":31,"weather_code":3})[0]
    assert not evaluate_condition(condition, {"temperature_2m":31,"weather_code":0})[0]

def test_sop_can_be_added_without_engine_changes(tmp_path: Path):
    config = tmp_path / "sops.yaml"
    config.write_text("version: 1\nsops:\n  - id: ADDED-013\n    title: Added by config\n    category: leisure\n    activities: [picnic]\n    severity: HIGH\n    priority: 99\n    conditions: {field: wind_speed_10m, operator: gt, value: 10}\n    guidance: [Choose another time.]\n", encoding="utf-8")
    result = evaluate_policies(load_sops(config), {"activity":"picnic", "wind_speed_10m":12})
    assert result.sop_id == "ADDED-013"

def test_highest_severity_wins_with_priority_tiebreak():
    sops = load_sops()
    result = evaluate_policies(sops, {"activity":"cycling", "wind_speed_10m":45, "temperature_2m":40, "precipitation_probability":75, "uv_index":2})
    assert result.outcome == "matched"
    assert result.sop_id == "WB-001"

def test_no_policy_result_does_not_create_guidance():
    result = evaluate_policies(load_sops(), {"activity":"cycling", "temperature_2m":20, "wind_speed_10m":5, "precipitation":0, "precipitation_probability":0, "uv_index":1, "weather_code":0})
    assert result.outcome == "no_match"
    assert result.guidance == []

def test_unknown_conditions_are_not_assumed_true():
    passed, detail = evaluate_condition({"field":"uv_index","operator":"gte","value":8}, {"uv_index":None})
    assert not passed and "unavailable" in detail
