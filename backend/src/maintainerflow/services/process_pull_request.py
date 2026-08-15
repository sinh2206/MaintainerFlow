from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.ai.base import AIProvider
from maintainerflow.analysis.repository import RepositoryContext
from maintainerflow.config import Settings
from maintainerflow.core.schemas import EventEnvelope, PullRequestSource
from maintainerflow.persistence.repositories import AnalysisRepository, DeliveryRepository
from maintainerflow.services.analyze_pull_request import AnalysisRun, analyze_pull_request
from maintainerflow.services.publish_check import queue_check_publish


async def persist_pull_request_analysis(
    session: AsyncSession,
    *,
    delivery_id: int,
    repository_id: int,
    envelope: EventEnvelope,
    source: PullRequestSource,
    settings: Settings,
    ai_provider: AIProvider | None = None,
    repository_context: RepositoryContext | None = None,
) -> AnalysisRun:
    run = await analyze_pull_request(
        source,
        max_diff_bytes=settings.analysis_max_diff_bytes,
        model_version=settings.gemini_model if ai_provider else "static-only",
        ai_provider=ai_provider,
        repository=AnalysisRepository(session),
        repository_id=repository_id,
        repository_context=repository_context,
    )
    if run.analysis_id is None:
        raise RuntimeError("persisted analysis has no ID")
    if settings.check_publish_enabled:
        await queue_check_publish(
            session,
            repository_id=repository_id,
            repository_github_id=envelope.repository.github_id,
            analysis_id=run.analysis_id,
            installation_id=envelope.installation.github_id,
            owner=envelope.repository.owner,
            repository=envelope.repository.name,
            head_sha=source.head_sha,
            result=run.result,
            mode=settings.check_mode,
            stale=source.head_sha != envelope.pull_request.head_sha,
            delivery_id=delivery_id,
        )
    await DeliveryRepository(session).complete(delivery_id)
    return run
