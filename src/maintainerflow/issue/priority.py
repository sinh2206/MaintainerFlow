import re

from maintainerflow.issue.schemas import IssueClassification, PrioritySuggestion


def suggest_priority(
    title: str,
    body: str,
    classification: IssueClassification,
    *,
    policy_adjustment: float = 0,
) -> PrioritySuggestion:
    text = f"{title}\n{body}".lower()
    score = 1.0
    reasons: list[str] = []
    rules = (
        (r"security|data loss|credential|production down", 5.5, "critical severity"),
        (r"crash|regression|unusable|exception", 2.5, "runtime failure"),
        (r"all users|every request|production|system-wide", 1.5, "wide affected scope"),
        (r"always|reproducible|steps to reproduce", 1.0, "reproducible"),
    )
    for pattern, weight, reason in rules:
        if re.search(pattern, text):
            score += weight
            reasons.append(reason)
    if classification.category in {"docs", "question", "maintenance"}:
        score -= 0.75
    score = round(min(10, max(0, score + policy_adjustment)), 1)
    level = (
        "critical" if score >= 8 else "high" if score >= 5 else "medium" if score >= 2.5 else "low"
    )
    return PrioritySuggestion(level=level, score=score, reasons=tuple(reasons))
