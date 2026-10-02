from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

class CurrentLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0, le=100000)
    timestamp: str | None = Field(default=None, max_length=80)

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    current_location: CurrentLocation | None = None
    @field_validator("message")
    @classmethod
    def message_must_contain_text(cls,value:str)->str:
        value=value.strip()
        if not value: raise ValueError("Message cannot be blank")
        return value

class Location(BaseModel):
    name: str
    country: str
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
    severity: Literal["LOW","MODERATE","HIGH","CRITICAL"]
    priority: int
    conditions: dict[str,Any]
    guidance: list[str]
    required_weather_fields: list[str]
    version: int = 1

class PolicyResult(BaseModel):
    outcome: Literal["matched","no_match","insufficient_data"]
    sop_id: str | None = None
    title: str | None = None
    severity: str | None = None
    priority: int | None = None
    guidance: list[str] = Field(default_factory=list)
    trace: list[dict[str,Any]] = Field(default_factory=list)

class ChatResponse(BaseModel):
    answer: str
    status: str
    location: Location | None = None
    weather: WeatherFacts | None = None
    policy: PolicyResult | None = None
    trace: list[str] = Field(default_factory=list)
