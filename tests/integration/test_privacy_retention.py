from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from maintainerflow.analysis.languages.base import RepositoryFile
from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.issue.schemas import IssueSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.intelligence import (
    IssueAnalysisRepository,
    RepositoryIntelligenceRepository,
)
from maintainerflow.persistence.models import (
    GitHubInstallation,
    IssueAnalysisRecord,
    Repository,
    RepositoryIndexRecord,
)
from maintainerflow.services.analyze_issue import analyze_issue
from maintainerflow.services.index_repository import index_repository


async def test_private_content_is_opt_in_and_expired_records_are_purged(
    database: Database,
) -> None:
    reference = RepositoryRef(github_id=202, owner="private", name="repo")
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=10)
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
        indexes = RepositoryIntelligenceRepository(session)
        async with session.begin():
            await index_repository(
                repository_id=repository.id,
                repository=reference,
                commit_sha="b" * 40,
                files=(RepositoryFile(path="secret.py", sha="x", content="TOKEN = 'secret'"),),
                store=indexes,
                store_source=False,
            )
            issue = IssueSource(
                repository=reference,
                github_id=33,
                number=3,
                title="Crash in login",
                body="private reproduction data",
                url="https://github.test/private/repo/issues/3",
            )
            await analyze_issue(
                issue,
                repository_id=repository.id,
                session=session,
                store_body=False,
            )
        index_row = await session.scalar(select(RepositoryIndexRecord))
        issue_row = await session.scalar(select(IssueAnalysisRecord))
        assert index_row is not None and index_row.source_archive is None
        assert issue_row is not None and issue_row.body_text is None
        await session.commit()

        async with session.begin():
            expiry = datetime.now(UTC) - timedelta(seconds=1)
            index_row.expires_at = expiry
            issue_row.expires_at = expiry
        async with session.begin():
            assert await IssueAnalysisRepository(session).purge_expired() == 1
            assert await indexes.purge_expired() == 1
        assert await session.scalar(select(func.count()).select_from(IssueAnalysisRecord)) == 0
        assert await session.scalar(select(func.count()).select_from(RepositoryIndexRecord)) == 0
        await session.commit()

        async with session.begin():
            await index_repository(
                repository_id=repository.id,
                repository=reference,
                commit_sha="c" * 40,
                files=(RepositoryFile(path="public.py", sha="y", content="value = 1"),),
                store=indexes,
            )
            await analyze_issue(
                issue.model_copy(update={"body": "new private content"}),
                repository_id=repository.id,
                session=session,
            )
        async with session.begin():
            assert await IssueAnalysisRepository(session).delete_repository(repository.id) == 1
            assert await indexes.delete_repository(repository.id) == 1
