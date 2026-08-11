from sqlalchemy import select

from maintainerflow.core.schemas import RepositoryRef
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import Repository
from maintainerflow.persistence.repositories import DeliveryRepository
from tests.helpers import make_envelope


async def test_duplicate_delivery_is_idempotent(database: Database) -> None:
    async with database.session() as session:
        repository = DeliveryRepository(session)
        async with session.begin():
            first, first_created = await repository.create("same-id", make_envelope(), "request-1")
        async with session.begin():
            second, second_created = await repository.create(
                "same-id", make_envelope(), "request-2"
            )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


async def test_repository_metadata_updates_without_duplicate(database: Database) -> None:
    initial = make_envelope()
    changed = initial.model_copy(
        update={"repository": RepositoryRef(github_id=1, owner="new-owner", name="new-name")}
    )
    async with database.session() as session:
        repository = DeliveryRepository(session)
        async with session.begin():
            await repository.create("id-1", initial, "request-1")
        async with session.begin():
            await repository.create("id-2", changed, "request-2")

    async with database.session() as session:
        delivery = await DeliveryRepository(session).get_by_github_id("id-2")
        assert delivery is not None
        stored_repository = await session.scalar(
            select(Repository).where(Repository.id == delivery.repository_id)
        )
        assert stored_repository is not None
        assert stored_repository.owner == "new-owner"
