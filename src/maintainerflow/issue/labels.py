from maintainerflow.issue.schemas import IssueClassification, LabelSuggestion

DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "bug": ("bug", "type: bug"),
    "feature": ("enhancement", "feature", "type: feature"),
    "docs": ("documentation", "docs"),
    "question": ("question", "support"),
    "maintenance": ("maintenance", "chore"),
}


def suggest_labels(
    classification: IssueClassification,
    available_labels: tuple[str, ...],
    *,
    aliases: dict[str, tuple[str, ...]] = DEFAULT_ALIASES,
    confidence_threshold: float = 0.6,
) -> tuple[LabelSuggestion, ...]:
    if classification.confidence < confidence_threshold:
        return ()
    by_lower = {label.lower(): label for label in available_labels}
    candidates = aliases[classification.category]
    match = next((by_lower[item.lower()] for item in candidates if item.lower() in by_lower), None)
    return (
        LabelSuggestion(
            canonical=classification.category,
            repository_label=match,
            available=match is not None,
            reason="repository_alias" if match else "label_missing_shadow_suggestion_only",
        ),
    )
