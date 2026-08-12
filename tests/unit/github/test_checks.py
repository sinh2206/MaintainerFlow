from maintainerflow.core.enums import AnalysisStatus, RiskLevel
from maintainerflow.core.policies import decide_check_policy
from maintainerflow.core.schemas import AnalysisResult, Evidence, Risk
from maintainerflow.github.checks import build_check_command


def report(level: RiskLevel, *, status: AnalysisStatus = AnalysisStatus.COMPLETE) -> AnalysisResult:
    evidence = tuple(
        Evidence(
            kind="unsafe<script>",
            path=f"src/file_{index}.py",
            line=index + 1,
            message="Review [link](javascript:alert(1)) ghs_SUPERSECRETVALUE",
            source="static",
            confidence=0.9,
        )
        for index in range(60)
    )
    return AnalysisResult(
        snapshot_id="a" * 64,
        status=status,
        summary="Unsafe <script> github_pat_SUPERSECRETVALUE",
        risk=Risk(score=8 if level == RiskLevel.HIGH else 2, level=level, confidence=0.9),
        evidence_coverage=1,
        evidence=evidence,
        suggested_tests=("Run tests",),
        review_focus=("Review auth",),
    )


def test_payload_limits_annotations_and_sanitizes_untrusted_markdown() -> None:
    result = report(RiskLevel.HIGH)
    command = build_check_command(
        analysis_id=7,
        installation_id=8,
        repository_github_id=1,
        owner="owner",
        repository="repo",
        head_sha="b" * 40,
        result=result,
        decision=decide_check_policy(result),
    )
    serialized = command.model_dump_json()
    assert command.external_id == "7"
    assert command.conclusion == "neutral"
    assert len(command.annotations) == 50
    assert "SUPERSECRETVALUE" not in serialized
    assert "<script>" not in serialized
    assert len(command.actions) <= 3


def test_partial_report_is_non_blocking() -> None:
    result = report(RiskLevel.MEDIUM, status=AnalysisStatus.PARTIAL)
    command = build_check_command(
        analysis_id=1,
        installation_id=2,
        repository_github_id=1,
        owner="o",
        repository="r",
        head_sha="b" * 40,
        result=result,
        decision=decide_check_policy(result, mode="suggestion"),
    )
    assert command.conclusion == "neutral"
