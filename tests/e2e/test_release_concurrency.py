import json
import os
import subprocess
import uuid

import pytest

pytestmark = pytest.mark.e2e

PROBE = r"""
import asyncio
import json
import os

from sqlalchemy import func, select

from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import GitHubInstallation, ReleaseDraftRecord, Repository
from maintainerflow.persistence.releases import ReleaseDraftRepository
from maintainerflow.release.schemas import Changelog, ReleaseDraft


async def main():
    database = Database(os.environ["MAINTAINERFLOW_DATABASE_URL"])
    async with database.session() as session:
        async with session.begin():
            installation = GitHubInstallation(github_id=99001)
            session.add(installation)
            await session.flush()
            repository = Repository(
                github_id=99002,
                installation_id=installation.id,
                owner="race",
                name="fixture",
            )
            session.add(repository)
            await session.flush()
            repository_id = repository.id

    draft = ReleaseDraft(
        repository="race/fixture",
        from_ref="v0.4.0",
        to_ref="v1.0.0",
        compare_url="https://github.test/race/fixture/compare/v0.4.0...v1.0.0",
        changelog=Changelog(),
        markdown="# race/fixture v1.0.0\n",
    )
    start = asyncio.Event()

    async def save():
        async with database.session() as session:
            async with session.begin():
                await start.wait()
                row, created = await ReleaseDraftRepository(session).save(
                    repository_id, "f" * 64, draft
                )
                return row.id, created

    tasks = (asyncio.create_task(save()), asyncio.create_task(save()))
    await asyncio.sleep(0)
    start.set()
    results = await asyncio.gather(*tasks)
    async with database.session() as session:
        count = await session.scalar(select(func.count()).select_from(ReleaseDraftRecord))
    await database.dispose()
    print(json.dumps({"results": results, "count": count}, sort_keys=True))


asyncio.run(main())
"""


def command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=True, capture_output=True, text=True, timeout=120)


def psql(database: str, sql: str) -> None:
    command(
        "docker",
        "compose",
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "maintainerflow",
        "-d",
        database,
        "-c",
        sql,
    )


def test_two_postgres_transactions_racing_same_release_create_exactly_one_row() -> None:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("set RUN_E2E=1 after starting Docker Compose")
    database = f"maintainerflow_release_race_{uuid.uuid4().hex[:10]}"
    psql("postgres", f'CREATE DATABASE "{database}"')
    url = f"postgresql+asyncpg://maintainerflow:maintainerflow@db:5432/{database}"
    try:
        command(
            "docker",
            "compose",
            "run",
            "--rm",
            "--no-deps",
            "-e",
            f"MAINTAINERFLOW_DATABASE_URL={url}",
            "migrate",
            "alembic",
            "upgrade",
            "head",
        )
        completed = command(
            "docker",
            "compose",
            "run",
            "--rm",
            "--no-deps",
            "-e",
            f"MAINTAINERFLOW_DATABASE_URL={url}",
            "api",
            "python",
            "-c",
            PROBE,
        )
        report = json.loads(completed.stdout.strip().splitlines()[-1])

        assert report["count"] == 1
        assert sorted(result[1] for result in report["results"]) == [False, True]
        assert len({result[0] for result in report["results"]}) == 1
    finally:
        psql("postgres", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
