import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evals.run_evals import run_evaluations


@pytest.mark.asyncio
async def test_full_evaluation_benchmarks():
    results = await run_evaluations()
    assert len(results) >= 10

    for r in results:
        # Every test must either PASS or be an honest SKIPPED (only permitted for live severe probe if no severe event is live)
        assert r["status"] in {"PASS", "SKIPPED"}, f"Evaluation {r['id']} ({r['name']}) failed: {r}"
