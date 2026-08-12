import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from maintainerflow.core.schemas import DeliveryEnvelope
from maintainerflow.persistence.repositories import DeliveryRepository

logger = logging.getLogger(__name__)
EnqueueDelivery = Callable[[int], Awaitable[None]]


@dataclass(frozen=True)
class RecordDeliveryResult:
    delivery_id: int
    created: bool


async def record_and_enqueue_delivery(
    session: AsyncSession,
    envelope: DeliveryEnvelope,
    github_delivery_id: str,
    request_id: str,
    enqueue: EnqueueDelivery,
) -> RecordDeliveryResult:
    repository = DeliveryRepository(session)
    async with session.begin():
        delivery, created = await repository.create(github_delivery_id, envelope, request_id)

    if not created:
        return RecordDeliveryResult(delivery.id, False)

    try:
        await enqueue(delivery.id)
    except Exception:
        logger.exception(
            "delivery enqueue failed; recovery will retry",
            extra={"delivery_id": delivery.id},
        )
        return RecordDeliveryResult(delivery.id, True)

    async with session.begin():
        await repository.mark_queued(delivery.id)
    return RecordDeliveryResult(delivery.id, True)
