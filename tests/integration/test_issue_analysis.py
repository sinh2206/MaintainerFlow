from sqlalchemy import func, select

from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.issue.schemas import IssueSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import (
    AuditEvent,
    GitHubInstallation,
    IssueAnalysisRecord,
    Repository,
)
from maintainerflow.services.analyze_issue import analyze_issue


async def test_same_issue_source_is_idempotent(database: Database) -> None:
    reference = RepositoryRef(github_id=303, owner="owner", name="repo")
    issue = IssueSource(
        repository=reference,
        github_id=44,
        number=4,
        title="Crash on retry",
        body="The worker raises an exception.",
        url="https://github.test/issues/4",
    )
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=11)
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
        async with session.begin():
            first = await analyze_issue(issue, repository_id=repository.id, session=session)
        async with session.begin():
            repeated = await analyze_issue(issue, repository_id=repository.id, session=session)

        assert first.persisted and not repeated.persisted
        assert first.analysis_id == repeated.analysis_id
        assert await session.scalar(select(func.count()).select_from(IssueAnalysisRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1
