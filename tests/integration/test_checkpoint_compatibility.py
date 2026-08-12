import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from maintainerflow.config import Settings
from maintainerflow.core.enums import DeliveryStatus, OutboxStatus
from maintainerflow.core.schemas import (
    GitHubCheckCommand,
    GitHubCheckStartCommand,
    PullRequestSource,
    RepositoryRef,
)
from maintainerflow.github.checks import safe_text
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import (
    AnalysisRecord,
    AnalysisSnapshotRecord,
    AuditEvent,
    Delivery,
    EvidenceRecord,
    OutboxEvent,
)
from maintainerflow.worker import tasks
from tests.helpers import signature

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json"


def test_cp1_webhook_runs_cp2_report_into_one_cp3_check(
    app_client: tuple[TestClient, list[int], str],
    github_payload: dict[str, object],
    webhook_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, queued, database_url = app_client
    body = json.dumps(github_payload, separators=(",", ":")).encode()
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "cp1-cp2-cp3-contract",
            "X-Hub-Signature-256": signature(body, webhook_secret),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    assert queued == [response.json()["delivery_id"]]

    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_copy(
        update={
            "repository": RepositoryRef(github_id=123, owner="sinh2206", name="MaintainerFlow"),
            "number": 5,
            "base_sha": "a" * 40,
            "head_sha": "b" * 40,
        }
    )
    worker_settings = Settings(
        environment="test",
        github_app_id=1,
        github_webhook_secret=webhook_secret,
        github_private_key="unused-in-contract-test",
        database_url=database_url,
        redis_url="redis://localhost:6379/15",
        workflow_enabled=True,
        check_publish_enabled=True,
    )
    token_scopes: list[tuple[int, int | None]] = []
    check_calls: list[GitHubCheckStartCommand | GitHubCheckCommand] = []

    class FakeAuth:
        async def installation_token(
            self, installation_id: int, *, repository_id: int | None = None
        ) -> SecretStr:
            token_scopes.append((installation_id, repository_id))
            return SecretStr("installation-token")

    class FakeGitHub:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def fetch_pull_request(self, *_: object) -> SimpleNamespace:
            return SimpleNamespace(source=source)

    class FakeChecks:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def start(self, command: GitHubCheckStartCommand) -> int:
            check_calls.append(command)
            return 9001

        async def publish(self, command: GitHubCheckCommand) -> int:
            check_calls.append(command)
            return 9001

    monkeypatch.setattr(tasks, "get_settings", lambda: worker_settings)
    monkeypatch.setattr(tasks, "_authenticator", lambda _: FakeAuth())
    monkeypatch.setattr(tasks, "GitHubClient", FakeGitHub)
    monkeypatch.setattr(tasks, "GitHubChecksClient", FakeChecks)
    monkeypatch.setattr(tasks.dispatch_outbox, "send", lambda: None)

    asyncio.run(tasks._process_delivery(queued[0]))
    asyncio.run(tasks._dispatch_outbox())

    async def verify() -> None:
        database = Database(database_url)
        try:
            async with database.session() as session:
                delivery = await session.get(Delivery, queued[0])
                analysis = await session.scalar(select(AnalysisRecord))
                events = list(await session.scalars(select(OutboxEvent).order_by(OutboxEvent.id)))
                assert delivery is not None and delivery.status == DeliveryStatus.COMPLETED.value
                assert analysis is not None and analysis.publish_status == "completed"
                assert analysis.github_check_id == 9001
                assert (
                    await session.scalar(select(func.count()).select_from(AnalysisSnapshotRecord))
                    == 1
                )
                assert await session.scalar(select(func.count()).select_from(EvidenceRecord))
                assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 2
                assert len(events) == 2
                assert {event.status for event in events} == {OutboxStatus.SENT.value}
                final = GitHubCheckCommand.model_validate(events[1].payload)
                assert final.analysis_id == analysis.id
                assert final.external_id == str(analysis.id)
                assert final.provisional_external_id == f"delivery:{delivery.id}"
                assert final.summary == safe_text(analysis.summary, 65_535)
                assert final.title == safe_text(
                    f"MaintainerFlow: {analysis.risk_level.upper()} risk "
                    f"({analysis.risk_score}/10)",
                    255,
                )
                assert "Suggested tests" in final.text
                assert "Review focus" in final.text
                assert all(safe_text(item, 500) in final.text for item in analysis.suggested_tests)
                assert all(safe_text(item, 500) in final.text for item in analysis.review_focus)
        finally:
            await database.dispose()

    asyncio.run(verify())
    start, final = check_calls
    assert isinstance(start, GitHubCheckStartCommand)
    assert isinstance(final, GitHubCheckCommand)
    assert start.head_sha == final.head_sha == "b" * 40
    assert start.repository_github_id == final.repository_github_id == 123
    assert token_scopes == [(77, 123), (77, 123), (77, 123)]
