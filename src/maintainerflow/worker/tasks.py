import asyncio
from datetime import UTC, datetime, timedelta

import dramatiq

from maintainerflow.config import get_settings
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.repositories import DeliveryRepository
from maintainerflow.worker.broker import broker as broker


async def _process_delivery(delivery_id: int) -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            repository = DeliveryRepository(session)
            async with session.begin():
                claimed = await repository.claim(delivery_id, settings.delivery_lease_seconds)
            if not claimed:
                return

            try:
                # Checkpoint 1 proves safe ingestion. Later checkpoints dispatch analysis here.
                async with session.begin():
                    await repository.complete(delivery_id)
            except Exception as exc:
                async with session.begin():
                    await repository.release_for_retry(delivery_id, type(exc).__name__)
                raise
    finally:
        await database.dispose()


@dramatiq.actor(queue_name="deliveries", max_retries=5, min_backoff=1_000, max_backoff=60_000)
def process_delivery(delivery_id: int) -> None:
    asyncio.run(_process_delivery(delivery_id))


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


@dramatiq.actor(queue_name="maintenance", max_retries=3, min_backoff=2_000)
def recover_deliveries() -> None:
    for delivery_id in asyncio.run(_find_recoverable()):
        process_delivery.send(delivery_id)
