from pathlib import Path

from sqlalchemy import func, select

from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import (
    AuditEvent,
    GitHubInstallation,
    OutboxEvent,
    Repository,
)
from maintainerflow.persistence.repositories import AnalysisRepository
from maintainerflow.services.analyze_pull_request import analyze_pull_request
from maintainerflow.services.publish_check import queue_check_publish

FIXTURE = Path(__file__).parents[3] / "benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json"


async def test_same_analysis_queues_one_logical_command(database: Database) -> None:
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=88)
            session.add(installation)
            await session.flush()
            repository = Repository(
                github_id=source.repository.github_id,
                installation_id=installation.id,
                owner=source.repository.owner,
                name=source.repository.name,
            )
            session.add(repository)
            await session.flush()
        async with session.begin():
            run = await analyze_pull_request(
                source,
                repository=AnalysisRepository(session),
                repository_id=repository.id,
            )
        assert run.analysis_id is not None
        async with session.begin():
            first = await queue_check_publish(
                session,
                repository_id=repository.id,
                repository_github_id=repository.github_id,
                analysis_id=run.analysis_id,
                installation_id=installation.github_id,
                owner=repository.owner,
                repository=repository.name,
                head_sha=source.head_sha,
                result=run.result,
            )
        async with session.begin():
            second = await queue_check_publish(
                session,
                repository_id=repository.id,
                repository_github_id=repository.github_id,
                analysis_id=run.analysis_id,
                installation_id=installation.github_id,
                owner=repository.owner,
                repository=repository.name,
                head_sha=source.head_sha,
                result=run.result,
            )
        assert first.created
        assert not second.created
        assert first.outbox_id == second.outbox_id
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1
