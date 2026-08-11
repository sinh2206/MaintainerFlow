from pathlib import Path

from sqlalchemy import func, select

from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import AnalysisRecord, GitHubInstallation, Repository
from maintainerflow.persistence.repositories import AnalysisRepository
from maintainerflow.services.analyze_pull_request import analyze_pull_request

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json"


async def test_same_snapshot_reuses_analysis(database: Database) -> None:
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=98)
            session.add(installation)
            await session.flush()
            db_repository = Repository(
                github_id=source.repository.github_id,
                installation_id=installation.id,
                owner=source.repository.owner,
                name=source.repository.name,
            )
            session.add(db_repository)
            await session.flush()
        repository = AnalysisRepository(session)
        async with session.begin():
            first = await analyze_pull_request(
                source, repository=repository, repository_id=db_repository.id
            )
        async with session.begin():
            second = await analyze_pull_request(
                source, repository=repository, repository_id=db_repository.id
            )
        assert first.persisted
        assert not second.persisted
        assert first.result.evidence == second.result.evidence
        assert await session.scalar(select(func.count()).select_from(AnalysisRecord)) == 1
