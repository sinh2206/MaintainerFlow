from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.analysis.languages.base import LanguageAnalysis
from maintainerflow.analysis.repository import RepositoryContext
from maintainerflow.core.schemas import Evidence, RepositoryRef
from maintainerflow.issue.schemas import IssueTriageResult
from maintainerflow.persistence.models import (
    HistoricalEvidenceRecord,
    IssueAnalysisRecord,
    RepositoryIndexRecord,
)


class RepositoryIntelligenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self,
        repository_id: int,
        repository: RepositoryRef,
        commit_sha: str,
        analyzer_version: str,
    ) -> RepositoryContext | None:
        row = await self.session.scalar(
            select(RepositoryIndexRecord).where(
                RepositoryIndexRecord.repository_id == repository_id,
                RepositoryIndexRecord.commit_sha == commit_sha,
                RepositoryIndexRecord.analyzer_version == analyzer_version,
                RepositoryIndexRecord.expires_at > datetime.now(UTC),
            )
        )
        if row is None:
            return None
        history_rows = await self.session.scalars(
            select(HistoricalEvidenceRecord)
            .where(HistoricalEvidenceRecord.repository_index_id == row.id)
            .order_by(HistoricalEvidenceRecord.id)
        )
        history = tuple(
            Evidence(
                kind=item.kind,
                path=item.path,
                message=str(item.payload["message"]),
                source="github-history",
                confidence=float(item.payload["confidence"]),
                metadata={
                    "id": item.source_id,
                    "url": item.source_url,
                    **item.payload.get("metadata", {}),
                },
            )
            for item in history_rows
        )
        return RepositoryContext(
            repository=repository,
            commit_sha=row.commit_sha,
            analyzer_version=row.analyzer_version,
            file_tree=tuple(row.file_tree),
            modules=tuple(LanguageAnalysis.model_validate(item) for item in row.modules),
            dependency_graph={key: tuple(value) for key, value in row.dependency_graph.items()},
            criticality=row.criticality,
            related_tests={key: tuple(value) for key, value in row.related_tests.items()},
            history=history,
            limitations=tuple(row.limitations),
        )

    async def save(
        self,
        repository_id: int,
        context: RepositoryContext,
        *,
        retention_days: int,
        source_archive: dict[str, str] | None = None,
    ) -> RepositoryIndexRecord:
        expires_at = datetime.now(UTC) + timedelta(days=retention_days)
        row = RepositoryIndexRecord(
            repository_id=repository_id,
            commit_sha=context.commit_sha,
            analyzer_version=context.analyzer_version,
            file_tree=list(context.file_tree),
            modules=[item.model_dump(mode="json") for item in context.modules],
            dependency_graph={key: list(value) for key, value in context.dependency_graph.items()},
            criticality=context.criticality,
            related_tests={key: list(value) for key, value in context.related_tests.items()},
            limitations=list(context.limitations),
            source_archive=source_archive,
            expires_at=expires_at,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(row)
                await self.session.flush()
        except IntegrityError:
            existing = await self.session.scalar(
                select(RepositoryIndexRecord).where(
                    RepositoryIndexRecord.repository_id == repository_id,
                    RepositoryIndexRecord.commit_sha == context.commit_sha,
                    RepositoryIndexRecord.analyzer_version == context.analyzer_version,
                )
            )
            if existing is None:
                raise
            return existing
        for item in context.history:
            source_id = str(item.metadata.get("id", "unknown"))
            source_url = str(item.metadata.get("url", ""))
            self.session.add(
                HistoricalEvidenceRecord(
                    repository_index_id=row.id,
                    kind=item.kind,
                    source_id=source_id,
                    source_url=source_url,
                    path=item.path,
                    payload={
                        "message": item.message,
                        "confidence": item.confidence,
                        "metadata": {
                            key: value
                            for key, value in item.metadata.items()
                            if key not in {"id", "url"}
                        },
                    },
                    expires_at=expires_at,
                )
            )
        await self.session.flush()
        return row

    async def purge_expired(self) -> int:
        result = await self.session.execute(
            delete(RepositoryIndexRecord).where(
                RepositoryIndexRecord.expires_at <= datetime.now(UTC)
            )
        )
        return int(getattr(result, "rowcount", 0))

    async def delete_repository(self, repository_id: int) -> int:
        result = await self.session.execute(
            delete(RepositoryIndexRecord).where(
                RepositoryIndexRecord.repository_id == repository_id
            )
        )
        return int(getattr(result, "rowcount", 0))


class IssueAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(
        self,
        repository_id: int,
        github_issue_id: int,
        issue_number: int,
        result: IssueTriageResult,
        *,
        retention_days: int,
        body_text: str | None = None,
    ) -> tuple[IssueAnalysisRecord, bool]:
        found = await self.session.scalar(
            select(IssueAnalysisRecord).where(
                IssueAnalysisRecord.repository_id == repository_id,
                IssueAnalysisRecord.github_issue_id == github_issue_id,
                IssueAnalysisRecord.source_hash == result.source_hash,
            )
        )
        if found:
            return found, False
        row = IssueAnalysisRecord(
            repository_id=repository_id,
            github_issue_id=github_issue_id,
            issue_number=issue_number,
            source_hash=result.source_hash,
            classification=result.classification.category,
            confidence=result.classification.confidence,
            evidence_spans=[
                item.model_dump(mode="json") for item in result.classification.evidence
            ],
            priority=result.priority.level,
            priority_score=result.priority.score,
            label_suggestions=[item.model_dump(mode="json") for item in result.labels],
            similar_issues=[item.model_dump(mode="json") for item in result.similar_issues],
            limitations=list(result.limitations),
            body_text=body_text,
            expires_at=datetime.now(UTC) + timedelta(days=retention_days),
        )
        try:
            async with self.session.begin_nested():
                self.session.add(row)
                await self.session.flush()
        except IntegrityError:
            found = await self.session.scalar(
                select(IssueAnalysisRecord).where(
                    IssueAnalysisRecord.repository_id == repository_id,
                    IssueAnalysisRecord.github_issue_id == github_issue_id,
                    IssueAnalysisRecord.source_hash == result.source_hash,
                )
            )
            if found is None:
                raise
            return found, False
        return row, True

    async def get(self, record_id: int) -> IssueAnalysisRecord | None:
        return cast(
            IssueAnalysisRecord | None, await self.session.get(IssueAnalysisRecord, record_id)
        )

    async def purge_expired(self) -> int:
        result = await self.session.execute(
            delete(IssueAnalysisRecord).where(IssueAnalysisRecord.expires_at <= datetime.now(UTC))
        )
        return int(getattr(result, "rowcount", 0))

    async def delete_repository(self, repository_id: int) -> int:
        result = await self.session.execute(
            delete(IssueAnalysisRecord).where(IssueAnalysisRecord.repository_id == repository_id)
        )
        return int(getattr(result, "rowcount", 0))
