from maintainerflow.ai.base import AIProviderResult
from maintainerflow.analysis.diff import ParsedDiff
from maintainerflow.analysis.evidence import deduplicate_evidence
from maintainerflow.analysis.risk import RiskAssessment, level_for_score
from maintainerflow.core.enums import AnalysisStatus
from maintainerflow.core.policies import apply_confidence_policy
from maintainerflow.core.sanitize import sanitize_text
from maintainerflow.core.schemas import AnalysisResult, AnalysisSnapshot, Evidence, Risk


def _unique(items: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(sanitize_text(item.strip(), 1_000) for item in items if item.strip())
    )


def build_report(
    snapshot: AnalysisSnapshot,
    parsed: ParsedDiff,
    assessment: RiskAssessment,
    *,
    ai_result: AIProviderResult | None = None,
    ai_error: str | None = None,
) -> AnalysisResult:
    evidence = list(assessment.evidence)
    score = assessment.risk.score
    summary = (
        f"PR changes {len(parsed.files)} file(s), "
        f"with {parsed.additions} addition(s) and {parsed.deletions} deletion(s)."
    )
    tests = list(assessment.suggested_tests)
    focus = [item.message for item in evidence if item.kind != "core_change"]
    limitations = list(parsed.limitations)
    provider_metadata = None
    status = AnalysisStatus.PARTIAL if parsed.limitations else AnalysisStatus.COMPLETE

    if ai_result:
        summary = sanitize_text(ai_result.output.summary, 4_000)
        score = round(min(10, max(0, score + ai_result.output.risk_adjustment)), 1)
        changed_paths = {file.path for file in parsed.files}
        evidence.extend(
            Evidence(
                kind=signal.kind,
                path=signal.path if signal.path in changed_paths else None,
                line=signal.line if signal.path in changed_paths else None,
                message=sanitize_text(signal.message, 1_000),
                source=f"gemini:{ai_result.metadata.model}",
                confidence=signal.confidence,
            )
            for signal in ai_result.output.risk_reasons
        )
        tests.extend(ai_result.output.suggested_tests)
        focus.extend(ai_result.output.review_focus)
        limitations.extend(ai_result.output.limitations)
        provider_metadata = ai_result.metadata.model_dump(mode="json")
    elif ai_error:
        status = AnalysisStatus.PARTIAL
        limitations.append(f"AI analysis unavailable ({ai_error}); static report retained.")

    normalized = deduplicate_evidence(evidence)
    coverage = (
        1.0
        if not normalized
        else sum(item.path is not None for item in normalized) / len(normalized)
    )
    risk = Risk(
        score=score,
        level=level_for_score(score),
        confidence=assessment.risk.confidence,
    )
    result = AnalysisResult(
        snapshot_id=snapshot.id,
        status=status,
        summary=sanitize_text(summary, 4_000),
        risk=risk,
        evidence_coverage=round(coverage, 3),
        evidence=normalized,
        suggested_tests=_unique(tests),
        review_focus=_unique(focus),
        limitations=_unique(limitations),
        provider_metadata=provider_metadata,
    )
    return apply_confidence_policy(result)
