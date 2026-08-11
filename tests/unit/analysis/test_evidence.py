from maintainerflow.analysis.evidence import deduplicate_evidence
from maintainerflow.core.schemas import Evidence


def evidence(source: str, confidence: float = 0.5) -> Evidence:
    return Evidence(
        kind="risk",
        path="src/a.py",
        line=3,
        message="Same signal",
        source=source,
        confidence=confidence,
    )


def test_deduplicates_and_preserves_provenance() -> None:
    result = deduplicate_evidence([evidence("static"), evidence("gemini", 0.8)])
    assert len(result) == 1
    assert result[0].confidence == 0.8
    assert result[0].metadata["sources"] == ["gemini", "static"]


def test_conflicting_signals_remain_distinct() -> None:
    first = evidence("static")
    second = first.model_copy(update={"kind": "protective_test", "message": "Tests added"})
    assert len(deduplicate_evidence([first, second])) == 2
