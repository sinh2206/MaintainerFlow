from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.core.enums import AnalysisStatus, DeliveryStatus, RiskLevel
from maintainerflow.core.schemas import (
    AnalysisResult,
    AnalysisSnapshot,
    EventEnvelope,
    Evidence,
    Risk,
)
from maintainerflow.persistence.models import (
    AnalysisRecord,
    AnalysisSnapshotRecord,
    Delivery,
    EvidenceRecord,
    GitHubInstallation,
    Repository,
)


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_or_create_installation(self, github_id: int) -> GitHubInstallation:
        found = await self.session.scalar(
            select(GitHubInstallation).where(GitHubInstallation.github_id == github_id)
        )
        if found:
            return found
        installation = GitHubInstallation(github_id=github_id)
        try:
            async with self.session.begin_nested():
                self.session.add(installation)
                await self.session.flush()
            return installation
        except IntegrityError:
            found = cast(
                GitHubInstallation | None,
                await self.session.scalar(
                    select(GitHubInstallation).where(GitHubInstallation.github_id == github_id)
                ),
            )
            if found is None:
                raise
            return found

    async def _get_or_create_repository(
        self, envelope: EventEnvelope, installation: GitHubInstallation
    ) -> Repository:
        github_id = envelope.repository.github_id
        found = await self.session.scalar(
            select(Repository).where(Repository.github_id == github_id)
        )
        if found:
            found.installation_id = installation.id
            found.owner = envelope.repository.owner
            found.name = envelope.repository.name
            return found
        repository = Repository(
            github_id=github_id,
            installation_id=installation.id,
            owner=envelope.repository.owner,
            name=envelope.repository.name,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(repository)
                await self.session.flush()
            return repository
        except IntegrityError:
            found = cast(
                Repository | None,
                await self.session.scalar(
                    select(Repository).where(Repository.github_id == github_id)
                ),
            )
            if found is None:
                raise
            found.installation_id = installation.id
            found.owner = envelope.repository.owner
            found.name = envelope.repository.name
            return found

    async def create(
        self,
        github_delivery_id: str,
        envelope: EventEnvelope,
        request_id: str,
    ) -> tuple[Delivery, bool]:
        existing = await self.get_by_github_id(github_delivery_id)
        if existing:
            return existing, False

        installation = await self._get_or_create_installation(envelope.installation.github_id)
        repository = await self._get_or_create_repository(envelope, installation)
        try:
            async with self.session.begin_nested():
                delivery = Delivery(
                    github_delivery_id=github_delivery_id,
                    repository_id=repository.id,
                    event_name=envelope.event,
                    action=envelope.action,
                    envelope=envelope.model_dump(mode="json"),
                    request_id=request_id,
                )
                self.session.add(delivery)
                await self.session.flush()
            return delivery, True
        except IntegrityError:
            existing = await self.get_by_github_id(github_delivery_id)
            if existing is None:
                raise
            return existing, False

    async def get_by_github_id(self, github_delivery_id: str) -> Delivery | None:
        return cast(
            Delivery | None,
            await self.session.scalar(
                select(Delivery).where(Delivery.github_delivery_id == github_delivery_id)
            ),
        )

    async def get(self, delivery_id: int) -> Delivery | None:
        return cast(Delivery | None, await self.session.get(Delivery, delivery_id))

    async def mark_queued(self, delivery_id: int) -> None:
        now = datetime.now(UTC)
        await self.session.execute(
            update(Delivery)
            .where(
                Delivery.id == delivery_id,
                Delivery.status == DeliveryStatus.RECEIVED.value,
            )
            .values(status=DeliveryStatus.QUEUED.value, queued_at=now)
        )

    async def claim(self, delivery_id: int, lease_seconds: int) -> bool:
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(Delivery)
            .where(
                Delivery.id == delivery_id,
                Delivery.status != DeliveryStatus.COMPLETED.value,
                or_(
                    Delivery.status.in_(
                        [DeliveryStatus.RECEIVED.value, DeliveryStatus.QUEUED.value]
                    ),
                    Delivery.lease_expires_at < now,
                ),
            )
            .values(
                status=DeliveryStatus.PROCESSING.value,
                attempts=Delivery.attempts + 1,
                processing_started_at=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                last_error=None,
            )
        )
        return bool(cast(CursorResult[Any], result).rowcount)

    async def complete(self, delivery_id: int) -> None:
        await self.session.execute(
            update(Delivery)
            .where(Delivery.id == delivery_id, Delivery.status == DeliveryStatus.PROCESSING.value)
            .values(
                status=DeliveryStatus.COMPLETED.value,
                processed_at=datetime.now(UTC),
                lease_expires_at=None,
            )
        )

    async def release_for_retry(self, delivery_id: int, error: str) -> None:
        await self.session.execute(
            update(Delivery)
            .where(Delivery.id == delivery_id, Delivery.status == DeliveryStatus.PROCESSING.value)
            .values(
                status=DeliveryStatus.QUEUED.value,
                queued_at=datetime.now(UTC),
                lease_expires_at=None,
                last_error=error[:500],
            )
        )

    async def fail_safe(self, delivery_id: int, error: str) -> None:
        await self.session.execute(
            update(Delivery)
            .where(Delivery.id == delivery_id)
            .values(
                status=DeliveryStatus.FAILED_SAFE.value,
                processed_at=datetime.now(UTC),
                lease_expires_at=None,
                last_error=error[:500],
            )
        )

    async def recoverable_ids(self, queued_before: datetime, limit: int) -> list[int]:
        now = datetime.now(UTC)
        rows = await self.session.scalars(
            select(Delivery.id)
            .where(
                or_(
                    Delivery.status == DeliveryStatus.RECEIVED.value,
                    (Delivery.status == DeliveryStatus.QUEUED.value)
                    & (Delivery.queued_at < queued_before),
                    (Delivery.status == DeliveryStatus.PROCESSING.value)
                    & (Delivery.lease_expires_at < now),
                )
            )
            .order_by(Delivery.id)
            .limit(limit)
        )
        return list(rows)


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_record(self, snapshot_id: str) -> AnalysisRecord | None:
        return cast(
            AnalysisRecord | None,
            await self.session.scalar(
                select(AnalysisRecord).where(AnalysisRecord.snapshot_id == snapshot_id)
            ),
        )

    async def save(
        self,
        repository_id: int,
        snapshot: AnalysisSnapshot,
        result: AnalysisResult,
    ) -> tuple[AnalysisRecord, bool]:
        existing = await self.get_record(snapshot.id)
        if existing:
            return existing, False
        if await self.session.get(AnalysisSnapshotRecord, snapshot.id) is None:
            self.session.add(
                AnalysisSnapshotRecord(
                    id=snapshot.id,
                    repository_id=repository_id,
                    pull_request_number=snapshot.pull_request_number,
                    base_sha=snapshot.base_sha,
                    head_sha=snapshot.head_sha,
                    diff_hash=snapshot.diff_hash,
                    metadata_hash=snapshot.metadata_hash,
                    config_hash=snapshot.config_hash,
                    rules_version=snapshot.rules_version,
                    prompt_version=snapshot.prompt_version,
                    model_version=snapshot.model_version,
                )
            )
            await self.session.flush()
        analysis = AnalysisRecord(
            snapshot_id=snapshot.id,
            schema_version=result.schema_version,
            status=result.status.value,
            summary=result.summary,
            risk_score=result.risk.score,
            risk_level=result.risk.level.value,
            risk_confidence=result.risk.confidence,
            evidence_coverage=result.evidence_coverage,
            suggested_tests=list(result.suggested_tests),
            review_focus=list(result.review_focus),
            limitations=list(result.limitations),
            provider_metadata=result.provider_metadata,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(analysis)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_record(snapshot.id)
            if existing is None:
                raise
            return existing, False
        self.session.add_all(
            EvidenceRecord(
                analysis_id=analysis.id,
                kind=item.kind,
                path=item.path,
                line=item.line,
                message=item.message,
                source=item.source,
                confidence=item.confidence,
                evidence_metadata=item.metadata,
            )
            for item in result.evidence
        )
        await self.session.flush()
        return analysis, True

    async def get_result(self, snapshot_id: str) -> AnalysisResult | None:
        analysis = await self.get_record(snapshot_id)
        if analysis is None:
            return None
        rows = await self.session.scalars(
            select(EvidenceRecord)
            .where(EvidenceRecord.analysis_id == analysis.id)
            .order_by(EvidenceRecord.id)
        )
        evidence = tuple(
            Evidence(
                kind=row.kind,
                path=row.path,
                line=row.line,
                message=row.message,
                source=row.source,
                confidence=row.confidence,
                metadata=row.evidence_metadata,
            )
            for row in rows
        )
        return AnalysisResult(
            schema_version="1",
            snapshot_id=snapshot_id,
            status=AnalysisStatus(analysis.status),
            summary=analysis.summary,
            risk=Risk(
                score=analysis.risk_score,
                level=RiskLevel(analysis.risk_level),
                confidence=analysis.risk_confidence,
            ),
            evidence_coverage=analysis.evidence_coverage,
            evidence=evidence,
            suggested_tests=tuple(analysis.suggested_tests),
            review_focus=tuple(analysis.review_focus),
            limitations=tuple(analysis.limitations),
            provider_metadata=analysis.provider_metadata,
        )
