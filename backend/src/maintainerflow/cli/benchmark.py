import json
from pathlib import Path
from typing import Annotated, Literal

import typer

BenchmarkSuite = Literal["all", "pr-risk", "issue-triage"]
OutputFormat = Literal["json", "markdown"]
Split = Literal["train", "validation", "test", "all"]


def benchmark_command(
    suite: Annotated[BenchmarkSuite, typer.Option("--suite")] = "all",
    split: Annotated[Split, typer.Option("--split")] = "test",
    output_format: Annotated[OutputFormat, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Run versioned offline benchmarks without sending data to an AI provider."""
    from benchmarks.runners.compare import render_markdown as render_pr_markdown
    from benchmarks.runners.compare import run_comparison
    from benchmarks.runners.issue_triage import render_markdown as render_issue_markdown
    from benchmarks.runners.issue_triage import run_benchmark as run_issue_benchmark

    pr_report = run_comparison(split=split) if suite in {"all", "pr-risk"} else None
    issue_report = run_issue_benchmark() if suite in {"all", "issue-triage"} else None
    payload = {
        "schema_version": "maintainerflow-benchmark-v1",
        "suite": suite,
        "pr_risk": pr_report,
        "issue_triage": issue_report,
    }
    if output_format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    else:
        sections = []
        if pr_report:
            sections.append(render_pr_markdown(pr_report).rstrip())
        if issue_report:
            sections.append(render_issue_markdown(issue_report).rstrip())
        rendered = "\n\n".join(sections) + "\n"
    if output:
        output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        typer.echo(rendered, nl=False)

    passed = (pr_report is None or pr_report["comparison"]["requirement_met"]) and (
        issue_report is None
        or (
            issue_report["classification"]["macro_f1"] >= 0.8
            and issue_report["duplicates"]["recall_at_3"] >= 0.75
        )
    )
    if not passed:
        raise typer.Exit(1)
