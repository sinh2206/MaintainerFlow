import asyncio
from datetime import UTC, datetime, timedelta

import dramatiq
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.ai.base import AIProvider
from maintainerflow.ai.gemini import GeminiProvider
from maintainerflow.analysis.repository import REPOSITORY_ANALYZER_VERSION, RepositoryContext
from maintainerflow.config import Settings, get_settings
from maintainerflow.core.errors import PermanentDependencyError, TransientDependencyError
from maintainerflow.core.schemas import (
    EventEnvelope,
    GitHubCheckCommand,
    GitHubCheckStartCommand,
    IssueEventEnvelope,
    RepositoryRef,
)
from maintainerflow.github.auth import GitHubAppAuthenticator
from maintainerflow.github.checks import GitHubChecksClient, GitHubRateLimitError
from maintainerflow.github.client import GitHubClient
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.intelligence import (
    IssueAnalysisRepository,
    RepositoryIntelligenceRepository,
)
from maintainerflow.persistence.outbox import OutboxRepository
from maintainerflow.persistence.repositories import AnalysisRepository, DeliveryRepository
from maintainerflow.services.analyze_issue import analyze_issue
from maintainerflow.services.index_repository import index_repository
from maintainerflow.services.process_pull_request import persist_pull_request_analysis
from maintainerflow.services.publish_check import queue_check_start
from maintainerflow.worker.broker import broker as broker


def _authenticator(settings: Settings) -> GitHubAppAuthenticator:
    if settings.github_private_key is None:
        raise PermanentDependencyError("github_private_key_missing")
    return GitHubAppAuthenticator(
        settings.github_app_id,
        settings.github_private_key,
        base_url=settings.github_api_url,
        api_version=settings.github_api_version,
    )


def _ai_provider(settings: Settings) -> AIProvider | None:
    if not settings.ai_enabled:
        return None
    if settings.gemini_api_key is None:
        return None
    return GeminiProvider(
        settings.gemini_api_key,
        model=settings.gemini_model,
        timeout=settings.ai_timeout_seconds,
    )


async def _repository_context(
    github: GitHubClient,
    session: AsyncSession,
    *,
    repository_id: int,
    repository: RepositoryRef,
    sha: str,
    settings: Settings,
) -> RepositoryContext | None:
    if not settings.repository_intelligence_enabled:
        return None
    store = RepositoryIntelligenceRepository(session)
    async with session.begin():
        cached = await store.get(
            repository_id,
            repository,
            sha,
            REPOSITORY_ANALYZER_VERSION,
        )
    if cached:
        return cached
    files, history = await asyncio.gather(
        github.fetch_repository_files(repository.owner, repository.name, sha),
        github.fetch_repository_history(
            repository.owner,
            repository.name,
            rate_limit_floor=settings.github_history_rate_limit_floor,
        ),
    )
    async with session.begin():
        context, _ = await index_repository(
            repository_id=repository_id,
            repository=repository,
            commit_sha=sha,
            files=files,
            store=store,
            history=history.evidence,
            retention_days=settings.intelligence_retention_days,
            store_source=settings.repository_store_source_code,
        )
    return context


async def _process_delivery(delivery_id: int) -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            deliveries = DeliveryRepository(session)
            async with session.begin():
                claimed = await deliveries.claim(delivery_id, settings.delivery_lease_seconds)
                delivery = await deliveries.get(delivery_id)
            if not claimed or delivery is None:
                return
            if not settings.workflow_enabled:
                async with session.begin():
                    await deliveries.complete(delivery_id)
                return

            try:
                if delivery.event_name == "issues":
                    issue_envelope = IssueEventEnvelope.model_validate(delivery.envelope)
                    if not settings.issue_triage_enabled:
                        async with session.begin():
                            await deliveries.complete(delivery_id)
                        return
                    token = await _authenticator(settings).installation_token(
                        issue_envelope.installation.github_id,
                        repository_id=issue_envelope.repository.github_id,
                        issues_read=True,
                        checks_write=False,
                    )
                    github = GitHubClient(
                        token,
                        base_url=settings.github_api_url,
                        api_version=settings.github_api_version,
                    )
                    issue, candidates, labels = await asyncio.gather(
                        github.fetch_issue(issue_envelope.repository, issue_envelope.issue.number),
                        github.list_issues(issue_envelope.repository),
                        github.list_repository_labels(
                            issue_envelope.repository.owner,
                            issue_envelope.repository.name,
                        ),
                    )
                    context = None
                    if settings.repository_intelligence_enabled:
                        sha = await github.fetch_default_branch_sha(
                            issue_envelope.repository.owner,
                            issue_envelope.repository.name,
                        )
                        context = await _repository_context(
                            github,
                            session,
                            repository_id=delivery.repository_id,
                            repository=issue_envelope.repository,
                            sha=sha,
                            settings=settings,
                        )
                    async with session.begin():
                        await analyze_issue(
                            issue,
                            repository_id=delivery.repository_id,
                            session=session,
                            candidates=candidates,
                            available_labels=labels,
                            repository_context=context,
                            retention_days=settings.intelligence_retention_days,
                            store_body=settings.issue_store_body,
                        )
                        await deliveries.complete(delivery_id)
                    return

                envelope = EventEnvelope.model_validate(delivery.envelope)
                if settings.check_publish_enabled:
                    async with session.begin():
                        await queue_check_start(
                            session,
                            delivery_id=delivery.id,
                            repository_id=delivery.repository_id,
                            repository_github_id=envelope.repository.github_id,
                            installation_id=envelope.installation.github_id,
                            owner=envelope.repository.owner,
                            repository=envelope.repository.name,
                            head_sha=envelope.pull_request.head_sha,
                        )
                    dispatch_outbox.send()
                token = await _authenticator(settings).installation_token(
                    envelope.installation.github_id,
                    repository_id=envelope.repository.github_id,
                )
                github = GitHubClient(
                    token,
                    base_url=settings.github_api_url,
                    api_version=settings.github_api_version,
                )
                fetched = await github.fetch_pull_request(
                    envelope.repository.owner,
                    envelope.repository.name,
                    envelope.pull_request.number,
                )
                context = await _repository_context(
                    github,
                    session,
                    repository_id=delivery.repository_id,
                    repository=envelope.repository,
                    sha=fetched.source.base_sha,
                    settings=settings,
                )
                async with session.begin():
                    await persist_pull_request_analysis(
                        session,
                        delivery_id=delivery_id,
                        repository_id=delivery.repository_id,
                        envelope=envelope,
                        source=fetched.source,
                        settings=settings,
                        ai_provider=_ai_provider(settings),
                        repository_context=context,
                    )
                if settings.check_publish_enabled:
                    dispatch_outbox.send()
            except TransientDependencyError as exc:
                async with session.begin():
                    await deliveries.release_for_retry(delivery_id, type(exc).__name__)
                raise
            except (PermanentDependencyError, ValidationError) as exc:
                async with session.begin():
                    await deliveries.fail_safe(delivery_id, type(exc).__name__)
            except Exception as exc:
                async with session.begin():
                    await deliveries.release_for_retry(delivery_id, type(exc).__name__)
                raise
    finally:
        await database.dispose()


