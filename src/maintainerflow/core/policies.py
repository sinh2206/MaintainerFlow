from maintainerflow.core.enums import AnalysisStatus, RiskLevel
from maintainerflow.core.schemas import AnalysisResult


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
