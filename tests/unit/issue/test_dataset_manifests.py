import json
from pathlib import Path

DATASETS = Path(__file__).parents[3] / "benchmarks/datasets"


def load(name: str) -> dict[str, object]:
    return json.loads((DATASETS / name / "manifest.json").read_text(encoding="utf-8"))


def test_classification_manifest_has_fixed_licensed_ground_truth() -> None:
    manifest = load("issue-classification")
    cases = manifest["cases"]

    assert manifest["source"] and manifest["license"] and manifest["dataset_version"]
    assert isinstance(cases, list) and len(cases) >= 100
    assert {item["label"] for item in cases} == {
        "bug",
        "feature",
        "docs",
        "question",
        "maintenance",
    }
    assert {item["split"] for item in cases} == {"train", "validation", "test"}


def test_duplicate_manifest_has_positives_negatives_and_family_split() -> None:
    manifest = load("duplicate-issues")
    cases = manifest["cases"]

    assert manifest["source"] and manifest["license"] and manifest["dataset_version"]
    assert isinstance(cases, list) and len(cases) >= 20
    family_splits: dict[str, set[str]] = {}
    roles: set[str] = set()
    for case in cases:
        family_splits.setdefault(case["family"], set()).add(case["split"])
        roles.update(candidate["role"] for candidate in case["candidates"])
    assert all(len(splits) == 1 for splits in family_splits.values())
    assert roles == {"positive", "hard_negative", "negative"}
