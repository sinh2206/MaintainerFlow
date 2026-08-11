from pathlib import Path

from sqlalchemy import func, select

from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import (
    AnalysisRecord,
    AnalysisSnapshotRecord,
    EvidenceRecord,
    GitHubInstallation,
    Repository,
)
from maintainerflow.persistence.repositories import AnalysisRepository
from maintainerflow.services.analyze_pull_request import analyze_pull_request

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/05-authentication.json"


async def test_fixture_is_persisted_without_full_diff(database: Database) -> None:
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=99)
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
            run = await analyze_pull_request(
                source, repository=repository, repository_id=db_repository.id
            )
        assert run.persisted
        assert await session.scalar(select(func.count()).select_from(AnalysisSnapshotRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(AnalysisRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(EvidenceRecord)) >= 1
        assert "diff" not in AnalysisSnapshotRecord.__table__.columns
        loaded = await repository.get_result(run.snapshot.id)
        assert loaded == run.result
