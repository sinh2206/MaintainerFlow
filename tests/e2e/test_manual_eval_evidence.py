import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[2]
EVIDENCE = ROOT / "evaluation/manual-v1.json"
pytestmark = pytest.mark.e2e


def test_five_manually_reviewed_cases_reproduce_recorded_cli_output() -> None:
    evidence = cast(dict[str, Any], json.loads(EVIDENCE.read_text(encoding="utf-8")))
    cases = cast(list[dict[str, Any]], evidence["cases"])

    assert evidence["schema_version"] == "maintainerflow-manual-eval-v1"
    assert len(cases) == 5
    assert len({case["id"] for case in cases}) == len(cases)

    for case in cases:
        fixture = ROOT / str(case["fixture"])
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == case["input_sha256"]
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "maintainerflow",
                "analyze",
                "--input",
                str(fixture),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        actual = cast(dict[str, Any], json.loads(completed.stdout))
        expected = cast(dict[str, Any], case["manual_expectation"])
        kinds = {item["kind"] for item in actual["evidence"]}

        assert actual == case["recorded_output"], case["id"]
        assert actual["status"] == expected["status"]
        assert actual["risk"]["level"] == expected["risk_level"]
        assert set(expected["required_evidence"]) <= kinds
        assert not set(expected["forbidden_evidence"]) & kinds
        if limitation := expected["limitation_contains"]:
            assert any(limitation in value for value in actual["limitations"])
