from typing import Literal

from maintainerflow.core.enums import AnalysisStatus, RiskLevel
from maintainerflow.core.schemas import AnalysisResult, CheckPolicyDecision


def apply_confidence_policy(result: AnalysisResult) -> AnalysisResult:
    """Fail safe when a warning cannot be traced to evidence."""
    needs_evidence = result.risk.level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
    if needs_evidence and not result.evidence:
        return result.model_copy(
            update={
                "status": AnalysisStatus.INSUFFICIENT_EVIDENCE,
                "risk": result.risk.model_copy(
                    update={"confidence": min(0.3, result.risk.confidence)}
                ),
                "limitations": (*result.limitations, "Risk warning has no supporting evidence."),
            }
        )
    if result.evidence_coverage < 0.5 and result.status == AnalysisStatus.COMPLETE:
        return result.model_copy(
            update={
                "status": AnalysisStatus.PARTIAL,
                "risk": result.risk.model_copy(
                    update={"confidence": round(result.risk.confidence * 0.75, 3)}
                ),
                "limitations": (*result.limitations, "Less than half of evidence is localized."),
            }
        )
    return result


def decide_check_policy(
    result: AnalysisResult,
    *,
    mode: Literal["shadow", "suggestion"] = "shadow",
    stale: bool = False,
) -> CheckPolicyDecision:
    if stale or result.status == AnalysisStatus.STALE:
        return CheckPolicyDecision(
            publish=False,
            mode=mode,
            conclusion="neutral",
            reason="stale_analysis",
        )
    confident = (
        result.status not in {AnalysisStatus.INSUFFICIENT_EVIDENCE, AnalysisStatus.FAILED_SAFE}
        and result.risk.confidence >= 0.5
    )
    actions = (
        (("useful", "not_useful") if mode == "shadow" else ("accept", "reject", "useful"))
        if confident
        else ()
    )
    conclusion = (
        "success" if mode == "suggestion" and result.risk.level == RiskLevel.LOW else "neutral"
    )
    return CheckPolicyDecision(
        publish=True,
        mode=mode,
        conclusion=conclusion,
        actions=actions,
        reason="publish_non_blocking" if confident else "publish_without_actions",
    )
