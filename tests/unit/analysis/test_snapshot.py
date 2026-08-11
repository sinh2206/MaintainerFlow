from maintainerflow.analysis.snapshot import create_snapshot
from maintainerflow.core.schemas import PullRequestSource, RepositoryRef


def source(head: str = "b" * 40) -> PullRequestSource:
    return PullRequestSource(
        repository=RepositoryRef(github_id=1, owner="o", name="r"),
        number=1,
        base_sha="a" * 40,
        head_sha=head,
        diff="diff",
    )


def snapshot(head: str = "b" * 40):  # type: ignore[no-untyped-def]
    return create_snapshot(
        source(head),
        config={"max": 1},
        rules_version="r1",
        prompt_version="p1",
        model_version="m1",
    )


def test_snapshot_is_stable_for_same_input() -> None:
    assert snapshot() == snapshot()


def test_head_sha_changes_snapshot_identity() -> None:
    assert snapshot().id != snapshot("c" * 40).id
