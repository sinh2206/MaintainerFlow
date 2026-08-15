from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.core.policies import decide_check_policy
from maintainerflow.core.schemas import AnalysisResult, CheckPolicyDecision, GitHubCheckStartCommand
from maintainerflow.github.checks import build_check_command
from maintainerflow.persistence.outbox import OutboxRepository
from maintainerflow.persistence.repositories import AnalysisRepository, AuditRepository


@dataclass(frozen=True)
class QueueCheckResult:
    outbox_id: int | None
    created: bool
    decision: CheckPolicyDecision


async def queue_check_start(
    session: AsyncSession,
    *,
    delivery_id: int,
    repository_id: int,
    repository_github_id: int,
    installation_id: int,
    owner: str,
    repository: str,
    head_sha: str,
) -> bool:
    command = GitHubCheckStartCommand(
        delivery_id=delivery_id,
        installation_id=installation_id,
        repository_github_id=repository_github_id,
        owner=owner,
        repository=repository,
        head_sha=head_sha,
        external_id=f"delivery:{delivery_id}",
    )
    event, created = await OutboxRepository(session).enqueue(
        event_type="github_check.start",
        aggregate_id=f"delivery:{delivery_id}",
        idempotency_key=f"github-check-start:{delivery_id}:{head_sha}",
        payload=command.model_dump(mode="json"),
    )
    if created:
        await AuditRepository(session).record(
            "check_start_queued",
            repository_id=repository_id,
            analysis_id=None,
            payload={"idempotency_key": event.idempotency_key},
        )
    return created


async def queue_check_publish(
    session: AsyncSession,
    *,
    repository_id: int,
    repository_github_id: int,
    analysis_id: int,
    installation_id: int,
    owner: str,
    repository: str,
    head_sha: str,
    result: AnalysisResult,
    mode: Literal["shadow", "suggestion"] = "shadow",
    stale: bool = False,
    delivery_id: int | None = None,
) -> QueueCheckResult:
    decision = decide_check_policy(result, mode=mode, stale=stale)
    audit = AuditRepository(session)
    if not decision.publish:
        await audit.record(
            "check_publish_suppressed",
            repository_id=repository_id,
            analysis_id=analysis_id,
            payload={"reason": decision.reason},
        )
        return QueueCheckResult(None, False, decision)

    command = build_check_command(
        analysis_id=analysis_id,
        installation_id=installation_id,
        repository_github_id=repository_github_id,
        owner=owner,
        repository=repository,
        head_sha=head_sha,
        result=result,
        decision=decision,
        provisional_external_id=f"delivery:{delivery_id}" if delivery_id else None,
    )
    outbox, created = await OutboxRepository(session).enqueue(
        event_type="github_check.publish",
        aggregate_id=str(analysis_id),
        idempotency_key=f"github-check:{analysis_id}:{head_sha}",
        payload=command.model_dump(mode="json"),
    )
    if created:
        await AnalysisRepository(session).mark_publish_queued(analysis_id)
        await audit.record(
            "check_publish_queued",
            repository_id=repository_id,
            analysis_id=analysis_id,
            payload={"mode": mode, "idempotency_key": outbox.idempotency_key},
        )
    return QueueCheckResult(outbox.id, created, decision)
