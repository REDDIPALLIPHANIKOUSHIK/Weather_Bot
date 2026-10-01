# Offline evaluation suite

The cases in `cases.yaml` exercise routing branches that can be checked without weather network calls: missing location, unsupported activity, and an instruction that tries to override policy. Run `python evals/run.py` from the repository root. The runner disables optional model credentials for repeatability.

Weather-dependent policy decisions are covered separately with fixed facts in `backend/tests/test_policy_engine.py`; the real weather adapter's response mapping is checked with an HTTP transport fixture in `backend/tests/test_weather_service.py`. Live forecasts are intentionally not fixed regression fixtures because they change over time.

To add a case, include an ID, input prompt, and expected status. Keep adversarial cases focused on whether untrusted wording changes control flow or policy authority. Don't assert that a live forecast is safe or unsafe without a fixed weather record and reviewed SOP version.
