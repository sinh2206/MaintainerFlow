from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

from maintainerflow.core.errors import PermanentDependencyError, TransientDependencyError
from maintainerflow.core.schemas import GitHubCheckCommand
from maintainerflow.github.checks import GitHubChecksClient, GitHubRateLimitError
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.outbox import OutboxRepository


def command() -> GitHubCheckCommand:
    return GitHubCheckCommand(
        analysis_id=1,
        installation_id=2,
        repository_github_id=3,
        owner="owner",
        repository="repo",
        head_sha="a" * 40,
        external_id="1",
        conclusion="neutral",
        title="Report",
        summary="Summary",
    )


@pytest.mark.parametrize(
    ("status", "headers", "error"),
    [
        (500, {}, TransientDependencyError),
        (429, {"retry-after": "7"}, GitHubRateLimitError),
        (404, {}, PermanentDependencyError),
    ],
)
async def test_github_errors_are_classified(
    status: int, headers: dict[str, str], error: type[Exception]
) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, headers=headers))
    client = GitHubChecksClient(SecretStr("token"), client=httpx.AsyncClient(transport=transport))
    with pytest.raises(error) as caught:
        await client.publish(command())
    if isinstance(caught.value, GitHubRateLimitError):
        assert caught.value.retry_after == 7


async def test_retry_lease_and_dead_letter_store_only_safe_error(database: Database) -> None:
    async with database.session() as session:
        outbox = OutboxRepository(session)
        async with session.begin():
            event, _ = await outbox.enqueue(
                event_type="github_check.publish",
                aggregate_id="1",
                idempotency_key="check:1",
                payload=command().model_dump(mode="json"),
            )
        async with session.begin():
            [claimed] = await outbox.claim(1, 10)
            await outbox.retry(claimed.id, "token=ghp_secret_value", 1)
        assert claimed.last_error == "token__REDACTED_"
        claimed.available_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        async with session.begin():
            [claimed_again] = await outbox.claim(1, 10)
            await outbox.dead_letter(claimed_again.id, "github_http_403")
        assert claimed_again.attempts == 2
        assert claimed_again.status == "dead_letter"


async def test_retry_after_lost_response_reuses_existing_check() -> None:
    methods: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"check_runs": [{"id": 99, "external_id": "1"}]})
        return httpx.Response(200, json={})

    client = GitHubChecksClient(
        SecretStr("token"), client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    )
    assert await client.publish(command()) == 99
    assert methods == ["GET", "PATCH", "PATCH"]
