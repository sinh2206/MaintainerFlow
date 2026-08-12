from pydantic import BaseModel, ConfigDict

from maintainerflow.analysis.languages.base import LanguageAnalysis


class DependencyGraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    edges: dict[str, tuple[str, ...]]
    criticality: dict[str, float]
    related_tests: dict[str, tuple[str, ...]]


def build_dependency_graph(analyses: tuple[LanguageAnalysis, ...]) -> DependencyGraph:
    modules = {item.module: item for item in analyses if item.module}
    edges: dict[str, tuple[str, ...]] = {}
    for module, item in modules.items():
        resolved = tuple(
            sorted(
                target
                for target in modules
                if target != module
                and any(
                    imported == target or imported.startswith(f"{target}.")
                    for imported in item.imports
                )
            )
        )
        edges[module] = resolved
    incoming = {module: 0 for module in modules}
    for targets in edges.values():
        for target in targets:
            incoming[target] += 1
    denominator = max(1, len(modules) - 1)
    criticality = {module: round(count / denominator, 4) for module, count in incoming.items()}
    tests: dict[str, list[str]] = {
        module: [] for module, item in modules.items() if not item.is_test
    }
    for test_module, item in modules.items():
        if not item.is_test:
            continue
        for source in tests:
            source_name = source.rsplit(".", 1)[-1]
            if source in edges.get(test_module, ()) or test_module.endswith(f"test_{source_name}"):
                tests[source].append(item.path)
    return DependencyGraph(
        edges=edges,
        criticality=criticality,
        related_tests={key: tuple(sorted(value)) for key, value in tests.items()},
    )
