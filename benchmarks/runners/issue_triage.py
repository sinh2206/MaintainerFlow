import json
from pathlib import Path
from typing import Any, cast

from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.issue.classifier import classify_issue
from maintainerflow.issue.duplicate import LexicalDuplicateEngine
from maintainerflow.issue.schemas import IssueSource

BENCHMARKS = Path(__file__).parents[1]
CLASSIFICATION = BENCHMARKS / "datasets/issue-classification/manifest.json"
DUPLICATES = BENCHMARKS / "datasets/duplicate-issues/manifest.json"
LABELS = ("bug", "feature", "docs", "question", "maintenance")
REPOSITORY = RepositoryRef(github_id=1, owner="benchmark", name="fixture")


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _classification_metrics(cases: list[dict[str, Any]]) -> dict[str, float]:
    pairs = [
        (str(case["label"]), classify_issue(str(case["title"]), str(case["body"])).category)
        for case in cases
        if case["split"] == "test"
    ]
    scores = []
    for label in LABELS:
        true_positive = sum(expected == predicted == label for expected, predicted in pairs)
        false_positive = sum(
            expected != label and predicted == label for expected, predicted in pairs
        )
        false_negative = sum(
            expected == label and predicted != label for expected, predicted in pairs
        )
        precision = true_positive / (true_positive + false_positive) if true_positive else 0
        recall = true_positive / (true_positive + false_negative) if true_positive else 0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return {"macro_f1": round(sum(scores) / len(scores), 4), "test_cases": float(len(pairs))}


def _source(identifier: int, value: dict[str, Any]) -> IssueSource:
    return IssueSource(
        repository=REPOSITORY,
        github_id=identifier,
        number=identifier,
        title=str(value["title"]),
        body=str(value.get("body", "")),
        url=f"https://benchmark.invalid/issues/{identifier}",
    )


def _duplicate_metrics(cases: list[dict[str, Any]]) -> dict[str, float]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    engine = LexicalDuplicateEngine()
    for offset, case in enumerate(item for item in cases if item["split"] == "test"):
        query = _source(100_000 + offset, case["query"])
        candidates = tuple(_source(int(item["id"]), item) for item in case["candidates"])
        ranked = engine.rank(query, candidates, top_k=3, min_score=0)
        expected = {int(item) for item in case["duplicate_ids"]}
        ranks = [index for index, item in enumerate(ranked, 1) if item.github_id in expected]
        recalls.append(float(bool(ranks)))
        reciprocal_ranks.append(1 / ranks[0] if ranks else 0)
    return {
        "recall_at_3": round(sum(recalls) / len(recalls), 4),
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
        "test_queries": float(len(recalls)),
    }


def run_benchmark() -> dict[str, Any]:
    classification = _load(CLASSIFICATION)
    duplicates = _load(DUPLICATES)
    return {
        "dataset_versions": {
            "classification": classification["dataset_version"],
            "duplicates": duplicates["dataset_version"],
        },
        "classification": _classification_metrics(classification["cases"]),
        "duplicates": _duplicate_metrics(duplicates["cases"]),
    }


def render_markdown(metrics: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Issue Triage Benchmark",
            "",
            f"- Classification Macro-F1: `{metrics['classification']['macro_f1']:.4f}`",
            f"- Duplicate Recall@3: `{metrics['duplicates']['recall_at_3']:.4f}`",
            f"- Duplicate MRR: `{metrics['duplicates']['mrr']:.4f}`",
            "",
        ]
    )


def main() -> int:
    metrics = run_benchmark()
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return int(
        metrics["classification"]["macro_f1"] < 0.8 or metrics["duplicates"]["recall_at_3"] < 0.75
    )


if __name__ == "__main__":
    raise SystemExit(main())
