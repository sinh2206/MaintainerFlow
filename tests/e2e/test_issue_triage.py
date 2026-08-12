import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from maintainerflow.config import Settings
from maintainerflow.core.enums import DeliveryStatus
from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.issue.schemas import IssueSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import (
    AnalysisRecord,
    AuditEvent,
    Delivery,
    IssueAnalysisRecord,
    OutboxEvent,
)
from maintainerflow.worker import tasks
from tests.helpers import signature

pytestmark = pytest.mark.e2e


def test_issue_opened_creates_shadow_suggestions_without_github_writes(
    app_client: tuple[TestClient, list[int], str],
    webhook_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, queued, database_url = app_client
    payload = {
        "action": "opened",
        "installation": {"id": 77},
        "repository": {
            "id": 123,
            "name": "MaintainerFlow",
            "owner": {"login": "sinh2206"},
        },
        "issue": {"id": 901, "number": 41},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "cp4-issue-contract",
            "X-Hub-Signature-256": signature(body, webhook_secret),
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    assert queued == [response.json()["delivery_id"]]

    repository = RepositoryRef(github_id=123, owner="sinh2206", name="MaintainerFlow")
    opened = IssueSource(
        repository=repository,
        github_id=901,
        number=41,
        title="Crash and exception when login token expires",
        body="This is reproducible for all users in production.",
        url="https://github.test/issues/41",
    )
    duplicate = opened.model_copy(
        update={
            "github_id": 800,
            "number": 12,
            "url": "https://github.test/issues/12",
            "title": "Login crashes when token expires",
        }
    )
    settings = Settings(
        environment="test",
        github_app_id=1,
        github_webhook_secret=webhook_secret,
        github_private_key="unused-in-contract-test",
        database_url=database_url,
        redis_url="redis://localhost:6379/15",
        workflow_enabled=True,
        issue_triage_enabled=True,
    )
    token_requests: list[bool] = []

    class FakeAuth:
        async def installation_token(
            self,
            installation_id: int,
            *,
            repository_id: int | None = None,
            issues_read: bool = False,
            checks_write: bool = True,
        ) -> SecretStr:
            assert (installation_id, repository_id) == (77, 123)
            token_requests.append(issues_read)
            assert not checks_write
            return SecretStr("installation-token")

    class FakeGitHub:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def fetch_issue(self, *_: object) -> IssueSource:
            return opened

        async def list_issues(self, *_: object) -> tuple[IssueSource, ...]:
            return (opened, duplicate)

        async def list_repository_labels(self, *_: object) -> tuple[str, ...]:
            return ("bug", "enhancement", "documentation")

    monkeypatch.setattr(tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(tasks, "_authenticator", lambda _: FakeAuth())
    monkeypatch.setattr(tasks, "GitHubClient", FakeGitHub)

    asyncio.run(tasks._process_delivery(queued[0]))

    async def verify() -> None:
        database = Database(database_url)
        try:
            async with database.session() as session:
                delivery = await session.get(Delivery, queued[0])
                result = await session.scalar(select(IssueAnalysisRecord))
                audit = await session.scalar(select(AuditEvent))
                assert delivery is not None
                assert delivery.status == DeliveryStatus.COMPLETED.value
                assert result is not None and result.classification == "bug"
                assert result.body_text is None
                assert result.similar_issues[0]["number"] == 12
                assert audit is not None and audit.issue_analysis_id == result.id
                assert audit.payload["side_effects"] == []
                assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 0
                assert await session.scalar(select(func.count()).select_from(AnalysisRecord)) == 0
        finally:
            await database.dispose()

    asyncio.run(verify())
    assert token_requests == [True]
