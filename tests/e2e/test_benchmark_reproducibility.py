import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
RUNNER = ROOT / "benchmarks/runners/compare.py"
pytestmark = pytest.mark.e2e


def _run() -> dict[str, Any]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in ("API_KEY", "PRIVATE_KEY", "TOKEN"))
    }
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--split", "test"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _stable(report: dict[str, Any]) -> dict[str, Any]:
    report.pop("environment")
    for result in report["strategies"].values():
        result.pop("latency")
    return report


def test_benchmark_two_clean_processes_have_same_samples_splits_and_metrics() -> None:
    first = _run()
    second = _run()

    assert first["evaluation"] == second["evaluation"] == {"sample_count": 30, "split": "test"}
    assert _stable(first) == _stable(second)
    assert len({result["sample_fingerprint"] for result in first["strategies"].values()}) == 1
    assert first["comparison"]["requirement_met"] is True
    assert "offline deterministic proxy" in first["reproducibility"]["model_variance"]
    assert "No charge occurred" in first["reproducibility"]["cost_variance"]
