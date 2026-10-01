import pytest
from pydantic import ValidationError
from app.llm import StructuredIntent

def test_structured_intent_rejects_activity_category_mismatch():
    value = StructuredIntent(activity="cycling", category="travel", location="Bhopal", time_reference="today", intent="safety_advisory")
    with pytest.raises(ValueError):
        value.validate_domain()

def test_structured_intent_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        StructuredIntent.model_validate({"activity":"cycling", "category":"outdoor_exercise", "location":"Bhopal", "time_reference":"today", "intent":"safety_advisory", "safe":True})
