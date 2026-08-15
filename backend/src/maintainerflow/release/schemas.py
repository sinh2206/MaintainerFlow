from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

ReleaseCategory = Literal["feature", "fix", "performance", "docs", "chore"]
BreakingEvidenceKind = Literal["label", "conventional_marker", "public_api", "migration"]


def validate_http_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in value
        )
        or "<" in value
        or ">" in value
    ):
        raise ValueError("must be an absolute HTTP(S) URL")
    return value


class MergedPullRequest(BaseModel):
    """Provider-neutral merged PR data needed by the release pipeline."""

    model_config = ConfigDict(frozen=True)

    github_id: int = Field(gt=0)
    number: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=1_000)
    url: str = Field(min_length=1, max_length=2_048)
    author: str = Field(min_length=1, max_length=255)
    body: str = Field(default="", max_length=100_000)
    labels: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    merged_at: datetime | None = None
    merge_commit_sha: str | None = Field(default=None, max_length=64)

    _http_url = field_validator("url")(validate_http_url)


class CategoryRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: ReleaseCategory
    labels: tuple[str, ...] = ()
    title_prefixes: tuple[str, ...] = ()


class ChangelogConfig(BaseModel):
    """First matching rule wins, making project-specific precedence explicit."""

    model_config = ConfigDict(frozen=True)

    rules: tuple[CategoryRule, ...]
    fallback: ReleaseCategory = "chore"


class CategorizedPullRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: ReleaseCategory
    pull_request: MergedPullRequest
    matched_by: str = Field(min_length=1, max_length=255)


class Changelog(BaseModel):
    model_config = ConfigDict(frozen=True)

    entries: tuple[CategorizedPullRequest, ...] = ()
    duplicate_github_ids: tuple[int, ...] = ()


class BreakingEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: BreakingEvidenceKind
    text: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=255)


class BreakingCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    pull_request: MergedPullRequest
    evidence: tuple[BreakingEvidence, ...] = Field(min_length=1)
    requires_maintainer_confirmation: Literal[True] = True


class ReleaseDraft(BaseModel):
    """Immutable hand-off shared by preview, persistence and future publishers."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1"] = "1"
    repository: str = Field(min_length=1, max_length=255)
    from_ref: str = Field(min_length=1, max_length=255)
    to_ref: str = Field(min_length=1, max_length=255)
    compare_url: str = Field(min_length=1, max_length=2_048)
    changelog: Changelog
    breaking_candidates: tuple[BreakingCandidate, ...] = ()
    contributors: tuple[str, ...] = ()
    markdown: str = Field(min_length=1)
    limitations: tuple[str, ...] = ()

    _http_compare_url = field_validator("compare_url")(validate_http_url)
