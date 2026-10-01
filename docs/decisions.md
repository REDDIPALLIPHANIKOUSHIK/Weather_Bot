# Engineering decisions

- **LangGraph:** makes the missing-location, geocoding failure, weather failure, matched-policy and no-policy routes explicit and traceable.
- **Deterministic policy evaluation:** reproducible thresholds and conditions are the authority for safety outcomes; language understanding cannot override them.
- **External SOP configuration:** policy additions belong in YAML and are evaluated by a generic condition interpreter. The test suite adds a new policy without changing code.
- **Open-Meteo:** provides no-key geocoding and forecast endpoints, keeping local setup simple. Its returned values and timestamp remain the source of truth.
- **FastAPI:** offers async upstream calls, request validation and an independently deployable API with a small footprint.
- **Session memory:** this take-home needs conversational follow-ups but not account persistence. The current in-process map has no cross-session sharing and resets on restart.
- **No vector database:** twelve concise structured policies need category/activity filtering, not semantic document retrieval infrastructure.
- **LLM boundary:** when configured, OpenAI returns strict JSON Schema output; other OpenAI-compatible services return JSON that Pydantic validates. Provider keys stay on the backend. Without a key, conservative local extraction works. The extraction model cannot choose policy or weather facts; answer language is assembled only from validated weather and the winning SOP.
- **Hallucination control:** weather service errors stop the graph; unsupported activities and no-match conditions do not produce generic advice; citations must exist in the candidate set; measured facts are copied from response state.
- **Multiple policies:** every activity candidate is evaluated. The highest severity wins, then explicit priority breaks ties. Policy IDs do not appear in engine control flow.
- **Latency and failures:** async HTTP uses an 8-second timeout and one retry. Failures return concise statuses without exposing response bodies or secrets.
- **Time phrases:** today/now, afternoon, evening, tonight and tomorrow choose a forecast hour. The forecast is a snapshot for the selected hour, not an hourly itinerary.

## Known design limits

Intent parsing supports a deliberately small activity vocabulary, location prepositions, and a handful of time phrases. Session state is process-local; deploy one backend process or replace the store with a TTL-backed shared store before horizontal scaling. SOP thresholds are illustrative product policies and require review by a qualified domain owner before real-world use.
