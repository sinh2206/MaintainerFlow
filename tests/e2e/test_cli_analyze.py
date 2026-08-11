import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from maintainerflow.cli.app import app
from maintainerflow.core.schemas import AnalysisResult

ROOT = Path(__file__).parents[2]
DATASET = ROOT / "benchmarks/datasets/pr-risk"


@pytest.mark.e2e
def test_cli_analyzes_entire_manifest_without_github_token() -> None:
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    runner = CliRunner()
    matched = 0
    for case in manifest["fixtures"]:
        result = runner.invoke(app, ["analyze", "--input", str(DATASET / case["path"])])
        assert result.exit_code == 0, result.output
        report = AnalysisResult.model_validate_json(result.stdout)
        matched += report.risk.level.value in case["levels"]
        if expected := case.get("evidence"):
            assert expected in {item.kind for item in report.evidence}
        if expected_status := case.get("status"):
            assert report.status.value == expected_status
    assert matched >= 9
