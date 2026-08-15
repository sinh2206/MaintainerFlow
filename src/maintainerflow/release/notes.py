from collections.abc import Iterable

from maintainerflow.release.schemas import (
    BreakingCandidate,
    Changelog,
    ReleaseCategory,
    ReleaseDraft,
    validate_http_url,
)

_CATEGORY_HEADINGS: tuple[tuple[ReleaseCategory, str], ...] = (
    ("feature", "Features"),
    ("fix", "Fixes"),
    ("performance", "Performance"),
    ("docs", "Documentation"),
    ("chore", "Chores"),
)


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _escape_text(value: str) -> str:
    return (
        _one_line(value)
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _is_bot(author: str) -> bool:
    login = author.casefold()
    return login.endswith("[bot]") or login in {
        "dependabot",
        "github-actions",
        "renovate-bot",
    }


def contributors(changelog: Changelog) -> tuple[str, ...]:
    by_login: dict[str, set[str]] = {}
    for entry in changelog.entries:
        author = _one_line(entry.pull_request.author)
        if author and not _is_bot(author):
            by_login.setdefault(author.casefold(), set()).add(author)
    canonical = (min(values) for values in by_login.values())
    return tuple(sorted(canonical, key=lambda value: (value.casefold(), value)))


def _unique_breaking(
    candidates: Iterable[BreakingCandidate],
) -> tuple[BreakingCandidate, ...]:
    by_id: dict[int, list[BreakingCandidate]] = {}
    for candidate in candidates:
        by_id.setdefault(candidate.pull_request.github_id, []).append(candidate)
    return tuple(
        min(values, key=lambda item: item.model_dump_json())
        for _, values in sorted(by_id.items(), key=lambda item: item[0])
    )


def render_release_notes(
    *,
    repository: str,
    from_ref: str,
    to_ref: str,
    compare_url: str,
    changelog: Changelog,
    breaking_candidates: Iterable[BreakingCandidate] = (),
    limitations: Iterable[str] = (),
) -> str:
    compare_url = validate_http_url(compare_url)
    lines = [
        f"# {_escape_text(repository)} {_escape_text(to_ref)}",
        "",
        f"**Compare:** [{_escape_text(from_ref)}...{_escape_text(to_ref)}](<{compare_url}>)",
    ]
    entries = tuple(changelog.entries)
    for category, heading in _CATEGORY_HEADINGS:
        category_entries = sorted(
            (item for item in entries if item.category == category),
            key=lambda item: (item.pull_request.number, item.pull_request.github_id),
        )
        if not category_entries:
            continue
        lines.extend(("", f"## {heading}", ""))
        for entry in category_entries:
            pull = entry.pull_request
            lines.append(
                f"- [{_escape_text(pull.title)} (#{pull.number})](<{pull.url}>) "
                f"by @{_escape_text(pull.author)}"
            )

    candidates = _unique_breaking(breaking_candidates)
    if candidates:
        lines.extend(
            (
                "",
                "## Breaking-change candidates",
                "",
                "> Every candidate requires maintainer confirmation before release.",
                "",
            )
        )
        for candidate in sorted(
            candidates, key=lambda item: (item.pull_request.number, item.pull_request.github_id)
        ):
            pull = candidate.pull_request
            reasons = "; ".join(
                f"{item.kind}: {_escape_text(item.text)}"
                for item in sorted(
                    candidate.evidence, key=lambda item: (item.kind, item.source, item.text)
                )
            )
            lines.append(f"- [#{pull.number}](<{pull.url}>): {reasons}")

    authors = contributors(changelog)
    if authors:
        lines.extend(
            ("", "## Contributors", "", ", ".join(f"@{_escape_text(author)}" for author in authors))
        )

    unique_limitations = sorted({_one_line(value) for value in limitations if _one_line(value)})
    if unique_limitations:
        lines.extend(("", "## Limitations", ""))
        lines.extend(f"- {_escape_text(value)}" for value in unique_limitations)
    return "\n".join(lines) + "\n"


def build_release_draft(
    *,
    repository: str,
    from_ref: str,
    to_ref: str,
    compare_url: str,
    changelog: Changelog,
    breaking_candidates: Iterable[BreakingCandidate] = (),
    limitations: Iterable[str] = (),
) -> ReleaseDraft:
    candidates = _unique_breaking(breaking_candidates)
    normalized_limitations = tuple(
        sorted({_one_line(item) for item in limitations if _one_line(item)})
    )
    markdown = render_release_notes(
        repository=repository,
        from_ref=from_ref,
        to_ref=to_ref,
        compare_url=compare_url,
        changelog=changelog,
        breaking_candidates=candidates,
        limitations=normalized_limitations,
    )
    return ReleaseDraft(
        repository=_one_line(repository),
        from_ref=_one_line(from_ref),
        to_ref=_one_line(to_ref),
        compare_url=compare_url,
        changelog=changelog,
        breaking_candidates=candidates,
        contributors=contributors(changelog),
        markdown=markdown,
        limitations=normalized_limitations,
    )
