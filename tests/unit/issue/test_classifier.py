import pytest

from maintainerflow.issue.classifier import classify_issue
from maintainerflow.issue.labels import suggest_labels


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Crash and exception on login", "bug"),
        ("Feature request: add dark mode", "feature"),
        ("Documentation typo in README", "docs"),
        ("Question: how do I configure this?", "question"),
        ("Maintenance chore: upgrade dependency", "maintenance"),
    ],
)
def test_classifies_supported_taxonomy_with_evidence(title: str, category: str) -> None:
    result = classify_issue(title, "")

    assert result.category == category
    assert result.confidence >= 0.6
    assert result.evidence
    assert all(title[item.start : item.end] == item.text for item in result.evidence)


def test_low_confidence_fallback_is_explicit() -> None:
    result = classify_issue("Unexpected behavior", "No diagnostic vocabulary")

    assert result.category == "bug"
    assert result.confidence < 0.6
    assert result.evidence == ()
    assert suggest_labels(result, ("bug",)) == ()


def test_empty_issue_is_low_confidence_maintenance() -> None:
    result = classify_issue("", "")

    assert result.category == "maintenance"
    assert result.confidence == 0.2
    assert result.evidence == ()
