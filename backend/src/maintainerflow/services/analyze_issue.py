import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.analysis.repository import RepositoryContext
from maintainerflow.issue.classifier import classify_issue
from maintainerflow.issue.duplicate import LexicalDuplicateEngine
from maintainerflow.issue.labels import suggest_labels
from maintainerflow.issue.priority import suggest_priority
from maintainerflow.issue.schemas import IssueSource, IssueTriageResult
from maintainerflow.persistence.intelligence import IssueAnalysisRepository
from maintainerflow.persistence.repositories import AuditRepository


@dataclass(frozen=True)
class IssueAnalysisRun:
    result: IssueTriageResult
    persisted: bool
    analysis_id: int | None = None


def issue_source_hash(issue: IssueSource) -> str:
    payload = json.dumps(
        {"title": issue.title.strip(), "body": issue.body.strip()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def analyze_issue(
    issue: IssueSource,
    *,
    repository_id: int,
    session: AsyncSession,
    candidates: tuple[IssueSource, ...] = (),
    available_labels: tuple[str, ...] = (),
    repository_context: RepositoryContext | None = None,
    retention_days: int = 30,
    store_body: bool = False,
) -> IssueAnalysisRun:
    classification = classify_issue(issue.title, issue.body)
    limitations = ["duplicate_detection_uses_lexical_baseline"]
    if repository_context is None:
        limitations.append("repository_context_unavailable")
    result = IssueTriageResult(
        source_hash=issue_source_hash(issue),
        classification=classification,
        priority=suggest_priority(issue.title, issue.body, classification),
        labels=suggest_labels(classification, available_labels),
        similar_issues=LexicalDuplicateEngine().rank(issue, candidates),
        limitations=tuple(limitations),
    )
    record, persisted = await IssueAnalysisRepository(session).save(
        repository_id,
        issue.github_id,
        issue.number,
        result,
        retention_days=retention_days,
        body_text=issue.body if store_body else None,
    )
    if persisted:
        await AuditRepository(session).record(
            "issue.triage.suggested",
            repository_id=repository_id,
            analysis_id=None,
            issue_analysis_id=record.id,
            payload={
                "issue_number": issue.number,
                "classification": result.classification.category,
                "confidence": result.classification.confidence,
                "priority": result.priority.level,
                "labels": [item.model_dump(mode="json") for item in result.labels],
                "similar_issues": [item.model_dump(mode="json") for item in result.similar_issues],
                "side_effects": [],
            },
        )
    return IssueAnalysisRun(result, persisted, record.id)
