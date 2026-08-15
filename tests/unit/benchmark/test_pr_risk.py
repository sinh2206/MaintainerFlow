import json
from dataclasses import replace

import pytest

from benchmarks.runners.compare import run_comparison, stable_projection
from benchmarks.runners.pr_risk import (
    DEFAULT_MANIFEST,
    STRATEGIES,
    AIOnly,
    Hybrid,
    HybridHistory,
    StaticOnly,
    load_manifest,
)

REPORT = DEFAULT_MANIFEST.parents[2] / "reports/pr-risk-v2.0.0.json"


def test_manifest_is_versioned_licensed_fixed_and_has_ground_truth() -> None:
    manifest, cases = load_manifest()

    assert manifest["schema_version"] == "pr-risk-manifest-v2"
    assert manifest["dataset_version"] == "2.0.0"
    assert manifest["license"] == "CC0-1.0"
    assert "Synthetic" in manifest["source"]
    assert len(cases) == 60
    assert {
        split: sum(case.split == split for case in cases)
        for split in {
            "train",
            "validation",
            "test",
        }
    } == {"train": 15, "validation": 15, "test": 30}
    assert all(case.ground_truth.risk for case in cases)
    assert all(case.ground_truth.review_priority for case in cases)
    assert len({case.identifier for case in cases}) == len(cases)


def test_strategies_are_deterministic_bounded_and_do_not_read_ground_truth() -> None:
    _, cases = load_manifest()
    case = cases[-3]
    altered_truth = replace(case.ground_truth, risk="low", review_priority="low")
    altered = replace(case, ground_truth=altered_truth)

    for strategy in STRATEGIES:
        first = strategy.predict(case)
        assert first == strategy.predict(case)
        assert first == strategy.predict(altered), f"{strategy.name} leaked benchmark labels"
        assert 0 <= first.high_risk_probability <= 1


def test_strategy_interface_covers_four_required_ablations() -> None:
    assert [strategy.name for strategy in STRATEGIES] == [
        "Static-only",
        "AI-only",
        "Hybrid",
        "Hybrid+History",
    ]
    assert isinstance(STRATEGIES[0], StaticOnly)
    assert isinstance(STRATEGIES[1], AIOnly)
    assert isinstance(STRATEGIES[2], Hybrid)
    assert isinstance(STRATEGIES[3], HybridHistory)


def test_comparison_measures_quality_calibration_cost_latency_and_hybrid_benefit() -> None:
    report = run_comparison()

    assert report["evaluation"] == {"split": "test", "sample_count": 30}
    for result in report["strategies"].values():
        metrics = result["metrics"]
        assert {
            "risk_macro_f1",
            "review_priority_accuracy",
            "high_risk_false_positives",
            "high_risk_false_negatives",
            "brier_score",
            "expected_calibration_error",
            "accepted_evidence_suggestions",
            "rejected_evidence_suggestions",
        } <= metrics.keys()
        assert result["latency"]["p95_ms"] >= 0
        assert result["cost"]["estimated_total_usd"] >= 0

    comparison = report["comparison"]
    assert comparison["requirement_met"] is True
    assert comparison["hybrid_macro_f1_gain_over_best_single_strategy"] > 0
    assert comparison["hybrid_false_negative_reduction_vs_static"] > 0
    assert comparison["history_false_negative_reduction_vs_hybrid"] > 0


def test_stable_projection_is_reproducible_and_report_excludes_raw_cases() -> None:
    first = run_comparison()
    second = run_comparison()

    assert stable_projection(first) == stable_projection(second)
    serialized = json.dumps(first).lower()
    assert '"title"' not in serialized
    assert '"body"' not in serialized
    assert '"diff"' not in serialized
    assert "api_key" not in serialized
    assert "private_key" not in serialized
    assert first["reproducibility"]["model_variance"]
    assert first["reproducibility"]["cost_variance"]


def test_committed_versioned_report_matches_current_deterministic_metrics() -> None:
    committed = json.loads(REPORT.read_text(encoding="utf-8"))
    current = run_comparison()

    assert stable_projection(committed) == stable_projection(current)


def test_manifest_loader_rejects_too_small_dataset(tmp_path) -> None:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    manifest["cases"] = manifest["cases"][:49]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="at least 50"):
        load_manifest(path)
