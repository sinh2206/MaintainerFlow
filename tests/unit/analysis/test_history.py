from maintainerflow.analysis.history import (
    HistoricalCommit,
    HistoricalPullRequest,
    collect_history_evidence,
)


def test_history_evidence_keeps_stable_source_provenance() -> None:
    evidence = collect_history_evidence(
        (
            HistoricalPullRequest(
                github_id=4,
                number=4,
                url="https://github.test/pull/4",
                title="Auth review",
                files=("src/auth.py",),
                reviewer_logins=("alice", "alice"),
            ),
        ),
        (
            HistoricalCommit(
                sha="abc1234",
                url="https://github.test/commit/abc1234",
                message="Fix auth regression",
                files=("src/auth.py",),
            ),
            HistoricalCommit(
                sha="def5678",
                url="https://github.test/commit/def5678",
                message="Revert auth change",
                files=("src/auth.py",),
            ),
        ),
    )

    assert {item.kind for item in evidence} == {
        "bug_fix_history",
        "revert_history",
        "file_churn_history",
        "reviewer_history",
    }
    assert all(item.metadata["id"] and item.metadata["url"] for item in evidence)
    reviewer = next(item for item in evidence if item.kind == "reviewer_history")
    assert reviewer.metadata["reviewers"] == ["alice"]
