from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class CurrentLocation(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy: float | None = Field(default=None, ge=0.0, le=100000.0)
    timestamp: str | None = Field(default=None, max_length=100)
    city_name: str | None = Field(default=None, max_length=200)


class Location(BaseModel):
    name: str
    country: str = ""
    latitude: float
    longitude: float


class WeatherFacts(BaseModel):
    temperature_2m: float | None = None
    wind_speed_10m: float | None = None
    precipitation: float | None = None
    precipitation_probability: float | None = None
    uv_index: float | None = None
    weather_code: int | None = None
    observed_at: str
    timezone: str
    source: str = "Open-Meteo"


class SOPDefinition(BaseModel):
    id: str
    title: str
    category: str
    activities: list[str]
    severity: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    priority: int
    conditions: dict[str, Any]
    guidance: list[str]
    required_weather_fields: list[str] = Field(default_factory=list)
    version: int = 1


class PolicyResult(BaseModel):
    outcome: Literal["matched", "no_match", "insufficient_data"]
    sop_id: str | None = None
    title: str | None = None
    severity: str | None = None
    priority: int | None = None
    guidance: list[str] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    current_location: CurrentLocation | None = None

    @field_validator("message")
    @classmethod
    def message_cannot_be_blank(cls, val: str) -> str:
        trimmed = val.strip()
        if not trimmed:
            raise ValueError("Message cannot be blank or whitespace only")
        return trimmed


class ChatResponse(BaseModel):
    answer: str
    status: str
    location: Location | None = None
    weather: WeatherFacts | None = None
    policy: PolicyResult | None = None
    trace: list[str] = Field(default_factory=list)


class VoiceSessionRequest(BaseModel):
    language: str = Field(default="en-IN")


class VoiceSessionResponse(BaseModel):
    mode: Literal["gemini_live", "fallback"]
    model: str | None = None
    ws_url: str | None = None
    language: str = "en-IN"
    instructions: str | None = None
