from datetime import UTC, datetime, timedelta

from maintainerflow.core.enums import DeliveryStatus
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.repositories import DeliveryRepository
from tests.helpers import make_envelope


async def test_claim_retry_and_completion(database: Database) -> None:
    async with database.session() as session:
        repository = DeliveryRepository(session)
        async with session.begin():
            delivery, _ = await repository.create("retry-id", make_envelope(), "request")
            await repository.mark_queued(delivery.id)

        async with session.begin():
            assert await repository.claim(delivery.id, lease_seconds=60)
        async with session.begin():
            await repository.release_for_retry(delivery.id, "simulated crash")
        async with session.begin():
            assert await repository.claim(delivery.id, lease_seconds=60)
        async with session.begin():
            await repository.complete(delivery.id)

        stored = await repository.get(delivery.id)
        assert stored is not None
        assert stored.status == DeliveryStatus.COMPLETED.value
        assert stored.attempts == 2
        assert stored.last_error is None


async def test_recovery_finds_stale_queued_delivery(database: Database) -> None:
    async with database.session() as session:
        repository = DeliveryRepository(session)
        async with session.begin():
            delivery, _ = await repository.create("stale-id", make_envelope(), "request")
            await repository.mark_queued(delivery.id)
            delivery.queued_at = datetime.now(UTC) - timedelta(minutes=10)

        ids = await repository.recoverable_ids(datetime.now(UTC) - timedelta(minutes=1), 100)

    assert ids == [delivery.id]
