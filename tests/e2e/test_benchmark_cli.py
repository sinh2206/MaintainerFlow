import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from maintainerflow.cli.app import app

pytestmark = pytest.mark.e2e


def test_benchmark_cli_runs_all_suites_exports_markdown_and_rejects_invalid_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAINTAINERFLOW_GEMINI_API_KEY", "benchmark-secret-sentinel")
    runner = CliRunner()
    report = runner.invoke(app, ["benchmark", "--suite", "all", "--format", "json"])
    output = tmp_path / "benchmark.md"
    markdown = runner.invoke(
        app,
        [
            "benchmark",
            "--suite",
            "all",
            "--format",
            "markdown",
            "--output",
            str(output),
        ],
    )
    invalid = runner.invoke(app, ["benchmark", "--split", "future"])

    assert report.exit_code == markdown.exit_code == 0
    payload = json.loads(report.stdout)
    assert payload["schema_version"] == "maintainerflow-benchmark-v1"
    assert payload["pr_risk"]["evaluation"] == {"sample_count": 30, "split": "test"}
    assert payload["pr_risk"]["comparison"]["requirement_met"] is True
    assert payload["issue_triage"]["classification"]["macro_f1"] >= 0.8
    assert payload["issue_triage"]["duplicates"]["recall_at_3"] >= 0.75
    serialized = report.stdout.lower()
    assert "benchmark-secret-sentinel" not in serialized
    assert "# PR Risk Benchmark" in output.read_text(encoding="utf-8")
    assert "# Issue Triage Benchmark" in output.read_text(encoding="utf-8")
    assert invalid.exit_code == 2
