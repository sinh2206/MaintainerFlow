"""Deterministic PR-risk benchmark strategies; never calls an external model or API."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

BENCHMARKS = Path(__file__).parents[1]
DEFAULT_MANIFEST = BENCHMARKS / "datasets/pr-risk/manifest.json"
RISK_LEVELS = ("low", "medium", "high")
RISK_RANK = {level: rank for rank, level in enumerate(RISK_LEVELS)}

RiskLevel = Literal["low", "medium", "high"]
ReviewPriority = Literal["low", "normal", "high", "urgent"]


@dataclass(frozen=True)
class GroundTruth:
    risk: RiskLevel
    review_priority: ReviewPriority
    evidence: frozenset[str]
    tests: frozenset[str]


@dataclass(frozen=True)
class BenchmarkCase:
    identifier: str
    split: str
    family: str
    title: str
    body: str
    signals: frozenset[str]
    history_incidents: int
    ground_truth: GroundTruth


@dataclass(frozen=True)
class Prediction:
    risk: RiskLevel
    review_priority: ReviewPriority
    high_risk_probability: float
    evidence: frozenset[str]
    tests: frozenset[str]


class RiskStrategy(Protocol):
    name: str
    version: str
    model: str
    estimated_cost_per_case_usd: float

    def predict(self, case: BenchmarkCase) -> Prediction: ...


def _case(raw: dict[str, Any]) -> BenchmarkCase:
    truth = raw["ground_truth"]
    risk = str(truth["risk"])
    priority = str(truth["review_priority"])
    if risk not in RISK_LEVELS:
        raise ValueError(f"Invalid risk for {raw['id']}: {risk}")
    if priority not in {"low", "normal", "high", "urgent"}:
        raise ValueError(f"Invalid review priority for {raw['id']}: {priority}")
    return BenchmarkCase(
        identifier=str(raw["id"]),
        split=str(raw["split"]),
        family=str(raw["family"]),
        title=str(raw["title"]),
        body=str(raw.get("body", "")),
        signals=frozenset(str(value) for value in raw["signals"]),
        history_incidents=int(raw.get("history_incidents", 0)),
        ground_truth=GroundTruth(
            risk=risk,  # type: ignore[arg-type]
            review_priority=priority,  # type: ignore[arg-type]
            evidence=frozenset(str(value) for value in truth["evidence"]),
            tests=frozenset(str(value) for value in truth["tests"]),
        ),
    )


def load_manifest(
    path: Path = DEFAULT_MANIFEST,
) -> tuple[dict[str, Any], tuple[BenchmarkCase, ...]]:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    cases = tuple(_case(value) for value in raw["cases"])
    identifiers = [case.identifier for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("PR-risk case identifiers must be unique")
    if len(cases) < 50:
        raise ValueError("PR-risk benchmark requires at least 50 cases")
    if {case.split for case in cases} != {"train", "validation", "test"}:
        raise ValueError("PR-risk benchmark requires fixed train/validation/test splits")
    return raw, cases


def _risk(score: float) -> RiskLevel:
    if score >= 4:
        return "high"
    if score >= 1.5:
        return "medium"
    return "low"


def _probability(level: RiskLevel, *, calibrated: bool) -> float:
    if calibrated:
        return {"low": 0.05, "medium": 0.25, "high": 0.9}[level]
    return {"low": 0.12, "medium": 0.42, "high": 0.78}[level]


def _priority(level: RiskLevel, urgent: bool = False) -> ReviewPriority:
    if level == "high":
        return "urgent" if urgent else "high"
    return "normal" if level == "medium" else "low"


STATIC_EVIDENCE = {
    "docs_only": "documentation",
    "missing_tests": "missing_tests",
    "security_path": "security_change",
    "migration": "migration_change",
    "major_dependency": "major_dependency",
    "large_diff": "large_diff",
    "critical_module": "critical_module",
}
STATIC_TESTS = {
    "missing_tests": "focused_unit",
    "security_path": "authorization_negative",
    "migration": "migration_roundtrip",
    "major_dependency": "dependency_compatibility",
    "large_diff": "performance_smoke",
    "critical_module": "integration_path",
}


class StaticOnly:
    name = "Static-only"
    version = "static-proxy-v1"
    model = "none"
    estimated_cost_per_case_usd = 0.0

    def predict(self, case: BenchmarkCase) -> Prediction:
        signals = case.signals
        if "docs_only" in signals:
            level: RiskLevel = "low"
        else:
            score = (
                4 * ("security_path" in signals)
                + 4 * ("migration" in signals)
                + 3 * ("large_diff" in signals)
                + 2 * ("major_dependency" in signals)
                + 1.5 * ("critical_module" in signals)
                + 1 * ("missing_tests" in signals)
                + 0.5 * ("source_change" in signals)
            )
            level = _risk(score)
        evidence = frozenset(STATIC_EVIDENCE[value] for value in signals & STATIC_EVIDENCE.keys())
        tests = frozenset(STATIC_TESTS[value] for value in signals & STATIC_TESTS.keys())
        urgent = bool(signals & {"security_path", "migration"})
        return Prediction(
            level, _priority(level, urgent), _probability(level, calibrated=False), evidence, tests
        )


HIGH_TERMS = (
    "authorization bypass",
    "credential",
    "data loss",
    "corruption",
    "outage",
    "critical",
)
MEDIUM_TERMS = (
    "add ",
    "change ",
    "fix ",
    "implement ",
    "parser",
    "refactor",
    "support ",
    "update ",
)


class AIOnly:
    """Offline deterministic language proxy, not a claim about a hosted model."""

    name = "AI-only"
    version = "offline-language-proxy-v1"
    model = "offline-deterministic-proxy"
    estimated_cost_per_case_usd = 0.00018

    def predict(self, case: BenchmarkCase) -> Prediction:
        text = f"{case.title} {case.body}".lower()
        if any(term in text for term in HIGH_TERMS):
            level: RiskLevel = "high"
            evidence = frozenset({"semantic_severity"})
            tests = frozenset({"regression_boundary"})
        elif any(term in text for term in MEDIUM_TERMS):
            level = "medium"
            evidence = frozenset({"behavior_change"})
            tests = frozenset()
        else:
            level = "low"
            evidence = frozenset()
            tests = frozenset()
        urgent = level == "high" and any(
            term in text for term in ("authorization", "credential", "permission")
        )
        return Prediction(
            level, _priority(level, urgent), _probability(level, calibrated=False), evidence, tests
        )


def _higher(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    return left if RISK_RANK[left] >= RISK_RANK[right] else right


class Hybrid:
    name = "Hybrid"
    version = "hybrid-proxy-v1"
    model = AIOnly.model
    estimated_cost_per_case_usd = AIOnly.estimated_cost_per_case_usd

    def predict(self, case: BenchmarkCase) -> Prediction:
        static = StaticOnly().predict(case)
        semantic = AIOnly().predict(case)
        level = _higher(static.risk, semantic.risk)
        urgent = "urgent" in {static.review_priority, semantic.review_priority}
        return Prediction(
            level,
            _priority(level, urgent),
            _probability(level, calibrated=True),
            static.evidence | semantic.evidence,
            static.tests | semantic.tests,
        )


class HybridHistory:
    name = "Hybrid+History"
    version = "hybrid-history-proxy-v1"
    model = AIOnly.model
    estimated_cost_per_case_usd = 0.00020

    def predict(self, case: BenchmarkCase) -> Prediction:
        base = Hybrid().predict(case)
        level = base.risk
        evidence = base.evidence
        tests = base.tests
        if case.history_incidents:
            evidence |= {"historical_regression"}
            tests |= {"historical_regression"}
            if case.history_incidents >= 2:
                level = "high"
            elif level == "low":
                level = "medium"
        urgent = base.review_priority == "urgent" or (
            case.history_incidents >= 2 and level == "high"
        )
        return Prediction(
            level,
            _priority(level, urgent),
            _probability(level, calibrated=True),
            frozenset(evidence),
            frozenset(tests),
        )


STRATEGIES: tuple[RiskStrategy, ...] = (StaticOnly(), AIOnly(), Hybrid(), HybridHistory())


def _macro_f1(expected: Sequence[RiskLevel], predicted: Sequence[RiskLevel]) -> float:
    pairs = tuple(zip(expected, predicted, strict=True))
    scores: list[float] = []
    for label in RISK_LEVELS:
        true_positive = sum(left == right == label for left, right in pairs)
        false_positive = sum(left != label and right == label for left, right in pairs)
        false_negative = sum(left == label and right != label for left, right in pairs)
        precision = true_positive / (true_positive + false_positive) if true_positive else 0
        recall = true_positive / (true_positive + false_negative) if true_positive else 0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return sum(scores) / len(scores)


def _set_recall(expected: frozenset[str], predicted: frozenset[str]) -> float:
    return len(expected & predicted) / len(expected) if expected else 1.0


def _set_precision(expected: frozenset[str], predicted: frozenset[str]) -> float:
    return len(expected & predicted) / len(predicted) if predicted else float(not expected)


def _calibration(probabilities: Sequence[float], labels: Sequence[int]) -> tuple[float, float]:
    brier = statistics.fmean(
        (probability - label) ** 2 for probability, label in zip(probabilities, labels, strict=True)
    )
    expected_calibration_error = 0.0
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        members = [
            index
            for index, probability in enumerate(probabilities)
            if lower <= probability <= (1.0 if lower == 0.8 else lower + 0.2)
        ]
        if members:
            confidence = statistics.fmean(probabilities[index] for index in members)
            frequency = statistics.fmean(labels[index] for index in members)
            expected_calibration_error += len(members) / len(labels) * abs(confidence - frequency)
    return brier, expected_calibration_error


def evaluate_strategy(strategy: RiskStrategy, cases: Sequence[BenchmarkCase]) -> dict[str, Any]:
    predictions: list[Prediction] = []
    latency_ms: list[float] = []
    for case in cases:
        started = time.perf_counter_ns()
        predictions.append(strategy.predict(case))
        latency_ms.append((time.perf_counter_ns() - started) / 1_000_000)

    expected = [case.ground_truth.risk for case in cases]
    predicted = [item.risk for item in predictions]
    case_predictions = tuple(zip(cases, predictions, strict=True))
    risk_pairs = tuple(zip(expected, predicted, strict=True))
    labels = [int(level == "high") for level in expected]
    probabilities = [item.high_risk_probability for item in predictions]
    brier, calibration_error = _calibration(probabilities, labels)
    false_positive = sum(left != "high" and right == "high" for left, right in risk_pairs)
    false_negative = sum(left == "high" and right != "high" for left, right in risk_pairs)
    accepted_suggestions = sum(
        len(case.ground_truth.evidence & prediction.evidence)
        for case, prediction in case_predictions
    )
    rejected_suggestions = sum(
        len(prediction.evidence - case.ground_truth.evidence)
        for case, prediction in case_predictions
    )
    ordered_latency = sorted(latency_ms)
    p95_index = max(0, math.ceil(0.95 * len(ordered_latency)) - 1)
    stable_sample = "\n".join(
        f"{case.identifier}:{case.split}:{case.ground_truth.risk}" for case in cases
    )
    return {
        "strategy_version": strategy.version,
        "model": strategy.model,
        "sample_count": len(cases),
        "sample_fingerprint": hashlib.sha256(stable_sample.encode()).hexdigest(),
        "metrics": {
            "risk_accuracy": round(
                sum(left == right for left, right in risk_pairs) / len(cases), 4
            ),
            "risk_macro_f1": round(_macro_f1(expected, predicted), 4),
            "review_priority_accuracy": round(
                sum(
                    case.ground_truth.review_priority == prediction.review_priority
                    for case, prediction in case_predictions
                )
                / len(cases),
                4,
            ),
            "high_risk_false_positives": false_positive,
            "high_risk_false_negatives": false_negative,
            "brier_score": round(brier, 4),
            "expected_calibration_error": round(calibration_error, 4),
            "evidence_recall": round(
                statistics.fmean(
                    _set_recall(case.ground_truth.evidence, prediction.evidence)
                    for case, prediction in case_predictions
                ),
                4,
            ),
            "evidence_precision": round(
                statistics.fmean(
                    _set_precision(case.ground_truth.evidence, prediction.evidence)
                    for case, prediction in case_predictions
                ),
                4,
            ),
            "test_suggestion_recall": round(
                statistics.fmean(
                    _set_recall(case.ground_truth.tests, prediction.tests)
                    for case, prediction in case_predictions
                ),
                4,
            ),
            "accepted_evidence_suggestions": accepted_suggestions,
            "rejected_evidence_suggestions": rejected_suggestions,
        },
        "latency": {
            "basis": "local measured wall time; excluded from deterministic comparison",
            "p50_ms": round(statistics.median(ordered_latency), 6),
            "p95_ms": round(ordered_latency[p95_index], 6),
        },
        "cost": {
            "basis": "modeled estimate; no billable API request was made",
            "estimated_total_usd": round(strategy.estimated_cost_per_case_usd * len(cases), 6),
            "estimated_per_case_usd": strategy.estimated_cost_per_case_usd,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--split", choices=("train", "validation", "test", "all"), default="test")
    parser.add_argument(
        "--strategy",
        choices=tuple(strategy.name for strategy in STRATEGIES),
        default="Hybrid+History",
    )
    args = parser.parse_args()
    manifest, all_cases = load_manifest(args.manifest)
    cases = (
        all_cases
        if args.split == "all"
        else tuple(case for case in all_cases if case.split == args.split)
    )
    strategy = next(item for item in STRATEGIES if item.name == args.strategy)
    print(
        json.dumps(
            {
                "dataset_version": manifest["dataset_version"],
                "split": args.split,
                "result": evaluate_strategy(strategy, cases),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
