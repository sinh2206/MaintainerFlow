from sqlalchemy import func, select

from maintainerflow.analysis.languages.base import RepositoryFile
from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.intelligence import RepositoryIntelligenceRepository
from maintainerflow.persistence.models import GitHubInstallation, Repository, RepositoryIndexRecord
from maintainerflow.services.index_repository import index_repository


async def test_repository_cache_keys_by_sha_and_analyzer_version(database: Database) -> None:
    reference = RepositoryRef(github_id=101, owner="owner", name="repo")
    files = (
        RepositoryFile(path="src/core.py", sha="blob1", content="def public():\n    return 1\n"),
    )
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=9)
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
        store = RepositoryIntelligenceRepository(session)
        async with session.begin():
            first, built_first = await index_repository(
                repository_id=repository.id,
                repository=reference,
                commit_sha="a" * 40,
                files=files,
                store=store,
                analyzer_version="repo-v1",
            )
        async with session.begin():
            cached, built_cached = await index_repository(
                repository_id=repository.id,
                repository=reference,
                commit_sha="a" * 40,
                files=files,
                store=store,
                analyzer_version="repo-v1",
            )
        async with session.begin():
            rebuilt, built_new_version = await index_repository(
                repository_id=repository.id,
                repository=reference,
                commit_sha="a" * 40,
                files=files,
                store=store,
                analyzer_version="repo-v2",
            )

        assert built_first and not built_cached and built_new_version
        assert first == cached
        assert rebuilt.analyzer_version == "repo-v2"
        assert await session.scalar(select(func.count()).select_from(RepositoryIndexRecord)) == 2
