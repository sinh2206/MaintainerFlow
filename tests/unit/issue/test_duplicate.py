from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.issue.duplicate import LexicalDuplicateEngine
from maintainerflow.issue.schemas import IssueSource

REPOSITORY = RepositoryRef(github_id=1, owner="owner", name="repo")


def issue(github_id: int, number: int, title: str, body: str = "") -> IssueSource:
    return IssueSource(
        repository=REPOSITORY,
        github_id=github_id,
        number=number,
        title=title,
        body=body,
        url=f"https://github.test/owner/repo/issues/{number}",
    )


def test_duplicate_ranking_is_stable_and_excludes_query() -> None:
    query = issue(10, 10, "Login crashes with invalid token", "auth exception")
    results = LexicalDuplicateEngine().rank(
        query,
        (
            query,
            issue(11, 11, "Invalid token crashes login", "auth exception"),
            issue(12, 12, "Login documentation", "write an auth guide"),
            issue(13, 13, "Add dark mode"),
        ),
    )

    assert results[0].number == 11
    assert results[0].score > 0.5
    assert all(item.github_id != query.github_id for item in results)


def test_exact_title_has_maximum_score() -> None:
    engine = LexicalDuplicateEngine()
    assert engine.score(issue(1, 1, "Same title"), issue(2, 2, "same title")) == 1
