import json
from pathlib import Path

import pytest

from maintainerflow.analysis.diff import ParsedDiff, parse_unified_diff
from maintainerflow.analysis.risk import assess_risk
from maintainerflow.core.schemas import PullRequestSource

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks/datasets/pr-risk"
MANIFEST = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", MANIFEST["fixtures"], ids=lambda case: case["id"])
def test_static_risk_fixture(case: dict[str, object]) -> None:
    source = PullRequestSource.model_validate_json(
        (DATASET / str(case["path"])).read_text(encoding="utf-8")
    )
    parsed = parse_unified_diff(source.diff)
    if source.changed_files:
        parsed = ParsedDiff(
            parsed.files or source.changed_files,
            max(parsed.additions, sum(item.additions for item in source.changed_files)),
            max(parsed.deletions, sum(item.deletions for item in source.changed_files)),
            parsed.truncated,
            parsed.limitations,
        )
    result = assess_risk(parsed)
    assert result.risk.level.value in case["levels"]
    if expected := case.get("evidence"):
        assert expected in {item.kind for item in result.evidence}


def test_critical_paths_are_not_low() -> None:
    for fixture in ("05-authentication.json", "06-migration.json"):
        source = PullRequestSource.model_validate_json(
            (DATASET / "fixtures" / fixture).read_text(encoding="utf-8")
        )
        assert assess_risk(parse_unified_diff(source.diff)).risk.level.value == "high"
