from maintainerflow.core.enums import AnalysisStatus, RiskLevel
from maintainerflow.core.policies import decide_check_policy
from maintainerflow.core.schemas import AnalysisResult, Evidence, Risk


def result(
    *,
    status: AnalysisStatus = AnalysisStatus.COMPLETE,
    level: RiskLevel = RiskLevel.MEDIUM,
    confidence: float = 0.9,
) -> AnalysisResult:
    return AnalysisResult(
        snapshot_id="a" * 64,
        status=status,
        summary="Report",
        risk=Risk(score=5, level=level, confidence=confidence),
        evidence_coverage=1,
        evidence=(
            Evidence(
                kind="core_change",
                path="src/a.py",
                message="Core changed",
                source="static",
                confidence=1,
            ),
        ),
    )


def test_shadow_is_always_non_blocking() -> None:
    decision = decide_check_policy(result(level=RiskLevel.HIGH), mode="shadow")
    assert decision.publish
    assert decision.conclusion == "neutral"
    assert decision.actions == ("useful", "not_useful")


def test_suggestion_low_can_succeed_but_warning_remains_neutral() -> None:
    assert (
        decide_check_policy(result(level=RiskLevel.LOW), mode="suggestion").conclusion == "success"
    )
    assert (
        decide_check_policy(result(level=RiskLevel.HIGH), mode="suggestion").conclusion == "neutral"
    )
    assert decide_check_policy(result(), mode="suggestion").actions == (
        "accept",
        "reject",
        "useful",
    )


def test_stale_is_not_published() -> None:
    assert not decide_check_policy(result(), stale=True).publish
    assert not decide_check_policy(result(status=AnalysisStatus.STALE)).publish


def test_low_confidence_or_insufficient_evidence_has_no_actions() -> None:
    assert decide_check_policy(result(confidence=0.2)).actions == ()
    assert decide_check_policy(result(status=AnalysisStatus.INSUFFICIENT_EVIDENCE)).actions == ()
