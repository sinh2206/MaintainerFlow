from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, cast

import anyio
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.config import Settings
from maintainerflow.persistence.database import Database

EnqueueDelivery = Callable[[int], Awaitable[None]]


def get_settings_from_request(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.session() as session:
        yield session


async def _enqueue_delivery(delivery_id: int) -> None:
    from maintainerflow.worker.tasks import process_delivery

    await anyio.to_thread.run_sync(process_delivery.send, delivery_id)


def get_enqueue_delivery() -> EnqueueDelivery:
    return _enqueue_delivery


SettingsDep = Annotated[Settings, Depends(get_settings_from_request)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
EnqueueDep = Annotated[EnqueueDelivery, Depends(get_enqueue_delivery)]
DatabaseDep = Annotated[Database, Depends(get_database)]
