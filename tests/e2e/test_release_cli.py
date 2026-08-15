import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from maintainerflow.cli.app import app

pytestmark = pytest.mark.e2e


def fixture(path: Path) -> None:
    pulls = [
        {
            "github_id": 100 + number,
            "number": number,
            "title": f"{'feat' if number % 2 else 'fix'}: change {number}",
            "url": f"https://github.test/owner/repo/pull/{number}",
            "author": "alice" if number % 3 else "dependabot[bot]",
            "body": "BREAKING CHANGE: confirm API" if number == 7 else "",
            "labels": ["feature", "docs"] if number == 1 else [],
            "changed_files": [f"src/file_{number}.py"],
        }
        for number in range(1, 13)
    ]
    path.write_text(
        json.dumps(
            {
                "repository": "owner/repo",
                "from_ref": "v0.4.0",
                "to_ref": "v1.0.0",
                "compare_url": "https://github.test/owner/repo/compare/v0.4.0...v1.0.0",
                "pull_requests": pulls,
            }
        ),
        encoding="utf-8",
    )


def test_release_preview_export_replay_is_deterministic_and_never_publishes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "release.json"
    first_file = tmp_path / "first.md"
    second_file = tmp_path / "second.md"
    fixture(source)
    runner = CliRunner()

    first = runner.invoke(app, ["release", "--input", str(source)])
    replay = runner.invoke(app, ["release", "--input", str(source)])
    export_one = runner.invoke(
        app, ["release", "--input", str(source), "--output", str(first_file)]
    )
    export_two = runner.invoke(
        app, ["release", "--input", str(source), "--output", str(second_file)]
    )
    rejected_publish = runner.invoke(app, ["release", "--input", str(source), "--publish"])

    assert first.exit_code == replay.exit_code == export_one.exit_code == export_two.exit_code == 0
    assert first.stdout == replay.stdout == first_file.read_text(encoding="utf-8")
    assert first_file.read_bytes() == second_file.read_bytes()
    assert "Breaking-change candidates" in first.stdout
    assert "dependabot" not in first.stdout.split("## Contributors", 1)[1]
    assert rejected_publish.exit_code == 2
    assert "intentionally unavailable" in rejected_publish.output
