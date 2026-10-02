import logging
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
import httpx
from ..models import Location, WeatherFacts

logger = logging.getLogger(__name__)


class UpstreamWeatherError(Exception):
    """Raised when an external weather/geocoding service fails or returns invalid data."""
    pass


class AmbiguousLocationError(Exception):
    """Raised when a city name is ambiguous across distinct countries."""
    pass


# Clean UTF-8 Indic and multilingual city mappings for Indian states & languages
INDIC_CITY_MAP: dict[str, str] = {
    # Hindi / Marathi
    "भोपाल": "Bhopal", "भोपाळ": "Bhopal",
    "पुणे": "Pune", "पुणा": "Pune",
    "मुंबई": "Mumbai", "मुम्बई": "Mumbai",
    "दिल्ली": "Delhi", "नई दिल्ली": "New Delhi",
    "जयपुर": "Jaipur", "जयपूर": "Jaipur",
    "बेंगलुरु": "Bengaluru", "बैंगलोर": "Bengaluru", "बंगळुरू": "Bengaluru",
    "चेन्नई": "Chennai", "मद्रास": "Chennai",
    "कोलकाता": "Kolkata", "कलकत्ता": "Kolkata",
    "हैदराबाद": "Hyderabad",
    "अहमदाबाद": "Ahmedabad",
    "लखनऊ": "Lucknow",
    "चंडीगढ़": "Chandigarh",
    "इंदौर": "Indore", "इंदूर": "Indore",
    "नागपुर": "Nagpur", "नागपूर": "Nagpur",
    "वाराणसी": "Varanasi", "काशी": "Varanasi",
    "गोवा": "Goa",
    "पटना": "Patna",

    # Telugu
    "భోపాల్": "Bhopal",
    "పూణే": "Pune", "పుణె": "Pune",
    "ముంబై": "Mumbai",
    "ఢిల్లీ": "Delhi", "న్యూఢిల్లీ": "New Delhi",
    "జైపూర్": "Jaipur",
    "బెంగళూరు": "Bengaluru", "బెంగళూర్": "Bengaluru",
    "చెన్నై": "Chennai",
    "కోల్‌కతా": "Kolkata", "కోల్కతా": "Kolkata",
    "హైదరాబాద్": "Hyderabad",
    "విశాఖపట్నం": "Visakhapatnam", "వైజాగ్": "Visakhapatnam",
    "విజయవాడ": "Vijayawada",
    "తిరుపతి": "Tirupati",
    "వరంగల్": "Warangal",
    "గుంటూరు": "Guntur",

    # Tamil
    "போபால்": "Bhopal",
    "புனே": "Pune",
    "மும்பை": "Mumbai",
    "தில்லி": "Delhi", "புது தில்லி": "New Delhi",
    "ஜெய்ப்பூர்": "Jaipur",
    "பெங்களூரு": "Bengaluru", "பெங்களூர்": "Bengaluru",
    "சென்னை": "Chennai",
    "கொல்கத்தா": "Kolkata",
    "ஹைதராபாத்": "Hyderabad",
    "மதுரை": "Madurai",
    "கோயம்புத்தூர்": "Coimbatore",

    # Kannada
    "ಭೋಪಾಲ್": "Bhopal",
    "ಪುಣೆ": "Pune",
    "ಮುಂಬೈ": "Mumbai",
    "ದೆಹಲಿ": "Delhi",
    "ಜೈಪುರ": "Jaipur",
    "ಬೆಂಗಳೂರು": "Bengaluru",
    "ಚೆನ್ನೈ": "Chennai",
    "ಕೋಲ್ಕತ್ತಾ": "Kolkata",
    "ಹೈದರಾಬಾದ್": "Hyderabad",
    "ಮೈಸೂರು": "Mysuru",

    # Malayalam
    "ഭോപ്പാൽ": "Bhopal",
    "പൂനെ": "Pune",
    "മുംബൈ": "Mumbai",
    "ഡൽഹി": "Delhi",
    "ജയ്‌പൂർ": "Jaipur",
    "ബംഗളൂരു": "Bengaluru",
    "ചെന്നൈ": "Chennai",
    "കൊൽക്കത്ത": "Kolkata",
    "ഹൈദരാബാദ്": "Hyderabad",
    "കൊച്ചി": "Kochi",
    "തിരുവനന്തപുരം": "Thiruvananthapuram",

    # Bengali
    "ভোপাল": "Bhopal",
    "পুনে": "Pune",
    "মুম্বাই": "Mumbai",
    "দিল্লি": "Delhi",
    "জয়পুর": "Jaipur",
    "বেঙ্গালুরু": "Bengaluru",
    "চেন্নাই": "Chennai",
    "কলকাতা": "Kolkata",
    "হায়দ্রাবাদ": "Hyderabad",
}


