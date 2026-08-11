import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from maintainerflow.api.dependencies import get_enqueue_delivery
from maintainerflow.api.main import create_app
from maintainerflow.config import Settings
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import Base


@pytest.fixture
def webhook_secret() -> str:
    return "test-webhook-secret-value"


@pytest.fixture
def github_payload() -> dict[str, object]:
    return {
        "action": "opened",
        "installation": {"id": 77},
        "repository": {
            "id": 123,
            "name": "MaintainerFlow",
            "owner": {"login": "sinh2206"},
        },
        "pull_request": {
            "number": 5,
            "base": {"sha": "a" * 40},
            "head": {"sha": "b" * 40},
        },
    }


async def _create_schema(database_url: str) -> None:
    database = Database(database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.dispose()


@pytest.fixture
def app_client(tmp_path: Path, webhook_secret: str) -> Iterator[tuple[TestClient, list[int], str]]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    asyncio.run(_create_schema(database_url))
    settings = Settings(
        environment="test",
        github_app_id=1,
        github_webhook_secret=webhook_secret,
        database_url=database_url,
        redis_url="redis://localhost:6379/15",
    )
    application = create_app(settings)
    queued: list[int] = []

    async def fake_enqueue(delivery_id: int) -> None:
        queued.append(delivery_id)

    application.dependency_overrides[get_enqueue_delivery] = lambda: fake_enqueue
    with TestClient(application) as client:
        yield client, queued, database_url


@pytest_asyncio.fixture
async def database() -> AsyncIterator[Database]:
    database = Database("sqlite+aiosqlite:///:memory:")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database
    await database.dispose()
