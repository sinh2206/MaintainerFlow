import re
from collections.abc import Iterable

from maintainerflow.release.schemas import BreakingCandidate, BreakingEvidence, MergedPullRequest

_BREAKING_LABELS = frozenset({"breaking", "breaking change", "breaking-change", "semver:major"})
_BANG_MARKER = re.compile(r"^[a-z][a-z0-9-]*(?:\([^)]+\))?!:\s*", re.IGNORECASE)
_BREAKING_FOOTER = re.compile(r"^BREAKING(?:[ -]CHANGE):\s*(\S.*)$", re.IGNORECASE | re.MULTILINE)
_PUBLIC_API_MARKER = re.compile(r"^Public API change:\s*(\S.*)$", re.IGNORECASE | re.MULTILINE)
_MIGRATION_MARKER = re.compile(r"^Migration required:\s*(\S.*)$", re.IGNORECASE | re.MULTILINE)


def _clean(value: str) -> str:
    return " ".join(value.split())[:500]


def detect_breaking_candidate(
    pull_request: MergedPullRequest,
    *,
    public_api_evidence: Iterable[str] = (),
    migration_evidence: Iterable[str] = (),
) -> BreakingCandidate | None:
    evidence: dict[tuple[str, str, str], BreakingEvidence] = {}

    for label in pull_request.labels:
        normalized = " ".join(label.casefold().replace("_", " ").split())
        if normalized in _BREAKING_LABELS:
            item = BreakingEvidence(kind="label", text=_clean(label), source="pull_request.label")
            evidence[(item.kind, item.text, item.source)] = item

    if _BANG_MARKER.match(pull_request.title):
        item = BreakingEvidence(
            kind="conventional_marker", text=_clean(pull_request.title), source="pull_request.title"
        )
        evidence[(item.kind, item.text, item.source)] = item

    for match in _BREAKING_FOOTER.finditer(pull_request.body):
        item = BreakingEvidence(
            kind="conventional_marker",
            text=_clean(match.group(1)),
            source="pull_request.body:BREAKING-CHANGE",
        )
        evidence[(item.kind, item.text, item.source)] = item
    for match in _PUBLIC_API_MARKER.finditer(pull_request.body):
        item = BreakingEvidence(
            kind="public_api", text=_clean(match.group(1)), source="pull_request.body:public-api"
        )
        evidence[(item.kind, item.text, item.source)] = item
    for match in _MIGRATION_MARKER.finditer(pull_request.body):
        item = BreakingEvidence(
            kind="migration", text=_clean(match.group(1)), source="pull_request.body:migration"
        )
        evidence[(item.kind, item.text, item.source)] = item

    for text in public_api_evidence:
        if cleaned := _clean(text):
            item = BreakingEvidence(kind="public_api", text=cleaned, source="repository-analysis")
            evidence[(item.kind, item.text, item.source)] = item
    for text in migration_evidence:
        if cleaned := _clean(text):
            item = BreakingEvidence(kind="migration", text=cleaned, source="repository-analysis")
            evidence[(item.kind, item.text, item.source)] = item

    if not evidence:
        return None
    return BreakingCandidate(
        pull_request=pull_request,
        evidence=tuple(
            sorted(evidence.values(), key=lambda item: (item.kind, item.source, item.text))
        ),
    )


def detect_breaking_candidates(
    pull_requests: Iterable[MergedPullRequest],
) -> tuple[BreakingCandidate, ...]:
    by_id: dict[int, list[BreakingCandidate]] = {}
    for pull_request in pull_requests:
        if candidate := detect_breaking_candidate(pull_request):
            by_id.setdefault(pull_request.github_id, []).append(candidate)
    candidates = (min(values, key=lambda item: item.model_dump_json()) for values in by_id.values())
    return tuple(
        sorted(candidates, key=lambda item: (item.pull_request.number, item.pull_request.github_id))
    )
