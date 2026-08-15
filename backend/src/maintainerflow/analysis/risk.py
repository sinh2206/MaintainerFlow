import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Protocol

from maintainerflow.analysis.diff import ParsedDiff
from maintainerflow.analysis.evidence import deduplicate_evidence
from maintainerflow.core.enums import RiskLevel
from maintainerflow.core.schemas import Evidence, Risk

if TYPE_CHECKING:
    from maintainerflow.analysis.repository import RepositoryContext

RULES_VERSION = "static-v1"
DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java"}
DEPENDENCY_FILES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "uv.lock",
    "go.mod",
    "cargo.toml",
}


class RiskRule(Protocol):
    def collect(self, parsed: ParsedDiff) -> list[Evidence]: ...


def _evidence(kind: str, message: str, weight: float, path: str | None = None) -> Evidence:
    return Evidence(
        kind=kind,
        path=path,
        message=message,
        source="static-rules",
        confidence=0.95,
        metadata={"weight": weight},
    )


def _is_test(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith("tests/") or "/test" in lowered or lowered.endswith("_test.py")


def _is_docs(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith("docs/") or PurePosixPath(lowered).suffix in DOC_SUFFIXES


def _is_source(path: str) -> bool:
    return PurePosixPath(path.lower()).suffix in SOURCE_SUFFIXES and not _is_test(path)


def _major_dependency_changed(patch: str) -> bool:
    old = {int(value) for value in re.findall(r"^-.*?[\^~<>=\"'](\d+)\.", patch, re.MULTILINE)}
    new = {int(value) for value in re.findall(r"^\+.*?[\^~<>=\"'](\d+)\.", patch, re.MULTILINE)}
    return bool(old and new and old != new)


class PathRule:
    def collect(self, parsed: ParsedDiff) -> list[Evidence]:
        evidence: list[Evidence] = []
        for file in parsed.files:
            path = file.path.lower()
            if any(token in path for token in ("auth", "security", "permission", "crypto")):
                evidence.append(
                    _evidence(
                        "authentication_change",
                        "Authentication/security path changed.",
                        6,
                        file.path,
                    )
                )
            elif "migration" in path or path.startswith("migrations/"):
                evidence.append(
                    _evidence("migration_change", "Database migration changed.", 6, file.path)
                )
            elif _is_source(file.path):
                evidence.append(
                    _evidence("core_change", "Executable source changed.", 2, file.path)
                )
        return evidence


class TestCoverageRule:
    def collect(self, parsed: ParsedDiff) -> list[Evidence]:
        source = [file.path for file in parsed.files if _is_source(file.path)]
        if source and not any(_is_test(file.path) for file in parsed.files):
            return [
                _evidence("missing_tests", "Source changed without a test change.", 1.5, source[0])
            ]
        return []


class DependencyRule:
    def collect(self, parsed: ParsedDiff) -> list[Evidence]:
        evidence: list[Evidence] = []
        for file in parsed.files:
            if PurePosixPath(file.path.lower()).name not in DEPENDENCY_FILES:
                continue
            evidence.append(
                _evidence("dependency_change", "Dependency configuration changed.", 1.5, file.path)
            )
            if _major_dependency_changed(file.patch):
                evidence.append(
                    _evidence(
                        "major_dependency",
                        "A dependency major version may have changed.",
                        3.5,
                        file.path,
                    )
                )
        return evidence


class SizeRule:
    def collect(self, parsed: ParsedDiff) -> list[Evidence]:
        changed = parsed.additions + parsed.deletions
        if changed > 1_000:
            return [_evidence("large_diff", f"Large change contains {changed} changed lines.", 3)]
        if changed > 400:
            return [_evidence("large_diff", f"Change contains {changed} changed lines.", 1.5)]
        return []


@dataclass(frozen=True)
class RiskAssessment:
    risk: Risk
    evidence: tuple[Evidence, ...]
    suggested_tests: tuple[str, ...]


def level_for_score(score: float) -> RiskLevel:
    if score >= 7:
        return RiskLevel.HIGH
    if score >= 3:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def assess_risk(
    parsed: ParsedDiff,
    rules: tuple[RiskRule, ...] = (PathRule(), TestCoverageRule(), DependencyRule(), SizeRule()),
    repository_context: "RepositoryContext | None" = None,
) -> RiskAssessment:
    collected = [item for rule in rules for item in rule.collect(parsed)]
    related_tests: list[str] = []
    if repository_context:
        changed_paths = {file.path for file in parsed.files}
        for path in changed_paths:
            criticality = repository_context.criticality_for_path(path)
            if criticality >= 0.5:
                collected.append(
                    _evidence(
                        "repository_criticality",
                        f"Repository graph marks this module as central ({criticality:.2f}).",
                        2,
                        path,
                    )
                )
            module = next(
                (item.module for item in repository_context.modules if item.path == path), None
            )
            if module:
                related_tests.extend(repository_context.related_tests.get(module, ()))
        collected.extend(
            item.model_copy(update={"metadata": {**item.metadata, "weight": 1.5}})
            for item in repository_context.history
            if item.path in changed_paths
        )
    evidence = deduplicate_evidence(collected)
    docs_only = bool(parsed.files) and all(_is_docs(file.path) for file in parsed.files)
    if docs_only:
        score = 1.0
    else:
        weights: dict[str, float] = {}
        for item in evidence:
            weights[item.kind] = max(weights.get(item.kind, 0), float(item.metadata["weight"]))
        score = 0.5 if not parsed.files else 1 + sum(weights.values())
        if any(_is_test(file.path) for file in parsed.files):
            score -= 0.75
    score = round(min(10, max(0, score)), 1)
    confidence = 0.95 - (0.2 if parsed.truncated else 0) - (0.2 if parsed.limitations else 0)
    kinds = {item.kind for item in evidence}
    tests: list[str] = []
    if "missing_tests" in kinds:
        tests.append("Add focused unit tests for changed source behavior.")
    if "authentication_change" in kinds:
        tests.append("Run authentication authorization and negative-path tests.")
    if "migration_change" in kinds:
        tests.append("Test migration upgrade, downgrade, and data preservation.")
    if kinds & {"dependency_change", "major_dependency"}:
        tests.append("Run dependency compatibility and application smoke tests.")
    tests.extend(f"Run related repository test: {path}" for path in sorted(set(related_tests)))
    return RiskAssessment(
        Risk(score=score, level=level_for_score(score), confidence=round(max(0.2, confidence), 2)),
        evidence,
        tuple(tests),
    )
