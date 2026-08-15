import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.github.client import FetchedReleaseRange
from maintainerflow.persistence.releases import ReleaseDraftRepository
from maintainerflow.persistence.repositories import AuditRepository
from maintainerflow.release.breaking import detect_breaking_candidate
from maintainerflow.release.changelog import DEFAULT_CHANGELOG_CONFIG, generate_changelog
from maintainerflow.release.notes import build_release_draft
from maintainerflow.release.schemas import (
    BreakingCandidate,
    ChangelogConfig,
    MergedPullRequest,
    ReleaseDraft,
)


@dataclass(frozen=True)
class ReleaseGenerationRun:
    draft: ReleaseDraft
    persisted: bool
    draft_id: int


class ReleaseSource(Protocol):
    async def list_release_tags(self, owner: str, repo: str) -> tuple[str, ...]: ...

    async def fetch_release_range(
        self, owner: str, repo: str, from_ref: str, to_ref: str
    ) -> FetchedReleaseRange: ...


def _breaking_candidate(pull: MergedPullRequest) -> BreakingCandidate | None:
    migrations = tuple(
        f"Migration path changed: {path}"
        for path in pull.changed_files
        if path.startswith(("migrations/", "alembic/"))
    )
    public_api = tuple(
        f"Public export surface changed: {path}"
        for path in pull.changed_files
        if path.endswith("/__init__.py") or path.startswith(("api/", "src/api/"))
    )
    return detect_breaking_candidate(
        pull,
        public_api_evidence=public_api,
        migration_evidence=migrations,
    )


def release_input_hash(
    draft: ReleaseDraft,
    config: ChangelogConfig,
) -> str:
    payload = {
        "draft": draft.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


async def generate_release_notes(
    session: AsyncSession,
    *,
    repository_id: int,
    repository: RepositoryRef,
    from_ref: str,
    to_ref: str,
    github: ReleaseSource,
    config: ChangelogConfig = DEFAULT_CHANGELOG_CONFIG,
) -> ReleaseGenerationRun:
    tags = await github.list_release_tags(repository.owner, repository.name)
    fetched = await github.fetch_release_range(
        repository.owner,
        repository.name,
        from_ref,
        to_ref,
    )
    limitations: list[str] = []
    if from_ref not in tags:
        limitations.append("from_ref_not_found_in_published_releases")
    if fetched.truncated_by_budget:
        limitations.append("github_history_truncated_by_rate_budget")
    changelog = generate_changelog(fetched.pull_requests, config)
    candidates = tuple(
        candidate
        for pull in fetched.pull_requests
        if (candidate := _breaking_candidate(pull)) is not None
    )
    draft = build_release_draft(
        repository=f"{repository.owner}/{repository.name}",
        from_ref=from_ref,
        to_ref=to_ref,
        compare_url=fetched.compare_url,
        changelog=changelog,
        breaking_candidates=candidates,
        limitations=limitations,
    )
    input_hash = release_input_hash(draft, config)
    record, persisted = await ReleaseDraftRepository(session).save(repository_id, input_hash, draft)
    if persisted:
        await AuditRepository(session).record(
            "release.draft.generated",
            repository_id=repository_id,
            analysis_id=None,
            release_draft_id=record.id,
            payload={
                "from_ref": from_ref,
                "to_ref": to_ref,
                "input_hash": input_hash,
                "pull_request_count": len(changelog.entries),
                "breaking_candidate_count": len(candidates),
                "side_effects": [],
            },
        )
    return ReleaseGenerationRun(draft, persisted, record.id)
