import re
from collections.abc import Iterable

from maintainerflow.release.schemas import (
    CategorizedPullRequest,
    CategoryRule,
    Changelog,
    ChangelogConfig,
    MergedPullRequest,
)

DEFAULT_CHANGELOG_CONFIG = ChangelogConfig(
    rules=(
        CategoryRule(
            category="feature",
            labels=("feature", "enhancement"),
            title_prefixes=("feat", "feature"),
        ),
        CategoryRule(
            category="fix", labels=("bug", "fix", "bugfix"), title_prefixes=("fix", "bugfix")
        ),
        CategoryRule(
            category="performance",
            labels=("performance", "perf"),
            title_prefixes=("perf", "performance"),
        ),
        CategoryRule(
            category="docs",
            labels=("docs", "documentation"),
            title_prefixes=("docs", "documentation"),
        ),
        CategoryRule(
            category="chore",
            labels=("chore", "maintenance", "dependencies"),
            title_prefixes=("chore", "build", "ci", "refactor", "test"),
        ),
    )
)


def _normal(value: str) -> str:
    return " ".join(value.casefold().split())


def _matches_title_prefix(title: str, prefix: str) -> bool:
    prefix = _normal(prefix)
    if not prefix:
        return False
    if prefix[-1:] in {":", "]"} or prefix[0] == "[":
        return _normal(title).startswith(prefix)
    return re.match(rf"^{re.escape(prefix)}(?:\([^)]+\))?!?:\s*", _normal(title)) is not None


def classify_pull_request(
    pull_request: MergedPullRequest,
    config: ChangelogConfig = DEFAULT_CHANGELOG_CONFIG,
) -> CategorizedPullRequest:
    labels = {_normal(label) for label in pull_request.labels}
    for rule in config.rules:
        for label in rule.labels:
            normalized = _normal(label)
            if normalized and normalized in labels:
                return CategorizedPullRequest(
                    category=rule.category,
                    pull_request=pull_request,
                    matched_by=f"label:{normalized}"[:255],
                )
        for prefix in rule.title_prefixes:
            if _matches_title_prefix(pull_request.title, prefix):
                return CategorizedPullRequest(
                    category=rule.category,
                    pull_request=pull_request,
                    matched_by=f"title:{_normal(prefix)}"[:255],
                )
    return CategorizedPullRequest(
        category=config.fallback,
        pull_request=pull_request,
        matched_by="fallback",
    )


def _canonical_key(pull_request: MergedPullRequest) -> tuple[object, ...]:
    return (
        pull_request.number,
        _normal(pull_request.title),
        pull_request.url,
        _normal(pull_request.author),
        tuple(sorted(_normal(label) for label in pull_request.labels)),
        pull_request.body,
        tuple(sorted(pull_request.changed_files)),
        pull_request.merge_commit_sha or "",
    )


def generate_changelog(
    pull_requests: Iterable[MergedPullRequest],
    config: ChangelogConfig = DEFAULT_CHANGELOG_CONFIG,
) -> Changelog:
    """Deduplicate and classify PRs without depending on provider/page order."""

    by_id: dict[int, list[MergedPullRequest]] = {}
    for pull_request in pull_requests:
        by_id.setdefault(pull_request.github_id, []).append(pull_request)

    duplicate_ids = tuple(
        sorted(github_id for github_id, values in by_id.items() if len(values) > 1)
    )
    canonical = [min(values, key=_canonical_key) for values in by_id.values()]
    classified = [classify_pull_request(item, config) for item in canonical]
    precedence: dict[str, int] = {}
    for index, rule in enumerate(config.rules):
        precedence.setdefault(rule.category, index)
    classified.sort(
        key=lambda item: (
            precedence.get(item.category, len(precedence)),
            item.pull_request.number,
            item.pull_request.github_id,
        )
    )
    return Changelog(entries=tuple(classified), duplicate_github_ids=duplicate_ids)
