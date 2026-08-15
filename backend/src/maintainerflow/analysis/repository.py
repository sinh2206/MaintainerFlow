from pydantic import BaseModel, ConfigDict, Field

from maintainerflow.analysis.languages.base import LanguageAnalysis
from maintainerflow.core.schemas import Evidence, RepositoryRef

REPOSITORY_ANALYZER_VERSION = "repository-v1+python-ast-v1"


class RepositoryContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository: RepositoryRef
    commit_sha: str = Field(min_length=7, max_length=64)
    analyzer_version: str = REPOSITORY_ANALYZER_VERSION
    file_tree: tuple[str, ...]
    modules: tuple[LanguageAnalysis, ...]
    dependency_graph: dict[str, tuple[str, ...]]
    criticality: dict[str, float]
    related_tests: dict[str, tuple[str, ...]]
    history: tuple[Evidence, ...] = ()
    limitations: tuple[str, ...] = ()

    def criticality_for_path(self, path: str) -> float:
        return next(
            (self.criticality.get(item.module, 0) for item in self.modules if item.path == path),
            0,
        )
