# Evaluation

`evals/cases.yaml` contains offline branch checks for a missing place, an unsupported activity, and an instruction attempting to bypass policy. Run `python evals/run.py` from the repository root after installing backend requirements. `backend/tests` checks the generic evaluator, YAML extension behavior, input validation, and health endpoint.

The evaluation deliberately asserts behavior and status, not a fabricated accuracy percentage. Weather-dependent behavior varies with the live forecast and should be evaluated against fixed weather facts at the policy-engine layer. Live integration checks require internet access and should record the request time, place, returned forecast hour, and API outcome. Weather can change between runs; this is not a deterministic regression fixture.

Expected results: missing location asks a follow-up; unsupported intent does not call weather; prompt injection does not bypass the same intent and SOP workflow; a new YAML SOP is recognized without evaluator changes. Failures in Open-Meteo return service-unavailable status rather than a weather claim.

## Recorded implementation run

On 2026-10-01, `python -m pytest -q` passed 16 tests and `python evals/run.py` passed all 3 offline cases. The frontend passed ESLint, TypeScript, and a Next.js 16 production build. An end-to-end live Open-Meteo query for cycling in Bhopal resolved to India and returned a 2026-10-02 00:00 local snapshot (23.3°C, 5.6 km/h wind, 0% precipitation chance, UV 0, WMO code 0); no cycling SOP matched those measured facts, so the graph returned `no_policy`. Those values document one run only and are not used as fixtures or defaults.

Limitations include English-only phrase extraction, a compact set of activities, illustrative thresholds, and no user study or domain-expert policy review. Add versioned fixed-fact cases for every material SOP change and review false positives/negatives before deployment.
