from collections.abc import Iterable

from maintainerflow.release.changelog import generate_changelog
from maintainerflow.release.schemas import Changelog, MergedPullRequest


def make_pull_request(
    number: int,
    title: str,
    *,
    github_id: int | None = None,
    author: str = "octocat",
    body: str = "",
    labels: Iterable[str] = (),
    changed_files: Iterable[str] = (),
) -> MergedPullRequest:
    return MergedPullRequest(
        github_id=github_id or number * 10,
        number=number,
        title=title,
        url=f"https://github.com/acme/widgets/pull/{number}",
        author=author,
        body=body,
        labels=tuple(labels),
        changed_files=tuple(changed_files),
    )


def make_changelog(*pull_requests: MergedPullRequest) -> Changelog:
    return generate_changelog(pull_requests)
