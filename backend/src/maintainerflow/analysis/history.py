import hashlib
from dataclasses import dataclass

from maintainerflow.core.schemas import Evidence


@dataclass(frozen=True)
class HistoricalPullRequest:
    github_id: int
    number: int
    url: str
    title: str
    files: tuple[str, ...]
    reviewer_logins: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalCommit:
    sha: str
    url: str
    message: str
    files: tuple[str, ...]


def collect_history_evidence(
    pull_requests: tuple[HistoricalPullRequest, ...],
    commits: tuple[HistoricalCommit, ...],
) -> tuple[Evidence, ...]:
    evidence: dict[tuple[str, str, str | None], Evidence] = {}
    commits_by_path: dict[str, list[HistoricalCommit]] = {}
    for commit in commits:
        lowered = commit.message.lower()
        kind = (
            "revert_history"
            if lowered.startswith("revert")
            else "bug_fix_history"
            if any(word in lowered for word in ("fix", "bug", "regression"))
            else None
        )
        if kind:
            for path in commit.files:
                commits_by_path.setdefault(path, []).append(commit)
                evidence[(kind, commit.sha, path)] = Evidence(
                    kind=kind,
                    path=path,
                    message=f"Historical {kind.replace('_', ' ')} touches this file.",
                    source="github-history",
                    confidence=0.8,
                    metadata={"id": commit.sha, "url": commit.url},
                )
        else:
            for path in commit.files:
                commits_by_path.setdefault(path, []).append(commit)
    for path, path_commits in commits_by_path.items():
        if len(path_commits) < 2:
            continue
        identifiers = [commit.sha for commit in path_commits]
        source_id = f"churn:{hashlib.sha256(path.encode()).hexdigest()}"
        evidence[("file_churn_history", source_id, path)] = Evidence(
            kind="file_churn_history",
            path=path,
            message=f"This file appears in {len(path_commits)} recent commits.",
            source="github-history",
            confidence=min(0.9, 0.5 + len(path_commits) * 0.05),
            metadata={
                "id": source_id,
                "url": path_commits[-1].url,
                "commit_ids": identifiers,
            },
        )
    for pull in pull_requests:
        if pull.reviewer_logins:
            evidence[
                ("reviewer_history", str(pull.github_id), pull.files[0] if pull.files else None)
            ] = Evidence(
                kind="reviewer_history",
                path=pull.files[0] if pull.files else None,
                message="Previous review activity is available for this area.",
                source="github-history",
                confidence=0.75,
                metadata={
                    "id": pull.github_id,
                    "url": pull.url,
                    "reviewers": sorted(set(pull.reviewer_logins)),
                },
            )
    return tuple(evidence.values())
