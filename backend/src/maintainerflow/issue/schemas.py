from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from maintainerflow.core.schemas import RepositoryRef

IssueCategory = Literal["bug", "feature", "docs", "question", "maintenance"]
PriorityLevel = Literal["low", "medium", "high", "critical"]


class TextEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=200)
    rule: str = Field(min_length=1, max_length=64)


class IssueClassification(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: IssueCategory
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[TextEvidence, ...] = ()


class IssueSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository: RepositoryRef
    github_id: int = Field(gt=0)
    number: int = Field(gt=0)
    title: str = Field(default="", max_length=1_000)
    body: str = Field(default="", max_length=100_000)
    url: str = Field(min_length=1, max_length=2_048)
    labels: tuple[str, ...] = ()


class SimilarIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    github_id: int = Field(gt=0)
    number: int = Field(gt=0)
    url: str = Field(min_length=1, max_length=2_048)
    score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=128)


class PrioritySuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: PriorityLevel
    score: float = Field(ge=0, le=10)
    reasons: tuple[str, ...] = ()


class LabelSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    canonical: str = Field(min_length=1, max_length=255)
    repository_label: str | None = Field(default=None, max_length=255)
    available: bool
    reason: str = Field(min_length=1, max_length=255)


class IssueTriageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1"] = "1"
    source_hash: str = Field(min_length=64, max_length=64)
    classification: IssueClassification
    priority: PrioritySuggestion
    labels: tuple[LabelSuggestion, ...] = ()
    similar_issues: tuple[SimilarIssue, ...] = ()
    limitations: tuple[str, ...] = ()
