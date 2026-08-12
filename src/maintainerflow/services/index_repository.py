from collections.abc import Sequence

from maintainerflow.analysis.dependency import build_dependency_graph
from maintainerflow.analysis.languages.base import LanguageAnalyzer, RepositoryFile
from maintainerflow.analysis.languages.python import PythonAnalyzer
from maintainerflow.analysis.repository import REPOSITORY_ANALYZER_VERSION, RepositoryContext
from maintainerflow.core.schemas import Evidence, RepositoryRef
from maintainerflow.persistence.intelligence import RepositoryIntelligenceRepository


async def index_repository(
    *,
    repository_id: int,
    repository: RepositoryRef,
    commit_sha: str,
    files: tuple[RepositoryFile, ...],
    store: RepositoryIntelligenceRepository,
    history: tuple[Evidence, ...] = (),
    analyzers: Sequence[LanguageAnalyzer] = (PythonAnalyzer(),),
    retention_days: int = 30,
    store_source: bool = False,
    analyzer_version: str = REPOSITORY_ANALYZER_VERSION,
) -> tuple[RepositoryContext, bool]:
    cached = await store.get(repository_id, repository, commit_sha, analyzer_version)
    if cached:
        return cached, False

    modules = []
    limitations: list[str] = []
    for file in files:
        analyzer = next((item for item in analyzers if item.supports(file)), None)
        if analyzer is None:
            continue
        analysis = analyzer.analyze(file)
        modules.append(analysis)
        limitations.extend(analysis.limitations)
    graph = build_dependency_graph(tuple(modules))
    context = RepositoryContext(
        repository=repository,
        commit_sha=commit_sha,
        analyzer_version=analyzer_version,
        file_tree=tuple(sorted(file.path for file in files)),
        modules=tuple(modules),
        dependency_graph=graph.edges,
        criticality=graph.criticality,
        related_tests=graph.related_tests,
        history=history,
        limitations=tuple(dict.fromkeys(limitations)),
    )
    source_archive = (
        {file.path: file.content for file in files if file.content is not None}
        if store_source
        else None
    )
    await store.save(
        repository_id,
        context,
        retention_days=retention_days,
        source_archive=source_archive,
    )
    return context, True
