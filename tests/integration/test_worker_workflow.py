from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from maintainerflow.config import Settings
from maintainerflow.core.enums import DeliveryStatus, OutboxStatus
from maintainerflow.core.errors import TransientDependencyError
from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import AnalysisRecord, Base, OutboxEvent
from maintainerflow.persistence.repositories import AnalysisRepository, DeliveryRepository
from maintainerflow.services.analyze_pull_request import analyze_pull_request
from maintainerflow.services.publish_check import queue_check_publish
from maintainerflow.worker import tasks
from tests.helpers import make_envelope

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json"


class FakeAuth:
    async def installation_token(self, *_: object, **__: object) -> SecretStr:
        return SecretStr("installation-token")


async def create_database(path: Path) -> tuple[Database, str]:
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    database = Database(url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database, url


def settings(url: str) -> Settings:
    return Settings(
        environment="test",
        github_app_id=1,
        github_webhook_secret="test-webhook-secret-value",
        github_private_key="unused-in-worker-test",
        database_url=url,
        redis_url="redis://localhost:6379/15",
        workflow_enabled=True,
        check_publish_enabled=True,
    )


async def seed_outbox(database: Database) -> None:
    envelope = make_envelope()
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_copy(
        update={"repository": envelope.repository}
    )
    async with database.session() as session, session.begin():
        delivery, _ = await DeliveryRepository(session).create("publisher", envelope, "req")
        run = await analyze_pull_request(
            source,
            repository=AnalysisRepository(session),
            repository_id=delivery.repository_id,
        )
        assert run.analysis_id is not None
        await queue_check_publish(
            session,
            repository_id=delivery.repository_id,
            repository_github_id=envelope.repository.github_id,
            analysis_id=run.analysis_id,
            installation_id=envelope.installation.github_id,
            owner=envelope.repository.owner,
            repository=envelope.repository.name,
            head_sha=source.head_sha,
            result=run.result,
        )


async def test_delivery_worker_runs_cp1_into_cp2_and_queues_cp3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, url = await create_database(tmp_path / "worker.db")
    envelope = make_envelope()
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_copy(
        update={
            "repository": envelope.repository,
            "number": envelope.pull_request.number,
            "base_sha": envelope.pull_request.base_sha,
            "head_sha": envelope.pull_request.head_sha,
        }
    )
    async with database.session() as session, session.begin():
        delivery, _ = await DeliveryRepository(session).create("worker-bridge", envelope, "req")
        await DeliveryRepository(session).mark_queued(delivery.id)
    await database.dispose()

    class FakeGitHub:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def fetch_pull_request(self, *_: object) -> SimpleNamespace:
            return SimpleNamespace(source=source)

    dispatched: list[bool] = []
    monkeypatch.setattr(tasks, "get_settings", lambda: settings(url))
    monkeypatch.setattr(tasks, "_authenticator", lambda _: FakeAuth())
    monkeypatch.setattr(tasks, "GitHubClient", FakeGitHub)
    monkeypatch.setattr(tasks.dispatch_outbox, "send", lambda: dispatched.append(True))

    await tasks._process_delivery(delivery.id)

    database = Database(url)
    async with database.session() as session:
        stored = await DeliveryRepository(session).get(delivery.id)
        assert stored is not None and stored.status == DeliveryStatus.COMPLETED.value
        assert await session.scalar(select(func.count()).select_from(AnalysisRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 2
    await database.dispose()
    assert dispatched == [True, True]


async def test_outbox_worker_marks_check_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, url = await create_database(tmp_path / "publisher.db")
    await seed_outbox(database)
    await database.dispose()

    class FakeChecks:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def publish(self, _: object) -> int:
            return 321

    monkeypatch.setattr(tasks, "get_settings", lambda: settings(url))
    monkeypatch.setattr(tasks, "_authenticator", lambda _: FakeAuth())
    monkeypatch.setattr(tasks, "GitHubChecksClient", FakeChecks)
    await tasks._dispatch_outbox()

    database = Database(url)
    async with database.session() as session:
        event = await session.scalar(select(OutboxEvent))
        analysis = await session.scalar(select(AnalysisRecord))
        assert event is not None and event.status == OutboxStatus.SENT.value
        assert event.github_check_id == 321
        assert analysis is not None and analysis.publish_status == "completed"
        assert analysis.github_check_id == 321
    await database.dispose()


async def test_outbox_worker_stops_after_retry_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, url = await create_database(tmp_path / "retry-limit.db")
    await seed_outbox(database)
    await database.dispose()

    class OfflineChecks:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def publish(self, _: object) -> int:
            raise TransientDependencyError("offline")

    limited = settings(url).model_copy(update={"outbox_max_attempts": 1})
    monkeypatch.setattr(tasks, "get_settings", lambda: limited)
    monkeypatch.setattr(tasks, "_authenticator", lambda _: FakeAuth())
    monkeypatch.setattr(tasks, "GitHubChecksClient", OfflineChecks)
    await tasks._dispatch_outbox()

    database = Database(url)
    async with database.session() as session:
        event = await session.scalar(select(OutboxEvent))
        analysis = await session.scalar(select(AnalysisRecord))
        assert event is not None and event.status == OutboxStatus.DEAD_LETTER.value
        assert analysis is not None and analysis.publish_status == "failed_safe"
        assert analysis.publish_error == "TransientDependencyError"
    await database.dispose()
