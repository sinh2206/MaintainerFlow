from pathlib import Path

from sqlalchemy import func, select

from maintainerflow.config import Settings
from maintainerflow.core.enums import DeliveryStatus
from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.persistence.database import Database
from maintainerflow.persistence.models import AnalysisRecord, OutboxEvent
from maintainerflow.persistence.repositories import DeliveryRepository
from maintainerflow.services.process_pull_request import persist_pull_request_analysis
from tests.helpers import make_envelope

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json"


async def test_cp1_delivery_creates_cp2_analysis_and_cp3_outbox(database: Database) -> None:
    envelope = make_envelope()
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_copy(
        update={
            "repository": envelope.repository,
            "number": envelope.pull_request.number,
            "base_sha": envelope.pull_request.base_sha,
            "head_sha": envelope.pull_request.head_sha,
        }
    )
    settings = Settings(
        environment="test",
        github_app_id=1,
        github_webhook_secret="test-webhook-secret-value",
        github_private_key="unused-in-service-test",
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/15",
        workflow_enabled=True,
        check_publish_enabled=True,
    )

    async with database.session() as session:
        deliveries = DeliveryRepository(session)
        async with session.begin():
            delivery, _ = await deliveries.create("bridge", envelope, "request")
            await deliveries.mark_queued(delivery.id)
            assert await deliveries.claim(delivery.id, 60)
        async with session.begin():
            run = await persist_pull_request_analysis(
                session,
                delivery_id=delivery.id,
                repository_id=delivery.repository_id,
                envelope=envelope,
                source=source,
                settings=settings,
            )

        stored = await deliveries.get(delivery.id)
        assert run.analysis_id is not None
        assert stored is not None and stored.status == DeliveryStatus.COMPLETED.value
        assert await session.scalar(select(func.count()).select_from(AnalysisRecord)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
