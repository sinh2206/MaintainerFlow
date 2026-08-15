"""Compare all deterministic PR-risk strategies and emit a versioned report."""

from __future__ import annotations

import argparse
import copy
import json
import platform
from pathlib import Path
from typing import Any

if __package__:
    from .pr_risk import (
        DEFAULT_MANIFEST,
        STRATEGIES,
        BenchmarkCase,
        evaluate_strategy,
        load_manifest,
    )
else:
    from pr_risk import (  # type: ignore[import-not-found,no-redef]
        DEFAULT_MANIFEST,
        STRATEGIES,
        BenchmarkCase,
        evaluate_strategy,
        load_manifest,
    )

REPORT_SCHEMA_VERSION = "pr-risk-comparison-v1"


def _selected(cases: tuple[BenchmarkCase, ...], split: str) -> tuple[BenchmarkCase, ...]:
    selected = cases if split == "all" else tuple(case for case in cases if case.split == split)
    if not selected:
        raise ValueError(f"Manifest has no cases in split {split!r}")
    return selected


def run_comparison(manifest_path: Path = DEFAULT_MANIFEST, split: str = "test") -> dict[str, Any]:
    manifest, cases = load_manifest(manifest_path)
    selected = _selected(cases, split)
    results = {strategy.name: evaluate_strategy(strategy, selected) for strategy in STRATEGIES}
    static = results["Static-only"]["metrics"]
    ai = results["AI-only"]["metrics"]
    hybrid = results["Hybrid"]["metrics"]
    history = results["Hybrid+History"]["metrics"]
    strongest_baseline_f1 = max(static["risk_macro_f1"], ai["risk_macro_f1"])
    benefit = {
        "hybrid_macro_f1_gain_over_best_single_strategy": round(
            hybrid["risk_macro_f1"] - strongest_baseline_f1, 4
        ),
        "hybrid_false_negative_reduction_vs_static": (
            static["high_risk_false_negatives"] - hybrid["high_risk_false_negatives"]
        ),
        "history_false_negative_reduction_vs_hybrid": (
            hybrid["high_risk_false_negatives"] - history["high_risk_false_negatives"]
        ),
    }
    benefit["requirement_met"] = any(value > 0 for value in benefit.values())
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "dataset": {
            "name": "pr-risk",
            "version": manifest["dataset_version"],
            "license": manifest["license"],
            "source": manifest["source"],
            "split_policy": manifest["split_policy"],
        },
        "evaluation": {"split": split, "sample_count": len(selected)},
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.system(),
        },
        "strategies": results,
        "comparison": benefit,
        "reproducibility": {
            "deterministic_fields": (
                "dataset, evaluation, strategy versions, sample fingerprints, prediction metrics, "
                "modeled cost"
            ),
            "variable_fields": "environment and locally measured latency",
            "model_variance": (
                "None in this report: AI-only is a named offline deterministic proxy with no "
                "sampling or provider request. Production model/version changes require a new "
                "report."
            ),
            "cost_variance": (
                "No charge occurred. Cost is a declared estimate and may differ by provider, "
                "model, tokenization, region, cache behavior and pricing date."
            ),
        },
        "privacy": (
            "Aggregate metrics and synthetic sample fingerprints only; no secrets, prompts, raw "
            "private source, issue bodies or PR diffs are included."
        ),
    }


def stable_projection(report: dict[str, Any]) -> dict[str, Any]:
    """Remove fields expected to vary between otherwise equivalent local runs."""
    stable = copy.deepcopy(report)
    stable.pop("environment", None)
    for result in stable["strategies"].values():
        result.pop("latency", None)
    return stable


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for name, result in report["strategies"].items():
        metrics = result["metrics"]
        rows.append(
            "| {name} | {f1:.4f} | {accuracy:.4f} | {fp} | {fn} | {brier:.4f} | "
            "{latency:.6f} | {cost:.6f} |".format(
                name=name,
                f1=metrics["risk_macro_f1"],
                accuracy=metrics["risk_accuracy"],
                fp=metrics["high_risk_false_positives"],
                fn=metrics["high_risk_false_negatives"],
                brier=metrics["brier_score"],
                latency=result["latency"]["p95_ms"],
                cost=result["cost"]["estimated_total_usd"],
            )
        )
    comparison = report["comparison"]
    return "\n".join(
        [
            f"# PR Risk Benchmark {report['dataset']['version']}",
            "",
            f"Split: `{report['evaluation']['split']}` "
            f"({report['evaluation']['sample_count']} samples)",
            "",
            "| Strategy | Macro F1 | Accuracy | FP | FN | Brier | p95 ms | Est. USD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## Hybrid benefit",
            "",
            f"- Macro-F1 gain over the best single strategy: "
            f"`{comparison['hybrid_macro_f1_gain_over_best_single_strategy']:.4f}`.",
            f"- False-negative reduction versus Static-only: "
            f"`{comparison['hybrid_false_negative_reduction_vs_static']}`.",
            f"- Additional false-negative reduction from history: "
            f"`{comparison['history_false_negative_reduction_vs_hybrid']}`.",
            "",
            "Latency is locally measured and may vary. Cost is modeled; no provider call or charge "
            "occurred. The AI strategy is an offline deterministic proxy, not a hosted-model "
            "claim.",
            "",
            report["privacy"],
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--split", choices=("train", "validation", "test", "all"), default="test")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = run_comparison(args.manifest, args.split)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.write_text(serialized, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(serialized, end="")
    return 0 if report["comparison"]["requirement_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
