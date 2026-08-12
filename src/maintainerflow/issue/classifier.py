import re

from maintainerflow.issue.schemas import IssueCategory, IssueClassification, TextEvidence

RULES: dict[IssueCategory, tuple[str, ...]] = {
    "bug": ("bug", "crash", "broken", "error", "exception", "regression", "fails"),
    "feature": ("feature", "request", "support", "enhancement", "implement", "add"),
    "docs": ("docs", "documentation", "readme", "typo", "guide", "example"),
    "question": ("question", "how", "why", "help", "clarify", "what"),
    "maintenance": ("maintenance", "chore", "dependency", "upgrade", "refactor", "cleanup", "ci"),
}


def classify_issue(title: str, body: str) -> IssueClassification:
    text = f"{title.strip()}\n{body.strip()}".strip()
    if not text:
        return IssueClassification(category="maintenance", confidence=0.2)
    matches: dict[IssueCategory, list[TextEvidence]] = {category: [] for category in RULES}
    for category, terms in RULES.items():
        for term in terms:
            found = re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)
            if found:
                matches[category].append(
                    TextEvidence(
                        start=found.start(),
                        end=found.end(),
                        text=found.group(0),
                        rule=f"keyword:{term}",
                    )
                )
    ranked = sorted(matches, key=lambda item: (-len(matches[item]), tuple(RULES).index(item)))
    category = ranked[0]
    count = len(matches[category])
    confidence = 0.25 if count == 0 else min(0.95, 0.55 + count * 0.12)
    return IssueClassification(
        category=category,
        confidence=round(confidence, 2),
        evidence=tuple(matches[category][:5]),
    )
