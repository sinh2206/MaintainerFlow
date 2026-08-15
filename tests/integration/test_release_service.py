from datetime import UTC, datetime

from sqlalchemy import func, select

from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.github.client import FetchedReleaseRange, RateLimitMetadata
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import (
    AuditEvent,
    GitHubInstallation,
    OutboxEvent,
    ReleaseDraftRecord,
    Repository,
)
from maintainerflow.release.schemas import MergedPullRequest
from maintainerflow.services.generate_release_notes import generate_release_notes


def pull(number: int) -> MergedPullRequest:
    prefixes = ("feat", "fix", "perf", "docs", "chore")
    prefix = prefixes[(number - 1) % len(prefixes)]
    changed = (f"src/module_{number}.py",)
    if number == 5:
        changed = ("migrations/versions/0005.py",)
    return MergedPullRequest(
        github_id=1_000 + number,
        number=number,
        title=f"{prefix}: change {number}",
        url=f"https://github.test/owner/repo/pull/{number}",
        author="alice" if number % 2 else "bob",
        body="BREAKING CHANGE: review compatibility" if number == 5 else "",
        labels=("feature", "docs") if number == 1 else (),
        changed_files=changed,
        merged_at=datetime(2026, 8, number, tzinfo=UTC),
        merge_commit_sha=f"sha{number}",
    )


async def test_two_tags_paginated_pr_result_persists_one_deterministic_draft(
    database: Database,
) -> None:
    reference = RepositoryRef(github_id=505, owner="owner", name="repo")
    pulls = tuple(pull(number) for number in range(1, 13))

    class FakeGitHub:
        async def list_release_tags(self, owner: str, repo: str) -> tuple[str, ...]:
            assert (owner, repo) == ("owner", "repo")
            return ("v0.4.0",)

        async def fetch_release_range(
            self, owner: str, repo: str, from_ref: str, to_ref: str
        ) -> FetchedReleaseRange:
            assert (owner, repo, from_ref, to_ref) == (
                "owner",
                "repo",
                "v0.4.0",
                "v1.0.0",
            )
            return FetchedReleaseRange(
                pulls,
                "https://github.test/owner/repo/compare/v0.4.0...v1.0.0",
                RateLimitMetadata(400, 1),
            )

    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=13)
            session.add(installation)
            await session.flush()
            repository = Repository(
                github_id=reference.github_id,
                installation_id=installation.id,
                owner=reference.owner,
                name=reference.name,
            )
            session.add(repository)
            await session.flush()
        github = FakeGitHub()
        async with session.begin():
            first = await generate_release_notes(
                session,
                repository_id=repository.id,
                repository=reference,
                from_ref="v0.4.0",
                to_ref="v1.0.0",
                github=github,
            )
        async with session.begin():
            replay = await generate_release_notes(
                session,
                repository_id=repository.id,
                repository=reference,
                from_ref="v0.4.0",
                to_ref="v1.0.0",
                github=github,
            )

        assert first.persisted and not replay.persisted
        assert first.draft_id == replay.draft_id
        assert first.draft == replay.draft
        assert len(first.draft.changelog.entries) == 12
        assert first.draft.contributors == ("alice", "bob")
        assert first.draft.breaking_candidates[0].requires_maintainer_confirmation
        assert await session.scalar(select(func.count()).select_from(ReleaseDraftRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 0
        audit = await session.scalar(select(AuditEvent))
        assert audit is not None and audit.release_draft_id == first.draft_id
        assert audit.payload["side_effects"] == []


async def test_rate_budget_limitation_changes_release_identity_instead_of_reusing_stale_draft(
    database: Database,
) -> None:
    reference = RepositoryRef(github_id=506, owner="owner", name="repo")

    class ChangingBudgetGitHub:
        truncated = False

        async def list_release_tags(self, owner: str, repo: str) -> tuple[str, ...]:
            return ("v0.4.0",)

        async def fetch_release_range(
            self, owner: str, repo: str, from_ref: str, to_ref: str
        ) -> FetchedReleaseRange:
            return FetchedReleaseRange(
                (pull(1),),
                "https://github.test/owner/repo/compare/v0.4.0...v1.0.0",
                RateLimitMetadata(100, 1),
                truncated_by_budget=self.truncated,
            )

    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=14)
            session.add(installation)
            await session.flush()
            repository = Repository(
                github_id=reference.github_id,
                installation_id=installation.id,
                owner=reference.owner,
                name=reference.name,
            )
            session.add(repository)
            await session.flush()
        github = ChangingBudgetGitHub()
        async with session.begin():
            complete = await generate_release_notes(
                session,
                repository_id=repository.id,
                repository=reference,
                from_ref="v0.4.0",
                to_ref="v1.0.0",
                github=github,
            )
        github.truncated = True
        async with session.begin():
            limited = await generate_release_notes(
                session,
                repository_id=repository.id,
                repository=reference,
                from_ref="v0.4.0",
                to_ref="v1.0.0",
                github=github,
            )

        assert complete.draft_id != limited.draft_id
        assert complete.draft.limitations == ()
        assert limited.draft.limitations == ("github_history_truncated_by_rate_budget",)
        assert await session.scalar(select(func.count()).select_from(ReleaseDraftRecord)) == 2
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 2
