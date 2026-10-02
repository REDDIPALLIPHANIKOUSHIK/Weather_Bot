import pytest
from app.services.intent import parse_intent_locally


def test_intent_activity_and_location():
    intent = parse_intent_locally("Is it safe to cycle in Bhopal today?")
    assert intent.activity == "cycling"
    assert intent.category == "outdoor_exercise"
    assert intent.location_text == "Bhopal"
    assert intent.time_reference == "today"
    assert intent.use_current_location is False


def test_intent_current_location():
    intent = parse_intent_locally("Is it safe to walk here today?")
    assert intent.activity == "walking"
    assert intent.use_current_location is True

    # Telugu current location marker
    intent_te = parse_intent_locally("ఇక్కడ నడవడం సురక్షితమేనా?")
    assert intent_te.activity == "walking"
    assert intent_te.use_current_location is True

    # Hindi current location marker
    intent_hi = parse_intent_locally("क्या यहाँ साइकिल चलाना सुरक्षित है?")
    assert intent_hi.activity == "cycling"
    assert intent_hi.use_current_location is True


def test_intent_followup_with_context():
    # Context holds previous activity and location
    context = {"activity": "cycling", "location_text": "Chennai"}
    followup_intent = parse_intent_locally("What about this evening?", session_context=context)

    assert followup_intent.activity == "cycling"
    assert followup_intent.location_text == "Chennai"
    assert followup_intent.time_reference == "this evening"


def test_unsupported_activity():
    intent = parse_intent_locally("Is it good weather for scuba diving in Goa?")
    assert intent.activity is None
    assert intent.category is None
