import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import operator as op
from pathlib import Path
from typing import Any
import httpx
import yaml
from .models import Location, WeatherFacts, PolicyResult, SOPDefinition
from pydantic import ValidationError

log = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent

class UpstreamError(Exception):
    pass

class AmbiguousLocation(Exception):
    pass

class OpenMeteo:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=8.0)
        self.owns_client = client is None

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(2):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected an object response")
                return data
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
                if attempt == 0:
                    continue
        log.warning("Open-Meteo request failed: %s", type(last).__name__)
        raise UpstreamError("Weather service is temporarily unavailable") from last

    async def geocode(self, query: str) -> Location | None:
        data = await self._get("https://geocoding-api.open-meteo.com/v1/search", {"name": query, "count": 5, "language": "en", "format": "json"})
        results = data.get("results") or []
        if not results:
            return None
        exact = [r for r in results if isinstance(r, dict) and str(r.get("name", "")).casefold() == query.casefold()]
        countries = sorted({str(r.get("country", "")) for r in exact if r.get("country")})
        if len(countries) > 1:
            raise AmbiguousLocation(", ".join(countries))
        # Open-Meteo ranks results; return the best match and disclose country in the UI.
        item = results[0]
        try:
            return Location(name=item["name"], country=item.get("country", ""), latitude=item["latitude"], longitude=item["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UpstreamError("Location service returned an invalid result") from exc

    async def forecast(self, location: Location, time_reference: str = "today") -> WeatherFacts:
        data = await self._get("https://api.open-meteo.com/v1/forecast", {
            "latitude": location.latitude, "longitude": location.longitude,
            "hourly": "temperature_2m,wind_speed_10m,precipitation,precipitation_probability,uv_index,weather_code",
            "forecast_days": 2, "timezone": "auto",
        })
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        zone = data.get("timezone", "UTC")
        now = datetime.now(ZoneInfo(zone))
        target = now
        if time_reference == "tomorrow": target = (now + timedelta(days=1)).replace(hour=12, minute=0)
        elif time_reference in {"this evening", "tonight"}: target = now.replace(hour=21 if time_reference == "tonight" else 18, minute=0)
        elif time_reference == "this afternoon": target = now.replace(hour=15, minute=0)
        # Pick the nearest forecast hour; only actual API values are returned.
        try:
            index = min(range(len(times)), key=lambda i: abs(datetime.fromisoformat(times[i]).replace(tzinfo=ZoneInfo(zone)).timestamp() - target.timestamp())) if times else 0
        except (ValueError, KeyError) as exc:
            raise UpstreamError("Weather service returned an invalid forecast") from exc
        def at(key):
            values = hourly.get(key) or []
            return values[index] if index < len(values) else None
        try:
            return WeatherFacts(temperature_2m=at("temperature_2m"), wind_speed_10m=at("wind_speed_10m"),
                precipitation=at("precipitation"), weather_code=at("weather_code"),
                precipitation_probability=at("precipitation_probability"), uv_index=at("uv_index"), observed_at=times[index] if times else "", timezone=zone)
        except ValidationError as exc:
            raise UpstreamError("Weather service returned invalid weather facts") from exc

def load_sops(path: Path | None = None) -> list[dict[str, Any]]:
    # Vercel builds the backend as an independent service, so its bundle keeps
    # a copy under backend/config. Local development uses the canonical root
    # config/sops.yaml. Both paths are anchored to this module, never cwd.
    if path is not None:
        source = path
    else:
        source = next(
            (candidate for candidate in (
                BACKEND_ROOT / "config" / "sops.yaml",
                REPOSITORY_ROOT / "config" / "sops.yaml",
            ) if candidate.is_file()),
            REPOSITORY_ROOT / "config" / "sops.yaml",
        )
    with source.open(encoding="utf-8") as f:
        value = yaml.safe_load(f)
    if not isinstance(value, dict) or not isinstance(value.get("sops"), list):
        raise ValueError("SOP configuration must contain a sops list")
    def fields(condition: dict[str, Any]) -> set[str]:
        if "field" in condition:
            return {condition["field"]}
        combined = set()
        for key in ("all", "any"):
            for child in condition.get(key, []): combined.update(fields(child))
        if "not" in condition: combined.update(fields(condition["not"]))
        return combined
    definitions = []
    for entry in value["sops"]:
        entry.setdefault("version", value.get("version", 1))
        entry.setdefault("required_weather_fields", sorted(fields(entry["conditions"])))
        definitions.append(SOPDefinition.model_validate(entry).model_dump())
    return definitions

OPS = {"eq": op.eq, "neq": op.ne, "gt": op.gt, "gte": op.ge, "lt": op.lt, "lte": op.le, "in": lambda a,b: a in b, "contains": lambda a,b: b in a}

def evaluate_condition(condition: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, str]:
    if "all" in condition:
        results = [evaluate_condition(c, facts) for c in condition["all"]]
        return all(x[0] for x in results), "all(" + "; ".join(x[1] for x in results) + ")"
    if "any" in condition:
        results = [evaluate_condition(c, facts) for c in condition["any"]]
        return any(x[0] for x in results), "any(" + "; ".join(x[1] for x in results) + ")"
    if "not" in condition:
        passed, detail = evaluate_condition(condition["not"], facts)
        return not passed, f"not({detail})"
    field, rule = condition["field"], condition
    actual = facts.get(field)
    if actual is None:
        return False, f"{field} unavailable"
    func = OPS.get(rule["operator"])
    if func is None:
        raise ValueError(f"Unsupported condition operator: {rule['operator']}")
    try:
        passed = bool(func(actual, rule["value"]))
    except (TypeError, ValueError):
        passed = False
    return passed, f"{field} {rule['operator']} {rule['value']} => {passed}"

def evaluate_policies(sops: list[dict[str, Any]], facts: dict[str, Any]) -> PolicyResult:
    evaluated = []
    trace = []
    severities = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}
    for sop in sops:
        if facts.get("activity") not in sop.get("activities", []):
            continue
        passed, detail = evaluate_condition(sop["conditions"], facts)
        trace.append({"sop_id": sop["id"], "matched": passed, "detail": detail})
        if passed:
            evaluated.append(sop)
    if not evaluated:
        missing = any("unavailable" in item["detail"] for item in trace)
        return PolicyResult(outcome="insufficient_data" if missing else "no_match", trace=trace)
    winner = max(evaluated, key=lambda s: (severities.get(s["severity"], 0), s.get("priority", 0)))
    return PolicyResult(outcome="matched", sop_id=winner["id"], title=winner["title"], severity=winner["severity"], priority=winner["priority"], guidance=winner["guidance"], trace=trace)