@dramatiq.actor(queue_name="deliveries", max_retries=5, min_backoff=1_000, max_backoff=60_000)
def process_delivery(delivery_id: int) -> None:
    asyncio.run(_process_delivery(delivery_id))


async def _dispatch_outbox() -> None:
    settings = get_settings()
    if not settings.check_publish_enabled:
        return
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            outbox = OutboxRepository(session)
            async with session.begin():
                events = await outbox.claim(
                    settings.outbox_batch_size, settings.outbox_lease_seconds
                )
            for event in events:
                analysis_id: int | None = None
                command: GitHubCheckStartCommand | GitHubCheckCommand
                try:
                    if event.event_type == "github_check.start":
                        command = GitHubCheckStartCommand.model_validate(event.payload)
                    else:
                        command = GitHubCheckCommand.model_validate(event.payload)
                        analysis_id = command.analysis_id
                    token = await _authenticator(settings).installation_token(
                        command.installation_id,
                        repository_id=command.repository_github_id,
                    )
                    checks = GitHubChecksClient(
                        token,
                        base_url=settings.github_api_url,
                        api_version=settings.github_api_version,
                    )
                    check_id = (
                        await checks.start(command)
                        if isinstance(command, GitHubCheckStartCommand)
                        else await checks.publish(command)
                    )
                    async with session.begin():
                        await outbox.mark_sent(event.id, check_id)
                        if analysis_id is not None:
                            await AnalysisRepository(session).mark_published(analysis_id, check_id)
                except TransientDependencyError as exc:
                    async with session.begin():
                        if event.attempts >= settings.outbox_max_attempts:
                            await outbox.dead_letter(event.id, type(exc).__name__)
                            if analysis_id is not None:
                                await AnalysisRepository(session).mark_publish_failed(
                                    analysis_id, type(exc).__name__
                                )
                        else:
                            delay = (
                                exc.retry_after
                                if isinstance(exc, GitHubRateLimitError)
                                else min(300, 2 ** min(event.attempts, 8))
                            )
                            await outbox.retry(event.id, type(exc).__name__, delay)
                except (PermanentDependencyError, ValidationError) as exc:
                    async with session.begin():
                        await outbox.dead_letter(event.id, type(exc).__name__)
                        if analysis_id is not None:
                            await AnalysisRepository(session).mark_publish_failed(
                                analysis_id, type(exc).__name__
                            )
    finally:
        await database.dispose()


@dramatiq.actor(queue_name="outbox", max_retries=3, min_backoff=2_000, max_backoff=60_000)
def dispatch_outbox() -> None:
    asyncio.run(_dispatch_outbox())


async def _find_recoverable() -> list[int]:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            repository = DeliveryRepository(session)
            return await repository.recoverable_ids(
                datetime.now(UTC) - timedelta(seconds=settings.recovery_interval_seconds * 2),
                settings.recovery_batch_size,
            )
    finally:
        await database.dispose()


async def _purge_expired_intelligence() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.session() as session, session.begin():
            await IssueAnalysisRepository(session).purge_expired()
            await RepositoryIntelligenceRepository(session).purge_expired()
    finally:
        await database.dispose()


@dramatiq.actor(queue_name="maintenance", max_retries=3, min_backoff=2_000)
def recover_deliveries() -> None:
    for delivery_id in asyncio.run(_find_recoverable()):
        process_delivery.send(delivery_id)
    asyncio.run(_purge_expired_intelligence())
    dispatch_outbox.send()