class WeatherService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._owns_client = client is None
        # Short-lived in-memory cache: key -> (timestamp, data)
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl_seconds = 180  # 3 minutes

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=9.0)
            self._owns_client = True
        return self._client

    async def close(self):
        if self._owns_client and self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _fetch_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        client = await self.get_client()
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Weather API returned non-dictionary JSON")
                return data
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                if attempt == 0:
                    continue
        logger.warning("Failed request to %s: %s", url, repr(last_exc))
        raise UpstreamWeatherError("External weather service is temporarily unavailable") from last_exc

    async def geocode(self, query: str) -> Location | None:
        trimmed = query.strip().rstrip("?.!,:;")
        if not trimmed:
            return None

        # Check Indic mapping first
        normalized = INDIC_CITY_MAP.get(trimmed, trimmed)

        cache_key = f"geo:{normalized.lower()}"
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and (now - cached[0] < self._cache_ttl_seconds):
            return cached[1]

        data = await self._fetch_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": normalized, "count": 6, "language": "en", "format": "json"},
        )

        results = data.get("results")
        if not results or not isinstance(results, list):
            return None

        # Open-Meteo ranks search results by relevance and population descending.
        exact_matches = [
            r for r in results
            if isinstance(r, dict) and str(r.get("name", "")).strip().casefold() == normalized.casefold()
        ]
        distinct_countries = sorted({
            str(r.get("country", "")).strip()
            for r in exact_matches
            if r.get("country")
        })

        item = results[0]
        if len(distinct_countries) > 1:
            india_match = next((r for r in exact_matches if str(r.get("country")).lower() == "india"), None)
            pop0 = exact_matches[0].get("population") or 0
            pop1 = exact_matches[1].get("population") or 0 if len(exact_matches) > 1 else 0

            if india_match and (india_match.get("population") or 0) > 5000:
                item = india_match
            elif pop0 > 50000 and (pop1 == 0 or pop0 >= pop1 * 2):
                item = exact_matches[0]
            elif pop0 == pop1:
                raise AmbiguousLocationError(", ".join(distinct_countries))
        try:
            loc = Location(
                name=str(item["name"]),
                country=str(item.get("country", "")),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
            )
            self._cache[cache_key] = (now, loc)
            return loc
        except (KeyError, TypeError, ValueError) as err:
            raise UpstreamWeatherError("Location service returned malformed coordinates") from err

    async def forecast(self, location: Location, time_reference: str = "today") -> WeatherFacts:
        cache_key = f"wx:{round(location.latitude, 3)}:{round(location.longitude, 3)}:{time_reference.lower()}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and (now - cached[0] < self._cache_ttl_seconds):
            return cached[1]

        data = await self._fetch_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "temperature_2m,wind_speed_10m,precipitation,weather_code",
                "hourly": "temperature_2m,wind_speed_10m,precipitation,precipitation_probability,uv_index,weather_code",
                "forecast_days": 2,
                "timezone": "auto",
            },
        )

        timezone_name = data.get("timezone", "UTC")
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = ZoneInfo("UTC")

        current_block = data.get("current")
        hourly_block = data.get("hourly") or {}
        hourly_times = hourly_block.get("time") or []

        normalized_time_ref = time_reference.lower().strip()

        # If requesting current / today weather and current block exists:
        if normalized_time_ref in {"now", "today"} and isinstance(current_block, dict):
            current_time_str = str(current_block.get("time", ""))
            try:
                curr_dt = datetime.fromisoformat(current_time_str) if current_time_str else datetime.now(tz)
                # Find nearest hourly index to obtain hourly fields (e.g. uv_index, precipitation_probability)
                if hourly_times:
                    best_idx = min(
                        range(len(hourly_times)),
                        key=lambda i: abs(datetime.fromisoformat(hourly_times[i]).replace(tzinfo=tz).timestamp() - curr_dt.replace(tzinfo=tz).timestamp())
                    )
                else:
                    best_idx = None
            except Exception:
                best_idx = None

            def get_hourly_val(key: str):
                vals = hourly_block.get(key) or []
                if best_idx is not None and best_idx < len(vals):
                    return vals[best_idx]
                return None

            try:
                facts = WeatherFacts(
                    temperature_2m=current_block.get("temperature_2m"),
                    wind_speed_10m=current_block.get("wind_speed_10m"),
                    precipitation=current_block.get("precipitation"),
                    precipitation_probability=get_hourly_val("precipitation_probability"),
                    uv_index=get_hourly_val("uv_index"),
                    weather_code=current_block.get("weather_code"),
                    observed_at=current_time_str or datetime.now(tz).isoformat(),
                    timezone=timezone_name,
                    source="Open-Meteo",
                )
                self._cache[cache_key] = (now, facts)
                return facts
            except Exception as err:
                raise UpstreamWeatherError("Weather service returned invalid current condition values") from err

        # Specific target times for forecasts
        now_dt = datetime.now(tz)
        if normalized_time_ref == "tomorrow":
            target_dt = (now_dt + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        elif normalized_time_ref in {"this evening", "tonight"}:
            hour = 21 if normalized_time_ref == "tonight" else 18
            target_dt = now_dt.replace(hour=hour, minute=0, second=0)
        elif normalized_time_ref == "this afternoon":
            target_dt = now_dt.replace(hour=15, minute=0, second=0)
        else:
            target_dt = now_dt

        if not hourly_times:
            raise UpstreamWeatherError("Weather service returned empty hourly forecast array")

        try:
            target_idx = min(
                range(len(hourly_times)),
                key=lambda i: abs(datetime.fromisoformat(hourly_times[i]).replace(tzinfo=tz).timestamp() - target_dt.timestamp())
            )
        except Exception as err:
            raise UpstreamWeatherError("Could not resolve forecast target timestamp") from err

        def get_val(key: str):
            vals = hourly_block.get(key) or []
            if target_idx < len(vals):
                return vals[target_idx]
            return None

        try:
            facts = WeatherFacts(
                temperature_2m=get_val("temperature_2m"),
                wind_speed_10m=get_val("wind_speed_10m"),
                precipitation=get_val("precipitation"),
                precipitation_probability=get_val("precipitation_probability"),
                uv_index=get_val("uv_index"),
                weather_code=get_val("weather_code"),
                observed_at=hourly_times[target_idx],
                timezone=timezone_name,
                source="Open-Meteo",
            )
            self._cache[cache_key] = (now, facts)
            return facts
        except Exception as err:
            raise UpstreamWeatherError("Weather service returned invalid forecast metrics") from err
