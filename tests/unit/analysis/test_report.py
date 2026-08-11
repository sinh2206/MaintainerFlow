from maintainerflow.analysis.diff import ParsedDiff
from maintainerflow.analysis.report import build_report
from maintainerflow.analysis.risk import RiskAssessment
from maintainerflow.analysis.snapshot import create_snapshot
from maintainerflow.core.enums import AnalysisStatus, RiskLevel
from maintainerflow.core.policies import apply_confidence_policy
from maintainerflow.core.schemas import (
    AnalysisResult,
    Evidence,
    PullRequestSource,
    RepositoryRef,
    Risk,
)


def test_high_risk_without_evidence_is_downgraded() -> None:
    result = AnalysisResult(
        snapshot_id="a" * 64,
        status=AnalysisStatus.COMPLETE,
        summary="Risk report",
        risk=Risk(score=8, level=RiskLevel.HIGH, confidence=0.9),
        evidence_coverage=1,
    )
    gated = apply_confidence_policy(result)
    assert gated.status == AnalysisStatus.INSUFFICIENT_EVIDENCE
    assert gated.risk.confidence == 0.3


def test_low_coverage_produces_parseable_partial_report() -> None:
    source = PullRequestSource(
        repository=RepositoryRef(github_id=1, owner="o", name="r"),
        number=1,
        base_sha="a" * 40,
        head_sha="b" * 40,
        diff="diff",
    )
    snapshot = create_snapshot(
        source, config={}, rules_version="r", prompt_version="p", model_version="m"
    )
    evidence = (
        Evidence(kind="large", message="Large", source="static", confidence=1),
        Evidence(kind="core", message="Core", source="static", confidence=1),
    )
    assessment = RiskAssessment(Risk(score=5, level=RiskLevel.MEDIUM, confidence=0.9), evidence, ())
    result = build_report(snapshot, ParsedDiff((), 0, 0), assessment)
    assert result.status == AnalysisStatus.PARTIAL
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
