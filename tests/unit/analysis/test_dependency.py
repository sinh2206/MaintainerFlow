from maintainerflow.analysis.dependency import build_dependency_graph
from maintainerflow.analysis.diff import parse_unified_diff
from maintainerflow.analysis.languages.base import LanguageAnalysis
from maintainerflow.analysis.repository import RepositoryContext
from maintainerflow.analysis.risk import assess_risk
from maintainerflow.core.schemas import Evidence, RepositoryRef


def test_dependency_graph_computes_centrality_and_related_tests() -> None:
    graph = build_dependency_graph(
        (
            LanguageAnalysis(path="src/app.py", module="app", imports=("core",)),
            LanguageAnalysis(path="src/api.py", module="api", imports=("core",)),
            LanguageAnalysis(path="src/core.py", module="core"),
            LanguageAnalysis(
                path="tests/test_core.py",
                module="tests.test_core",
                imports=("core",),
                is_test=True,
            ),
        )
    )

    assert graph.edges["app"] == ("core",)
    assert graph.criticality["core"] == 1
    assert graph.related_tests["core"] == ("tests/test_core.py",)


def test_dependency_graph_preserves_known_import_chain() -> None:
    graph = build_dependency_graph(
        (
            LanguageAnalysis(path="a.py", module="a", imports=("b",)),
            LanguageAnalysis(path="b.py", module="b", imports=("c",)),
            LanguageAnalysis(path="c.py", module="c"),
            LanguageAnalysis(path="demo.py", module="demo"),
        )
    )

    assert graph.edges == {"a": ("b",), "b": ("c",), "c": (), "demo": ()}
    assert graph.criticality["b"] > graph.criticality["demo"]


def test_repository_context_changes_pr_risk_with_traceable_evidence() -> None:
    parsed = parse_unified_diff(
        "diff --git a/src/core.py b/src/core.py\n"
        "--- a/src/core.py\n+++ b/src/core.py\n@@ -1 +1 @@\n-old = 1\n+new = 2\n"
    )
    module = LanguageAnalysis(path="src/core.py", module="core")
    context = RepositoryContext(
        repository=RepositoryRef(github_id=1, owner="owner", name="repo"),
        commit_sha="a" * 40,
        file_tree=("src/core.py", "tests/test_core.py"),
        modules=(module,),
        dependency_graph={"core": ()},
        criticality={"core": 0.9},
        related_tests={"core": ("tests/test_core.py",)},
        history=(
            Evidence(
                kind="bug_fix_history",
                path="src/core.py",
                message="Prior regression fix touched this file.",
                source="github-history",
                confidence=0.8,
                metadata={"id": "abc", "url": "https://github.test/commit/abc"},
            ),
        ),
    )

    baseline = assess_risk(parsed)
    enriched = assess_risk(parsed, repository_context=context)

    assert enriched.risk.score > baseline.risk.score
    assert {item.kind for item in enriched.evidence} >= {
        "repository_criticality",
        "bug_fix_history",
    }
    assert enriched.suggested_tests[-1].endswith("tests/test_core.py")
