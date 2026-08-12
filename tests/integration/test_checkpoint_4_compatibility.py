from sqlalchemy import func, select

from maintainerflow.analysis.languages.base import LanguageAnalysis
from maintainerflow.analysis.repository import RepositoryContext
from maintainerflow.core.schemas import PullRequestSource, RepositoryRef
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import AnalysisRecord, GitHubInstallation, Repository
from maintainerflow.persistence.repositories import AnalysisRepository
from maintainerflow.services.analyze_pull_request import analyze_pull_request


async def test_cp4_context_has_distinct_cp2_snapshot_and_enriches_risk(
    database: Database,
) -> None:
    reference = RepositoryRef(github_id=404, owner="owner", name="repo")
    source = PullRequestSource(
        repository=reference,
        number=4,
        base_sha="a" * 40,
        head_sha="b" * 40,
        title="Change core",
        diff=(
            "diff --git a/src/core.py b/src/core.py\n"
            "--- a/src/core.py\n+++ b/src/core.py\n"
            "@@ -1 +1 @@\n-old = 1\n+new = 2\n"
        ),
    )
    context = RepositoryContext(
        repository=reference,
        commit_sha=source.base_sha,
        file_tree=("src/core.py", "tests/test_core.py"),
        modules=(LanguageAnalysis(path="src/core.py", module="core"),),
        dependency_graph={"core": ()},
        criticality={"core": 0.9},
        related_tests={"core": ("tests/test_core.py",)},
    )
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=12)
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
        analyses = AnalysisRepository(session)
        async with session.begin():
            baseline = await analyze_pull_request(
                source,
                repository=analyses,
                repository_id=repository.id,
            )
        async with session.begin():
            enriched = await analyze_pull_request(
                source,
                repository=analyses,
                repository_id=repository.id,
                repository_context=context,
            )

        assert baseline.snapshot.id != enriched.snapshot.id
        assert baseline.snapshot.config_hash != enriched.snapshot.config_hash
        assert enriched.result.risk.score > baseline.result.risk.score
        assert "repository_criticality" in {item.kind for item in enriched.result.evidence}
        assert await session.scalar(select(func.count()).select_from(AnalysisRecord)) == 2
