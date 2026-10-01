"""Small offline graph evaluations; cases needing weather never call external services."""
import asyncio
import os
import sys
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.graph import workflow

async def main():
    # Offline branch checks exercise the deterministic local intent fallback.
    os.environ.pop("OPENAI_API_KEY", None)
    cases = yaml.safe_load(Path(__file__).with_name("cases.yaml").read_text(encoding="utf-8"))["cases"]
    failures = 0
    for case in cases:
        result = await workflow.ainvoke({"session_id": "eval-"+case["id"], "message":case["prompt"], "trace":[]})
        passed = result["status"] == case["expected_status"]
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {result['status']}")
        failures += not passed
    return failures

if __name__ == "__main__": raise SystemExit(asyncio.run(main()))
