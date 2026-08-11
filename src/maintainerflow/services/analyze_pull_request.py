from dataclasses import dataclass

from maintainerflow.ai.base import AIAnalysisInput, AIProvider, AIProviderError
from maintainerflow.analysis.diff import ParsedDiff, parse_unified_diff
from maintainerflow.analysis.report import build_report
from maintainerflow.analysis.risk import RULES_VERSION, assess_risk
from maintainerflow.analysis.snapshot import create_snapshot
from maintainerflow.core.schemas import AnalysisResult, AnalysisSnapshot, PullRequestSource
from maintainerflow.persistence.repositories import AnalysisRepository

PROMPT_VERSION = "pr-analysis-v1"


@dataclass(frozen=True)
class AnalysisRun:
    snapshot: AnalysisSnapshot
    result: AnalysisResult
    persisted: bool


async def analyze_pull_request(
    source: PullRequestSource,
    *,
    max_diff_bytes: int = 1_000_000,
    model_version: str = "static-only",
    ai_provider: AIProvider | None = None,
    repository: AnalysisRepository | None = None,
    repository_id: int | None = None,
) -> AnalysisRun:
    snapshot = create_snapshot(
        source,
        config={"max_diff_bytes": max_diff_bytes, "store_diff": False},
        rules_version=RULES_VERSION,
        prompt_version=PROMPT_VERSION,
        model_version=model_version,
    )
    if repository:
        existing = await repository.get_result(snapshot.id)
        if existing:
            return AnalysisRun(snapshot, existing, False)

    parsed = parse_unified_diff(source.diff, max_bytes=max_diff_bytes)
    if source.changed_files:
        metadata_additions = sum(file.additions for file in source.changed_files)
        metadata_deletions = sum(file.deletions for file in source.changed_files)
        parsed = ParsedDiff(
            parsed.files or source.changed_files,
            max(parsed.additions, metadata_additions),
            max(parsed.deletions, metadata_deletions),
            parsed.truncated,
            parsed.limitations,
        )
    assessment = assess_risk(parsed)
    ai_result = None
    ai_error = None
    if ai_provider:
        try:
            ai_result = await ai_provider.analyze(
                AIAnalysisInput(
                    title=source.title,
                    body=source.body,
                    diff_excerpt=source.diff[:100_000],
                    files=tuple(file.path for file in parsed.files),
                    static_risk=assessment.risk,
                    static_evidence=assessment.evidence,
                )
            )
        except AIProviderError as exc:
            ai_error = exc.code
        except Exception:
            ai_error = "provider_failure"
    result = build_report(snapshot, parsed, assessment, ai_result=ai_result, ai_error=ai_error)
    persisted = False
    if repository:
        if repository_id is None:
            raise ValueError("repository_id is required when persistence is enabled")
        _, persisted = await repository.save(repository_id, snapshot, result)
    return AnalysisRun(snapshot, result, persisted)
