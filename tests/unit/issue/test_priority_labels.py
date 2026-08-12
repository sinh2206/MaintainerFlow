from maintainerflow.issue.classifier import classify_issue
from maintainerflow.issue.labels import suggest_labels
from maintainerflow.issue.priority import suggest_priority


def test_priority_combines_severity_scope_and_reproducibility() -> None:
    title = "Security bug causes data loss"
    body = "Always reproducible for all users in production."
    classification = classify_issue(title, body)

    result = suggest_priority(title, body, classification)

    assert result.level == "critical"
    assert result.score == 9
    assert len(result.reasons) == 3


def test_label_alias_only_selects_existing_repository_label() -> None:
    classification = classify_issue("Feature request add export", "")
    matched = suggest_labels(classification, ("type: feature", "bug"))
    missing = suggest_labels(classification, ("bug",))

    assert matched[0].repository_label == "type: feature"
    assert matched[0].available
    assert missing[0].repository_label is None
    assert not missing[0].available
