from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from maintainerflow.core.enums import AnalysisStatus, RiskLevel

JsonObject = dict[str, Any]
ChangeType = Literal["added", "deleted", "modified", "renamed", "binary", "unknown"]


class RepositoryRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    github_id: int = Field(gt=0)
    owner: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)


class InstallationRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    github_id: int = Field(gt=0)


class PullRequestRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int = Field(gt=0)
    base_sha: str = Field(min_length=7, max_length=64)
    head_sha: str = Field(min_length=7, max_length=64)


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: Literal["pull_request"]
    action: Literal["opened", "synchronize"]
    repository: RepositoryRef
    installation: InstallationRef
    pull_request: PullRequestRef


class WebhookResponse(BaseModel):
    status: Literal["accepted", "duplicate", "ignored"]
    delivery_id: int | None = None


class ChangedFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1, max_length=4096)
    previous_path: str | None = Field(default=None, max_length=4096)
    change_type: ChangeType
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    patch: str = ""
    malformed: bool = False


class PullRequestSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository: RepositoryRef
    number: int = Field(gt=0)
    base_sha: str = Field(min_length=7, max_length=64)
    head_sha: str = Field(min_length=7, max_length=64)
    title: str = Field(default="", max_length=1000)
    body: str = Field(default="", max_length=100_000)
    diff: str = ""
    changed_files: tuple[ChangedFile, ...] = ()


class AnalysisSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=64, max_length=64)
    repository: RepositoryRef
    pull_request_number: int = Field(gt=0)
    base_sha: str = Field(min_length=7, max_length=64)
    head_sha: str = Field(min_length=7, max_length=64)
    diff_hash: str = Field(min_length=64, max_length=64)
    metadata_hash: str = Field(min_length=64, max_length=64)
    config_hash: str = Field(min_length=64, max_length=64)
    rules_version: str = Field(min_length=1, max_length=64)
    prompt_version: str = Field(min_length=1, max_length=64)
    model_version: str = Field(min_length=1, max_length=128)


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, max_length=64)
    path: str | None = Field(default=None, max_length=4096)
    line: int | None = Field(default=None, ge=1)
    message: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=128)
    confidence: float = Field(ge=0, le=1)
    metadata: JsonObject = Field(default_factory=dict)


class Risk(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0, le=10)
    level: RiskLevel
    confidence: float = Field(ge=0, le=1)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1"] = "1"
    snapshot_id: str = Field(min_length=64, max_length=64)
    status: AnalysisStatus
    summary: str = Field(min_length=1, max_length=4000)
    risk: Risk
    evidence_coverage: float = Field(ge=0, le=1)
    evidence: tuple[Evidence, ...] = ()
    suggested_tests: tuple[str, ...] = ()
    review_focus: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    provider_metadata: JsonObject | None = None
